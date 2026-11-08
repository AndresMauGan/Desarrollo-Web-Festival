from django.urls import path

from . import views

app_name = "votos"

urlpatterns = [
    path("categoria/<int:pk>/", views.VotarCategoriaView.as_view(), name="votar"),
    path("categoria/<int:pk>/confirmar/", views.ConfirmarVotoView.as_view(), name="confirmar"),
    path("comprobante/<int:pk>/", views.ComprobanteView.as_view(), name="comprobante"),
    path("mis-votos/", views.MisVotosView.as_view(), name="mis_votos"),
]
