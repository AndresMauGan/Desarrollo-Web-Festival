from django import forms
from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.db.models import Count
from django.forms.models import BaseInlineFormSet

from votos.servicios import auditar

from .models import Categoria, Edicion, Opcion, Votacion


def ip_de(request):
    return request.META.get("REMOTE_ADDR", "")


class ConteoDeVotosMixin:
    """Columna de solo lectura con el número de votos, calculada con Count en la misma consulta de la lista."""

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(num_votos=Count("votos", distinct=True))

    @admin.display(description="votos", ordering="num_votos")
    def conteo_votos(self, objeto):
        return objeto.num_votos


# Las líneas no permiten borrar (can_delete = False): una categoría u opción con votos no se elimina,
# se despublica o se retira (RN-10). Borrar algo sin votos se hace desde su propia página del admin,
# que muestra qué lo impide cuando PROTECT lo protege.


class CategoriaInline(admin.TabularInline):
    model = Categoria
    fields = ("nombre", "familia", "nivel", "admite_voto_publico", "publicada", "orden")
    extra = 0
    can_delete = False
    show_change_link = True


@admin.register(Edicion)
class EdicionAdmin(admin.ModelAdmin):
    list_display = ("anio", "numero", "nombre", "fecha_inicio", "fecha_fin", "activa")
    list_filter = ("activa",)
    search_fields = ("nombre", "homenaje")
    ordering = ("-anio",)
    inlines = [CategoriaInline]


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "edicion", "familia", "nivel", "admite_voto_publico", "publicada", "orden")
    list_filter = ("edicion", "familia", "publicada", "admite_voto_publico", "es_rey_de_reyes")
    search_fields = ("nombre", "nivel")
    ordering = ("-edicion__anio", "orden", "nombre")


class OpcionInlineFormSet(BaseInlineFormSet):
    """RN-11 con los datos del formulario: cuenta las opciones tal como quedarán al guardar."""

    def clean(self):
        super().clean()
        votacion = self.instance
        if not votacion.pasa_a_abierta():
            return
        publicadas = sum(
            1 for f in self.forms
            if f.cleaned_data
            and f.cleaned_data.get("publicada")
            and f.cleaned_data.get("estado", Opcion.Estado.ACTIVA) == Opcion.Estado.ACTIVA
        )
        try:
            votacion.validar_minimo_opciones(publicadas)
        except ValidationError as error:
            raise ValidationError(error.message_dict["estado"])


class OpcionInline(admin.TabularInline):
    model = Opcion
    formset = OpcionInlineFormSet
    fields = ("nombre", "tipo", "orden", "publicada", "estado")
    extra = 0
    can_delete = False
    show_change_link = True


class VotacionAdminForm(forms.ModelForm):
    class Meta:
        model = Votacion
        fields = "__all__"

    def clean(self):
        # RN-11 la valida OpcionInlineFormSet, que ve las opciones que se guardan junto con la votación.
        self.instance._rn11_en_formulario = True
        return super().clean()


@admin.register(Votacion)
class VotacionAdmin(ConteoDeVotosMixin, admin.ModelAdmin):
    form = VotacionAdminForm
    list_display = ("nombre", "categoria", "ronda", "estado", "abre_en", "cierra_en", "visibilidad_resultados",
                    "resultados_publicados", "conteo_votos")
    # Filtro por fecha en lugar de date_hierarchy: este usa CONVERT_TZ y falla en MySQL sin las tablas de zonas horarias.
    list_filter = ("estado", "ronda", "visibilidad_resultados", "categoria__edicion", "categoria", "abre_en")
    search_fields = ("nombre", "categoria__nombre")
    ordering = ("abre_en", "nombre")
    inlines = [OpcionInline]
    actions = ["publicar_resultados", "retirar_publicacion"]
    fieldsets = (
        (None, {"fields": ("categoria", "nombre", "ronda", "estado")}),
        ("Horario", {"fields": ("abre_en", "cierra_en")}),
        ("Reglas pendientes de la Fundación (provisionales)", {"fields": ("visibilidad_resultados", "resultados_publicados")}),
    )

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if change and "resultados_publicados" in form.changed_data:
            accion = "Resultados publicados" if obj.resultados_publicados else "Publicación de resultados retirada"
            auditar(request.user, accion, f"festival.Votacion #{obj.pk}", obj.nombre, ip_de(request))

    # RN-06, pendiente (P-05): publicar solo cambia algo con visibilidad «En la ceremonia».
    # No se exige que la votación esté cerrada; solo se avisa.
    @admin.action(description="Publicar resultados (visibilidad «En la ceremonia»)", permissions=["change"])
    def publicar_resultados(self, request, queryset):
        self._cambiar_publicacion(request, queryset, publicar=True)

    @admin.action(description="Retirar la publicación de resultados", permissions=["change"])
    def retirar_publicacion(self, request, queryset):
        self._cambiar_publicacion(request, queryset, publicar=False)

    def _cambiar_publicacion(self, request, queryset, publicar):
        cambiadas = []
        for votacion in queryset:
            if votacion.resultados_publicados == publicar:
                continue
            votacion.resultados_publicados = publicar
            votacion.save(update_fields=["resultados_publicados"])
            accion = "Resultados publicados" if publicar else "Publicación de resultados retirada"
            auditar(request.user, accion, f"festival.Votacion #{votacion.pk}", votacion.nombre, ip_de(request))
            cambiadas.append(votacion)
            if publicar and votacion.visibilidad_resultados != Votacion.Visibilidad.EN_CEREMONIA:
                self.message_user(request, f"«{votacion.nombre}» tiene visibilidad «{votacion.get_visibilidad_resultados_display()}»: "
                                           "marcarla como publicada no cambia lo que ve el público.", messages.WARNING)
            elif publicar and votacion.estado != Votacion.Estado.CERRADA:
                self.message_user(request, f"Atención: «{votacion.nombre}» todavía no está cerrada y sus resultados ya son públicos.",
                                  messages.WARNING)
        if cambiadas:
            verbo = "publicaron" if publicar else "retiraron"
            self.message_user(request, f"Se {verbo} los resultados de {len(cambiadas)} votación(es): "
                                       + ", ".join(f"«{v.nombre}»" for v in cambiadas) + ".", messages.SUCCESS)
        else:
            self.message_user(request, "No hubo cambios: las votaciones elegidas ya estaban así.", messages.INFO)


@admin.register(Opcion)
class OpcionAdmin(ConteoDeVotosMixin, admin.ModelAdmin):
    list_display = ("nombre", "votacion", "tipo", "orden", "publicada", "estado", "conteo_votos")
    list_filter = ("estado", "publicada", "tipo", "votacion__categoria__edicion", "votacion")
    search_fields = ("nombre", "integrantes", "descripcion")
    ordering = ("votacion", "orden", "nombre")
