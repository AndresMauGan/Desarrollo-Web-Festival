"""
Demostración reproducible de CP-09, fuera de las pruebas automáticas.

Crea un votante desechable y envía varias solicitudes de voto simultáneas a la misma categoría. Cada
solicitud corre en su propio hilo, con su propia conexión a MySQL. Al final cuenta con SQL directo los
votos de ese votante en la categoría: siempre debe quedar uno.

    python manage.py probar_concurrencia
    python manage.py probar_concurrencia --solicitudes 8 --forzar-carrera
    python manage.py probar_concurrencia --categoria 3

Con --forzar-carrera todas las solicitudes pasan las validaciones de Django antes de que alguna inserte,
así que la única protección que queda es la restricción única de MySQL.

Úsalo en la base de desarrollo, con los datos de cargar_datos_prueba:
- El votante desechable no tiene contraseña, así que nadie puede iniciar sesión con él.
- Él y su voto quedan guardados, porque los votos son inmutables (RN-02) y las relaciones usan PROTECT (RN-10).
"""

import secrets

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.utils import timezone

from festival.models import Categoria
from festival.views import edicion_activa
from votos.concurrencia import votar_a_la_vez
from votos.models import RegistroAuditoria
from votos.servicios import VotoRechazado, opciones_disponibles, se_puede_votar, verificar_categoria

SQL_CONTEO = "SELECT COUNT(*) FROM votos_voto WHERE usuario_id = %s AND categoria_id = %s AND edicion_id = %s"


class Command(BaseCommand):
    help = "Demuestra que varias solicitudes simultáneas en la misma categoría dejan un solo voto (CP-09)."

    def add_arguments(self, parser):
        parser.add_argument("--solicitudes", type=int, default=2,
                            help="Cuántas solicitudes simultáneas enviar, de 2 a 20 (por defecto 2).")
        parser.add_argument("--categoria", type=int,
                            help="Id de la categoría. Por defecto, la primera abierta de la edición activa.")
        parser.add_argument("--forzar-carrera", action="store_true",
                            help="Todas las solicitudes pasan las validaciones de Django antes de insertar; "
                                 "solo la restricción única de MySQL puede detener los duplicados.")

    def handle(self, *args, solicitudes, categoria, forzar_carrera, **opciones):
        if not 2 <= solicitudes <= 20:
            raise CommandError("--solicitudes debe estar entre 2 y 20.")
        categoria = self.elegir_categoria(categoria)
        disponibles = list(opciones_disponibles(categoria))
        if not disponibles:
            raise CommandError(f"{categoria.nombre} no tiene opciones publicadas y activas para votar.")
        nombres = {o.pk: f"{o.nombre} · {o.votacion.nombre}" for o in disponibles}
        # Una opción distinta por solicitud mientras alcancen, también de otros subeventos de la categoría
        opciones_ids = [disponibles[n % len(disponibles)].pk for n in range(solicitudes)]

        votante = get_user_model().objects.create_user(
            email=f"concurrencia-{timezone.localtime():%Y%m%d-%H%M%S}-{secrets.token_hex(2)}@example.invalid",
            nombre_para_mostrar="Prueba de concurrencia",
        )  # sin contraseña: la cuenta no puede iniciar sesión

        self.stdout.write(f"Categoría: {categoria.nombre} · {categoria.edicion.nombre} (id {categoria.pk})")
        self.stdout.write(f"Votante desechable: {votante.email} (id {votante.pk})")
        modo = ("forzando la carrera: todas pasan las validaciones de Django antes de insertar"
                if forzar_carrera else "todas salen al mismo tiempo")
        self.stdout.write(f"Enviando {solicitudes} solicitudes simultáneas, {modo}...\n")

        resultados = votar_a_la_vez(votante, categoria.pk, opciones_ids, forzar_carrera=forzar_carrera)
        for r in resultados:
            self.stdout.write(f"  Solicitud {r['solicitud']}: {nombres[r['opcion']]}")
            self.stdout.write(f"    {r['resultado'].upper()}: {r['detalle']}")

        with connection.cursor() as cursor:
            cursor.execute(SQL_CONTEO, [votante.pk, categoria.pk, categoria.edicion_id])
            en_mysql = cursor.fetchone()[0]
        auditoria = RegistroAuditoria.objects.filter(usuario=votante)
        por_django = auditoria.filter(accion="Voto rechazado: ya votó en la categoría").count()
        por_mysql = auditoria.filter(accion="Voto duplicado detenido por la base de datos").count()
        registrados = sum(r["resultado"] == "registrado" for r in resultados)
        errores = [r for r in resultados if r["resultado"] == "error"]

        self.stdout.write("\nResumen")
        self.stdout.write(f"  Registrados: {registrados}")
        self.stdout.write(f"  Rechazados por la validación de Django (paso 5): {por_django}")
        self.stdout.write(f"  Detenidos por la restricción única de MySQL (IntegrityError): {por_mysql}")
        self.stdout.write(f"  Errores inesperados: {len(errores)}")
        self.stdout.write(f"  Votos en votos_voto para este votante en la categoría: {en_mysql}")
        self.stdout.write(f"  Compruébalo en MySQL: SELECT * FROM votos_voto WHERE usuario_id = {votante.pk};")

        if en_mysql != 1 or registrados != 1 or errores:
            raise CommandError("La prueba falló: debía quedar exactamente un voto y ningún error.")
        self.stdout.write(self.style.SUCCESS(
            f"\nCorrecto: de {solicitudes} solicitudes simultáneas quedó un solo voto (RN-01)."))
        self.stdout.write("El votante desechable y su voto quedan en la base: los votos son inmutables (RN-02).")

    def elegir_categoria(self, categoria_id):
        if categoria_id is not None:
            categoria = Categoria.objects.select_related("edicion").filter(pk=categoria_id, publicada=True).first()
            if categoria is None:
                raise CommandError(f"No hay una categoría publicada con id {categoria_id}.")
            try:
                verificar_categoria(categoria)
            except VotoRechazado as rechazo:
                raise CommandError(f"{categoria.nombre}: {rechazo.mensaje}") from None
            return categoria
        edicion = edicion_activa()
        if edicion:
            for categoria in edicion.categorias.filter(publicada=True).select_related("edicion").order_by("orden", "nombre"):
                if se_puede_votar(categoria) and opciones_disponibles(categoria).exists():
                    return categoria
        raise CommandError("No hay categorías con votaciones abiertas. Ejecuta primero «python manage.py cargar_datos_prueba».")
