"""
Motor de diagnostico basico: detecta picos en el espectro FFT y los
compara contra las frecuencias esperadas de 1x/2x/3x RPM, aplicando un
subconjunto de las reglas curadas en conocimiento/normativa_motorguardian.yaml
(D-032).

Alcance actual (deliberadamente acotado — ver PROYECTO.md):
    - Solo 3 reglas, las que dependen unicamente de 1x/2x/3x: desbalanceo,
      desalineacion_angular, desalineacion_paralela. Rodamientos y
      engranajes quedan pendientes hasta capturar geometria de rodamiento.
    - No hay linea base (baseline) historica todavia (gestion_condicion.
      baseline en el YAML): "elevada" se interpreta como "hay un pico
      significativo" (prominencia + relacion senal/ruido), no como una
      comparacion contra una condicion sana conocida. Se declara como
      limitacion explicita en cada resultado.
    - No se distingue vibracion radial de axial (los sensores no traen
      esa semantica todavia): se buscan picos en los 3 ejes por igual.
      Por eso desalineacion_angular, cuya evidencia mas fuerte es
      vibracion axial, queda con confianza tope acotada.
"""

from functools import lru_cache
from pathlib import Path

import numpy as np
import yaml
from scipy.signal import find_peaks

RUTA_PROYECTO = Path(__file__).parent.parent.parent
RUTA_NORMATIVA = RUTA_PROYECTO / "conocimiento" / "normativa_motorguardian.yaml"

TOLERANCIA_FRECUENCIA_PCT = 3.0
EJES = ["x", "y", "z"]

LIMITACIONES = [
    "Diagnostico basado en reglas de 1x/2x/3x RPM (desbalanceo, desalineacion "
    "angular, desalineacion paralela) y, si corresponde, en las 4 reglas de "
    "rodamiento (pista exterior/interior, elemento rodante, jaula). Engranajes "
    "no se evaluan todavia.",
    "No existe una linea base (baseline) historica del equipo sano: 'evidencia "
    "presente' significa que hay un pico significativo en la frecuencia "
    "esperada, no que la amplitud sea anormalmente alta respecto a un "
    "historial. Interpretar con cautela.",
    "No se distingue vibracion radial de axial: se revisan los 3 ejes por "
    "igual. La desalineacion angular depende principalmente de vibracion "
    "axial, que no se puede aislar todavia — su confianza queda acotada.",
    "Requiere inspeccion fisica para confirmar cualquier hipotesis.",
]


@lru_cache
def cargar_normativa():
    with open(RUTA_NORMATIVA, encoding="utf-8") as archivo:
        return yaml.safe_load(archivo)


def detectar_picos(frecuencias, amplitudes):
    """Picos con prominencia >= 5% del maximo y relacion senal/ruido >= 3x."""
    amplitudes = np.array(amplitudes)

    if len(amplitudes) == 0 or amplitudes.max() <= 0:
        return []

    prominencia_minima = 0.05 * amplitudes.max()
    indices, _ = find_peaks(amplitudes, prominence=prominencia_minima)

    ruido = np.median(amplitudes) or 1e-9

    return [
        {"frecuencia": float(frecuencias[i]), "amplitud": float(amplitudes[i])}
        for i in indices
        if amplitudes[i] / ruido >= 3.0
    ]


def frecuencias_esperadas(rpm_nominal):
    base = rpm_nominal / 60
    return {"1x": base, "2x": base * 2, "3x": base * 3}


def buscar_pico_cercano(picos, frecuencia_objetivo, tolerancia_pct=TOLERANCIA_FRECUENCIA_PCT):
    tolerancia = frecuencia_objetivo * (tolerancia_pct / 100)
    coincidencias = [
        p for p in picos if abs(p["frecuencia"] - frecuencia_objetivo) <= tolerancia
    ]
    return max(coincidencias, key=lambda p: p["amplitud"]) if coincidencias else None


def analizar_espectro_fft(datos_fft, rpm_nominal):
    """
    datos_fft: lista de {frecuencia, amplitud_x, amplitud_y, amplitud_z}
    tal como devuelve backend/procesamiento/frecuencia.py::calcular_fft.

    Devuelve, por armonico (1x/2x/3x), el mejor pico encontrado en
    cualquiera de los 3 ejes (y en cual).
    """
    frecuencias = [d["frecuencia"] for d in datos_fft]
    picos_por_eje = {
        eje: detectar_picos(frecuencias, [d[f"amplitud_{eje}"] for d in datos_fft])
        for eje in EJES
    }

    resultado = {}
    for armonico, frecuencia_objetivo in frecuencias_esperadas(rpm_nominal).items():
        mejor = None
        for eje in EJES:
            pico = buscar_pico_cercano(picos_por_eje[eje], frecuencia_objetivo)
            if pico and (mejor is None or pico["amplitud"] > mejor["amplitud"]):
                mejor = {**pico, "eje": eje, "frecuencia_esperada": frecuencia_objetivo}
        resultado[armonico] = mejor

    return resultado


def evaluar_reglas(hallazgos_armonicos, normativa):
    """
    hallazgos_armonicos: {"1x": pico_o_None, "2x": ..., "3x": ...}

    Evalua las 3 reglas soportadas con un subconjunto reducido de su
    evidencia (ver docstring del modulo) y devuelve las hipotesis con
    confianza >= 0.30, ordenadas de mayor a menor, maximo 3 (mismos
    criterios que confianza_diagnostico.reglas_salida en el YAML).
    """
    pesos = normativa["motor_diagnostico"]["pesos_evidencia"]
    reglas_yaml = normativa["motor_diagnostico"]["reglas"]

    presente_1x = hallazgos_armonicos["1x"] is not None
    presente_2x = hallazgos_armonicos["2x"] is not None

    definiciones = [
        {
            "falla": "desbalanceo",
            "peso_cumplido": pesos["fuerte"] if presente_1x else 0,
            "peso_evaluable": pesos["fuerte"],
            "evidencias": ["pico significativo en 1x"] if presente_1x else [],
            "tope_confianza": 1.0,
        },
        {
            "falla": "desalineacion_paralela",
            "peso_cumplido": (
                (pesos["fuerte"] if presente_2x else 0)
                + (pesos["moderada"] if presente_1x else 0)
            ),
            "peso_evaluable": pesos["fuerte"] + pesos["moderada"],
            "evidencias": (
                (["pico significativo en 2x"] if presente_2x else [])
                + (["pico significativo en 1x"] if presente_1x else [])
            ),
            "tope_confianza": 1.0,
        },
        {
            "falla": "desalineacion_angular",
            "peso_cumplido": (
                (pesos["moderada"] if presente_1x else 0)
                + (pesos["moderada"] if presente_2x else 0)
            ),
            "peso_evaluable": pesos["moderada"] * 2,
            "evidencias": (
                (["pico significativo en 1x"] if presente_1x else [])
                + (["pico significativo en 2x"] if presente_2x else [])
            ),
            # Su evidencia mas fuerte (vibracion axial) no es evaluable
            # todavia: se acota el tope de confianza (mismo criterio que
            # las restricciones de confianza_diagnostico en el YAML).
            "tope_confianza": 0.50,
        },
    ]

    hipotesis = []
    for definicion in definiciones:
        if definicion["peso_cumplido"] <= 0:
            continue

        score = min(
            definicion["peso_cumplido"] / definicion["peso_evaluable"],
            definicion["tope_confianza"],
        )

        if score < 0.30:
            continue

        regla_yaml = reglas_yaml.get(definicion["falla"], {})

        hipotesis.append(
            {
                "falla": definicion["falla"],
                "confianza": round(score, 2),
                "evidencias": definicion["evidencias"],
                "recomendacion": regla_yaml.get("recomendacion", []),
            }
        )

    hipotesis.sort(key=lambda h: h["confianza"], reverse=True)
    return hipotesis[:3]


def diagnosticar_sensor(
    datos_fft,
    rpm_nominal,
    datos_crudos=None,
    frecuencia_muestreo=None,
    rodamiento=None,
):
    """
    datos_crudos, frecuencia_muestreo y rodamiento son opcionales: solo
    hace falta pasarlos cuando el sensor tiene un Rodamiento vinculado
    (D-038) y se quiere evaluar tambien sus 4 reglas de falla
    (backend/procesamiento/rodamientos.py) - a diferencia de 1x/2x/3x,
    esas reglas necesitan la señal cruda en el tiempo, no solo la FFT
    ya calculada, porque trabajan sobre el espectro de envolvente.
    """
    normativa = cargar_normativa()
    hallazgos = analizar_espectro_fft(datos_fft, rpm_nominal)
    hipotesis = evaluar_reglas(hallazgos, normativa)
    limitaciones = list(LIMITACIONES)
    frecuencias_falla_rodamiento = None
    datos_grafico_rodamiento = None

    if rodamiento is not None:
        from backend.procesamiento.diagnostico_rodamientos import (
            LIMITACIONES_RODAMIENTO,
            calcular_datos_grafico,
            calcular_frecuencias_falla,
            evaluar_rodamiento,
            geometria_completa,
        )

        if not geometria_completa(rodamiento):
            limitaciones.append(
                f"El sensor tiene el rodamiento {rodamiento.codigo} vinculado, pero su "
                "geometria esta incompleta (faltan datos en Configuracion > Rodamientos) "
                "- no se evaluaron sus fallas."
            )
        elif datos_crudos is None or not frecuencia_muestreo:
            limitaciones.append(
                f"El rodamiento {rodamiento.codigo} tiene geometria completa, pero no se "
                "recibio la señal cruda para calcular su espectro de envolvente - no se "
                "evaluaron sus fallas."
            )
        else:
            frecuencias_falla_rodamiento = calcular_frecuencias_falla(rpm_nominal, rodamiento)
            hipotesis_rodamiento = evaluar_rodamiento(
                datos_crudos, frecuencia_muestreo, rpm_nominal, rodamiento, normativa
            )
            hipotesis += hipotesis_rodamiento
            limitaciones += LIMITACIONES_RODAMIENTO
            # Datos crudos para graficar espectro de envolvente + señal
            # con su envolvente superpuesta - se calcula con la lista de
            # hipotesis de rodamiento SIN recortar (para elegir el eje
            # de la de mayor confianza, aunque despues no quede entre
            # las 3 hipotesis totales que se muestran).
            datos_grafico_rodamiento = calcular_datos_grafico(
                datos_crudos, frecuencia_muestreo, rpm_nominal, rodamiento, hipotesis_rodamiento
            )

    hipotesis.sort(key=lambda h: h["confianza"], reverse=True)
    hipotesis = hipotesis[:3]

    return {
        "datos_grafico_rodamiento": datos_grafico_rodamiento,
        "frecuencias_esperadas": frecuencias_esperadas(rpm_nominal),
        "frecuencias_falla_rodamiento": frecuencias_falla_rodamiento,
        "hallazgos_armonicos": hallazgos,
        "hipotesis": hipotesis,
        "limitaciones": limitaciones,
    }
