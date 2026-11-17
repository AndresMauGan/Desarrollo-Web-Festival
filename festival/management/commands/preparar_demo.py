"""
Deja lista la base de demostración antes de la sustentación. Solo funciona si DB_NAME termina en «_demo».

    python manage.py preparar_demo

1. Verifica que no falten migraciones; si faltan, pide ejecutar migrate y se detiene.
2. Recarga los datos de prueba con horarios vigentes (cargar_datos_prueba, sin preguntar).
3. Crea o actualiza el grupo «Administración del festival».
4. Imprime un resumen: votaciones abiertas, id de las categorías y qué perfiles faltan por crear.

No crea usuarios ni contraseñas: el superusuario se crea con createsuperuser y las demás cuentas
se registran desde el sitio.
"""

from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from cuentas.grupos import GRUPO_ADMINISTRACION, crear_grupo_administracion
from festival.templatetags.festival_extras import fecha_hora_co
from festival.views import edicion_activa
from votos.models import Voto
from votos.servicios import se_puede_votar, votaciones_abiertas


class Command(BaseCommand):
    help = "Prepara la base de demostración (DB_NAME terminado en «_demo») para la sustentación."

    def handle(self, *args, **opciones):
        base = connection.settings_dict["NAME"]
        if not base.endswith("_demo"):
            raise CommandError(f"preparar_demo solo se ejecuta en la base de demostración: DB_NAME debe terminar en «_demo» "
                               f"(por ejemplo, festival_demo) y ahora es «{base}».")
        self.stdout.write(f"Base de demostración: {base}")

        # 1. Migraciones
        ejecutor = MigrationExecutor(connection)
        pendientes = ejecutor.migration_plan(ejecutor.loader.graph.leaf_nodes())
        if pendientes:
            raise CommandError(f"Faltan {len(pendientes)} migraciones. Ejecuta «python manage.py migrate» y vuelve a intentarlo.")
        self.stdout.write("1. Migraciones al día.")

        # 2. Datos de prueba con horarios vigentes
        call_command("cargar_datos_prueba", interactive=False, permitir_sin_debug=True, stdout=StringIO())
        self.stdout.write("2. Datos de prueba recargados: las votaciones abiertas quedan abiertas desde hace una hora y por 30 días.")

        # 3. Grupos
        grupo, _ = crear_grupo_administracion()
        self.stdout.write(f"3. Grupo «{GRUPO_ADMINISTRACION}» listo con {grupo.permissions.count()} permisos.")

        # 4. Resumen
        self.stdout.write("\n4. Resumen")
        edicion = edicion_activa()
        self.stdout.write(f"Edición activa: {edicion}" if edicion else "No hay edición activa.")
        if edicion:
            for categoria in edicion.categorias.filter(publicada=True).order_by("orden", "nombre"):
                estado = "se puede votar" if se_puede_votar(categoria) else "sin votación abierta"
                self.stdout.write(f"  Categoría id {categoria.pk}: {categoria.nombre} · {estado} · /votar/categoria/{categoria.pk}/")
                for votacion in votaciones_abiertas(categoria):
                    self.stdout.write(f"      Votación abierta id {votacion.pk}: {votacion.nombre} (hasta el {fecha_hora_co(votacion.cierra_en)})")
        votos = Voto.objects.count()
        self.stdout.write(f"Votos ya registrados en esta base: {votos}"
                          + (" (de ensayos anteriores; los votos no se borran, RN-02)." if votos else "."))

        Usuario = get_user_model()
        perfiles = [
            ("Superusuario (técnico)", Usuario.objects.filter(is_superuser=True).exists(),
             "python manage.py createsuperuser"),
            ("Administración del festival", Usuario.objects.filter(is_staff=True, is_superuser=False, groups=grupo).exists(),
             "registra la cuenta en /cuentas/registro/ y luego: python manage.py crear_grupos --asignar <correo>"),
            ("Votante", Usuario.objects.filter(is_staff=False, is_active=True).exists(),
             "regístrala en /cuentas/registro/"),
        ]
        self.stdout.write("Perfiles para la demostración:")
        for perfil, existe, como in perfiles:
            self.stdout.write(f"  {perfil}: {'listo' if existe else 'FALTA: ' + como}")
        self.stdout.write(self.style.SUCCESS("\nBase de demostración lista. Inicia el servidor con «python manage.py runserver»."))
