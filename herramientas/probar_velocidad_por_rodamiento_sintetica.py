"""
Prueba de la estimacion de velocidad por la firma de una falla de rodamiento, con señales SINTETICAS (D-066).

Mide diagnostico_rodamientos.py::estimar_velocidad_por_rodamiento (respaldo del peine armonico cuando este es
ambiguo) con las mismas señales de probar_rodamientos_sinteticos.py: impactos que excitan una resonancia, ruido,
armonicos del eje y lineas de la red. Se simula una velocidad real fr y se le pasa al estimador una velocidad
nominal equivocada (de -8 % a +8 %); como se conoce la real, se puede medir si la recupera.

Que mide:
    - Sin falla: cuantas veces inventa una velocidad (lo que importa: una velocidad inventada seria una falla supuesta).
    - Con falla (pista exterior, interior, elemento rodante, y exterior + interior): en que fraccion de los
      ensayos estima y en que fraccion acierta (error <= 2 % de la real), por severidad.
    - Cuantas veces estima y se equivoca.

Uso:
    cd C:\\Users\\comet\\Documents\\mg
    .\\venv\\Scripts\\python.exe herramientas\\probar_velocidad_por_rodamiento_sintetica.py
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

RUTA_PROYECTO = Path(__file__).parent.parent
sys.path.insert(0, str(RUTA_PROYECTO))
sys.path.insert(0, str(Path(__file__).parent))

import probar_rodamientos_sinteticos as ps  # noqa: E402
from backend.procesamiento.diagnostico import cargar_normativa  # noqa: E402
from backend.procesamiento.diagnostico_rodamientos import estimar_velocidad_por_rodamiento  # noqa: E402

ERRORES_NOMINAL_PCT = (-8, -4, 0, 4, 8)
SEVERIDADES = (1.0, 2.0, 4.0)
FALLAS = ([], ["BPFO"], ["BPFI"], ["BSF"], ["BPFO", "BPFI"])
TOLERANCIA_ACIERTO_PCT = 2.0


def ejecutar(ensayos, semilla):
    normativa = cargar_normativa()
    rng = np.random.default_rng(semilla)
    filas = []
    for rodamiento in ps.RODAMIENTOS.values():
        for fr in ps.VELOCIDADES_HZ:
            for real in FALLAS:
                for severidad in ([0.0] if not real else SEVERIDADES):
                    for error in ERRORES_NOMINAL_PCT:
                        for _ in range(ensayos):
                            señal = ps.senal(rng, rodamiento, fr, real, severidad)
                            nominal = fr * 60 * (1 + error / 100)
                            r = estimar_velocidad_por_rodamiento(
                                pd.DataFrame({"vibracion_x": señal}), ps.FRECUENCIA_MUESTREO, nominal, rodamiento, normativa
                            )
                            filas.append(
                                {
                                    "real": "+".join(real) or "sano", "severidad": severidad, "error_nominal_pct": error,
                                    "estima": r is not None,
                                    "acierto": r is not None and abs(r["rpm"] - fr * 60) / (fr * 60) * 100 <= TOLERANCIA_ACIERTO_PCT,
                                }
                            )
    return pd.DataFrame(filas)


def resumen(df):
    sano = df[df["real"] == "sano"]
    con_falla = df[df["real"] != "sano"]
    salida = [
        "Velocidad estimada por la firma del rodamiento, señales sinteticas (la nominal se equivoca de -8 % a +8 %).",
        "",
        f"SANO: velocidades inventadas {int(sano['estima'].sum())} de {len(sano)} ensayos ({sano['estima'].mean() * 100:.1f} %).",
        "",
        "Con falla: ensayos en que estima (E) y en que acierta, error <= 2 % de la real (A):",
    ]
    for real in ("BPFO", "BPFI", "BSF", "BPFO+BPFI"):
        sub = df[df["real"] == real]
        celdas = [
            f"sev {s:g}: E {sub[sub['severidad'] == s]['estima'].mean() * 100:.0f} % A {sub[sub['severidad'] == s]['acierto'].mean() * 100:.0f} %"
            for s in SEVERIDADES
        ]
        salida.append(f"  {real:10s} " + " | ".join(celdas))
    salida += [
        "",
        f"Estima pero se equivoca (fuera de 2 %): {int((con_falla['estima'] & ~con_falla['acierto']).sum())} de {int(con_falla['estima'].sum())} estimaciones.",
        "Acierto segun el error de la nominal (con falla, severidad >= 2): "
        + ", ".join(
            f"{e:+d} %: {con_falla[(con_falla['severidad'] >= 2) & (con_falla['error_nominal_pct'] == e)]['acierto'].mean() * 100:.0f} %"
            for e in ERRORES_NOMINAL_PCT
        ),
    ]
    return "\n".join(salida)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ensayos", type=int, default=20, help="ensayos por celda")
    parser.add_argument("--semilla", type=int, default=77)
    parser.add_argument("--salida", default=None, help="si se indica, guarda el resumen en este archivo")
    argumentos = parser.parse_args()
    texto = resumen(ejecutar(argumentos.ensayos, argumentos.semilla))
    print(texto)
    if argumentos.salida:
        Path(argumentos.salida).write_text(texto, encoding="utf-8")


if __name__ == "__main__":
    main()
