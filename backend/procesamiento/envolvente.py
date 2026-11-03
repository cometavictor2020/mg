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

Demodular la señal completa (calcular_espectro_envolvente sin filtrar)
tiene un problema: las componentes de baja frecuencia, fuertes y
deterministas (armonicos del eje, red electrica), dominan la magnitud
del analitico, y sus productos de intermodulacion (ej. 150 Hz - 66 Hz =
84 Hz) aparecen en el espectro de envolvente sobre frecuencias que
podrian ser de falla. Por eso el diagnostico de rodamientos demodula
solo una banda de resonancia elegida desde la señal (D-065): de las
bandas candidatas sobre las componentes de baja frecuencia, la que da el
espectro de envolvente con lineas mas marcadas (mayor curtosis del
espectro, criterio del protrugrama). Los impactos de una falla se repiten
a una frecuencia fija y producen lineas; el ruido de banda ancha y las
rafagas esporadicas dan un espectro plano. El criterio no mira las
frecuencias de falla, asi que elegir la banda no favorece a ninguna
hipotesis. Se calcula con una sola STFT: la envolvente de cada bin de
frecuencia es su modulo a lo largo del tiempo, y su espectro es el
espectro de envolvente de esa banda angosta.

Se probo antes la curtosis espectral clasica (SK) y se descarto: elige
bandas con rafagas aisladas no periodicas, que en un ensayo real dejaron
la linea de falla en 1-2 veces el ruido local. Ver
seleccionar_banda_resonancia() y aislar_banda_resonancia().
"""

import numpy as np
from scipy.fft import fft, fftfreq, rfft, rfftfreq
from scipy.signal import butter, hilbert, sosfiltfilt, stft

ANCHO_VENTANA_STFT_HZ = 250.0  # resolucion en frecuencia de la STFT con que se compara cada banda
FACTOR_MUESTREO_ENVOLVENTE = 4  # la envolvente de cada bin se muestrea a esta cantidad de veces la frecuencia maxima del espectro
FRACCION_NYQUIST_MAXIMA = 0.9  # la banda no pasa de esta fraccion de la frecuencia de Nyquist
FRECUENCIA_MINIMA_PUNTAJE_HZ = 1.0  # el puntaje ignora el continuo (DC y frecuencias casi nulas)


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


def _curtosis(valores):
    valores = np.asarray(valores, dtype=float)
    desviacion = valores.std()
    if desviacion <= 0:
        return 0.0
    return float(np.mean((valores - valores.mean()) ** 4) / desviacion ** 4)


def seleccionar_banda_resonancia(señal, frecuencia_muestreo, frecuencia_minima, ancho_minimo, frecuencia_maxima_envolvente):
    """
    Banda (f_bajo, f_alto, puntaje) que da el espectro de envolvente de lineas mas marcadas, o None si la
    frecuencia de muestreo no deja espacio para una banda sobre `frecuencia_minima`. El puntaje de cada bin
    de la STFT es la curtosis del espectro de su envolvente entre FRECUENCIA_MINIMA_PUNTAJE_HZ y
    `frecuencia_maxima_envolvente`; la banda reune los bins contiguos (a lo menos `ancho_minimo` Hz: debe
    caber la portadora y sus bandas laterales) de mayor puntaje promedio, entre los que tienen al menos la
    potencia mediana (zonas casi sin energia, como las atenuadas por un filtro antialias, dan puntajes sin sentido).
    """
    señal = np.asarray(señal, dtype=float)
    tope = FRACCION_NYQUIST_MAXIMA * frecuencia_muestreo / 2
    if tope - frecuencia_minima < ancho_minimo:
        return None

    nperseg = min(int(2 ** round(np.log2(max(frecuencia_muestreo / ANCHO_VENTANA_STFT_HZ, 16)))), len(señal))
    salto = max(int(frecuencia_muestreo / (FACTOR_MUESTREO_ENVOLVENTE * frecuencia_maxima_envolvente)), 1)
    frecuencias, _, z = stft(señal - señal.mean(), fs=frecuencia_muestreo, nperseg=nperseg, noverlap=nperseg - salto)
    modulo = np.abs(z)
    potencia = np.mean(modulo ** 2, axis=1)

    espectro_modulacion = np.abs(rfft(modulo - modulo.mean(axis=1, keepdims=True), axis=1))
    alfas = rfftfreq(modulo.shape[1], d=salto / frecuencia_muestreo)
    rango = (alfas >= FRECUENCIA_MINIMA_PUNTAJE_HZ) & (alfas <= frecuencia_maxima_envolvente)
    if rango.sum() < 8:
        return None
    centrado = espectro_modulacion[:, rango] - espectro_modulacion[:, rango].mean(axis=1, keepdims=True)
    desviacion = np.sqrt(np.mean(centrado ** 2, axis=1))
    puntaje_bin = np.where(desviacion > 0, np.mean(centrado ** 4, axis=1) / np.maximum(desviacion ** 4, 1e-30), 0.0)

    resolucion = frecuencias[1] - frecuencias[0]
    bins_banda = max(int(np.ceil(ancho_minimo / resolucion)), 3)
    nucleo = np.ones(bins_banda) / bins_banda
    puntaje_banda = np.convolve(puntaje_bin, nucleo, mode="same")
    potencia_banda = np.convolve(potencia, nucleo, mode="same")
    ancho = bins_banda * resolucion
    validas = (
        (frecuencias - ancho / 2 >= frecuencia_minima)
        & (frecuencias + ancho / 2 <= tope)
        & (potencia_banda >= np.median(potencia))
    )
    if not validas.any():
        return None
    i = int(np.argmax(np.where(validas, puntaje_banda, -np.inf)))
    return float(frecuencias[i] - ancho / 2), float(frecuencias[i] + ancho / 2), float(puntaje_banda[i])


def filtrar_banda(señal, frecuencia_muestreo, f_bajo, f_alto):
    sos = butter(4, [f_bajo, f_alto], btype="bandpass", fs=frecuencia_muestreo, output="sos")
    return sosfiltfilt(sos, np.asarray(señal, dtype=float))


def aislar_banda_resonancia(señal, frecuencia_muestreo, frecuencia_banda_minima, ancho_minimo, frecuencia_maxima_envolvente):
    """
    La señal filtrada en la banda de resonancia elegida (ver seleccionar_banda_resonancia), lista para
    demodular. Devuelve (señal, banda) con banda = (f_bajo, f_alto, puntaje); si no hay espacio para una banda
    sobre `frecuencia_banda_minima` (frecuencia de muestreo baja) devuelve la señal sin filtrar y banda = None.
    """
    banda = seleccionar_banda_resonancia(
        señal, frecuencia_muestreo, frecuencia_banda_minima, ancho_minimo, frecuencia_maxima_envolvente
    )
    if banda is None:
        return np.asarray(señal, dtype=float), None
    return filtrar_banda(señal, frecuencia_muestreo, banda[0], banda[1]), banda
