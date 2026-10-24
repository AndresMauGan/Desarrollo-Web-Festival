"""
Gestión de votaciones (Entrega 1): Edición, Categoría, Votación y Opción.

Cardinalidades del modelo conceptual corregido (ver CLAUDE.md, «Modelo de datos»):
- Edición contiene Categoría:  1 a 0..*  → Categoria.edicion
- Categoría agrupa Votación:   1 a 0..*  → Votacion.categoria
- Votación posee Opción:       1 a 0..*  → Opcion.votacion

El lado «exactamente uno» es una ForeignKey obligatoria con PROTECT: nada se borra en cascada (RN-10).
"""

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from . import reglas


class Edicion(models.Model):
    numero = models.PositiveSmallIntegerField("número")
    anio = models.PositiveSmallIntegerField("año", unique=True)
    nombre = models.CharField("nombre", max_length=120)
    fecha_inicio = models.DateField("fecha de inicio")
    fecha_fin = models.DateField("fecha de fin")
    homenaje = models.CharField("homenaje", max_length=150, blank=True)
    activa = models.BooleanField("activa", default=False)

    class Meta:
        verbose_name = "edición"
        verbose_name_plural = "ediciones"
        ordering = ["-anio"]

    def __str__(self):
        return f"{self.nombre} ({self.anio})"

    def clean(self):
        if self.fecha_inicio and self.fecha_fin and self.fecha_fin < self.fecha_inicio:
            raise ValidationError({"fecha_fin": "La fecha de fin no puede ser anterior a la de inicio."})


class Categoria(models.Model):
    class Familia(models.TextChoices):
        ACORDEON = "acordeon", "Acordeón"
        CANCION = "cancion", "Canción"
        PIQUERIA = "piqueria", "Piquería"
        PILONERA = "pilonera", "Pilonera"
        OTRA = "otra", "Otra"

    edicion = models.ForeignKey(Edicion, on_delete=models.PROTECT, related_name="categorias", verbose_name="edición")
    nombre = models.CharField("nombre", max_length=100)
    familia = models.CharField("familia", max_length=20, choices=Familia.choices)
    nivel = models.CharField("nivel", max_length=40, blank=True, help_text="Ej.: Profesional, Mayor, Aficionado, Juvenil o Infantil.")
    es_rey_de_reyes = models.BooleanField("es Rey de Reyes", default=False)
    admite_voto_publico = models.BooleanField("admite voto del público", default=False)
    publicada = models.BooleanField("publicada", default=False)
    orden = models.PositiveSmallIntegerField("orden", default=0)

    class Meta:
        verbose_name = "categoría"
        verbose_name_plural = "categorías"
        ordering = ["edicion", "orden", "nombre"]
        constraints = [
            models.UniqueConstraint(fields=["edicion", "nombre"], name="categoria_nombre_unico_por_edicion"),
        ]

    def __str__(self):
        return f"{self.nombre} · {self.edicion.anio}"


class Votacion(models.Model):
    class Ronda(models.TextChoices):
        ELIMINATORIA = "eliminatoria", "Eliminatoria"
        SEMIFINAL = "semifinal", "Semifinal"
        FINAL = "final", "Final"
        DESEMPATE = "desempate", "Desempate"

    class Estado(models.TextChoices):
        BORRADOR = "borrador", "Borrador"
        PROGRAMADA = "programada", "Programada"
        ABIERTA = "abierta", "Abierta"
        PAUSADA = "pausada", "Pausada"
        CERRADA = "cerrada", "Cerrada"

    class Visibilidad(models.TextChoices):
        EN_VIVO = "en_vivo", "En vivo"
        AL_CIERRE = "al_cierre", "Al cierre"
        EN_CEREMONIA = "en_ceremonia", "En la ceremonia"

    categoria = models.ForeignKey(Categoria, on_delete=models.PROTECT, related_name="votaciones", verbose_name="categoría")
    nombre = models.CharField("nombre", max_length=150)
    ronda = models.CharField("ronda", max_length=20, choices=Ronda.choices)
    estado = models.CharField("estado", max_length=20, choices=Estado.choices, default=Estado.BORRADOR)
    abre_en = models.DateTimeField("abre en")
    cierra_en = models.DateTimeField("cierra en")
    # RN-06, pendiente (P-05): el valor por defecto viene de reglas.py y no es una decisión de la Fundación.
    visibilidad_resultados = models.CharField(
        "visibilidad de resultados",
        max_length=20,
        choices=Visibilidad.choices,
        default=reglas.VISIBILIDAD_RESULTADOS_POR_DEFECTO,
        help_text="Pendiente de validación (P-05). Por defecto, al cierre.",
    )
    # RN-01, pendiente (P-03). Por eso no hay restricción única (usuario, votación) en Voto.
    limite_votos_por_usuario = models.PositiveSmallIntegerField(
        "límite de votos por usuario",
        default=reglas.LIMITE_VOTOS_POR_DEFECTO,
        validators=[MinValueValidator(1)],
        help_text="Pendiente de validación (P-03). Por defecto, 1.",
    )

    class Meta:
        verbose_name = "votación"
        verbose_name_plural = "votaciones"
        ordering = ["abre_en", "nombre"]

    def __str__(self):
        return f"{self.nombre} ({self.get_estado_display()})"

    def opciones_publicadas(self):
        """Opciones que ve el público y que cuentan para RN-11: publicadas y activas."""
        return self.opciones.filter(publicada=True, estado=Opcion.Estado.ACTIVA)

    def pasa_a_abierta(self):
        """True si este guardado lleva la votación a «abierta» (es nueva o venía de otro estado)."""
        if self.estado != self.Estado.ABIERTA:
            return False
        anterior = Votacion.objects.filter(pk=self.pk).values_list("estado", flat=True).first() if self.pk else None
        return anterior != self.Estado.ABIERTA

    def validar_minimo_opciones(self, cantidad_publicadas):
        """RN-11: una votación no pasa a «abierta» con menos de dos opciones publicadas."""
        if cantidad_publicadas < reglas.MINIMO_OPCIONES_PARA_ABRIR:
            raise ValidationError(
                {"estado": f"No se puede abrir: necesita al menos {reglas.MINIMO_OPCIONES_PARA_ABRIR} opciones "
                           f"publicadas y activas (RN-11); tiene {cantidad_publicadas}."}
            )

    def clean(self):
        if self.abre_en and self.cierra_en and self.cierra_en <= self.abre_en:
            raise ValidationError({"cierra_en": "El cierre debe ser posterior a la apertura."})
        # En Django Admin, RN-11 la valida el formulario de opciones en línea, que sí ve las opciones
        # que se están guardando junto con la votación (ver festival/admin.py).
        if self.pasa_a_abierta() and not getattr(self, "_rn11_en_formulario", False):
            self.validar_minimo_opciones(self.opciones_publicadas().count() if self.pk else 0)


class Opcion(models.Model):
    class Tipo(models.TextChoices):
        PERSONA = "persona", "Persona"
        CONJUNTO = "conjunto", "Conjunto"
        OBRA = "obra", "Obra"
        GRUPO = "grupo", "Grupo"

    class Estado(models.TextChoices):
        ACTIVA = "activa", "Activa"
        RETIRADA = "retirada", "Retirada"

    votacion = models.ForeignKey(Votacion, on_delete=models.PROTECT, related_name="opciones", verbose_name="votación")
    nombre = models.CharField("nombre", max_length=150)
    tipo = models.CharField("tipo", max_length=20, choices=Tipo.choices)
    integrantes = models.TextField("integrantes", blank=True, help_text="Para conjuntos y grupos.")
    descripcion = models.TextField("descripción", blank=True)
    foto = models.ImageField("foto", upload_to="opciones/", blank=True)
    orden = models.PositiveSmallIntegerField("orden en tarima", default=0)
    publicada = models.BooleanField("publicada", default=False)
    # RN-10: una opción con votos no se elimina; se retira.
    estado = models.CharField("estado", max_length=20, choices=Estado.choices, default=Estado.ACTIVA)

    class Meta:
        verbose_name = "opción"
        verbose_name_plural = "opciones"
        ordering = ["votacion", "orden", "nombre"]

    def __str__(self):
        return self.nombre
