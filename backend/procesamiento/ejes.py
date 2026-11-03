"""
Ejes de vibracion presentes en una señal (D-062, ver PROYECTO.md).

Un sensor puede medir 1, 2 o 3 ejes (Sensor.configuracion["ejes"]). El
archivo de una medicion trae solo las columnas vibracion_<eje> de los ejes
que el sensor tiene, y el resto del procesamiento (FFT, estadisticos,
diagnostico, linea base, reportes) trabaja con los ejes que realmente hay en
los datos, en vez de asumir siempre X, Y y Z. Para una señal triaxial el
resultado es el de siempre: los tres ejes, en el orden x, y, z.
"""

EJES_POSIBLES = ("x", "y", "z")


def ejes_en_columnas(columnas):
    """Ejes con columna vibracion_<eje> en `columnas` (DataFrame.columns), en orden x, y, z."""
    columnas = set(columnas)
    return [eje for eje in EJES_POSIBLES if f"vibracion_{eje}" in columnas]


def ejes_en_datos_fft(datos_fft):
    """
    Ejes con amplitud_<eje> en la lista de filas que devuelve
    frecuencia.py::calcular_fft. Sin filas no hay forma de saberlo y se
    asumen los tres (el comportamiento de antes de D-062).
    """
    if not datos_fft:
        return list(EJES_POSIBLES)
    primera_fila = datos_fft[0]
    return [eje for eje in EJES_POSIBLES if f"amplitud_{eje}" in primera_fila]
