"""
Casos de prueba CP-01 a CP-10 de la Entrega 3 (guía del Eje 3).

- CP-01 a CP-08 y CP-10 recorren el flujo real por HTTP (elegir → confirmar → comprobante) y comparan
  con lo que hay en la tabla votos_voto, leída con SQL directo.
- CP-09 usa TransactionTestCase: dos hilos, cada uno con su conexión a MySQL, llaman a la vez a registrar_voto.

Los usuarios de prueba se crean sin contraseña (inutilizable) y entran con force_login.
"""

import json
from datetime import date, timedelta
from datetime import timezone as dt_timezone
from unittest import skipUnless

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.contrib.messages import get_messages
from django.db import connection
from django.test import Client, TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from festival.models import Categoria, Edicion, Opcion, Votacion
from festival.templatetags.festival_extras import fecha_hora_co

from .concurrencia import votar_a_la_vez
from .models import RegistroAuditoria, Voto
from .servicios import VotoRechazado, huella, registrar_voto

Estado = Votacion.Estado

# Votos con su usuario, edición, categoría, votación y opción, leídos de MySQL sin pasar por el ORM
SQL_VOTOS = """
    SELECT v.id, u.email, e.anio, c.nombre, vo.nombre, o.nombre, v.fecha_hora
    FROM votos_voto v
    JOIN cuentas_usuario u ON u.id = v.usuario_id
    JOIN festival_edicion e ON e.id = v.edicion_id
    JOIN festival_categoria c ON c.id = v.categoria_id
    JOIN festival_votacion vo ON vo.id = v.votacion_id
    JOIN festival_opcion o ON o.id = v.opcion_id
"""


def nueva_categoria(edicion, nombre, familia=Categoria.Familia.ACORDEON, **campos):
    return Categoria.objects.create(edicion=edicion, nombre=nombre, familia=familia,
                                    **{"publicada": True, "admite_voto_publico": True, **campos})


def nueva_votacion(categoria, nombre, estado=Estado.ABIERTA, abre=None):
    """Por defecto, abierta desde hace una hora y hasta mañana (dentro de su horario, RN-03)."""
    abre = abre or timezone.now() - timedelta(hours=1)
    return Votacion.objects.create(categoria=categoria, nombre=nombre, ronda=Votacion.Ronda.SEMIFINAL,
                                   estado=estado, abre_en=abre, cierra_en=abre + timedelta(days=1))


def nuevas_opciones(votacion, *nombres):
    return [Opcion.objects.create(votacion=votacion, nombre=nombre, tipo=Opcion.Tipo.PERSONA, publicada=True, orden=n)
            for n, nombre in enumerate(nombres, 1)]


def crear_escenario(destino):
    """
    Edición 2027 activa y 2026 inactiva. En 2027:
    - Acordeonera Mayor: dos votaciones abiertas (subeventos A y B) con dos opciones cada una, y una sin publicar.
    - Piquería Mayor: una votación abierta con dos opciones.
    Votantes: Ana y Beto.
    """
    Usuario = get_user_model()
    destino.ana = Usuario.objects.create_user(email="ana@example.com", nombre_para_mostrar="Ana")
    destino.beto = Usuario.objects.create_user(email="beto@example.com", nombre_para_mostrar="Beto")
    destino.edicion = Edicion.objects.create(numero=60, anio=2027, nombre="60.º Festival de la Leyenda Vallenata",
                                             fecha_inicio=date(2027, 4, 28), fecha_fin=date(2027, 5, 1), activa=True)
    destino.edicion_anterior = Edicion.objects.create(numero=59, anio=2026, nombre="59.º Festival de la Leyenda Vallenata",
                                                      fecha_inicio=date(2026, 4, 29), fecha_fin=date(2026, 5, 2))
    destino.acordeon = nueva_categoria(destino.edicion, "Acordeonera Mayor", orden=1)
    destino.piqueria = nueva_categoria(destino.edicion, "Piquería Mayor", Categoria.Familia.PIQUERIA, orden=2)
    abre = timezone.now() - timedelta(hours=1)
    destino.grupo_a = nueva_votacion(destino.acordeon, "Semifinal · Grupo A", abre=abre)
    destino.grupo_b = nueva_votacion(destino.acordeon, "Semifinal · Grupo B", abre=abre)
    destino.final_piqueria = nueva_votacion(destino.piqueria, "Final Piquería Mayor", abre=abre)
    destino.a1, destino.a2 = nuevas_opciones(destino.grupo_a, "Acordeonera Ficticia A1", "Acordeonera Ficticia A2")
    destino.b1, destino.b2 = nuevas_opciones(destino.grupo_b, "Acordeonera Ficticia B1", "Acordeonera Ficticia B2")
    destino.p1, destino.p2 = nuevas_opciones(destino.final_piqueria, "Pareja Ficticia P1", "Pareja Ficticia P2")
    destino.a_sin_publicar = Opcion.objects.create(votacion=destino.grupo_a, nombre="Acordeonera Ficticia A3",
                                                   tipo=Opcion.Tipo.PERSONA, publicada=False)


class CasosDePruebaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        crear_escenario(cls)

    # Ayudas -----------------------------------------------------------------------------------------
    def url_votar(self, categoria):
        return reverse("votos:votar", args=[categoria.pk])

    def elegir(self, categoria, opcion_id):
        """Primer POST: elegir la opción (muestra la confirmación, todavía no registra)."""
        return self.client.post(self.url_votar(categoria), {"opcion": opcion_id})

    def confirmar(self, categoria, opcion_id):
        """Segundo POST: confirmar, que es el que llama a registrar_voto."""
        return self.client.post(reverse("votos:confirmar", args=[categoria.pk]), {"opcion": opcion_id})

    def mensajes(self, respuesta):
        return [str(m) for m in get_messages(respuesta.wsgi_request)]

    def filas_en_mysql(self, usuario=None):
        """(usuario, edición, categoría, votación, opción) de cada fila de votos_voto, con SQL directo."""
        sql, parametros = "SELECT usuario_id, edicion_id, categoria_id, votacion_id, opcion_id FROM votos_voto", []
        if usuario:
            sql, parametros = sql + " WHERE usuario_id = %s", [usuario.pk]
        with connection.cursor() as cursor:
            cursor.execute(sql + " ORDER BY id", parametros)
            return [tuple(fila) for fila in cursor.fetchall()]

    def fila(self, usuario, opcion):
        votacion = opcion.votacion
        return (usuario.pk, votacion.categoria.edicion_id, votacion.categoria_id, votacion.pk, opcion.pk)

    # CP-01 ------------------------------------------------------------------------------------------
    def test_cp01_voto_valido(self):
        """Un usuario autenticado elige una opción válida, confirma y queda un voto en MySQL."""
        self.client.force_login(self.ana)
        pagina = self.client.get(self.url_votar(self.acordeon))
        self.assertContains(pagina, self.a1.nombre)
        self.assertContains(pagina, "csrfmiddlewaretoken")

        confirmacion = self.elegir(self.acordeon, self.a1.pk)
        self.assertContains(confirmacion, "Confirma tu voto")
        self.assertContains(confirmacion, "Es irreversible")
        self.assertEqual(self.filas_en_mysql(), [], "Elegir no registra: falta confirmar")

        respuesta = self.confirmar(self.acordeon, self.a1.pk)
        voto = Voto.objects.get(usuario=self.ana)
        self.assertRedirects(respuesta, reverse("votos:comprobante", args=[voto.pk]))  # POST → redirección → GET
        self.assertEqual(self.mensajes(respuesta), ["Tu voto quedó registrado."])
        # Votación, categoría y edición se derivan de la opción
        self.assertEqual(self.filas_en_mysql(), [self.fila(self.ana, self.a1)])
        # La IP no se guarda en claro, solo su huella
        self.assertEqual(voto.huella_ip, huella("127.0.0.1"))
        self.assertContains(self.client.get(respuesta.url), voto.codigo_comprobante)

    # CP-02 ------------------------------------------------------------------------------------------
    def test_cp02_segundo_voto_en_la_misma_categoria_se_rechaza(self):
        """Después de votar, otro voto en la misma categoría se rechaza: misma opción, otra opción u otro subevento."""
        self.client.force_login(self.ana)
        self.confirmar(self.acordeon, self.a1.pk)
        intentos = {"la misma opción": self.a1, "otra opción del mismo subevento": self.a2,
                    "una opción de otro subevento": self.b1}
        for descripcion, opcion in intentos.items():
            with self.subTest(descripcion):
                respuesta = self.confirmar(self.acordeon, opcion.pk)
                self.assertEqual(respuesta.status_code, 403)
                self.assertIn("Ya votaste en esta categoría.", self.mensajes(respuesta))
                # Muestra el voto ya emitido, sin formulario
                self.assertContains(respuesta, self.a1.nombre, status_code=403)
                self.assertNotContains(respuesta, 'name="opcion"', status_code=403)

        self.assertEqual(self.elegir(self.acordeon, self.b2.pk).status_code, 403)
        with self.assertRaises(VotoRechazado) as rechazo:
            registrar_voto(self.ana, self.acordeon.pk, self.b2.pk)
        self.assertEqual((rechazo.exception.mensaje, rechazo.exception.estado_http), ("Ya votaste en esta categoría.", 403))

        self.assertEqual(self.filas_en_mysql(self.ana), [self.fila(self.ana, self.a1)])
        self.assertEqual(RegistroAuditoria.objects.filter(usuario=self.ana, accion="Voto rechazado: ya votó en la categoría").count(), 4)

    # CP-03 ------------------------------------------------------------------------------------------
    def test_cp03_voto_en_otra_categoria_se_permite(self):
        """Votar en una categoría no impide votar en otra de la misma edición."""
        self.client.force_login(self.ana)
        self.assertEqual(self.confirmar(self.acordeon, self.a1.pk).status_code, 302)
        segunda = self.confirmar(self.piqueria, self.p1.pk)
        self.assertRedirects(segunda, reverse("votos:comprobante", args=[Voto.objects.get(usuario=self.ana, categoria=self.piqueria).pk]))
        self.assertEqual(self.filas_en_mysql(self.ana), [self.fila(self.ana, self.a1), self.fila(self.ana, self.p1)])
        # Y otra persona puede votar en la categoría en la que Ana ya votó
        registrar_voto(self.beto, self.acordeon.pk, self.a1.pk)
        self.assertEqual(len(self.filas_en_mysql()), 3)

    # CP-04 ------------------------------------------------------------------------------------------
    def test_cp04_sin_sesion_se_exige_iniciar_sesion(self):
        """Sin sesión, votar redirige al inicio de sesión con «next» y no se registra nada."""
        login = reverse("cuentas:login")
        votar = self.url_votar(self.acordeon)
        intentos = {
            "abrir la página de votación": lambda: self.client.get(votar),
            "elegir una opción": lambda: self.elegir(self.acordeon, self.a1.pk),
            "confirmar el voto": lambda: self.confirmar(self.acordeon, self.a1.pk),
        }
        for descripcion, intento in intentos.items():
            with self.subTest(descripcion):
                self.assertRedirects(intento(), f"{login}?next={votar}", fetch_redirect_response=False)
        mis_votos = reverse("votos:mis_votos")
        self.assertRedirects(self.client.get(mis_votos), f"{login}?next={mis_votos}", fetch_redirect_response=False)

        # El servicio también rechaza a quien no inició sesión o tiene la cuenta inactiva
        inactiva = get_user_model().objects.create_user(email="inactiva@example.com", nombre_para_mostrar="Inactiva", is_active=False)
        for usuario in (AnonymousUser(), inactiva):
            with self.subTest(usuario=str(usuario)), self.assertRaises(VotoRechazado) as rechazo:
                registrar_voto(usuario, self.acordeon.pk, self.a1.pk)
            self.assertEqual(rechazo.exception.estado_http, 403)
        self.assertEqual(self.filas_en_mysql(), [])

    # CP-05 ------------------------------------------------------------------------------------------
    def test_cp05_categoria_no_habilitada_se_rechaza(self):
        """No se vota en categorías sin voto del público, de otra edición, sin votación abierta o sin publicar."""
        no_habilitada = ("Esta categoría no está habilitada para el voto del público.", "Voto rechazado: categoría no habilitada")
        sin_votacion = ("Esta categoría no tiene votaciones abiertas en este momento.", "Voto rechazado: votación cerrada o fuera de horario")
        casos = [
            # (descripción, categoría, estado de su votación, apertura, código HTTP, (mensaje, auditoría))
            ("no admite voto del público", nueva_categoria(self.edicion, "Rey de Reyes", admite_voto_publico=False), Estado.ABIERTA, None, 403, no_habilitada),
            ("es de una edición que no está activa", nueva_categoria(self.edicion_anterior, "Acordeonera Mayor"), Estado.ABIERTA, None, 403, no_habilitada),
            ("su votación está cerrada", nueva_categoria(self.edicion, "Canción Inédita", Categoria.Familia.CANCION), Estado.CERRADA, None, 403, sin_votacion),
            ("su votación está pausada", nueva_categoria(self.edicion, "Acordeonero Juvenil"), Estado.PAUSADA, None, 403, sin_votacion),
            ("su votación está abierta pero aún no empieza su horario (RN-03)", nueva_categoria(self.edicion, "Acordeonero Infantil"),
             Estado.ABIERTA, timezone.now() + timedelta(days=1), 403, sin_votacion),
            ("no está publicada", nueva_categoria(self.edicion, "Piquería Infantil", publicada=False), Estado.ABIERTA, None, 404,
             ("Esta categoría no existe o no está publicada.", "")),
        ]
        self.client.force_login(self.ana)
        for descripcion, categoria, estado, abre, codigo, (mensaje, accion) in casos:
            opcion, _ = nuevas_opciones(nueva_votacion(categoria, f"Votación de {categoria.nombre}", estado, abre),
                                        f"Opción Ficticia de {categoria.nombre} 1", f"Opción Ficticia de {categoria.nombre} 2")
            with self.subTest(descripcion):
                respuesta = self.confirmar(categoria, opcion.pk)
                self.assertEqual(respuesta.status_code, codigo)
                self.assertIn(mensaje, self.mensajes(respuesta))
                self.assertEqual(self.elegir(categoria, opcion.pk).status_code, codigo)
                pagina = self.client.get(self.url_votar(categoria))
                if codigo == 404:
                    self.assertEqual(pagina.status_code, 404)
                else:
                    self.assertContains(pagina, mensaje)  # explica el motivo y no muestra el formulario
                    self.assertNotContains(pagina, 'name="opcion"')
                    self.assertTrue(RegistroAuditoria.objects.filter(usuario=self.ana, accion=accion,
                                                                     entidad_afectada=f"festival.Categoria #{categoria.pk}").exists())
        self.assertEqual(self.filas_en_mysql(), [])

    # CP-06 ------------------------------------------------------------------------------------------
    def test_cp06_opcion_de_otra_categoria_se_rechaza(self):
        """Una opción de otra categoría (o que no corresponde) se rechaza y no se registra en ninguna categoría."""
        self.client.force_login(self.ana)
        # Al elegir, el formulario solo acepta las opciones de esta categoría
        eleccion = self.elegir(self.acordeon, self.p1.pk)
        self.assertEqual(eleccion.status_code, 400)
        self.assertIn("La opción elegida no es válida para esta categoría.", self.mensajes(eleccion))
        # Si alguien altera la confirmación, el servicio vuelve a validar en el servidor
        respuesta = self.confirmar(self.acordeon, self.p1.pk)
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("La opción elegida no corresponde a esta categoría.", self.mensajes(respuesta))
        self.assertTrue(RegistroAuditoria.objects.filter(usuario=self.ana, accion="Voto rechazado: opción de otra categoría").exists())

        otros_valores = {
            "opción sin publicar": (self.a_sin_publicar.pk, "La opción elegida no está disponible para votar."),
            "opción que no existe": (999999, "La opción elegida no está disponible para votar."),
            "valor que no es un número": ("abc", "Elige una opción válida."),
            "sin opción": ("", "Elige una opción válida."),
        }
        for descripcion, (valor, mensaje) in otros_valores.items():
            with self.subTest(descripcion):
                respuesta = self.confirmar(self.acordeon, valor)
                self.assertEqual(respuesta.status_code, 400)
                self.assertIn(mensaje, self.mensajes(respuesta))
        self.assertEqual(self.filas_en_mysql(), [])

        # Los rechazos no gastan el voto
        self.assertEqual(self.confirmar(self.acordeon, self.a1.pk).status_code, 302)

    # CP-07 ------------------------------------------------------------------------------------------
    def test_cp07_mis_votos_muestra_solo_los_registros_propios(self):
        """«Mis votos» muestra categoría, edición, votación, opción, fecha y comprobante, y nunca votos ajenos."""
        votos_ana = [registrar_voto(self.ana, self.acordeon.pk, self.a1.pk), registrar_voto(self.ana, self.piqueria.pk, self.p2.pk)]
        voto_beto = registrar_voto(self.beto, self.acordeon.pk, self.b2.pk)

        self.client.force_login(self.ana)
        respuesta = self.client.get(reverse("votos:mis_votos"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertCountEqual(respuesta.context["votos"], votos_ana)
        for voto in votos_ana:
            with self.subTest(categoria=voto.categoria.nombre):
                for dato in (f"{voto.categoria.nombre} · {voto.edicion.anio}", voto.votacion.nombre, voto.opcion.nombre,
                             fecha_hora_co(voto.fecha_hora), voto.codigo_comprobante):
                    self.assertContains(respuesta, dato)
        self.assertNotContains(respuesta, voto_beto.opcion.nombre)
        self.assertNotContains(respuesta, voto_beto.codigo_comprobante)
        # El comprobante de otra persona no se puede abrir
        self.assertEqual(self.client.get(reverse("votos:comprobante", args=[voto_beto.pk])).status_code, 404)

        # Beto ve su voto y la categoría en la que aún puede votar
        self.client.force_login(self.beto)
        respuesta = self.client.get(reverse("votos:mis_votos"))
        self.assertEqual(list(respuesta.context["votos"]), [voto_beto])
        self.assertEqual(respuesta.context["pendientes"], [self.piqueria])

    # CP-08 ------------------------------------------------------------------------------------------
    def filas_del_admin(self, respuesta):
        return [(v.pk, v.usuario.email, v.edicion.anio, v.categoria.nombre, v.votacion.nombre, v.opcion.nombre,
                 timezone.make_naive(v.fecha_hora, dt_timezone.utc))  # MySQL guarda la fecha en UTC
                for v in sorted(respuesta.context["cl"].result_list, key=lambda v: v.pk)]

    def filas_sql(self, condicion="", parametros=()):
        with connection.cursor() as cursor:
            cursor.execute(SQL_VOTOS + condicion + " ORDER BY v.id", list(parametros))
            return [tuple(fila) for fila in cursor.fetchall()]

    def test_cp08_el_admin_muestra_los_votos_igual_que_mysql(self):
        """El administrador consulta los votos y coinciden con SELECT ... FROM votos_voto."""
        registrar_voto(self.ana, self.acordeon.pk, self.a1.pk)
        registrar_voto(self.ana, self.piqueria.pk, self.p2.pk)
        voto_beto = registrar_voto(self.beto, self.acordeon.pk, self.b1.pk)
        personal = get_user_model().objects.create_superuser(email="personal@example.com", nombre_para_mostrar="Personal")
        self.client.force_login(personal)
        lista_url = reverse("admin:votos_voto_changelist")

        lista = self.client.get(lista_url)
        self.assertEqual(lista.status_code, 200)
        self.assertEqual(list(lista.context["cl"].list_display), ["usuario", "edicion", "categoria", "votacion", "opcion", "fecha_hora"])
        self.assertEqual(len(self.filas_sql()), 3)
        self.assertEqual(self.filas_del_admin(lista), self.filas_sql())

        # Filtros por edición, categoría y fecha, y búsqueda por correo
        filtros = {
            "edición": (f"?edicion__id__exact={self.edicion.pk}", " WHERE v.edicion_id = %s", [self.edicion.pk]),
            "categoría": (f"?categoria__id__exact={self.acordeon.pk}", " WHERE v.categoria_id = %s", [self.acordeon.pk]),
            "búsqueda por correo": ("?q=beto@example.com", " WHERE u.email = %s", ["beto@example.com"]),
        }
        filtro_fecha = next(f for f in lista.context["cl"].filter_specs if getattr(f, "field_path", "") == "fecha_hora")
        # El primer enlace con fecha_hora__gte es «Hoy» (después de «Cualquier fecha»)
        hoy = next(opcion for opcion in filtro_fecha.choices(lista.context["cl"]) if "fecha_hora__gte" in opcion["query_string"])
        inicio_hoy = timezone.make_naive(timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0), dt_timezone.utc)
        filtros["fecha (hoy)"] = (hoy["query_string"], " WHERE v.fecha_hora >= %s", [inicio_hoy])
        for descripcion, (consulta, condicion, parametros) in filtros.items():
            with self.subTest(descripcion):
                self.assertEqual(self.filas_del_admin(self.client.get(lista_url + consulta)), self.filas_sql(condicion, parametros))

        # Solo lectura: no se agregan, editan ni borran votos
        self.assertEqual(self.client.get(reverse("admin:votos_voto_add")).status_code, 403)
        self.assertNotContains(self.client.get(reverse("admin:votos_voto_change", args=[voto_beto.pk])), 'name="_save"')
        self.assertEqual(self.client.get(reverse("admin:votos_voto_delete", args=[voto_beto.pk])).status_code, 403)

    # CP-10 ------------------------------------------------------------------------------------------
    def test_cp10_api_categorias_devuelve_json_con_datos_reales(self):
        """GET /api/categorias/ devuelve JSON válido con las categorías y opciones guardadas en MySQL."""
        registrar_voto(self.ana, self.acordeon.pk, self.a1.pk)  # hay votos, pero la API no los cuenta (RN-06)
        url = reverse("festival:api_categorias")
        self.assertEqual(url, "/api/categorias/")

        respuesta = self.client.get(url)
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta["Content-Type"], "application/json")
        texto = respuesta.content.decode("utf-8")
        datos = json.loads(texto)  # JSON válido

        self.assertEqual(datos["edicion"]["anio"], 2027)
        en_mysql = list(Categoria.objects.filter(edicion=self.edicion, publicada=True).order_by("orden", "nombre").values_list("id", "nombre"))
        self.assertEqual([(c["id"], c["nombre"]) for c in datos["categorias"]], en_mysql)
        for categoria in datos["categorias"]:
            with self.subTest(categoria["nombre"]):
                self.assertEqual(categoria["edicion"]["anio"], 2027)
                ids_api = sorted(o["id"] for v in categoria["votaciones"] for o in v["opciones"])
                ids_mysql = sorted(Opcion.objects.filter(votacion__categoria_id=categoria["id"], publicada=True,
                                                         estado=Opcion.Estado.ACTIVA).values_list("id", flat=True))
                self.assertEqual(ids_api, ids_mysql)
        acordeon = datos["categorias"][0]
        self.assertEqual([v["nombre"] for v in acordeon["votaciones"]], ["Semifinal · Grupo A", "Semifinal · Grupo B"])
        self.assertEqual(set(acordeon["votaciones"][0]["opciones"][0]), {"id", "nombre", "tipo", "descripcion"})
        self.assertNotIn(self.a_sin_publicar.nombre, texto)
        self.assertIn("Piquería Mayor", texto)  # tildes legibles (ensure_ascii=False)

        # Sin conteos de votos ni datos personales
        claves = set()

        def recorrer(valor):
            if isinstance(valor, dict):
                claves.update(valor)
                for hijo in valor.values():
                    recorrer(hijo)
            elif isinstance(valor, list):
                for hijo in valor:
                    recorrer(hijo)

        recorrer(datos)
        self.assertFalse(claves & {"votos", "total_votos", "conteo", "resultados", "usuario", "email"})
        self.assertNotIn("ana@example.com", texto)

        # Solo GET: otros métodos responden 405, aun con la protección CSRF activa
        cliente = Client(enforce_csrf_checks=True)
        for metodo in ("post", "put", "delete"):
            with self.subTest(metodo=metodo):
                self.assertEqual(getattr(cliente, metodo)(url).status_code, 405)


# CP-09 ----------------------------------------------------------------------------------------------
@skipUnless(connection.vendor == "mysql", "CP-09 se comprueba contra MySQL")
class ConcurrenciaTests(TransactionTestCase):
    """
    Dos solicitudes simultáneas a la misma categoría dejan un solo voto.

    TransactionTestCase confirma (COMMIT) los datos de cada prueba, así que los hilos, cada uno con su
    propia conexión a MySQL, los ven igual que dos peticiones web reales.
    """

    def setUp(self):
        crear_escenario(self)

    def comprobar_un_solo_voto(self, resultados):
        self.assertEqual(sorted(r["resultado"] for r in resultados), ["rechazado", "registrado"], resultados)
        rechazo = next(r for r in resultados if r["resultado"] == "rechazado")
        self.assertEqual(rechazo["detalle"], "Ya votaste en esta categoría. (HTTP 403)")
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM votos_voto WHERE usuario_id = %s AND categoria_id = %s AND edicion_id = %s",
                           [self.ana.pk, self.acordeon.pk, self.edicion.pk])
            self.assertEqual(cursor.fetchone()[0], 1)

    def test_cp09_dos_solicitudes_simultaneas_dejan_un_solo_voto(self):
        """Dos hilos votan a la vez en la misma categoría, uno por cada subevento: solo queda un voto."""
        resultados = votar_a_la_vez(self.ana, self.acordeon.pk, [self.a1.pk, self.b1.pk])
        self.comprobar_un_solo_voto(resultados)

    def test_cp09_la_restriccion_de_mysql_detiene_el_duplicado(self):
        """
        Peor caso: las dos solicitudes pasan todas las validaciones de Django antes de que alguna inserte.
        Solo la restricción única de MySQL puede detener la segunda; el servicio captura el IntegrityError
        y responde «Ya votaste en esta categoría», sin error 500.
        """
        resultados = votar_a_la_vez(self.ana, self.acordeon.pk, [self.a1.pk, self.a2.pk], forzar_carrera=True)
        self.comprobar_un_solo_voto(resultados)
        auditoria = RegistroAuditoria.objects.filter(usuario=self.ana)
        self.assertEqual(auditoria.filter(accion="Voto duplicado detenido por la base de datos").count(), 1)
        self.assertFalse(auditoria.filter(accion="Voto rechazado: ya votó en la categoría").exists())
