"""Filtros y etiquetas de plantilla: formato colombiano, estados públicos e íconos."""

from datetime import datetime

from django import template
from django.utils import timezone
from django.utils.html import format_html

from festival.models import Categoria
from festival.views import ETIQUETAS_ESTADO

register = template.Library()

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]

ICONOS_FAMILIA = {
    Categoria.Familia.ACORDEON: "ph-music-notes",
    Categoria.Familia.CANCION: "ph-pen-nib",
    Categoria.Familia.PIQUERIA: "ph-microphone-stage",
    Categoria.Familia.PILONERA: "ph-users-three",
    Categoria.Familia.OTRA: "ph-star",
}

# Qué botón de la barra inferior se resalta según la vista actual
SECCIONES = {
    "inicio": "inicio",
    "categorias_actuales": "categorias", "categorias": "categorias", "categoria": "categorias", "votacion": "categorias",
    "ediciones": "ediciones", "edicion": "ediciones",
}


def _local(valor):
    return timezone.localtime(valor) if isinstance(valor, datetime) else valor


@register.filter
def fecha_co(valor):
    """1 de mayo de 2027"""
    if not valor:
        return ""
    valor = _local(valor)
    return f"{valor.day} de {MESES[valor.month - 1]} de {valor.year}"


@register.filter
def hora_co(valor):
    """7:30 p. m."""
    if not valor:
        return ""
    valor = _local(valor)
    hora = valor.hour % 12 or 12
    sufijo = "a. m." if valor.hour < 12 else "p. m."
    return f"{hora}:{valor.minute:02d} {sufijo}"


@register.filter
def fecha_hora_co(valor):
    """1 de mayo de 2027, 7:30 p. m."""
    return f"{fecha_co(valor)}, {hora_co(valor)}" if valor else ""


@register.simple_tag
def rango_fechas(inicio, fin):
    """Del 28 de abril al 1 de mayo de 2027"""
    if inicio.year == fin.year:
        return f"Del {inicio.day} de {MESES[inicio.month - 1]} al {fecha_co(fin)}"
    return f"Del {fecha_co(inicio)} al {fecha_co(fin)}"


@register.simple_tag
def estado_votacion(votacion):
    texto, clase = ETIQUETAS_ESTADO.get(votacion.estado, (votacion.get_estado_display(), "badge-cerrada"))
    return format_html('<span class="badge {}">{}</span>', clase, texto)


@register.filter
def icono_categoria(categoria):
    return "ph-crown" if categoria.es_rey_de_reyes else ICONOS_FAMILIA.get(categoria.familia, "ph-star")


@register.simple_tag(takes_context=True)
def seccion_activa(context):
    coincidencia = getattr(context.get("request"), "resolver_match", None)
    return SECCIONES.get(coincidencia.url_name, "") if coincidencia else ""
