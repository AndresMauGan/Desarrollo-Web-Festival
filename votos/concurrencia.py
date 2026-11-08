"""
Demostración de CP-09: varias solicitudes de voto simultáneas a la misma categoría.

La usan la prueba ConcurrenciaTests (votos/test_casos_prueba.py) y el comando probar_concurrencia.
Cada solicitud corre en su propio hilo, con su propia conexión a MySQL, y todas llaman a la vez
a registrar_voto, igual que dos peticiones web que llegan al mismo tiempo.
"""

import threading
from contextlib import nullcontext
from unittest import mock

from django.db import connection

from .models import Voto
from .servicios import VotoRechazado, registrar_voto

ESPERA_MAXIMA = 30  # segundos; evita que una falla deje los hilos esperando para siempre


def votar_a_la_vez(usuario, categoria_id, opciones_ids, *, forzar_carrera=False):
    """
    Lanza un hilo por cada opción de opciones_ids y los suelta al mismo tiempo contra registrar_voto.

    Con forzar_carrera=True, cada hilo espera a los demás después de pasar todas las validaciones
    de Django y justo antes de insertar en MySQL. Así ninguna solicitud ve el voto de otra y la
    única protección que queda es la restricción única «un_voto_por_usuario_categoria_edicion».

    Devuelve una lista con un diccionario por solicitud:
    {"solicitud": n, "opcion": id, "resultado": "registrado" | "rechazado" | "error", "detalle": texto}.
    """
    cantidad = len(opciones_ids)
    salida = threading.Barrier(cantidad, timeout=ESPERA_MAXIMA)
    antes_de_insertar = threading.Barrier(cantidad, timeout=ESPERA_MAXIMA)
    resultados = []
    candado = threading.Lock()

    def solicitud(numero, opcion_id):
        try:
            salida.wait()
            voto = registrar_voto(usuario, categoria_id, opcion_id, ip="127.0.0.1", navegador="probar_concurrencia")
            resultado = {"resultado": "registrado", "detalle": f"Voto #{voto.pk} ({voto.codigo_comprobante})"}
        except VotoRechazado as rechazo:
            resultado = {"resultado": "rechazado", "detalle": f"{rechazo.mensaje} (HTTP {rechazo.estado_http})"}
        except Exception as error:  # se informa en lugar de perderse dentro del hilo
            resultado = {"resultado": "error", "detalle": repr(error)}
        finally:
            connection.close()  # cada hilo cierra su propia conexión a MySQL
        with candado:
            resultados.append({"solicitud": numero, "opcion": opcion_id, **resultado})

    full_clean_original = Voto.full_clean

    def validar_y_esperar(voto, *args, **kwargs):
        full_clean_original(voto, *args, **kwargs)
        antes_de_insertar.wait()

    hilos = [threading.Thread(target=solicitud, args=(n, opcion_id)) for n, opcion_id in enumerate(opciones_ids, 1)]
    # registrar_voto llama a full_clean() después de las cinco validaciones y antes de save()
    with mock.patch.object(Voto, "full_clean", validar_y_esperar) if forzar_carrera else nullcontext():
        for hilo in hilos:
            hilo.start()
        for hilo in hilos:
            hilo.join(ESPERA_MAXIMA * 2)
    return sorted(resultados, key=lambda r: r["solicitud"])
