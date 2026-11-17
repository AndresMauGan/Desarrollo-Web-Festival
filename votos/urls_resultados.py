"""Rutas de resultados (CU-05): la página del personal y los resultados públicos de cada votación."""

from django.urls import path

from . import views

app_name = "resultados"

urlpatterns = [
    path("resultados/", views.ResultadosView.as_view(), name="panel"),
    path("votaciones/<int:pk>/resultados/", views.ResultadosVotacionView.as_view(), name="votacion"),
]
