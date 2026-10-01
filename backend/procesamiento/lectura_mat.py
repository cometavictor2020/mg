"""
Lectura de archivos .mat de Matlab.

Modulo separado a proposito (D-044, ver PROYECTO.md) del resto de la
lectura de datos (lectura_csv.py): un .mat no es una medicion real de
un equipo de planta, es un archivo externo (tipicamente un dataset
publico de referencia, como el CWRU Bearing Data Center, usado para
validar el motor de diagnostico de rodamientos contra un caso con
resultado ya publicado - paper de Tyagi & Panigrahi, 2017, Journal of
Computational Design and Engineering). Por eso vive fuera del modelo
Equipo/Sensor/Medicion en vez de intentar encajarlo ahi.

Generico a proposito (D-045, ver PROYECTO.md): no asume que el archivo
viene de CWRU ni que trae una geometria de rodamiento en particular -
inspeccionar_mat() describe cualquier .mat sin adivinar nada, y
leer_señal_cwru() es solo una autodeteccion de conveniencia para el
caso comun (activada si quien sube el archivo no elige manualmente una
variable). Ningun .mat declara su propia frecuencia de muestreo dentro
del archivo - por eso quien lo sube siempre debe indicarla.
"""

import io

import numpy as np
from scipy.io import loadmat


def cargar_mat(contenido_bytes):
    """Carga un .mat y descarta las claves internas de Matlab (__header__, etc.)."""
    datos = loadmat(io.BytesIO(contenido_bytes))
    return {nombre: valor for nombre, valor in datos.items() if not nombre.startswith("__")}


def inspeccionar_mat(contenido_bytes):
    """
    Describe el contenido de CUALQUIER archivo .mat, sin asumir ninguna
    convencion de nombres (a diferencia de leer_señal_cwru) - pensado
    para que quien sube el archivo vea que hay adentro antes de elegir
    que variable analizar, en vez de que el sistema lo adivine a ciegas.

    Devuelve una lista de {"nombre", "forma", "tipo_dato",
    "cantidad_elementos", y si es numerico "vista_previa" (primeros
    valores) + "minimo"/"maximo" cuando hay mas de 10 elementos}.
    """
    variables = cargar_mat(contenido_bytes)

    resultado = []
    for nombre, valor in variables.items():
        arreglo = np.asarray(valor)
        info = {
            "nombre": nombre,
            "forma": list(arreglo.shape),
            "tipo_dato": str(arreglo.dtype),
            "cantidad_elementos": int(arreglo.size),
        }

        if np.issubdtype(arreglo.dtype, np.number) and arreglo.size > 0:
            plano = arreglo.flatten()
            if plano.size <= 10:
                info["vista_previa"] = [round(float(v), 6) for v in plano]
            else:
                info["vista_previa"] = [round(float(v), 6) for v in plano[:5]]
                info["minimo"] = round(float(plano.min()), 6)
                info["maximo"] = round(float(plano.max()), 6)

        resultado.append(info)

    return resultado


def extraer_variable(contenido_bytes, nombre_variable):
    """Extrae una variable puntual por su nombre exacto (seleccion manual del usuario)."""
    variables = cargar_mat(contenido_bytes)
    if nombre_variable not in variables:
        raise ValueError(f"La variable '{nombre_variable}' no existe en el archivo.")
    return np.asarray(variables[nombre_variable]).flatten().astype(float)


def leer_señal_cwru(contenido_bytes):
    """
    Autodeteccion de conveniencia para archivos con la convencion de
    nombres de CWRU: busca la señal de vibracion y la velocidad (RPM)
    sin depender de un nombre de archivo especifico (ej. "135.mat") -
    los nombres de sus variables cambian con cada archivo (X135_DE_time,
    X174_DE_time, ...), pero siguen el mismo patron documentado por
    CWRU: "<numero>_DE_time" para el acelerometro del lado de
    accionamiento (Drive End - el que usa el paper), "<numero>_FE_time"
    para el del lado del ventilador (se usa solo si no hay DE_time), y
    "<numero>RPM" para la velocidad.

    No es la unica forma de leer un archivo: si quien lo sube indica
    manualmente que variable usar (D-045), esta funcion no se llama.

    Devuelve {"señal": array 1D de floats, "variable_señal": nombre
    encontrado, "rpm": float o None si el archivo no trae RPM}.
    """
    variables = cargar_mat(contenido_bytes)

    nombre_señal = next((n for n in variables if "DE_time" in n), None)
    if nombre_señal is None:
        nombre_señal = next((n for n in variables if "FE_time" in n), None)
    if nombre_señal is None:
        raise ValueError(
            "El archivo no tiene ninguna variable de señal reconocible automaticamente (se "
            "esperaba un nombre que contenga 'DE_time' o 'FE_time', como los nombra CWRU) - "
            "usa \"Ver metadata del archivo\" y elige la variable manualmente."
        )

    nombre_rpm = next((n for n in variables if "RPM" in n.upper()), None)
    rpm = float(variables[nombre_rpm].flatten()[0]) if nombre_rpm else None

    return {
        "señal": variables[nombre_señal].flatten().astype(float),
        "variable_señal": nombre_señal,
        "rpm": rpm,
    }
