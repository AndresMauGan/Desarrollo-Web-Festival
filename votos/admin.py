from django.contrib import admin

from .models import RegistroAuditoria, Voto


class SoloLecturaAdmin(admin.ModelAdmin):
    """Solo consulta: sin agregar, editar ni borrar (Voto es inmutable, RN-02; la auditoría no se altera)."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Voto)
class VotoAdmin(SoloLecturaAdmin):
    list_display = ("fecha_hora", "usuario", "votacion", "opcion")
    list_filter = ("votacion__categoria__edicion", "votacion")
    search_fields = ("usuario__email", "hash_auditoria")
    ordering = ("-fecha_hora",)


@admin.register(RegistroAuditoria)
class RegistroAuditoriaAdmin(SoloLecturaAdmin):
    list_display = ("fecha_hora", "usuario", "accion", "entidad_afectada")
    list_filter = ("accion",)
    search_fields = ("usuario__email", "accion", "entidad_afectada", "detalle")
    ordering = ("-fecha_hora",)
