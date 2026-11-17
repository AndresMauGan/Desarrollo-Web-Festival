"""
Pruebas de perfiles, permisos, páginas de error y despliegue (entrega final, Parte C).

- Cada perfil (anónimo, votante, administración del festival, superusuario) ve y hace solo lo que le corresponde.
- El grupo «Administración del festival» puede crear una edición, pero no administrar usuarios.
- Las páginas de error responden con su código y en español.
- «check --deploy» no da advertencias con la configuración de producción de ejemplo de .env.example.
"""

import os
import re
import subprocess
import sys
from io import StringIO

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import CommandError, call_command
from django.core.management.utils import get_random_secret_key
from django.template.loader import render_to_string
from django.test import Client, TestCase, override_settings
from django.urls import include, path, reverse

from festival.models import Edicion
from votos.test_casos_prueba import crear_escenario

from .grupos import GRUPO_ADMINISTRACION, PERMISOS_ADMINISTRACION, crear_grupo_administracion


def vista_que_falla(request):
    raise RuntimeError("Error provocado por la prueba de la página 500")


# Rutas para la prueba de la página 500: las del proyecto más una vista que falla
urlpatterns = [path("error-de-prueba/", vista_que_falla), path("", include("config.urls"))]


class PerfilesBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        crear_escenario(cls)  # Ana y Beto son votantes
        grupo, _ = crear_grupo_administracion()
        Usuario = get_user_model()
        cls.admin_festival = Usuario.objects.create_user(email="admin.festival@example.com",
                                                         nombre_para_mostrar="Administración", is_staff=True)
        cls.admin_festival.groups.add(grupo)
        cls.tecnico = Usuario.objects.create_superuser(email="tecnico@example.com", nombre_para_mostrar="Técnico")

    def entrar(self, usuario):
        self.client.force_login(usuario)


class GrupoDeAdministracionTests(PerfilesBase):
    def test_crear_grupos_es_idempotente_y_con_los_permisos_exactos(self):
        salida = StringIO()
        call_command("crear_grupos", stdout=salida)
        call_command("crear_grupos", stdout=salida)
        self.assertIn("actualizado", salida.getvalue())
        grupo = Group.objects.get(name=GRUPO_ADMINISTRACION)
        self.assertEqual(Group.objects.filter(name=GRUPO_ADMINISTRACION).count(), 1)
        tiene = {f"{p.content_type.app_label}.{p.codename}" for p in grupo.permissions.select_related("content_type")}
        self.assertEqual(tiene, set(PERMISOS_ADMINISTRACION))
        self.assertFalse(any(p.startswith("cuentas.") or "delete" in p for p in tiene))

    def test_asignar_el_perfil_a_una_cuenta_existente(self):
        call_command("crear_grupos", "--asignar", "BETO@example.com", stdout=StringIO())
        self.beto.refresh_from_db()
        self.assertTrue(self.beto.is_staff)
        self.assertTrue(self.beto.has_perm("votos.ver_resultados"))
        with self.assertRaises(CommandError):
            call_command("crear_grupos", "--asignar", "nadie@example.com", stdout=StringIO())


class MenuSegunElPerfilTests(PerfilesBase):
    ENLACES = {"mis_votos": 'href="/votar/mis-votos/"', "resultados": 'href="/resultados/"',
               "administracion": 'href="/admin/"', "salir": "Cerrar sesión"}

    def test_cada_perfil_ve_solo_sus_opciones(self):
        casos = {
            "anónimo": (None, set()),
            "votante": (self.ana, {"mis_votos", "salir"}),
            "administración del festival": (self.admin_festival, {"mis_votos", "resultados", "administracion", "salir"}),
            "superusuario": (self.tecnico, {"mis_votos", "resultados", "administracion", "salir"}),
        }
        for perfil, (usuario, esperados) in casos.items():
            with self.subTest(perfil):
                self.client.logout()
                if usuario:
                    self.entrar(usuario)
                html = self.client.get(reverse("festival:inicio")).content.decode()
                visibles = {nombre for nombre, marca in self.ENLACES.items() if marca in html}
                self.assertEqual(visibles, esperados)


class AccesoSinPermisoTests(PerfilesBase):
    def test_votante_en_el_admin_ve_el_inicio_de_sesion_con_el_aviso(self):
        self.entrar(self.ana)
        respuesta = self.client.get("/admin/", follow=True)
        self.assertEqual(respuesta.redirect_chain[-1][0], "/admin/login/?next=/admin/")
        self.assertContains(respuesta, "no está autorizado")
        self.assertContains(respuesta, self.ana.email)

    def test_votante_en_resultados_recibe_403_en_espanol(self):
        self.entrar(self.ana)
        respuesta = self.client.get(reverse("resultados:panel"))
        self.assertEqual(respuesta.status_code, 403)
        self.assertTemplateUsed(respuesta, "403.html")
        self.assertContains(respuesta, "No tienes permiso para ver esta página", status_code=403)

    def test_anonimo_va_al_inicio_de_sesion_con_next(self):
        for url in (reverse("resultados:panel"), reverse("votos:mis_votos"), reverse("cuentas:cuenta")):
            with self.subTest(url):
                self.assertRedirects(self.client.get(url), f"{reverse('cuentas:login')}?next={url}", fetch_redirect_response=False)


class AdministracionDelFestivalTests(PerfilesBase):
    def test_puede_crear_una_edicion(self):
        self.entrar(self.admin_festival)
        self.assertEqual(self.client.get("/admin/").status_code, 200)
        respuesta = self.client.post(reverse("admin:festival_edicion_add"), {
            "numero": 61, "anio": 2028, "nombre": "61.º Festival de la Leyenda Vallenata", "homenaje": "",
            "fecha_inicio": "26/04/2028", "fecha_fin": "29/04/2028",
            "categorias-TOTAL_FORMS": 0, "categorias-INITIAL_FORMS": 0, "categorias-MIN_NUM_FORMS": 0, "categorias-MAX_NUM_FORMS": 1000,
        })
        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(Edicion.objects.filter(anio=2028).exists())

    def test_consulta_votos_auditoria_y_resultados(self):
        self.entrar(self.admin_festival)
        for url in ("/admin/votos/voto/", "/admin/votos/registroauditoria/", reverse("resultados:panel")):
            with self.subTest(url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_no_administra_usuarios_ni_grupos_ni_borra(self):
        self.entrar(self.admin_festival)
        for url in ("/admin/cuentas/usuario/", "/admin/cuentas/usuario/add/", f"/admin/cuentas/usuario/{self.ana.pk}/change/",
                    "/admin/auth/group/", f"/admin/festival/edicion/{self.edicion.pk}/delete/"):
            with self.subTest(url):
                self.assertEqual(self.client.get(url).status_code, 403)
        self.assertNotContains(self.client.get("/admin/"), "/admin/cuentas/usuario/")

    def test_el_superusuario_si_administra_usuarios(self):
        self.entrar(self.tecnico)
        self.assertEqual(self.client.get("/admin/cuentas/usuario/").status_code, 200)


class PaginasDeErrorTests(TestCase):
    def test_404(self):
        self.assertContains(self.client.get("/no-existe/"), "No encontramos esta página", status_code=404)

    def test_400_por_un_host_no_permitido(self):
        with self.assertLogs("django.security", "ERROR"):
            respuesta = self.client.get("/", HTTP_HOST="sitio-no-permitido.example")
        self.assertContains(respuesta, "No pudimos procesar la solicitud", status_code=400)

    @override_settings(ROOT_URLCONF="cuentas.test_permisos")
    def test_500_en_espanol(self):
        cliente = Client(raise_request_exception=False)
        with self.assertLogs("django.request", "ERROR"):
            respuesta = cliente.get("/error-de-prueba/")
        self.assertContains(respuesta, "Algo salió mal de nuestro lado", status_code=500)

    def test_la_pagina_500_no_consulta_la_base_de_datos(self):
        with self.assertNumQueries(0):
            html = render_to_string("500.html")  # Django la renderiza sin contexto
        self.assertIn("Algo salió mal", html)

    def test_fallo_de_csrf(self):
        # Sin la cookie CSRF, el formulario se rechaza antes de mirar sus datos
        respuesta = Client(enforce_csrf_checks=True).post(reverse("cuentas:login"), {"username": "x@example.com"})
        self.assertEqual(respuesta.status_code, 403)
        self.assertTemplateUsed(respuesta, "403_csrf.html")
        self.assertContains(respuesta, "El formulario venció", status_code=403)

    def test_registro_de_errores_en_logs_fuera_de_git(self):
        archivo = settings.LOGGING["handlers"]["archivo"]
        self.assertEqual(archivo["filename"].parent, settings.BASE_DIR / "logs")
        self.assertEqual(archivo["class"], "logging.handlers.RotatingFileHandler")
        self.assertIn("logs/", (settings.BASE_DIR / ".gitignore").read_text(encoding="utf-8").splitlines())


class DespliegueTests(TestCase):
    @staticmethod
    def configuracion_de_produccion():
        """El bloque «Producción (ejemplo…)» de .env.example, con una SECRET_KEY generada en el momento."""
        texto = (settings.BASE_DIR / ".env.example").read_text(encoding="utf-8")
        bloque = texto.split("# Producción (ejemplo", 1)[1]
        valores = dict(re.findall(r"^#\s+(DJANGO_[A-Z_]+)=(.*)$", bloque, re.MULTILINE))
        valores["DJANGO_SECRET_KEY"] = get_random_secret_key()
        return valores

    def check_deploy(self, **variables):
        entorno = {**os.environ, "DJANGO_SETTINGS_MODULE": "config.settings", "PYTHONIOENCODING": "utf-8", **variables}
        return subprocess.run([sys.executable, "manage.py", "check", "--deploy", "--fail-level", "WARNING"],
                              cwd=settings.BASE_DIR, env=entorno, capture_output=True, text=True, encoding="utf-8", timeout=120)

    def test_check_deploy_sin_advertencias_con_la_configuracion_de_produccion(self):
        resultado = self.check_deploy(**self.configuracion_de_produccion())
        self.assertEqual(resultado.returncode, 0, resultado.stdout + resultado.stderr)
        self.assertIn("no issues", resultado.stdout + resultado.stderr)

    def test_check_deploy_avisa_con_la_configuracion_de_desarrollo(self):
        desarrollo = {clave: "" for clave in self.configuracion_de_produccion()} | {
            "DJANGO_DEBUG": "True", "DJANGO_SECRET_KEY": get_random_secret_key()}
        resultado = self.check_deploy(**desarrollo)
        self.assertNotEqual(resultado.returncode, 0)
        self.assertIn("security.W018", resultado.stdout + resultado.stderr)  # DEBUG activo
