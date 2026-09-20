"""
Genera un CSV sintetico con una senal de vibracion que simula una falla
de rodamiento en la pista externa (BPFO), y verifica que la deteccion
de picos ya existente (backend/procesamiento/diagnostico.py) efectivamente
encuentra picos cerca de las frecuencias de falla teoricas.

Este script es un paso de validacion ANTES de construir las reglas de
rodamiento en diagnostico.py (D-038 dejo listo el modelo de datos -
Rodamiento con su geometria -, pero el motor que las use es un paso
posterior, ver "Ideas futuras" en PROYECTO.md).

Geometria usada: rodamiento SKF 6205 (9 elementos rodantes, diametro de
elemento 7.94 mm, diametro de paso 39.04 mm, angulo de contacto 0
grados) - la misma referencia que se uso de prueba en Configuracion, y
una de las mas citadas en la literatura de diagnostico de rodamientos.
Las formulas de BPFO/BPFI/BSF/FTF salen de conocimiento/
normativa_motorguardian.yaml (seccion rodamientos.variables_geometria).

IMPORTANTE sobre la resolucion de frecuencia: el pipeline real
(backend/api/administracion/reportes.py) siempre lee las primeras 1000
filas del CSV para calcular la FFT. Con los 10000 Hz que usan las
mediciones reales existentes, esas 1000 muestras dan una resolucion de
apenas 10 Hz por bin - insuficiente frente al margen de tolerancia del
2% que el YAML define para frecuencias de rodamiento
(coincidencia_frecuencia_rodamientos_pct_default), que a ~70-160 Hz
equivale a apenas 1.4-3 Hz. Por eso este archivo se genera a 1000 Hz de
muestreo en vez de 10000 (mismas 1000 muestras, pero 1 Hz por bin): es
una limitacion real del pipeline actual, no un capricho de este script.
Un motor de rodamientos real, sobre mediciones a 10000 Hz, va a
necesitar leer mas muestras o analizar la envolvente en vez del
espectro crudo.

La senal es deliberadamente simple (senoides discretas en las
frecuencias de falla, no un modelo fisico de impactos): alcanza para
probar que la deteccion de picos encuentra las frecuencias correctas,
que es lo que hace falta antes de escribir las reglas.
"""

from datetime import datetime, timedelta
from pathlib import Path
import sys

import numpy as np
import pandas as pd

RUTA_PROYECTO = Path(__file__).parent.parent
sys.path.append(str(RUTA_PROYECTO))

from backend.procesamiento.frecuencia import calcular_fft
from backend.procesamiento.diagnostico import detectar_picos, buscar_pico_cercano, diagnosticar_sensor

RUTA_SALIDA = RUTA_PROYECTO / "datos" / "datos_vibracion_falla_rodamiento_pista_externa.csv"

RPM_NOMINAL = 1800
FRECUENCIA_MUESTREO = 1000  # Hz - ver docstring: da 1 Hz por bin con 1000 muestras
CANTIDAD_MUESTRAS = 1000

# Geometria SKF 6205.
NUMERO_ELEMENTOS_RODANTES = 9
DIAMETRO_ELEMENTO_MM = 7.94
DIAMETRO_PASO_MM = 39.04
ANGULO_CONTACTO_GRADOS = 0.0

TOLERANCIA_RODAMIENTOS_PCT = 2.0  # coincidencia_frecuencia_rodamientos_pct_default del YAML


def calcular_frecuencias_falla(rpm, n, d, diametro_paso, angulo_grados):
    """BPFO/BPFI/BSF/FTF - formulas estandar de diagnostico de rodamientos."""
    fr = rpm / 60
    ratio = (d / diametro_paso) * np.cos(np.radians(angulo_grados))

    return {
        "BPFO": (n / 2) * fr * (1 - ratio),
        "BPFI": (n / 2) * fr * (1 + ratio),
        "BSF": (diametro_paso / (2 * d)) * fr * (1 - ratio ** 2),
        "FTF": (fr / 2) * (1 - ratio),
    }


def generar_senal(bpfo, fr, fs, n_muestras, semilla=42):
    rng = np.random.default_rng(semilla)
    t = np.arange(n_muestras) / fs

    def canal(amplitud_1x, amplitud_bpfo, amplitud_2bpfo, amplitud_3bpfo, ruido_std, fase):
        senal = (
            amplitud_1x * np.sin(2 * np.pi * fr * t)
            + amplitud_bpfo * np.sin(2 * np.pi * bpfo * t + fase)
            + amplitud_2bpfo * np.sin(2 * np.pi * 2 * bpfo * t + fase)
            + amplitud_3bpfo * np.sin(2 * np.pi * 3 * bpfo * t + fase)
        )
        senal += rng.normal(0, ruido_std, n_muestras)
        return senal

    # Falla de pista externa: predominante en direccion radial (X/Y),
    # mucho mas debil en axial (Z) - el sistema todavia no distingue
    # radial de axial (D-036); este dato sintetico es justo el tipo de
    # caso que hara falta cuando se aborde ese punto.
    x = canal(0.15, 1.20, 0.55, 0.25, 0.05, fase=0.0)
    y = canal(0.15, 1.05, 0.45, 0.20, 0.05, fase=0.4)
    z = canal(0.10, 0.15, 0.05, 0.02, 0.04, fase=0.0)

    return x, y, z


def guardar_csv(x, y, z, fs, n_muestras):
    inicio = datetime(2026, 9, 16, 9, 0, 0)
    paso = timedelta(seconds=1 / fs)
    timestamps = [inicio + i * paso for i in range(n_muestras)]

    rng_temp = np.random.default_rng(7)
    # Un rodamiento con falla suele calentarse mas que lo normal (~45 C
    # en los datos reales existentes).
    temperatura = 52.0 + rng_temp.normal(0, 0.3, n_muestras)

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


def verificar_deteccion(tabla, frecuencias_falla, fr):
    """
    Corre la misma FFT y deteccion de picos que usa el sistema hoy
    (backend/procesamiento/frecuencia.py + diagnostico.py) para
    confirmar que las frecuencias de falla generadas efectivamente
    aparecen como picos detectables - la base numerica que necesitaria
    una futura regla de rodamientos.
    """
    datos_fft = calcular_fft(tabla, frecuencia_muestreo=FRECUENCIA_MUESTREO, frecuencia_maxima=300)
    frecuencias = [d["frecuencia"] for d in datos_fft]
    amplitudes_x = [d["amplitud_x"] for d in datos_fft]

    picos_x = detectar_picos(frecuencias, amplitudes_x)

    print("\nPicos detectados en eje X (radial, el mas afectado por esta falla):")
    for pico in sorted(picos_x, key=lambda p: p["frecuencia"]):
        print(f"  {pico['frecuencia']:.1f} Hz -> amplitud {pico['amplitud']:.3f}")

    print(f"\nComparacion contra frecuencias teoricas (tolerancia {TOLERANCIA_RODAMIENTOS_PCT}%, criterio del YAML):")
    for nombre, objetivo in frecuencias_falla.items():
        encontrado = buscar_pico_cercano(picos_x, objetivo, tolerancia_pct=TOLERANCIA_RODAMIENTOS_PCT)
        if encontrado:
            error_pct = abs(encontrado["frecuencia"] - objetivo) / objetivo * 100
            print(
                f"  {nombre}: teorico {objetivo:.2f} Hz -> detectado {encontrado['frecuencia']:.1f} Hz "
                f"(amplitud {encontrado['amplitud']:.3f}, error {error_pct:.2f}%) [OK]"
            )
        else:
            print(f"  {nombre}: teorico {objetivo:.2f} Hz -> NO se encontro un pico dentro de la tolerancia")

    print(f"\nComo referencia, 1x (giro) esperado en {fr:.1f} Hz:")
    encontrado_1x = buscar_pico_cercano(picos_x, fr, tolerancia_pct=3.0)
    if encontrado_1x:
        print(f"  1x: detectado {encontrado_1x['frecuencia']:.1f} Hz (amplitud {encontrado_1x['amplitud']:.3f})")

    print(
        "\nOJO: diagnostico.py todavia NO tiene reglas de rodamiento (D-036). "
        "Si se corre diagnosticar_sensor() sobre estos datos hoy, solo evalua "
        "1x/2x/3x - veamos que dice:"
    )
    diagnostico = diagnosticar_sensor(datos_fft, RPM_NOMINAL)
    if diagnostico["hipotesis"]:
        for hipotesis in diagnostico["hipotesis"]:
            print(f"  -> {hipotesis['falla']} ({hipotesis['confianza']*100:.0f}% confianza) - evidencia: {hipotesis['evidencias']}")
        print(
            "  Esto es un FALSO POSITIVO relevante: el 1x residual (giro normal) "
            "puede bastar para que hoy se sugiera 'desbalanceo' cuando la causa "
            "real es la falla de rodamiento en BPFO. Confirma que hace falta "
            "construir la regla de rodamiento para diagnosticar esto correctamente."
        )
    else:
        print("  -> Ninguna hipotesis (el 1x residual no fue suficiente para disparar una regla).")


def main():
    frecuencias_falla = calcular_frecuencias_falla(
        RPM_NOMINAL,
        NUMERO_ELEMENTOS_RODANTES,
        DIAMETRO_ELEMENTO_MM,
        DIAMETRO_PASO_MM,
        ANGULO_CONTACTO_GRADOS,
    )
    fr = RPM_NOMINAL / 60

    x, y, z = generar_senal(frecuencias_falla["BPFO"], fr, FRECUENCIA_MUESTREO, CANTIDAD_MUESTRAS)
    tabla = guardar_csv(x, y, z, FRECUENCIA_MUESTREO, CANTIDAD_MUESTRAS)

    print(f"CSV generado: {RUTA_SALIDA} ({CANTIDAD_MUESTRAS} muestras a {FRECUENCIA_MUESTREO} Hz)")
    print(f"RPM nominal usado: {RPM_NOMINAL} (fr = {fr:.2f} Hz)")
    print("Geometria: SKF 6205 (9 elementos, 7.94/39.04 mm, 0 grados)")
    print("Frecuencias de falla teoricas (pista externa):")
    for nombre, valor in frecuencias_falla.items():
        print(f"  {nombre}: {valor:.2f} Hz")

    verificar_deteccion(tabla, frecuencias_falla, fr)


if __name__ == "__main__":
    main()
