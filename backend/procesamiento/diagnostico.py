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
      "vibracion muy elevada" (criterios_proyecto.
      direccion_radial_axial en criterios_proyecto.yaml) NO son una cita ISO especifica -
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
from backend.procesamiento.cambio_linea_base import evaluar_cambio_respecto_linea_base
from backend.procesamiento.ejes import EJES_POSIBLES, ejes_en_datos_fft
from backend.procesamiento.linea_base import (
    anotar_hallazgos_con_linea_base,
    esta_elevada,
    factor_aumento_minimo,
)
from backend.procesamiento.severidad_iso import clasificar_severidad_peor_eje
from backend.procesamiento.velocidad_peine import estimar_velocidad_por_peine

RUTA_PROYECTO = Path(__file__).parent.parent.parent
RUTA_NORMATIVA = RUTA_PROYECTO / "conocimiento" / "normativa_motorguardian.yaml"
RUTA_CRITERIOS_PROYECTO = RUTA_PROYECTO / "conocimiento" / "criterios_proyecto.yaml"

TOLERANCIA_FRECUENCIA_PCT = 3.0
EJES = ["x", "y", "z"]

LIMITACIONES = [
    "Diagnostico basado en reglas de 1x/2x/3x RPM (desbalanceo, desalineacion "
    "angular, desalineacion paralela) y, si corresponde, en las 4 reglas de "
    "rodamiento (pista exterior/interior, elemento rodante, jaula). Engranajes "
    "no se evaluan todavia.",
    "Requiere inspeccion fisica para confirmar cualquier hipotesis.",
]

LIMITACION_VELOCIDAD_MEDIDA = (
    "Se usó la velocidad de giro declarada al cargar la medición ({rpm:.0f} r/min, "
    "{desviacion_pct:+.1f} % respecto de la nominal de {rpm_nominal:.0f} r/min) para ubicar "
    "1x/2x/3x y las frecuencias de falla."
)

LIMITACION_VELOCIDAD_ESTIMADA = (
    "La medición no declara la velocidad de giro: se estimó desde el espectro ({rpm:.0f} r/min, "
    "{desviacion_pct:+.1f} % respecto de la nominal de {rpm_nominal:.0f} r/min) como el pico "
    "dominante cerca de la nominal. Es una estimación que supone que ese pico es 1x, no una "
    "medición; para usar un valor confiable, declara la velocidad real al cargar la medición."
)

LIMITACION_VELOCIDAD_ESTIMADA_PEINE = (
    "La medición no declara la velocidad de giro: se estimó desde el espectro ({rpm:.0f} r/min, "
    "{desviacion_pct:+.1f} % respecto de la nominal de {rpm_nominal:.0f} r/min) como la velocidad que "
    "alinea los múltiplos {armonicos_texto} con líneas significativas. Es una estimación de la señal, "
    "no una medición: las líneas de la red eléctrica caen en múltiplos de la velocidad sincrónica y "
    "pueden atraer el resultado hacia ella; para usar un valor confiable, declara la velocidad real "
    "al cargar la medición."
)

LIMITACION_VELOCIDAD_ESTIMADA_RODAMIENTO = (
    "La medición no declara la velocidad de giro y el espectro no permite fijarla por los armónicos del eje: se estimó "
    "({rpm:.0f} r/min, {desviacion_pct:+.1f} % respecto de la nominal de {rpm_nominal:.0f} r/min) como la velocidad "
    "que hace coincidir la firma completa de una falla de {falla_texto} del rodamiento en el espectro de envolvente. "
    "Esta estimación supone que esa falla existe: es una estimación de la señal, no una medición, y si la falla no "
    "fuera real la velocidad tampoco lo sería. Para usar un valor confiable, declara la velocidad real al cargar la "
    "medición."
)

LIMITACION_CAMBIO_LINEA_BASE = (
    "El indicador de cambio compara la velocidad RMS de banda limitada ({f_min:g}–{f_max:g} Hz, peor eje) con la "
    "de la línea base: 'elevado' desde {elevado:g} veces y 'muy elevado' desde {muy_elevado:g} veces. Son criterios "
    "del proyecto, no una norma, pendientes de validación; no reemplazan la severidad de ISO 20816-3 (que solo "
    "aplica sobre 15 kW) y solo son válidos si la referencia y la medición actual se tomaron en condiciones de "
    "operación comparables."
)

AVISO_VELOCIDAD_INCONSISTENTE = (
    "Posible inconsistencia de velocidad: junto a la frecuencia de giro usada ({f1:.1f} Hz = {rpm:.0f} r/min) "
    "hay un pico en {f_ext:.1f} Hz (amplitud {a_ext:.3g}), fuera de la ventana de ±{tol:g} % donde se busca el 1x, "
    "{detalle}. La velocidad usada puede no ser la real y el 1x encontrado puede ser un pico vecino: la "
    "evidencia de 1x/2x/3x y de frecuencias de falla de este reporte puede estar mal ubicada. Declara la "
    "velocidad real al cargar la medición."
)

LIMITACION_SIN_LINEA_BASE = (
    "Este sensor no tiene una línea base (medición sana de referencia): 'evidencia "
    "presente' en 1x/2x significa solo que hay un pico significativo en esa "
    "frecuencia, no que sea anormal para esta máquina — un equipo sano con carga "
    "ya tiene un 1x apreciable. Por eso la confianza de desbalanceo y "
    "desalineación queda acotada a {tope:.0%}. Para quitar esa restricción, "
    "marca una medición sana como línea base en el Analizador de Vibraciones."
)

LIMITACION_CON_LINEA_BASE = (
    "Desbalanceo y desalineación se evaluaron contra la línea base de este sensor "
    "({fecha}): un armónico (1x/2x/3x) cuenta como evidencia solo si su amplitud "
    "supera {factor:g} veces la de la referencia. Ese factor es el criterio "
    "'elevado' del archivo de conocimiento, pendiente de validación; la "
    "comparación es válida solo si la medición actual y la de referencia se "
    "tomaron en condiciones de operación comparables (velocidad y carga). Las "
    "reglas de rodamiento no usan línea base."
)

LIMITACION_SIN_ORIENTACION = (
    "El sensor no tiene declarada la orientación de sus ejes (Configuración → "
    "Sensores): se revisan los 3 ejes por igual, sin distinguir vibración "
    "radial de axial. La desalineación angular depende principalmente de "
    "vibración axial — sin poder aislarla, su confianza queda acotada a 50%."
)

LIMITACION_EJES_INCOMPLETOS = (
    "El sensor mide {cantidad} de los 3 ejes ({ejes}): 1x/2x/3x y los estadísticos se evalúan solo en "
    "{este_ese}, y no se puede comparar vibración radial con axial en el mismo punto, así que esa evidencia "
    "no se evalúa. La desalineación angular depende principalmente de la vibración axial — sin poder "
    "aislarla, su confianza queda acotada a 50 %. Tampoco se sabe cuánta vibración hay en los ejes que no "
    "se midieron: un sensor de un solo eje puede no ver una falla que se manifiesta en otra dirección."
)

LIMITACION_ORIENTACION_NO_VALIDADA = (
    "La orientación del sensor está declarada y se usó para evaluar "
    "vibración radial vs. axial, pero los umbrales que definen \"dirección "
    "predominante\"/\"vibración muy elevada\" son práctica general de "
    "análisis de vibraciones, no una cita ISO específica — pendientes de "
    "validación (ver R-003 en PROYECTO.md)."
)


class BaseConocimientoIncompleta(RuntimeError):
    """Falta o no se pudo leer alguno de los dos archivos de conocimiento: el sistema no debe calcular nada."""


def _leer_yaml_obligatorio(ruta, descripcion):
    if not ruta.is_file():
        raise BaseConocimientoIncompleta(f"No se encontró el archivo de {descripcion}: {ruta}")
    try:
        with open(ruta, encoding="utf-8") as archivo:
            datos = yaml.safe_load(archivo)
    except yaml.YAMLError as error:
        raise BaseConocimientoIncompleta(f"No se pudo interpretar el archivo de {descripcion} ({ruta.name}): {error}") from error
    if not isinstance(datos, dict) or not datos:
        raise BaseConocimientoIncompleta(f"El archivo de {descripcion} ({ruta.name}) está vacío o no es un mapa YAML")
    return datos


def _parametros_repetidos(base, complemento, ruta=""):
    """Rutas de parametros que estan en ambos mapas con un valor final (no un sub-mapa) en alguno de los dos."""
    repetidos = []
    for clave, valor in complemento.items():
        if clave not in base:
            continue
        if isinstance(valor, dict) and isinstance(base[clave], dict):
            repetidos += _parametros_repetidos(base[clave], valor, f"{ruta}{clave}.")
        else:
            repetidos.append(f"{ruta}{clave}")
    return repetidos


@lru_cache
def cargar_normativa():
    """
    Lee los DOS archivos de conocimiento y los entrega en un solo diccionario:
      - normativa_motorguardian.yaml: lo que tiene respaldo en una norma, con sus claves de siempre.
      - criterios_proyecto.yaml: lo que el proyecto adoptó sin respaldo normativo, bajo la clave
        "criterios_proyecto" (y su metadata en "metadata_criterios_proyecto").
    Si falta o no se puede leer cualquiera de los dos, o el segundo repite un parámetro que la normativa
    ya fija, lanza BaseConocimientoIncompleta: el sistema no calcula con una base a medias, ni con un
    criterio del proyecto que contradiga la norma.
    """
    normativa = _leer_yaml_obligatorio(RUTA_NORMATIVA, "la normativa")
    criterios = _leer_yaml_obligatorio(RUTA_CRITERIOS_PROYECTO, "los criterios del proyecto")
    if not isinstance(criterios.get("criterios_proyecto"), dict) or not criterios["criterios_proyecto"]:
        raise BaseConocimientoIncompleta(f"{RUTA_CRITERIOS_PROYECTO.name} no tiene la sección 'criterios_proyecto'")

    repetidos = _parametros_repetidos(normativa, criterios["criterios_proyecto"])
    if repetidos:
        raise BaseConocimientoIncompleta(
            f"Los criterios del proyecto repiten parámetros que la normativa ya define: {', '.join(repetidos)}"
        )

    normativa["criterios_proyecto"] = criterios["criterios_proyecto"]
    normativa["metadata_criterios_proyecto"] = criterios.get("metadata", {})
    _componer_pesos_de_reglas(normativa)
    return normativa


def _agregar_evidencias_complementarias(reglas, complementarias):
    """
    Suma a cada regla de la normativa las evidencias que criterios_proyecto.evidencias_complementarias le
    agrega (marcadas con origen "criterios_proyecto"). Una complementaria no puede repetir una evidencia
    que la regla ya tiene: eso seria redefinirla, y los criterios solo complementan. Devuelve los problemas
    encontrados (lista de textos, vacia si todo esta bien).
    """
    problemas = []
    for nombre, por_lista in complementarias.items():
        if nombre not in reglas:
            problemas.append(f"{nombre}: evidencias complementarias de una regla que no existe en la normativa")
            continue
        for lista, evidencias in (por_lista or {}).items():
            if lista not in ("evidencias", "evidencias_en_contra"):
                problemas.append(f"{nombre}.{lista}: solo se complementan 'evidencias' y 'evidencias_en_contra'")
                continue
            existentes = {e["feature"] for e in reglas[nombre].get(lista, [])}
            for evidencia in evidencias:
                if evidencia["feature"] in existentes:
                    problemas.append(f"{nombre}.{lista}.{evidencia['feature']}: ya existe en la normativa, no se puede redefinir")
                    continue
                existentes.add(evidencia["feature"])
                reglas[nombre].setdefault(lista, []).append({**evidencia, "origen": "criterios_proyecto"})
    return problemas


def _componer_pesos_de_reglas(normativa):
    """
    Las reglas de la normativa dicen QUE sintoma indica cada falla (feature + condicion); cuanto pesa cada
    uno vive en criterios_proyecto.pesos_reglas (el peso no sale de ninguna norma). Aqui se juntan: cada
    evidencia recibe su "peso" desde los criterios del proyecto. Falla si a una evidencia le falta peso,
    si sobra un peso sin evidencia o si el peso nombrado no existe en pesos_evidencia.
    """
    criterios = normativa["criterios_proyecto"]
    escala = criterios.get("pesos_evidencia")
    pesos_reglas = criterios.get("pesos_reglas")
    if not isinstance(escala, dict) or not isinstance(pesos_reglas, dict):
        raise BaseConocimientoIncompleta("criterios_proyecto.yaml no define 'pesos_evidencia' y 'pesos_reglas'")

    reglas = normativa["motor_diagnostico"]["reglas"]
    problemas = _agregar_evidencias_complementarias(reglas, criterios.get("evidencias_complementarias") or {})
    for nombre, regla in reglas.items():
        pesos_de_la_regla = pesos_reglas.get(nombre, {})
        for lista in ("evidencias", "evidencias_en_contra"):
            pesos_lista = dict(pesos_de_la_regla.get(lista) or {})
            for evidencia in regla.get(lista, []):
                feature = evidencia["feature"]
                if feature not in pesos_lista:
                    problemas.append(f"{nombre}.{lista}.{feature}: sin peso en criterios_proyecto.pesos_reglas")
                    continue
                peso = pesos_lista.pop(feature)
                if peso not in escala:
                    problemas.append(f"{nombre}.{lista}.{feature}: el peso '{peso}' no existe en pesos_evidencia")
                evidencia["peso"] = peso
            problemas += [f"{nombre}.{lista}.{sobrante}: peso sin evidencia en la regla" for sobrante in pesos_lista]
    problemas += [f"{nombre}: regla con pesos que no existe en la normativa" for nombre in pesos_reglas if nombre not in reglas]
    if problemas:
        raise BaseConocimientoIncompleta("Pesos de reglas inconsistentes: " + "; ".join(problemas))


def detectar_picos(frecuencias, amplitudes):
    """
    Picos con prominencia y relacion senal/ruido minimas, leidas de
    criterios_proyecto.deteccion_picos (criterios_proyecto.yaml) - antes eran
    literales (0.05/3.0) hardcodeados aca que por coincidencia ya
    calzaban con el YAML pero nunca lo leian; ahora el YAML es la unica
    fuente de verdad.
    """
    amplitudes = np.array(amplitudes)

    if len(amplitudes) == 0 or amplitudes.max() <= 0:
        return []

    parametros = cargar_normativa()["criterios_proyecto"]["deteccion_picos"]
    prominencia_minima = parametros["prominencia_minima_relativa"] * amplitudes.max()
    indices, _ = find_peaks(amplitudes, prominence=prominencia_minima)

    ruido = np.median(amplitudes) or 1e-9
    relacion_minima = parametros["relacion_sobre_ruido_minima"]

    # Relacion senal/ruido LOCAL (opcional): la mediana global subestima el ruido donde el espectro esta mas
    # alto (ruido coloreado, resonancias), y un armonico que solo roza ese ruido pasa por "pico". Si el YAML
    # define ambos parametros, el pico tambien debe superar relacion_sobre_ruido_local_minima veces la mediana
    # del espectro a +-ventana_ruido_local_hz de el. Sin ellos, el comportamiento es el de siempre.
    relacion_local = parametros.get("relacion_sobre_ruido_local_minima")
    ventana_local = parametros.get("ventana_ruido_local_hz")
    frecuencias_np = np.asarray(frecuencias, dtype=float) if relacion_local and ventana_local else None

    def destaca_del_ruido_local(indice):
        if frecuencias_np is None:
            return True
        vecindad = amplitudes[np.abs(frecuencias_np - frecuencias_np[indice]) <= ventana_local]
        return amplitudes[indice] / (np.median(vecindad) or 1e-9) >= relacion_local

    return [
        {"frecuencia": float(frecuencias[i]), "amplitud": float(amplitudes[i])}
        for i in indices
        if amplitudes[i] / ruido >= relacion_minima and destaca_del_ruido_local(i)
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


def _refinar_frecuencia_del_pico(datos_fft, eje, frecuencia_pico):
    """
    Interpolacion parabolica sobre los 3 bins alrededor de un pico: la
    resolucion de la FFT (con la ventana de 2 s, 0.5 Hz, es decir 30 r/min)
    deja el pico en el bin mas cercano, hasta ~1 % lejos de la frecuencia
    real. Devuelve la frecuencia sin refinar si el pico esta en un borde.
    """
    frecuencias = [fila["frecuencia"] for fila in datos_fft]
    indice = min(range(len(frecuencias)), key=lambda i: abs(frecuencias[i] - frecuencia_pico))
    if indice == 0 or indice == len(frecuencias) - 1:
        return frecuencia_pico

    izquierda, centro, derecha = (datos_fft[i][f"amplitud_{eje}"] for i in (indice - 1, indice, indice + 1))
    denominador = izquierda - 2 * centro + derecha
    if denominador == 0:
        return frecuencia_pico

    desplazamiento = 0.5 * (izquierda - derecha) / denominador
    if abs(desplazamiento) > 0.5:
        return frecuencia_pico

    return frecuencias[indice] + desplazamiento * (frecuencias[indice + 1] - frecuencias[indice])


def estimar_rpm_por_picos(picos_por_eje, rpm_nominal, normativa, datos_fft=None):
    """
    Estima la velocidad de giro como el pico dominante (mayor amplitud, en
    cualquiera de los 3 ejes) dentro de la banda de busqueda alrededor de la
    nominal - criterios_proyecto.velocidad_real (criterios_proyecto.yaml, D-057).
    Devuelve r/min, o None si no hay ningun pico detectado en esa banda. Si
    se entrega datos_fft, la frecuencia del pico se refina por interpolacion.

    Es una ESTIMACION: se apoya en la propia señal, asi que supone que el
    pico dominante cerca de la nominal es el 1x. Por eso quien la usa debe
    declararla como estimada, nunca presentarla como una medicion.
    """
    parametros = normativa["criterios_proyecto"]["velocidad_real"]
    frecuencia_nominal = rpm_nominal / 60
    minimo = frecuencia_nominal * (1 - parametros["ventana_busqueda_inferior_pct"] / 100)
    maximo = frecuencia_nominal * (1 + parametros["ventana_busqueda_superior_pct"] / 100)

    candidatos = [
        (eje, pico)
        for eje, picos in picos_por_eje.items()
        for pico in picos
        if minimo <= pico["frecuencia"] <= maximo
    ]
    if not candidatos:
        return None

    eje, mejor = max(candidatos, key=lambda candidato: candidato[1]["amplitud"])
    frecuencia = mejor["frecuencia"]
    if datos_fft is not None:
        frecuencia = _refinar_frecuencia_del_pico(datos_fft, eje, frecuencia)

    return frecuencia * 60


def resolver_velocidad(
    datos_fft, rpm_nominal, rpm_real=None, normativa=None, datos_crudos=None, frecuencia_muestreo=None, rodamiento=None
):
    """
    Que velocidad de giro usar para ubicar 1x/2x/3x y las frecuencias de
    falla de rodamiento (D-057, ver PROYECTO.md). En este orden:
        1. "medida": la que el operador declaro al cargar la medicion.
        2. "estimada", y el metodo con que se obtuvo:
             "peine": la velocidad que alinea varios multiplos k*fr con
                 lineas significativas del espectro (D-066);
             "rodamiento": si el peine es ambiguo y se entrego la señal cruda
                 y un rodamiento con geometria completa, la velocidad que hace
                 coincidir la firma completa de una falla de rodamiento en el
                 espectro de envolvente (D-066). Supone que esa falla existe;
             "pico": el pico dominante cerca de la nominal (D-057).
        3. "nominal": la del equipo (comportamiento anterior a D-057).

    Devuelve {"rpm", "origen", "metodo" (None, "peine", "rodamiento" o
    "pico"), "armonicos" (los k alineados por el peine, o None), "falla"
    (la del metodo "rodamiento", o None), "rpm_nominal", "desviacion_pct"}.
    """
    normativa = normativa or cargar_normativa()

    metodo, armonicos, falla = None, None, None
    if rpm_real:
        rpm, origen = float(rpm_real), "medida"
    else:
        peine = estimar_velocidad_por_peine(datos_fft, rpm_nominal, normativa)
        por_rodamiento = None
        if not peine and datos_crudos is not None and frecuencia_muestreo and rodamiento is not None:
            from backend.procesamiento.diagnostico_rodamientos import estimar_velocidad_por_rodamiento

            por_rodamiento = estimar_velocidad_por_rodamiento(
                datos_crudos, frecuencia_muestreo, rpm_nominal, rodamiento, normativa
            )

        if peine:
            rpm, origen, metodo, armonicos = peine["rpm"], "estimada", "peine", peine["armonicos"]
        elif por_rodamiento:
            rpm, origen, metodo, falla = por_rodamiento["rpm"], "estimada", "rodamiento", por_rodamiento["falla"]
        else:
            frecuencias = [fila["frecuencia"] for fila in datos_fft]
            picos_por_eje = {
                eje: detectar_picos(frecuencias, [fila[f"amplitud_{eje}"] for fila in datos_fft])
                for eje in ejes_en_datos_fft(datos_fft)
            }
            estimada = estimar_rpm_por_picos(picos_por_eje, rpm_nominal, normativa, datos_fft)
            if estimada:
                rpm, origen, metodo = estimada, "estimada", "pico"
            else:
                rpm, origen = float(rpm_nominal), "nominal"

    return {
        "rpm": rpm,
        "origen": origen,
        "metodo": metodo,
        "armonicos": armonicos,
        "falla": falla,
        "rpm_nominal": float(rpm_nominal),
        "desviacion_pct": round((rpm - rpm_nominal) / rpm_nominal * 100, 2),
    }


def verificar_consistencia_velocidad(pico_1x, picos_por_eje, rpm_usada, normativa, tolerancia_pct=TOLERANCIA_FRECUENCIA_PCT):
    """
    Control de consistencia de la velocidad usada (D-058, ver PROYECTO.md).

    El motor asume que la velocidad usada es la real y busca el 1x en una
    ventana de +-tolerancia_pct; si la velocidad esta mal, puede tomar un
    pico vecino pequeño como si fuera el 1x y reportarlo sin que nada lo
    avise. Este control no depende de como se obtuvo la velocidad: mira si,
    cerca del 1x esperado pero FUERA de la ventana, hay un pico claramente
    mayor que el encontrado dentro de ella.

    Devuelve un dict para mostrar en el reporte:
        frecuencia_1x_esperada, tolerancia_pct,
        pico_1x: el encontrado dentro de la ventana (o None),
        pico_dominante: el de mayor amplitud de todo el espectro (o None),
        pico_externo: el mayor fuera de la ventana pero dentro de
            +-zona_pct del 1x esperado (o None),
        razon_pico_externo: amplitud externa / amplitud del pico_1x (None si
            no hay pico_1x), e inconsistente (bool).
    No cambia el diagnostico: solo advierte.
    """
    parametros = normativa["criterios_proyecto"]["velocidad_real"]["verificacion"]
    frecuencia_1x = rpm_usada / 60
    ventana = frecuencia_1x * tolerancia_pct / 100
    zona = frecuencia_1x * parametros["zona_pct"] / 100

    todos = [
        {"frecuencia": pico["frecuencia"], "amplitud": pico["amplitud"], "eje": eje}
        for eje, picos in picos_por_eje.items()
        for pico in picos
    ]
    pico_dominante = max(todos, key=lambda p: p["amplitud"]) if todos else None

    externos = [p for p in todos if ventana < abs(p["frecuencia"] - frecuencia_1x) <= zona]
    pico_externo = max(externos, key=lambda p: p["amplitud"]) if externos else None

    amplitud_1x = pico_1x["amplitud"] if pico_1x else 0.0
    razon = (pico_externo["amplitud"] / amplitud_1x) if (pico_externo and amplitud_1x > 0) else None

    inconsistente = bool(
        pico_externo
        and (amplitud_1x == 0 or pico_externo["amplitud"] >= parametros["razon_minima_pico_externo"] * amplitud_1x)
    )

    return {
        "frecuencia_1x_esperada": round(frecuencia_1x, 2),
        "tolerancia_pct": tolerancia_pct,
        "pico_1x": (
            {"frecuencia": round(pico_1x["frecuencia"], 2), "amplitud": pico_1x["amplitud"], "eje": pico_1x["eje"]}
            if pico_1x
            else None
        ),
        "pico_dominante": pico_dominante,
        "pico_externo": pico_externo,
        "razon_pico_externo": round(razon, 1) if razon is not None else None,
        "inconsistente": inconsistente,
    }


def analizar_espectro_fft(datos_fft, rpm_nominal):
    """
    datos_fft: lista de {frecuencia, amplitud_x, amplitud_y, amplitud_z}
    tal como devuelve backend/procesamiento/frecuencia.py::calcular_fft
    (solo con los ejes que el sensor tiene - D-062).

    Devuelve (resultado, picos_por_eje):
        - resultado: por armonico (1x/2x/3x), el mejor pico encontrado
          en cualquiera de los ejes presentes (y en cual).
        - picos_por_eje: todos los picos detectados en cada eje, sin
          reducir al "mejor" - lo necesita evaluar_direccion() (D-051)
          para comparar radial vs. axial eje por eje, no solo el eje
          ganador.
    """
    frecuencias = [d["frecuencia"] for d in datos_fft]
    ejes = ejes_en_datos_fft(datos_fft)
    picos_por_eje = {
        eje: detectar_picos(frecuencias, [d[f"amplitud_{eje}"] for d in datos_fft])
        for eje in ejes
    }

    resultado = {}
    for armonico, frecuencia_objetivo in frecuencias_esperadas(rpm_nominal).items():
        mejor = None
        for eje in ejes:
            pico = buscar_pico_cercano(picos_por_eje[eje], frecuencia_objetivo)
            if pico and (mejor is None or pico["amplitud"] > mejor["amplitud"]):
                mejor = {**pico, "eje": eje, "frecuencia_esperada": frecuencia_objetivo}
        resultado[armonico] = mejor

    return resultado, picos_por_eje


def evaluar_direccion(
    picos_por_eje,
    frecuencia_objetivo,
    orientacion_ejes,
    normativa,
    valores_linea_base=None,
    armonico=None,
):
    """
    Compara la amplitud del mejor pico en los ejes radiales vs. el eje
    axial, en frecuencia_objetivo, usando la orientacion declarada del
    sensor (D-051, ver PROYECTO.md).

    Si se entrega valores_linea_base (D-056) junto con el armonico evaluado
    ("1x"/"2x"), "radial_elevada"/"axial_elevada" pasan de significar "hay
    un pico" a "algun eje de ese grupo supera a su referencia" (factor de
    linea_base.factor_aumento_minimo). Las razones radial/axial de
    predominante/muy_elevada no cambian: comparan un eje con otro.

    Devuelve None si no hay orientacion declarada, o si falta al menos
    un eje radial (horizontal o vertical) Y el eje axial - sin ambos
    lados no hay nada que comparar.

    Los umbrales que definen "predominante"/"muy_elevada" (config en
    criterios_proyecto.direccion_radial_axial, criterios_proyecto.yaml) NO son una
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

    def _elevada(ejes, amplitud_del_grupo):
        if valores_linea_base is None or armonico is None:
            return amplitud_del_grupo > 0
        factor = factor_aumento_minimo(normativa)
        referencias = valores_linea_base["amplitudes"].get(armonico, {})
        for eje in ejes:
            pico = buscar_pico_cercano(picos_por_eje.get(eje, []), frecuencia_objetivo)
            if pico and esta_elevada(pico["amplitud"], referencias.get(eje), factor):
                return True
        return False

    parametros = normativa["criterios_proyecto"]["direccion_radial_axial"]
    ratio_predominante = parametros["ratio_minimo_radial_sobre_axial_para_predominante"]
    ratio_muy_elevada = parametros["ratio_minimo_axial_sobre_radial_para_muy_elevada"]

    return {
        "amplitud_radial": amplitud_radial,
        "amplitud_axial": amplitud_axial,
        "radial_elevada": _elevada(ejes_radiales, amplitud_radial),
        "axial_elevada": _elevada(ejes_axiales, amplitud_axial),
        "radial_predominante": amplitud_radial > 0 and (
            amplitud_axial == 0 or amplitud_radial / amplitud_axial >= ratio_predominante
        ),
        "axial_muy_elevada": amplitud_axial > 0 and (
            amplitud_radial == 0 or amplitud_axial / amplitud_radial >= ratio_muy_elevada
        ),
    }


def calcular_relacion_2x_1x(hallazgos):
    """
    Razon entre la amplitud del mejor pico en 2x y la del mejor pico en 1x (en cualquiera de los ejes), medidas
    en la propia medicion - no contra la linea base. Devuelve None si no hay pico en ninguno de los dos, e
    infinito si hay 2x pero ningun 1x. Alimenta las evidencias "2x bajo respecto de 1x" (desbalanceo) y "2x
    elevado" (desalineacion paralela); umbrales en criterios_proyecto.relacion_2x_1x.
    """
    amplitud_1x = hallazgos["1x"]["amplitud"] if hallazgos["1x"] else 0.0
    amplitud_2x = hallazgos["2x"]["amplitud"] if hallazgos["2x"] else 0.0
    if amplitud_1x > 0:
        return amplitud_2x / amplitud_1x
    return float("inf") if amplitud_2x > 0 else None


def evaluar_reglas(
    hallazgos_armonicos,
    normativa,
    frecuencias_objetivo,
    picos_por_eje=None,
    orientacion_ejes=None,
    valores_linea_base=None,
    relacion_2x_1x=None,
):
    """
    hallazgos_armonicos: {"1x": pico_o_None, "2x": ..., "3x": ...}
    frecuencias_objetivo: {"1x": Hz, "2x": Hz, "3x": Hz} (frecuencias_esperadas()).
    picos_por_eje/orientacion_ejes: opcionales (D-051) - si ambos estan
    disponibles, se evalua tambien la evidencia de direccion
    (radial/axial) que el YAML ya definia para estas 3 reglas pero que
    antes no se usaba (ver evaluar_direccion()).
    valores_linea_base: opcional (D-056) - si se entrega, hallazgos_armonicos
    ya debe traer None en los armonicos que NO superan a su referencia
    (linea_base.anotar_hallazgos_con_linea_base), y la evidencia de
    direccion de un armonico solo cuenta si ese armonico es evidencia.

    Evalua las 3 reglas soportadas con un subconjunto reducido de su
    evidencia (ver docstring del modulo) y devuelve las hipotesis con
    confianza >= 0.30, ordenadas de mayor a menor, maximo 3 (mismos
    criterios que confianza_diagnostico.reglas_salida en el YAML).

    relacion_2x_1x: opcional - calcular_relacion_2x_1x() de la medicion (sin
    mirar la linea base). Con ella, el 2x solo es evidencia de desalineacion
    paralela si ademas es "elevado" respecto del 1x, y un 2x "bajo" respecto
    del 1x es evidencia a favor del desbalanceo (criterios_proyecto.
    relacion_2x_1x). Sin ella, el 2x cuenta con que haya un pico, como antes.
    """
    pesos = normativa["criterios_proyecto"]["pesos_evidencia"]
    reglas_yaml = normativa["motor_diagnostico"]["reglas"]

    presente_1x = hallazgos_armonicos["1x"] is not None
    presente_2x = hallazgos_armonicos["2x"] is not None

    # Evidencias que dependen de cuanto pesa el 2x frente al 1x (solo si se entrego la relacion).
    dos_x_bajo = False
    dos_x_elevado = presente_2x
    if relacion_2x_1x is not None:
        umbrales = normativa["criterios_proyecto"]["relacion_2x_1x"]
        dos_x_bajo = relacion_2x_1x <= umbrales["razon_maxima_para_baja"]
        dos_x_elevado = presente_2x and relacion_2x_1x >= umbrales["razon_minima_para_elevada"]

    direccion_1x = None
    direccion_2x = None
    if picos_por_eje is not None:
        direccion_1x = evaluar_direccion(
            picos_por_eje, frecuencias_objetivo["1x"], orientacion_ejes, normativa, valores_linea_base, "1x"
        )
        direccion_2x = evaluar_direccion(
            picos_por_eje, frecuencias_objetivo["2x"], orientacion_ejes, normativa, valores_linea_base, "2x"
        )

    # Con linea base, un armonico que no supera su referencia no es
    # evidencia, y tampoco lo son las comparaciones radial/axial hechas
    # sobre ese mismo armonico (seguirian puntuando a favor de una falla
    # cuyo sintoma principal ya no cuenta).
    if valores_linea_base is not None:
        if direccion_1x is not None and not presente_1x:
            direccion_1x = {
                **direccion_1x,
                "radial_predominante": False,
                "axial_elevada": False,
                "axial_muy_elevada": False,
            }
        if direccion_2x is not None and not presente_2x:
            direccion_2x = {**direccion_2x, "radial_elevada": False}

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
    if presente_1x and relacion_2x_1x is not None:
        peso_evaluable_deseq += pesos["debil"]
        if dos_x_bajo:
            peso_cumplido_deseq += pesos["debil"]
            evidencias_deseq.append(f"2x bajo respecto de 1x (razón {relacion_2x_1x:.2f})")

    # --- desalineacion_paralela: amplitud_2x (fuerte) + amplitud_1x
    # presente (moderada) + vibracion_radial elevada en 2x (moderada).
    # Con la relacion 2x/1x, el 2x elevado es su sintoma definitorio: si el 2x es pequeño frente al 1x (lo que
    # deja un desbalanceo) no hay hipotesis, ni siquiera con 1x y vibracion radial presentes.
    par_descartada = relacion_2x_1x is not None and not dos_x_elevado
    peso_cumplido_par = 0 if par_descartada else (
        (pesos["fuerte"] if presente_2x else 0)
        + (pesos["moderada"] if presente_1x else 0)
    )
    peso_evaluable_par = pesos["fuerte"] + pesos["moderada"]
    evidencias_par = []
    if not par_descartada:
        if presente_2x:
            evidencias_par.append(
                "pico significativo en 2x"
                if relacion_2x_1x is None
                else f"pico significativo en 2x, elevado respecto de 1x (razón {relacion_2x_1x:.2f})"
            )
        if presente_1x:
            evidencias_par.append("pico significativo en 1x")
    if direccion_2x is not None:
        peso_evaluable_par += pesos["moderada"]
        if direccion_2x["radial_elevada"] and not par_descartada:
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
    for restriccion in normativa["criterios_proyecto"]["confianza_diagnostico"]["restricciones"]:
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
    linea_base=None,
    rpm_real=None,
):
    """
    rpm_real es opcional (D-057, ver PROYECTO.md): la velocidad de giro que
    el operador declaro al cargar la medicion. Si falta, se estima desde el
    espectro (resolver_velocidad); si tampoco se puede, se usa la nominal.
    Desde ahi, "rpm_nominal" dentro de esta funcion es la velocidad ya
    resuelta - el parametro conserva su nombre por compatibilidad con los
    llamadores existentes.

    linea_base es opcional (D-056, ver PROYECTO.md): {"valores": dict de
    linea_base.calcular_valores_linea_base(), "fecha": "dd/mm/aaaa"} o None
    si el sensor no tiene una referencia marcada. Con ella, 1x/2x/3x cuentan
    como evidencia solo si superan a su referencia; sin ella, la confianza
    de desbalanceo/desalineacion queda acotada (confianza_diagnostico.
    restricciones, condicion "linea_base_no_disponible", en el YAML).

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

    velocidad = resolver_velocidad(
        datos_fft, rpm_nominal, rpm_real, normativa,
        datos_crudos=datos_crudos, frecuencia_muestreo=frecuencia_muestreo, rodamiento=rodamiento,
    )
    rpm_nominal = velocidad["rpm"]

    hallazgos, picos_por_eje = analizar_espectro_fft(datos_fft, rpm_nominal)

    valores_linea_base = linea_base["valores"] if linea_base else None
    hallazgos_para_reglas = hallazgos
    factor_linea_base = None
    if valores_linea_base:
        factor_linea_base = factor_aumento_minimo(normativa)
        hallazgos, hallazgos_para_reglas = anotar_hallazgos_con_linea_base(
            hallazgos, valores_linea_base, factor_linea_base
        )

    hipotesis = evaluar_reglas(
        hallazgos_para_reglas,
        normativa,
        frecuencias_esperadas(rpm_nominal),
        picos_por_eje,
        orientacion_ejes,
        valores_linea_base,
        calcular_relacion_2x_1x(hallazgos),
    )

    limitaciones = [LIMITACIONES[0]]
    if valores_linea_base:
        limitaciones.append(
            LIMITACION_CON_LINEA_BASE.format(fecha=linea_base.get("fecha", "fecha no registrada"), factor=factor_linea_base)
        )
    else:
        # Sin referencia no se puede distinguir "presente" de "anormal": se
        # acota la confianza de las fallas que dependen solo de 1x/2x (opcion
        # 1 de D-056). Mismo mecanismo que calidad_medicion invalida.
        hipotesis = aplicar_restriccion_confianza(hipotesis, "linea_base_no_disponible", normativa)
        tope_sin_linea_base = (limite_confianza_por_condicion("linea_base_no_disponible", normativa) or (1.0, None))[0]
        limitaciones.append(LIMITACION_SIN_LINEA_BASE.format(tope=tope_sin_linea_base))
    limitaciones.extend(LIMITACIONES[1:])
    if velocidad["origen"] == "medida":
        limitaciones.append(LIMITACION_VELOCIDAD_MEDIDA.format(**velocidad))
    elif velocidad["origen"] == "estimada":
        if velocidad["metodo"] == "rodamiento":
            falla_texto = {"BPFO": "pista exterior (BPFO)", "BPFI": "pista interior (BPFI)", "BSF": "elemento rodante (BSF)"}[
                velocidad["falla"]
            ]
            limitaciones.append(LIMITACION_VELOCIDAD_ESTIMADA_RODAMIENTO.format(falla_texto=falla_texto, **velocidad))
        elif velocidad["metodo"] == "peine":
            armonicos_texto = ", ".join(f"{k}x" for k in velocidad["armonicos"])
            limitaciones.append(LIMITACION_VELOCIDAD_ESTIMADA_PEINE.format(armonicos_texto=armonicos_texto, **velocidad))
        else:
            limitaciones.append(LIMITACION_VELOCIDAD_ESTIMADA.format(**velocidad))

    verificacion_velocidad = verificar_consistencia_velocidad(hallazgos["1x"], picos_por_eje, rpm_nominal, normativa)
    if verificacion_velocidad["inconsistente"]:
        externo = verificacion_velocidad["pico_externo"]
        pico_1x = verificacion_velocidad["pico_1x"]
        detalle = (
            f"y es {verificacion_velocidad['razon_pico_externo']:g} veces el pico encontrado dentro de ella "
            f"({pico_1x['frecuencia']:.1f} Hz, amplitud {pico_1x['amplitud']:.3g})"
            if pico_1x
            else "y dentro de ella no se encontró ningún pico"
        )
        limitaciones.append(
            AVISO_VELOCIDAD_INCONSISTENTE.format(
                f1=verificacion_velocidad["frecuencia_1x_esperada"],
                rpm=rpm_nominal,
                f_ext=externo["frecuencia"],
                a_ext=externo["amplitud"],
                tol=verificacion_velocidad["tolerancia_pct"],
                detalle=detalle,
            )
        )
    ejes_medidos = ejes_en_datos_fft(datos_fft)
    if len(ejes_medidos) < len(EJES_POSIBLES):
        # D-062: con menos de 3 ejes la comparacion radial/axial no existe, haya o no
        # orientacion declarada (evaluar_direccion devuelve None sin un eje de cada tipo).
        limitaciones.append(
            LIMITACION_EJES_INCOMPLETOS.format(
                cantidad=len(ejes_medidos),
                ejes=", ".join(eje.upper() for eje in ejes_medidos),
                este_ese="ese eje" if len(ejes_medidos) == 1 else "esos ejes",
            )
        )
    else:
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
            evaluar_rodamiento_detallado,
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
            hipotesis_rodamiento, notas_rodamiento = evaluar_rodamiento_detallado(
                datos_crudos, frecuencia_muestreo, rpm_nominal, rodamiento, normativa
            )
            hipotesis += hipotesis_rodamiento
            limitaciones += notas_rodamiento
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
    cambio_linea_base = None
    if datos_crudos is not None and frecuencia_muestreo:
        severidad_iso = clasificar_severidad_peor_eje(
            datos_crudos, frecuencia_muestreo, unidad_señal, potencia_kw, rpm_nominal, tipo_soporte, normativa
        )

        # D-059: criterio relativo para los equipos donde la severidad ISO no
        # aplica (bajo 15 kW) - y complemento de ella en los demas.
        cambio_linea_base = evaluar_cambio_respecto_linea_base(
            datos_crudos, frecuencia_muestreo, unidad_señal, valores_linea_base, normativa
        )
        if cambio_linea_base["aplicable"]:
            limitaciones.append(
                LIMITACION_CAMBIO_LINEA_BASE.format(
                    f_min=cambio_linea_base["banda_hz"][0],
                    f_max=cambio_linea_base["banda_hz"][1],
                    elevado=cambio_linea_base["umbrales"]["elevado"],
                    muy_elevado=cambio_linea_base["umbrales"]["muy_elevado"],
                )
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
        "velocidad": velocidad,
        "verificacion_velocidad": verificacion_velocidad,
        "linea_base": {
            "disponible": bool(valores_linea_base),
            "fecha": linea_base.get("fecha") if valores_linea_base else None,
            "factor_aumento_minimo": factor_linea_base,
        },
        "hipotesis": hipotesis,
        "limitaciones": limitaciones,
        "severidad_iso": severidad_iso,
        "cambio_linea_base": cambio_linea_base,
        "calidad_medicion": calidad_medicion,
    }
