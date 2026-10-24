"""
Carga datos de prueba: ediciones 2026 y 2027, sus categorías, votaciones en distintos estados
y opciones con nombres claramente ficticios (ninguna persona real).

Se puede ejecutar varias veces: actualiza los registros existentes en lugar de duplicarlos.
Cada registro pasa por full_clean(), así que respeta las mismas validaciones del modelo (RN-11 incluida).
"""

from datetime import date, datetime

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from festival.models import Categoria, Edicion, Opcion, Votacion

Familia = Categoria.Familia
Ronda = Votacion.Ronda
Estado = Votacion.Estado
Tipo = Opcion.Tipo


def hora(anio, mes, dia, h, m=0):
    return timezone.make_aware(datetime(anio, mes, dia, h, m))  # zona America/Bogota (settings.TIME_ZONE)


EDICIONES = [
    # Fechas de 2026 de ejemplo; las de 2027 son las del Festival (28 de abril al 1 de mayo).
    dict(anio=2026, numero=59, nombre="59.º Festival de la Leyenda Vallenata", fecha_inicio=date(2026, 4, 29), fecha_fin=date(2026, 5, 2), activa=False),
    dict(anio=2027, numero=60, nombre="60.º Festival de la Leyenda Vallenata", fecha_inicio=date(2027, 4, 28), fecha_fin=date(2027, 5, 1), activa=True),
]

CATEGORIAS = [
    dict(nombre="Rey Vallenato Profesional", familia=Familia.ACORDEON, nivel="Profesional", orden=1),
    dict(nombre="Acordeonera Mayor", familia=Familia.ACORDEON, nivel="Mayor", orden=2),
    dict(nombre="Canción Inédita", familia=Familia.CANCION, nivel="", orden=3),
    dict(nombre="Piquería Mayor", familia=Familia.PIQUERIA, nivel="Mayor", orden=4),
]

# (categoría, nombre, ronda, estado, abre, cierra, opciones)
# Cada opción: (nombre, tipo, publicada, estado). Todos los nombres son inventados.
VOTACIONES = {
    2027: [
        ("Rey Vallenato Profesional", "Final Rey Vallenato Profesional", Ronda.FINAL, Estado.PROGRAMADA,
         hora(2027, 5, 1, 19), hora(2027, 5, 1, 23, 30),
         [("Acordeonero Ficticio Uno", Tipo.PERSONA, True, "activa"),
          ("Acordeonero Ficticio Dos", Tipo.PERSONA, True, "activa"),
          ("Acordeonero Ficticio Tres", Tipo.PERSONA, True, "activa")]),
        ("Rey Vallenato Profesional", "Eliminatoria Rey Vallenato Profesional", Ronda.ELIMINATORIA, Estado.BORRADOR,
         hora(2027, 4, 28, 9), hora(2027, 4, 28, 18),
         [("Acordeonero Ficticio Cuatro", Tipo.PERSONA, False, "activa")]),
        ("Acordeonera Mayor", "Semifinal Acordeonera Mayor", Ronda.SEMIFINAL, Estado.ABIERTA,
         hora(2027, 4, 30, 14), hora(2027, 4, 30, 22),
         [("Acordeonera Ficticia Uno", Tipo.PERSONA, True, "activa"),
          ("Acordeonera Ficticia Dos", Tipo.PERSONA, True, "activa"),
          ("Acordeonera Ficticia Tres", Tipo.PERSONA, True, "retirada"),
          ("Acordeonera Ficticia Cuatro", Tipo.PERSONA, False, "activa")]),
        ("Canción Inédita", "Final Canción Inédita", Ronda.FINAL, Estado.PAUSADA,
         hora(2027, 4, 30, 16), hora(2027, 4, 30, 23),
         [("«Río de Ejemplo», de Autor Ficticio A", Tipo.OBRA, True, "activa"),
          ("«Sabana de Prueba», de Autora Ficticia B", Tipo.OBRA, True, "activa")]),
        ("Piquería Mayor", "Eliminatoria Piquería Mayor", Ronda.ELIMINATORIA, Estado.CERRADA,
         hora(2027, 4, 29, 15), hora(2027, 4, 29, 21),
         [("Pareja Repentista Ficticia A", Tipo.GRUPO, True, "activa"),
          ("Pareja Repentista Ficticia B", Tipo.GRUPO, True, "activa")]),
    ],
    2026: [
        ("Rey Vallenato Profesional", "Final Rey Vallenato Profesional 2026", Ronda.FINAL, Estado.CERRADA,
         hora(2026, 5, 2, 19), hora(2026, 5, 2, 23),
         [("Acordeonero Ficticio Histórico A", Tipo.PERSONA, True, "activa"),
          ("Acordeonero Ficticio Histórico B", Tipo.PERSONA, True, "activa")]),
    ],
}


def guardar(modelo, buscar, valores):
    """update_or_create que además valida el registro completo antes de guardarlo."""
    objeto = modelo.objects.filter(**buscar).first() or modelo(**buscar)
    for campo, valor in valores.items():
        setattr(objeto, campo, valor)
    objeto.full_clean()
    objeto.save()
    return objeto


class Command(BaseCommand):
    help = "Carga ediciones, categorías, votaciones y opciones de prueba (nombres ficticios)."

    @transaction.atomic
    def handle(self, *args, **options):
        conteo = {"ediciones": 0, "categorias": 0, "votaciones": 0, "opciones": 0}

        for datos in EDICIONES:
            edicion = guardar(Edicion, {"anio": datos["anio"]}, datos)
            conteo["ediciones"] += 1

            categorias = {}
            for cat in CATEGORIAS:
                categorias[cat["nombre"]] = guardar(
                    Categoria, {"edicion": edicion, "nombre": cat["nombre"]},
                    {**cat, "admite_voto_publico": True, "publicada": True},
                )
                conteo["categorias"] += 1

            for cat_nombre, nombre, ronda, estado, abre, cierra, opciones in VOTACIONES[edicion.anio]:
                # Primero se guarda sin abrir y con sus opciones; después se pone el estado final,
                # así «abierta» pasa por la validación de RN-11 como en el admin.
                existente = Votacion.objects.filter(categoria=categorias[cat_nombre], nombre=nombre).first()
                votacion = guardar(
                    Votacion, {"categoria": categorias[cat_nombre], "nombre": nombre},
                    {"ronda": ronda, "abre_en": abre, "cierra_en": cierra,
                     "estado": existente.estado if existente else Estado.BORRADOR},
                )
                for orden, (op_nombre, tipo, publicada, op_estado) in enumerate(opciones, start=1):
                    guardar(Opcion, {"votacion": votacion, "nombre": op_nombre},
                            {"tipo": tipo, "orden": orden, "publicada": publicada, "estado": op_estado})
                    conteo["opciones"] += 1
                votacion.estado = estado
                votacion.full_clean()
                votacion.save()
                conteo["votaciones"] += 1

        self.stdout.write(self.style.SUCCESS(
            "Datos de prueba cargados: {ediciones} ediciones, {categorias} categorías, "
            "{votaciones} votaciones y {opciones} opciones.".format(**conteo)
        ))
