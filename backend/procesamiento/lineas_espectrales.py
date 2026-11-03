"""
Deteccion estadistica de lineas en un espectro (D-065, ver PROYECTO.md).

Un criterio de "pico significativo" fijo (amplitud relativa al maximo del
espectro, razon sobre la mediana GLOBAL) depende de la maquina: un espectro
dominado por una linea intensa esconde las demas, y uno con piso de ruido
inclinado deja pasar ruido en la zona alta. Aca el criterio se define contra
el ruido LOCAL y con una probabilidad de falsa alarma explicita:

    - Piso de ruido: mediana movil de la amplitud en una ventana de varios
      Hz alrededor de cada bin (robusta mientras las lineas ocupen menos de
      la mitad de la ventana).
    - Razon de un bin = amplitud / piso local.
    - Bajo solo ruido, la amplitud de cada bin de una FFT sigue una
      distribucion de Rayleigh. Usando la mediana como escala, la
      probabilidad de que un bin supere r veces el piso es 2^(-r^2). Buscar
      una linea dentro de una ventana de n bins es una busqueda multiple:
      para que la probabilidad de falsa alarma de TODA la busqueda sea p, se
      exige   r >= sqrt(log2(n / p)).
    - El piso tambien es una estimacion (mediana de ~41 bins, error relativo
      cercano al 11 %), lo que engrosa la cola: con ruido blanco gaussiano
      simulado la falsa alarma real salia entre 1.8 % y 2.7 % para p = 1 %.
      El factor `margen_estimacion_piso` (1.07, del YAML) la devuelve a ~1 %
      para ventanas de 5 a 25 bins; se calibro con ruido sintetico, no con
      datos de ningun ensayo.
    - r^2 es ademas la "sorpresa" de la linea en bits (-log2 de la
      probabilidad de verla por azar): sumar r^2 de varias lineas mide la
      fuerza de la evidencia sin saturar como lo hace una confianza acotada
      a 1.

Limitaciones: el modelo de Rayleigh supone ruido de fondo sin estructura;
con lineas deterministas ajenas al fenomeno buscado (red electrica,
armonicos del eje) un pico puede ser significativo y aun asi no ser la
falla - eso lo resuelve la coherencia y la competencia entre hipotesis de
diagnostico_rodamientos.py, no esta capa.
"""

import math

import numpy as np
from scipy.ndimage import median_filter

EPSILON = 1e-12


def resolucion_hz(frecuencias):
    return float(frecuencias[1] - frecuencias[0]) if len(frecuencias) > 1 else 1.0


def piso_de_ruido(amplitudes, resolucion, ventana_hz, minimo_bins):
    """Mediana movil de `amplitudes` en una ventana de `ventana_hz` (al menos `minimo_bins` bins)."""
    amplitudes = np.asarray(amplitudes, dtype=float)
    ancho = max(int(round(ventana_hz / resolucion)), int(minimo_bins))
    ancho = min(ancho, len(amplitudes))
    if ancho % 2 == 0:
        ancho = max(ancho - 1, 1)
    return np.maximum(median_filter(amplitudes, size=ancho, mode="nearest"), EPSILON)


def razon_critica(cantidad_bins, probabilidad_falsa_alarma):
    """Razon sobre el piso que una busqueda en `cantidad_bins` bins debe superar (ver docstring del modulo)."""
    cantidad_bins = max(int(cantidad_bins), 1)
    return math.sqrt(math.log2(cantidad_bins / probabilidad_falsa_alarma))


class EspectroLineas:
    """Un espectro (frecuencias, amplitudes) con su piso de ruido local, listo para buscar lineas."""

    def __init__(self, frecuencias, amplitudes, parametros, cantidad_ejes=1):
        self.frecuencias = np.asarray(frecuencias, dtype=float)
        self.amplitudes = np.asarray(amplitudes, dtype=float)
        self.resolucion = resolucion_hz(self.frecuencias)
        self.parametros = parametros
        self.cantidad_ejes = max(int(cantidad_ejes), 1)
        self.piso = piso_de_ruido(
            self.amplitudes, self.resolucion, parametros["ventana_piso_ruido_hz"], parametros["minimo_bins_piso"]
        )
        self.razones = self.amplitudes / self.piso
        self.frecuencia_maxima = float(self.frecuencias[-1]) if len(self.frecuencias) else 0.0

    def semiancho_hz(self, frecuencia, porcentaje, minimo_bins):
        """Semiancho de una ventana de busqueda: `porcentaje` % de la frecuencia, nunca menos de `minimo_bins` bins."""
        return max(frecuencia * porcentaje / 100.0, minimo_bins * self.resolucion)

    def evaluable(self, frecuencia, semiancho):
        """La ventana cabe entera dentro del espectro calculado (si no, no se puede decir que la linea falte)."""
        return frecuencia - semiancho >= self.frecuencias[0] and frecuencia + semiancho <= self.frecuencia_maxima

    def buscar_linea(self, frecuencia, semiancho):
        """
        Mejor linea significativa en [frecuencia - semiancho, frecuencia + semiancho], o None. Una linea es un
        maximo local cuya razon sobre el piso supera la critica de esta busqueda (que crece con la cantidad de
        bins de la ventana y de ejes en que se busca). Devuelve {frecuencia (interpolada), amplitud, razon}.
        """
        mascara = np.abs(self.frecuencias - frecuencia) <= semiancho
        indices = np.nonzero(mascara)[0]
        if len(indices) == 0:
            return None

        critica = self.parametros["margen_estimacion_piso"] * razon_critica(
            len(indices) * self.cantidad_ejes, self.parametros["probabilidad_falsa_alarma"]
        )
        mejor = None
        for i in indices:
            izquierda = self.amplitudes[i - 1] if i > 0 else -np.inf
            derecha = self.amplitudes[i + 1] if i < len(self.amplitudes) - 1 else -np.inf
            if self.amplitudes[i] < izquierda or self.amplitudes[i] < derecha:
                continue
            if self.razones[i] >= critica and (mejor is None or self.razones[i] > self.razones[mejor]):
                mejor = i

        if mejor is None:
            return None
        return {
            "frecuencia": self._interpolar(mejor),
            "amplitud": float(self.amplitudes[mejor]),
            "razon": float(self.razones[mejor]),
        }

    def _interpolar(self, i):
        """Interpolacion parabolica sobre los 3 bins alrededor de `i` (la FFT de 2 s da 0.5 Hz por bin)."""
        if i == 0 or i == len(self.amplitudes) - 1:
            return float(self.frecuencias[i])
        izquierda, centro, derecha = self.amplitudes[i - 1], self.amplitudes[i], self.amplitudes[i + 1]
        denominador = izquierda - 2 * centro + derecha
        if denominador == 0:
            return float(self.frecuencias[i])
        desplazamiento = 0.5 * (izquierda - derecha) / denominador
        if abs(desplazamiento) > 0.5:
            return float(self.frecuencias[i])
        return float(self.frecuencias[i] + desplazamiento * self.resolucion)
