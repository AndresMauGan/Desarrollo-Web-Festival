"""Rutas principales del proyecto."""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "Festival de la Leyenda Vallenata · Administración"
admin.site.site_title = "Administración del Festival"
admin.site.index_title = "Gestión de ediciones, categorías, votaciones y opciones"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("cuentas/", include("cuentas.urls")),
    path("", include("festival.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
