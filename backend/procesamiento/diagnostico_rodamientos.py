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

Las evidencias de cada regla (y su peso) se leen del YAML: la entrada
`espectro_envolvente_*` es la linea fundamental, `armonicos_*` el segundo
armonico y `bandas_laterales_*` las bandas laterales (separadas 1x
alrededor de BPFI, FTF alrededor de BSF). La kurtosis no se evalua.

Como se decide cada evidencia y cuando se descarta una hipotesis (D-065):

    0. Banda de demodulacion: no se demodula la señal completa sino la banda
       de resonancia cuyo espectro de envolvente tiene las lineas mas marcadas
       (envolvente.py), para que los armonicos del eje y la red electrica no
       dominen la envolvente.
    1. Linea significativa: un maximo local cuya amplitud supera el piso de
       ruido LOCAL con una probabilidad de falsa alarma explicita
       (lineas_espectrales.py), en vez de un umbral fijo relativo al
       maximo del espectro.
    2. Una hipotesis se evalua en cada eje por separado y se queda con el
       mejor: sus lineas deben estar en el MISMO eje (mezclar el mejor
       pico de cada eje encontraba coincidencias que ningun eje tenia).
    3. Coherencia: el armonico y las bandas laterales se buscan a partir de
       la frecuencia en que SE DETECTO la fundamental, no de la teorica. La
       desviacion (deslizamiento, error de velocidad) es la misma para toda
       la familia; un "armonico" fuera de esa posicion es otra cosa.
    4. Competencia: las hipotesis se ordenan por confianza y, a igualdad,
       por la fuerza de su evidencia (suma de r^2 = bits de sorpresa de sus
       lineas). Una linea que ya explica una hipotesis aceptada (por ser su
       armonico o banda lateral) deja de contar como evidencia de las
       siguientes; si una hipotesis se queda sin evidencia propia se
       descarta y se avisa en las limitaciones del reporte.

Alcance actual, deliberadamente acotado (ver LIMITACIONES_RODAMIENTO,
que se agrega a las limitaciones generales del reporte cuando aplica):
    - No se evalua kurtosis (evidencia moderada adicional de BPFO en el
      YAML) - mas compleja de calcular con una base fiable todavia.
"""

import numpy as np

from backend.procesamiento.diagnostico import cargar_normativa
from backend.procesamiento.ejes import ejes_en_columnas
from backend.procesamiento.envolvente import aislar_banda_resonancia, calcular_envolvente, calcular_espectro_envolvente
from backend.procesamiento.lineas_espectrales import EspectroLineas

EJES = ["x", "y", "z"]

# Valores por defecto de las tolerancias del YAML (criterios_proyecto.tolerancias),
# usados solo si el YAML no las trae; pso_envolvente.py usa la misma tolerancia.
TOLERANCIA_RODAMIENTO_PCT = 2.0
TOLERANCIA_BANDA_LATERAL_PCT = 3.0

UMBRAL_DESCARTE = 0.30  # igual que diagnostico.py: por debajo no se muestra la hipotesis
BINS_MINIMOS_VENTANA = 2  # una ventana de busqueda nunca es mas angosta que +-2 bins
SEPARACION_MINIMA_BANDAS_BINS = 4  # bandas laterales mas juntas que esto no se distinguen de la linea central
FRACCION_PLATEAU_VELOCIDAD = 0.9  # candidatas con al menos esta fraccion de la fuerza maxima forman el plateau de la velocidad
FACTOR_FRECUENCIA_MAXIMA = 3  # el espectro de envolvente llega, como minimo, a 3 veces la mayor frecuencia de falla
DURACION_GRAFICO_TIEMPO_S = 0.1  # tramo inicial de la señal filtrada y su envolvente que se grafica en el tiempo

NOMBRE_REGLA_POR_FALLA = {
    "BPFO": "rodamiento_pista_exterior",
    "BPFI": "rodamiento_pista_interior",
    "BSF": "rodamiento_elemento_rodante",
    "FTF": "rodamiento_jaula",
}

NOMBRE_LEGIBLE = {
    "BPFO": "pista exterior (BPFO)",
    "BPFI": "pista interior (BPFI)",
    "BSF": "elemento rodante (BSF)",
    "FTF": "jaula (FTF)",
}

# Prefijo de la entrada `feature` del YAML -> papel de esa evidencia.
ROL_POR_PREFIJO = (
    ("espectro_envolvente", "fundamental"),
    ("armonicos", "armonico"),
    ("bandas_laterales", "laterales"),
)

# Lineas que cada falla produce en el espectro de envolvente, para decidir si una linea ya esta explicada por
# otra hipotesis (no para exigirlas todas como evidencia): `armonicos` multiplos de la frecuencia de falla,
# `bandas` bandas laterales a cada lado de cada armonico y `modulacion` multiplos de la frecuencia que modula
# los impactos (1x en pista interior, FTF en elemento rodante), que aparecen solos en el espectro de envolvente.
# La jaula (FTF ~ 0.4x) genera un peine denso que cubre todo el espectro: por la geometria BPFO = N x FTF, de
# modo que una falla de jaula siempre deja una linea sobre BPFO.
MODELO_DE_LINEAS = {
    "BPFO": {"armonicos": 4, "bandas": 0, "modulacion": 0},
    "BPFI": {"armonicos": 3, "bandas": 2, "modulacion": 2},
    "BSF": {"armonicos": 2, "bandas": 2, "modulacion": 2},
    "FTF": {"armonicos": 60, "bandas": 0, "modulacion": 0},
}

LIMITACIONES_RODAMIENTO = [
    "La banda de resonancia que se demodula se elige sola, por la curtosis de su espectro "
    "de envolvente: si la señal no tiene impactos (rodamiento sano) la banda elegida no "
    "significa nada, y si hay otra fuente periodica en alta frecuencia (engrane, aspas) "
    "puede elegir esa banda en vez de la del rodamiento.",
    "No se evalua kurtosis (evidencia adicional de pista exterior que la normativa "
    "tambien define) - requiere una base de comparacion que todavia no existe.",
    "Una linea del espectro de envolvente cuenta como evidencia cuando supera el ruido "
    "local con la probabilidad de falsa alarma configurada en el archivo de conocimiento. "
    "Una linea ajena al rodamiento (red eléctrica, otros componentes de la máquina) que "
    "caiga justo sobre una frecuencia de falla puede cumplir ese criterio: por eso el "
    "armónico y las bandas laterales deben ser coherentes con la línea detectada.",
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


def _espectro_demodulado(señal, frecuencia_muestreo, frecuencias_falla, frecuencia_maxima, parametros):
    """
    Espectro de envolvente de la banda de resonancia de `señal` (envolvente.py::aislar_banda_resonancia), con la
    banda empezando sobre `factor_banda_minima` veces la mayor frecuencia de falla y de ancho no menor a
    `factor_ancho_banda_minimo` veces esa frecuencia. Devuelve
    (señal filtrada, banda o None, frecuencias, amplitudes).
    """
    mayor_frecuencia_falla = max(frecuencias_falla.values())
    filtrada, banda = aislar_banda_resonancia(
        señal,
        frecuencia_muestreo,
        parametros["factor_banda_minima"] * mayor_frecuencia_falla,
        parametros["factor_ancho_banda_minimo"] * mayor_frecuencia_falla,
        frecuencia_maxima,
    )
    frecuencias, amplitudes = calcular_espectro_envolvente(filtrada, frecuencia_muestreo, frecuencia_maxima)
    return filtrada, banda, frecuencias, amplitudes


def _roles_de_regla(regla_yaml, pesos):
    """{papel: peso} de las evidencias de la regla que este modulo sabe evaluar (la kurtosis queda fuera)."""
    roles = {}
    for evidencia in regla_yaml.get("evidencias", []):
        for prefijo, rol in ROL_POR_PREFIJO:
            if evidencia["feature"].startswith(prefijo):
                roles[rol] = pesos[evidencia["peso"]]
    return roles


def _linea(identificador, rol, hallazgo, eje):
    return {"id": identificador, "rol": rol, "eje": eje, **hallazgo}


def _evaluar_en_eje(espectro, eje, f_nominal, espaciado, roles, tolerancias, parametros):
    """
    Evidencias de una falla en el espectro de envolvente de un eje. Devuelve
    {"evaluables": [roles que se podian evaluar], "lineas": {rol: [linea, ...]}, "escala": f_detectada/f_nominal
    o None si no se detecto la fundamental}.
    """
    resolucion = espectro.resolucion
    evaluables, lineas, escala = [], {}, None

    # Fundamental: unica busqueda anclada en la frecuencia teorica, con la tolerancia del YAML.
    if "fundamental" in roles:
        semiancho = espectro.semiancho_hz(f_nominal, tolerancias["rodamientos"], BINS_MINIMOS_VENTANA)
        if espectro.evaluable(f_nominal, semiancho):
            evaluables.append("fundamental")
            fundamental = espectro.buscar_linea(f_nominal, semiancho)
            if fundamental is not None:
                lineas["fundamental"] = [_linea("fundamental", "fundamental", fundamental, eje)]
                escala = fundamental["frecuencia"] / f_nominal

    # Sin fundamental no hay hipotesis: un armonico suelto, sin la linea que lo ancla, es la evidencia mas
    # facil de que sea coincidencia (mismo criterio que antes de D-065).
    if "fundamental" in roles and escala is None:
        return {"eje": eje, "evaluables": [], "lineas": {}, "escala": None}

    # Armonico: a 2x la frecuencia DETECTADA (coherencia).
    if "armonico" in roles:
        centro = 2 * f_nominal * escala
        semiancho = max(parametros["coherencia_armonicos_pct"] / 100 * centro, parametros["coherencia_minima_bins"] * resolucion)
        if espectro.evaluable(centro, semiancho):
            evaluables.append("armonico")
            armonico = espectro.buscar_linea(centro, semiancho)
            if armonico is not None:
                lineas["armonico"] = [_linea("armonico", "armonico", armonico, eje)]

    # Bandas laterales: a +-espaciado de la fundamental detectada.
    if "laterales" in roles and espaciado and espaciado > SEPARACION_MINIMA_BANDAS_BINS * resolucion:
        semiancho = max(tolerancias["banda_lateral"] / 100 * espaciado, BINS_MINIMOS_VENTANA * resolucion)
        centro_banda = lineas["fundamental"][0]["frecuencia"] if "fundamental" in lineas else f_nominal
        if espectro.evaluable(centro_banda - espaciado, semiancho) and espectro.evaluable(centro_banda + espaciado, semiancho):
            evaluables.append("laterales")
            if "fundamental" in lineas:
                lados = []
                for signo, nombre in ((-1, "inferior"), (1, "superior")):
                    hallazgo = espectro.buscar_linea(centro_banda + signo * espaciado, semiancho)
                    if hallazgo is not None:
                        lados.append(_linea(f"laterales:{nombre}", "laterales", hallazgo, eje))
                if lados:
                    lineas["laterales"] = lados

    return {"eje": eje, "evaluables": evaluables, "lineas": lineas, "escala": escala}


def _puntuar(resultado, roles, explicadas=frozenset()):
    """(peso cumplido, peso evaluable, fuerza) del resultado de un eje, sin contar las lineas `explicadas`."""
    cumplido = evaluable = fuerza = 0.0
    for rol in resultado["evaluables"]:
        evaluable += roles[rol]
        vigentes = [l for l in resultado["lineas"].get(rol, []) if l["id"] not in explicadas]
        if vigentes:
            cumplido += roles[rol]
            fuerza += sum(l["razon"] ** 2 for l in vigentes)
    return cumplido, evaluable, fuerza


def _confianza(cumplido, evaluable):
    return min(cumplido / evaluable, 1.0) if evaluable else 0.0


def _lineas_modeladas(codigo, f_nominal, escala, espaciado):
    """Frecuencias (Hz) que la falla `codigo` produce en el espectro de envolvente: armonicos y bandas laterales."""
    modelo = MODELO_DE_LINEAS[codigo]
    base = f_nominal * (escala if escala is not None else 1.0)
    lineas = []
    for k in range(1, modelo["armonicos"] + 1):
        centro = k * base
        lineas.append(centro)
        if espaciado:
            for m in range(1, modelo["bandas"] + 1):
                lineas += [centro - m * espaciado, centro + m * espaciado]
    if espaciado:
        lineas += [m * espaciado for m in range(1, modelo["modulacion"] + 1)]
    return [l for l in lineas if l > 0]


def _esta_explicada(frecuencia, lineas_modeladas, resolucion, parametros):
    margen = max(parametros["coincidencia_lineas_bins"] * resolucion, parametros["coincidencia_lineas_pct"] / 100 * frecuencia)
    return any(abs(frecuencia - modelada) <= margen for modelada in lineas_modeladas)


def _texto_evidencia(rol, codigo, resultado, explicadas):
    lineas = [l for l in resultado["lineas"].get(rol, []) if l["id"] not in explicadas]
    if not lineas:
        return None
    eje = resultado["eje"].upper()
    if rol == "fundamental":
        l = lineas[0]
        return f"pico significativo en espectro de envolvente en {codigo} (eje {eje}, {l['frecuencia']:.1f} Hz, {l['razon']:.0f} veces el ruido local)"
    if rol == "armonico":
        l = lineas[0]
        return f"armonico de {codigo} presente ({l['frecuencia']:.1f} Hz, coherente con la linea detectada)"
    separacion = "1x" if codigo == "BPFI" else "FTF"
    return f"bandas laterales separadas {separacion} alrededor de {codigo} ({len(lineas)}/2 lados)"


def _fuerza_propia(codigo, candidatos, espectros, parametros):
    """
    Fuerza (suma de r^2) de las lineas de `codigo` que NO coinciden con lo que modela otra falla candidata. Una
    linea que dos hipotesis pueden reclamar (p. ej. el tercer armonico de BPFO cae sobre el segundo de BPFI) no
    prueba a ninguna de las dos, pero con la fuerza total inflaba la de la que la reclamaba. La jaula no cuenta
    como "otra": su peine de armonicos cubre todo el espectro y dejaria sin fuerza propia a las demas.
    """
    c = candidatos[codigo]
    resolucion = espectros[c["resultado"]["eje"]].resolucion
    compartidas = {
        linea["id"]
        for lineas in c["resultado"]["lineas"].values()
        for linea in lineas
        if any(
            _esta_explicada(linea["frecuencia"], otro["modeladas"], resolucion, parametros)
            for otro_codigo, otro in candidatos.items()
            if otro_codigo not in (codigo, "FTF")
        )
    }
    return _puntuar(c["resultado"], c["roles"], compartidas)[2]


def _competir(candidatos, espectros, parametros, competencia):
    """
    Explicacion exclusiva de lineas entre hipotesis (ver docstring del modulo, punto 4). `candidatos` es
    {codigo: dict con resultado, roles, f_nominal, espaciado}; `competencia` son los criterios de
    criterios_proyecto.competencia_rodamientos. Devuelve (aceptadas en orden, notas).
    """
    claves = {}
    for codigo, c in candidatos.items():
        cumplido, evaluable, _ = _puntuar(c["resultado"], c["roles"])
        claves[codigo] = (round(_confianza(cumplido, evaluable), 4), _fuerza_propia(codigo, candidatos, espectros, parametros))

    aceptadas, notas = [], []
    for codigo in sorted(candidatos, key=claves.get, reverse=True):
        c = candidatos[codigo]
        resolucion = espectros[c["resultado"]["eje"]].resolucion

        explicadas, culpables = set(), {}
        for rol, lineas in c["resultado"]["lineas"].items():
            for linea in lineas:
                for anterior in aceptadas:
                    if _esta_explicada(linea["frecuencia"], candidatos[anterior]["modeladas"], resolucion, parametros):
                        explicadas.add(linea["id"])
                        culpables.setdefault(anterior, []).append(linea["frecuencia"])
                        break

        cumplido, evaluable, fuerza = _puntuar(c["resultado"], c["roles"], explicadas)
        confianza = _confianza(cumplido, evaluable)
        if explicadas:
            detalle = "; ".join(
                f"{NOMBRE_LEGIBLE[a]}: {', '.join(f'{f:.1f}' for f in sorted(fs))} Hz" for a, fs in culpables.items()
            )
            if confianza < UMBRAL_DESCARTE:
                notas.append(
                    f"Se descartó la hipótesis de {NOMBRE_LEGIBLE[codigo]}: sus líneas en el espectro de envolvente "
                    f"coinciden con armónicos o bandas laterales que ya explica otra falla ({detalle}). Con esta "
                    "geometría y velocidad no se pueden distinguir solo con esta medición."
                )
                continue
            notas.append(
                f"Parte de la evidencia de {NOMBRE_LEGIBLE[codigo]} no se contó porque coincide con líneas que ya "
                f"explica otra falla ({detalle})."
            )

        if confianza < UMBRAL_DESCARTE:
            continue

        # El criterio de significancia de cada linea supone ruido blanco; en una señal real, el piso de baja
        # frecuencia tiene combs de armonicos del eje y la red que lo incumplen, y un rodamiento SANO puede dar
        # dos lineas apenas sobre el umbral que sumadas parecen una falla. Una falla de verdad tiene al menos una
        # linea que supera con holgura el piso local.
        minima = competencia["razon_minima_linea_mas_fuerte"]
        vigentes = [l["razon"] for lineas in c["resultado"]["lineas"].values() for l in lineas if l["id"] not in explicadas]
        if vigentes and max(vigentes) < minima:
            notas.append(
                f"Se descartó la hipótesis de {NOMBRE_LEGIBLE[codigo]}: su línea más fuerte supera el ruido local solo "
                f"{max(vigentes):.1f} veces (se exige al menos {minima:g}); con una evidencia tan débil no se distingue "
                "de la variación normal de un rodamiento sano."
            )
            continue

        # Una falla intensa deja lineas secundarias (modulaciones, intermodulacion) que caen por casualidad sobre
        # otras frecuencias de falla: sin evidencia propia comparable, la otra hipotesis no se distingue de ellas.
        if aceptadas:
            dominante = aceptadas[0]
            fraccion = competencia["fuerza_minima_respecto_dominante"]
            if fuerza < fraccion * candidatos[dominante]["fuerza"]:
                notas.append(
                    f"Se descartó la hipótesis de {NOMBRE_LEGIBLE[codigo]}: su evidencia propia es menos del "
                    f"{fraccion * 100:.0f} % de la de {NOMBRE_LEGIBLE[dominante]}, la falla dominante, y no se distingue "
                    "de las líneas secundarias que esa falla deja en el espectro de envolvente."
                )
                continue

        c["explicadas"], c["cumplido"], c["evaluable"], c["fuerza"], c["confianza"] = explicadas, cumplido, evaluable, fuerza, confianza
        aceptadas.append(codigo)

    # Con una falla de pista confirmada, una linea en FTF no distingue una falla de jaula de la modulacion por
    # jaula que acompaña a las fallas de pista: la jaula se informa solo si no hay pista que la explique.
    minima = competencia["jaula_subordinada_a_pista"]["confianza_minima_pista"]
    pistas = [a for a in aceptadas if a in ("BPFO", "BPFI") and candidatos[a]["confianza"] >= minima]
    if "FTF" in aceptadas and pistas:
        aceptadas.remove("FTF")
        notas.append(
            f"Se descartó la hipótesis de {NOMBRE_LEGIBLE['FTF']}: hay una falla de pista con confianza de al menos "
            f"{minima:.2f}, {' y '.join(NOMBRE_LEGIBLE[p] for p in pistas)}, y con esa falla una línea en FTF no "
            "permite distinguir un daño de jaula de la modulación por jaula que acompaña a la falla de pista."
        )
    return aceptadas, notas


def estimar_velocidad_por_rodamiento(datos_crudos, frecuencia_muestreo, rpm_nominal, rodamiento, normativa, frecuencia_maxima=500):
    """
    Velocidad de giro que hace coincidir la firma completa de una falla de rodamiento con el espectro de
    envolvente (D-066). Respaldo del peine armonico (velocidad_peine.py) cuando este es ambiguo: en el espectro
    de un rodamiento con falla, el peine ve lineas de la falla por todas partes, pero esas mismas lineas
    (fundamental, armonico y bandas laterales, coherentes entre si) son una firma mucho mas especifica.

    Se prueba cada velocidad de la banda `velocidad_real.rodamiento` y se conservan las que dan una hipotesis de
    BPFO, BPFI o BSF con TODA su evidencia (`confianza_minima`; la jaula queda fuera: tiene una sola linea). La
    velocidad se afina promediando la que implica cada linea detectada. Si hay dos candidatas de fallas o
    velocidades distintas con fuerza comparable, es ambiguo y no estima.

    Supone que la falla existe: sin falla no deberia haber ninguna candidata, pero si la hay, la velocidad que
    devuelve es la de una falla supuesta. Quien la use debe decirlo. Devuelve {"rpm", "falla", "puntaje"} o None.
    """
    if not geometria_completa(rodamiento) or not rpm_nominal:
        return None
    ejes = ejes_en_columnas(datos_crudos.columns)
    if not ejes:
        return None

    criterios = normativa["criterios_proyecto"]
    parametros = criterios["deteccion_lineas_rodamiento"]
    escaneo = criterios["velocidad_real"]["rodamiento"]
    tolerancias = {
        "rodamientos": criterios["tolerancias"].get("coincidencia_frecuencia_rodamientos_pct_default", TOLERANCIA_RODAMIENTO_PCT),
        "banda_lateral": criterios["tolerancias"].get("coincidencia_banda_lateral_pct_default", TOLERANCIA_BANDA_LATERAL_PCT),
    }
    pesos = normativa["criterios_proyecto"]["pesos_evidencia"]
    reglas_yaml = normativa["motor_diagnostico"]["reglas"]
    roles_por_falla = {
        codigo: _roles_de_regla(reglas_yaml.get(NOMBRE_REGLA_POR_FALLA[codigo], {}), pesos) for codigo in ("BPFO", "BPFI", "BSF")
    }

    # Los espectros se calculan una vez, con la banda y el tope de la velocidad mas alta de la busqueda.
    rpm_maxima = rpm_nominal * (1 + escaneo["ventana_superior_pct"] / 100)
    frecuencias_maximas = {k: float(v) for k, v in calcular_frecuencias_falla(rpm_maxima, rodamiento).items()}
    frecuencia_tope = min(
        max(frecuencia_maxima, FACTOR_FRECUENCIA_MAXIMA * max(frecuencias_maximas.values())), frecuencia_muestreo / 4
    )
    espectros = {}
    for eje in ejes:
        _, _, frecuencias, amplitudes = _espectro_demodulado(
            datos_crudos[f"vibracion_{eje}"].to_numpy(), frecuencia_muestreo, frecuencias_maximas, frecuencia_tope, parametros
        )
        espectros[eje] = EspectroLineas(frecuencias, amplitudes, parametros, cantidad_ejes=len(ejes))

    paso = escaneo["paso_busqueda_pct"] / 100
    factores = np.arange(1 - escaneo["ventana_inferior_pct"] / 100, 1 + escaneo["ventana_superior_pct"] / 100 + paso / 2, paso)
    candidatas = []  # (rpm probada, falla, fuerza, rpm implicada por las lineas)
    for factor in factores:
        rpm = rpm_nominal * factor
        frecuencias_falla = {k: float(v) for k, v in calcular_frecuencias_falla(rpm, rodamiento).items()}
        fr = rpm / 60
        espaciado = {"BPFI": fr, "BSF": frecuencias_falla["FTF"]}
        for codigo, roles in roles_por_falla.items():
            if not roles:
                continue
            for eje, espectro in espectros.items():
                resultado = _evaluar_en_eje(
                    espectro, eje, frecuencias_falla[codigo], espaciado.get(codigo), roles, tolerancias, parametros
                )
                cumplido, evaluable, fuerza = _puntuar(resultado, roles)
                if evaluable and cumplido / evaluable >= escaneo["confianza_minima"]:
                    implicadas = [
                        linea["frecuencia"] / (k * frecuencias_falla[codigo] / fr)
                        for rol, k in (("fundamental", 1), ("armonico", 2))
                        for linea in resultado["lineas"].get(rol, [])
                    ]
                    candidatas.append((rpm, codigo, fuerza, 60 * float(np.mean(implicadas))))
    if not candidatas:
        return None

    mejor = max(candidatas, key=lambda c: c[2])
    plateau = [c for c in candidatas if c[1] == mejor[1] and c[2] >= FRACCION_PLATEAU_VELOCIDAD * mejor[2]]
    rivales = [c for c in candidatas if abs(c[3] - mejor[3]) / mejor[3] * 100 > escaneo["separacion_unicidad_pct"]]
    if rivales and mejor[2] < escaneo["razon_minima_unicidad"] * max(c[2] for c in rivales):
        return None
    return {"rpm": float(np.mean([c[3] for c in plateau])), "falla": mejor[1], "puntaje": float(mejor[2])}


def evaluar_rodamiento_detallado(datos_crudos, frecuencia_muestreo, rpm_nominal, rodamiento, normativa, frecuencia_maxima=500):
    """
    Devuelve (hipotesis, notas): las hipotesis de falla de rodamiento (mismo formato que evaluar_reglas() en
    diagnostico.py, con 'intensidad_evidencia' en bits para desempatar) y los avisos de ambiguedad entre fallas,
    listos para agregar a las limitaciones del reporte. ([], []) si la geometria esta incompleta.
    """
    if not geometria_completa(rodamiento):
        return [], []

    ejes = ejes_en_columnas(datos_crudos.columns)
    if not ejes:
        return [], []

    criterios = normativa["criterios_proyecto"]
    parametros = criterios["deteccion_lineas_rodamiento"]
    tolerancias = {
        "rodamientos": criterios["tolerancias"].get("coincidencia_frecuencia_rodamientos_pct_default", TOLERANCIA_RODAMIENTO_PCT),
        "banda_lateral": criterios["tolerancias"].get("coincidencia_banda_lateral_pct_default", TOLERANCIA_BANDA_LATERAL_PCT),
    }
    pesos = normativa["criterios_proyecto"]["pesos_evidencia"]
    reglas_yaml = normativa["motor_diagnostico"]["reglas"]

    frecuencias_falla = {k: float(v) for k, v in calcular_frecuencias_falla(rpm_nominal, rodamiento).items()}
    fr = rpm_nominal / 60
    espaciado_laterales = {"BPFI": fr, "BSF": frecuencias_falla["FTF"]}

    frecuencia_tope = min(
        max(frecuencia_maxima, FACTOR_FRECUENCIA_MAXIMA * max(frecuencias_falla.values())), frecuencia_muestreo / 4
    )
    espectros, bandas = {}, {}
    for eje in ejes:
        _, bandas[eje], frecuencias, amplitudes = _espectro_demodulado(
            datos_crudos[f"vibracion_{eje}"].to_numpy(), frecuencia_muestreo, frecuencias_falla, frecuencia_tope, parametros
        )
        espectros[eje] = EspectroLineas(frecuencias, amplitudes, parametros, cantidad_ejes=len(ejes))

    candidatos = {}
    for codigo, f_nominal in frecuencias_falla.items():
        roles = _roles_de_regla(reglas_yaml.get(NOMBRE_REGLA_POR_FALLA[codigo], {}), pesos)
        if not roles or f_nominal <= 0:
            continue
        espaciado = espaciado_laterales.get(codigo)

        mejor = None
        for eje, espectro in espectros.items():
            resultado = _evaluar_en_eje(espectro, eje, f_nominal, espaciado, roles, tolerancias, parametros)
            cumplido, evaluable, fuerza = _puntuar(resultado, roles)
            if cumplido <= 0:
                continue
            clave = (_confianza(cumplido, evaluable), fuerza)
            if mejor is None or clave > mejor[0]:
                mejor = (clave, resultado)

        if mejor is not None:
            resultado = mejor[1]
            candidatos[codigo] = {
                "resultado": resultado,
                "roles": roles,
                "f_nominal": f_nominal,
                "espaciado": espaciado,
                "modeladas": _lineas_modeladas(codigo, f_nominal, resultado["escala"], espaciado),
            }

    aceptadas, notas = _competir(candidatos, espectros, parametros, criterios["competencia_rodamientos"])

    hipotesis = []
    for codigo in aceptadas:
        c = candidatos[codigo]
        nombre_regla = NOMBRE_REGLA_POR_FALLA[codigo]
        evidencias = [
            texto
            for rol in ("fundamental", "armonico", "laterales")
            if (texto := _texto_evidencia(rol, codigo, c["resultado"], c["explicadas"]))
        ]
        hipotesis.append(
            {
                "falla": nombre_regla,
                "confianza": round(c["confianza"], 2),
                "evidencias": evidencias,
                "recomendacion": reglas_yaml.get(nombre_regla, {}).get("recomendacion", []),
                # Eje donde se encontro la evidencia - lo usa
                # calcular_datos_grafico() para saber que eje graficar.
                "eje": c["resultado"]["eje"],
                # Suma de r^2 de las lineas (bits de sorpresa): desempata hipotesis con la misma confianza.
                "intensidad_evidencia": round(float(c["fuerza"]), 1),
            }
        )

    hipotesis.sort(key=lambda h: (h["confianza"], h["intensidad_evidencia"]), reverse=True)

    if hipotesis:
        eje_principal = hipotesis[0]["eje"]
        banda = bandas[eje_principal]
        if banda is not None:
            notas.insert(
                0,
                f"Banda de demodulación del espectro de envolvente (eje {eje_principal.upper()}): "
                f"{banda[0] / 1000:.1f}–{banda[1] / 1000:.1f} kHz, elegida por la curtosis de su espectro de envolvente ({banda[2]:.1f}).",
            )
    return hipotesis, notas


def evaluar_rodamiento(datos_crudos, frecuencia_muestreo, rpm_nominal, rodamiento, normativa, frecuencia_maxima=500):
    """
    Devuelve hipotesis de falla de rodamiento (mismo formato que
    evaluar_reglas() en diagnostico.py), o [] si la geometria del
    rodamiento esta incompleta. Los avisos de ambiguedad entre fallas
    los entrega evaluar_rodamiento_detallado().
    """
    hipotesis, _ = evaluar_rodamiento_detallado(
        datos_crudos, frecuencia_muestreo, rpm_nominal, rodamiento, normativa, frecuencia_maxima
    )
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
    parametros = cargar_normativa()["criterios_proyecto"]["deteccion_lineas_rodamiento"]

    # El espectro y la envolvente que se grafican son los de la banda de resonancia que uso el diagnostico.
    demodulados = {}
    for candidato in EJES:
        columna = f"vibracion_{candidato}"
        if columna in datos_crudos.columns:
            demodulados[candidato] = _espectro_demodulado(
                datos_crudos[columna].to_numpy(), frecuencia_muestreo, frecuencias_falla, frecuencia_maxima, parametros
            )

    if hipotesis and hipotesis[0]["eje"] in demodulados:
        eje = hipotesis[0]["eje"]
    else:
        eje = None
        mejor_amplitud = -1
        for candidato, (_, _, _, amplitudes) in demodulados.items():
            if len(amplitudes) and amplitudes.max() > mejor_amplitud:
                mejor_amplitud = amplitudes.max()
                eje = candidato
        if eje is None:
            return None

    señal = datos_crudos[f"vibracion_{eje}"].to_numpy()
    señal_banda, banda, frecuencias_espectro, amplitudes_espectro = demodulados[eje]

    # La envolvente (Hilbert) es la de la señal FILTRADA en la banda de resonancia, de una amplitud mucho menor que
    # la de la señal cruda de banda ancha: graficarlas juntas dejaba la envolvente como una linea plana. Se grafica
    # la señal filtrada con su envolvente, y solo un tramo inicial: en toda la ventana los impactos (cada 1/BPFO,
    # unos 9 ms) se apretan hasta no distinguirse.
    muestras_grafico = min(len(señal_banda), max(2, int(round(DURACION_GRAFICO_TIEMPO_S * frecuencia_muestreo))))
    tiempo = np.arange(muestras_grafico) / frecuencia_muestreo
    envolvente_tiempo = calcular_envolvente(señal_banda)[:muestras_grafico]

    return {
        "eje": eje,
        "banda_demodulacion_hz": None if banda is None else [round(banda[0], 1), round(banda[1], 1)],
        "frecuencias_falla": frecuencias_falla,
        # Arreglos numpy sin serializar - pdf_reporte.py los grafica
        # directamente con matplotlib a resolucion completa; la API
        # (reportes.py) los reduce antes de mandarlos como JSON.
        "frecuencias_espectro": frecuencias_espectro,
        "amplitudes_espectro": amplitudes_espectro,
        "tiempo": tiempo,
        "señal": señal_banda[:muestras_grafico],  # filtrada en la banda de demodulacion (la que envuelve Hilbert)
        "envolvente_tiempo": envolvente_tiempo,
    }


def serializar_datos_grafico(datos_grafico, cantidad_maxima_tiempo=1200):
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
        "banda_demodulacion_hz": datos_grafico["banda_demodulacion_hz"],
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
                "senal": round(float(señal[i]), 6),
                "envolvente": round(float(envolvente_tiempo[i]), 6),
            }
            for i in indices
        ],
    }
