"""
Respaldo de la base MySQL configurada en .env, con mysqldump.

    python manage.py respaldar_base
    python manage.py respaldar_base --mysqldump "C:\\Program Files\\MySQL\\MySQL Server 8.0\\bin\\mysqldump.exe"

- Guarda el respaldo en respaldos/AAAA-MM-DD_HHMM.sql; la carpeta respaldos/ no se sube a Git.
- La contraseña nunca va en la línea de comandos (otros procesos podrían verla): se pasa en un archivo de
  opciones temporal (--defaults-extra-file) que se borra en cuanto termina mysqldump.
- --single-transaction hace una copia consistente sin bloquear las tablas (InnoDB).
- --no-tablespaces evita el error de privilegio PROCESS, que el usuario de la aplicación no tiene.
El README explica cómo restaurarlo.
"""

import glob
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.utils import timezone

# Dónde suele quedar mysqldump en Windows cuando no está en el PATH
RUTAS_WINDOWS = "C:/Program Files/MySQL/MySQL Server */bin/mysqldump.exe"


def buscar_mysqldump(indicado=None):
    """Ruta de mysqldump: la indicada, la del PATH o la de la instalación de MySQL en Windows; None si no está."""
    if indicado:
        return indicado if Path(indicado).is_file() else None
    return shutil.which("mysqldump") or next(iter(sorted(glob.glob(RUTAS_WINDOWS), reverse=True)), None)


def valor_de_opcion(texto):
    """Valor entre comillas para un archivo de opciones de MySQL (admite #, espacios y comillas)."""
    return '"' + str(texto).replace("\\", "\\\\").replace('"', '\\"') + '"'


class Command(BaseCommand):
    help = "Respalda la base de datos MySQL configurada en .env con mysqldump (respaldos/AAAA-MM-DD_HHMM.sql)."

    def add_arguments(self, parser):
        parser.add_argument("--mysqldump", help="Ruta de mysqldump, si no está en el PATH.")
        parser.add_argument("--carpeta", help="Carpeta donde guardar el respaldo (por defecto, respaldos/).")

    def handle(self, *args, mysqldump=None, carpeta=None, **opciones):
        if connection.vendor != "mysql":
            raise CommandError("respaldar_base solo funciona con MySQL.")
        programa = buscar_mysqldump(mysqldump)
        if programa is None:
            raise CommandError("No encontré mysqldump. Viene con MySQL Server; indica su ruta con --mysqldump.")
        datos = connection.settings_dict
        carpeta = Path(carpeta) if carpeta else Path(settings.BASE_DIR) / "respaldos"
        carpeta.mkdir(parents=True, exist_ok=True)
        nombre = f"{timezone.localtime():%Y-%m-%d_%H%M}"
        destino = carpeta / f"{nombre}.sql"
        n = 2
        while destino.exists():  # dos respaldos en el mismo minuto
            destino, n = carpeta / f"{nombre}-{n}.sql", n + 1

        # Archivo de opciones temporal con las credenciales; solo existe mientras corre mysqldump
        with tempfile.NamedTemporaryFile("w", suffix=".cnf", delete=False, encoding="utf-8") as archivo:
            archivo.write("[client]\n")
            archivo.write(f"user={valor_de_opcion(datos['USER'])}\n")
            archivo.write(f"password={valor_de_opcion(datos['PASSWORD'])}\n")
            archivo.write(f"host={valor_de_opcion(datos['HOST'] or 'localhost')}\n")
            archivo.write(f"port={int(datos['PORT'] or 3306)}\n")
            opciones_mysql = archivo.name
        comando = [
            programa, f"--defaults-extra-file={opciones_mysql}",  # tiene que ser la primera opción
            "--single-transaction", "--triggers", "--no-tablespaces", "--set-gtid-purged=OFF",
            "--default-character-set=utf8mb4", f"--result-file={destino}", datos["NAME"],
        ]
        try:
            resultado = subprocess.run(comando, capture_output=True, text=True, encoding="utf-8", errors="replace")
        finally:
            os.remove(opciones_mysql)
        if resultado.returncode != 0:
            destino.unlink(missing_ok=True)
            raise CommandError(f"mysqldump falló: {resultado.stderr.strip()}")

        tamano = destino.stat().st_size / 1024
        try:  # ruta relativa al proyecto: la completa puede tener espacios, que rompen el «<» de cmd
            mostrar = destino.resolve().relative_to(Path(settings.BASE_DIR).resolve())
        except ValueError:
            mostrar = destino
        self.stdout.write(self.style.SUCCESS(f"Respaldo de «{datos['NAME']}» guardado en {mostrar} ({tamano:.0f} KB)."))
        self.stdout.write("Para restaurarlo desde la carpeta del proyecto (ver «Respaldos y restauración» en el README):\n"
                          f'  cmd /c "mysql -u {datos["USER"]} -p {datos["NAME"]} < {mostrar}"')
