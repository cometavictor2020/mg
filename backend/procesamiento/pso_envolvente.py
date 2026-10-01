"""
Optimizacion por enjambre de particulas (PSO) de la ventana del filtro
pasa-banda usado antes de calcular la envolvente (D-046, ver
PROYECTO.md) - el metodo "improved ED" del paper de Tyagi & Panigrahi
(2017) que motivo la seccion Laboratorio (D-044).

Modulo deliberadamente separado del resto del motor de rodamientos:
no importa nada de diagnostico_rodamientos.py ni sabe que es un
"equipo" o un "sensor" - solo conoce una señal en el tiempo y una
frecuencia objetivo. Es opcional y bajo demanda (checkbox en
Laboratorio); el camino por defecto (envolvente sin filtrar) sigue
siendo el que usa el resto de la aplicacion, sin cambios.

Diferencia clave con el resto del motor de diagnostico: el fitness que
maximiza PSO es la amplitud CRUDA maxima dentro de una ventana de
tolerancia alrededor de la frecuencia objetivo (igual en espiritu al
paper, seccion 8: "Acdf = f(Fcf, W)"), no el criterio de "pico valido"
(prominencia + relacion señal/ruido) que usa
diagnostico.py::detectar_picos - ese criterio da una superficie de
fitness plana (0 si no hay pico, 1 si lo hay) sobre la que PSO no tiene
gradiente real para moverse. Ver amplitud_en_frecuencia() para por que
hace falta una ventana de tolerancia y no el bin exacto.
"""

import numpy as np
from scipy.signal import butter, sosfiltfilt

from backend.procesamiento.envolvente import calcular_espectro_envolvente

# Limites de busqueda de la Tabla 3 del paper (Fc: 2000-25000 Hz,
# W: 20-4000 Hz); el limite superior de Fc se recorta ademas al
# Nyquist real de la señal en optimizar_ventana().
FC_MINIMO = 2000.0
FC_MAXIMO_PAPER = 25000.0
W_MINIMO = 20.0
W_MAXIMO = 4000.0

# Factores de confianza propia/enjambre e inercia lineal decreciente,
# igual que la Tabla 3 del paper.
C1 = 2.0
C2 = 2.0
INERCIA_INICIAL = 0.99
INERCIA_FINAL = 0.4

# Misma tolerancia que usa el resto del motor de rodamientos
# (TOLERANCIA_RODAMIENTO_PCT en diagnostico_rodamientos.py) para
# emparejar un pico con su frecuencia teorica - la frecuencia de falla
# calculada desde el RPM es una estimacion, no cae exactamente en un
# bin de la FFT real (con datos reales, el desfase tipico es de
# fracciones de Hz por la resolucion de la FFT y la imprecision del
# RPM nominal).
TOLERANCIA_PCT = 2.0
TOLERANCIA_MINIMA_HZ = 1.0


def _filtrar_pasabanda(señal, frecuencia_muestreo, frecuencia_central, ancho_banda):
    nyquist = frecuencia_muestreo / 2
    bajo = max(frecuencia_central - ancho_banda / 2, 1.0)
    alto = min(frecuencia_central + ancho_banda / 2, nyquist - 1.0)
    if alto <= bajo:
        alto = bajo + 1.0
    sos = butter(4, [bajo, alto], btype="bandpass", fs=frecuencia_muestreo, output="sos")
    return sosfiltfilt(sos, señal)


def amplitud_en_frecuencia(frecuencias, amplitudes, frecuencia_objetivo):
    """
    Amplitud maxima dentro de una ventana de tolerancia alrededor de la
    frecuencia objetivo - el fitness que maximiza PSO. No se usa el bin
    mas cercano a secas: la frecuencia objetivo (calculada desde el RPM
    nominal) es una estimacion teorica que en datos reales cae a
    fracciones de Hz del pico real (confirmado en 135.mat: BPFO teorico
    en 107.3046 Hz, pico real en 107.6136 Hz - leer solo el bin exacto
    habria devuelto una amplitud casi 8 veces menor que el pico real).
    """
    tolerancia = max(frecuencia_objetivo * TOLERANCIA_PCT / 100, TOLERANCIA_MINIMA_HZ)
    mascara = np.abs(frecuencias - frecuencia_objetivo) <= tolerancia
    if not np.any(mascara):
        return 0.0
    return float(amplitudes[mascara].max())


def _evaluar_ventana(señal, frecuencia_muestreo, frecuencia_objetivo, frecuencia_central, ancho_banda, frecuencia_maxima_espectro):
    señal_filtrada = _filtrar_pasabanda(señal, frecuencia_muestreo, frecuencia_central, ancho_banda)
    frecuencias, amplitudes = calcular_espectro_envolvente(señal_filtrada, frecuencia_muestreo, frecuencia_maxima_espectro)
    return amplitud_en_frecuencia(frecuencias, amplitudes, frecuencia_objetivo)


def optimizar_ventana(señal, frecuencia_muestreo, frecuencia_objetivo, enjambre=30, iteraciones=30, callback_progreso=None):
    """
    Busca, con PSO, la ventana de filtro pasa-banda (frecuencia central
    Fc, ancho W) que maximiza la amplitud de la envolvente en
    frecuencia_objetivo.

    callback_progreso(iteracion, mejor_fitness), si se entrega, se
    llama al terminar cada iteracion - lo usa quien ejecuta esto en
    segundo plano para reportar avance; este modulo no sabe nada de
    trabajos en segundo plano ni de HTTP.

    Devuelve {"frecuencia_central", "ancho_banda", "amplitud",
    "espectro_frecuencias", "espectro_amplitudes", "historial_fitness"}.
    """
    señal = np.asarray(señal, dtype=float)
    rng = np.random.default_rng()

    nyquist = frecuencia_muestreo / 2
    fc_maximo = min(FC_MAXIMO_PAPER, nyquist - W_MINIMO / 2 - 1)
    frecuencia_maxima_espectro = max(500.0, frecuencia_objetivo * 1.5)

    limite_minimo = np.array([FC_MINIMO, W_MINIMO])
    limite_maximo = np.array([fc_maximo, W_MAXIMO])

    def fitness_de(posicion):
        frecuencia_central, ancho_banda = posicion
        return _evaluar_ventana(
            señal, frecuencia_muestreo, frecuencia_objetivo, frecuencia_central, ancho_banda, frecuencia_maxima_espectro
        )

    posiciones = limite_minimo + rng.random((enjambre, 2)) * (limite_maximo - limite_minimo)
    velocidades = (rng.random((enjambre, 2)) - 0.5) * (limite_maximo - limite_minimo) * 0.1

    fitness_particulas = np.array([fitness_de(posicion) for posicion in posiciones])
    mejor_posicion_propia = posiciones.copy()
    mejor_fitness_propio = fitness_particulas.copy()

    indice_global = int(np.argmax(mejor_fitness_propio))
    mejor_posicion_global = mejor_posicion_propia[indice_global].copy()
    mejor_fitness_global = float(mejor_fitness_propio[indice_global])

    historial_fitness = [mejor_fitness_global]

    for iteracion in range(iteraciones):
        inercia = INERCIA_INICIAL - (INERCIA_INICIAL - INERCIA_FINAL) * (iteracion / max(iteraciones - 1, 1))

        r1 = rng.random((enjambre, 2))
        r2 = rng.random((enjambre, 2))
        velocidades = (
            inercia * velocidades
            + C1 * r1 * (mejor_posicion_propia - posiciones)
            + C2 * r2 * (mejor_posicion_global - posiciones)
        )
        posiciones = np.clip(posiciones + velocidades, limite_minimo, limite_maximo)

        fitness_particulas = np.array([fitness_de(posicion) for posicion in posiciones])

        mejoraron = fitness_particulas > mejor_fitness_propio
        mejor_posicion_propia[mejoraron] = posiciones[mejoraron]
        mejor_fitness_propio[mejoraron] = fitness_particulas[mejoraron]

        indice_global = int(np.argmax(mejor_fitness_propio))
        if mejor_fitness_propio[indice_global] > mejor_fitness_global:
            mejor_fitness_global = float(mejor_fitness_propio[indice_global])
            mejor_posicion_global = mejor_posicion_propia[indice_global].copy()

        historial_fitness.append(mejor_fitness_global)

        if callback_progreso:
            callback_progreso(iteracion + 1, mejor_fitness_global)

    frecuencia_central_final, ancho_banda_final = mejor_posicion_global
    señal_filtrada_final = _filtrar_pasabanda(señal, frecuencia_muestreo, frecuencia_central_final, ancho_banda_final)
    espectro_frecuencias, espectro_amplitudes = calcular_espectro_envolvente(
        señal_filtrada_final, frecuencia_muestreo, frecuencia_maxima_espectro
    )

    return {
        "frecuencia_central": float(frecuencia_central_final),
        "ancho_banda": float(ancho_banda_final),
        "amplitud": mejor_fitness_global,
        "espectro_frecuencias": espectro_frecuencias,
        "espectro_amplitudes": espectro_amplitudes,
        "historial_fitness": historial_fitness,
    }
