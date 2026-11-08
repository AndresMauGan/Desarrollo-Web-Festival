"""
Usuarios y votos · Control y auditoría (Entrega 1). El voto se registra con votos.servicios.registrar_voto.

Cardinalidades del modelo conceptual corregido (ver CLAUDE.md, «Modelo de datos»):
- Votación recibe Voto:                 1 a 0..*     → Voto.votacion
- Opción acumula Voto:                  1 a 0..*     → Voto.opcion
- Usuario emite Voto:                   1 a 0..*     → Voto.usuario
- Categoría recibe Voto (Entrega 3):    1 a 0..*     → Voto.categoria
- Edición recibe Voto (Entrega 3):      1 a 0..*     → Voto.edicion
- Usuario genera Registro de auditoría: 0..1 a 0..*  → RegistroAuditoria.usuario (null = sistema)

RN-01 (definida por la guía de la Entrega 3): un voto por usuario, categoría y edición. Lo garantiza
la restricción única «un_voto_por_usuario_categoria_edicion» en MySQL, también ante solicitudes simultáneas.
Categoría y edición se guardan en el voto (aunque se deducen de la opción) para que MySQL pueda aplicar
esa restricción: una restricción única no puede recorrer relaciones.
"""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class VotoInmutableError(Exception):
    """RN-02: un voto emitido no se modifica ni se borra."""


class VotoQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise VotoInmutableError("Los votos son inmutables (RN-02): no se pueden modificar.")

    def delete(self):
        raise VotoInmutableError("Los votos son inmutables (RN-02): no se pueden borrar.")


class Voto(models.Model):
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="votos", verbose_name="usuario")
    edicion = models.ForeignKey("festival.Edicion", on_delete=models.PROTECT, related_name="votos", verbose_name="edición")
    categoria = models.ForeignKey("festival.Categoria", on_delete=models.PROTECT, related_name="votos", verbose_name="categoría")
    votacion = models.ForeignKey("festival.Votacion", on_delete=models.PROTECT, related_name="votos", verbose_name="votación")
    opcion = models.ForeignKey("festival.Opcion", on_delete=models.PROTECT, related_name="votos", verbose_name="opción")
    fecha_hora = models.DateTimeField("fecha y hora", auto_now_add=True)
    huella_ip = models.CharField("huella de IP", max_length=64, help_text="HMAC-SHA256 de la IP; la IP no se guarda en claro.")
    huella_navegador = models.CharField("huella del navegador", max_length=64, help_text="HMAC-SHA256 del navegador (User-Agent).")
    hash_auditoria = models.CharField("hash de auditoría", max_length=64)

    objects = VotoQuerySet.as_manager()

    class Meta:
        verbose_name = "voto"
        verbose_name_plural = "votos"
        ordering = ["-fecha_hora"]
        constraints = [
            # RN-01: una sola opción por usuario, categoría y edición, aunque la categoría tenga varias votaciones.
            models.UniqueConstraint(fields=["usuario", "categoria", "edicion"], name="un_voto_por_usuario_categoria_edicion"),
        ]

    def __str__(self):
        return f"Voto #{self.pk} en «{self.votacion.nombre}»"

    @classmethod
    def desde_opcion(cls, usuario, opcion, **campos):
        """Arma un voto tomando votación, categoría y edición de la opción; nunca del formulario."""
        votacion = opcion.votacion
        categoria = votacion.categoria
        return cls(usuario=usuario, opcion=opcion, votacion=votacion, categoria=categoria, edicion=categoria.edicion, **campos)

    @property
    def codigo_comprobante(self):
        """Código corto del comprobante, tomado del hash de auditoría (por ejemplo, VV-3F2A-9C1B)."""
        h = (self.hash_auditoria or "").upper()
        return f"VV-{h[:4]}-{h[4:8]}" if h else ""

    def clean(self):
        # Integridad entre relaciones: opción → votación → categoría → edición.
        errores = {}
        if self.opcion_id and self.votacion_id and self.opcion.votacion_id != self.votacion_id:
            errores["opcion"] = "La opción no pertenece a esta votación."
        if self.votacion_id and self.categoria_id and self.votacion.categoria_id != self.categoria_id:
            errores["votacion"] = "La votación no pertenece a esta categoría."
        if self.categoria_id and self.edicion_id and self.categoria.edicion_id != self.edicion_id:
            errores["categoria"] = "La categoría no pertenece a esta edición."
        if errores:
            raise ValidationError(errores)

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise VotoInmutableError("Los votos son inmutables (RN-02): no se pueden modificar.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise VotoInmutableError("Los votos son inmutables (RN-02): no se pueden borrar.")


class RegistroAuditoria(models.Model):
    fecha_hora = models.DateTimeField("fecha y hora", auto_now_add=True)
    # «Actor» del diagrama: vacío cuando el registro lo genera el sistema (por ejemplo, una alerta).
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="registros",
        verbose_name="usuario",
        help_text="Vacío si el registro lo generó el sistema.",
    )
    accion = models.CharField("acción", max_length=100)
    entidad_afectada = models.CharField("entidad afectada", max_length=100)
    detalle = models.TextField("detalle", blank=True)
    huella_ip = models.CharField("huella de IP", max_length=64, blank=True)

    class Meta:
        verbose_name = "registro de auditoría"
        verbose_name_plural = "registros de auditoría"
        ordering = ["-fecha_hora"]

    def __str__(self):
        actor = self.usuario or "Sistema"
        return f"{actor} · {self.accion} · {self.entidad_afectada}"
