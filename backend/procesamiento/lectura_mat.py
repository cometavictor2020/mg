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
variable). Los archivos de CWRU no declaran su frecuencia de muestreo dentro
del archivo - por eso, por defecto, quien lo sube la indica; otros datasets
(como los del MFPT, que guardan una estructura "bearing" con gs, sr, rate y
load) si la traen, y entonces puede elegirse la variable que la contiene.

Estructuras de Matlab (D-060): inspeccionar_mat() y extraer_variable() abren
las estructuras en rutas "variable.campo", y sugerir_lectura() propone que
variable es la señal, la frecuencia de muestreo y la velocidad de giro. Es
solo una propuesta: nada se aplica sin que quien sube el archivo lo
confirme (mismo criterio de "nunca adivinar" de D-044).
"""

import io

import numpy as np
from scipy.io import loadmat


def cargar_mat(contenido_bytes):
    """Carga un .mat y descarta las claves internas de Matlab (__header__, etc.)."""
    datos = loadmat(io.BytesIO(contenido_bytes))
    return {nombre: valor for nombre, valor in datos.items() if not nombre.startswith("__")}


LIMITE_PROFUNDIDAD = 6
LIMITE_ELEMENTOS_COLECCION = 20


def _desenvolver(valor):
    """loadmat guarda cada campo de una estructura (y cada celda) como un arreglo de objetos de 1 elemento: se lo quita."""
    while isinstance(valor, np.ndarray) and valor.dtype == object and valor.size == 1:
        valor = valor.flat[0]
    return valor


def _hojas(nombre, valor, profundidad=0):
    """
    Recorre una variable de un .mat y devuelve pares (ruta, arreglo): una
    variable comun es su propia unica hoja (la ruta es su nombre, sin
    cambios); una ESTRUCTURA de Matlab (como la variable "bearing" de los
    archivos del MFPT, con los campos gs, sr, rate y load) se abre en una
    hoja por campo con ruta "nombre.campo"; una celda o un arreglo de
    estructuras, en "nombre{i}" / "nombre[i].campo". Se limitan la
    profundidad y la cantidad de elementos por si el archivo es enorme.
    """
    valor = _desenvolver(valor)

    # Un arreglo vacio (de objetos o de estructuras) se describe tal cual, como
    # siempre, en vez de desaparecer de la lista.
    if profundidad < LIMITE_PROFUNDIDAD and isinstance(valor, np.ndarray) and valor.size > 0:
        if valor.dtype.names is not None:
            for indice, elemento in enumerate(valor.flat):
                if indice >= LIMITE_ELEMENTOS_COLECCION:
                    break
                prefijo = nombre if valor.size == 1 else f"{nombre}[{indice}]"
                for campo in valor.dtype.names:
                    yield from _hojas(f"{prefijo}.{campo}", elemento[campo], profundidad + 1)
            return

        if valor.dtype == object:
            for indice, elemento in enumerate(valor.flat):
                if indice >= LIMITE_ELEMENTOS_COLECCION:
                    break
                yield from _hojas(f"{nombre}{{{indice}}}", elemento, profundidad + 1)
            return

    yield nombre, np.asarray(valor)


def _todas_las_hojas(variables):
    return {ruta: arreglo for nombre, valor in variables.items() for ruta, arreglo in _hojas(nombre, valor)}


def leer_hojas_mat(contenido_bytes):
    """Todas las variables numericas o no de un .mat como {ruta: arreglo}, con las estructuras y
    celdas ya abiertas (mismas rutas que inspeccionar_mat). Lo usa el importador (D-063)."""
    return _todas_las_hojas(cargar_mat(contenido_bytes))


def inspeccionar_mat(contenido_bytes):
    """
    Describe el contenido de CUALQUIER archivo .mat, sin asumir ninguna
    convencion de nombres (a diferencia de leer_señal_cwru) - pensado
    para que quien sube el archivo vea que hay adentro antes de elegir
    que variable analizar, en vez de que el sistema lo adivine a ciegas.

    Devuelve una lista de {"nombre", "forma", "tipo_dato",
    "cantidad_elementos", y si es numerico "vista_previa" (primeros
    valores) + "minimo"/"maximo" cuando hay mas de 10 elementos}.

    Las variables comunes salen igual que siempre. Una estructura de
    Matlab se abre en una fila por campo, con "nombre" = su ruta
    ("bearing.gs"), que es lo que se entrega despues a extraer_variable().
    """
    variables = cargar_mat(contenido_bytes)

    resultado = []
    for nombre, arreglo in _todas_las_hojas(variables).items():
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
    """
    Extrae una variable puntual por su nombre exacto (seleccion manual del
    usuario). Si es un campo de una estructura, el nombre es su ruta, tal
    como la entrega inspeccionar_mat() ("bearing.gs").
    """
    variables = cargar_mat(contenido_bytes)
    if nombre_variable in variables:
        return np.asarray(variables[nombre_variable]).flatten().astype(float)

    hojas = _todas_las_hojas(variables)
    if nombre_variable not in hojas:
        raise ValueError(f"La variable '{nombre_variable}' no existe en el archivo.")

    arreglo = hojas[nombre_variable]
    if not np.issubdtype(arreglo.dtype, np.number):
        raise ValueError(f"La variable '{nombre_variable}' no es numérica: no se puede usar como señal ni como dato.")
    return arreglo.flatten().astype(float)


# Nombres (en minuscula y sin separadores) con que los archivos suelen
# declarar su frecuencia de muestreo y su velocidad de giro. Solo alimentan
# las SUGERENCIAS de sugerir_lectura(): nunca se aplica nada sin que quien
# sube el archivo lo confirme.
NOMBRES_FRECUENCIA_MUESTREO = {
    "sr", "fs", "fsamp", "samplerate", "samplingrate", "samplingfrequency",
    "samplefrequency", "sampfreq", "frecuenciamuestreo", "frecuenciademuestreo",
}
NOMBRES_VELOCIDAD = {
    "rate", "speed", "shaftspeed", "shaftrate", "inputshaftrate", "rps", "velocidad", "velocidadgiro",
}
# Un eje de maquina industrial gira entre unas decenas de r/min y unas
# decenas de miles; un valor tan pequeño casi siempre es Hz (rev/s).
VELOCIDAD_MAXIMA_PROBABLE_EN_HZ = 200
MUESTRAS_MINIMAS_SEÑAL = 1000


def _normalizar(nombre):
    ultimo = nombre.split(".")[-1].split("{")[0].split("[")[0]
    return "".join(c for c in ultimo.lower() if c.isalnum())


def sugerir_lectura(variables_inspeccionadas):
    """
    A partir de la salida de inspeccionar_mat(), propone (sin aplicar nada)
    que variable es la señal, cual la frecuencia de muestreo y cual la
    velocidad de giro, para archivos que no siguen la convencion de CWRU.
    Devuelve:
        {"variable_señal", "señal_candidatas", "variable_frecuencia_muestreo",
         "variable_rpm", "unidad_rpm", "valores", "notas"}
    con None donde no hay una propuesta clara. Si hay varios vectores de
    igual tamaño (como X135_DE_time y X135_FE_time de CWRU) no elige ninguno:
    esos archivos ya los cubre la autodeteccion de leer_señal_cwru().
    """
    notas = []

    vectores = [
        v for v in variables_inspeccionadas
        if v.get("vista_previa") is not None
        and v["cantidad_elementos"] >= MUESTRAS_MINIMAS_SEÑAL
        and sum(1 for dimension in v["forma"] if dimension > 1) <= 1
    ]
    variable_señal, candidatas = None, []
    if vectores:
        mayor = max(v["cantidad_elementos"] for v in vectores)
        candidatas = [v["nombre"] for v in vectores if v["cantidad_elementos"] == mayor]
        if len(candidatas) == 1:
            variable_señal = candidatas[0]
        else:
            notas.append("Hay varias variables con el mismo largo: elige la señal manualmente.")

    escalares = [
        v for v in variables_inspeccionadas
        if v["cantidad_elementos"] == 1 and v.get("vista_previa") and v["vista_previa"][0] > 0
    ]

    variable_frecuencia = next((v for v in escalares if _normalizar(v["nombre"]) in NOMBRES_FRECUENCIA_MUESTREO), None)
    valores = {}
    if variable_frecuencia:
        valores["frecuencia_muestreo"] = variable_frecuencia["vista_previa"][0]

    variable_velocidad = next(
        (
            v for v in escalares
            if _normalizar(v["nombre"]) in NOMBRES_VELOCIDAD or "rpm" in _normalizar(v["nombre"])
        ),
        None,
    )
    unidad_rpm = None
    if variable_velocidad:
        valor = variable_velocidad["vista_previa"][0]
        valores["velocidad"] = valor
        if "rpm" in _normalizar(variable_velocidad["nombre"]):
            unidad_rpm = "rpm"
        elif valor <= VELOCIDAD_MAXIMA_PROBABLE_EN_HZ:
            unidad_rpm = "hz"
            notas.append(
                f"La velocidad ({valor:g}) no declara su unidad: por su magnitud se sugiere Hz (rev/s), "
                f"es decir {valor * 60:g} r/min. Confírmalo."
            )
        else:
            unidad_rpm = "rpm"
            notas.append(f"La velocidad ({valor:g}) no declara su unidad: por su magnitud se sugiere r/min. Confírmalo.")

    return {
        "variable_señal": variable_señal,
        "señal_candidatas": candidatas,
        "variable_frecuencia_muestreo": variable_frecuencia["nombre"] if variable_frecuencia else None,
        "variable_rpm": variable_velocidad["nombre"] if variable_velocidad else None,
        "unidad_rpm": unidad_rpm,
        "valores": valores,
        "notas": notas,
    }


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
