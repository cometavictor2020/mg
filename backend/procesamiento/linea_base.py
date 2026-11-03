"""
Linea base (baseline) de un sensor: valores de referencia tomados con el
equipo sano, para saber si una vibracion es ANORMAL y no solo si esta
presente (D-056, ver PROYECTO.md).

El motor de reglas de diagnostico.py solo sabia si habia un pico en 1x/2x/3x.
Una maquina sana con carga ya tiene un 1x apreciable (en los archivos de
prueba del dataset de Kumar et al., 2022, el "sano con polea" tiene 0,23 g en
1x), asi que "hay un pico" no distingue una condicion normal de una falla.
Con una linea base, la evidencia pasa a ser "el pico creció respecto de la
referencia".

Alcance acotado a proposito:
    - Solo cubre la evidencia de 1x/2x/3x (desbalanceo y desalineaciones).
      Las 4 reglas de rodamiento no usan linea base: su evidencia son picos
      del espectro de envolvente en frecuencias que, en un rodamiento sano,
      normalmente no aparecen.
    - La referencia es la amplitud maxima del espectro FFT (no del "pico
      detectado") en una vecindad de cada armonico, para que exista aunque
      el pico de referencia fuera pequeno.
    - La referencia puede armarse con varias mediciones sanas (el maximo por
      armonico y eje, combinar_valores_linea_base): la amplitud de un
      armonico varia entre mediciones sanas mas que el factor de "elevado"
      (x1,25), y con un solo registro esa variacion da falsas alarmas. El
      formato resultante es el mismo, asi que el motor no lo distingue.
    - No separa por rango de RPM ni de carga todavia (el YAML lo preve:
      gestion_condicion.baseline.separar_por); quien marca la referencia
      debe hacerlo con el equipo en condiciones de operacion comparables.

Este modulo no conoce la base de datos ni HTTP: recibe y devuelve datos.
"""

from backend.procesamiento.ejes import ejes_en_datos_fft

ARMONICOS = ("1x", "2x", "3x")
EJES = ("x", "y", "z")


def amplitud_maxima_cerca(frecuencias, amplitudes, frecuencia_objetivo, tolerancia_pct):
    """Amplitud maxima del espectro a +-tolerancia_pct de la frecuencia objetivo (0.0 si no hay bins)."""
    tolerancia = frecuencia_objetivo * tolerancia_pct / 100
    cercanas = [
        amplitud
        for frecuencia, amplitud in zip(frecuencias, amplitudes)
        if abs(frecuencia - frecuencia_objetivo) <= tolerancia
    ]
    return float(max(cercanas)) if cercanas else 0.0


def calcular_valores_linea_base(datos_fft, rpm_nominal, tolerancia_pct):
    """
    datos_fft: lista de {frecuencia, amplitud_x, amplitud_y, amplitud_z}, tal
    como la devuelve frecuencia.py::calcular_fft.

    Devuelve el dict que se guarda en LineaBase.valores.
    """
    frecuencias = [fila["frecuencia"] for fila in datos_fft]
    frecuencia_giro = rpm_nominal / 60

    ejes = ejes_en_datos_fft(datos_fft)  # solo los ejes que el sensor tiene (D-062)
    amplitudes = {}
    for multiplo, armonico in enumerate(ARMONICOS, start=1):
        amplitudes[armonico] = {
            eje: amplitud_maxima_cerca(
                frecuencias,
                [fila[f"amplitud_{eje}"] for fila in datos_fft],
                frecuencia_giro * multiplo,
                tolerancia_pct,
            )
            for eje in ejes
        }

    return {
        "rpm": rpm_nominal,
        "tolerancia_pct": tolerancia_pct,
        "amplitudes": amplitudes,
    }


def _mediana(valores):
    ordenados = sorted(valores)
    medio = len(ordenados) // 2
    return ordenados[medio] if len(ordenados) % 2 else (ordenados[medio - 1] + ordenados[medio]) / 2


def _combinar_velocidad_rms(referencias):
    """
    Maximo por eje de la velocidad RMS de referencia (D-059), si todos los registros la traen y se calcularon
    con la misma banda, frecuencia de muestreo y unidad (si no, el indicador de cambio no seria comparable: None).
    """
    if not all(referencias):
        return None
    primera = referencias[0]
    for otra in referencias[1:]:
        if any(otra.get(clave) != primera.get(clave) for clave in ("banda_hz", "frecuencia_muestreo", "unidad")):
            return None
    ejes = set(primera["por_eje_mm_s"]).intersection(*(set(r["por_eje_mm_s"]) for r in referencias[1:]))
    if not ejes:
        return None
    return {**primera, "por_eje_mm_s": {eje: max(r["por_eje_mm_s"][eje] for r in referencias) for eje in sorted(ejes)}}


def combinar_valores_linea_base(lista_valores, regla="max"):
    """
    Resume varios registros SANOS del mismo sensor en una sola linea base (ver criterios_proyecto.
    linea_base_varios_registros): para cada armonico y eje, la referencia es el maximo de los registros. Devuelve
    el MISMO formato que calcular_valores_linea_base, asi el motor de diagnostico no distingue una linea base de
    un registro de una de varios; solo agrega n_registros y regla_combinacion para mostrarlo.

    Con un solo registro devuelve sus valores sin cambios (mas n_registros = 1): es la linea base de siempre.
    """
    if not lista_valores:
        raise ValueError("Hacen falta al menos un registro para armar la línea base.")
    if regla != "max":
        raise ValueError(f"Regla de combinación no soportada: {regla!r}")

    if len(lista_valores) == 1:
        return {**lista_valores[0], "n_registros": 1, "regla_combinacion": None}

    base = lista_valores[-1]  # el mas reciente aporta rpm de referencia, tolerancia y origen de la velocidad
    ejes = [eje for eje in EJES if all(eje in v["amplitudes"][armonico] for v in lista_valores for armonico in ARMONICOS)]
    amplitudes = {
        armonico: {eje: max(v["amplitudes"][armonico][eje] for v in lista_valores) for eje in ejes}
        for armonico in ARMONICOS
    }

    combinados = {
        **base,
        "rpm": _mediana([v["rpm"] for v in lista_valores]),
        "amplitudes": amplitudes,
        "n_registros": len(lista_valores),
        "regla_combinacion": regla,
    }
    if any("velocidad_rms" in v for v in lista_valores):
        combinados["velocidad_rms"] = _combinar_velocidad_rms([v.get("velocidad_rms") for v in lista_valores])
    return combinados


def evaluar_registros_de_referencia(lista_valores, minimo, factor_atipico, tolerancia_velocidad_pct):
    """
    Avisos (lista de dicts {codigo, mensaje}) sobre los registros con que se arma una linea base. No bloquean:
    quien marca es el que confirma que el equipo estaba sano, esto solo le senala lo que ve en los datos.
        - pocos_registros: menos de `minimo` (la variacion normal entre mediciones sigue sin cubrirse).
        - registro_atipico: un registro cuyo armonico supera factor_atipico veces la mediana de los demas
          (con el maximo, uno solo con falla inflaria la referencia y taparia fallas reales).
        - velocidades_distintas: las rpm de los registros se apartan mas que la tolerancia de los armonicos,
          o sea que no se tomaron en condiciones comparables.
    """
    avisos = []
    cantidad = len(lista_valores)

    if cantidad < minimo:
        avisos.append({
            "codigo": "pocos_registros",
            "mensaje": (
                f"La referencia se armó con {cantidad} registro(s); se recomiendan al menos {minimo}. "
                "Con menos, la variación normal entre mediciones sanas puede leerse como un aumento y dar falsas alarmas."
            ),
        })

    if cantidad >= 3:
        for indice, valores in enumerate(lista_valores):
            otros = lista_valores[:indice] + lista_valores[indice + 1:]
            for armonico in ARMONICOS:
                for eje, amplitud in valores["amplitudes"][armonico].items():
                    mediana_otros = _mediana([o["amplitudes"][armonico].get(eje, 0.0) for o in otros])
                    if mediana_otros > 0 and amplitud >= factor_atipico * mediana_otros:
                        avisos.append({
                            "codigo": "registro_atipico",
                            "mensaje": (
                                f"El registro {indice + 1} de {cantidad} tiene un {armonico} en el eje {eje} "
                                f"{amplitud / mediana_otros:.1f} veces mayor que el de los demás: si el equipo "
                                "tenía una falla en ese registro, la referencia ocultaría fallas reales."
                            ),
                            "registro": indice,
                        })
                        break
                else:
                    continue
                break

    rpms = [v["rpm"] for v in lista_valores]
    mediana_rpm = _mediana(rpms)
    if mediana_rpm and any(abs(rpm - mediana_rpm) / mediana_rpm * 100 > tolerancia_velocidad_pct for rpm in rpms):
        avisos.append({
            "codigo": "velocidades_distintas",
            "mensaje": (
                f"Los registros se tomaron a velocidades distintas ({min(rpms):.0f} a {max(rpms):.0f} r/min): "
                "la referencia mezcla condiciones de operación que no son comparables."
            ),
        })

    return avisos


def factor_aumento_minimo(normativa):
    """
    Cuantas veces la referencia debe superarse para considerar "elevada" una
    amplitud: definicion_cualitativa.elevado.min_ratio_baseline del YAML (el
    mismo criterio cualitativo que el archivo ya definia, sin cifras nuevas).
    """
    return normativa["criterios_proyecto"]["definicion_cualitativa"]["elevado"]["min_ratio_baseline"]


def esta_elevada(amplitud_actual, amplitud_referencia, factor):
    """
    True si amplitud_actual >= factor x amplitud_referencia. Si la referencia
    no trae ese dato (None), no hay con que comparar y se conserva la
    evidencia tal como esta (no se la descarta sin fundamento).
    """
    if amplitud_referencia is None:
        return True
    return amplitud_actual >= factor * amplitud_referencia


def anotar_hallazgos_con_linea_base(hallazgos_armonicos, valores_linea_base, factor):
    """
    hallazgos_armonicos: {"1x": pico_o_None, ...} (diagnostico.py::
    analizar_espectro_fft). Devuelve (anotados, efectivos):
        - anotados: igual que la entrada, pero cada pico trae ademas
          amplitud_linea_base, razon_linea_base y elevado_respecto_linea_base
          (para mostrarlo en el resultado).
        - efectivos: igual, pero con None donde el pico NO supera a la
          referencia - esos armonicos dejan de contar como evidencia.
    """
    amplitudes_referencia = valores_linea_base["amplitudes"]
    anotados = {}
    efectivos = {}

    for armonico, pico in hallazgos_armonicos.items():
        if pico is None:
            anotados[armonico] = None
            efectivos[armonico] = None
            continue

        referencia = amplitudes_referencia.get(armonico, {}).get(pico["eje"])
        elevada = esta_elevada(pico["amplitud"], referencia, factor)
        razon = (pico["amplitud"] / referencia) if referencia else None

        anotado = {
            **pico,
            "amplitud_linea_base": referencia,
            "razon_linea_base": round(razon, 2) if razon is not None else None,
            "elevado_respecto_linea_base": elevada,
        }
        anotados[armonico] = anotado
        efectivos[armonico] = anotado if elevada else None

    return anotados, efectivos
