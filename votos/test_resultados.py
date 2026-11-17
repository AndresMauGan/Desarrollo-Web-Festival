"""
Pruebas de resultados (entrega final, Parte A).

- Los conteos coinciden con SELECT opcion_id, COUNT(*) FROM votos_voto GROUP BY opcion_id.
- Aparecen las opciones con 0 votos; los porcentajes y el orden son correctos.
- /resultados/ exige el permiso votos.ver_resultados: el votante recibe 403 y el anónimo va al inicio de sesión.
- Los resultados públicos se muestran u ocultan según la visibilidad y el estado de la votación.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db import connection
from django.test import TestCase
from django.urls import reverse

from festival.models import Categoria, Opcion, Votacion

from .models import RegistroAuditoria
from .resultados import resultados_de_edicion, resultados_visibles
from .servicios import registrar_voto
from .test_casos_prueba import crear_escenario, nuevas_opciones, nueva_votacion

Estado = Votacion.Estado
Visibilidad = Votacion.Visibilidad


def conteos_en_mysql():
    with connection.cursor() as cursor:
        cursor.execute("SELECT opcion_id, COUNT(*) FROM votos_voto GROUP BY opcion_id")
        return dict(cursor.fetchall())


class ResultadosBase(TestCase):
    """
    Escenario de test_casos_prueba más estos votos:
    - Acordeonera Mayor, grupo A: A1 = 2 (Ana y Beto), A2 = 1 (Dora; después se retira la opción).
    - Acordeonera Mayor, grupo B: B2 = 1 (Carla), B1 = 0.
    - Piquería Mayor: P1 = 1 (Ana), P2 = 0.
    """

    @classmethod
    def setUpTestData(cls):
        crear_escenario(cls)
        Usuario = get_user_model()
        cls.carla = Usuario.objects.create_user(email="carla@example.com", nombre_para_mostrar="Carla")
        cls.dora = Usuario.objects.create_user(email="dora@example.com", nombre_para_mostrar="Dora")
        registrar_voto(cls.ana, cls.acordeon.pk, cls.a1.pk)
        registrar_voto(cls.beto, cls.acordeon.pk, cls.a1.pk)
        registrar_voto(cls.dora, cls.acordeon.pk, cls.a2.pk)
        registrar_voto(cls.carla, cls.acordeon.pk, cls.b2.pk)
        registrar_voto(cls.ana, cls.piqueria.pk, cls.p1.pk)
        # Una opción que recibió un voto y luego se retiró sigue contando (RN-10: se retira, no se borra)
        Opcion.objects.filter(pk=cls.a2.pk).update(estado=Opcion.Estado.RETIRADA)
        cls.personal = Usuario.objects.create_user(email="personal@example.com", nombre_para_mostrar="Personal", is_staff=True)
        cls.personal.user_permissions.add(Permission.objects.get(content_type__app_label="votos", codename="ver_resultados"))

    def pagina_del_personal(self, consulta=""):
        self.client.force_login(self.personal)
        return self.client.get(reverse("resultados:panel") + consulta)

    @staticmethod
    def opciones_de(respuesta):
        return {o.pk: o for c in respuesta.context["categorias"] for v in c.votaciones_contadas for o in v.resultados}


class ResultadosDelPersonalTests(ResultadosBase):
    def test_conteos_coinciden_con_mysql(self):
        respuesta = self.pagina_del_personal()
        self.assertEqual(respuesta.status_code, 200)
        con_votos = {pk: o.num_votos for pk, o in self.opciones_de(respuesta).items() if o.num_votos}
        self.assertEqual(con_votos, conteos_en_mysql())
        self.assertEqual(sum(con_votos.values()), 5)

    def test_aparecen_las_opciones_con_cero_votos(self):
        opciones = self.opciones_de(self.pagina_del_personal())
        self.assertEqual(opciones[self.b1.pk].num_votos, 0)
        self.assertEqual(opciones[self.p2.pk].num_votos, 0)
        # Una opción sin publicar y sin votos no aparece; una retirada con votos sí, marcada
        self.assertNotIn(self.a_sin_publicar.pk, opciones)
        self.assertEqual(opciones[self.a2.pk].aviso, "Retirada")

    def test_porcentajes_de_mayor_a_menor_por_votacion(self):
        respuesta = self.pagina_del_personal()
        votaciones = {v.pk: v for c in respuesta.context["categorias"] for v in c.votaciones_contadas}
        grupo_a = votaciones[self.grupo_a.pk]
        self.assertEqual(grupo_a.total_votos, 3)
        self.assertEqual([(o.nombre, o.num_votos, o.porcentaje) for o in grupo_a.resultados],
                         [(self.a1.nombre, 2, 66.7), (self.a2.nombre, 1, 33.3)])
        self.assertEqual([(o.nombre, o.porcentaje) for o in votaciones[self.grupo_b.pk].resultados],
                         [(self.b2.nombre, 100.0), (self.b1.nombre, 0.0)])
        # Barras en CSS: el ancho usa punto decimal; el texto, coma (formato colombiano)
        self.assertContains(respuesta, 'style="width: 66.7%"')
        self.assertContains(respuesta, "2 votos · 66,7 %")

    def test_personas_que_votaron_por_categoria(self):
        respuesta = self.pagina_del_personal()
        votantes = {c.nombre: c.votantes for c in respuesta.context["categorias"]}
        self.assertEqual(votantes, {"Acordeonera Mayor": 4, "Piquería Mayor": 1})
        self.assertContains(respuesta, "4 personas votaron en esta categoría")
        self.assertContains(respuesta, "1 persona votó en esta categoría")

    def test_estado_de_cada_votacion_y_hora_de_la_consulta(self):
        respuesta = self.pagina_del_personal()
        self.assertContains(respuesta, "En vivo")
        self.assertContains(respuesta, "consultado el")
        self.assertIn("consultado_en", respuesta.context)

    def test_tres_consultas_sin_importar_cuantas_opciones_haya(self):
        with self.assertNumQueries(3):
            resultados_de_edicion(self.edicion)
        otra = nueva_votacion(self.piqueria, "Desempate Piquería Mayor")
        nuevas_opciones(otra, *[f"Pareja Ficticia Extra {n}" for n in range(10)])
        with self.assertNumQueries(3):
            categorias = resultados_de_edicion(self.edicion)
        self.assertEqual(sum(len(v.resultados) for c in categorias for v in c.votaciones_contadas), 16)

    def test_no_muestra_votaciones_en_borrador(self):
        borrador = nueva_votacion(self.acordeon, "Final en preparación", estado=Estado.BORRADOR)
        respuesta = self.pagina_del_personal()
        self.assertNotIn(borrador.pk, {v.pk for c in respuesta.context["categorias"] for v in c.votaciones_contadas})

    def test_otra_edicion_con_el_parametro(self):
        respuesta = self.pagina_del_personal("?edicion=2026")
        self.assertEqual(respuesta.context["edicion"], self.edicion_anterior)
        self.assertEqual(respuesta.context["categorias"], [])
        self.assertEqual(self.pagina_del_personal("?edicion=1999").status_code, 404)
        self.assertEqual(self.pagina_del_personal("?edicion=abc").status_code, 404)


class AccesoAResultadosTests(ResultadosBase):
    def test_anonimo_va_al_inicio_de_sesion(self):
        url = reverse("resultados:panel")
        self.assertRedirects(self.client.get(url), f"{reverse('cuentas:login')}?next={url}", fetch_redirect_response=False)

    def test_votante_y_personal_sin_permiso_reciben_403(self):
        sin_permiso = get_user_model().objects.create_user(email="staff@example.com", nombre_para_mostrar="Staff", is_staff=True)
        for usuario in (self.ana, sin_permiso):
            with self.subTest(usuario=usuario.email):
                self.client.force_login(usuario)
                self.assertEqual(self.client.get(reverse("resultados:panel")).status_code, 403)

    def test_con_permiso_o_superusuario_entra(self):
        self.assertEqual(self.pagina_del_personal().status_code, 200)
        superusuario = get_user_model().objects.create_superuser(email="tecnico@example.com", nombre_para_mostrar="Técnico")
        self.client.force_login(superusuario)
        self.assertEqual(self.client.get(reverse("resultados:panel")).status_code, 200)


class ResultadosPublicosTests(ResultadosBase):
    def ver(self, votacion):
        return self.client.get(reverse("resultados:votacion", args=[votacion.pk]))

    def configurar(self, **campos):
        Votacion.objects.filter(pk=self.grupo_a.pk).update(**campos)
        self.grupo_a.refresh_from_db()

    def test_visibilidad_segun_la_eleccion_del_administrador(self):
        casos = [
            # (visibilidad, estado, publicados, ¿se ven?, texto esperado)
            (Visibilidad.EN_VIVO, Estado.ABIERTA, False, True, "en vivo"),
            (Visibilidad.AL_CIERRE, Estado.ABIERTA, False, False, "cuando cierre la votación"),
            (Visibilidad.AL_CIERRE, Estado.PAUSADA, False, False, "cuando cierre la votación"),
            (Visibilidad.AL_CIERRE, Estado.CERRADA, False, True, "ya cerró"),
            (Visibilidad.EN_CEREMONIA, Estado.CERRADA, False, False, "ceremonia de premiación"),
            (Visibilidad.EN_CEREMONIA, Estado.CERRADA, True, True, "se dieron a conocer"),
        ]
        for visibilidad, estado, publicados, se_ven, texto in casos:
            with self.subTest(visibilidad=visibilidad, estado=estado, publicados=publicados):
                self.configurar(visibilidad_resultados=visibilidad, estado=estado, resultados_publicados=publicados)
                self.assertEqual(resultados_visibles(self.grupo_a)[0], se_ven)
                respuesta = self.ver(self.grupo_a)
                self.assertEqual(respuesta.status_code, 200)
                self.assertContains(respuesta, texto)
                if se_ven:
                    self.assertContains(respuesta, "2 votos · 66,7 %")
                else:
                    # Mientras no se puedan ver, no se muestra ningún conteo ni las opciones
                    self.assertNotContains(respuesta, "barra-fill")
                    self.assertNotContains(respuesta, self.a1.nombre)
                    self.assertNotIn("resultados", vars(respuesta.context["votacion"]))

    def test_publicados_solo_cambia_algo_en_ceremonia(self):
        self.configurar(visibilidad_resultados=Visibilidad.AL_CIERRE, estado=Estado.ABIERTA, resultados_publicados=True)
        self.assertFalse(resultados_visibles(self.grupo_a)[0])

    def test_borrador_o_categoria_sin_publicar_no_tienen_pagina(self):
        self.configurar(estado=Estado.BORRADOR)
        self.assertEqual(self.ver(self.grupo_a).status_code, 404)
        self.configurar(estado=Estado.ABIERTA)
        Categoria.objects.filter(pk=self.acordeon.pk).update(publicada=False)
        self.assertEqual(self.ver(self.grupo_a).status_code, 404)

    def test_detalle_de_la_votacion_enlaza_los_resultados(self):
        respuesta = self.client.get(reverse("festival:votacion", args=[self.grupo_a.pk]))
        self.assertContains(respuesta, reverse("resultados:votacion", args=[self.grupo_a.pk]))


class AdminDeResultadosTests(ResultadosBase):
    def setUp(self):
        self.client.force_login(get_user_model().objects.create_superuser(email="tecnico@example.com", nombre_para_mostrar="Técnico"))

    def test_columna_de_votos_en_votaciones_y_opciones(self):
        lista = self.client.get(reverse("admin:festival_votacion_changelist"))
        self.assertIn("conteo_votos", lista.context["cl"].list_display)
        por_votacion = {v.pk: v.num_votos for v in lista.context["cl"].result_list}
        self.assertEqual((por_votacion[self.grupo_a.pk], por_votacion[self.grupo_b.pk], por_votacion[self.final_piqueria.pk]), (3, 1, 1))
        lista = self.client.get(reverse("admin:festival_opcion_changelist"))
        por_opcion = {o.pk: o.num_votos for o in lista.context["cl"].result_list if o.num_votos}
        self.assertEqual(por_opcion, conteos_en_mysql())

    def test_acciones_publicar_y_retirar_dejan_auditoria(self):
        Votacion.objects.filter(pk=self.grupo_a.pk).update(visibilidad_resultados=Visibilidad.EN_CEREMONIA, estado=Estado.CERRADA)
        url = reverse("admin:festival_votacion_changelist")
        for accion, publicados, registro in (("publicar_resultados", True, "Resultados publicados"),
                                             ("retirar_publicacion", False, "Publicación de resultados retirada")):
            with self.subTest(accion):
                respuesta = self.client.post(url, {"action": accion, "_selected_action": [self.grupo_a.pk]}, follow=True)
                self.assertEqual(respuesta.status_code, 200)
                self.grupo_a.refresh_from_db()
                self.assertEqual(self.grupo_a.resultados_publicados, publicados)
                self.assertTrue(RegistroAuditoria.objects.filter(accion=registro, entidad_afectada=f"festival.Votacion #{self.grupo_a.pk}").exists())
