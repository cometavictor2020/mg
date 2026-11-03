"""
Validacion de archivos CSV antes de aceptarlos como Medicion (D-040).

Diseño extensible a proposito: cada "perfil" de validacion describe
como verificar la estructura/consistencia de un archivo para una
familia de sensor. Hoy existen "vibracion_triaxial" (columnas
vibracion_x/y/z) y, desde D-062, "vibracion_uniaxial" (solo vibracion_x):
el motor de diagnostico trabaja con los ejes que trae el archivo (ver
backend/procesamiento/ejes.py), asi que ambos se procesan igual. Agregar un
perfil nuevo para otra familia (temperatura, electrico, aceite, etc.)
es agregar una funcion de verificacion y una entrada en
PERFILES_VALIDACION, sin tocar el resto del pipeline de carga.

Limitaciones deliberadas de esta primera version, a resolver antes de
considerar terminado el trabajo de carga de mediciones (ver D-040 e
Ideas futuras en PROYECTO.md):
    - Solo existe el perfil "vibracion_triaxial". Sensores de otras
      familias se rechazan explicitamente (mensaje claro), no se
      aceptan "a ciegas" ni se ignora el problema.
    - La unidad la declara el operador al cargar el archivo y se
      registra tal cual (Medicion.unidad) - no hay todavia un chequeo
      heuristico de que los valores numericos correspondan realmente a
      esa unidad (ej. diferenciar valores en "g" de valores en "m/s2").
"""

import pandas as pd

from backend.procesamiento.ejes import EJES_POSIBLES

COLUMNAS_VIBRACION_TRIAXIAL = ["timestamp", "vibracion_x", "vibracion_y", "vibracion_z"]
COLUMNA_TEMPERATURA_OPCIONAL = "temperatura"

DELIMITADORES_SOPORTADOS = [",", ";"]


class ErrorValidacionMedicion(Exception):
    """Agrupa todos los errores encontrados, no solo el primero -
    para que el operador pueda corregir el archivo de una vez."""

    def __init__(self, errores):
        self.errores = errores
        super().__init__("; ".join(errores))


def detectar_delimitador(ruta_archivo):
    with open(ruta_archivo, encoding="utf-8") as archivo:
        primera_linea = archivo.readline()

    conteos = {delimitador: primera_linea.count(delimitador) for delimitador in DELIMITADORES_SOPORTADOS}
    delimitador_mas_frecuente = max(conteos, key=conteos.get)

    if conteos[delimitador_mas_frecuente] == 0:
        return None

    return delimitador_mas_frecuente


def _validar_columna_numerica(datos, columna, errores):
    no_numericos = pd.to_numeric(datos[columna], errors="coerce").isna().sum()
    if no_numericos:
        errores.append(f"La columna '{columna}' tiene {no_numericos} valor(es) no numerico(s)")


def validar_vibracion(datos, ejes):
    """Validacion de una señal de vibracion con los ejes dados (D-062): timestamp y una
    columna vibracion_<eje> por cada eje del sensor. Los perfiles de abajo la fijan para
    sensores de 3 ejes (el caso original, D-040) y de uno."""
    errores = []

    columnas_obligatorias = ["timestamp"] + [f"vibracion_{eje}" for eje in ejes]
    columnas_faltantes = [c for c in columnas_obligatorias if c not in datos.columns]
    if columnas_faltantes:
        errores.append(f"Faltan columnas obligatorias: {', '.join(columnas_faltantes)}")
        return errores

    # El motor trabaja con los ejes que hay en el archivo: una columna de un eje que el
    # sensor no tiene haria que se evaluara como si lo midiera.
    sobrantes = [f"vibracion_{eje}" for eje in EJES_POSIBLES if eje not in ejes and f"vibracion_{eje}" in datos.columns]
    if sobrantes:
        errores.append(
            f"El archivo trae columnas de ejes que este sensor no tiene: {', '.join(sobrantes)}. "
            "Deja solo las de los ejes del sensor."
        )
        return errores

    if len(datos) < 2:
        errores.append("El archivo necesita al menos 2 filas de datos para poder analizarse")
        return errores

    for eje in ejes:
        _validar_columna_numerica(datos, f"vibracion_{eje}", errores)

    if COLUMNA_TEMPERATURA_OPCIONAL in datos.columns:
        _validar_columna_numerica(datos, COLUMNA_TEMPERATURA_OPCIONAL, errores)

    timestamps = pd.to_datetime(datos["timestamp"], errors="coerce")
    if timestamps.isna().any():
        errores.append("Hay valores de 'timestamp' que no se pueden interpretar como fecha/hora")
    else:
        if not timestamps.is_monotonic_increasing:
            errores.append("Los valores de 'timestamp' no estan ordenados de forma creciente")
        if timestamps.duplicated().any():
            errores.append("Hay valores de 'timestamp' duplicados")

    return errores


def validar_vibracion_triaxial(datos):
    """Perfil de validacion para acelerometros triaxiales (D-040): timestamp,
    vibracion_x, vibracion_y y vibracion_z - mismas columnas y mismos mensajes de siempre."""
    return validar_vibracion(datos, ("x", "y", "z"))


def validar_vibracion_uniaxial(datos):
    """Perfil para sensores de un eje (D-062): timestamp y vibracion_x. El unico eje
    del sensor se llama X en el archivo; su orientacion real (radial, axial) se declara
    en Sensor.configuracion, no en el nombre de la columna."""
    return validar_vibracion(datos, ("x",))


PERFILES_VALIDACION = {
    "vibracion_triaxial": validar_vibracion_triaxial,
    "vibracion_uniaxial": validar_vibracion_uniaxial,
}


def validar_archivo_medicion(ruta_archivo, perfil):
    """
    Lee y valida el archivo. Lanza ErrorValidacionMedicion (con todos
    los errores encontrados) si algo no calza; si no, devuelve el
    DataFrame ya leido (para no tener que releerlo despues).
    """
    if perfil not in PERFILES_VALIDACION:
        raise ErrorValidacionMedicion(
            [
                f"Todavia no existe un perfil de validacion para '{perfil}'. "
                "Por ahora solo se pueden cargar mediciones de vibracion de 1 o 3 ejes."
            ]
        )

    delimitador = detectar_delimitador(ruta_archivo)
    if delimitador is None:
        raise ErrorValidacionMedicion(
            ["No se pudo detectar el delimitador del archivo (se esperaba ',' o ';')"]
        )

    try:
        datos = pd.read_csv(ruta_archivo, sep=delimitador)
    except Exception as error:
        raise ErrorValidacionMedicion([f"No se pudo leer el archivo como CSV: {error}"])

    errores = PERFILES_VALIDACION[perfil](datos)
    if errores:
        raise ErrorValidacionMedicion(errores)

    return datos


def determinar_perfil(sensor):
    """
    Que perfil de validacion aplica a este sensor, segun su tipo. Punto
    de extension: agregar mas condiciones aqui a medida que se agreguen
    perfiles nuevos a PERFILES_VALIDACION.
    """
    tipo_sensor = sensor.tipo_sensor
    if not tipo_sensor:
        return None

    ejes = (sensor.configuracion or {}).get("ejes", [])
    if tipo_sensor.familia == "Vibracion" and set(ejes) == {"X", "Y", "Z"}:
        return "vibracion_triaxial"
    if tipo_sensor.familia == "Vibracion" and set(ejes) == {"X"}:
        return "vibracion_uniaxial"

    return None


def ejes_del_perfil(perfil):
    """Ejes de vibracion que el perfil exige (para adaptar un archivo con el importador)."""
    return {"vibracion_triaxial": ("x", "y", "z"), "vibracion_uniaxial": ("x",)}.get(perfil)
