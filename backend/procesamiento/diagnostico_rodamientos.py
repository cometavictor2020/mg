"""
Formulas y evaluacion de las 4 reglas de falla de rodamiento de
conocimiento/normativa_motorguardian.yaml: pista exterior (BPFO), pista
interior (BPFI), elemento rodante (BSF) y jaula (FTF).

Nota de nombres: este modulo vive en backend/procesamiento/ (calculo y
reglas de diagnostico) y es distinto de backend/api/administracion/
rodamientos.py (el CRUD del catalogo de Rodamiento) - mismo patron que
diagnostico.py vs los endpoints de administracion.

Requiere geometria completa en el Rodamiento vinculado al sensor
(D-038): numero_elementos_rodantes, diametro_elemento_mm,
diametro_paso_mm, angulo_contacto_grados - sin ella no se puede
calcular ninguna de las 4 frecuencias.

A diferencia de las reglas de diagnostico.py (que miran el espectro
crudo en 1x/2x/3x), estas miran el ESPECTRO DE ENVOLVENTE
(envolvente.py) - el metodo que especifica el propio YAML para
rodamientos. Por eso necesitan la señal cruda en el tiempo (no solo el
espectro ya calculado que usa diagnostico.py).

Cada regla evalua la evidencia que el propio YAML le asigna (distinta
por regla, no generica):
    - BPFO: pico fundamental (fuerte) + armonico (fuerte).
    - BPFI: pico fundamental (fuerte) + bandas laterales separadas 1x
      alrededor de BPFI (fuerte) + armonico (moderada).
    - BSF: pico fundamental (fuerte) + bandas laterales separadas FTF
      alrededor de BSF (moderada).
    - FTF: solo pico fundamental (fuerte) - es la unica evidencia que
      la normativa define para esta regla.

Alcance actual, deliberadamente acotado (ver LIMITACIONES_RODAMIENTO,
que se agrega a las limitaciones generales del reporte cuando aplica):
    - No se evalua kurtosis (evidencia moderada adicional de BPFO en el
      YAML) - mas compleja de calcular con una base fiable todavia.
    - El espectro de envolvente no aisla antes una banda de resonancia
      (ver limitacion en envolvente.py).
"""

import numpy as np

from backend.procesamiento.diagnostico import detectar_picos, buscar_pico_cercano
from backend.procesamiento.envolvente import calcular_envolvente, calcular_espectro_envolvente

EJES = ["x", "y", "z"]

# coincidencia_frecuencia_rodamientos_pct_default del YAML.
TOLERANCIA_RODAMIENTO_PCT = 2.0

NOMBRE_REGLA_POR_FALLA = {
    "BPFO": "rodamiento_pista_exterior",
    "BPFI": "rodamiento_pista_interior",
    "BSF": "rodamiento_elemento_rodante",
    "FTF": "rodamiento_jaula",
}

LIMITACIONES_RODAMIENTO = [
    "El espectro de envolvente no aisla antes una banda de resonancia especifica "
    "(no hay filtro de banda pasante ni deteccion automatica todavia): se demodula "
    "la señal completa, lo que puede diluir el pico real en señales ruidosas.",
    "No se evalua kurtosis (evidencia adicional de pista exterior que la normativa "
    "tambien define) - requiere una base de comparacion que todavia no existe.",
]


def geometria_completa(rodamiento):
    return all(
        valor is not None
        for valor in [
            rodamiento.numero_elementos_rodantes,
            rodamiento.diametro_elemento_mm,
            rodamiento.diametro_paso_mm,
            rodamiento.angulo_contacto_grados,
        ]
    )


def calcular_frecuencias_falla(rpm_nominal, rodamiento):
    """BPFO/BPFI/BSF/FTF - formulas estandar de diagnostico de rodamientos."""
    fr = rpm_nominal / 60
    ratio = (rodamiento.diametro_elemento_mm / rodamiento.diametro_paso_mm) * np.cos(
        np.radians(rodamiento.angulo_contacto_grados)
    )
    n = rodamiento.numero_elementos_rodantes

    return {
        "BPFO": (n / 2) * fr * (1 - ratio),
        "BPFI": (n / 2) * fr * (1 + ratio),
        "BSF": (rodamiento.diametro_paso_mm / (2 * rodamiento.diametro_elemento_mm))
        * fr
        * (1 - ratio ** 2),
        "FTF": (fr / 2) * (1 - ratio),
    }


def _mejor_pico_por_eje(datos_crudos, frecuencia_muestreo, frecuencia_objetivo, frecuencia_maxima):
    if frecuencia_objetivo <= 0:
        return None

    mejor = None
    for eje in EJES:
        columna = f"vibracion_{eje}"
        if columna not in datos_crudos.columns:
            continue

        frecuencias, amplitudes = calcular_espectro_envolvente(
            datos_crudos[columna].to_numpy(), frecuencia_muestreo, frecuencia_maxima
        )
        picos = detectar_picos(frecuencias, amplitudes)
        pico = buscar_pico_cercano(picos, frecuencia_objetivo, tolerancia_pct=TOLERANCIA_RODAMIENTO_PCT)

        if pico and (mejor is None or pico["amplitud"] > mejor["amplitud"]):
            mejor = {**pico, "eje": eje}

    return mejor


def _bandas_laterales_detectadas(datos_crudos, frecuencia_muestreo, frecuencia_central, espaciado, frecuencia_maxima):
    """
    Busca picos a frecuencia_central - espaciado y + espaciado (bandas
    laterales moduladas alrededor de una frecuencia de falla - ej.
    BPFI modulado por 1x, BSF modulado por FTF). Devuelve la lista de
    lados donde se encontro un pico (0, 1 o 2 elementos).
    """
    lado_inferior = _mejor_pico_por_eje(
        datos_crudos, frecuencia_muestreo, frecuencia_central - espaciado, frecuencia_maxima
    )
    lado_superior = _mejor_pico_por_eje(
        datos_crudos, frecuencia_muestreo, frecuencia_central + espaciado, frecuencia_maxima
    )
    return [lado for lado in (lado_inferior, lado_superior) if lado is not None]


def _evaluar_bpfo(datos_crudos, frecuencia_muestreo, frecuencia_maxima, frecuencia_objetivo, pesos):
    fundamental = _mejor_pico_por_eje(datos_crudos, frecuencia_muestreo, frecuencia_objetivo, frecuencia_maxima)
    if fundamental is None:
        return None

    armonico = _mejor_pico_por_eje(datos_crudos, frecuencia_muestreo, frecuencia_objetivo * 2, frecuencia_maxima)

    peso_cumplido = pesos["fuerte"]
    peso_evaluable = pesos["fuerte"] * 2
    evidencias = [f"pico significativo en espectro de envolvente en BPFO (eje {fundamental['eje'].upper()})"]

    if armonico is not None:
        peso_cumplido += pesos["fuerte"]
        evidencias.append("armonico de BPFO presente")

    return peso_cumplido, peso_evaluable, evidencias, fundamental["eje"]


def _evaluar_bpfi(datos_crudos, frecuencia_muestreo, frecuencia_maxima, frecuencia_objetivo, fr, pesos):
    fundamental = _mejor_pico_por_eje(datos_crudos, frecuencia_muestreo, frecuencia_objetivo, frecuencia_maxima)
    if fundamental is None:
        return None

    lados = _bandas_laterales_detectadas(datos_crudos, frecuencia_muestreo, frecuencia_objetivo, fr, frecuencia_maxima)
    armonico = _mejor_pico_por_eje(datos_crudos, frecuencia_muestreo, frecuencia_objetivo * 2, frecuencia_maxima)

    peso_cumplido = pesos["fuerte"]
    peso_evaluable = pesos["fuerte"] + pesos["fuerte"] + pesos["moderada"]
    evidencias = [f"pico significativo en espectro de envolvente en BPFI (eje {fundamental['eje'].upper()})"]

    if lados:
        peso_cumplido += pesos["fuerte"]
        evidencias.append(f"bandas laterales separadas 1x alrededor de BPFI ({len(lados)}/2 lados)")
    if armonico is not None:
        peso_cumplido += pesos["moderada"]
        evidencias.append("armonico de BPFI presente")

    return peso_cumplido, peso_evaluable, evidencias, fundamental["eje"]


def _evaluar_bsf(datos_crudos, frecuencia_muestreo, frecuencia_maxima, frecuencia_objetivo, ftf, pesos):
    fundamental = _mejor_pico_por_eje(datos_crudos, frecuencia_muestreo, frecuencia_objetivo, frecuencia_maxima)
    if fundamental is None:
        return None

    lados = _bandas_laterales_detectadas(datos_crudos, frecuencia_muestreo, frecuencia_objetivo, ftf, frecuencia_maxima)

    peso_cumplido = pesos["fuerte"]
    peso_evaluable = pesos["fuerte"] + pesos["moderada"]
    evidencias = [f"pico significativo en espectro de envolvente en BSF (eje {fundamental['eje'].upper()})"]

    if lados:
        peso_cumplido += pesos["moderada"]
        evidencias.append(f"bandas laterales separadas FTF alrededor de BSF ({len(lados)}/2 lados)")

    return peso_cumplido, peso_evaluable, evidencias, fundamental["eje"]


def _evaluar_ftf(datos_crudos, frecuencia_muestreo, frecuencia_maxima, frecuencia_objetivo, pesos):
    fundamental = _mejor_pico_por_eje(datos_crudos, frecuencia_muestreo, frecuencia_objetivo, frecuencia_maxima)
    if fundamental is None:
        return None

    peso_cumplido = pesos["fuerte"]
    peso_evaluable = pesos["fuerte"]
    evidencias = [f"pico significativo en espectro de envolvente en FTF (eje {fundamental['eje'].upper()})"]

    return peso_cumplido, peso_evaluable, evidencias, fundamental["eje"]


def evaluar_rodamiento(datos_crudos, frecuencia_muestreo, rpm_nominal, rodamiento, normativa, frecuencia_maxima=500):
    """
    Devuelve hipotesis de falla de rodamiento (mismo formato que
    evaluar_reglas() en diagnostico.py), o [] si la geometria del
    rodamiento esta incompleta.
    """
    if not geometria_completa(rodamiento):
        return []

    pesos = normativa["motor_diagnostico"]["pesos_evidencia"]
    reglas_yaml = normativa["motor_diagnostico"]["reglas"]
    frecuencias_falla = calcular_frecuencias_falla(rpm_nominal, rodamiento)
    fr = rpm_nominal / 60

    resultados_por_falla = {
        "BPFO": _evaluar_bpfo(datos_crudos, frecuencia_muestreo, frecuencia_maxima, frecuencias_falla["BPFO"], pesos),
        "BPFI": _evaluar_bpfi(datos_crudos, frecuencia_muestreo, frecuencia_maxima, frecuencias_falla["BPFI"], fr, pesos),
        "BSF": _evaluar_bsf(
            datos_crudos, frecuencia_muestreo, frecuencia_maxima, frecuencias_falla["BSF"], frecuencias_falla["FTF"], pesos
        ),
        "FTF": _evaluar_ftf(datos_crudos, frecuencia_muestreo, frecuencia_maxima, frecuencias_falla["FTF"], pesos),
    }

    hipotesis = []
    for codigo_falla, resultado in resultados_por_falla.items():
        if resultado is None:
            continue
        peso_cumplido, peso_evaluable, evidencias, eje = resultado

        score = min(peso_cumplido / peso_evaluable, 1.0)
        if score < 0.30:
            continue

        nombre_regla = NOMBRE_REGLA_POR_FALLA[codigo_falla]
        regla_yaml = reglas_yaml.get(nombre_regla, {})

        hipotesis.append(
            {
                "falla": nombre_regla,
                "confianza": round(score, 2),
                "evidencias": evidencias,
                "recomendacion": regla_yaml.get("recomendacion", []),
                # Eje donde se encontro la evidencia - lo usa
                # calcular_datos_grafico() para saber que eje graficar.
                "eje": eje,
            }
        )

    hipotesis.sort(key=lambda h: h["confianza"], reverse=True)
    return hipotesis


def calcular_datos_grafico(datos_crudos, frecuencia_muestreo, rpm_nominal, rodamiento, hipotesis, frecuencia_maxima=500):
    """
    Arma los datos para graficar el espectro de envolvente (con las 4
    frecuencias de falla marcadas) y, opcionalmente, la señal cruda con
    su curva de envolvente superpuesta - para que la confianza mostrada
    en el reporte se pueda inspeccionar visualmente, no solo como texto.

    Usa el eje de la hipotesis con mayor confianza si hay alguna; si no
    se detecto ninguna, usa el eje con mayor amplitud en el espectro de
    envolvente (para igual poder mostrar el gráfico, aunque no haya
    evidencia de falla que destacar).

    Devuelve None si la geometria del rodamiento esta incompleta.
    """
    if not geometria_completa(rodamiento):
        return None

    frecuencias_falla = calcular_frecuencias_falla(rpm_nominal, rodamiento)

    if hipotesis:
        eje = hipotesis[0]["eje"]
    else:
        eje = None
        mejor_amplitud = -1
        for candidato in EJES:
            columna = f"vibracion_{candidato}"
            if columna not in datos_crudos.columns:
                continue
            _, amplitudes = calcular_espectro_envolvente(
                datos_crudos[columna].to_numpy(), frecuencia_muestreo, frecuencia_maxima
            )
            if len(amplitudes) and amplitudes.max() > mejor_amplitud:
                mejor_amplitud = amplitudes.max()
                eje = candidato
        if eje is None:
            return None

    señal = datos_crudos[f"vibracion_{eje}"].to_numpy()
    frecuencias_espectro, amplitudes_espectro = calcular_espectro_envolvente(
        señal, frecuencia_muestreo, frecuencia_maxima
    )

    tiempo = np.arange(len(señal)) / frecuencia_muestreo
    envolvente_tiempo = calcular_envolvente(señal)

    return {
        "eje": eje,
        "frecuencias_falla": frecuencias_falla,
        # Arreglos numpy sin serializar - pdf_reporte.py los grafica
        # directamente con matplotlib a resolucion completa; la API
        # (reportes.py) los reduce antes de mandarlos como JSON.
        "frecuencias_espectro": frecuencias_espectro,
        "amplitudes_espectro": amplitudes_espectro,
        "tiempo": tiempo,
        "señal": señal,
        "envolvente_tiempo": envolvente_tiempo,
    }


def serializar_datos_grafico(datos_grafico, cantidad_maxima_tiempo=400):
    """
    Version JSON-amigable de calcular_datos_grafico(), para la
    respuesta de la API. El espectro de envolvente se manda completo
    (unos cientos de puntos, liviano); la señal en el tiempo se reduce
    a cantidad_maxima_tiempo puntos distribuidos uniformemente - a
    resolucion completa seria demasiado pesado para mandarlo por red
    sin aportar mas detalle visible en el grafico.
    """
    if datos_grafico is None:
        return None

    tiempo = datos_grafico["tiempo"]
    señal = datos_grafico["señal"]
    envolvente_tiempo = datos_grafico["envolvente_tiempo"]

    if len(tiempo) > cantidad_maxima_tiempo:
        indices = np.linspace(0, len(tiempo) - 1, cantidad_maxima_tiempo).round().astype(int)
    else:
        indices = np.arange(len(tiempo))

    return {
        "eje": datos_grafico["eje"],
        "frecuencias_falla": {
            nombre: round(float(valor), 4) for nombre, valor in datos_grafico["frecuencias_falla"].items()
        },
        "espectro_envolvente": [
            {"frecuencia": round(float(f), 4), "amplitud": round(float(a), 6)}
            for f, a in zip(datos_grafico["frecuencias_espectro"], datos_grafico["amplitudes_espectro"])
        ],
        "señal_tiempo": [
            {
                "t": round(float(tiempo[i]), 6),
                "senal": round(float(señal[i]), 4),
                "envolvente": round(float(envolvente_tiempo[i]), 4),
            }
            for i in indices
        ],
    }
