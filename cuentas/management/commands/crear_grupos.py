"""
Crea o actualiza el grupo «Administración del festival» con sus permisos. Se puede ejecutar varias veces.

    python manage.py crear_grupos
    python manage.py crear_grupos --asignar persona@ejemplo.org

Con --asignar, una cuenta que ya existe pasa a ser administradora del festival (is_staff y el grupo).
No crea usuarios ni contraseñas: la cuenta se registra antes desde el sitio o con createsuperuser.
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from cuentas.grupos import GRUPO_ADMINISTRACION, PERMISOS_ADMINISTRACION, crear_grupo_administracion


class Command(BaseCommand):
    help = "Crea o actualiza el grupo «Administración del festival» con sus permisos."

    def add_arguments(self, parser):
        parser.add_argument("--asignar", nargs="+", metavar="CORREO", default=[],
                            help="Correos de cuentas existentes que pasan a ser administradoras del festival.")

    def handle(self, *args, asignar, **opciones):
        grupo, creado = crear_grupo_administracion()
        self.stdout.write(self.style.SUCCESS(
            f"Grupo «{GRUPO_ADMINISTRACION}» {'creado' if creado else 'actualizado'} con {len(PERMISOS_ADMINISTRACION)} permisos:"))
        for permiso in grupo.permissions.select_related("content_type").order_by("content_type__app_label", "codename"):
            self.stdout.write(f"  {permiso.content_type.app_label}.{permiso.codename} · {permiso.name}")
        Usuario = get_user_model()
        for correo in asignar:
            usuario = Usuario.objects.filter(email__iexact=correo).first()
            if usuario is None:
                raise CommandError(f"No existe una cuenta con el correo {correo}. Regístrala primero desde el sitio.")
            usuario.is_staff = True
            usuario.save(update_fields=["is_staff"])
            usuario.groups.add(grupo)
            self.stdout.write(f"{usuario.email} ahora tiene el perfil de administración del festival (personal y grupo).")
        if not asignar:
            self.stdout.write("Para dar este perfil a una cuenta: --asignar <correo>, o en el admin marca «Es staff» y agrega el grupo.")
