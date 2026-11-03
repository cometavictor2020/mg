import numpy as np
from scipy.fft import fft, fftfreq

from backend.procesamiento.ejes import ejes_en_columnas


def calcular_fft(
    datos,
    frecuencia_muestreo=10000,
    frecuencia_maxima=300,
):
    """
    Calcula la FFT de los ejes de una señal de vibraciones.

    Parámetros:
        datos:
            DataFrame con las columnas vibracion_x, vibracion_y y
            vibracion_z. Desde D-062 basta con las de los ejes que el
            sensor tiene (un sensor de un eje trae solo vibracion_x): se
            calcula la FFT de cada columna presente y no se inventa ninguna
            para los ejes que faltan.

        frecuencia_muestreo:
            Cantidad de muestras tomadas por segundo, expresada en Hz.

        frecuencia_maxima:
            Frecuencia máxima que será incluida en el resultado.

    Retorna:
        Lista de diccionarios preparada para enviarse como JSON
        y ser graficada en React con Recharts: una fila por frecuencia, con
        "frecuencia" y una "amplitud_<eje>" por cada eje presente.
    """

    ejes = ejes_en_columnas(datos.columns)

    if not ejes:
        raise ValueError(
            "Faltan columnas necesarias para calcular la FFT: "
            "vibracion_x, vibracion_y, vibracion_z"
        )

    cantidad_muestras = len(datos)

    if cantidad_muestras < 2:
        raise ValueError(
            "Se necesitan al menos dos muestras para calcular la FFT"
        )

    frecuencias = fftfreq(
        cantidad_muestras,
        d=1 / frecuencia_muestreo,
    )[: cantidad_muestras // 2]

    mascara_frecuencias = (
        (frecuencias >= 0)
        & (frecuencias <= frecuencia_maxima)
    )

    frecuencias_filtradas = frecuencias[mascara_frecuencias]

    amplitudes_filtradas = {}
    for eje in ejes:
        amplitud = (
            2.0
            / cantidad_muestras
            * np.abs(
                fft(datos[f"vibracion_{eje}"].to_numpy())[
                    : cantidad_muestras // 2
                ]
            )
        )
        amplitudes_filtradas[eje] = amplitud[mascara_frecuencias]

    resultado = []

    for indice, frecuencia in enumerate(frecuencias_filtradas):
        fila = {"frecuencia": round(float(frecuencia), 4)}
        for eje in ejes:
            fila[f"amplitud_{eje}"] = round(
                float(amplitudes_filtradas[eje][indice]),
                6,
            )
        resultado.append(fila)

    return resultado
