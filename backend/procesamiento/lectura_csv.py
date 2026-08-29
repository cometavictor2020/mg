import pandas as pd


def leer_csv(ruta_archivo):
    """
    Lee un archivo CSV completo.

    Parámetros:
        ruta_archivo: Ruta del archivo CSV.

    Retorna:
        Un DataFrame de pandas.
    """

    datos = pd.read_csv(ruta_archivo)

    return datos


def leer_muestra_csv(ruta_archivo, cantidad_filas=10):
    """
    Lee una cantidad limitada de filas desde un archivo CSV.

    Parámetros:
        ruta_archivo: Ruta del archivo CSV.
        cantidad_filas: Número de filas que se desea leer.

    Retorna:
        Un DataFrame de pandas.
    """

    muestra = pd.read_csv(
        ruta_archivo,
        nrows=cantidad_filas
    )

    return muestra