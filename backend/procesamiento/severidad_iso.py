"""
Clasificacion de severidad global de vibracion segun ISO 20816-3:2022,
usando la tabla de zonas (A/B/C/D) ya curada en
conocimiento/normativa_motorguardian.yaml (severidad_iso_20816_3).

Es un eje de evaluacion DISTINTO y complementario al motor de reglas de
diagnostico.py: ese motor responde "cual es la falla mas probable"; este
modulo responde "que tan grave es la vibracion en terminos absolutos",
independiente de la causa.

Requiere:
    - Velocidad RMS de la señal (mm/s). Si la medicion esta declarada en
      unidades de aceleracion (g, m/s2, cm/s2), se integra en el dominio
      de la frecuencia (V(f) = A(f) / (2*pi*f), omitiendo la componente
      DC - integrar un offset constante da una rampa sin sentido fisico,
      no una velocidad real). Si ya esta en unidades de velocidad (mm/s,
      in/s), se usa directo. Sin una unidad declarada y reconocida, NO
      se clasifica - nunca se asume una unidad por defecto (mismo
      criterio que D-040: "confiar en lo declarado", nunca inventar).
    - potencia_kw del equipo, para elegir el grupo de la tabla (1 o 2).
      La norma tambien permite elegir el grupo por altura de eje, dato
      que el sistema no captura todavia - si la potencia no alcanza para
      decidir el grupo, se declara explicitamente en vez de adivinar.
    - tipo_soporte del equipo ("rigido"/"flexible") - dato nuevo en
      Equipo.atributos, sin el cual no se puede elegir la sub-tabla
      correcta.

Alcance acotado a proposito: no distingue evaluacion "en servicio" vs
"arranque/parada" ni tendencia de cambio respecto a mediciones previas
(ISO 20816-1 tambien contempla eso) - solo clasifica el valor absoluto
de una medicion puntual contra las 4 zonas.
"""

import numpy as np

UNIDADES_VELOCIDAD_A_MM_S = {
    "mm/s": 1.0,
    "in/s": 25.4,
}

UNIDADES_ACELERACION_A_M_S2 = {
    "m/s2": 1.0,
    "cm/s2": 0.01,
    "g": 9.80665,
}


def _resultado_no_aplicable(motivo):
    return {
        "aplicable": False,
        "motivo_no_aplicable": motivo,
        "velocidad_rms_mm_s": None,
        "grupo": None,
        "tipo_soporte": None,
        "zona": None,
        "severidad": None,
        "accion_recomendada": None,
        "edicion_referencia": None,
    }


def calcular_velocidad_rms_mm_s(señal, frecuencia_muestreo, unidad_señal):
    """
    Devuelve la velocidad RMS en mm/s, o None si unidad_señal no es una
    unidad de aceleracion o velocidad reconocida (ver UNIDADES_* arriba).
    """
    señal = np.asarray(señal, dtype=float)

    factor_velocidad = UNIDADES_VELOCIDAD_A_MM_S.get(unidad_señal)
    if factor_velocidad is not None:
        return float(np.sqrt(np.mean(np.square(señal * factor_velocidad))))

    factor_aceleracion = UNIDADES_ACELERACION_A_M_S2.get(unidad_señal)
    if factor_aceleracion is None:
        return None

    aceleracion_m_s2 = señal * factor_aceleracion
    cantidad_muestras = len(aceleracion_m_s2)
    if cantidad_muestras < 2:
        return None

    espectro = np.fft.rfft(aceleracion_m_s2)
    frecuencias = np.fft.rfftfreq(cantidad_muestras, d=1 / frecuencia_muestreo)

    espectro_velocidad = np.zeros_like(espectro)
    distinto_de_cero = frecuencias > 0
    espectro_velocidad[distinto_de_cero] = espectro[distinto_de_cero] / (
        1j * 2 * np.pi * frecuencias[distinto_de_cero]
    )

    velocidad_m_s = np.fft.irfft(espectro_velocidad, n=cantidad_muestras)
    velocidad_mm_s = velocidad_m_s * 1000
    return float(np.sqrt(np.mean(np.square(velocidad_mm_s))))


def _clasificar_grupo(potencia_kw, seleccion_grupo):
    """
    Recorre seleccion_grupo tal como viene del YAML (no se hardcodean
    los umbrales aca) y devuelve el nombre del primer grupo cuyo criterio
    de potencia se cumple. Solo evalua el criterio de potencia - el
    criterio alternativo por altura de eje no se puede evaluar (el
    sistema no captura ese dato todavia).
    """
    for nombre_grupo, definicion in seleccion_grupo.items():
        criterio = definicion["criterio"]
        mayor_que = criterio.get("potencia_kw_mayor_que")
        menor_igual = criterio.get("potencia_kw_menor_igual_que")

        if mayor_que is not None and not (potencia_kw > mayor_que):
            continue
        if menor_igual is not None and not (potencia_kw <= menor_igual):
            continue
        return nombre_grupo

    return None


def _zona_desde_velocidad(velocidad_rms_mm_s, tabla_zonas):
    for letra, rango in tabla_zonas.items():
        minimo = rango["min_inclusivo"]
        maximo = rango["max_exclusivo"]
        if velocidad_rms_mm_s >= minimo and (maximo is None or velocidad_rms_mm_s < maximo):
            return letra
    return None


def clasificar_severidad(señal, frecuencia_muestreo, unidad_señal, potencia_kw, rpm_nominal, tipo_soporte, normativa):
    """
    Clasifica una sola señal (un eje) contra la tabla de ISO 20816-3.
    Ver clasificar_severidad_peor_eje() para evaluar los 3 ejes juntos.
    """
    tabla = normativa["severidad_iso_20816_3"]
    if not tabla.get("habilitado", False):
        return _resultado_no_aplicable("La tabla de severidad ISO 20816-3 está deshabilitada en la normativa curada.")

    condiciones = tabla["condiciones_aplicacion"]

    if potencia_kw is None:
        return _resultado_no_aplicable(
            "Falta la potencia del equipo (Configuración → Equipos) — necesaria para elegir "
            "el grupo de máquina de ISO 20816-3."
        )

    if not (condiciones["potencia_min_kw"] <= potencia_kw <= condiciones["potencia_max_kw"]):
        return _resultado_no_aplicable(
            f"La potencia del equipo ({potencia_kw:.0f} kW) está fuera del rango que cubre "
            f"ISO 20816-3 ({condiciones['potencia_min_kw']:.0f}-{condiciones['potencia_max_kw']:.0f} kW)."
        )

    if rpm_nominal is not None and not (condiciones["rpm_min"] <= rpm_nominal <= condiciones["rpm_max"]):
        return _resultado_no_aplicable(
            f"El RPM nominal del equipo ({rpm_nominal:.0f}) está fuera del rango que cubre "
            f"ISO 20816-3 ({condiciones['rpm_min']:.0f}-{condiciones['rpm_max']:.0f} RPM)."
        )

    if tipo_soporte not in ("rigido", "flexible"):
        return _resultado_no_aplicable(
            "El equipo no tiene declarado su tipo de soporte (rígido/flexible) en "
            "Configuración → Equipos — dato requerido por la tabla ISO 20816-3."
        )

    grupo = _clasificar_grupo(potencia_kw, tabla["seleccion_grupo"])
    if grupo is None:
        return _resultado_no_aplicable(
            f"No fue posible determinar el grupo de máquina (1 o 2) de ISO 20816-3 solo con "
            f"la potencia declarada ({potencia_kw:.0f} kW) — la norma también permite "
            "clasificar por altura de eje, dato que el sistema no captura todavía."
        )

    velocidad_rms = calcular_velocidad_rms_mm_s(señal, frecuencia_muestreo, unidad_señal)
    if velocidad_rms is None:
        return _resultado_no_aplicable(
            f"La unidad de la medición ({unidad_señal or 'no declarada'}) no es una unidad "
            "de aceleración o velocidad reconocida — no se puede calcular la velocidad RMS "
            "que exige ISO 20816-3."
        )

    tabla_zonas = tabla["tablas"][grupo][tipo_soporte]
    zona = _zona_desde_velocidad(velocidad_rms, tabla_zonas)
    significado = tabla["significado_zonas"].get(zona, {})

    return {
        "aplicable": True,
        "motivo_no_aplicable": None,
        "velocidad_rms_mm_s": round(velocidad_rms, 4),
        "grupo": grupo,
        "tipo_soporte": tipo_soporte,
        "zona": zona,
        "severidad": significado.get("severidad"),
        "accion_recomendada": significado.get("accion_default"),
        "edicion_referencia": tabla.get("edicion_referencia"),
    }


def clasificar_severidad_peor_eje(datos_crudos, frecuencia_muestreo, unidad_señal, potencia_kw, rpm_nominal, tipo_soporte, normativa):
    """
    Evalua vibracion_x/y/z y devuelve el resultado del eje con la zona
    mas severa (mismo criterio conservador que el resto del sistema:
    reportar el peor hallazgo, no promediarlo ni ocultarlo). Si ningun
    eje es aplicable, devuelve el motivo del primero (son el mismo
    motivo en la practica, ya que aplicabilidad no depende del eje).
    """
    ORDEN_ZONAS = {"A": 0, "B": 1, "C": 2, "D": 3}

    resultados = []
    for eje in ("x", "y", "z"):
        columna = f"vibracion_{eje}"
        if columna not in datos_crudos.columns:
            continue
        resultado = clasificar_severidad(
            datos_crudos[columna].to_numpy(), frecuencia_muestreo, unidad_señal,
            potencia_kw, rpm_nominal, tipo_soporte, normativa,
        )
        resultados.append({**resultado, "eje": eje})

    if not resultados:
        return _resultado_no_aplicable("No hay ejes de vibración disponibles en la señal.")

    aplicables = [r for r in resultados if r["aplicable"]]
    if not aplicables:
        return resultados[0]

    return max(aplicables, key=lambda r: ORDEN_ZONAS.get(r["zona"], -1))
