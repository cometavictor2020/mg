"""
Importador de archivos de medicion (D-061, ver PROYECTO.md).

El motor de diagnostico consume un unico formato interno (CSV con las
columnas timestamp, vibracion_x, vibracion_y, vibracion_z y, opcional,
temperatura - ver validacion_medicion.py). Cada investigador entrega sus
datos de otra forma: otros nombres de columna, otro delimitador, sin columna
de tiempo, con canales que no son vibracion. Este modulo adapta ese archivo
al formato interno en tres pasos separados a proposito:

    1. leer_tabla / describir_canales: lectura determinista que describe que
       trae el archivo (columnas, rangos, unidades que dicen los nombres).
    2. proponer_mapeo: una PROPUESTA (heuristica por nombres) de que columna
       es X, Y, Z, tiempo o temperatura, con la unidad y la frecuencia de
       muestreo cuando el archivo las declara. Nunca se aplica sola: la
       persona la confirma o la corrige, y lo que el archivo no dice
       (frecuencia de muestreo, unidad, orientacion de los sensores) queda
       como "pendiente" en vez de inferirse a ciegas.
    3. aplicar_mapeo: conversion determinista y reproducible del archivo
       original al formato interno, segun el mapeo ya confirmado.

El mapeo confirmado es un dato (JSON) que se guarda junto a la medicion y
puede guardarse como plantilla para los archivos siguientes del mismo origen.
Este modulo no convierte unidades: la unidad declarada se registra tal cual.
"""

import hashlib
import io
import re
import unicodedata
import warnings
from datetime import datetime

import numpy as np
import pandas as pd

from backend.procesamiento.ejes import ejes_en_columnas

VERSION_MAPEO = 1

DELIMITADORES = [",", ";", "\t", "|"]
LINEAS_PARA_DETECTAR_FORMATO = 20
FILAS_VISTA_PREVIA = 5
FRECUENCIA_MAXIMA_REPRESENTABLE = 500_000  # timestamps con resolucion de microsegundos

ROLES = ("tiempo", "x", "y", "z", "temperatura")
EJES = ("x", "y", "z")

# Unidades de nombre de columna (lo que va entre parentesis) -> unidad que usa
# la app (las mismas que reconoce severidad_iso.py).
ALIAS_UNIDADES = {
    "m/s2": "m/s2", "m/s^2": "m/s2", "m/s²": "m/s2", "ms2": "m/s2", "m/s/s": "m/s2",
    "cm/s2": "cm/s2", "cm/s^2": "cm/s2", "cm/s²": "cm/s2",
    "g": "g", "gs": "g", "g's": "g",
    "mm/s": "mm/s", "mm/sec": "mm/s",
    "in/s": "in/s", "in/sec": "in/s", "ips": "in/s",
}
FACTOR_UNIDAD_TIEMPO = {"s": 1.0, "sec": 1.0, "seg": 1.0, "seconds": 1.0, "segundos": 1.0, "ms": 1e-3, "us": 1e-6, "µs": 1e-6}

# Frecuencias de muestreo habituales: la estimada desde una columna de tiempo
# redondeada (ej. 2.38E-05 s -> 42016 Hz) se ajusta a la mas cercana si difiere
# menos que TOLERANCIA_FRECUENCIA_ESTANDAR.
FRECUENCIAS_ESTANDAR = [
    1000, 2000, 2560, 4000, 5000, 5120, 8000, 10000, 12000, 16000, 20000, 20480, 22050, 25000, 25600, 32000,
    40000, 42000, 44100, 48000, 50000, 51200, 64000, 96000, 100000, 102400,
]
TOLERANCIA_FRECUENCIA_ESTANDAR = 0.002

PALABRAS_TIEMPO = {"time", "tiempo", "timestamp", "fecha", "date", "datetime", "hora", "t"}
PALABRAS_INDICE = {"index", "indice", "sample", "muestra", "n"}
PALABRAS_TEMPERATURA = {"temp", "temperature", "temperatura", "celsius"}
PALABRAS_OTRO_CANAL = {
    "microphone", "microfono", "mic", "audio", "sound", "sonido", "acoustic", "acustico",
    "current", "corriente", "voltage", "tension", "tacho", "tacometer", "rpm",
}
PALABRAS_SENSOR_NUMERADO = {
    "accelerometer", "acelerometro", "accel", "acc", "acceleration", "aceleracion", "vibracion", "vibration",
    "sensor", "canal", "channel", "ch",
}
EJE_POR_ABREVIATURA = {"ax": "x", "ay": "y", "az": "z", "accx": "x", "accy": "y", "accz": "z", "vx": "x", "vy": "y", "vz": "z"}


# ---------------------------------------------------------------------------
# 1. Lectura
# ---------------------------------------------------------------------------

def _decodificar(contenido):
    for codificacion in ("utf-8-sig", "latin-1"):
        try:
            return contenido.decode(codificacion)
        except UnicodeDecodeError:
            continue


def _es_numero(texto, decimal):
    texto = texto.strip()
    if decimal == ",":
        texto = texto.replace(",", ".")
    try:
        float(texto)
    except ValueError:
        return False
    return True


def _detectar_formato(texto):
    lineas = [linea for linea in texto.splitlines() if linea.strip()][:LINEAS_PARA_DETECTAR_FORMATO]
    if len(lineas) < 2:
        raise ValueError("El archivo no tiene filas de datos que leer.")

    delimitador = None
    mejor = 0
    for candidato in DELIMITADORES:
        conteos = [linea.count(candidato) for linea in lineas]
        if min(conteos) > 0 and len(set(conteos)) == 1 and conteos[0] > mejor:
            delimitador, mejor = candidato, conteos[0]
    if delimitador is None:
        # Un archivo de una sola columna (la señal de un sensor de un eje) no tiene
        # delimitador: ninguna linea contiene ninguno de los candidatos.
        # Se acepta solo si las filas de datos son numeros (la primera linea puede ser el
        # encabezado): un archivo separado por espacios no es una columna de texto.
        sin_delimitador = all(linea.count(candidato) == 0 for linea in lineas for candidato in DELIMITADORES)
        if sin_delimitador and all(_es_numero(linea, ".") for linea in lineas[1:]):
            delimitador = ","
        else:
            raise ValueError(
                "No se pudo detectar el delimitador del archivo (se esperaba ',', ';', tabulación o '|'; "
                "los archivos separados por espacios todavía no se leen)."
            )

    decimal = "."
    if delimitador != ",":
        if any(re.search(r"(^|[{0}])\s*-?\d+,\d+\s*($|[{0}])".format(re.escape(delimitador)), linea) for linea in lineas[1:]):
            decimal = ","

    celdas = lineas[0].split(delimitador)
    encabezado = not all(_es_numero(celda, decimal) for celda in celdas)
    return {"delimitador": delimitador, "decimal": decimal, "encabezado": encabezado}


def leer_tabla(contenido, formato=None):
    """
    Lee el archivo (bytes) como tabla. Si no se pasa "formato" lo detecta
    (delimitador, separador decimal, si trae fila de encabezado); un mapeo
    guardado lo pasa para repetir exactamente la misma lectura. Devuelve
    (DataFrame, formato).
    """
    texto = _decodificar(contenido)
    if formato is None:
        formato = _detectar_formato(texto)

    try:
        datos = pd.read_csv(
            io.StringIO(texto),
            sep=formato["delimitador"],
            decimal=formato["decimal"],
            header=0 if formato["encabezado"] else None,
            skipinitialspace=True,
        )
    except Exception as error:
        raise ValueError(f"No se pudo leer el archivo como tabla: {error}")

    datos = datos.dropna(axis=1, how="all")
    if formato["encabezado"]:
        datos.columns = [str(columna).strip() for columna in datos.columns]
    else:
        datos.columns = [f"columna_{indice + 1}" for indice in range(len(datos.columns))]

    if datos.columns.duplicated().any():
        raise ValueError("El archivo tiene columnas con el mismo nombre; renómbralas antes de importarlo.")
    if len(datos) < 2:
        raise ValueError("El archivo necesita al menos 2 filas de datos para poder analizarse.")

    return datos, formato


def huella_formato(columnas, formato):
    """Identifica la 'forma' de un archivo (nombres de columna en orden + delimitador):
    dos archivos del mismo instrumento/exportador comparten huella y, por tanto, plantilla."""
    texto = formato["delimitador"] + "|" + "|".join(columnas)
    return hashlib.sha1(texto.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# 2. Descripcion y propuesta
# ---------------------------------------------------------------------------

def _normalizar(texto):
    sin_acentos = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode("ascii")
    return sin_acentos.lower()


def _unidad_del_nombre(nombre):
    """Texto entre parentesis o corchetes del nombre de una columna, tal cual."""
    coincidencia = re.search(r"[\(\[]\s*([^\)\]]+?)\s*[\)\]]", str(nombre))
    return coincidencia.group(1).strip().lower() if coincidencia else None


def _tokens(nombre):
    sin_unidad = re.sub(r"[\(\[][^\)\]]*[\)\]]", " ", str(nombre))
    return re.findall(r"[a-z]+|\d+", _normalizar(sin_unidad))


def _eje_del_nombre(tokens):
    candidatos = set()
    for token in tokens:
        if token in EJES:
            candidatos.add(token)
        elif token in EJE_POR_ABREVIATURA:
            candidatos.add(EJE_POR_ABREVIATURA[token])
    return candidatos.pop() if len(candidatos) == 1 else None


def _paso_en_segundos(serie, factor):
    """Paso medio entre muestras de una columna de tiempo que no decrece, en segundos. Se calcula
    sobre todo el tramo y no entre vecinos: un tiempo redondeado (ej. 3 cifras) repite valores."""
    valores = serie.to_numpy(dtype=float)
    if len(valores) < 2 or not np.all(np.diff(valores) >= 0) or valores[-1] <= valores[0]:
        return None
    return float((valores[-1] - valores[0]) / (len(valores) - 1) * factor)


def _ajustar_a_frecuencia_estandar(frecuencia):
    for estandar in FRECUENCIAS_ESTANDAR:
        if abs(frecuencia - estandar) / estandar <= TOLERANCIA_FRECUENCIA_ESTANDAR:
            return estandar, estandar != round(frecuencia)
    return round(frecuencia), False


def _es_fecha_hora(serie):
    if pd.api.types.is_numeric_dtype(serie):
        return False
    muestra = serie.head(200)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return bool(pd.to_datetime(muestra, errors="coerce").notna().all())


def _redondear(valor):
    return None if pd.isna(valor) else round(float(valor), 6)


def describir_canales(datos):
    canales = []
    for indice, nombre in enumerate(datos.columns):
        serie = datos[nombre]
        canal = {"nombre": nombre, "indice": indice, "unidad_en_nombre": _unidad_del_nombre(nombre)}
        if pd.api.types.is_numeric_dtype(serie):
            canal.update(
                tipo="numerico",
                minimo=_redondear(serie.min()),
                maximo=_redondear(serie.max()),
                media=_redondear(serie.mean()),
                desviacion=_redondear(serie.std()),
                creciente=bool(serie.is_monotonic_increasing and serie.is_unique),
            )
        elif _es_fecha_hora(serie):
            canal["tipo"] = "fecha_hora"
        else:
            canal["tipo"] = "texto"
        canales.append(canal)
    return canales


def proponer_mapeo(datos, canales, formato):
    """
    Propuesta de mapeo para un archivo ya leido. No modifica nada ni asume lo
    que el archivo no dice: lo que falta se devuelve en "pendientes".
    """
    notas = []
    columnas = {rol: None for rol in ROLES}
    ignoradas = set()
    por_nombre = {canal["nombre"]: canal for canal in canales}

    # Nativo: ya tiene timestamp y las columnas vibracion_<eje> de un sensor de 3 ejes o de uno.
    ejes_nativos = ejes_en_columnas(datos.columns)
    es_nativo = "timestamp" in datos.columns and ejes_nativos in (["x"], list(EJES))
    if es_nativo:
        columnas["tiempo"] = "timestamp"
        for eje in ejes_nativos:
            columnas[eje] = f"vibracion_{eje}"
        if "temperatura" in datos.columns:
            columnas["temperatura"] = "temperatura"
        return {
            "formato_nativo": True,
            "columnas": columnas,
            "unidad": None,
            "frecuencia_muestreo": None,
            "origen_frecuencia": None,
            "unidad_tiempo": "s",
            "asignacion_ejes": "nombre",
            "confianza": "alta",
            "notas": ["El archivo ya tiene el formato interno de MotorGuardian; no necesita adaptarse."],
            "pendientes": [],
        }

    # Columna de tiempo / indice / temperatura / otros canales, por nombre.
    for canal in canales:
        tokens = _tokens(canal["nombre"])
        if not tokens:
            continue
        if columnas["tiempo"] is None and tokens[0] in PALABRAS_TIEMPO and canal["tipo"] in ("numerico", "fecha_hora"):
            columnas["tiempo"] = canal["nombre"]
        elif columnas["temperatura"] is None and PALABRAS_TEMPERATURA & set(tokens) and canal["tipo"] == "numerico":
            columnas["temperatura"] = canal["nombre"]
        elif tokens[0] in PALABRAS_INDICE or PALABRAS_OTRO_CANAL & set(tokens):
            ignoradas.add(canal["nombre"])

    ocupadas = {nombre for nombre in columnas.values() if nombre} | ignoradas
    candidatas = [c for c in canales if c["tipo"] == "numerico" and c["nombre"] not in ocupadas]

    # Ejes: 1) nombre con el eje (vibracion_x, ax, ...), 2) sensores numerados, 3) posicion.
    asignacion = None
    for canal in candidatas:
        eje = _eje_del_nombre(_tokens(canal["nombre"]))
        if eje and columnas[eje] is None:
            columnas[eje] = canal["nombre"]
    if ejes_del_mapeo({"columnas": columnas}) in (("x",), EJES):
        asignacion = "nombre"

    if asignacion is None and not any(columnas[eje] for eje in EJES):
        numerados = []
        for canal in candidatas:
            tokens = _tokens(canal["nombre"])
            numeros = [int(token) for token in tokens if token.isdigit()]
            if PALABRAS_SENSOR_NUMERADO & set(tokens) and len(numeros) == 1:
                numerados.append((numeros[0], canal["nombre"]))
        if len(numerados) == 3 and len({n for n, _ in numerados}) == 3:
            for eje, (_, nombre) in zip(EJES, sorted(numerados)):
                columnas[eje] = nombre
            asignacion = "numeracion"
            notas.append(
                "Los canales vienen numerados: se asignaron a X, Y y Z según ese orden. El archivo no declara la "
                "orientación de cada sensor; confirma que la asignación corresponde a tu montaje."
            )
        elif len(candidatas) == 3:
            for eje, canal in zip(EJES, candidatas):
                columnas[eje] = canal["nombre"]
            asignacion = "posicion"
            notas.append(
                "El archivo no nombra los ejes: se tomaron sus 3 columnas numéricas en orden como X, Y y Z. "
                "Verifica la asignación."
            )
        elif len(candidatas) == 1:
            columnas["x"] = candidatas[0]["nombre"]
            asignacion = "posicion"
            notas.append(
                "El archivo trae un solo canal de vibración: se asignó a X. Corresponde a un sensor de un eje; "
                "verifica que sea la señal de vibración."
            )

    sin_asignar = [c["nombre"] for c in candidatas if c["nombre"] not in columnas.values()]
    if sin_asignar and asignacion is not None:
        notas.append("Columnas numéricas sin asignar (quedan como «No usar»): " + ", ".join(sin_asignar) + ".")

    if ignoradas:
        notas.append("No se usarán como vibración: " + ", ".join(sorted(ignoradas)) + ".")

    # Unidad: solo si las tres columnas de vibracion la declaran y coinciden.
    unidades = {
        ALIAS_UNIDADES.get(por_nombre[columnas[eje]]["unidad_en_nombre"] or "") for eje in EJES if columnas[eje]
    }
    unidad = unidades.pop() if len(unidades) == 1 and None not in unidades else None
    if unidad:
        notas.append(f"La unidad ({unidad}) se tomó del nombre de las columnas; el sistema no convierte unidades.")

    # Frecuencia de muestreo: solo si hay una columna de tiempo interpretable.
    frecuencia = origen = None
    unidad_tiempo = "s"
    nombre_tiempo = columnas["tiempo"]
    if nombre_tiempo:
        canal_tiempo = por_nombre[nombre_tiempo]
        paso = None
        if canal_tiempo["tipo"] == "fecha_hora":
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                segundos = pd.to_datetime(datos[nombre_tiempo]).astype("int64").to_numpy() / 1e9
            if len(segundos) > 1 and np.all(np.diff(segundos) >= 0) and segundos[-1] > segundos[0]:
                paso = float((segundos[-1] - segundos[0]) / (len(segundos) - 1))
        elif canal_tiempo["tipo"] == "numerico":
            unidad_declarada = canal_tiempo["unidad_en_nombre"]
            factor = FACTOR_UNIDAD_TIEMPO.get(unidad_declarada or "")
            if factor:
                unidad_tiempo = {1.0: "s", 1e-3: "ms", 1e-6: "us"}[factor]
            paso = _paso_en_segundos(datos[nombre_tiempo], factor or 1.0)
            if paso is not None and factor is None and paso >= 1:
                paso = None
                notas.append(
                    f"La columna '{nombre_tiempo}' no declara su unidad y sus pasos son ≥ 1: podría ser un índice o "
                    "milisegundos, así que no se estimó la frecuencia de muestreo."
                )
        if paso:
            estimada = 1 / paso
            if 1 <= estimada <= FRECUENCIA_MAXIMA_REPRESENTABLE:
                frecuencia, ajustada = _ajustar_a_frecuencia_estandar(estimada)
                origen = "columna_tiempo"
                notas.append(
                    f"La frecuencia de muestreo ({frecuencia} Hz) se estimó desde la columna '{nombre_tiempo}'"
                    + (" y se ajustó a la frecuencia estándar más cercana (el tiempo del archivo viene redondeado)." if ajustada else ".")
                )

    pendientes = []
    if ejes_del_mapeo({"columnas": columnas}) not in (("x",), EJES):
        pendientes.append("ejes")
    if unidad is None:
        pendientes.append("unidad")
    if frecuencia is None:
        pendientes.append("frecuencia_muestreo")

    confianza = {"nombre": "alta", "numeracion": "media", "posicion": "baja"}.get(asignacion, "baja")
    if columnas["tiempo"] is None:
        notas.append(
            "El archivo no trae columna de tiempo: la columna 'timestamp' se generará a partir de la frecuencia de muestreo."
        )

    return {
        "formato_nativo": False,
        "columnas": columnas,
        "unidad": unidad,
        "frecuencia_muestreo": frecuencia,
        "origen_frecuencia": origen,
        "unidad_tiempo": unidad_tiempo,
        "asignacion_ejes": asignacion,
        "confianza": confianza,
        "notas": notas,
        "pendientes": pendientes,
    }


def analizar_archivo(contenido, nombre_archivo=None):
    """Lectura + descripcion + propuesta, para mostrar antes de confirmar nada.
    Si el contenido es solo el inicio de un archivo grande, la ultima linea (posiblemente
    cortada) se descarta. Un .mat (D-063) se analiza con importador_mat; el resto, como
    tabla de texto."""
    if (nombre_archivo or "").lower().endswith(".mat"):
        from backend.procesamiento.importador_mat import analizar_mat

        return analizar_mat(contenido)

    if not contenido.endswith(b"\n") and b"\n" in contenido:
        contenido = contenido[: contenido.rfind(b"\n") + 1]

    datos, formato = leer_tabla(contenido)
    canales = describir_canales(datos)
    propuesta = proponer_mapeo(datos, canales, formato)
    vista = datos.head(FILAS_VISTA_PREVIA)

    return {
        "formato": formato,
        "huella": huella_formato(list(datos.columns), formato),
        "filas_analizadas": len(datos),
        "canales": canales,
        "vista_previa": {
            "columnas": list(vista.columns),
            "filas": [[None if pd.isna(valor) else valor for valor in fila] for fila in vista.to_numpy().tolist()],
        },
        "propuesta": propuesta,
    }


# ---------------------------------------------------------------------------
# 3. Conversion
# ---------------------------------------------------------------------------

def ejes_del_mapeo(mapeo):
    """Ejes con columna asignada en el mapeo, en orden x, y, z."""
    return tuple(eje for eje in EJES if mapeo["columnas"].get(eje))


def validar_mapeo(mapeo, ejes=None):
    """
    Errores de forma del mapeo (lista de textos; vacia si esta bien). `ejes` son los ejes
    que tiene el sensor al que se carga la medicion (D-062): deben estar todos asignados y
    ninguno mas. Sin `ejes` (p. ej. al guardar una plantilla, que no sabe de que sensor
    sera) se acepta un mapeo de un eje (X) o de tres (X, Y y Z).
    """
    errores = []
    if not isinstance(mapeo, dict) or not isinstance(mapeo.get("columnas"), dict) or not isinstance(mapeo.get("formato"), dict):
        return ["El mapeo de importación está incompleto (faltan 'formato' o 'columnas')."]

    columnas = mapeo["columnas"]
    if ejes is None:
        if ejes_del_mapeo(mapeo) not in (("x",), EJES):
            errores.append("Asigna una columna a X (sensor de un eje) o a X, Y y Z (sensor de tres ejes).")
    else:
        faltantes = [eje.upper() for eje in ejes if not columnas.get(eje)]
        if faltantes:
            errores.append("Falta asignar una columna a: " + ", ".join(faltantes) + ".")
        sobrantes = [eje.upper() for eje in EJES if columnas.get(eje) and eje not in ejes]
        if sobrantes:
            errores.append(
                f"El sensor no tiene el eje {', '.join(sobrantes)}: deja esas columnas como «No usar». "
                "Un sensor de un solo eje se carga con una única columna de vibración (X)."
            )
    usadas = [columnas[rol] for rol in ROLES if columnas.get(rol)]
    if len(usadas) != len(set(usadas)):
        errores.append("Una misma columna no puede cumplir dos roles distintos.")
    return errores


def aplicar_mapeo(contenido, mapeo, frecuencia_muestreo=None, inicio=None, ejes=None):
    """
    Convierte el archivo original (bytes) al CSV interno, segun el mapeo
    confirmado. `ejes` son los del sensor destino (D-062; sin ellos, los que el
    mapeo asigna). Devuelve (csv_bytes, resumen). La columna timestamp se genera
    de forma uniforme a partir de la frecuencia de muestreo (el motor de
    diagnostico usa esa frecuencia, no los timestamps): empieza en la primera
    fecha del archivo si trae una columna de fecha/hora, y si no en "inicio"
    (por defecto, ahora). Lanza ValueError con un mensaje claro si algo no calza.
    """
    if es_mapeo_mat(mapeo):
        from backend.procesamiento.importador_mat import aplicar_mapeo_mat

        return aplicar_mapeo_mat(contenido, mapeo, frecuencia_muestreo, inicio, ejes)

    errores = validar_mapeo(mapeo, ejes)
    if errores:
        raise ValueError(" ".join(errores))
    ejes = tuple(ejes) if ejes is not None else ejes_del_mapeo(mapeo)

    datos, _ = leer_tabla(contenido, mapeo["formato"])
    columnas = mapeo["columnas"]

    ausentes = [nombre for nombre in (columnas.get(rol) for rol in ROLES) if nombre and nombre not in datos.columns]
    if ausentes:
        raise ValueError(
            "El archivo no tiene la(s) columna(s) que indica el mapeo: " + ", ".join(ausentes) + ". "
            "¿Es el mismo formato con el que se confirmó el mapeo?"
        )

    frecuencia = validar_frecuencia(frecuencia_muestreo or mapeo.get("frecuencia_muestreo"))

    salida = {}
    for rol in (*ejes, "temperatura"):
        nombre = columnas.get(rol)
        if not nombre:
            continue
        serie = pd.to_numeric(datos[nombre], errors="coerce")
        invalidos = int(serie.isna().sum())
        if invalidos:
            raise ValueError(f"La columna '{nombre}' tiene {invalidos} valor(es) no numérico(s) o vacío(s).")
        salida["vibracion_" + rol if rol in EJES else rol] = serie.to_numpy()

    comienzo = pd.Timestamp(inicio or datetime.utcnow())
    nombre_tiempo = columnas.get("tiempo")
    if nombre_tiempo and not pd.api.types.is_numeric_dtype(datos[nombre_tiempo]):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            primera = pd.to_datetime(datos[nombre_tiempo].iloc[0], errors="coerce")
        if pd.isna(primera):
            raise ValueError(f"La columna de tiempo '{nombre_tiempo}' no se puede interpretar como fecha/hora.")
        comienzo = primera

    return csv_interno(salida, len(datos), frecuencia, comienzo)


def es_mapeo_mat(mapeo):
    return isinstance(mapeo, dict) and isinstance(mapeo.get("formato"), dict) and mapeo["formato"].get("tipo") == "mat"


def validar_frecuencia(frecuencia):
    if not frecuencia or frecuencia <= 0:
        raise ValueError("Falta la frecuencia de muestreo: el archivo no la declara y no se indicó una.")
    if frecuencia > FRECUENCIA_MAXIMA_REPRESENTABLE:
        raise ValueError(
            f"La frecuencia de muestreo ({frecuencia} Hz) supera la que pueden representar los timestamps "
            f"({FRECUENCIA_MAXIMA_REPRESENTABLE} Hz)."
        )
    return frecuencia


def csv_interno(salida, cantidad, frecuencia, comienzo):
    """
    CSV del formato interno: timestamp uniforme (desde `comienzo`, a 1/frecuencia) mas las
    columnas de `salida` ({"vibracion_x": arreglo, ..., "temperatura": arreglo}). Comun a todos
    los formatos de origen (tabla de texto, .mat). Devuelve (csv_bytes, resumen).
    """
    instantes = comienzo + pd.to_timedelta(np.arange(cantidad) / frecuencia, unit="s")
    tabla = pd.DataFrame({"timestamp": instantes.strftime("%Y-%m-%d %H:%M:%S.%f"), **salida})

    resumen = {"filas": cantidad, "frecuencia_muestreo": int(frecuencia), "duracion_segundos": round(cantidad / frecuencia, 3)}
    return tabla.to_csv(index=False).encode("utf-8"), resumen
