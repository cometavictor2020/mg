"""
Prueba de la estimacion de velocidad con señales SINTETICAS de velocidad conocida (D-066).

Compara el peine armonico (velocidad_peine.py, D-066) con la estimacion anterior (pico
dominante cerca de la nominal, D-057) sobre espectros de una maquina que gira a una
velocidad distinta de la nominal. Al ser sintetica, la velocidad real se conoce y se
pueden variar el perfil de armonicos, el error de la nominal y la intensidad de las lineas.

Modelo de la señal (2 s, 10 kHz): armonicos del giro k*fr (k = 1..5) con la amplitud relativa
de cada perfil, lineas de la red electrica (multiplos 1 a 4 de 50 o 60 Hz) y ruido blanco gaussiano.
La red electrica es de 50 Hz (o la que se indique con --red-hz). La amplitud de las lineas se expresa como veces el piso de ruido mediano del espectro.

Perfiles (amplitud relativa de 1x..5x):
    desbalanceo   1x dominante.
    desalineacion 2x dominante, 1x debil.
    sin_1x        1x ausente (solo 2x..5x): el caso en que el pico dominante no puede ser 1x.
    debil         todo bajo (maxima linea 8 veces el piso).

Resultado por metodo: 'bien' (error <= 0.5 %), 'mal' (estima otra velocidad), 'nada'
(no estima y se usaria la nominal).

Uso:
    cd C:\\Users\\comet\\Documents\\mg
    .\\venv\\Scripts\\python.exe herramientas\\probar_velocidad_sintetica.py
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

RUTA_PROYECTO = Path(__file__).parent.parent
sys.path.insert(0, str(RUTA_PROYECTO))

from backend.procesamiento.diagnostico import (  # noqa: E402
    cargar_normativa,
    detectar_picos,
    estimar_rpm_por_picos,
)
from backend.procesamiento.ejes import ejes_en_datos_fft  # noqa: E402
from backend.procesamiento.frecuencia import calcular_fft  # noqa: E402
from backend.procesamiento.velocidad_peine import estimar_velocidad_por_peine  # noqa: E402

FRECUENCIA_MUESTREO = 10000
DURACION_S = 2.0
RPM_NOMINAL = 1500.0  # por defecto; --rpm-nominal lo cambia
ERRORES_PCT = (-10, -7, -5, -3, 0, 3, 5, 7, 10)  # velocidad real respecto de la nominal
FRECUENCIA_RED_HZ = 50.0  # por defecto; --red-hz la cambia. Se simulan sus multiplos 1..4
INTENSIDAD_RED = 6.0  # veces el piso de ruido
TOLERANCIA_ACIERTO_PCT = 0.5
ENSAYOS = 30

PERFILES = {
    "desbalanceo": ([1.0, 0.15, 0.10, 0.05, 0.0], 30.0),
    "desalineacion": ([0.2, 1.0, 0.5, 0.2, 0.1], 30.0),
    "sin_1x": ([0.0, 1.0, 0.8, 0.3, 0.2], 30.0),
    "debil": ([0.3, 0.2, 0.15, 0.1, 0.1], 26.0),  # la mayor linea queda en ~8 veces el piso
}


def espectro(rng, rpm_real, perfil, intensidad_maxima, red_hz=FRECUENCIA_RED_HZ, con_red=True):
    n = int(FRECUENCIA_MUESTREO * DURACION_S)
    t = np.arange(n) / FRECUENCIA_MUESTREO
    piso = 1.664 / np.sqrt(n)  # amplitud mediana de un bin de ruido blanco de sigma 1
    x = rng.normal(0.0, 1.0, n)
    fr = rpm_real / 60
    for k, relativa in enumerate(perfil, start=1):
        if relativa > 0:
            x += relativa * intensidad_maxima * piso * np.cos(2 * np.pi * k * fr * t + rng.uniform(0, 2 * np.pi))
    if con_red:
        for f in (red_hz * m for m in (1, 2, 3, 4)):
            x += INTENSIDAD_RED * piso * np.cos(2 * np.pi * f * t + rng.uniform(0, 2 * np.pi))
    return calcular_fft(pd.DataFrame({"vibracion_x": x}), FRECUENCIA_MUESTREO, 300)


def clasificar(rpm_estimada, rpm_real):
    if rpm_estimada is None:
        return "nada"
    return "bien" if abs(rpm_estimada - rpm_real) / rpm_real * 100 <= TOLERANCIA_ACIERTO_PCT else "mal"


def metodo_pico(fft, normativa, rpm_nominal):
    frecuencias = [f["frecuencia"] for f in fft]
    picos = {eje: detectar_picos(frecuencias, [f[f"amplitud_{eje}"] for f in fft]) for eje in ejes_en_datos_fft(fft)}
    return estimar_rpm_por_picos(picos, rpm_nominal, normativa, fft)


def metodo_peine(fft, normativa, rpm_nominal):
    r = estimar_velocidad_por_peine(fft, rpm_nominal, normativa)
    return None if r is None else r["rpm"]


def metodo_combinado(fft, normativa, rpm_nominal):
    """Lo que hace resolver_velocidad: el peine y, si no alinea suficientes armonicos, el pico dominante."""
    rpm = metodo_peine(fft, normativa, rpm_nominal)
    return rpm if rpm is not None else metodo_pico(fft, normativa, rpm_nominal)


METODOS = {"pico dominante (D-057)": metodo_pico, "peine armonico (D-066)": metodo_peine, "combinado (el que usa la app)": metodo_combinado}


def ejecutar(ensayos=ENSAYOS, semilla=2024, red_hz=FRECUENCIA_RED_HZ, rpm_nominal=RPM_NOMINAL):
    normativa = cargar_normativa()
    rng = np.random.default_rng(semilla)
    filas = []
    for nombre, (perfil, intensidad) in PERFILES.items():
        for error in ERRORES_PCT:
            rpm_real = rpm_nominal * (1 + error / 100)
            for _ in range(ensayos):
                fft = espectro(rng, rpm_real, perfil, intensidad, red_hz)
                for metodo, funcion in METODOS.items():
                    rpm = funcion(fft, normativa, rpm_nominal)
                    filas.append({"perfil": nombre, "error_pct": error, "metodo": metodo, "resultado": clasificar(rpm, rpm_real),
                                  "sesgo_pct": None if rpm is None else (rpm - rpm_real) / rpm_real * 100})
    # Sin ninguna linea del giro: solo red electrica y ruido (la maquina no aporta un peine).
    for _ in range(ensayos * len(ERRORES_PCT)):
        fft = espectro(rng, rpm_nominal, [0.0] * 5, 0.0, red_hz)
        for metodo, funcion in METODOS.items():
            filas.append({"perfil": "sin_giro", "error_pct": 0, "metodo": metodo, "resultado": "nada" if funcion(fft, normativa, rpm_nominal) is None else "mal", "sesgo_pct": None})
    return pd.DataFrame(filas)


def resumen(df):
    salida = []
    for perfil in list(PERFILES) + ["sin_giro"]:
        sub = df[df["perfil"] == perfil]
        salida += [f"### Perfil {perfil}" + (" (sin lineas del giro: solo red electrica y ruido; 'mal' = invento una velocidad)" if perfil == "sin_giro" else ""),
                   "| metodo | bien | mal | nada |", "|---|---|---|---|"]
        for metodo in METODOS:
            r = sub[sub["metodo"] == metodo]["resultado"]
            salida.append(f"| {metodo} | " + " | ".join(f"{(r == v).mean() * 100:.0f} %" for v in ("bien", "mal", "nada")) + " |")
        salida.append("")

    salida += ["### Acierto del metodo combinado segun la velocidad real respecto de la nominal (todos los perfiles con giro)",
               "| velocidad real | " + " | ".join(f"{e:+d} %" for e in ERRORES_PCT) + " |", "|---|" + "---|" * len(ERRORES_PCT)]
    con_giro = df[df["perfil"].isin(PERFILES)]
    for metodo in METODOS:
        celdas = []
        for e in ERRORES_PCT:
            r = con_giro[(con_giro["metodo"] == metodo) & (con_giro["error_pct"] == e)]["resultado"]
            celdas.append(f"{(r == 'bien').mean() * 100:.0f} %")
        salida.append(f"| {metodo} | " + " | ".join(celdas) + " |")

    estimas = con_giro[(con_giro["metodo"] == "peine armonico (D-066)") & con_giro["sesgo_pct"].notna()]["sesgo_pct"]
    salida += ["", f"Sesgo del peine cuando estima (todos los perfiles): mediana {estimas.median():+.2f} %, percentil 5 {estimas.quantile(.05):+.2f} %, percentil 95 {estimas.quantile(.95):+.2f} %."]
    return "\n".join(salida)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ensayos", type=int, default=ENSAYOS, help="ensayos por celda")
    parser.add_argument("--semilla", type=int, default=2024)
    parser.add_argument("--red-hz", type=float, default=FRECUENCIA_RED_HZ, help="frecuencia de la red electrica simulada (50 o 60)")
    parser.add_argument("--rpm-nominal", type=float, default=RPM_NOMINAL)
    parser.add_argument("--salida", default=None, help="si se indica, guarda el resumen en este archivo")
    argumentos = parser.parse_args()
    texto = resumen(ejecutar(argumentos.ensayos, argumentos.semilla, argumentos.red_hz, argumentos.rpm_nominal))
    print(texto)
    if argumentos.salida:
        Path(argumentos.salida).write_text(texto, encoding="utf-8")


if __name__ == "__main__":
    main()
