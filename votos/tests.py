"""Pruebas de votos: Voto (coherencia entre relaciones, RN-01 en MySQL, inmutabilidad, PROTECT) y RegistroAuditoria (0..1)."""

from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.test import TestCase
from django.utils import timezone

from festival.models import Categoria, Edicion, Opcion, Votacion

from .models import RegistroAuditoria, Voto, VotoInmutableError

HUELLAS = {"huella_ip": "a" * 64, "huella_navegador": "b" * 64}


class VotosBase(TestCase):
    """Una categoría con dos votaciones (subeventos) y otra categoría aparte, en la misma edición."""

    @classmethod
    def setUpTestData(cls):
        cls.usuario = get_user_model().objects.create_user(email="votante@example.com", password="Votante-2027", nombre_para_mostrar="Votante")
        cls.edicion = Edicion.objects.create(numero=60, anio=2027, nombre="60.º", fecha_inicio=date(2027, 4, 28), fecha_fin=date(2027, 5, 1))
        cls.categoria = Categoria.objects.create(edicion=cls.edicion, nombre="Piquería Mayor", familia=Categoria.Familia.PIQUERIA)
        cls.otra_categoria = Categoria.objects.create(edicion=cls.edicion, nombre="Canción Inédita", familia=Categoria.Familia.CANCION)
        abre = timezone.now()
        nueva = lambda categoria, nombre: Votacion.objects.create(categoria=categoria, nombre=nombre, ronda=Votacion.Ronda.ELIMINATORIA, abre_en=abre, cierra_en=abre + timedelta(hours=2))
        cls.votacion = nueva(cls.categoria, "Eliminatoria")
        cls.otra_votacion = nueva(cls.categoria, "Final")
        cls.votacion_otra_categoria = nueva(cls.otra_categoria, "Final de canción")
        cls.opcion = Opcion.objects.create(votacion=cls.votacion, nombre="Pareja Ficticia A", tipo=Opcion.Tipo.GRUPO)
        cls.opcion_ajena = Opcion.objects.create(votacion=cls.otra_votacion, nombre="Pareja Ficticia B", tipo=Opcion.Tipo.GRUPO)
        cls.opcion_otra_categoria = Opcion.objects.create(votacion=cls.votacion_otra_categoria, nombre="Obra Ficticia C", tipo=Opcion.Tipo.OBRA)

    def votar(self, opcion=None, usuario=None, **campos):
        voto = Voto.desde_opcion(usuario or self.usuario, opcion or self.opcion,
                                 hash_auditoria=campos.pop("hash_auditoria", "c" * 64), **HUELLAS, **campos)
        voto.save()
        return voto


class VotoTests(VotosBase):
    def test_str(self):
        voto = self.votar()
        self.assertEqual(str(voto), f"Voto #{voto.pk} en «Eliminatoria»")

    def test_desde_opcion_deriva_votacion_categoria_y_edicion(self):
        voto = self.votar()
        self.assertEqual((voto.votacion, voto.categoria, voto.edicion), (self.votacion, self.categoria, self.edicion))
        self.assertEqual(voto.codigo_comprobante, "VV-CCCC-CCCC")

    def test_la_opcion_debe_pertenecer_a_la_votacion_del_voto(self):
        voto = Voto.desde_opcion(self.usuario, self.opcion, hash_auditoria="c" * 64, **HUELLAS)
        voto.full_clean()
        voto.opcion = self.opcion_ajena
        with self.assertRaises(ValidationError) as error:
            voto.full_clean()
        self.assertIn("opcion", error.exception.message_dict)

    def test_la_votacion_debe_pertenecer_a_la_categoria_y_esta_a_la_edicion(self):
        voto = Voto.desde_opcion(self.usuario, self.opcion, hash_auditoria="c" * 64, **HUELLAS)
        voto.categoria = self.otra_categoria
        with self.assertRaises(ValidationError) as error:
            voto.full_clean()
        self.assertIn("votacion", error.exception.message_dict)
        otra_edicion = Edicion.objects.create(numero=59, anio=2026, nombre="59.º", fecha_inicio=date(2026, 4, 29), fecha_fin=date(2026, 5, 2))
        voto = Voto.desde_opcion(self.usuario, self.opcion, hash_auditoria="c" * 64, **HUELLAS)
        voto.edicion = otra_edicion
        with self.assertRaises(ValidationError) as error:
            voto.full_clean()
        self.assertIn("categoria", error.exception.message_dict)

    def test_relaciones_obligatorias(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Voto.objects.create(votacion=self.votacion, opcion=self.opcion, categoria=self.categoria, edicion=self.edicion,
                                hash_auditoria="c" * 64, **HUELLAS)

    # RN-01 (definida por la guía de la Entrega 3): un voto por usuario, categoría y edición, en MySQL
    def test_restriccion_unica_en_la_misma_categoria(self):
        self.votar()
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.votar(opcion=self.opcion_ajena, hash_auditoria="d" * 64)  # otro subevento de la misma categoría
        self.assertEqual(Voto.objects.filter(usuario=self.usuario, categoria=self.categoria).count(), 1)

    def test_restriccion_permite_otra_categoria_y_otro_usuario(self):
        self.votar()
        self.votar(opcion=self.opcion_otra_categoria, hash_auditoria="d" * 64)
        otro = get_user_model().objects.create_user(email="otra@example.com", password="Votante-2027", nombre_para_mostrar="Otra")
        self.votar(usuario=otro, hash_auditoria="e" * 64)
        self.assertEqual(Voto.objects.count(), 3)

    def test_restriccion_registrada_en_el_modelo(self):
        restricciones = {r.name: r for r in Voto._meta.constraints}
        self.assertEqual(restricciones["un_voto_por_usuario_categoria_edicion"].fields, ("usuario", "categoria", "edicion"))

    def test_related_names(self):
        voto = self.votar()
        for relacionado in (self.votacion, self.opcion, self.usuario, self.categoria, self.edicion):
            with self.subTest(relacionado=relacionado):
                self.assertEqual(list(relacionado.votos.all()), [voto])

    # RN-02: votos inmutables
    def test_no_se_modifica(self):
        voto = self.votar()
        voto.hash_auditoria = "e" * 64
        with self.assertRaises(VotoInmutableError):
            voto.save()
        with self.assertRaises(VotoInmutableError):
            Voto.objects.filter(pk=voto.pk).update(hash_auditoria="e" * 64)

    def test_no_se_borra(self):
        voto = self.votar()
        with self.assertRaises(VotoInmutableError):
            voto.delete()
        with self.assertRaises(VotoInmutableError):
            Voto.objects.all().delete()
        self.assertTrue(Voto.objects.filter(pk=voto.pk).exists())

    # PROTECT (RN-10)
    def test_protect_opcion_votacion_y_usuario_con_votos(self):
        self.votar()
        for objeto in (self.opcion, self.votacion, self.usuario, self.categoria, self.edicion):
            with self.subTest(objeto=objeto), self.assertRaises(ProtectedError):
                objeto.delete()


class RegistroAuditoriaTests(VotosBase):
    def test_registro_sin_usuario_es_del_sistema(self):
        registro = RegistroAuditoria.objects.create(accion="Alerta", entidad_afectada="votos.Voto", detalle="Prueba")
        self.assertIsNone(registro.usuario)
        self.assertEqual(str(registro), "Sistema · Alerta · votos.Voto")

    def test_registro_con_usuario(self):
        registro = RegistroAuditoria.objects.create(usuario=self.usuario, accion="Inicio de sesión", entidad_afectada="cuentas.Usuario")
        self.assertEqual(list(self.usuario.registros.all()), [registro])
        with self.assertRaises(ProtectedError):
            self.usuario.delete()


class AdminSoloLecturaTests(VotosBase):
    def setUp(self):
        admin = get_user_model().objects.create_superuser(email="admin@example.com", password="Admin-Prueba-2027", nombre_para_mostrar="Admin")
        self.client.force_login(admin)

    def test_voto_y_auditoria_no_se_agregan_ni_editan(self):
        voto = self.votar()
        registro = RegistroAuditoria.objects.create(accion="Alerta", entidad_afectada="votos.Voto")
        for modelo, objeto in (("voto", voto), ("registroauditoria", registro)):
            with self.subTest(modelo=modelo):
                self.assertEqual(self.client.get(f"/admin/votos/{modelo}/add/").status_code, 403)
                detalle = self.client.get(f"/admin/votos/{modelo}/{objeto.pk}/change/")
                self.assertEqual(detalle.status_code, 200)
                self.assertNotContains(detalle, 'name="_save"')
