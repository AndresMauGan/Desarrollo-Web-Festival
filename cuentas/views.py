"""CU-01 · Registro, inicio y cierre de sesión con el sistema de autenticación de Django."""

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import redirect, resolve_url
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.generic import CreateView, TemplateView

from .forms import IngresoForm, RegistroForm


class RegistroView(CreateView):
    form_class = RegistroForm
    template_name = "registration/registro.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect(settings.LOGIN_REDIRECT_URL)
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        usuario = form.save()
        # PENDIENTE (RN-04, P-01): mientras la verificación del correo no esté definida, la cuenta
        # nueva inicia sesión de una vez.
        login(self.request, usuario, backend="django.contrib.auth.backends.ModelBackend")
        messages.success(self.request, f"Listo, {usuario.nombre_para_mostrar}: tu cuenta quedó creada.")
        siguiente = self.request.POST.get("next") or self.request.GET.get("next")
        if siguiente and url_has_allowed_host_and_scheme(siguiente, allowed_hosts={self.request.get_host()}, require_https=self.request.is_secure()):
            return redirect(siguiente)
        return redirect(resolve_url(settings.LOGIN_REDIRECT_URL))


class IngresoView(LoginView):
    form_class = IngresoForm
    template_name = "registration/login.html"
    redirect_authenticated_user = True

    def form_valid(self, form):
        respuesta = super().form_valid(form)
        messages.success(self.request, "Sesión iniciada.")
        return respuesta


class SalidaView(LogoutView):
    """Cierre de sesión solo por POST (LogoutView no acepta GET desde Django 5)."""

    def post(self, request, *args, **kwargs):
        respuesta = super().post(request, *args, **kwargs)
        messages.info(request, "Sesión cerrada.")
        return respuesta


class CuentaView(LoginRequiredMixin, TemplateView):
    template_name = "registration/cuenta.html"
