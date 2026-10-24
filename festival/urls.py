from django.urls import path

from . import views

app_name = "festival"

urlpatterns = [
    path("", views.InicioView.as_view(), name="inicio"),
    path("ediciones/", views.EdicionListView.as_view(), name="ediciones"),
    path("ediciones/<int:anio>/", views.EdicionDetailView.as_view(), name="edicion"),
    path("ediciones/<int:anio>/categorias/", views.CategoriasEdicionView.as_view(), name="categorias"),
    path("categorias/", views.categorias_actuales, name="categorias_actuales"),
    path("categorias/<int:pk>/", views.CategoriaDetailView.as_view(), name="categoria"),
    path("votaciones/<int:pk>/", views.VotacionDetailView.as_view(), name="votacion"),
]
