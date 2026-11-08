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
    """Votos tal como están en votos_voto (CP-08). Filtro de fecha normal: date_hierarchy necesita
    las tablas de zonas horarias de MySQL."""

    list_display = ("usuario", "edicion", "categoria", "votacion", "opcion", "fecha_hora")
    list_filter = ("edicion", "categoria", "fecha_hora")
    search_fields = ("usuario__email",)
    search_help_text = "Busca por el correo de quien votó."
    ordering = ("-fecha_hora",)
    list_select_related = ("usuario", "edicion", "categoria", "votacion", "opcion")
    fields = ("usuario", "edicion", "categoria", "votacion", "opcion", "fecha_hora", "codigo_comprobante",
              "hash_auditoria", "huella_ip", "huella_navegador")
    readonly_fields = ("fecha_hora", "codigo_comprobante")

    @admin.display(description="código de comprobante")
    def codigo_comprobante(self, voto):
        return voto.codigo_comprobante


@admin.register(RegistroAuditoria)
class RegistroAuditoriaAdmin(SoloLecturaAdmin):
    list_display = ("fecha_hora", "usuario", "accion", "entidad_afectada")
    list_filter = ("accion",)
    search_fields = ("usuario__email", "accion", "entidad_afectada", "detalle")
    ordering = ("-fecha_hora",)
