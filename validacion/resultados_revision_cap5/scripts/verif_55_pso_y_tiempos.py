"""Reverifica el capitulo 5.5: PSO vs envolvente sin optimizar en 135.mat, malla de 220 bandas y tiempos. Solo lectura."""
import statistics
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.signal import decimate

RAIZ = Path(r"C:\Users\comet\Documents\mg")
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "herramientas"))

import reproducir_figuras_paper as rp  # noqa: E402
from backend.procesamiento import pso_envolvente as pso  # noqa: E402
from backend.procesamiento.diagnostico import diagnosticar_sensor  # noqa: E402
from backend.procesamiento.frecuencia import calcular_fft  # noqa: E402

ruta = Path(rp.DATOS_POR_DEFECTO) / "48K-Drive/Set01-07plg1707RPM" / "135.mat"
_, señal, rpm = rp.leer_archivo(ruta)
fs = rp.FRECUENCIA_MUESTREO
objetivo = rp.MULTIPLO_PAPER["BPFO"] * rpm / 60
print(f"135.mat: {len(señal)} muestras ({len(señal) / fs:.2f} s) a {fs} Hz; objetivo BPFO {objetivo:.2f} Hz", flush=True)

sin_filtrar, _ = rp.pico_y_pmr(señal, objetivo)
print(f"envolvente sin filtrar en BPFO: {sin_filtrar:.5f} g", flush=True)

# --- tiempo por banda (una evaluacion de la funcion objetivo sobre la señal completa) ---
fmax_esp = max(500.0, objetivo * 1.5)
tiempos = []
for _ in range(15):
    t0 = time.perf_counter()
    pso._evaluar_ventana(señal, fs, objetivo, 8000.0, 1500.0, fmax_esp)
    tiempos.append((time.perf_counter() - t0) * 1000)
por_banda_ms = statistics.median(tiempos)
print(f"tiempo por banda (señal completa): mediana {por_banda_ms:.0f} ms (min {min(tiempos):.0f}, max {max(tiempos):.0f})", flush=True)
print(f"  estimado 30x30 = {900 * por_banda_ms / 60000:.1f} min; 100x100 = {10000 * por_banda_ms / 60000:.1f} min", flush=True)

# --- malla ordenada de 220 bandas (22 frecuencias centrales x 10 anchos) ---
centros = np.linspace(2000, min(pso.FC_MAXIMO_PAPER, fs / 2 - 1010), 22)
anchos = np.geomspace(pso.W_MINIMO, pso.W_MAXIMO, 10)
mejor_malla = (0.0, None)
t0 = time.perf_counter()
for fc in centros:
    for w in anchos:
        a = pso._evaluar_ventana(señal, fs, objetivo, float(fc), float(w), fmax_esp)
        if a > mejor_malla[0]:
            mejor_malla = (a, (round(float(fc)), round(float(w))))
print(f"malla de 220 bandas: mejor {mejor_malla[0]:.5f} g en (centro, ancho) = {mejor_malla[1]}; {time.perf_counter() - t0:.0f} s", flush=True)

# --- PSO 30x30, tres corridas, señal completa ---
resultados = []
for i in range(3):
    t0 = time.perf_counter()
    r = pso.optimizar_ventana(señal, fs, objetivo, enjambre=30, iteraciones=30)
    dt = time.perf_counter() - t0
    resultados.append(r["amplitud"])
    print(f"PSO 30x30 corrida {i + 1}: {r['amplitud']:.5f} g (x{r['amplitud'] / sin_filtrar:.4f} sobre la envolvente sin filtrar; centro {r['frecuencia_central']:.0f}, ancho {r['ancho_banda']:.0f}); {dt:.0f} s", flush=True)
mejor_pso = max(resultados)
print(f"mejor de las 3 corridas PSO: {mejor_pso:.5f} g ; mejora sobre sin filtrar: {(mejor_pso / sin_filtrar - 1) * 100:.2f} % ; veces sobre espectro crudo (amplitud cruda 0,00116 g): {mejor_pso / 0.00116:.0f}", flush=True)
print(f"malla / mejor PSO = {mejor_malla[0] / mejor_pso * 100:.1f} %", flush=True)

# --- tramo de 2 s a 8000 muestras/s ---
fs8 = 8000
s8 = decimate(señal, 6, zero_phase=True)[: fs8 * 2]
t0 = time.perf_counter()
r8 = pso.optimizar_ventana(s8, fs8, objetivo, enjambre=30, iteraciones=30)
print(f"PSO 30x30 sobre 2 s a {fs8} muestras/s: {time.perf_counter() - t0:.1f} s", flush=True)

# --- motor de diagnostico por sensor ---
ventana = señal[: int(fs * 2)]
df = pd.DataFrame({"vibracion_x": ventana})
fft = calcular_fft(df, fs, 300)
for etiqueta, rod in (("sin rodamiento", None), ("con rodamiento", rp.RODAMIENTO_SKF_6205)):
    ts = []
    for _ in range(30):
        t0 = time.perf_counter()
        diagnosticar_sensor(fft, 1797, datos_crudos=df, frecuencia_muestreo=fs, rodamiento=rod)
        ts.append((time.perf_counter() - t0) * 1000)
    print(f"diagnosticar_sensor {etiqueta} (1 eje, 2 s a 48 kHz): mediana {statistics.median(ts):.1f} ms (min {min(ts):.1f}, max {max(ts):.1f})", flush=True)
print("FIN", flush=True)
