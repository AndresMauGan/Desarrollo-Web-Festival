"""
API de solo lectura (CU-02): GET /api/categorias/

Devuelve en JSON las categorías publicadas de la edición activa, o de ?edicion=<año>, cada una con su edición,
sus votaciones públicas (id, nombre, estado, horario) y sus opciones publicadas y activas (id, nombre, tipo,
descripción). No incluye conteos de votos (RN-06) ni datos personales.
"""

from django.db.models import Prefetch
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET

from .models import Edicion, Opcion, Votacion
from .views import ETIQUETAS_ESTADO, ESTADOS_PUBLICOS, edicion_activa

PARAMETROS_JSON = {"ensure_ascii": False, "indent": 2}


def _fecha(valor):
    return timezone.localtime(valor).isoformat() if valor else None


def _edicion(edicion):
    return {"anio": edicion.anio, "numero": edicion.numero, "nombre": edicion.nombre,
            "fecha_inicio": edicion.fecha_inicio.isoformat(), "fecha_fin": edicion.fecha_fin.isoformat(),
            "activa": edicion.activa}


def _votacion(votacion):
    return {
        "id": votacion.pk,
        "nombre": votacion.nombre,
        "ronda": votacion.ronda,
        "estado": votacion.estado,
        "estado_publico": ETIQUETAS_ESTADO[votacion.estado][0],
        "abre_en": _fecha(votacion.abre_en),
        "cierra_en": _fecha(votacion.cierra_en),
        "opciones": [{"id": o.pk, "nombre": o.nombre, "tipo": o.tipo, "descripcion": o.descripcion}
                     for o in votacion.opciones.all()],
    }


@csrf_exempt  # solo lectura; sin esto, un POST se detendría en CSRF (403) en lugar de responder 405
@require_GET
def categorias(request):
    anio = request.GET.get("edicion")
    if anio is None:
        edicion = edicion_activa()
        if edicion is None:
            return JsonResponse({"edicion": None, "categorias": []}, json_dumps_params=PARAMETROS_JSON)
    else:
        if not anio.isdigit():
            return JsonResponse({"error": "El parámetro «edicion» debe ser un año, por ejemplo 2027."},
                                status=400, json_dumps_params=PARAMETROS_JSON)
        edicion = Edicion.objects.filter(anio=int(anio)).first()
        if edicion is None:
            return JsonResponse({"error": f"No existe la edición {anio}."}, status=404, json_dumps_params=PARAMETROS_JSON)

    opciones = Opcion.objects.filter(publicada=True, estado=Opcion.Estado.ACTIVA).order_by("orden", "nombre")
    votaciones = (Votacion.objects.filter(estado__in=ESTADOS_PUBLICOS).order_by("abre_en", "nombre")
                  .prefetch_related(Prefetch("opciones", queryset=opciones)))
    categorias = (edicion.categorias.filter(publicada=True).order_by("orden", "nombre")
                  .prefetch_related(Prefetch("votaciones", queryset=votaciones)))

    datos = {
        "edicion": _edicion(edicion),
        "categorias": [
            {
                "id": c.pk,
                "nombre": c.nombre,
                "familia": c.familia,
                "nivel": c.nivel,
                "admite_voto_publico": c.admite_voto_publico,
                "edicion": {"anio": edicion.anio, "nombre": edicion.nombre},
                "votaciones": [_votacion(v) for v in c.votaciones.all()],
            }
            for c in categorias
        ],
    }
    return JsonResponse(datos, json_dumps_params=PARAMETROS_JSON)
