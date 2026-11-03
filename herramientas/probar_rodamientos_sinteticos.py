"""
Prueba del diagnostico de rodamientos con señales SINTETICAS de verdad conocida (D-065).

Complementa a validar_motor.py: aquel mide el motor con ensayos reales, cuya verdad solo
se conoce por el nombre del archivo y de los que ya se miraron los resultados; esta
simula la falla, asi que se sabe exactamente que hay en cada señal y se pueden variar
la severidad, la geometria y la velocidad sin depender de ningun dataset.

Modelo de la señal (una ventana de 2 s):
    - Cada impacto del rodamiento excita una resonancia estructural (seno amortiguado
      a 3 kHz) y se repite a la frecuencia de falla con una fluctuacion del periodo
      (deslizamiento de los elementos rodantes), de ahi que la linea no sea perfecta.
    - Pista interior: la amplitud de los impactos se modula con el giro (1x), como
      ocurre cuando la zona danada entra y sale de la zona de carga. Pista exterior:
      sin modulacion. Elemento rodante: modulado a FTF. Jaula: sin modulacion.
      (Se simula lo que define el archivo de conocimiento para cada regla; esta prueba
      verifica que el motor ve lo que su propia especificacion describe, no la fisica.)
    - Ruido blanco gaussiano, armonicos del eje (1x, 2x, 3x) y lineas de la red electrica
      (100 y 150 Hz): son componentes ajenos al rodamiento que el espectro de
      envolvente SI ve, porque el motor no aplica filtro pasabanda antes de demodular.

Experimentos:
    sensibilidad   - fraccion de ensayos en que la falla correcta llega a la confianza
                     minima, segun la severidad (amplitud del impacto / sigma del ruido).
    falsa alarma   - ensayos sin falla: fraccion con alguna hipotesis de rodamiento.
    especificidad  - con falla: fraccion de ensayos con OTRA hipotesis de rodamiento.
    doble falla    - pista exterior e interior a la vez: ¿se ven las dos?

Uso:
    cd C:\\Users\\comet\\Documents\\mg
    .\\venv\\Scripts\\python.exe herramientas\\probar_rodamientos_sinteticos.py
"""

import argparse
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd

RUTA_PROYECTO = Path(__file__).parent.parent
sys.path.insert(0, str(RUTA_PROYECTO))

from backend.procesamiento.diagnostico import cargar_normativa  # noqa: E402
from backend.procesamiento.diagnostico_rodamientos import (  # noqa: E402
    NOMBRE_REGLA_POR_FALLA,
    calcular_frecuencias_falla,
    evaluar_rodamiento_detallado,
)

FRECUENCIA_MUESTREO = 20000
DURACION_S = 2.0
FRECUENCIA_RESONANCIA = 3000.0
AMORTIGUAMIENTO = 800.0  # 1/s
FLUCTUACION_PERIODO = 0.01  # desviacion tipica relativa del periodo entre impactos
SEVERIDADES = (0.5, 1.0, 2.0, 4.0)  # amplitud del impacto / sigma del ruido
ENSAYOS = 40
UMBRAL_CONFIANZA = 0.50

RODAMIENTOS = {
    "tipo A (8 bolas, d/D = 0.19)": SimpleNamespace(
        codigo="A", numero_elementos_rodantes=8, diametro_elemento_mm=0.235, diametro_paso_mm=1.245, angulo_contacto_grados=0.0
    ),
    "tipo B (9 bolas, d/D = 0.20)": SimpleNamespace(
        codigo="B", numero_elementos_rodantes=9, diametro_elemento_mm=7.94, diametro_paso_mm=39.04, angulo_contacto_grados=0.0
    ),
}
VELOCIDADES_HZ = (25.0, 33.0)
FALLAS = ("BPFO", "BPFI", "BSF", "FTF")


def _modulacion(codigo, fr, frecuencias):
    """Frecuencia con que se modula la amplitud de los impactos de cada falla (None = sin modular)."""
    return {"BPFI": fr, "BSF": frecuencias["FTF"]}.get(codigo)


def senal(rng, rodamiento, fr, fallas, severidad):
    """Aceleracion sintetica de una ventana, con las `fallas` indicadas (lista de codigos, puede ser vacia)."""
    n = int(FRECUENCIA_MUESTREO * DURACION_S)
    t = np.arange(n) / FRECUENCIA_MUESTREO
    frecuencias = calcular_frecuencias_falla(fr * 60, rodamiento)

    x = rng.normal(0.0, 1.0, n)
    for k, amplitud in ((1, 3.0), (2, 1.5), (3, 0.7)):
        x += amplitud * np.cos(2 * np.pi * k * fr * t + rng.uniform(0, 2 * np.pi))
    for f_red in (100.0, 150.0):
        x += 0.8 * np.cos(2 * np.pi * f_red * t + rng.uniform(0, 2 * np.pi))

    nucleo_t = np.arange(0, 6 / AMORTIGUAMIENTO, 1 / FRECUENCIA_MUESTREO)
    nucleo = np.exp(-AMORTIGUAMIENTO * nucleo_t) * np.sin(2 * np.pi * FRECUENCIA_RESONANCIA * nucleo_t)
    for codigo in fallas:
        periodo = 1.0 / frecuencias[codigo]
        impactos = np.zeros(n)
        instante = rng.uniform(0, periodo)
        f_mod = _modulacion(codigo, fr, frecuencias)
        fase = rng.uniform(0, 2 * np.pi)
        while instante < DURACION_S:
            amplitud = severidad * (1 + 0.8 * np.cos(2 * np.pi * f_mod * instante + fase)) / 1.8 if f_mod else severidad
            impactos[int(instante * FRECUENCIA_MUESTREO)] += amplitud
            instante += periodo * (1 + FLUCTUACION_PERIODO * rng.normal())
        x += np.convolve(impactos, nucleo)[:n]
    return x


def hipotesis_de(codigo_serie, rodamiento, fr, normativa):
    datos = pd.DataFrame({"vibracion_x": codigo_serie})
    hipotesis, notas = evaluar_rodamiento_detallado(datos, FRECUENCIA_MUESTREO, fr * 60, rodamiento, normativa)
    return {h["falla"]: h["confianza"] for h in hipotesis}, notas


def ejecutar(ensayos=ENSAYOS, semilla=12345):
    normativa = cargar_normativa()
    rng = np.random.default_rng(semilla)
    filas = []
    for nombre_rod, rodamiento in RODAMIENTOS.items():
        for fr in VELOCIDADES_HZ:
            # Sin falla.
            for _ in range(ensayos):
                h, _ = hipotesis_de(senal(rng, rodamiento, fr, [], 0.0), rodamiento, fr, normativa)
                filas.append({"rodamiento": nombre_rod, "fr": fr, "real": "sano", "severidad": 0.0, "hipotesis": h})
            # Una falla a la vez y la doble falla exterior + interior.
            for severidad in SEVERIDADES:
                for real in [(f,) for f in FALLAS] + [("BPFO", "BPFI")]:
                    for _ in range(ensayos):
                        h, _ = hipotesis_de(senal(rng, rodamiento, fr, list(real), severidad), rodamiento, fr, normativa)
                        filas.append(
                            {"rodamiento": nombre_rod, "fr": fr, "real": "+".join(real), "severidad": severidad, "hipotesis": h}
                        )
    return pd.DataFrame(filas)


def proporcion(serie):
    return f"{serie.mean() * 100:.0f} %" if len(serie) else "—"


def resumen(df, umbral=UMBRAL_CONFIANZA):
    nombre = NOMBRE_REGLA_POR_FALLA
    df = df.copy()
    for codigo, regla in nombre.items():
        df[f"ve_{codigo}"] = df["hipotesis"].apply(lambda h, r=regla: h.get(r, 0.0) >= umbral)
    salida = [f"Confianza minima considerada: {umbral:.2f}. Ensayos por celda: {df.groupby(['rodamiento', 'fr', 'real', 'severidad']).size().iloc[0]}"
              f" (x {len(RODAMIENTOS)} rodamientos x {len(VELOCIDADES_HZ)} velocidades en cada fila).", ""]

    sano = df[df["real"] == "sano"]
    algun = sano[[f"ve_{c}" for c in FALLAS]].any(axis=1)
    salida += ["### Falsa alarma (sin falla; lineas de eje y de red presentes)",
               f"- alguna hipotesis de rodamiento >= {umbral:.2f}: {algun.sum()}/{len(sano)} = {proporcion(algun)}"]
    for c in FALLAS:
        salida.append(f"- {c}: {sano[f've_{c}'].sum()}/{len(sano)} = {proporcion(sano[f've_{c}'])}")

    salida += ["", "### Sensibilidad: fraccion de ensayos con la falla correcta (fila: falla real; columna: severidad)",
               "| falla real | " + " | ".join(f"sev {s:g}" for s in SEVERIDADES) + " |", "|---|" + "---|" * len(SEVERIDADES)]
    for c in FALLAS:
        celdas = [proporcion(df[(df["real"] == c) & (df["severidad"] == s)][f"ve_{c}"]) for s in SEVERIDADES]
        salida.append(f"| {c} | " + " | ".join(celdas) + " |")

    salida += ["", "### Especificidad: fraccion de ensayos con ALGUNA otra hipotesis de rodamiento ademas de la correcta",
               "| falla real | " + " | ".join(f"sev {s:g}" for s in SEVERIDADES) + " |", "|---|" + "---|" * len(SEVERIDADES)]
    for c in FALLAS:
        otras = [f"ve_{o}" for o in FALLAS if o != c]
        celdas = []
        for s in SEVERIDADES:
            sub = df[(df["real"] == c) & (df["severidad"] == s)]
            celdas.append(proporcion(sub[otras].any(axis=1)))
        salida.append(f"| {c} | " + " | ".join(celdas) + " |")

    salida += ["", "### Doble falla (pista exterior + interior a la vez)",
               "| severidad | solo BPFO | solo BPFI | las dos | ninguna |", "|---|---|---|---|---|"]
    for s in SEVERIDADES:
        sub = df[(df["real"] == "BPFO+BPFI") & (df["severidad"] == s)]
        solo_o = sub["ve_BPFO"] & ~sub["ve_BPFI"]
        solo_i = ~sub["ve_BPFO"] & sub["ve_BPFI"]
        ambas = sub["ve_BPFO"] & sub["ve_BPFI"]
        ninguna = ~sub["ve_BPFO"] & ~sub["ve_BPFI"]
        salida.append(f"| {s:g} | {proporcion(solo_o)} | {proporcion(solo_i)} | {proporcion(ambas)} | {proporcion(ninguna)} |")
    return "\n".join(salida)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ensayos", type=int, default=ENSAYOS, help="ensayos por celda")
    parser.add_argument("--semilla", type=int, default=12345)
    parser.add_argument("--umbral", type=float, default=UMBRAL_CONFIANZA)
    parser.add_argument("--salida", default=None, help="si se indica, guarda el resumen en este archivo")
    argumentos = parser.parse_args()

    df = ejecutar(argumentos.ensayos, argumentos.semilla)
    texto = resumen(df, argumentos.umbral)
    print(texto)
    if argumentos.salida:
        Path(argumentos.salida).write_text(texto, encoding="utf-8")


if __name__ == "__main__":
    main()
