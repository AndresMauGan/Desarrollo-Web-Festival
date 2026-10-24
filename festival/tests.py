"""Pruebas de festival: modelos (cardinalidades, PROTECT, RN-11), admin, vistas públicas y datos de prueba."""

from datetime import date, timedelta
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.test import TestCase
from django.utils import timezone

from . import reglas
from .models import Categoria, Edicion, Opcion, Votacion


class DatosBase(TestCase):
    """Una edición activa con una categoría publicada, una votación programada y dos opciones (una publicada)."""

    @classmethod
    def setUpTestData(cls):
        cls.edicion = Edicion.objects.create(
            numero=60, anio=2027, nombre="60.º Festival de la Leyenda Vallenata",
            fecha_inicio=date(2027, 4, 28), fecha_fin=date(2027, 5, 1), activa=True,
        )
        cls.categoria = Categoria.objects.create(
            edicion=cls.edicion, nombre="Acordeonera Mayor", familia=Categoria.Familia.ACORDEON,
            nivel="Mayor", admite_voto_publico=True, publicada=True,
        )
        abre = timezone.now() + timedelta(days=1)
        cls.votacion = Votacion.objects.create(
            categoria=cls.categoria, nombre="Semifinal de prueba", ronda=Votacion.Ronda.SEMIFINAL,
            estado=Votacion.Estado.PROGRAMADA, abre_en=abre, cierra_en=abre + timedelta(hours=6),
        )
        cls.publicada = Opcion.objects.create(votacion=cls.votacion, nombre="Concursante Ficticia A", tipo=Opcion.Tipo.PERSONA, publicada=True, orden=1)
        cls.sin_publicar = Opcion.objects.create(votacion=cls.votacion, nombre="Concursante Ficticia B", tipo=Opcion.Tipo.PERSONA, publicada=False, orden=2)

    def nueva_votacion(self, **campos):
        abre = timezone.now() + timedelta(days=2)
        datos = {"categoria": self.categoria, "nombre": "Votación auxiliar", "ronda": Votacion.Ronda.FINAL,
                 "estado": Votacion.Estado.BORRADOR, "abre_en": abre, "cierra_en": abre + timedelta(hours=4), **campos}
        return Votacion.objects.create(**datos)


class ModelosTests(DatosBase):
    def test_str_en_espanol(self):
        self.assertEqual(str(self.edicion), "60.º Festival de la Leyenda Vallenata (2027)")
        self.assertEqual(str(self.categoria), "Acordeonera Mayor · 2027")
        self.assertEqual(str(self.votacion), "Semifinal de prueba (Programada)")
        self.assertEqual(str(self.publicada), "Concursante Ficticia A")

    def test_verbose_name_en_espanol(self):
        self.assertEqual(Edicion._meta.verbose_name_plural, "ediciones")
        self.assertEqual(Categoria._meta.verbose_name, "categoría")
        self.assertEqual(Votacion._meta.verbose_name, "votación")
        self.assertEqual(Opcion._meta.verbose_name_plural, "opciones")

    # Cardinalidades: el lado «exactamente uno» es obligatorio
    def test_no_se_crea_una_categoria_sin_edicion(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Categoria.objects.create(nombre="Sin edición", familia=Categoria.Familia.OTRA)

    def test_no_se_crea_una_votacion_sin_categoria(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Votacion.objects.create(nombre="Sin categoría", ronda=Votacion.Ronda.FINAL,
                                    abre_en=timezone.now(), cierra_en=timezone.now() + timedelta(hours=1))

    def test_no_se_crea_una_opcion_sin_votacion(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Opcion.objects.create(nombre="Sin votación", tipo=Opcion.Tipo.PERSONA)

    def test_lado_muchos_admite_cero(self):
        otra = Edicion.objects.create(numero=59, anio=2026, nombre="59.º", fecha_inicio=date(2026, 4, 29), fecha_fin=date(2026, 5, 2))
        self.assertEqual(otra.categorias.count(), 0)
        vacia = self.nueva_votacion()
        vacia.full_clean()  # una votación en borrador puede no tener opciones
        self.assertEqual(vacia.opciones.count(), 0)

    def test_nombre_de_categoria_unico_por_edicion(self):
        with self.assertRaises(ValidationError):
            Categoria(edicion=self.edicion, nombre="Acordeonera Mayor", familia=Categoria.Familia.ACORDEON).full_clean()
        with self.assertRaises(IntegrityError), transaction.atomic():
            Categoria.objects.create(edicion=self.edicion, nombre="Acordeonera Mayor", familia=Categoria.Familia.ACORDEON)
        otra = Edicion.objects.create(numero=59, anio=2026, nombre="59.º", fecha_inicio=date(2026, 4, 29), fecha_fin=date(2026, 5, 2))
        Categoria.objects.create(edicion=otra, nombre="Acordeonera Mayor", familia=Categoria.Familia.ACORDEON)

    def test_anio_de_edicion_unico(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Edicion.objects.create(numero=61, anio=2027, nombre="Repetida", fecha_inicio=date(2027, 1, 1), fecha_fin=date(2027, 1, 2))

    # PROTECT: nada se borra en cascada (RN-10)
    def test_protect_edicion_con_categorias(self):
        with self.assertRaises(ProtectedError):
            self.edicion.delete()

    def test_protect_categoria_con_votaciones(self):
        with self.assertRaises(ProtectedError):
            self.categoria.delete()

    def test_protect_votacion_con_opciones(self):
        with self.assertRaises(ProtectedError):
            self.votacion.delete()
        self.assertTrue(Opcion.objects.filter(pk=self.publicada.pk).exists())

    # Validaciones
    def test_cierre_posterior_a_la_apertura(self):
        self.votacion.cierra_en = self.votacion.abre_en
        with self.assertRaises(ValidationError) as error:
            self.votacion.full_clean()
        self.assertIn("cierra_en", error.exception.message_dict)

    def test_fin_de_edicion_no_anterior_al_inicio(self):
        self.edicion.fecha_fin = date(2027, 4, 1)
        with self.assertRaises(ValidationError):
            self.edicion.full_clean()

    def test_rn11_no_abre_con_una_opcion_publicada(self):
        self.votacion.estado = Votacion.Estado.ABIERTA
        with self.assertRaises(ValidationError) as error:
            self.votacion.full_clean()
        self.assertIn("RN-11", str(error.exception))

    def test_rn11_abre_con_dos_opciones_publicadas(self):
        self.sin_publicar.publicada = True
        self.sin_publicar.save()
        self.votacion.estado = Votacion.Estado.ABIERTA
        self.votacion.full_clean()

    def test_rn11_no_cuenta_opciones_retiradas(self):
        self.sin_publicar.publicada = True
        self.sin_publicar.estado = Opcion.Estado.RETIRADA
        self.sin_publicar.save()
        self.votacion.estado = Votacion.Estado.ABIERTA
        with self.assertRaises(ValidationError):
            self.votacion.full_clean()

    def test_rn11_tambien_al_reanudar_una_pausada(self):
        Votacion.objects.filter(pk=self.votacion.pk).update(estado=Votacion.Estado.PAUSADA)
        self.votacion.refresh_from_db()
        self.votacion.estado = Votacion.Estado.ABIERTA
        with self.assertRaises(ValidationError):
            self.votacion.full_clean()

    def test_rn11_no_se_revisa_si_ya_estaba_abierta(self):
        Votacion.objects.filter(pk=self.votacion.pk).update(estado=Votacion.Estado.ABIERTA)
        self.votacion.refresh_from_db()
        self.votacion.nombre = "Semifinal renombrada"
        self.votacion.full_clean()

    # Reglas pendientes (observación 2 del docente): valores por defecto en reglas.py, marcados en el admin
    def test_valores_por_defecto_salen_de_reglas(self):
        vacia = self.nueva_votacion()
        self.assertEqual(vacia.limite_votos_por_usuario, reglas.LIMITE_VOTOS_POR_DEFECTO)
        self.assertEqual(vacia.visibilidad_resultados, reglas.VISIBILIDAD_RESULTADOS_POR_DEFECTO)
        self.assertIn("Pendiente de validación (P-03)", Votacion._meta.get_field("limite_votos_por_usuario").help_text)
        self.assertIn("Pendiente de validación (P-05)", Votacion._meta.get_field("visibilidad_resultados").help_text)

    def test_limite_minimo_uno(self):
        self.votacion.limite_votos_por_usuario = 0
        with self.assertRaises(ValidationError):
            self.votacion.full_clean()


class AdminTests(DatosBase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.admin = get_user_model().objects.create_superuser(email="admin@example.com", password="Admin-Prueba-2027", nombre_para_mostrar="Admin")

    def setUp(self):
        self.client.force_login(self.admin)

    def test_paginas_del_admin_de_los_siete_modelos(self):
        for modelo in ["festival/edicion", "festival/categoria", "festival/votacion", "festival/opcion",
                       "votos/voto", "votos/registroauditoria", "cuentas/usuario"]:
            with self.subTest(modelo=modelo):
                self.assertEqual(self.client.get(f"/admin/{modelo}/").status_code, 200)
        self.assertEqual(self.client.get(f"/admin/festival/edicion/{self.edicion.pk}/change/").status_code, 200)
        self.assertEqual(self.client.get(f"/admin/festival/votacion/{self.votacion.pk}/change/").status_code, 200)

    def datos_votacion(self, estado, publicadas):
        """Formulario del admin de la votación con sus dos opciones en línea; publica las primeras «publicadas»."""
        v, local = self.votacion, timezone.localtime
        datos = {
            "categoria": v.categoria_id, "nombre": v.nombre, "ronda": v.ronda, "estado": estado,
            "abre_en_0": local(v.abre_en).strftime("%d/%m/%Y"), "abre_en_1": local(v.abre_en).strftime("%H:%M:%S"),
            "cierra_en_0": local(v.cierra_en).strftime("%d/%m/%Y"), "cierra_en_1": local(v.cierra_en).strftime("%H:%M:%S"),
            "limite_votos_por_usuario": 1, "visibilidad_resultados": "al_cierre",
            "opciones-TOTAL_FORMS": 2, "opciones-INITIAL_FORMS": 2, "opciones-MIN_NUM_FORMS": 0, "opciones-MAX_NUM_FORMS": 1000,
        }
        for i, opcion in enumerate([self.publicada, self.sin_publicar]):
            datos.update({f"opciones-{i}-id": opcion.pk, f"opciones-{i}-votacion": v.pk, f"opciones-{i}-nombre": opcion.nombre,
                          f"opciones-{i}-tipo": opcion.tipo, f"opciones-{i}-orden": opcion.orden, f"opciones-{i}-estado": "activa"})
            if i < publicadas:
                datos[f"opciones-{i}-publicada"] = "on"
        return datos

    def test_rn11_en_el_admin_rechaza_abrir_con_una_opcion(self):
        respuesta = self.client.post(f"/admin/festival/votacion/{self.votacion.pk}/change/", self.datos_votacion("abierta", 1))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "RN-11")
        self.votacion.refresh_from_db()
        self.assertEqual(self.votacion.estado, Votacion.Estado.PROGRAMADA)

    def test_rn11_en_el_admin_abre_si_publica_la_segunda_opcion_al_mismo_tiempo(self):
        respuesta = self.client.post(f"/admin/festival/votacion/{self.votacion.pk}/change/", self.datos_votacion("abierta", 2))
        self.assertEqual(respuesta.status_code, 302)
        self.votacion.refresh_from_db()
        self.assertEqual(self.votacion.estado, Votacion.Estado.ABIERTA)


class VistasPublicasTests(DatosBase):
    def test_inicio_muestra_edicion_activa_y_categorias_publicadas(self):
        Categoria.objects.create(edicion=self.edicion, nombre="Categoría oculta", familia=Categoria.Familia.OTRA, publicada=False)
        respuesta = self.client.get("/")
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "60.º Festival de la Leyenda Vallenata")
        self.assertContains(respuesta, "Del 28 de abril al 1 de mayo de 2027")
        self.assertContains(respuesta, "Acordeonera Mayor")
        self.assertNotContains(respuesta, "Categoría oculta")

    def test_inicio_sin_edicion_activa(self):
        Edicion.objects.update(activa=False)
        self.assertContains(self.client.get("/"), "No hay una edición activa")

    def test_paginas_publicas_responden_200(self):
        for url in ["/ediciones/", "/ediciones/2027/", "/ediciones/2027/categorias/",
                    f"/categorias/{self.categoria.pk}/", f"/votaciones/{self.votacion.pk}/"]:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_categorias_lleva_a_la_edicion_activa(self):
        self.assertRedirects(self.client.get("/categorias/"), "/ediciones/2027/categorias/")

    def test_categoria_sin_publicar_no_se_lista_y_da_404(self):
        oculta = Categoria.objects.create(edicion=self.edicion, nombre="Categoría oculta", familia=Categoria.Familia.OTRA, publicada=False)
        self.assertNotContains(self.client.get("/ediciones/2027/categorias/"), "Categoría oculta")
        self.assertEqual(self.client.get(f"/categorias/{oculta.pk}/").status_code, 404)

    def test_votacion_de_categoria_sin_publicar_da_404(self):
        Categoria.objects.filter(pk=self.categoria.pk).update(publicada=False)
        self.assertEqual(self.client.get(f"/votaciones/{self.votacion.pk}/").status_code, 404)

    def test_votacion_en_borrador_no_es_publica(self):
        borrador = self.nueva_votacion(nombre="Votación en borrador")
        self.assertNotContains(self.client.get(f"/categorias/{self.categoria.pk}/"), "Votación en borrador")
        self.assertEqual(self.client.get(f"/votaciones/{borrador.pk}/").status_code, 404)

    def test_estados_publicos_con_su_etiqueta(self):
        etiquetas = {"programada": "Próximamente", "abierta": "En vivo", "pausada": "Pausada", "cerrada": "Cerrada"}
        for estado, etiqueta in etiquetas.items():
            with self.subTest(estado=estado):
                Votacion.objects.filter(pk=self.votacion.pk).update(estado=estado)
                self.assertContains(self.client.get(f"/categorias/{self.categoria.pk}/"), etiqueta)

    def test_detalle_solo_opciones_publicadas_y_activas(self):
        Opcion.objects.create(votacion=self.votacion, nombre="Concursante Retirada", tipo=Opcion.Tipo.PERSONA, publicada=True, estado=Opcion.Estado.RETIRADA)
        respuesta = self.client.get(f"/votaciones/{self.votacion.pk}/")
        self.assertContains(respuesta, "Concursante Ficticia A")
        self.assertNotContains(respuesta, "Concursante Ficticia B")
        self.assertNotContains(respuesta, "Concursante Retirada")

    def test_detalle_marca_reglas_pendientes_como_provisionales(self):
        respuesta = self.client.get(f"/votaciones/{self.votacion.pk}/")
        self.assertContains(respuesta, "Provisional", count=2)
        self.assertContains(respuesta, "(P-03)")
        self.assertContains(respuesta, "(P-05)")

    def test_detalle_sin_conteos_ni_boton_de_voto(self):
        respuesta = self.client.get(f"/votaciones/{self.votacion.pk}/")
        self.assertNotContains(respuesta, "<form")
        self.assertContains(respuesta, "El registro de votos todavía no está habilitado.")

    def test_formato_colombiano_de_fecha_y_hora(self):
        apertura = timezone.make_aware(timezone.datetime(2027, 5, 1, 19, 30))
        Votacion.objects.filter(pk=self.votacion.pk).update(abre_en=apertura, cierra_en=apertura + timedelta(hours=3))
        self.assertContains(self.client.get(f"/votaciones/{self.votacion.pk}/"), "1 de mayo de 2027, 7:30 p. m.")

    def test_404_para_lo_que_no_existe(self):
        for url in ["/ediciones/1999/", "/ediciones/1999/categorias/", "/categorias/99999/", "/votaciones/99999/", "/no-existe/"]:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 404)
        self.assertContains(self.client.get("/no-existe/"), "No encontramos esta página", status_code=404)


class CargarDatosPruebaTests(TestCase):
    def test_carga_sin_duplicar_y_con_todos_los_estados(self):
        call_command("cargar_datos_prueba", stdout=StringIO())
        call_command("cargar_datos_prueba", stdout=StringIO())
        self.assertEqual(list(Edicion.objects.order_by("anio").values_list("anio", flat=True)), [2026, 2027])
        self.assertEqual(Categoria.objects.filter(edicion__anio=2027).count(), 4)
        self.assertEqual(set(Votacion.objects.values_list("estado", flat=True)), set(Votacion.Estado.values))
        self.assertEqual(Opcion.objects.count(), 14)
        self.assertTrue(all("Ficti" in nombre for nombre in Opcion.objects.values_list("nombre", flat=True)))
