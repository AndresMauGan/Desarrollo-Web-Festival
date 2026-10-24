"""
Vistas públicas (CU-02, consultar). Muestran datos reales de MySQL y solo contenido publicado:
- Categorías con publicada=True.
- Votaciones que no están en borrador (decisión del equipo: «borrador» no es público).
- Opciones publicadas y activas.
Lo que no existe o no es público responde 404.
"""

from datetime import datetime, time

from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views.generic import DetailView, ListView, TemplateView

from .models import Categoria, Edicion, Votacion

# Estados que ve el público y su etiqueta. «Programada» se muestra como «Próximamente».
ETIQUETAS_ESTADO = {
    Votacion.Estado.PROGRAMADA: ("Próximamente", "badge-prox"),
    Votacion.Estado.ABIERTA: ("En vivo", "badge-vivo"),
    Votacion.Estado.PAUSADA: ("Pausada", "badge-pausada"),
    Votacion.Estado.CERRADA: ("Cerrada", "badge-cerrada"),
}
ESTADOS_PUBLICOS = list(ETIQUETAS_ESTADO)


def edicion_activa():
    """La edición activa más reciente. No hay regla de «una sola activa» (MySQL no admite restricciones únicas condicionales)."""
    return Edicion.objects.filter(activa=True).order_by("-anio").first()


def categorias_publicadas(edicion):
    """Categorías publicadas de una edición, con cuántas votaciones públicas tiene cada una."""
    return edicion.categorias.filter(publicada=True).annotate(
        votaciones_publicas=Count("votaciones", filter=Q(votaciones__estado__in=ESTADOS_PUBLICOS))
    )


class InicioView(TemplateView):
    """Pantalla 1 · Inicio: edición activa y sus categorías publicadas."""

    template_name = "festival/inicio.html"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        edicion = edicion_activa()
        contexto["edicion"] = edicion
        if edicion:
            contexto["categorias"] = categorias_publicadas(edicion)
            zona = timezone.get_current_timezone()
            inicio = timezone.make_aware(datetime.combine(edicion.fecha_inicio, time.min), zona)
            fin = timezone.make_aware(datetime.combine(edicion.fecha_fin, time.max), zona)
            ahora = timezone.now()
            contexto["fase"] = "antes" if ahora < inicio else "en_curso" if ahora <= fin else "terminada"
            contexto["inicio_iso"] = inicio.isoformat()
        return contexto


class EdicionListView(ListView):
    """Ediciones: lista."""

    model = Edicion
    template_name = "festival/ediciones.html"
    context_object_name = "ediciones"


class EdicionDetailView(DetailView):
    """Ediciones: detalle."""

    model = Edicion
    slug_field = "anio"
    slug_url_kwarg = "anio"
    template_name = "festival/edicion.html"
    context_object_name = "edicion"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["total_categorias"] = self.object.categorias.filter(publicada=True).count()
        return contexto


def categorias_actuales(request):
    """Acceso de la barra inferior: lleva a las categorías de la edición activa."""
    edicion = edicion_activa()
    if edicion is None:
        return redirect("festival:ediciones")
    return redirect("festival:categorias", anio=edicion.anio)


class CategoriasEdicionView(ListView):
    """Pantalla 4 · Categorías de una edición (solo publicadas)."""

    template_name = "festival/categorias.html"
    context_object_name = "categorias"

    def get_queryset(self):
        self.edicion = get_object_or_404(Edicion, anio=self.kwargs["anio"])
        return categorias_publicadas(self.edicion)

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["edicion"] = self.edicion
        return contexto


class CategoriaDetailView(DetailView):
    """Pantalla 5 · Votaciones de una categoría, con su estado."""

    queryset = Categoria.objects.filter(publicada=True).select_related("edicion")
    template_name = "festival/categoria.html"
    context_object_name = "categoria"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["votaciones"] = self.object.votaciones.filter(estado__in=ESTADOS_PUBLICOS)
        return contexto


class VotacionDetailView(DetailView):
    """Pantalla 6 · Detalle de la votación: horario, reglas provisionales y opciones publicadas. Sin conteos."""

    queryset = Votacion.objects.filter(categoria__publicada=True, estado__in=ESTADOS_PUBLICOS).select_related("categoria__edicion")
    template_name = "festival/votacion.html"
    context_object_name = "votacion"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["opciones"] = self.object.opciones_publicadas()
        return contexto
