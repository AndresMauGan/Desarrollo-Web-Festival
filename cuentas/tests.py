"""Pruebas de cuentas: modelo Usuario, registro, inicio y cierre de sesión (CU-01)."""

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase

from .forms import VERSION_POLITICA_DATOS

Usuario = get_user_model()

VALIDO = {
    "email": "Nueva.Persona@Example.com", "nombre_para_mostrar": "Nueva Persona",
    "password1": "Acordeon-2027!", "password2": "Acordeon-2027!", "autoriza_datos": "on", "mayor_edad": "on",
}


class UsuarioTests(TestCase):
    def test_usuario_con_correo_y_sin_username(self):
        self.assertEqual(Usuario.USERNAME_FIELD, "email")
        nombres = {campo.name for campo in Usuario._meta.get_fields()}
        self.assertTrue({"username", "first_name", "last_name"}.isdisjoint(nombres))

    def test_create_user_exige_correo(self):
        with self.assertRaises(ValueError):
            Usuario.objects.create_user(email="", password="x")

    def test_create_user_y_str(self):
        usuario = Usuario.objects.create_user(email="ana@EXAMPLE.com", password="Clave-2027", nombre_para_mostrar="Ana")
        self.assertEqual(usuario.email, "ana@example.com")
        self.assertEqual(str(usuario), "Ana <ana@example.com>")
        self.assertFalse(usuario.is_staff or usuario.is_superuser or usuario.correo_verificado)

    def test_create_superuser(self):
        admin = Usuario.objects.create_superuser(email="admin@example.com", password="Admin-2027", nombre_para_mostrar="Admin")
        self.assertTrue(admin.is_staff and admin.is_superuser)

    def test_correo_unico(self):
        Usuario.objects.create_user(email="ana@example.com", password="Clave-2027", nombre_para_mostrar="Ana")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Usuario.objects.create_user(email="ana@example.com", password="Clave-2027", nombre_para_mostrar="Copia")


class RegistroTests(TestCase):
    def registrar(self, **cambios):
        datos = {**VALIDO, **cambios}
        return self.client.post("/cuentas/registro/", {k: v for k, v in datos.items() if v is not None})

    def test_formulario_con_casillas_separadas_y_sin_celular(self):
        respuesta = self.client.get("/cuentas/registro/")
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'name="autoriza_datos"')
        self.assertContains(respuesta, 'name="mayor_edad"')
        self.assertContains(respuesta, "(P-12)")
        self.assertNotContains(respuesta, "elular")

    def test_registro_valido_crea_el_usuario_e_inicia_sesion(self):
        respuesta = self.registrar()
        self.assertRedirects(respuesta, "/")
        usuario = Usuario.objects.get(email="nueva.persona@example.com")
        self.assertEqual(usuario.nombre_para_mostrar, "Nueva Persona")
        self.assertIsNotNone(usuario.autorizacion_datos_en)
        self.assertEqual(usuario.politica_datos_version, VERSION_POLITICA_DATOS)
        self.assertTrue(usuario.declara_mayor_edad)
        self.assertFalse(usuario.correo_verificado)  # RN-04 pendiente: no bloquea la sesión
        self.assertEqual(int(self.client.session["_auth_user_id"]), usuario.pk)

    def test_rechaza_datos_invalidos(self):
        casos = {
            "sin autorización de datos": {"autoriza_datos": None},
            "sin mayoría de edad": {"mayor_edad": None},
            "contraseñas distintas": {"password2": "Otra-Clave-2027"},
            "contraseña débil": {"password1": "123", "password2": "123"},
            "correo inválido": {"email": "no-es-correo"},
            "sin nombre": {"nombre_para_mostrar": ""},
        }
        for caso, cambios in casos.items():
            with self.subTest(caso=caso):
                respuesta = self.registrar(**cambios)
                self.assertEqual(respuesta.status_code, 200)
                self.assertFalse(Usuario.objects.exists())

    def test_rechaza_correo_repetido_aunque_cambien_mayusculas(self):
        Usuario.objects.create_user(email="nueva.persona@example.com", password="Clave-2027", nombre_para_mostrar="Primera")
        respuesta = self.registrar(email="NUEVA.Persona@example.com")
        self.assertContains(respuesta, "Ya existe una cuenta con este correo.")
        self.assertEqual(Usuario.objects.count(), 1)


class SesionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = Usuario.objects.create_user(email="ana@example.com", password="Clave-Segura-2027", nombre_para_mostrar="Ana")

    def test_inicio_de_sesion_correcto(self):
        respuesta = self.client.post("/cuentas/ingresar/", {"username": "ana@example.com", "password": "Clave-Segura-2027"})
        self.assertRedirects(respuesta, "/")
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.usuario.pk)

    def test_inicio_de_sesion_sin_importar_mayusculas_y_con_next(self):
        respuesta = self.client.post("/cuentas/ingresar/", {"username": "ANA@example.com", "password": "Clave-Segura-2027", "next": "/cuentas/"})
        self.assertRedirects(respuesta, "/cuentas/")

    def test_rechaza_contrasena_incorrecta(self):
        respuesta = self.client.post("/cuentas/ingresar/", {"username": "ana@example.com", "password": "otra"})
        self.assertContains(respuesta, "El correo o la contraseña no coinciden.")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_no_redirige_a_sitios_externos(self):
        respuesta = self.client.post("/cuentas/ingresar/", {"username": "ana@example.com", "password": "Clave-Segura-2027", "next": "https://externo.example/"})
        self.assertRedirects(respuesta, "/")

    def test_cierre_de_sesion_solo_por_post(self):
        self.client.force_login(self.usuario)
        self.assertEqual(self.client.get("/cuentas/salir/").status_code, 405)
        self.assertIn("_auth_user_id", self.client.session)
        self.assertRedirects(self.client.post("/cuentas/salir/"), "/")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_cuenta_exige_sesion(self):
        self.assertRedirects(self.client.get("/cuentas/"), "/cuentas/ingresar/?next=/cuentas/")
        self.client.force_login(self.usuario)
        self.assertContains(self.client.get("/cuentas/"), "ana@example.com")
