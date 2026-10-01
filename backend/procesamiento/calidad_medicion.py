"""
Chequeo de calidad de una medicion antes de diagnosticar, segun los
criterios ya curados en conocimiento/normativa_motorguardian.yaml
(calidad_medicion) - la parte de ISO 13373-1 que el sistema puede
evaluar con los datos que ya captura.

Alcance acotado a proposito: de las validaciones que define el YAML,
solo se evaluan las 2 que se pueden calcular con los datos disponibles
hoy:
    - frecuencia_muestreo (Nyquist): la frecuencia de muestreo debe ser
      al menos 2.0x (minimo) o 2.56x (recomendado) la frecuencia mas
      alta que efectivamente se necesita analizar (3x RPM, o la mayor
      frecuencia de falla de rodamiento si corresponde).
    - duracion_registro: la resolucion en frecuencia (1/duracion) debe
      ser fina respecto a la frecuencia de giro del equipo, para poder
      separar 1x de 2x sin ambiguedad (heuristica propia, ver
      RESOLUCION_MINIMA_DIVISORES_RPM - el YAML solo dice
      "exigir_resolucion_frecuencia_adecuada: true" sin un numero).

Las demas validaciones que el YAML define (saturacion_sensor,
muestras_perdidas, montaje_sensor, orientacion_sensor,
condicion_operacional_estable) requieren metadata que el sistema no
captura todavia (ninguna pantalla pide esos datos hoy) - se declaran
explicitamente en "no_evaluados", nunca se asume que pasaron.

Decision de diseño: el YAML pide "bloqueo_diagnostico_si_falla_critica:
true". Se decidio NO bloquear la respuesta de los endpoints existentes
(cambiaria el contrato de /api/reportes y /api/alertas para equipos que
hoy funcionan bien) - en su lugar, un estado "invalida" queda expuesto
de forma imposible de pasar por alto (limitaciones del diagnostico,
UI, PDF), pero el calculo se sigue mostrando. Revisar con el
desarrollador si en algun momento se prefiere bloquear de verdad.
"""

RESOLUCION_MINIMA_DIVISORES_RPM = 4

NO_EVALUADOS_SIEMPRE = [
    "saturacion_sensor",
    "muestras_perdidas",
    "montaje_sensor",
    "orientacion_sensor",
    "condicion_operacional_estable",
]


def evaluar_calidad_medicion(frecuencia_muestreo, duracion_segundos, frecuencia_maxima_interes_hz, frecuencia_rotacion_hz, normativa):
    config = normativa["calidad_medicion"]["validaciones"]
    advertencias = []
    criticas = []

    regla_fs = config["frecuencia_muestreo"]["regla"]
    if frecuencia_muestreo and frecuencia_maxima_interes_hz:
        factor_minimo = regla_fs["factor_minimo_sobre_fmax"]
        factor_recomendado = regla_fs["factor_recomendado_sobre_fmax"]
        factor_actual = frecuencia_muestreo / frecuencia_maxima_interes_hz
        frecuencia_minima_requerida = frecuencia_maxima_interes_hz * factor_minimo
        frecuencia_recomendada = frecuencia_maxima_interes_hz * factor_recomendado

        if factor_actual < factor_minimo:
            criticas.append(
                f"La frecuencia de muestreo ({frecuencia_muestreo:.0f} Hz) es {factor_actual:.2f} veces "
                f"la frecuencia máxima analizada ({frecuencia_maxima_interes_hz:.1f} Hz) — insuficiente. "
                f"Para una medición válida (ISO 13373-1) se requiere muestrear a al menos "
                f"{frecuencia_minima_requerida:.0f} Hz (idealmente {frecuencia_recomendada:.0f} Hz)."
            )
        elif factor_actual < factor_recomendado:
            advertencias.append(
                f"La frecuencia de muestreo ({frecuencia_muestreo:.0f} Hz) es {factor_actual:.2f} veces "
                f"la frecuencia máxima analizada ({frecuencia_maxima_interes_hz:.1f} Hz) — por debajo de "
                f"lo recomendado. ISO 13373-1 recomienda al menos {frecuencia_recomendada:.0f} Hz "
                f"({factor_recomendado}x) para un margen más seguro."
            )

    if frecuencia_rotacion_hz and duracion_segundos:
        resolucion_hz = 1 / duracion_segundos
        resolucion_exigida = frecuencia_rotacion_hz / RESOLUCION_MINIMA_DIVISORES_RPM
        if resolucion_hz > resolucion_exigida:
            advertencias.append(
                f"Ventana de {duracion_segundos:.1f} s da una resolución de {resolucion_hz:.2f} Hz — "
                f"puede no alcanzar a separar claramente 1x ({frecuencia_rotacion_hz:.1f} Hz) de 2x "
                "(ISO 13373-1, resolución de frecuencia adecuada)."
            )

    if criticas:
        estado = "invalida"
    elif advertencias:
        estado = "valida_con_advertencias"
    else:
        estado = "valida"

    return {
        "estado": estado,
        "criticas": criticas,
        "advertencias": advertencias,
        "no_evaluados": list(NO_EVALUADOS_SIEMPRE),
    }
