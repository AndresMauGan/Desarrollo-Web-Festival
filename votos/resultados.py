"""
Resultados (CU-05): conteo de los votos guardados en MySQL.

- Los conteos se calculan con agregaciones del ORM (Count). Para una edición completa son tres consultas,
  sin importar cuántas categorías, votaciones u opciones haya:
  1. categorías, con cuántas personas votaron en cada una;
  2. votaciones, sin las que están en borrador;
  3. opciones, con su número de votos.
- Count hace LEFT JOIN, así que las opciones sin votos aparecen con 0.
- No se usan funciones de fecha de MySQL (TruncDate, TruncHour…): fallan sin las tablas de zonas horarias.

Visibilidad para el público (RN-06, pendiente P-05): la elige el administrador en cada votación.
"""

from django.db.models import Count, Prefetch, Q

from festival.models import Opcion, Votacion
from festival.templatetags.festival_extras import fecha_hora_co


def opciones_con_votos():
    """
    Opciones con su número de votos (num_votos), de mayor a menor.

    Incluye las publicadas y activas, aunque tengan 0 votos, y también las retiradas o sin publicar que ya
    recibieron votos, para que los totales coincidan con la tabla votos_voto.
    """
    return (Opcion.objects.annotate(num_votos=Count("votos"))
            .filter(Q(publicada=True, estado=Opcion.Estado.ACTIVA) | Q(num_votos__gt=0))
            .order_by("-num_votos", "orden", "nombre"))


def calcular_porcentajes(votacion, opciones):
    """Agrega a la votación su total y a cada opción su porcentaje y el ancho de su barra (texto con punto, para CSS)."""
    total = sum(opcion.num_votos for opcion in opciones)
    for opcion in opciones:
        opcion.porcentaje = round(opcion.num_votos * 100 / total, 1) if total else 0.0
        opcion.ancho_barra = f"{opcion.porcentaje:.1f}"
        # Solo aparecen así las opciones que ya tenían votos (ver opciones_con_votos)
        opcion.aviso = ("Retirada" if opcion.estado == Opcion.Estado.RETIRADA
                        else "Sin publicar" if not opcion.publicada else "")
    votacion.total_votos = total
    votacion.resultados = opciones
    return votacion


def resultados_de_edicion(edicion):
    """Categorías de la edición con sus votaciones y opciones contadas. Hace tres consultas en total."""
    votaciones = (Votacion.objects.exclude(estado=Votacion.Estado.BORRADOR).order_by("abre_en", "nombre")
                  .prefetch_related(Prefetch("opciones", queryset=opciones_con_votos(), to_attr="opciones_contadas")))
    categorias = list(
        edicion.categorias.annotate(votantes=Count("votos")).order_by("orden", "nombre")
        .prefetch_related(Prefetch("votaciones", queryset=votaciones, to_attr="votaciones_contadas"))
    )
    for categoria in categorias:
        for votacion in categoria.votaciones_contadas:
            calcular_porcentajes(votacion, votacion.opciones_contadas)
            votacion.visible_al_publico, votacion.explicacion_publica = resultados_visibles(votacion)
    return categorias


def resultados_de_votacion(votacion):
    """Una votación con sus opciones contadas (una consulta)."""
    return calcular_porcentajes(votacion, list(opciones_con_votos().filter(votacion=votacion)))


def resultados_visibles(votacion):
    """
    Si el público puede ver los resultados de la votación y por qué, según su visibilidad_resultados.

    - en_vivo: siempre.
    - al_cierre: solo cuando la votación está cerrada (estado «cerrada»).
    - en_ceremonia: solo cuando el personal marca «resultados publicados».

    Devuelve (visibles, explicación).
    """
    Visibilidad = Votacion.Visibilidad
    if votacion.visibilidad_resultados == Visibilidad.EN_VIVO:
        return True, "Los resultados se muestran en vivo mientras avanza la votación."
    if votacion.visibilidad_resultados == Visibilidad.AL_CIERRE:
        if votacion.estado == Votacion.Estado.CERRADA:
            return True, "La votación ya cerró: estos son sus resultados."
        return False, (f"Los resultados se publicarán cuando cierre la votación "
                       f"(cierre previsto: {fecha_hora_co(votacion.cierra_en)}).")
    if votacion.visibilidad_resultados == Visibilidad.EN_CEREMONIA:
        if votacion.resultados_publicados:
            return True, "Los resultados se dieron a conocer en la ceremonia de premiación."
        return False, "Los resultados se darán a conocer en la ceremonia de premiación del Festival."
    return False, "Los resultados todavía no están disponibles."
