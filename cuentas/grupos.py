"""
Perfiles del sistema (entrega final):
- Superusuario: técnico; puede todo, incluida la gestión de usuarios.
- Administración del festival: is_staff y este grupo. Configura ediciones, categorías, votaciones y opciones,
  consulta los votos y la auditoría y ve los resultados. No gestiona usuarios.
- Votante: cuenta sin is_staff, registrada desde el sitio.
"""

from django.apps import apps
from django.contrib.auth.management import create_permissions
from django.contrib.auth.models import Group, Permission

GRUPO_ADMINISTRACION = "Administración del festival"

PERMISOS_ADMINISTRACION = [
    *(f"festival.{accion}_{modelo}" for modelo in ("edicion", "categoria", "votacion", "opcion")
      for accion in ("add", "change", "view")),
    "votos.view_voto",
    "votos.view_registroauditoria",
    "votos.ver_resultados",
]


def crear_grupo_administracion():
    """Crea el grupo, o lo actualiza, con exactamente PERMISOS_ADMINISTRACION. Es idempotente. Devuelve (grupo, creado)."""
    # Django crea los permisos después de las migraciones; así existen aunque la base se acabe de migrar
    for app_config in apps.get_app_configs():
        create_permissions(app_config, verbosity=0)
    permisos = [Permission.objects.get(content_type__app_label=nombre.split(".")[0], codename=nombre.split(".")[1])
                for nombre in PERMISOS_ADMINISTRACION]
    grupo, creado = Group.objects.get_or_create(name=GRUPO_ADMINISTRACION)
    grupo.permissions.set(permisos)
    return grupo, creado
