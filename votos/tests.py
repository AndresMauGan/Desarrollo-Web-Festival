"""Pruebas de votos: Voto (integridad entre relaciones, inmutabilidad, PROTECT) y RegistroAuditoria (0..1)."""

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
    @classmethod
    def setUpTestData(cls):
        cls.usuario = get_user_model().objects.create_user(email="votante@example.com", password="Votante-2027", nombre_para_mostrar="Votante")
        edicion = Edicion.objects.create(numero=60, anio=2027, nombre="60.º", fecha_inicio=date(2027, 4, 28), fecha_fin=date(2027, 5, 1))
        categoria = Categoria.objects.create(edicion=edicion, nombre="Piquería Mayor", familia=Categoria.Familia.PIQUERIA)
        abre = timezone.now()
        cls.votacion = Votacion.objects.create(categoria=categoria, nombre="Eliminatoria", ronda=Votacion.Ronda.ELIMINATORIA, abre_en=abre, cierra_en=abre + timedelta(hours=2))
        cls.otra_votacion = Votacion.objects.create(categoria=categoria, nombre="Final", ronda=Votacion.Ronda.FINAL, abre_en=abre, cierra_en=abre + timedelta(hours=2))
        cls.opcion = Opcion.objects.create(votacion=cls.votacion, nombre="Pareja Ficticia A", tipo=Opcion.Tipo.GRUPO)
        cls.opcion_ajena = Opcion.objects.create(votacion=cls.otra_votacion, nombre="Pareja Ficticia B", tipo=Opcion.Tipo.GRUPO)

    def votar(self, opcion=None, votacion=None, **campos):
        return Voto.objects.create(usuario=self.usuario, votacion=votacion or self.votacion, opcion=opcion or self.opcion,
                                   hash_auditoria=campos.pop("hash_auditoria", "c" * 64), **HUELLAS, **campos)


class VotoTests(VotosBase):
    def test_str(self):
        voto = self.votar()
        self.assertEqual(str(voto), f"Voto #{voto.pk} en «Eliminatoria»")

    def test_la_opcion_debe_pertenecer_a_la_votacion_del_voto(self):
        voto = Voto(usuario=self.usuario, votacion=self.votacion, opcion=self.opcion_ajena, hash_auditoria="c" * 64, **HUELLAS)
        with self.assertRaises(ValidationError) as error:
            voto.full_clean()
        self.assertIn("opcion", error.exception.message_dict)
        Voto(usuario=self.usuario, votacion=self.votacion, opcion=self.opcion, hash_auditoria="c" * 64, **HUELLAS).full_clean()

    def test_relaciones_obligatorias(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Voto.objects.create(votacion=self.votacion, opcion=self.opcion, hash_auditoria="c" * 64, **HUELLAS)

    def test_sin_restriccion_unica_usuario_votacion(self):
        # RN-01 (límite de votos) está pendiente (P-03): la base no impide un segundo voto
        self.votar()
        self.votar(hash_auditoria="d" * 64)
        self.assertEqual(self.usuario.votos.filter(votacion=self.votacion).count(), 2)

    def test_related_names(self):
        voto = self.votar()
        self.assertEqual(list(self.votacion.votos.all()), [voto])
        self.assertEqual(list(self.opcion.votos.all()), [voto])
        self.assertEqual(list(self.usuario.votos.all()), [voto])

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
        for objeto in (self.opcion, self.votacion, self.usuario):
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
