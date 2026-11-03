"""
Indicador de cambio de la vibracion respecto de la linea base (D-059, ver
PROYECTO.md).

La severidad de ISO 20816-3 (severidad_iso.py) solo aplica a maquinas de mas
de 15 kW; bajo ese limite el sistema la declara "no aplicable" y no entrega
ninguna medida de que tan grave es la vibracion. Este modulo cubre ese hueco
con un criterio RELATIVO: compara la velocidad RMS de banda ancha de la
medicion actual con la de la medicion que el usuario marco como referencia
sana (linea base, D-056). Es el mismo principio del criterio II de la norma
(cambio respecto de un valor de referencia), pero con la referencia propia de
la maquina en vez de los limites de zona.

NO es una norma: los umbrales de cambio son los de
criterios_proyecto.definicion_cualitativa (criterios_proyecto.yaml) (elevado >= 1,25 y
muy_elevado >= 2,0 veces la referencia) y la banda de medicion es la de ISO
20816-3 aplicada como criterio del proyecto. Pendiente de validacion.

Se usa banda limitada (10-1000 Hz; 2-1000 Hz bajo 600 r/min) y no todo el
espectro: integrar a velocidad amplifica el ruido de baja frecuencia (la
velocidad es la aceleracion dividida por 2*pi*f), y en una señal sin falla eso
hace variar la velocidad calculada por un factor 2, lo que arruinaria un
cociente entre dos mediciones.

Este modulo no conoce la base de datos ni HTTP: recibe y devuelve datos.
"""

import numpy as np

from backend.procesamiento.severidad_iso import (
    UNIDADES_ACELERACION_A_M_S2,
    UNIDADES_VELOCIDAD_A_MM_S,
)

EJES = ("x", "y", "z")

# Fraccion minima del limite superior de la banda de referencia que debe
# alcanzar el Nyquist de la medicion actual para considerarlas comparables.
UMBRAL_BANDA_COMPARABLE = 0.9


def _no_aplicable(motivo, codigo):
    return {
        "aplicable": False,
        "motivo_no_aplicable": motivo,
        "motivo_codigo": codigo,
        "velocidad_rms_actual_mm_s": None,
        "velocidad_rms_referencia_mm_s": None,
        "razon": None,
        "nivel": None,
        "banda_hz": None,
        "por_eje": None,
    }


def banda_de_medicion(frecuencia_muestreo, rpm, normativa):
    """(f_min, f_max) en Hz: la banda del YAML, recortada al Nyquist de la señal."""
    banda = normativa["criterios_proyecto"]["cambio_respecto_linea_base"]["banda_hz"]
    if rpm and rpm < banda["rpm_limite_banda_baja"]:
        minima = banda["minima_bajo_600_rpm"]
    else:
        minima = banda["minima"]
    return float(minima), float(min(banda["maxima"], frecuencia_muestreo / 2))


def calcular_velocidad_rms_banda_mm_s(señal, frecuencia_muestreo, unidad, f_min, f_max):
    """
    Velocidad RMS (mm/s) de la señal restringida a [f_min, f_max]. Si la unidad
    es de aceleracion, se integra en el dominio de la frecuencia dentro de la
    banda; si ya es de velocidad, solo se limita la banda. Devuelve None si la
    unidad no es de aceleracion ni de velocidad reconocida: nunca se asume una.
    """
    señal = np.asarray(señal, dtype=float)
    if len(señal) < 2:
        return None

    factor_velocidad = UNIDADES_VELOCIDAD_A_MM_S.get(unidad)
    factor_aceleracion = UNIDADES_ACELERACION_A_M_S2.get(unidad)
    if factor_velocidad is None and factor_aceleracion is None:
        return None

    espectro = np.fft.rfft(señal * (factor_velocidad if factor_velocidad is not None else factor_aceleracion))
    frecuencias = np.fft.rfftfreq(len(señal), d=1 / frecuencia_muestreo)
    en_banda = (frecuencias >= f_min) & (frecuencias <= f_max)

    resultado = np.zeros_like(espectro)
    if factor_velocidad is not None:
        resultado[en_banda] = espectro[en_banda]
        velocidad_mm_s = np.fft.irfft(resultado, n=len(señal))
    else:
        resultado[en_banda] = espectro[en_banda] / (1j * 2 * np.pi * frecuencias[en_banda])
        velocidad_mm_s = np.fft.irfft(resultado, n=len(señal)) * 1000

    return float(np.sqrt(np.mean(np.square(velocidad_mm_s))))


def calcular_valores_velocidad_linea_base(datos_crudos, frecuencia_muestreo, unidad, rpm, normativa):
    """
    Lo que se guarda en LineaBase.valores["velocidad_rms"]: la velocidad RMS de
    banda limitada por eje de la medicion de referencia, mas la banda y la
    frecuencia de muestreo con que se calculo (para comparar con lo mismo).
    Devuelve None si la unidad no es reconocida o no hay ejes de vibracion.
    """
    f_min, f_max = banda_de_medicion(frecuencia_muestreo, rpm, normativa)

    por_eje = {}
    for eje in EJES:
        columna = f"vibracion_{eje}"
        if columna not in datos_crudos.columns:
            continue
        valor = calcular_velocidad_rms_banda_mm_s(datos_crudos[columna].to_numpy(), frecuencia_muestreo, unidad, f_min, f_max)
        if valor is None:
            return None
        por_eje[eje] = round(valor, 6)

    if not por_eje:
        return None

    return {
        "por_eje_mm_s": por_eje,
        "banda_hz": [f_min, f_max],
        "frecuencia_muestreo": frecuencia_muestreo,
        "unidad": unidad,
    }


def evaluar_cambio_respecto_linea_base(datos_crudos, frecuencia_muestreo, unidad, valores_linea_base, normativa):
    """
    Compara la velocidad RMS actual (peor eje) con la de la referencia (peor
    eje), en la misma banda. Devuelve un dict con aplicable True y la razon y
    el nivel (sin_cambio / elevado / muy_elevado / disminuyo), o aplicable
    False con el motivo exacto.
    """
    if not valores_linea_base:
        return _no_aplicable(
            "El sensor no tiene línea base: marca una medición sana como referencia en el "
            "Analizador de Vibraciones para comparar el cambio de la vibración.",
            "sin_linea_base",
        )

    referencia = valores_linea_base.get("velocidad_rms")
    if not referencia:
        return _no_aplicable(
            "La línea base de este sensor no trae la velocidad de referencia (se marcó antes de este "
            "indicador, o su medición no declaraba una unidad de aceleración o velocidad reconocida): "
            "márcala de nuevo con una medición que declare la unidad.",
            "linea_base_sin_velocidad",
        )

    f_min, f_max = referencia["banda_hz"]
    # Se tolera hasta un 10 % de diferencia en el limite superior de la banda:
    # la frecuencia de muestreo real de un registro rara vez es exacta (en los
    # archivos de Kumar et al. fluctuaba ~1 %) y recortar la banda en esa
    # proporcion no altera la velocidad RMS de forma apreciable.
    if frecuencia_muestreo / 2 < f_max * UMBRAL_BANDA_COMPARABLE:
        return _no_aplicable(
            f"La medición actual se muestreó a {frecuencia_muestreo:g} Hz y la referencia se calculó hasta "
            f"{f_max:g} Hz: no son comparables. Marca la línea base con una medición de la misma frecuencia de muestreo.",
            "muestreo_distinto",
        )
    f_max = min(f_max, frecuencia_muestreo / 2)

    por_eje = {}
    for eje, valor_referencia in referencia["por_eje_mm_s"].items():
        columna = f"vibracion_{eje}"
        if columna not in datos_crudos.columns:
            continue
        valor_actual = calcular_velocidad_rms_banda_mm_s(datos_crudos[columna].to_numpy(), frecuencia_muestreo, unidad, f_min, f_max)
        if valor_actual is None:
            return _no_aplicable(
                f"La unidad de la medición ({unidad or 'no declarada'}) no es una unidad de aceleración o "
                "velocidad reconocida: no se puede calcular la velocidad RMS.",
                "unidad_no_reconocida",
            )
        por_eje[eje] = {
            "actual_mm_s": round(valor_actual, 4),
            "referencia_mm_s": valor_referencia,
            "razon": round(valor_actual / valor_referencia, 2) if valor_referencia > 0 else None,
        }

    if not por_eje:
        return _no_aplicable("No hay ejes de vibración disponibles en la señal.", "sin_ejes")

    eje_actual = max(por_eje, key=lambda e: por_eje[e]["actual_mm_s"])
    eje_referencia = max(por_eje, key=lambda e: por_eje[e]["referencia_mm_s"])
    actual = por_eje[eje_actual]["actual_mm_s"]
    valor_referencia = por_eje[eje_referencia]["referencia_mm_s"]

    if valor_referencia <= 0:
        return _no_aplicable("La velocidad de la referencia es cero: no se puede calcular el cambio.", "referencia_cero")

    razon = actual / valor_referencia
    umbrales = normativa["criterios_proyecto"]["definicion_cualitativa"]
    elevado = umbrales["elevado"]["min_ratio_baseline"]
    muy_elevado = umbrales["muy_elevado"]["min_ratio_baseline"]

    if razon >= muy_elevado:
        nivel = "muy_elevado"
    elif razon >= elevado:
        nivel = "elevado"
    elif razon <= 1 / elevado:
        nivel = "disminuyo"
    else:
        nivel = "sin_cambio"

    return {
        "aplicable": True,
        "motivo_no_aplicable": None,
        "motivo_codigo": None,
        "velocidad_rms_actual_mm_s": actual,
        "eje_actual": eje_actual,
        "velocidad_rms_referencia_mm_s": valor_referencia,
        "eje_referencia": eje_referencia,
        "razon": round(razon, 2),
        "nivel": nivel,
        "banda_hz": [f_min, f_max],
        "por_eje": por_eje,
        "umbrales": {"elevado": elevado, "muy_elevado": muy_elevado},
    }
