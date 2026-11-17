"""
Pruebas de administración dinámica (entrega final, Parte B).

- Una sola edición activa (Edicion.save) y el aviso del admin.
- Acciones de Votación «Abrir», «Pausar» y «Cerrar», con RN-11 y registro de auditoría.
- Acción «Duplicar la edición».
- Validaciones del admin y ausencia de textos fijos de una edición.
- Integración «Festival 2028 sin tocar el código», solo a través de las URLs del admin.
"""

import json
import re
from datetime import date, timedelta
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from votos.models import RegistroAuditoria, Voto
from votos.test_casos_prueba import crear_escenario, nuevas_opciones, nueva_votacion

from .models import Categoria, Edicion, Opcion, Votacion

Estado = Votacion.Estado
local = timezone.localtime


def fecha_admin(valor):
    return valor.strftime("%d/%m/%Y")


def hora_admin(valor):
    return local(valor).strftime("%H:%M:%S")


class AdminBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        crear_escenario(cls)  # 2027 activa (Acordeonera Mayor y Piquería Mayor abiertas) y 2026 inactiva
        cls.tecnico = get_user_model().objects.create_superuser(email="tecnico@example.com", nombre_para_mostrar="Técnico")

    def setUp(self):
        self.client.force_login(self.tecnico)

    def mensajes(self, respuesta):
        return [str(m) for m in get_messages(respuesta.wsgi_request)]

    def accion(self, modelo, accion, *objetos, **extra):
        datos = {"action": accion, "_selected_action": [o.pk for o in objetos], **extra}
        return self.client.post(reverse(f"admin:festival_{modelo}_changelist"), datos)

    def datos_edicion(self, edicion, **cambios):
        """Formulario del admin de una edición existente, con sus categorías en línea sin cambios."""
        datos = {
            "numero": edicion.numero, "anio": edicion.anio, "nombre": edicion.nombre, "homenaje": edicion.homenaje,
            "fecha_inicio": fecha_admin(edicion.fecha_inicio), "fecha_fin": fecha_admin(edicion.fecha_fin),
        }
        if edicion.activa:
            datos["activa"] = "on"
        categorias = list(edicion.categorias.order_by("pk"))
        datos.update({"categorias-TOTAL_FORMS": len(categorias), "categorias-INITIAL_FORMS": len(categorias),
                      "categorias-MIN_NUM_FORMS": 0, "categorias-MAX_NUM_FORMS": 1000})
        for i, c in enumerate(categorias):
            datos.update({f"categorias-{i}-id": c.pk, f"categorias-{i}-edicion": edicion.pk, f"categorias-{i}-nombre": c.nombre,
                          f"categorias-{i}-familia": c.familia, f"categorias-{i}-nivel": c.nivel, f"categorias-{i}-orden": c.orden})
            if c.admite_voto_publico:
                datos[f"categorias-{i}-admite_voto_publico"] = "on"
            if c.publicada:
                datos[f"categorias-{i}-publicada"] = "on"
        datos.update(cambios)
        return {k: v for k, v in datos.items() if v is not None}


class UnaSolaEdicionActivaTests(AdminBase):
    def test_al_activar_una_edicion_se_desactivan_las_demas(self):
        self.edicion_anterior.activa = True
        self.edicion_anterior.save()
        self.edicion.refresh_from_db()
        self.assertFalse(self.edicion.activa)
        self.assertEqual(list(Edicion.objects.filter(activa=True)), [self.edicion_anterior])
        self.assertEqual(self.edicion_anterior.ediciones_desactivadas, [self.edicion])

    def test_guardar_otros_campos_no_cambia_la_activa(self):
        Edicion.objects.filter(pk=self.edicion_anterior.pk).update(activa=True)  # dato heredado: dos activas
        self.edicion.nombre = "Nombre corregido"
        self.edicion.save(update_fields=["nombre"])
        self.assertEqual(Edicion.objects.filter(activa=True).count(), 2)

    def test_el_admin_explica_que_desactivo_la_otra(self):
        url = reverse("admin:festival_edicion_change", args=[self.edicion_anterior.pk])
        respuesta = self.client.post(url, self.datos_edicion(self.edicion_anterior, activa="on"))
        self.assertEqual(respuesta.status_code, 302)
        self.edicion.refresh_from_db()
        self.assertFalse(self.edicion.activa)
        self.assertTrue(any("es ahora la edición activa" in m and "Solo puede haber una" in m for m in self.mensajes(respuesta)))
        self.assertTrue(RegistroAuditoria.objects.filter(accion="Edición activada", usuario=self.tecnico).exists())
        self.assertContains(self.client.get(url), "Solo puede haber una edición activa")


class AccionesDeVotacionTests(AdminBase):
    def test_abrir_pausar_y_cerrar_con_auditoria(self):
        for accion, estado, registro in (("pausar", Estado.PAUSADA, "Votación pausada"),
                                         ("abrir", Estado.ABIERTA, "Votación abierta"),
                                         ("cerrar", Estado.CERRADA, "Votación cerrada")):
            with self.subTest(accion):
                respuesta = self.accion("votacion", accion, self.grupo_a)
                self.assertEqual(respuesta.status_code, 302)
                self.grupo_a.refresh_from_db()
                self.assertEqual(self.grupo_a.estado, estado)
                self.assertTrue(RegistroAuditoria.objects.filter(accion=registro, entidad_afectada=f"festival.Votacion #{self.grupo_a.pk}",
                                                                 usuario=self.tecnico).exists())

    def test_abrir_respeta_rn11(self):
        sola = nueva_votacion(self.piqueria, "Votación con una opción", estado=Estado.PROGRAMADA)
        nuevas_opciones(sola, "Pareja Ficticia Única")
        respuesta = self.accion("votacion", "abrir", sola)
        sola.refresh_from_db()
        self.assertEqual(sola.estado, Estado.PROGRAMADA)
        self.assertTrue(any("RN-11" in m for m in self.mensajes(respuesta)))
        self.assertFalse(RegistroAuditoria.objects.filter(accion="Votación abierta").exists())

    def test_avisa_si_se_abre_fuera_de_su_horario(self):
        futura = nueva_votacion(self.piqueria, "Votación futura", estado=Estado.PROGRAMADA, abre=timezone.now() + timedelta(days=3))
        nuevas_opciones(futura, "Pareja Ficticia F1", "Pareja Ficticia F2")
        respuesta = self.accion("votacion", "abrir", futura)
        futura.refresh_from_db()
        self.assertEqual(futura.estado, Estado.ABIERTA)
        self.assertTrue(any("todavía no empieza" in m and "RN-03" in m for m in self.mensajes(respuesta)))

    def test_transicion_no_permitida(self):
        Votacion.objects.filter(pk=self.grupo_a.pk).update(estado=Estado.CERRADA)
        respuesta = self.accion("votacion", "pausar", self.grupo_a)
        self.grupo_a.refresh_from_db()
        self.assertEqual(self.grupo_a.estado, Estado.CERRADA)
        self.assertIn("«Semifinal · Grupo A» no se puede pausar porque está cerrada.", self.mensajes(respuesta))


class DuplicarEdicionTests(AdminBase):
    def test_muestra_el_formulario_con_valores_sugeridos(self):
        respuesta = self.accion("edicion", "duplicar", self.edicion)
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.context["form"].initial["anio"], 2028)
        self.assertEqual(respuesta.context["form"].initial["nombre"], "61.º Festival de la Leyenda Vallenata")
        self.assertContains(respuesta, "No se copian opciones, votos ni registros de auditoría")

    def test_copia_categorias_sin_publicar_y_votaciones_en_borrador(self):
        respuesta = self.accion("edicion", "duplicar", self.edicion, aplicar="1", anio=2028, numero=61,
                                nombre="61.º Festival de la Leyenda Vallenata", fecha_inicio="2028-04-26", fecha_fin="2028-04-29")
        nueva = Edicion.objects.get(anio=2028)
        self.assertRedirects(respuesta, reverse("admin:festival_edicion_change", args=[nueva.pk]))
        self.assertFalse(nueva.activa)
        self.assertEqual(list(nueva.categorias.values_list("nombre", "publicada")),
                         [("Acordeonera Mayor", False), ("Piquería Mayor", False)])
        copias = Votacion.objects.filter(categoria__edicion=nueva).order_by("nombre")
        self.assertEqual(copias.count(), 3)
        self.assertEqual(set(copias.values_list("estado", flat=True)), {Estado.BORRADOR})
        desplazamiento = date(2028, 4, 26) - self.edicion.fecha_inicio
        original = Votacion.objects.get(pk=self.grupo_a.pk)
        copia = copias.get(nombre=original.nombre)
        self.assertEqual(copia.abre_en - original.abre_en, desplazamiento)
        self.assertFalse(Opcion.objects.filter(votacion__categoria__edicion=nueva).exists())
        self.assertFalse(Voto.objects.filter(edicion=nueva).exists())
        self.assertTrue(self.edicion.categorias.filter(publicada=True).exists())  # el original no cambia
        self.assertTrue(RegistroAuditoria.objects.filter(accion="Edición duplicada", entidad_afectada=f"festival.Edicion #{nueva.pk}").exists())

    def test_rechaza_un_anio_que_ya_existe(self):
        respuesta = self.accion("edicion", "duplicar", self.edicion, aplicar="1", anio=2026, numero=61,
                                nombre="Copia", fecha_inicio="2028-04-26", fecha_fin="2028-04-29")
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Ya existe una edición del año 2026.")
        self.assertEqual(Edicion.objects.count(), 2)

    def test_exige_una_sola_edicion(self):
        respuesta = self.accion("edicion", "duplicar", self.edicion, self.edicion_anterior)
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn("Elige exactamente una edición para duplicar.", self.mensajes(respuesta))


class ValidacionesDelAdminTests(AdminBase):
    def test_cierre_posterior_a_la_apertura(self):
        abre = timezone.now() + timedelta(days=1)
        datos = {"categoria": self.piqueria.pk, "nombre": "Votación con horario al revés", "ronda": "final", "estado": "programada",
                 "abre_en_0": fecha_admin(local(abre)), "abre_en_1": hora_admin(abre),
                 "cierra_en_0": fecha_admin(local(abre - timedelta(hours=2))), "cierra_en_1": hora_admin(abre - timedelta(hours=2)),
                 "visibilidad_resultados": "al_cierre",
                 "opciones-TOTAL_FORMS": 0, "opciones-INITIAL_FORMS": 0, "opciones-MIN_NUM_FORMS": 0, "opciones-MAX_NUM_FORMS": 1000}
        respuesta = self.client.post(reverse("admin:festival_votacion_add"), datos)
        self.assertContains(respuesta, "El cierre debe ser posterior a la apertura.")
        self.assertFalse(Votacion.objects.filter(nombre="Votación con horario al revés").exists())

    def test_nombre_de_categoria_unico_por_edicion(self):
        datos = {"edicion": self.edicion.pk, "nombre": "Piquería Mayor", "familia": "piqueria", "orden": 0}
        respuesta = self.client.post(reverse("admin:festival_categoria_add"), datos)
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(Categoria.objects.filter(edicion=self.edicion, nombre="Piquería Mayor").count(), 1)

    def test_sin_textos_fijos_de_una_edicion(self):
        """Ninguna plantilla ni vista tiene escrito un año o un número de edición: todo sale de la base de datos."""
        base = Path(settings.BASE_DIR)
        archivos = [*base.joinpath("templates").rglob("*.html"),
                    *(base / ruta for ruta in ("festival/views.py", "festival/api.py", "votos/views.py", "cuentas/views.py"))]
        patron = re.compile(r"\b(19|20)\d\d\b|\d+\.º")
        encontrados = [f"{archivo.relative_to(base)}:{n}" for archivo in archivos
                       for n, linea in enumerate(archivo.read_text(encoding="utf-8").splitlines(), 1) if patron.search(linea)]
        self.assertEqual(encontrados, [])


class Festival2028SinTocarElCodigoTests(AdminBase):
    """Configura la edición 2028 completa desde el admin, con client.post, y un votante vota en ella."""

    def test_festival_2028_sin_tocar_el_codigo(self):
        # 1. Edición 2028 con una categoría...
        respuesta = self.client.post(reverse("admin:festival_edicion_add"), {
            "numero": 61, "anio": 2028, "nombre": "61.º Festival de la Leyenda Vallenata", "homenaje": "",
            "fecha_inicio": "26/04/2028", "fecha_fin": "29/04/2028",
            "categorias-TOTAL_FORMS": 1, "categorias-INITIAL_FORMS": 0, "categorias-MIN_NUM_FORMS": 0, "categorias-MAX_NUM_FORMS": 1000,
            "categorias-0-nombre": "Acordeonero Profesional", "categorias-0-familia": "acordeon", "categorias-0-nivel": "Profesional",
            "categorias-0-admite_voto_publico": "on", "categorias-0-publicada": "on", "categorias-0-orden": 1,
        })
        self.assertEqual(respuesta.status_code, 302)
        edicion_2028 = Edicion.objects.get(anio=2028)
        categoria = edicion_2028.categorias.get()
        self.assertFalse(edicion_2028.activa)

        # ... una votación con horario y dos opciones
        abre, cierra = timezone.now() - timedelta(hours=1), timezone.now() + timedelta(days=2)
        respuesta = self.client.post(reverse("admin:festival_votacion_add"), {
            "categoria": categoria.pk, "nombre": "Final Acordeonero Profesional", "ronda": "final", "estado": "programada",
            "abre_en_0": fecha_admin(local(abre)), "abre_en_1": hora_admin(abre),
            "cierra_en_0": fecha_admin(local(cierra)), "cierra_en_1": hora_admin(cierra),
            "visibilidad_resultados": "al_cierre",
            "opciones-TOTAL_FORMS": 2, "opciones-INITIAL_FORMS": 0, "opciones-MIN_NUM_FORMS": 0, "opciones-MAX_NUM_FORMS": 1000,
            "opciones-0-nombre": "Acordeonero Ficticio 2028 A", "opciones-0-tipo": "persona", "opciones-0-orden": 1,
            "opciones-0-publicada": "on", "opciones-0-estado": "activa",
            "opciones-1-nombre": "Acordeonero Ficticio 2028 B", "opciones-1-tipo": "persona", "opciones-1-orden": 2,
            "opciones-1-publicada": "on", "opciones-1-estado": "activa",
        })
        self.assertEqual(respuesta.status_code, 302)
        votacion = Votacion.objects.get(categoria=categoria)
        self.assertEqual(votacion.opciones.count(), 2)

        # 2. Abre la votación y marca 2028 como activa
        self.accion("votacion", "abrir", votacion)
        votacion.refresh_from_db()
        self.assertEqual(votacion.estado, Estado.ABIERTA)
        respuesta = self.client.post(reverse("admin:festival_edicion_change", args=[edicion_2028.pk]),
                                     self.datos_edicion(edicion_2028, activa="on"))
        self.assertEqual(respuesta.status_code, 302)

        # 3. La edición anterior quedó inactiva
        self.edicion.refresh_from_db()
        self.assertFalse(self.edicion.activa)
        self.assertEqual(list(Edicion.objects.filter(activa=True)), [edicion_2028])

        # 4. El sitio, la página de votación y la API muestran 2028
        self.client.logout()
        inicio = self.client.get(reverse("festival:inicio"))
        self.assertContains(inicio, "61.º Festival de la Leyenda Vallenata")
        self.assertContains(inicio, "Acordeonero Profesional")
        self.assertNotContains(inicio, "60.º Festival")
        api = json.loads(self.client.get(reverse("festival:api_categorias")).content)
        self.assertEqual(api["edicion"]["anio"], 2028)
        self.assertEqual([c["nombre"] for c in api["categorias"]], ["Acordeonero Profesional"])
        self.client.force_login(self.ana)
        pagina = self.client.get(reverse("votos:votar", args=[categoria.pk]))
        self.assertContains(pagina, "61.º Festival de la Leyenda Vallenata")
        self.assertContains(pagina, "Acordeonero Ficticio 2028 A")
        # La categoría de 2027 ya no recibe votos: no es de la edición activa
        self.assertEqual(self.client.post(reverse("votos:confirmar", args=[self.acordeon.pk]), {"opcion": self.a1.pk}).status_code, 403)

        # 5. Un votante vota con éxito en 2028
        opcion = votacion.opciones.get(nombre="Acordeonero Ficticio 2028 A")
        respuesta = self.client.post(reverse("votos:confirmar", args=[categoria.pk]), {"opcion": opcion.pk})
        voto = Voto.objects.get(usuario=self.ana, edicion=edicion_2028)
        self.assertRedirects(respuesta, reverse("votos:comprobante", args=[voto.pk]))
        self.assertEqual((voto.categoria, voto.opcion), (categoria, opcion))
