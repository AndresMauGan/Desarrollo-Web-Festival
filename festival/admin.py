from django import forms
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.forms.models import BaseInlineFormSet

from .models import Categoria, Edicion, Opcion, Votacion

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
class VotacionAdmin(admin.ModelAdmin):
    form = VotacionAdminForm
    list_display = ("nombre", "categoria", "ronda", "estado", "abre_en", "cierra_en", "limite_votos_por_usuario", "visibilidad_resultados")
    list_filter = ("estado", "ronda", "visibilidad_resultados", "categoria__edicion", "categoria")
    search_fields = ("nombre", "categoria__nombre")
    ordering = ("abre_en", "nombre")
    date_hierarchy = "abre_en"
    inlines = [OpcionInline]
    fieldsets = (
        (None, {"fields": ("categoria", "nombre", "ronda", "estado")}),
        ("Horario", {"fields": ("abre_en", "cierra_en")}),
        ("Reglas pendientes de la Fundación (provisionales)", {"fields": ("limite_votos_por_usuario", "visibilidad_resultados")}),
    )


@admin.register(Opcion)
class OpcionAdmin(admin.ModelAdmin):
    list_display = ("nombre", "votacion", "tipo", "orden", "publicada", "estado")
    list_filter = ("estado", "publicada", "tipo", "votacion__categoria__edicion", "votacion")
    search_fields = ("nombre", "integrantes", "descripcion")
    ordering = ("votacion", "orden", "nombre")
