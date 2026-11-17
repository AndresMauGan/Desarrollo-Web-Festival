"""
Administración dinámica: configurar una edición nueva (por ejemplo, 2028) desde el admin, sin tocar el código.

duplicar_edicion copia de otra edición solo la estructura:
- sus categorías, sin publicar;
- las votaciones de cada categoría, en estado borrador, con el horario corrido según la nueva fecha de inicio.
Nunca copia opciones, votos ni registros de auditoría. La edición nueva queda inactiva.
"""

from django.db import transaction

from .models import Categoria, Edicion, Votacion


def un_anio_despues(fecha):
    try:
        return fecha.replace(year=fecha.year + 1)
    except ValueError:  # 29 de febrero
        return fecha.replace(year=fecha.year + 1, day=28)


def valores_para_la_siguiente(origen):
    """Valores sugeridos para la edición siguiente a origen; el administrador los revisa en el formulario."""
    numero = origen.numero + 1
    return {
        "anio": origen.anio + 1,
        "numero": numero,
        "nombre": origen.nombre.replace(f"{origen.numero}.º", f"{numero}.º", 1),
        "fecha_inicio": un_anio_despues(origen.fecha_inicio),
        "fecha_fin": un_anio_despues(origen.fecha_fin),
    }


@transaction.atomic
def duplicar_edicion(origen, *, anio, numero, nombre, fecha_inicio, fecha_fin, homenaje=""):
    """Crea la edición nueva con la copia de la estructura de origen. Devuelve (edición, categorías, votaciones)."""
    nueva = Edicion(anio=anio, numero=numero, nombre=nombre, fecha_inicio=fecha_inicio, fecha_fin=fecha_fin,
                    homenaje=homenaje, activa=False)
    nueva.full_clean()
    nueva.save()

    desplazamiento = fecha_inicio - origen.fecha_inicio

    def con_el_anio_nuevo(texto):
        return texto.replace(str(origen.anio), str(anio))

    categorias = votaciones = 0
    for categoria in origen.categorias.order_by("orden", "nombre").prefetch_related("votaciones"):
        copia = Categoria.objects.create(
            edicion=nueva, nombre=con_el_anio_nuevo(categoria.nombre), familia=categoria.familia, nivel=categoria.nivel,
            es_rey_de_reyes=categoria.es_rey_de_reyes, admite_voto_publico=categoria.admite_voto_publico,
            publicada=False, orden=categoria.orden,
        )
        categorias += 1
        for votacion in categoria.votaciones.all():
            Votacion.objects.create(
                categoria=copia, nombre=con_el_anio_nuevo(votacion.nombre), ronda=votacion.ronda,
                estado=Votacion.Estado.BORRADOR, abre_en=votacion.abre_en + desplazamiento,
                cierra_en=votacion.cierra_en + desplazamiento, visibilidad_resultados=votacion.visibilidad_resultados,
            )
            votaciones += 1
    return nueva, categorias, votaciones
