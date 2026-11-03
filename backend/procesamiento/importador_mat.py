"""
Importador de archivos .mat de Matlab como medicion (D-063, ver PROYECTO.md).

Mismo esquema que el importador de tablas de texto (importador.py) - leer,
proponer, que la persona confirme y convertir al formato interno - aplicado a
los .mat que publican los datasets de vibraciones (CWRU, MFPT, ...). La
lectura de estructuras y las sugerencias vienen de lectura_mat.py (D-060).

Canales: se consideran señal los vectores numericos de al menos
MUESTRAS_MINIMAS_SEÑAL muestras y las columnas de las matrices de pocas
columnas (ej. un arreglo N x 3 con los tres ejes). Los escalares numericos
(frecuencia de muestreo, velocidad de giro, carga) quedan como "escalares": el
archivo los declara y la propuesta los usa, pero nada se aplica sin que quien
sube el archivo lo confirme. Lo que el archivo no declara (la unidad de la
señal, y a veces la frecuencia de muestreo) queda como "pendiente".

Un .mat no trae columna de tiempo: el timestamp se genera de forma uniforme
a partir de la frecuencia de muestreo, igual que con una tabla sin tiempo.
"""

import hashlib
from datetime import datetime

import numpy as np
import pandas as pd

from backend.procesamiento.importador import (
    EJES,
    FRECUENCIA_MAXIMA_REPRESENTABLE,
    ROLES,
    _eje_del_nombre,
    _tokens,
    csv_interno,
    ejes_del_mapeo,
    validar_frecuencia,
    validar_mapeo,
)
from backend.procesamiento.lectura_mat import MUESTRAS_MINIMAS_SEÑAL, leer_hojas_mat, sugerir_lectura

LIMITE_CANALES = 50
LIMITE_ESCALARES = 100
MAXIMO_COLUMNAS_MATRIZ = 8

MENSAJE_V73 = (
    "El archivo es un .mat de Matlab v7.3 (formato HDF5), que el lector todavía no soporta. "
    "Guárdalo desde Matlab con la opción -v7 (save archivo.mat variables -v7) o conviértelo a CSV."
)


def leer_canales_y_escalares(contenido):
    """
    Devuelve ({nombre: señal 1D de floats}, {nombre: valor}). Un vector largo es un canal con el
    nombre de su variable ("bearing.gs"); una matriz de pocas columnas aporta un canal por
    columna ("acc(:,1)"), o por fila si viene transpuesta ("acc(1,:)"). Un numero suelto es un
    escalar. Lo demas (texto, arreglos cortos, complejos) se ignora.
    """
    try:
        hojas = leer_hojas_mat(contenido)
    except NotImplementedError:
        raise ValueError(MENSAJE_V73)
    except Exception:
        raise ValueError("No fue posible leer el archivo como .mat.")

    canales, escalares = {}, {}
    for ruta, arreglo in hojas.items():
        if arreglo.size == 0 or not np.issubdtype(arreglo.dtype, np.number) or np.iscomplexobj(arreglo):
            continue

        if arreglo.size == 1:
            valor = float(arreglo.reshape(-1)[0])
            if np.isfinite(valor):
                escalares[ruta] = valor
            continue

        if sum(1 for dimension in arreglo.shape if dimension > 1) == 1 and arreglo.size >= MUESTRAS_MINIMAS_SEÑAL:
            canales[ruta] = arreglo.reshape(-1).astype(float)
        elif (
            arreglo.ndim == 2
            and 2 <= min(arreglo.shape) <= MAXIMO_COLUMNAS_MATRIZ
            and max(arreglo.shape) >= MUESTRAS_MINIMAS_SEÑAL
        ):
            por_columnas = arreglo.shape[0] >= arreglo.shape[1]
            matriz = arreglo if por_columnas else arreglo.T
            for indice in range(matriz.shape[1]):
                nombre = f"{ruta}(:,{indice + 1})" if por_columnas else f"{ruta}({indice + 1},:)"
                canales[nombre] = matriz[:, indice].astype(float)

    return canales, escalares


def _describir(canales):
    descripcion = []
    for indice, (nombre, señal) in enumerate(canales.items()):
        descripcion.append(
            {
                "nombre": nombre,
                "indice": indice,
                "tipo": "numerico",
                "muestras": int(señal.size),
                "minimo": round(float(señal.min()), 6),
                "maximo": round(float(señal.max()), 6),
                "media": round(float(señal.mean()), 6),
                "desviacion": round(float(señal.std()), 6),
                "creciente": False,
                "unidad_en_nombre": None,
            }
        )
    return descripcion


def _proponer_ejes(canales):
    """(columnas, asignacion, notas): que canal es X, Y y Z. Nunca elige entre señales parecidas sin decirlo."""
    columnas = {rol: None for rol in ROLES}
    notas = []
    nombres = list(canales)
    largo_maximo = max(len(señal) for señal in canales.values())
    principales = [nombre for nombre in nombres if len(canales[nombre]) == largo_maximo]

    # 1) convencion de CWRU: "X097_DE_time" es el acelerometro del lado de accionamiento. Va antes
    # que los nombres con eje: la "X" inicial de esas variables no es un eje.
    de = [nombre for nombre in principales if "de_time" in nombre.lower()]
    if len(de) == 1:
        columnas["x"] = de[0]
        notas.append(
            f"Se propuso '{de[0]}' (acelerómetro del lado de accionamiento, como en CWRU); las demás señales "
            "quedan sin usar. Cámbialo en «Uso» si necesitas otra."
        )
        return columnas, "posicion", notas

    # 2) nombres con el eje (acc_x, ax, ...).
    for nombre in principales:
        eje = _eje_del_nombre(_tokens(nombre))
        if eje and columnas[eje] is None:
            columnas[eje] = nombre
    if ejes_del_mapeo({"columnas": columnas}) in (("x",), EJES):
        return columnas, "nombre", notas
    columnas = {rol: None for rol in ROLES}

    # 3) una sola señal larga, o exactamente tres (por orden).
    if len(principales) == 1:
        columnas["x"] = principales[0]
        notas.append("El archivo trae una sola señal larga: se asignó a X (sensor de un eje). Verifica que sea la vibración.")
        return columnas, "posicion", notas
    if len(principales) == 3:
        for eje, nombre in zip(EJES, principales):
            columnas[eje] = nombre
        notas.append(
            "El archivo trae tres señales del mismo largo: se asignaron a X, Y y Z en el orden en que aparecen. "
            "No declara la orientación de cada sensor; verifica la asignación."
        )
        return columnas, "posicion", notas

    notas.append(
        f"Hay {len(principales)} señales del mismo largo ({', '.join(principales[:6])}"
        + ("…" if len(principales) > 6 else "")
        + "): elige en «Uso» cuál es la vibración de cada eje."
    )
    return columnas, None, notas


def analizar_mat(contenido):
    """Lectura + descripcion + propuesta de un .mat, con la misma forma que analizar_archivo de las tablas de texto."""
    canales, escalares = leer_canales_y_escalares(contenido)
    if not canales:
        raise ValueError(
            f"El archivo no tiene ninguna variable que parezca una señal (un vector numérico de al menos "
            f"{MUESTRAS_MINIMAS_SEÑAL} muestras)."
        )

    notas = []
    if len(canales) > LIMITE_CANALES:
        notas.append(f"El archivo tiene {len(canales)} señales posibles: se muestran las primeras {LIMITE_CANALES}.")
        canales = dict(list(canales.items())[:LIMITE_CANALES])

    columnas, asignacion, notas_ejes = _proponer_ejes(canales)
    notas += notas_ejes

    # Frecuencia de muestreo y velocidad: las que el archivo declare, con las reglas de D-060.
    como_variables = [
        {"nombre": nombre, "forma": [1, 1], "cantidad_elementos": 1, "vista_previa": [round(valor, 6)]}
        for nombre, valor in escalares.items()
    ]
    sugerencia = sugerir_lectura(como_variables)
    notas += sugerencia["notas"]

    frecuencia = None
    if sugerencia["variable_frecuencia_muestreo"]:
        candidata = sugerencia["valores"]["frecuencia_muestreo"]
        if 1 <= candidata <= FRECUENCIA_MAXIMA_REPRESENTABLE:
            frecuencia = int(round(candidata))
            notas.append(f"La frecuencia de muestreo ({frecuencia} Hz) se tomó de la variable '{sugerencia['variable_frecuencia_muestreo']}'.")

    velocidad_rpm = None
    if sugerencia["variable_rpm"]:
        valor = sugerencia["valores"]["velocidad"]
        velocidad_rpm = round(valor * 60 if sugerencia["unidad_rpm"] == "hz" else valor, 3)

    pendientes = []
    if ejes_del_mapeo({"columnas": columnas}) not in (("x",), EJES):
        pendientes.append("ejes")
    pendientes.append("unidad")
    notas.append(
        "Un .mat no declara la unidad de la señal: indícala tú (el sistema no convierte unidades). "
        "Tampoco trae columna de tiempo: el 'timestamp' se generará desde la frecuencia de muestreo."
    )
    if frecuencia is None:
        pendientes.append("frecuencia_muestreo")
        notas.append("El archivo no declara su frecuencia de muestreo: indícala (está en la documentación del dataset).")

    formato = {"tipo": "mat"}
    return {
        "formato": formato,
        "huella": hashlib.sha1(("mat|" + "|".join(sorted(canales))).encode("utf-8")).hexdigest(),
        "filas_analizadas": max(len(señal) for señal in canales.values()),
        "canales": _describir(canales),
        "escalares": {nombre: round(valor, 6) for nombre, valor in list(escalares.items())[:LIMITE_ESCALARES]},
        "vista_previa": None,
        "propuesta": {
            "formato_nativo": False,
            "columnas": columnas,
            "unidad": None,
            "frecuencia_muestreo": frecuencia,
            "origen_frecuencia": "variable" if frecuencia else None,
            "variable_frecuencia_muestreo": sugerencia["variable_frecuencia_muestreo"] if frecuencia else None,
            "variable_rpm": sugerencia["variable_rpm"],
            "unidad_variable_rpm": sugerencia["unidad_rpm"],
            "velocidad_rpm": velocidad_rpm,
            "unidad_tiempo": "s",
            "asignacion_ejes": asignacion,
            "confianza": {"nombre": "alta", "posicion": "baja"}.get(asignacion, "baja"),
            "notas": notas,
            "pendientes": pendientes,
        },
    }


def aplicar_mapeo_mat(contenido, mapeo, frecuencia_muestreo=None, inicio=None, ejes=None):
    """
    Convierte el .mat al CSV interno segun el mapeo confirmado (columnas = nombres de variable
    o de columna de matriz). La frecuencia de muestreo es, en este orden: la indicada al cargar,
    la de la variable que el mapeo declara, o la guardada en el mapeo. Devuelve (csv_bytes, resumen).
    """
    errores = validar_mapeo(mapeo, ejes)
    if errores:
        raise ValueError(" ".join(errores))
    ejes = tuple(ejes) if ejes is not None else ejes_del_mapeo(mapeo)

    columnas = mapeo["columnas"]
    if columnas.get("tiempo"):
        raise ValueError(
            "Un archivo .mat no tiene columna de tiempo: deja «Tiempo» sin asignar, el timestamp se genera "
            "desde la frecuencia de muestreo."
        )

    canales, escalares = leer_canales_y_escalares(contenido)

    ausentes = [nombre for nombre in (columnas.get(rol) for rol in (*EJES, "temperatura")) if nombre and nombre not in canales]
    if ausentes:
        raise ValueError(
            "El archivo no tiene la(s) variable(s) que indica el mapeo: " + ", ".join(ausentes) + ". "
            "¿Es el mismo formato con el que se confirmó el mapeo?"
        )

    frecuencia = frecuencia_muestreo or escalares.get(mapeo.get("variable_frecuencia_muestreo")) or mapeo.get("frecuencia_muestreo")
    frecuencia = validar_frecuencia(round(frecuencia) if frecuencia else frecuencia)

    elegidas = {rol: columnas[rol] for rol in (*ejes, "temperatura") if columnas.get(rol)}
    largos = {nombre: len(canales[nombre]) for nombre in elegidas.values()}
    if len(set(largos.values())) > 1:
        detalle = ", ".join(f"{nombre}: {largo}" for nombre, largo in largos.items())
        raise ValueError(f"Las señales elegidas tienen distinto número de muestras ({detalle}).")

    salida = {}
    for rol, nombre in elegidas.items():
        señal = canales[nombre]
        invalidos = int((~np.isfinite(señal)).sum())
        if invalidos:
            raise ValueError(f"La variable '{nombre}' tiene {invalidos} valor(es) no numérico(s) o infinito(s).")
        salida["vibracion_" + rol if rol in EJES else rol] = señal

    cantidad = next(iter(largos.values()))
    return csv_interno(salida, cantidad, frecuencia, pd.Timestamp(inicio or datetime.utcnow()))
