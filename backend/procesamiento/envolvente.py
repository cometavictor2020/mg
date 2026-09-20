"""
Espectro de envolvente por demodulacion de Hilbert.

Metodo especificado en conocimiento/normativa_motorguardian.yaml
(seccion procesamiento_senal.envolvente: metodo="demodulacion_hilbert"),
necesario para diagnosticar fallas de rodamiento (backend/procesamiento/
rodamientos.py): la energia de un impacto en un rodamiento suele excitar
una resonancia estructural de alta frecuencia, y es la ENVOLVENTE de esa
resonancia (no la señal cruda directamente) la que vibra al ritmo de la
frecuencia de falla (BPFO/BPFI/BSF/FTF) - por eso hace falta demodularla
antes de buscar esos picos.

Limitacion conocida: no se aplica ningun filtro de banda pasante antes
de demodular (se usa la señal cruda completa tal cual). Si la resonancia
a aislar esta en una banda especifica del espectro, esto puede diluir
la señal util en ruido de otras bandas. Aislar esa banda automaticamente
(ej. via kurtograma) o de forma configurable es trabajo futuro - ver
LIMITACIONES_RODAMIENTO en rodamientos.py.
"""

import numpy as np
from scipy.fft import fft, fftfreq
from scipy.signal import hilbert


def calcular_envolvente(señal):
    """
    La curva de envolvente en el tiempo (|transformada de Hilbert|),
    sin pasar a espectro - util para graficar la señal cruda con su
    envolvente superpuesta (ver diagnostico_rodamientos.py::
    calcular_datos_grafico), ademas de como paso intermedio de
    calcular_espectro_envolvente().
    """
    señal = np.asarray(señal, dtype=float)
    if len(señal) < 2:
        raise ValueError("Se necesitan al menos dos muestras para calcular la envolvente")

    señal_centrada = señal - señal.mean()
    return np.abs(hilbert(señal_centrada))


def calcular_espectro_envolvente(señal, frecuencia_muestreo, frecuencia_maxima=500):
    """
    Parametros:
        señal: arreglo 1D con la señal cruda en el tiempo (un eje).
        frecuencia_muestreo: Hz.
        frecuencia_maxima: tope de frecuencia a devolver del espectro
            de envolvente (las frecuencias de falla de rodamiento son
            tipicamente bajas frente a la resonancia demodulada).

    Retorna:
        (frecuencias, amplitudes) - arreglos numpy, mismo formato que
        usa detectar_picos() en diagnostico.py.
    """
    señal = np.asarray(señal, dtype=float)
    cantidad_muestras = len(señal)

    if cantidad_muestras < 2:
        raise ValueError("Se necesitan al menos dos muestras para calcular la envolvente")

    envolvente = calcular_envolvente(señal)
    envolvente_centrada = envolvente - envolvente.mean()

    frecuencias = fftfreq(cantidad_muestras, d=1 / frecuencia_muestreo)[: cantidad_muestras // 2]
    amplitudes = (
        2.0
        / cantidad_muestras
        * np.abs(fft(envolvente_centrada)[: cantidad_muestras // 2])
    )

    mascara = (frecuencias >= 0) & (frecuencias <= frecuencia_maxima)
    return frecuencias[mascara], amplitudes[mascara]
