"""
Genera un CSV sintetico mas realista que herramientas/
generar_csv_falla_rodamiento.py: en vez de tonos discretos directamente
en BPFO (que ya se detectan con la FFT cruda, sin necesitar envolvente),
simula el mecanismo fisico real de una falla de pista externa: una
serie de IMPACTOS que se repiten a la tasa BPFO, cada uno excitando una
resonancia estructural de alta frecuencia que se apaga rapido antes del
siguiente impacto.

En una señal asi, el espectro CRUDO muestra energia esparcida alrededor
de la frecuencia de resonancia (dificil de interpretar directamente),
mientras que el ESPECTRO DE ENVOLVENTE (backend/procesamiento/
envolvente.py, demodulacion de Hilbert) muestra un pico limpio
exactamente en BPFO - que es la razon de ser de ese modulo, y lo que
este script verifica end-to-end junto con backend/procesamiento/
diagnostico_rodamientos.py.

Geometria: mismo rodamiento SKF 6205 que el script anterior (9
elementos, 7.94/39.04 mm, 0 grados), RPM=1800.

Frecuencia de muestreo: 8000 Hz (para poder capturar la resonancia de
2000 Hz con margen), duracion 2 segundos - el default acordado para la
ventana de lectura (D-0XX, ver PROYECTO.md), aunque para esta prueba
puntual se generan las 2 completas en el archivo (no hace falta que el
archivo sea mas largo que la ventana que se va a leer).
"""

from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
import sys

import numpy as np
import pandas as pd

RUTA_PROYECTO = Path(__file__).parent.parent
sys.path.append(str(RUTA_PROYECTO))

from backend.procesamiento.frecuencia import calcular_fft
from backend.procesamiento.envolvente import calcular_espectro_envolvente
from backend.procesamiento.diagnostico import detectar_picos, buscar_pico_cercano, diagnosticar_sensor
from backend.procesamiento.diagnostico_rodamientos import calcular_frecuencias_falla, evaluar_rodamiento

RUTA_SALIDA = RUTA_PROYECTO / "datos" / "datos_vibracion_falla_rodamiento_envolvente.csv"

RPM_NOMINAL = 1800
FRECUENCIA_MUESTREO = 8000  # Hz - necesita capturar la resonancia (2000 Hz) con margen
DURACION_SEGUNDOS = 2.0  # ventana default acordada para lectura de mediciones

RODAMIENTO_PRUEBA = SimpleNamespace(
    codigo="ROD-PRUEBA",
    numero_elementos_rodantes=9,
    diametro_elemento_mm=7.94,
    diametro_paso_mm=39.04,
    angulo_contacto_grados=0.0,
)

FRECUENCIA_RESONANCIA = 2000  # Hz - la "campana" estructural que excita cada impacto
TAU_DECAIMIENTO = 0.0015  # segundos - se apaga antes del siguiente impacto


def generar_tren_de_impactos(t, tasa_repeticion, frecuencia_portadora, tau, amplitud, fase=0.0):
    """Suma de impulsos amortiguados repitiendose a tasa_repeticion Hz - el modelo
    clasico de vibracion de un rodamiento con un defecto puntual (impacto en cada
    paso del elemento rodante sobre el defecto)."""
    señal = np.zeros_like(t)
    periodo = 1 / tasa_repeticion
    n_impactos = int(np.ceil((t[-1] + (t[1] - t[0])) / periodo)) + 1

    for k in range(n_impactos):
        t_impacto = k * periodo
        dt = t - t_impacto
        mascara = dt >= 0
        señal[mascara] += amplitud * np.exp(-dt[mascara] / tau) * np.sin(
            2 * np.pi * frecuencia_portadora * dt[mascara] + fase
        )

    return señal


def generar_senal(bpfo, fr, fs, duracion_segundos, semilla=11):
    rng = np.random.default_rng(semilla)
    t = np.arange(int(fs * duracion_segundos)) / fs

    def canal(amplitud_impacto, amplitud_1x, ruido_std, fase):
        señal = generar_tren_de_impactos(t, bpfo, FRECUENCIA_RESONANCIA, TAU_DECAIMIENTO, amplitud_impacto, fase)
        señal += amplitud_1x * np.sin(2 * np.pi * fr * t)
        señal += rng.normal(0, ruido_std, len(t))
        return señal

    # Falla de pista externa: radial (X/Y) domina, axial (Z) mucho mas debil.
    x = canal(amplitud_impacto=2.0, amplitud_1x=0.12, ruido_std=0.15, fase=0.0)
    y = canal(amplitud_impacto=1.7, amplitud_1x=0.12, ruido_std=0.15, fase=0.6)
    z = canal(amplitud_impacto=0.25, amplitud_1x=0.08, ruido_std=0.1, fase=0.0)

    return x, y, z


def guardar_csv(x, y, z, fs, n_muestras):
    inicio = datetime(2026, 9, 16, 10, 0, 0)
    paso = timedelta(seconds=1 / fs)
    timestamps = [inicio + i * paso for i in range(n_muestras)]

    rng_temp = np.random.default_rng(7)
    temperatura = 53.0 + rng_temp.normal(0, 0.3, n_muestras)

    tabla = pd.DataFrame({
        "timestamp": [ts.strftime("%Y-%m-%d %H:%M:%S.%f") for ts in timestamps],
        "vibracion_x": np.round(x, 4),
        "vibracion_y": np.round(y, 4),
        "vibracion_z": np.round(z, 4),
        "temperatura": np.round(temperatura, 2),
    })

    RUTA_SALIDA.parent.mkdir(exist_ok=True)
    tabla.to_csv(RUTA_SALIDA, index=False)
    return tabla


def verificar(tabla, frecuencias_falla, fr):
    print("\n--- Espectro CRUDO (lo que ve diagnostico.py hoy, 1x/2x/3x) ---")
    datos_fft = calcular_fft(tabla, frecuencia_muestreo=FRECUENCIA_MUESTREO, frecuencia_maxima=300)
    frecuencias = [d["frecuencia"] for d in datos_fft]
    amplitudes_x = [d["amplitud_x"] for d in datos_fft]
    picos_crudos = detectar_picos(frecuencias, amplitudes_x)
    bpfo_en_crudo = buscar_pico_cercano(picos_crudos, frecuencias_falla["BPFO"], tolerancia_pct=2.0)
    print(f"Picos en espectro crudo (eje X, 0-300 Hz): {[(round(p['frecuencia'],1), round(p['amplitud'],3)) for p in sorted(picos_crudos, key=lambda p: p['frecuencia'])]}")
    if bpfo_en_crudo:
        print(
            f"BPFO tambien aparece en el espectro CRUDO (amplitud {bpfo_en_crudo['amplitud']:.3f}) - un tren de "
            "impactos tiene un peine de armonicos que igual deja algo de energia en su frecuencia fundamental, "
            "pero es mucho mas debil que en la envolvente (ver abajo) y que el 1x de giro normal - por si sola "
            "no bastaria para confiar en ella sin la envolvente."
        )
    else:
        print(f"BPFO ({frecuencias_falla['BPFO']:.1f} Hz) no aparece en el espectro crudo.")

    print("\n--- Espectro de ENVOLVENTE (backend/procesamiento/envolvente.py) ---")
    frecuencias_env, amplitudes_env = calcular_espectro_envolvente(
        tabla["vibracion_x"].to_numpy(), FRECUENCIA_MUESTREO, frecuencia_maxima=500
    )
    picos_env = detectar_picos(frecuencias_env, amplitudes_env)
    print("Picos en espectro de envolvente (eje X):")
    for pico in sorted(picos_env, key=lambda p: p["frecuencia"])[:10]:
        print(f"  {pico['frecuencia']:.1f} Hz -> amplitud {pico['amplitud']:.4f}")

    for nombre, objetivo in frecuencias_falla.items():
        encontrado = buscar_pico_cercano(picos_env, objetivo, tolerancia_pct=2.0)
        if encontrado:
            error_pct = abs(encontrado["frecuencia"] - objetivo) / objetivo * 100
            print(f"  {nombre}: teorico {objetivo:.2f} Hz -> detectado {encontrado['frecuencia']:.1f} Hz (error {error_pct:.2f}%) [OK]")
        else:
            print(f"  {nombre}: teorico {objetivo:.2f} Hz -> no encontrado en la envolvente")

    print("\n--- Motor completo: backend/procesamiento/diagnostico_rodamientos.py::evaluar_rodamiento ---")
    from backend.procesamiento.diagnostico import cargar_normativa
    normativa = cargar_normativa()
    hipotesis_rodamiento = evaluar_rodamiento(tabla, FRECUENCIA_MUESTREO, RPM_NOMINAL, RODAMIENTO_PRUEBA, normativa)
    if hipotesis_rodamiento:
        for h in hipotesis_rodamiento:
            print(f"  -> {h['falla']} ({h['confianza']*100:.0f}% confianza) - evidencia: {h['evidencias']}")
    else:
        print("  -> Ninguna hipotesis de rodamiento (revisar amplitudes/tolerancias)")

    print("\n--- diagnosticar_sensor() completo (1x/2x/3x + rodamiento juntos) ---")
    diagnostico = diagnosticar_sensor(
        datos_fft, RPM_NOMINAL, datos_crudos=tabla, frecuencia_muestreo=FRECUENCIA_MUESTREO, rodamiento=RODAMIENTO_PRUEBA
    )
    for h in diagnostico["hipotesis"]:
        print(f"  -> {h['falla']} ({h['confianza']*100:.0f}% confianza)")
    print(f"  Limitaciones declaradas: {len(diagnostico['limitaciones'])}")


def main():
    frecuencias_falla = calcular_frecuencias_falla(RPM_NOMINAL, RODAMIENTO_PRUEBA)
    fr = RPM_NOMINAL / 60

    x, y, z = generar_senal(frecuencias_falla["BPFO"], fr, FRECUENCIA_MUESTREO, DURACION_SEGUNDOS)
    tabla = guardar_csv(x, y, z, FRECUENCIA_MUESTREO, len(x))

    print(f"CSV generado: {RUTA_SALIDA} ({len(x)} muestras a {FRECUENCIA_MUESTREO} Hz, {DURACION_SEGUNDOS}s)")
    print(f"RPM nominal: {RPM_NOMINAL} (fr={fr:.2f} Hz) - resonancia simulada: {FRECUENCIA_RESONANCIA} Hz")
    print("Frecuencias de falla teoricas:")
    for nombre, valor in frecuencias_falla.items():
        print(f"  {nombre}: {valor:.2f} Hz")

    verificar(tabla, frecuencias_falla, fr)


if __name__ == "__main__":
    main()
