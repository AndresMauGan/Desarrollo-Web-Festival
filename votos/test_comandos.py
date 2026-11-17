"""
Prueba del comando probar_concurrencia (Parte D): trabaja en una base temporal y no deja datos en la real.

Crear de verdad otra base dentro de las pruebas no es posible (ya se está en test_<DB_NAME>), así que se
simulan create_test_db y destroy_test_db y la demostración corre en la base de pruebas. Lo que se comprueba
es el recorrido: crea la base temporal, carga datos, deja un solo voto y elimina la base (o la conserva).
"""

from io import StringIO
from unittest import mock, skipUnless

from django.core.management import CommandError, call_command
from django.db import connection
from django.test import TransactionTestCase


@skipUnless(connection.vendor == "mysql", "probar_concurrencia necesita MySQL")
class ProbarConcurrenciaTests(TransactionTestCase):
    def ejecutar(self, *argumentos):
        salida = StringIO()
        creation = connection.creation
        with mock.patch.object(creation, "create_test_db") as crear, mock.patch.object(creation, "destroy_test_db") as destruir:
            call_command("probar_concurrencia", *argumentos, "--no-input", stdout=salida)
        return salida.getvalue(), crear, destruir

    def test_crea_y_elimina_la_base_temporal(self):
        original = connection.settings_dict["NAME"]
        salida, crear, destruir = self.ejecutar("--solicitudes", "4", "--forzar-carrera")
        crear.assert_called_once()
        destruir.assert_called_once_with(original, verbosity=0)
        self.assertIn(f"Base temporal: {connection.creation._get_test_db_name()}", salida)
        self.assertIn("Correcto: de 4 solicitudes simultáneas quedó un solo voto (RN-01).", salida)
        self.assertIn("se eliminó: no quedó ningún dato", salida)

    def test_con_conservar_no_la_elimina(self):
        original = connection.settings_dict["NAME"]
        salida, crear, destruir = self.ejecutar("--conservar")
        destruir.assert_not_called()
        self.assertIn("se conservó", salida)
        self.assertIn(".votos_voto WHERE usuario_id =", salida)
        self.assertEqual(connection.settings_dict["NAME"], original)  # la conexión vuelve a la base de siempre

    def test_valida_las_solicitudes_antes_de_crear_nada(self):
        with mock.patch.object(connection.creation, "create_test_db") as crear, self.assertRaises(CommandError):
            call_command("probar_concurrencia", "--solicitudes", "1", stdout=StringIO())
        crear.assert_not_called()
