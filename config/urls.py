"""Rutas principales del proyecto."""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path

admin.site.site_header = "Festival de la Leyenda Vallenata · Administración"
admin.site.site_title = "Administración del Festival"
admin.site.index_title = "Gestión de ediciones, categorías, votaciones y opciones"

urlpatterns = [
    path("admin/", admin.site.urls),
    # Integrante 3 agrega aquí las rutas de cuentas (registro, inicio y cierre de sesión)
    # e Integrante 4 las rutas públicas de festival, con include().
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
