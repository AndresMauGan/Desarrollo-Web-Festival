"""
Reglas de negocio en un solo lugar (observación 2 del docente sobre la Entrega 1).

Las reglas pendientes de la Fundación no se implementan como decisiones definitivas:
aquí solo se guardan sus valores por defecto, con la regla y la pregunta abierta.
"""

# Valores por defecto mientras la Fundación decide. No son reglas confirmadas.
LIMITE_VOTOS_POR_DEFECTO = 1             # RN-01, pendiente (P-03)
VISIBILIDAD_RESULTADOS_POR_DEFECTO = "al_cierre"  # RN-06, pendiente (P-05)
REQUIERE_CORREO_VERIFICADO = False       # RN-04, pendiente (P-01)
EDAD_MINIMA = 18                         # RN-08, pendiente (P-12)

# Reglas propuestas por el equipo, que sí se aplican.
MINIMO_OPCIONES_PARA_ABRIR = 2           # RN-11: no se abre una votación con menos de dos opciones publicadas
