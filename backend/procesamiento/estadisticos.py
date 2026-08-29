import numpy as np
from scipy.stats import kurtosis, skew


def calcular_estadisticos(datos):
    """
    Calcula curtosis, factor de cresta y skewness de los ejes X, Y y Z.

    Parámetros:
        datos:
            DataFrame con las columnas:
            vibracion_x, vibracion_y y vibracion_z.

    Retorna:
        Diccionario con tres listas (curtosis, factor_cresta, skewness),
        cada una con un valor por eje, listo para graficarse en React
        con Recharts (BarChart).
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
            "Faltan columnas necesarias para calcular los estadísticos: "
            + ", ".join(columnas_faltantes)
        )

    curtosis_por_eje = []
    factor_cresta_por_eje = []
    skewness_por_eje = []

    ejes = [
        ("X", "vibracion_x"),
        ("Y", "vibracion_y"),
        ("Z", "vibracion_z"),
    ]

    for nombre_eje, columna in ejes:

        señal = datos[columna].to_numpy()

        valor_rms = np.sqrt(np.mean(np.square(señal)))
        valor_pico = np.max(np.abs(señal))
        factor_cresta = (
            float(valor_pico / valor_rms) if valor_rms != 0 else 0.0
        )

        curtosis_por_eje.append(
            {
                "eje": nombre_eje,
                "valor": round(float(kurtosis(señal, fisher=True)), 6),
            }
        )

        factor_cresta_por_eje.append(
            {
                "eje": nombre_eje,
                "valor": round(factor_cresta, 6),
            }
        )

        skewness_por_eje.append(
            {
                "eje": nombre_eje,
                "valor": round(float(skew(señal)), 6),
            }
        )

    return {
        "curtosis": curtosis_por_eje,
        "factor_cresta": factor_cresta_por_eje,
        "skewness": skewness_por_eje,
    }
