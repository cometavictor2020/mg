import numpy as np
from scipy.fft import fft, fftfreq


def calcular_fft(
    datos,
    frecuencia_muestreo=10000,
    frecuencia_maxima=300,
):
    """
    Calcula la FFT de los ejes X, Y y Z de una señal de vibraciones.

    Parámetros:
        datos:
            DataFrame con las columnas:
            vibracion_x, vibracion_y y vibracion_z.

        frecuencia_muestreo:
            Cantidad de muestras tomadas por segundo, expresada en Hz.

        frecuencia_maxima:
            Frecuencia máxima que será incluida en el resultado.

    Retorna:
        Lista de diccionarios preparada para enviarse como JSON
        y ser graficada en React con Recharts.
    """

    columnas_requeridas = [
        "vibracion_x",
        "vibracion_y",
        "vibracion_z",
    ]

    columnas_faltantes = [
        columna
        for columna in columnas_requeridas
        if columna not in datos.columns
    ]

    if columnas_faltantes:
        raise ValueError(
            "Faltan columnas necesarias para calcular la FFT: "
            + ", ".join(columnas_faltantes)
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

    amplitud_x = (
        2.0
        / cantidad_muestras
        * np.abs(
            fft(datos["vibracion_x"].to_numpy())[
                : cantidad_muestras // 2
            ]
        )
    )

    amplitud_y = (
        2.0
        / cantidad_muestras
        * np.abs(
            fft(datos["vibracion_y"].to_numpy())[
                : cantidad_muestras // 2
            ]
        )
    )

    amplitud_z = (
        2.0
        / cantidad_muestras
        * np.abs(
            fft(datos["vibracion_z"].to_numpy())[
                : cantidad_muestras // 2
            ]
        )
    )

    mascara_frecuencias = (
        (frecuencias >= 0)
        & (frecuencias <= frecuencia_maxima)
    )

    frecuencias_filtradas = frecuencias[mascara_frecuencias]
    amplitud_x_filtrada = amplitud_x[mascara_frecuencias]
    amplitud_y_filtrada = amplitud_y[mascara_frecuencias]
    amplitud_z_filtrada = amplitud_z[mascara_frecuencias]

    resultado = []

    for indice, frecuencia in enumerate(frecuencias_filtradas):
        resultado.append(
            {
                "frecuencia": round(float(frecuencia), 4),
                "amplitud_x": round(
                    float(amplitud_x_filtrada[indice]),
                    6,
                ),
                "amplitud_y": round(
                    float(amplitud_y_filtrada[indice]),
                    6,
                ),
                "amplitud_z": round(
                    float(amplitud_z_filtrada[indice]),
                    6,
                ),
            }
        )

    return resultado