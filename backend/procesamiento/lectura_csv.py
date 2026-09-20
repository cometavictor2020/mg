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


def leer_ventana_segundos(ruta_archivo, frecuencia_muestreo, duracion_segundos=2.0):
    """
    Lee una ventana de datos definida por DURACIÓN, no por una cantidad
    de filas fija — la ventana se ajusta a la frecuencia de muestreo de
    cada medición en vez de asumir siempre la misma (ver PROYECTO.md,
    limitación de resolución con el hardcodeo anterior de 1000 filas).

    Ej: con un sensor de 10000 Hz y duracion_segundos=2, lee 20000 filas
    (de hasta 600000 disponibles en una captura de 1 minuto) — más
    filas que las 1000 de antes, pero lejos de tener que cargar el
    archivo completo en cada cálculo de FFT/envolvente.

    Parámetros:
        ruta_archivo: Ruta del archivo CSV.
        frecuencia_muestreo: Hz de esa medición puntual.
        duracion_segundos: cuántos segundos de la captura leer.

    Retorna:
        Un DataFrame de pandas.
    """

    cantidad_filas = max(2, round(frecuencia_muestreo * duracion_segundos))
    return leer_muestra_csv(ruta_archivo, cantidad_filas=cantidad_filas)