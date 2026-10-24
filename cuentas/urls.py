from django.urls import path

from . import views

app_name = "cuentas"

urlpatterns = [
    path("", views.CuentaView.as_view(), name="cuenta"),
    path("registro/", views.RegistroView.as_view(), name="registro"),
    path("ingresar/", views.IngresoView.as_view(), name="login"),
    path("salir/", views.SalidaView.as_view(), name="logout"),
]
