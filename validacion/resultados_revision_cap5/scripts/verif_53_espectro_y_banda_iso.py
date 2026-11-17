"""Verificacion de las dos cifras de la seccion 5.3 (solo lectura del motor; no escribe en el proyecto)."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(r"C:\Users\comet\Documents\mg")
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "herramientas"))
sys.path.insert(0, str(RAIZ / "herramientas" / "local_sin_git"))

from backend.procesamiento.frecuencia import calcular_fft  # noqa: E402
from backend.procesamiento.severidad_iso import calcular_velocidad_rms_mm_s  # noqa: E402
from backend.procesamiento.cambio_linea_base import calcular_velocidad_rms_banda_mm_s  # noqa: E402

# --- 1. Perdida de amplitud de la FFT segun donde cae la frecuencia entre dos puntos del calculo -------------------
fs, dur = 10000, 2.0
n = int(fs * dur)
t = np.arange(n) / fs
df = fs / n
print("== FFT de la aplicacion (sin ventana), seno de amplitud 1, fs 10 kHz, 2 s (resolucion 0,5 Hz)")
for desplazamiento in (0.0, 0.1, 0.25, 0.5):
    f = (100 + desplazamiento) * df
    fft = calcular_fft(pd.DataFrame({"vibracion_x": np.sin(2 * np.pi * f * t)}), fs, 300)
    pico = max(fila["amplitud_x"] for fila in fft)
    print(f"  frecuencia a {desplazamiento:.2f} puntos del calculo -> amplitud medida {pico:.4f}  ({20*np.log10(pico):+.2f} dB)")

# --- 2. Velocidad RMS de todo el espectro frente a la de banda limitada 10-1000 Hz ---------------------------------
print("\n== Velocidad RMS: todo el espectro (lo que usa severidad_iso.py) / banda 10-1000 Hz (lo que usa el indicador de cambio)")
import generar_sintetico_desalineacion_vacio_y_carga as sint  # noqa: E402

rng = np.random.default_rng(1)
razones = []
completas = []
for carga in ("vacio", "carga_75"):
    for _ in range(10):
        registros, info = sint.sintetizar_registro(rng, "sano", sint.CARGAS[carga])
        for sensor, datos in registros.items():
            for eje in ("vibracion_x", "vibracion_y", "vibracion_z"):
                s = datos[eje].to_numpy()
                completa = calcular_velocidad_rms_mm_s(s, sint.FRECUENCIA_MUESTREO, "m/s2")
                banda = calcular_velocidad_rms_banda_mm_s(s, sint.FRECUENCIA_MUESTREO, "m/s2", 10.0, 1000.0)
                razones.append(completa / banda)
                completas.append(completa)
razones = np.array(razones)
completas = np.array(completas)
print(f"  22 kW simulado, sano ({len(razones)} ejes): completa/banda mediana {np.median(razones):.2f}, minimo {razones.min():.2f}, maximo {razones.max():.2f}")
print(f"  variacion de la velocidad de todo el espectro entre registros sanos: max/min = {completas.max()/completas.min():.2f}")

try:
    from generar_reportes_mafaulda_corte import leer_archivo, FRECUENCIA_MUESTREO as FS_M  # noqa: E402
    carpeta = Path(r"C:\Users\comet\Downloads\normal\normal")
    archivos = sorted(carpeta.glob("*.csv"))[:12]
    r2 = []
    for ruta in archivos:
        ventana, _ = leer_archivo(ruta)
        for eje in ("vibracion_x", "vibracion_y", "vibracion_z"):
            s = ventana[eje].to_numpy()
            r2.append(calcular_velocidad_rms_mm_s(s, FS_M, "m/s2") / calcular_velocidad_rms_banda_mm_s(s, FS_M, "m/s2", 10.0, 1000.0))
    r2 = np.array(r2)
    print(f"  MAFAULDA normal ({len(archivos)} archivos x 3 ejes): completa/banda mediana {np.median(r2):.2f}, minimo {r2.min():.2f}, maximo {r2.max():.2f}")
except Exception as e:  # noqa: BLE001
    print("  MAFAULDA no disponible:", e)
