"""
Pruebas de los comandos de la entrega final (Parte D): respaldar_base y preparar_demo.
"""

import secrets
import shutil
import sys
import tempfile
from io import StringIO
from pathlib import Path
from unittest import mock, skipUnless

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import CommandError, call_command
from django.db import connection
from django.test import TestCase

from cuentas.grupos import GRUPO_ADMINISTRACION
from votos.test_casos_prueba import crear_escenario

from .management.commands.respaldar_base import buscar_mysqldump
from .models import Edicion


class RespaldarBaseTests(TestCase):
    def setUp(self):
        self.carpeta = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.carpeta, ignore_errors=True)

    def respaldar_con_mysqldump_simulado(self, codigo=0):
        llamadas = []

        def mysqldump_simulado(comando, **kwargs):
            opciones = next(a for a in comando if a.startswith("--defaults-extra-file=")).split("=", 1)[1]
            destino = Path(next(a for a in comando if a.startswith("--result-file=")).split("=", 1)[1])
            llamadas.append({"comando": comando, "opciones": Path(opciones).read_text(encoding="utf-8")})
            if codigo == 0:
                destino.write_text("-- respaldo simulado\n", encoding="utf-8")
            return mock.Mock(returncode=codigo, stderr="Access denied" if codigo else "")

        clave = secrets.token_urlsafe(12)  # contraseña simulada, generada en memoria
        with mock.patch.object(connection, "vendor", "mysql"), \
                mock.patch.dict(connection.settings_dict, {"PASSWORD": clave}), \
                mock.patch("festival.management.commands.respaldar_base.subprocess.run", side_effect=mysqldump_simulado):
            call_command("respaldar_base", mysqldump=sys.executable, carpeta=str(self.carpeta), stdout=StringIO())
        return {**llamadas[0], "clave": clave}

    def test_la_contrasena_no_va_en_la_linea_de_comandos(self):
        llamada = self.respaldar_con_mysqldump_simulado()
        self.assertTrue(all(llamada["clave"] not in argumento for argumento in llamada["comando"]))
        self.assertIn(f'password="{llamada["clave"]}"', llamada["opciones"])  # va en el archivo de opciones temporal...
        archivo = next(a for a in llamada["comando"] if a.startswith("--defaults-extra-file=")).split("=", 1)[1]
        self.assertFalse(Path(archivo).exists())  # ...que se borra al terminar
        self.assertTrue(llamada["comando"][1].startswith("--defaults-extra-file="))
        for opcion in ("--single-transaction", "--no-tablespaces"):
            self.assertIn(opcion, llamada["comando"])

    def test_nombre_del_archivo_con_fecha_y_hora(self):
        self.respaldar_con_mysqldump_simulado()
        self.respaldar_con_mysqldump_simulado()  # dos en el mismo minuto no se pisan
        nombres = sorted(p.name for p in self.carpeta.iterdir())
        self.assertEqual(len(nombres), 2)
        self.assertRegex(nombres[0], r"^\d{4}-\d{2}-\d{2}_\d{4}(-2)?\.sql$")

    def test_si_mysqldump_falla_no_queda_un_respaldo_a_medias(self):
        with self.assertRaisesMessage(CommandError, "mysqldump falló"):
            self.respaldar_con_mysqldump_simulado(codigo=2)
        self.assertEqual(list(self.carpeta.iterdir()), [])

    def test_avisa_si_no_encuentra_mysqldump(self):
        with mock.patch.object(connection, "vendor", "mysql"), self.assertRaisesMessage(CommandError, "No encontré mysqldump"):
            call_command("respaldar_base", mysqldump=str(self.carpeta / "no-existe.exe"), stdout=StringIO())

    @skipUnless(connection.vendor == "mysql" and buscar_mysqldump(), "Necesita MySQL y mysqldump")
    def test_respaldo_real_de_la_base_de_pruebas(self):
        call_command("respaldar_base", carpeta=str(self.carpeta), stdout=StringIO())
        respaldo = next(self.carpeta.iterdir()).read_text(encoding="utf-8")
        self.assertIn("CREATE TABLE `votos_voto`", respaldo)
        self.assertIn("un_voto_por_usuario_categoria_edicion", respaldo)
        self.assertNotIn(connection.settings_dict["PASSWORD"], respaldo)


class PrepararDemoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        crear_escenario(cls)

    def preparar(self):
        salida = StringIO()
        with mock.patch.dict(connection.settings_dict, {"NAME": "festival_demo"}):
            call_command("preparar_demo", stdout=salida)
        return salida.getvalue()

    def test_solo_en_la_base_de_demostracion(self):
        with self.assertRaisesMessage(CommandError, "solo se ejecuta en la base de demostración"):
            call_command("preparar_demo", stdout=StringIO())

    def test_recarga_datos_crea_grupos_y_resume_sin_crear_usuarios(self):
        usuarios = get_user_model().objects.count()
        salida = self.preparar()
        self.assertEqual(get_user_model().objects.count(), usuarios)
        self.assertTrue(Group.objects.filter(name=GRUPO_ADMINISTRACION).exists())
        self.assertTrue(Edicion.objects.filter(anio=2026).exists())
        self.assertIn("Migraciones al día", salida)
        self.assertRegex(salida, r"Categoría id \d+: Acordeonera Mayor · se puede votar")
        self.assertIn("Votación abierta id", salida)
        # Ana y Beto son votantes; faltan el superusuario y la administración del festival
        self.assertIn("Superusuario (técnico): FALTA: python manage.py createsuperuser", salida)
        self.assertIn("Administración del festival: FALTA", salida)
        self.assertIn("Votante: listo", salida)

    def test_se_detiene_si_faltan_migraciones(self):
        with mock.patch("festival.management.commands.preparar_demo.MigrationExecutor") as ejecutor:
            ejecutor.return_value.migration_plan.return_value = ["votos.0004_pendiente"]
            with self.assertRaisesMessage(CommandError, "Faltan 1 migraciones"):
                self.preparar()
