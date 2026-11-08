"""
CU-03 · Emitir voto. Flujo: elegir categoría → elegir opción → confirmar → registrar → comprobante.

- Todas las vistas exigen sesión (LoginRequiredMixin); sin sesión redirigen al inicio de sesión con «next».
- El voto solo se crea en votos.servicios.registrar_voto, que valida todo en el servidor.
- Cada rechazo muestra un mensaje con django.contrib.messages y responde 400, 403 o 404 según el caso.
"""

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import redirect_to_login
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import DetailView, ListView

from festival.models import Categoria
from festival.views import edicion_activa

from .forms import ElegirOpcionForm
from .models import Voto
from .servicios import (VotoRechazado, opciones_disponibles, registrar_voto, se_puede_votar, verificar_categoria,
                        voto_en_categoria)


def _categoria_publicada(pk):
    return get_object_or_404(Categoria.objects.select_related("edicion"), pk=pk, publicada=True)


def pagina_de_votacion(request, categoria, form=None, status=200):
    """Página de votación de una categoría: sus votaciones abiertas con sus opciones, o el voto ya emitido."""
    voto = voto_en_categoria(request.user, categoria)
    motivo = None
    grupos = []
    if voto is None:
        try:
            verificar_categoria(categoria)
        except VotoRechazado as rechazo:
            motivo = rechazo.mensaje
        else:
            # Subeventos abiertos con sus opciones, en el orden en que se muestran
            for opcion in opciones_disponibles(categoria):
                if not grupos or grupos[-1][0] != opcion.votacion:
                    grupos.append((opcion.votacion, []))
                grupos[-1][1].append(opcion)
    contexto = {
        "categoria": categoria,
        "voto": voto,
        "motivo": motivo,
        "grupos": grupos,
        "form": form or ElegirOpcionForm(categoria=categoria),
    }
    return render(request, "votos/votar.html", contexto, status=status)


class VotarCategoriaView(LoginRequiredMixin, View):
    """GET: página de votación. POST: valida la opción elegida y muestra la confirmación."""

    def get(self, request, pk):
        return pagina_de_votacion(request, _categoria_publicada(pk))

    def post(self, request, pk):
        categoria = _categoria_publicada(pk)
        if voto_en_categoria(request.user, categoria):
            messages.error(request, "Ya votaste en esta categoría.")
            return pagina_de_votacion(request, categoria, status=403)
        try:
            verificar_categoria(categoria)
        except VotoRechazado as rechazo:
            messages.error(request, rechazo.mensaje)
            return pagina_de_votacion(request, categoria, status=rechazo.estado_http)
        form = ElegirOpcionForm(request.POST, categoria=categoria)
        if not form.is_valid():
            messages.error(request, form.errors["opcion"][0])
            return pagina_de_votacion(request, categoria, form=form, status=400)
        return render(request, "votos/confirmar.html", {"categoria": categoria, "opcion": form.cleaned_data["opcion"]})


class ConfirmarVotoView(LoginRequiredMixin, View):
    """Solo POST (GET responde 405): registra el voto y redirige al comprobante (patrón POST/redirección/GET)."""

    http_method_names = ["post"]

    def handle_no_permission(self):
        # Sin sesión, después de iniciarla se vuelve a la página de la categoría, no a esta URL de solo POST.
        return redirect_to_login(reverse("votos:votar", args=[self.kwargs["pk"]]), self.get_login_url(),
                                 self.get_redirect_field_name())

    def post(self, request, pk):
        try:
            voto = registrar_voto(request.user, pk, request.POST.get("opcion"),
                                  ip=request.META.get("REMOTE_ADDR", ""),
                                  navegador=request.META.get("HTTP_USER_AGENT", ""))
        except VotoRechazado as rechazo:
            messages.error(request, rechazo.mensaje)
            categoria = Categoria.objects.select_related("edicion").filter(pk=pk, publicada=True).first()
            if categoria is None:
                raise Http404(rechazo.mensaje) from None
            return pagina_de_votacion(request, categoria, status=rechazo.estado_http)
        messages.success(request, "Tu voto quedó registrado.")
        return redirect("votos:comprobante", pk=voto.pk)


class ComprobanteView(LoginRequiredMixin, DetailView):
    """Comprobante de un voto. Solo lo ve quien votó: el voto de otra persona responde 404."""

    template_name = "votos/comprobante.html"
    context_object_name = "voto"

    def get_queryset(self):
        return Voto.objects.filter(usuario=self.request.user).select_related("opcion", "votacion", "categoria", "edicion")


class MisVotosView(LoginRequiredMixin, ListView):
    """«Mis votos» (CP-07): solo los votos de quien inició sesión, nunca los de otras personas."""

    template_name = "votos/mis_votos.html"
    context_object_name = "votos"

    def get_queryset(self):
        return (Voto.objects.filter(usuario=self.request.user)
                .select_related("opcion", "votacion", "categoria", "edicion")
                .order_by("-edicion__anio", "categoria__orden", "categoria__nombre"))

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        # Participación: categorías abiertas de la edición activa en las que todavía no ha votado
        edicion = edicion_activa()
        pendientes = []
        if edicion:
            votadas = {voto.categoria_id for voto in contexto["votos"]}
            for categoria in edicion.categorias.filter(publicada=True).exclude(pk__in=votadas).select_related("edicion"):
                if se_puede_votar(categoria):
                    pendientes.append(categoria)
        contexto["pendientes"] = pendientes
        return contexto
