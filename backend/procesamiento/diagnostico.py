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
    - No se distingue vibracion radial de axial salvo que el sensor
      declare su orientacion por eje (D-051, ver PROYECTO.md) - sin
      ella, se buscan picos en los 3 ejes por igual y desalineacion_angular
      (cuya evidencia mas fuerte es vibracion axial) queda con confianza
      tope acotada. Los umbrales que definen "direccion predominante" /
      "vibracion muy elevada" (configuracion_motor_reglas.
      direccion_radial_axial en el YAML) NO son una cita ISO especifica -
      son practica general de analisis de vibraciones, pendiente de
      validacion (ver R-003 en PROYECTO.md).

Ademas del motor de reglas (que causa), diagnosticar_sensor() tambien
expone dos ejes de evaluacion nuevos (D-050, ver PROYECTO.md), cada uno
en su propio modulo:
    - severidad_iso.py: clasificacion de severidad ISO 20816-3 (zonas
      A/B/C/D) - que tan grave es la vibracion en terminos absolutos,
      independiente de la causa.
    - calidad_medicion.py: chequeo de calidad de la medicion segun ISO
      13373-1 (Nyquist, resolucion de frecuencia) antes de confiar en
      el diagnostico.
"""

from functools import lru_cache
from pathlib import Path

import numpy as np
import yaml
from scipy.signal import find_peaks

from backend.procesamiento.calidad_medicion import evaluar_calidad_medicion
from backend.procesamiento.severidad_iso import clasificar_severidad_peor_eje

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
    "Requiere inspeccion fisica para confirmar cualquier hipotesis.",
]

LIMITACION_SIN_ORIENTACION = (
    "El sensor no tiene declarada la orientación de sus ejes (Configuración → "
    "Sensores): se revisan los 3 ejes por igual, sin distinguir vibración "
    "radial de axial. La desalineación angular depende principalmente de "
    "vibración axial — sin poder aislarla, su confianza queda acotada a 50%."
)

LIMITACION_ORIENTACION_NO_VALIDADA = (
    "La orientación del sensor está declarada y se usó para evaluar "
    "vibración radial vs. axial, pero los umbrales que definen \"dirección "
    "predominante\"/\"vibración muy elevada\" son práctica general de "
    "análisis de vibraciones, no una cita ISO específica — pendientes de "
    "validación (ver R-003 en PROYECTO.md)."
)


@lru_cache
def cargar_normativa():
    with open(RUTA_NORMATIVA, encoding="utf-8") as archivo:
        return yaml.safe_load(archivo)


def detectar_picos(frecuencias, amplitudes):
    """
    Picos con prominencia y relacion senal/ruido minimas, leidas de
    configuracion_motor_reglas.deteccion_picos (YAML) - antes eran
    literales (0.05/3.0) hardcodeados aca que por coincidencia ya
    calzaban con el YAML pero nunca lo leian; ahora el YAML es la unica
    fuente de verdad.
    """
    amplitudes = np.array(amplitudes)

    if len(amplitudes) == 0 or amplitudes.max() <= 0:
        return []

    parametros = cargar_normativa()["configuracion_motor_reglas"]["deteccion_picos"]
    prominencia_minima = parametros["prominencia_minima_relativa"] * amplitudes.max()
    indices, _ = find_peaks(amplitudes, prominence=prominencia_minima)

    ruido = np.median(amplitudes) or 1e-9
    relacion_minima = parametros["relacion_sobre_ruido_minima"]

    return [
        {"frecuencia": float(frecuencias[i]), "amplitud": float(amplitudes[i])}
        for i in indices
        if amplitudes[i] / ruido >= relacion_minima
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

    Devuelve (resultado, picos_por_eje):
        - resultado: por armonico (1x/2x/3x), el mejor pico encontrado
          en cualquiera de los 3 ejes (y en cual).
        - picos_por_eje: todos los picos detectados en cada eje, sin
          reducir al "mejor" - lo necesita evaluar_direccion() (D-051)
          para comparar radial vs. axial eje por eje, no solo el eje
          ganador.
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

    return resultado, picos_por_eje


def evaluar_direccion(picos_por_eje, frecuencia_objetivo, orientacion_ejes, normativa):
    """
    Compara la amplitud del mejor pico en los ejes radiales vs. el eje
    axial, en frecuencia_objetivo, usando la orientacion declarada del
    sensor (D-051, ver PROYECTO.md).

    Devuelve None si no hay orientacion declarada, o si falta al menos
    un eje radial (horizontal o vertical) Y el eje axial - sin ambos
    lados no hay nada que comparar.

    Los umbrales que definen "predominante"/"muy_elevada" (config en
    configuracion_motor_reglas.direccion_radial_axial, YAML) NO son una
    cita ISO especifica - son practica general de analisis de
    vibraciones, pendiente de validacion (ver R-003 en PROYECTO.md).
    """
    if not orientacion_ejes:
        return None

    ejes_radiales = [e for e, o in orientacion_ejes.items() if o in ("radial_horizontal", "radial_vertical")]
    ejes_axiales = [e for e, o in orientacion_ejes.items() if o == "axial"]

    if not ejes_radiales or not ejes_axiales:
        return None

    def _mejor_amplitud(ejes):
        mejor = 0.0
        for eje in ejes:
            pico = buscar_pico_cercano(picos_por_eje.get(eje, []), frecuencia_objetivo)
            if pico and pico["amplitud"] > mejor:
                mejor = pico["amplitud"]
        return mejor

    amplitud_radial = _mejor_amplitud(ejes_radiales)
    amplitud_axial = _mejor_amplitud(ejes_axiales)

    parametros = normativa["configuracion_motor_reglas"]["direccion_radial_axial"]
    ratio_predominante = parametros["ratio_minimo_radial_sobre_axial_para_predominante"]
    ratio_muy_elevada = parametros["ratio_minimo_axial_sobre_radial_para_muy_elevada"]

    return {
        "amplitud_radial": amplitud_radial,
        "amplitud_axial": amplitud_axial,
        "radial_elevada": amplitud_radial > 0,
        "axial_elevada": amplitud_axial > 0,
        "radial_predominante": amplitud_radial > 0 and (
            amplitud_axial == 0 or amplitud_radial / amplitud_axial >= ratio_predominante
        ),
        "axial_muy_elevada": amplitud_axial > 0 and (
            amplitud_radial == 0 or amplitud_axial / amplitud_radial >= ratio_muy_elevada
        ),
    }


def evaluar_reglas(hallazgos_armonicos, normativa, frecuencias_objetivo, picos_por_eje=None, orientacion_ejes=None):
    """
    hallazgos_armonicos: {"1x": pico_o_None, "2x": ..., "3x": ...}
    frecuencias_objetivo: {"1x": Hz, "2x": Hz, "3x": Hz} (frecuencias_esperadas()).
    picos_por_eje/orientacion_ejes: opcionales (D-051) - si ambos estan
    disponibles, se evalua tambien la evidencia de direccion
    (radial/axial) que el YAML ya definia para estas 3 reglas pero que
    antes no se usaba (ver evaluar_direccion()).

    Evalua las 3 reglas soportadas con un subconjunto reducido de su
    evidencia (ver docstring del modulo) y devuelve las hipotesis con
    confianza >= 0.30, ordenadas de mayor a menor, maximo 3 (mismos
    criterios que confianza_diagnostico.reglas_salida en el YAML).
    """
    pesos = normativa["motor_diagnostico"]["pesos_evidencia"]
    reglas_yaml = normativa["motor_diagnostico"]["reglas"]

    presente_1x = hallazgos_armonicos["1x"] is not None
    presente_2x = hallazgos_armonicos["2x"] is not None

    direccion_1x = None
    direccion_2x = None
    if picos_por_eje is not None:
        direccion_1x = evaluar_direccion(picos_por_eje, frecuencias_objetivo["1x"], orientacion_ejes, normativa)
        direccion_2x = evaluar_direccion(picos_por_eje, frecuencias_objetivo["2x"], orientacion_ejes, normativa)

    # --- desbalanceo: amplitud_1x (fuerte) + direccion_radial predominante
    # (moderada) - evidencias_en_contra: vibracion_axial muy_elevada (peso
    # en_contra, negativo - resta en vez de solo topear).
    peso_cumplido_deseq = pesos["fuerte"] if presente_1x else 0
    peso_evaluable_deseq = pesos["fuerte"]
    evidencias_deseq = ["pico significativo en 1x"] if presente_1x else []
    if direccion_1x is not None:
        peso_evaluable_deseq += pesos["moderada"]
        if direccion_1x["radial_predominante"]:
            peso_cumplido_deseq += pesos["moderada"]
            evidencias_deseq.append("vibración predominantemente radial en 1x")
        if direccion_1x["axial_muy_elevada"]:
            peso_cumplido_deseq += pesos["en_contra"]
            evidencias_deseq.append("evidencia en contra: vibración axial muy elevada en 1x")

    # --- desalineacion_paralela: amplitud_2x (fuerte) + amplitud_1x
    # presente (moderada) + vibracion_radial elevada en 2x (moderada).
    peso_cumplido_par = (
        (pesos["fuerte"] if presente_2x else 0)
        + (pesos["moderada"] if presente_1x else 0)
    )
    peso_evaluable_par = pesos["fuerte"] + pesos["moderada"]
    evidencias_par = (
        (["pico significativo en 2x"] if presente_2x else [])
        + (["pico significativo en 1x"] if presente_1x else [])
    )
    if direccion_2x is not None:
        peso_evaluable_par += pesos["moderada"]
        if direccion_2x["radial_elevada"]:
            peso_cumplido_par += pesos["moderada"]
            evidencias_par.append("vibración radial elevada en 2x")

    # --- desalineacion_angular: amplitud_1x (moderada) + amplitud_2x
    # (moderada) + vibracion_axial elevada en 1x (fuerte - su evidencia
    # mas fuerte). Sin orientacion declarada, esa evidencia no se puede
    # evaluar y el tope de confianza queda acotado a 0.50 (mismo
    # criterio que las restricciones de confianza_diagnostico del YAML);
    # con orientacion declarada, el tope sube a 1.0.
    peso_cumplido_ang = (
        (pesos["moderada"] if presente_1x else 0)
        + (pesos["moderada"] if presente_2x else 0)
    )
    peso_evaluable_ang = pesos["moderada"] * 2
    evidencias_ang = (
        (["pico significativo en 1x"] if presente_1x else [])
        + (["pico significativo en 2x"] if presente_2x else [])
    )
    tope_confianza_ang = 0.50
    if direccion_1x is not None:
        peso_evaluable_ang += pesos["fuerte"]
        tope_confianza_ang = 1.0
        if direccion_1x["axial_elevada"]:
            peso_cumplido_ang += pesos["fuerte"]
            evidencias_ang.append("vibración axial elevada en 1x")

    definiciones = [
        {
            "falla": "desbalanceo",
            "peso_cumplido": peso_cumplido_deseq,
            "peso_evaluable": peso_evaluable_deseq,
            "evidencias": evidencias_deseq,
            "tope_confianza": 1.0,
        },
        {
            "falla": "desalineacion_paralela",
            "peso_cumplido": peso_cumplido_par,
            "peso_evaluable": peso_evaluable_par,
            "evidencias": evidencias_par,
            "tope_confianza": 1.0,
        },
        {
            "falla": "desalineacion_angular",
            "peso_cumplido": peso_cumplido_ang,
            "peso_evaluable": peso_evaluable_ang,
            "evidencias": evidencias_ang,
            "tope_confianza": tope_confianza_ang,
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


def limite_confianza_por_condicion(condicion, normativa):
    """
    Busca en confianza_diagnostico.restricciones (YAML) el limite de
    confianza para una condicion puntual (ej. "calidad_medicion ==
    invalida"). Devuelve (confianza_maxima, fallas_afectadas) o None si
    no hay ninguna restriccion con esa condicion - fallas_afectadas es
    None cuando la restriccion aplica a todas las fallas (no trae
    "afecta" en el YAML).
    """
    for restriccion in normativa["confianza_diagnostico"]["restricciones"]:
        if restriccion["condicion"] == condicion:
            return restriccion["confianza_maxima"], restriccion.get("afecta")
    return None


def aplicar_restriccion_confianza(hipotesis, condicion, normativa, umbral_minimo=0.30):
    """
    Acota la confianza de las hipotesis afectadas por una condicion de
    confianza_diagnostico.restricciones (YAML) al confianza_maxima que
    define, y vuelve a filtrar por el umbral minimo de hipotesis.py
    (0.30) - una hipotesis acotada por debajo de ese umbral deja de
    mostrarse, en vez de mostrarse con una confianza que ya no refleja
    evidencia real (ej. calidad_medicion invalida -> confianza_maxima
    0.0 -> la hipotesis desaparece).
    """
    limite = limite_confianza_por_condicion(condicion, normativa)
    if limite is None:
        return hipotesis

    confianza_maxima, fallas_afectadas = limite
    acotadas = []
    for h in hipotesis:
        if fallas_afectadas is None or h["falla"] in fallas_afectadas:
            h = {**h, "confianza": round(min(h["confianza"], confianza_maxima), 2)}
        acotadas.append(h)

    return [h for h in acotadas if h["confianza"] >= umbral_minimo]


def diagnosticar_sensor(
    datos_fft,
    rpm_nominal,
    datos_crudos=None,
    frecuencia_muestreo=None,
    rodamiento=None,
    potencia_kw=None,
    tipo_soporte=None,
    unidad_señal=None,
    orientacion_ejes=None,
):
    """
    datos_crudos, frecuencia_muestreo y rodamiento son opcionales: solo
    hace falta pasarlos cuando el sensor tiene un Rodamiento vinculado
    (D-038) y se quiere evaluar tambien sus 4 reglas de falla
    (backend/procesamiento/rodamientos.py) - a diferencia de 1x/2x/3x,
    esas reglas necesitan la señal cruda en el tiempo, no solo la FFT
    ya calculada, porque trabajan sobre el espectro de envolvente.

    potencia_kw, tipo_soporte y unidad_señal son opcionales tambien:
    alimentan la clasificacion de severidad ISO 20816-3 (D-050, ver
    PROYECTO.md) - un eje de evaluacion distinto al de las hipotesis de
    falla, que responde "que tan grave es la vibracion en terminos
    absolutos" en vez de "cual es la causa mas probable". Sin ellos (o
    si no se reconoce la unidad declarada), severidad_iso queda con
    aplicable=False y un motivo explicito, nunca se asume un valor.

    orientacion_ejes es opcional tambien (D-051, ver PROYECTO.md):
    {"x": "radial_horizontal", ...} segun Sensor.configuracion. Sin
    ella, el motor sigue funcionando exactamente igual que antes de
    D-051 (mismo tope de confianza 0.50 en desalineacion angular).
    """
    normativa = cargar_normativa()
    hallazgos, picos_por_eje = analizar_espectro_fft(datos_fft, rpm_nominal)
    hipotesis = evaluar_reglas(
        hallazgos, normativa, frecuencias_esperadas(rpm_nominal), picos_por_eje, orientacion_ejes
    )
    limitaciones = list(LIMITACIONES)
    limitaciones.append(
        LIMITACION_ORIENTACION_NO_VALIDADA if orientacion_ejes else LIMITACION_SIN_ORIENTACION
    )
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
            NOMBRES_CAMPO_GEOMETRIA = {
                "numero_elementos_rodantes": "número de elementos rodantes",
                "diametro_elemento_mm": "diámetro del elemento rodante",
                "diametro_paso_mm": "diámetro de paso",
                "angulo_contacto_grados": "ángulo de contacto",
            }
            campos_faltantes = [
                etiqueta
                for campo, etiqueta in NOMBRES_CAMPO_GEOMETRIA.items()
                if getattr(rodamiento, campo) is None
            ]
            limitaciones.append(
                f"No se pudo calcular el espectro de envolvente (Hilbert) ni las frecuencias "
                f"de falla (BPFO/BPFI/BSF/FTF) del rodamiento {rodamiento.codigo}: falta su "
                + ", ".join(campos_faltantes)
                + " (Configuración → Rodamientos)."
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

    severidad_iso = None
    calidad_medicion = None
    if datos_crudos is not None and frecuencia_muestreo:
        severidad_iso = clasificar_severidad_peor_eje(
            datos_crudos, frecuencia_muestreo, unidad_señal, potencia_kw, rpm_nominal, tipo_soporte, normativa
        )

        frecuencia_rotacion_hz = rpm_nominal / 60 if rpm_nominal else None
        frecuencia_maxima_interes = frecuencia_rotacion_hz * 3 if frecuencia_rotacion_hz else 0
        if frecuencias_falla_rodamiento:
            frecuencia_maxima_interes = max(
                frecuencia_maxima_interes, max(frecuencias_falla_rodamiento.values()) * 2
            )

        calidad_medicion = evaluar_calidad_medicion(
            frecuencia_muestreo,
            len(datos_crudos) / frecuencia_muestreo,
            frecuencia_maxima_interes,
            frecuencia_rotacion_hz,
            normativa,
        )

        # Bloqueo real (no un simple aviso): confianza_diagnostico.
        # restricciones (YAML) define que una calidad de medicion
        # invalida acota la confianza de TODAS las hipotesis a 0.0 - por
        # debajo del umbral minimo (0.30), asi que ninguna sobrevive.
        # "insuficiente" (mas leve, tope 0.30) hoy nunca lo produce
        # calidad_medicion.py - queda listo para cuando se defina esa
        # condicion.
        if calidad_medicion["estado"] in ("invalida", "insuficiente"):
            hipotesis = aplicar_restriccion_confianza(
                hipotesis, f"calidad_medicion == {calidad_medicion['estado']}", normativa
            )
            mensajes = calidad_medicion["criticas"] + calidad_medicion["advertencias"]
            limitaciones.append(
                "Diagnóstico de causa no disponible — calidad de medición insuficiente "
                "(ISO 13373-1): " + " ".join(mensajes)
                if calidad_medicion["estado"] == "invalida"
                else "Confianza del diagnóstico acotada — calidad de medición con reservas "
                "(ISO 13373-1): " + " ".join(mensajes)
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
        "severidad_iso": severidad_iso,
        "calidad_medicion": calidad_medicion,
    }
