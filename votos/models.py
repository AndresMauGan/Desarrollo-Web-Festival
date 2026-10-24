"""
Usuarios y votos · Control y auditoría (Entrega 1). Solo estructura en esta entrega:
migración y admin de solo lectura, sin flujo de voto.

Cardinalidades del modelo conceptual corregido (ver CLAUDE.md, «Modelo de datos»):
- Votación recibe Voto:                 1 a 0..*     → Voto.votacion
- Opción acumula Voto:                  1 a 0..*     → Voto.opcion
- Usuario emite Voto:                   1 a 0..*     → Voto.usuario
- Usuario genera Registro de auditoría: 0..1 a 0..*  → RegistroAuditoria.usuario (null = sistema)

No es cardinalidad sino regla: «votos por usuario en una votación ≤ límite» es RN-01, pendiente (P-03).
Por eso no hay restricción única (usuario, votación).
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
    votacion = models.ForeignKey("festival.Votacion", on_delete=models.PROTECT, related_name="votos", verbose_name="votación")
    opcion = models.ForeignKey("festival.Opcion", on_delete=models.PROTECT, related_name="votos", verbose_name="opción")
    fecha_hora = models.DateTimeField("fecha y hora", auto_now_add=True)
    huella_ip = models.CharField("huella de IP", max_length=64, help_text="SHA-256 de la IP; la IP no se guarda en claro.")
    huella_navegador = models.CharField("huella del navegador", max_length=64)
    hash_auditoria = models.CharField("hash de auditoría", max_length=64)

    objects = VotoQuerySet.as_manager()

    class Meta:
        verbose_name = "voto"
        verbose_name_plural = "votos"
        ordering = ["-fecha_hora"]

    def __str__(self):
        return f"Voto #{self.pk} en «{self.votacion.nombre}»"

    def clean(self):
        # Integridad entre relaciones: la opción elegida debe pertenecer a la votación del voto.
        if self.opcion_id and self.votacion_id and self.opcion.votacion_id != self.votacion_id:
            raise ValidationError({"opcion": "La opción no pertenece a esta votación."})

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
