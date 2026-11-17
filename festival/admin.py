from django import forms
from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.db.models import Count
from django.forms.models import BaseInlineFormSet
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils import timezone

from votos.servicios import auditar

from .models import Categoria, Edicion, Opcion, Votacion
from .servicios import duplicar_edicion, valores_para_la_siguiente
from .templatetags.festival_extras import fecha_hora_co

Estado = Votacion.Estado

# Acciones de estado de Votación en el admin: (estados desde los que se puede, estado nuevo, registro de auditoría)
TRANSICIONES = {
    "abrir": ((Estado.BORRADOR, Estado.PROGRAMADA, Estado.PAUSADA), Estado.ABIERTA, "Votación abierta"),
    "pausar": ((Estado.ABIERTA,), Estado.PAUSADA, "Votación pausada"),
    "cerrar": ((Estado.PROGRAMADA, Estado.ABIERTA, Estado.PAUSADA), Estado.CERRADA, "Votación cerrada"),
}


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


class EdicionAdminForm(forms.ModelForm):
    class Meta:
        model = Edicion
        fields = "__all__"
        help_texts = {
            "activa": "Solo puede haber una edición activa: al marcar esta, las demás se desactivan. "
                      "El sitio, la votación y la API muestran la edición activa.",
        }


class DuplicarEdicionForm(forms.Form):
    """Datos de la edición nueva en la acción «Duplicar» (formulario intermedio)."""

    anio = forms.IntegerField(label="Año", min_value=1900, max_value=2999)
    numero = forms.IntegerField(label="Número", min_value=1)
    nombre = forms.CharField(label="Nombre", max_length=120)
    fecha_inicio = forms.DateField(label="Fecha de inicio", widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"))
    fecha_fin = forms.DateField(label="Fecha de fin", widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"))
    homenaje = forms.CharField(label="Homenaje", max_length=150, required=False)

    def clean_anio(self):
        anio = self.cleaned_data["anio"]
        if Edicion.objects.filter(anio=anio).exists():
            raise ValidationError(f"Ya existe una edición del año {anio}.")
        return anio

    def clean(self):
        datos = super().clean()
        if datos.get("fecha_inicio") and datos.get("fecha_fin") and datos["fecha_fin"] < datos["fecha_inicio"]:
            self.add_error("fecha_fin", "La fecha de fin no puede ser anterior a la de inicio.")
        return datos


@admin.register(Edicion)
class EdicionAdmin(admin.ModelAdmin):
    form = EdicionAdminForm
    list_display = ("anio", "numero", "nombre", "fecha_inicio", "fecha_fin", "activa")
    list_filter = ("activa",)
    search_fields = ("nombre", "homenaje")
    ordering = ("-anio",)
    inlines = [CategoriaInline]
    actions = ["duplicar"]

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if obj.ediciones_desactivadas:
            otras = ", ".join(f"«{edicion}»" for edicion in obj.ediciones_desactivadas)
            self.message_user(request, f"«{obj}» es ahora la edición activa y se desactivó {otras}. Solo puede haber una "
                                       "edición activa: el sitio, la votación y la API usan esa.", messages.INFO)
            auditar(request.user, "Edición activada", f"festival.Edicion #{obj.pk}", f"Se desactivó {otras}.", ip_de(request))

    @admin.action(description="Duplicar la edición (categorías y votaciones en borrador)", permissions=["add"])
    def duplicar(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(request, "Elige exactamente una edición para duplicar.", messages.ERROR)
            return None
        origen = queryset.get()
        if "aplicar" in request.POST:
            form = DuplicarEdicionForm(request.POST)
            if form.is_valid():
                nueva, categorias, votaciones = duplicar_edicion(origen, **form.cleaned_data)
                auditar(request.user, "Edición duplicada", f"festival.Edicion #{nueva.pk}",
                        f"Copia de «{origen}»: {categorias} categorías y {votaciones} votaciones en borrador.", ip_de(request))
                self.message_user(request, f"Se creó «{nueva}», inactiva, con {categorias} categorías sin publicar y "
                                           f"{votaciones} votaciones en borrador. Agrega las opciones, publica las categorías, "
                                           "abre las votaciones y márcala como activa cuando esté lista.", messages.SUCCESS)
                return HttpResponseRedirect(reverse("admin:festival_edicion_change", args=[nueva.pk]))
        else:
            form = DuplicarEdicionForm(initial=valores_para_la_siguiente(origen))
        contexto = {
            **self.admin_site.each_context(request),
            "title": f"Duplicar «{origen}»",
            "opts": self.model._meta,
            "origen": origen,
            "form": form,
            "total_categorias": origen.categorias.count(),
            "total_votaciones": Votacion.objects.filter(categoria__edicion=origen).count(),
        }
        return TemplateResponse(request, "admin/festival/edicion/duplicar.html", contexto)


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
    actions = ["abrir", "pausar", "cerrar", "publicar_resultados", "retirar_publicacion"]
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

    @admin.action(description="Abrir las votaciones elegidas", permissions=["change"])
    def abrir(self, request, queryset):
        self._cambiar_estado(request, queryset, "abrir")

    @admin.action(description="Pausar las votaciones elegidas", permissions=["change"])
    def pausar(self, request, queryset):
        self._cambiar_estado(request, queryset, "pausar")

    @admin.action(description="Cerrar las votaciones elegidas", permissions=["change"])
    def cerrar(self, request, queryset):
        self._cambiar_estado(request, queryset, "cerrar")

    def _cambiar_estado(self, request, queryset, accion):
        """Cambia el estado según TRANSICIONES. Abrir respeta RN-11. Cada cambio queda en RegistroAuditoria."""
        desde, hacia, registro = TRANSICIONES[accion]
        ahora = timezone.now()
        cambiadas = []
        for votacion in queryset.select_related("categoria"):
            if votacion.estado == hacia:
                self.message_user(request, f"«{votacion.nombre}» ya estaba {votacion.get_estado_display().lower()}.", messages.INFO)
                continue
            if votacion.estado not in desde:
                self.message_user(request, f"«{votacion.nombre}» no se puede {accion} porque está "
                                           f"{votacion.get_estado_display().lower()}.", messages.ERROR)
                continue
            if hacia == Estado.ABIERTA:
                try:
                    votacion.validar_minimo_opciones(votacion.opciones_publicadas().count())  # RN-11
                except ValidationError as error:
                    self.message_user(request, f"«{votacion.nombre}»: {error.message_dict['estado'][0]}", messages.ERROR)
                    continue
            anterior = votacion.get_estado_display().lower()
            votacion.estado = hacia
            votacion.save(update_fields=["estado"])
            auditar(request.user, registro, f"festival.Votacion #{votacion.pk}",
                    f"«{votacion.nombre}»: de {anterior} a {votacion.get_estado_display().lower()}.", ip_de(request))
            cambiadas.append(votacion)
            if hacia == Estado.ABIERTA and not votacion.abre_en <= ahora < votacion.cierra_en:
                cuando = "todavía no empieza" if ahora < votacion.abre_en else "ya terminó"
                self.message_user(request, f"«{votacion.nombre}» quedó abierta, pero su horario {cuando} "
                                           f"({fecha_hora_co(votacion.abre_en)} a {fecha_hora_co(votacion.cierra_en)}): "
                                           "el servidor solo recibe votos dentro del horario (RN-03).", messages.WARNING)
        if cambiadas:
            self.message_user(request, f"Quedaron {hacia.label.lower()}s: " + ", ".join(f"«{v.nombre}»" for v in cambiadas) + ".",
                              messages.SUCCESS)

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
