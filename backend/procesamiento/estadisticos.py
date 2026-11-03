import numpy as np
from scipy.stats import kurtosis, skew

from backend.procesamiento.ejes import ejes_en_columnas


def calcular_estadisticos(datos):
    """
    Calcula curtosis, factor de cresta y skewness de los ejes de vibración.

    Parámetros:
        datos:
            DataFrame con las columnas vibracion_x, vibracion_y y
            vibracion_z. Desde D-062 basta con las de los ejes que el
            sensor tiene (un sensor de un eje trae solo vibracion_x).

    Retorna:
        Diccionario con tres listas (curtosis, factor_cresta, skewness),
        cada una con un valor por eje presente, listo para graficarse en
        React con Recharts (BarChart).
    """

    ejes_presentes = ejes_en_columnas(datos.columns)

    if not ejes_presentes:
        raise ValueError(
            "Faltan columnas necesarias para calcular los estadísticos: "
            "vibracion_x, vibracion_y, vibracion_z"
        )

    curtosis_por_eje = []
    factor_cresta_por_eje = []
    skewness_por_eje = []

    for eje in ejes_presentes:

        nombre_eje = eje.upper()
        señal = datos[f"vibracion_{eje}"].to_numpy()

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
