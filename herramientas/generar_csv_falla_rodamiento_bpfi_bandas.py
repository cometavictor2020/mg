"""
Genera un CSV sintetico de falla de PISTA INTERIOR (BPFI) con
modulacion de amplitud real por el giro del eje (1x) - el mecanismo
fisico que produce bandas laterales: como el defecto esta en la pista
interior, que gira junto con el eje, la fuerza de acoplamiento del
impacto hacia el sensor varia segun la posicion angular del eje,
amplitud-modulando el tren de impactos a la tasa 1x. Eso se traduce en
picos a BPFI-1x y BPFI+1x en el espectro de envolvente.

A diferencia de herramientas/generar_csv_falla_rodamiento_envolvente.py
(pista exterior, impactos de amplitud constante), aqui la amplitud de
cada impacto varia con el tiempo - por eso sirve para probar
especificamente backend/procesamiento/diagnostico_rodamientos.py::
_bandas_laterales_detectadas(), que antes no existia.

Misma geometria SKF 6205 y RPM=1800 que los scripts anteriores.
"""

from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
import sys

import numpy as np
import pandas as pd

RUTA_PROYECTO = Path(__file__).parent.parent
sys.path.append(str(RUTA_PROYECTO))

from backend.procesamiento.diagnostico import cargar_normativa, detectar_picos, buscar_pico_cercano, diagnosticar_sensor
from backend.procesamiento.diagnostico_rodamientos import calcular_frecuencias_falla, evaluar_rodamiento
from backend.procesamiento.envolvente import calcular_espectro_envolvente
from backend.procesamiento.frecuencia import calcular_fft

RUTA_SALIDA = RUTA_PROYECTO / "datos" / "datos_vibracion_falla_rodamiento_bpfi_bandas.csv"

RPM_NOMINAL = 1800
FRECUENCIA_MUESTREO = 8000
DURACION_SEGUNDOS = 2.0

RODAMIENTO_PRUEBA = SimpleNamespace(
    codigo="ROD-PRUEBA-BPFI",
    numero_elementos_rodantes=9,
    diametro_elemento_mm=7.94,
    diametro_paso_mm=39.04,
    angulo_contacto_grados=0.0,
)

FRECUENCIA_RESONANCIA = 2000
TAU_DECAIMIENTO = 0.0015
INDICE_MODULACION = 0.7  # que tan fuerte varia la amplitud del impacto con el giro


def generar_tren_de_impactos_modulado(t, tasa_repeticion, frecuencia_portadora, tau, amplitud_base, indice_modulacion, fr, fase=0.0):
    señal = np.zeros_like(t)
    periodo = 1 / tasa_repeticion
    n_impactos = int(np.ceil((t[-1] + (t[1] - t[0])) / periodo)) + 1

    for k in range(n_impactos):
        t_impacto = k * periodo
        # Amplitud de este impacto en particular, modulada por la posicion
        # angular del eje en el momento del impacto - esto es lo que crea
        # las bandas laterales a +-1x alrededor de BPFI.
        amplitud_impacto = amplitud_base * (1 + indice_modulacion * np.cos(2 * np.pi * fr * t_impacto))

        dt = t - t_impacto
        mascara = dt >= 0
        señal[mascara] += amplitud_impacto * np.exp(-dt[mascara] / tau) * np.sin(
            2 * np.pi * frecuencia_portadora * dt[mascara] + fase
        )

    return señal


def generar_senal(bpfi, fr, fs, duracion_segundos, semilla=23):
    rng = np.random.default_rng(semilla)
    t = np.arange(int(fs * duracion_segundos)) / fs

    def canal(amplitud_impacto, amplitud_1x, ruido_std, fase):
        señal = generar_tren_de_impactos_modulado(
            t, bpfi, FRECUENCIA_RESONANCIA, TAU_DECAIMIENTO, amplitud_impacto, INDICE_MODULACION, fr, fase
        )
        señal += amplitud_1x * np.sin(2 * np.pi * fr * t)
        señal += rng.normal(0, ruido_std, len(t))
        return señal

    # Falla de pista interior: tambien predominante en direccion radial.
    x = canal(amplitud_impacto=2.0, amplitud_1x=0.12, ruido_std=0.15, fase=0.0)
    y = canal(amplitud_impacto=1.7, amplitud_1x=0.12, ruido_std=0.15, fase=0.6)
    z = canal(amplitud_impacto=0.25, amplitud_1x=0.08, ruido_std=0.1, fase=0.0)

    return x, y, z


def guardar_csv(x, y, z, fs, n_muestras):
    inicio = datetime(2026, 9, 18, 9, 0, 0)
    paso = timedelta(seconds=1 / fs)
    timestamps = [inicio + i * paso for i in range(n_muestras)]

    rng_temp = np.random.default_rng(9)
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
    print("\n--- Espectro de ENVOLVENTE (eje X) alrededor de BPFI ---")
    frecuencias_env, amplitudes_env = calcular_espectro_envolvente(
        tabla["vibracion_x"].to_numpy(), FRECUENCIA_MUESTREO, frecuencia_maxima=500
    )
    picos_env = detectar_picos(frecuencias_env, amplitudes_env)

    bpfi = frecuencias_falla["BPFI"]
    print(f"Objetivo: BPFI={bpfi:.2f} Hz, bandas laterales esperadas en {bpfi-fr:.2f} Hz y {bpfi+fr:.2f} Hz")
    for pico in sorted(picos_env, key=lambda p: p["frecuencia"]):
        if abs(pico["frecuencia"] - bpfi) < fr * 1.5:
            print(f"  {pico['frecuencia']:.1f} Hz -> amplitud {pico['amplitud']:.4f}")

    for etiqueta, objetivo in [("BPFI", bpfi), ("BPFI - 1x", bpfi - fr), ("BPFI + 1x", bpfi + fr)]:
        encontrado = buscar_pico_cercano(picos_env, objetivo, tolerancia_pct=2.0)
        estado = f"detectado {encontrado['frecuencia']:.1f} Hz" if encontrado else "NO encontrado"
        print(f"  {etiqueta} (teorico {objetivo:.2f} Hz): {estado}")

    print("\n--- backend/procesamiento/diagnostico_rodamientos.py::evaluar_rodamiento ---")
    normativa = cargar_normativa()
    hipotesis_rodamiento = evaluar_rodamiento(tabla, FRECUENCIA_MUESTREO, RPM_NOMINAL, RODAMIENTO_PRUEBA, normativa)
    for h in hipotesis_rodamiento:
        print(f"  -> {h['falla']} ({h['confianza']*100:.0f}% confianza) - evidencia: {h['evidencias']}")
    if not hipotesis_rodamiento:
        print("  -> Ninguna hipotesis de rodamiento")

    print("\n--- diagnosticar_sensor() completo ---")
    datos_fft = calcular_fft(tabla, frecuencia_muestreo=FRECUENCIA_MUESTREO, frecuencia_maxima=300)
    diagnostico = diagnosticar_sensor(
        datos_fft, RPM_NOMINAL, datos_crudos=tabla, frecuencia_muestreo=FRECUENCIA_MUESTREO, rodamiento=RODAMIENTO_PRUEBA
    )
    for h in diagnostico["hipotesis"]:
        print(f"  -> {h['falla']} ({h['confianza']*100:.0f}% confianza)")


def main():
    frecuencias_falla = calcular_frecuencias_falla(RPM_NOMINAL, RODAMIENTO_PRUEBA)
    fr = RPM_NOMINAL / 60

    x, y, z = generar_senal(frecuencias_falla["BPFI"], fr, FRECUENCIA_MUESTREO, DURACION_SEGUNDOS)
    tabla = guardar_csv(x, y, z, FRECUENCIA_MUESTREO, len(x))

    print(f"CSV generado: {RUTA_SALIDA} ({len(x)} muestras a {FRECUENCIA_MUESTREO} Hz, {DURACION_SEGUNDOS}s)")
    print(f"RPM nominal: {RPM_NOMINAL} (fr={fr:.2f} Hz) - resonancia: {FRECUENCIA_RESONANCIA} Hz, modulacion 1x indice {INDICE_MODULACION}")
    print("Frecuencias de falla teoricas:")
    for nombre, valor in frecuencias_falla.items():
        print(f"  {nombre}: {valor:.2f} Hz")

    verificar(tabla, frecuencias_falla, fr)


if __name__ == "__main__":
    main()
