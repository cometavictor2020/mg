"""
Valida las reglas de desbalanceo y desalineacion del motor con el dataset SRO (Qasim y Almubarak, KFUPM; Mendeley Data
y8mv28hjwb, CC BY 4.0): muestras de 1 s, 4 canales radiales a 25,6 kHz (dos ubicaciones, vertical y horizontal en
cada una) con la maquina normal, con desbalanceo y con desalineacion a 600, 900 y 1200 r/min. Sin tacometro y sin
severidades, sin pasar por la base de datos.

Cada ubicacion se diagnostica por separado como un sensor de dos ejes (vibracion_x = vertical, vibracion_y =
horizontal). La velocidad es la nominal del archivo (lo que declararia un operador); el motor la refina con el espectro.
La linea base es una muestra normal de la PRIMERA corrida normal de cada velocidad, y esa corrida no se evalua.
Ningun umbral del motor se ajusto con este dataset: todas las corridas restantes son datos de reserva.

Se leen los .zip tal como vienen en la carpeta "data" del dataset, sin descomprimir.

Uso:
    cd C:\\Users\\comet\\Documents\\mg
    .\\venv\\Scripts\\python.exe herramientas\\validar_sro.py --datos "C:\\Users\\comet\\Downloads\\...\\SRO-Cross-Speed-Dataset" --velocidades 900
"""

import argparse
import io
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.io as sio

RUTA_PROYECTO = Path(__file__).parent.parent
sys.path.insert(0, str(RUTA_PROYECTO))
sys.path.insert(0, str(Path(__file__).parent))

import backend.procesamiento.diagnostico as modulo_diagnostico  # noqa: E402
from backend.procesamiento.cambio_linea_base import calcular_valores_velocidad_linea_base  # noqa: E402
from backend.procesamiento.diagnostico import (  # noqa: E402
    TOLERANCIA_FRECUENCIA_PCT,
    calcular_relacion_2x_1x,
    cargar_normativa,
    diagnosticar_sensor,
    resolver_velocidad,
)
from backend.procesamiento.frecuencia import calcular_fft  # noqa: E402
from backend.procesamiento.linea_base import calcular_valores_linea_base  # noqa: E402

CONDICIONES = ["normal", "imbalance", "misalignment"]
ETIQUETA = {"normal": "normal", "imbalance": "desbalanceo", "misalignment": "desalineacion"}
UBICACIONES = {1: (0, 1), 2: (2, 3)}  # ubicacion -> (canal vertical, canal horizontal)
ORIENTACION_EJES = {"x": "radial_vertical", "y": "radial_horizontal"}
FALLAS = ["desbalanceo", "desalineacion_paralela", "desalineacion_angular"]
UMBRAL_PRINCIPAL = 0.70  # confianza_diagnostico.reglas_salida.marcar_diagnostico_principal_desde_confianza
ESCENARIOS = (("sin_relacion", False), ("con_relacion", True))


def leer_muestras(base, condicion, velocidad_rpm, manifiesto):
    """Itera (sample_id, corrida, senales 4 x N, fs) de un archivo zip de condicion y velocidad."""
    sub = manifiesto[(manifiesto.condition == condicion) & (manifiesto.speed_rpm == velocidad_rpm)]
    corridas = dict(zip(sub.archived_filename, sub.original_file))
    with zipfile.ZipFile(Path(base) / "data" / f"{condicion}_{velocidad_rpm}rpm.zip") as archivo:
        for nombre in sorted(archivo.namelist()):
            if Path(nombre).name not in corridas:
                continue
            contenido = sio.loadmat(io.BytesIO(archivo.read(nombre)))
            yield Path(nombre).stem, corridas[Path(nombre).name], contenido["signals"].astype(float), int(contenido["fs"].ravel()[0])


def datos_de_ubicacion(senales, ubicacion):
    vertical, horizontal = UBICACIONES[ubicacion]
    return pd.DataFrame({"vibracion_x": senales[vertical], "vibracion_y": senales[horizontal]})


def linea_base_de(datos_crudos, fs, rpm_nominal):
    """Lo que guarda lineas_base.py::marcar_linea_base para una medicion sana con velocidad declarada."""
    datos_fft = calcular_fft(datos=datos_crudos, frecuencia_muestreo=fs, frecuencia_maxima=300)
    velocidad = resolver_velocidad(datos_fft, rpm_nominal, None)
    valores = calcular_valores_linea_base(datos_fft, velocidad["rpm"], TOLERANCIA_FRECUENCIA_PCT)
    valores["velocidad_origen"] = velocidad["origen"]
    valores["velocidad_rms"] = calcular_valores_velocidad_linea_base(datos_crudos, fs, None, velocidad["rpm"], cargar_normativa())
    return {"valores": valores, "fecha": "referencia"}


def diagnosticar(fft, datos, fs, rpm, linea_base, con_relacion):
    original = modulo_diagnostico.calcular_relacion_2x_1x
    if not con_relacion:
        modulo_diagnostico.calcular_relacion_2x_1x = lambda hallazgos: None
    try:
        d = diagnosticar_sensor(
            fft, rpm, datos_crudos=datos, frecuencia_muestreo=fs, rodamiento=None,
            orientacion_ejes=ORIENTACION_EJES, linea_base=linea_base,
        )
    finally:
        modulo_diagnostico.calcular_relacion_2x_1x = original
    return {h["falla"]: h["confianza"] for h in d["hipotesis"]}, d


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--datos", required=True, help="carpeta SRO-Cross-Speed-Dataset (la que contiene data/ y dataset_manifest.csv)")
    parser.add_argument("--velocidades", nargs="+", type=int, default=[900], choices=[600, 900, 1200])
    parser.add_argument("--salida", default=str(RUTA_PROYECTO / "validacion" / "resultados_sro"))
    argumentos = parser.parse_args()

    salida = Path(argumentos.salida)
    salida.mkdir(parents=True, exist_ok=True)
    manifiesto = pd.read_csv(Path(argumentos.datos) / "dataset_manifest.csv")

    filas = []
    for velocidad in argumentos.velocidades:
        muestras = {c: list(leer_muestras(argumentos.datos, c, velocidad, manifiesto)) for c in CONDICIONES}
        corrida_base = sorted({m[1] for m in muestras["normal"]})[0]
        muestra_base = next(m for m in muestras["normal"] if m[1] == corrida_base)
        lineas_base = {}
        for ubicacion in UBICACIONES:
            datos = datos_de_ubicacion(muestra_base[2], ubicacion)
            lineas_base[ubicacion] = linea_base_de(datos, muestra_base[3], velocidad)
        print(f"{velocidad} r/min: linea base = {muestra_base[0]} (corrida {corrida_base}); esa corrida no se evalua", flush=True)

        for condicion in CONDICIONES:
            for numero, (sample_id, corrida, senales, fs) in enumerate(muestras[condicion], start=1):
                if corrida == corrida_base:
                    continue
                for ubicacion in UBICACIONES:
                    datos = datos_de_ubicacion(senales, ubicacion)
                    fft = calcular_fft(datos=datos, frecuencia_muestreo=fs, frecuencia_maxima=300)
                    fila = {"velocidad_rpm": velocidad, "condicion": ETIQUETA[condicion], "ubicacion": ubicacion, "corrida": corrida, "muestra": sample_id}
                    for escenario, con_relacion in ESCENARIOS:
                        hipotesis, detalle = diagnosticar(fft, datos, fs, velocidad, lineas_base[ubicacion], con_relacion)
                        for falla in FALLAS:
                            fila[f"{escenario}:{falla}"] = hipotesis.get(falla, 0.0)
                    razon = calcular_relacion_2x_1x(modulo_diagnostico.analizar_espectro_fft(fft, detalle["velocidad"]["rpm"])[0])
                    fila["razon_2x_1x"] = None if razon is None else round(razon, 3)
                    fila["rpm_usada"] = round(detalle["velocidad"]["rpm"], 1)
                    filas.append(fila)
                if numero % 50 == 0:
                    print(f"  {velocidad} r/min {condicion}: {numero}/{len(muestras[condicion])}", flush=True)

    tabla = pd.DataFrame(filas)
    tabla.to_csv(salida / "sro_por_muestra.csv", index=False)
    escribir_resumen(tabla, salida / "resumen.txt")
    print(f"\nGuardado en {salida}")


def porcentaje(serie_booleana):
    return f"{100 * serie_booleana.mean():.0f} %"


def escribir_resumen(tabla, destino):
    lineas = [
        "Validacion de desbalanceo y desalineacion con SRO (1 s por muestra, velocidad nominal declarada, linea base = primera corrida normal de cada velocidad)",
        "",
        "Cada celda: % de muestras con esa hipotesis en confianza >= 0,70. Ninguno de los umbrales del motor se ajusto con este dataset.",
        "",
    ]
    for escenario, _ in ESCENARIOS:
        lineas.append(f"== Escenario: {escenario}")
        for (velocidad, ubicacion), sub in tabla.groupby(["velocidad_rpm", "ubicacion"]):
            lineas.append(f"-- {velocidad} r/min, ubicacion {ubicacion}")
            lineas.append(f"{'condicion':16s}{'N':>5s}{'corridas':>9s}  {'desbalanceo':>12s}{'parale.':>9s}{'angular':>9s}  {'ninguna>=0,3':>13s}  razon 2x/1x (mediana)")
            for condicion in ("normal", "desbalanceo", "desalineacion"):
                grupo = sub[sub["condicion"] == condicion]
                columnas = {falla: grupo[f"{escenario}:{falla}"] for falla in FALLAS}
                ninguna = (pd.concat(columnas, axis=1) < 0.30).all(axis=1)
                lineas.append(
                    f"{condicion:16s}{len(grupo):>5d}{grupo['corrida'].nunique():>9d}  {porcentaje(columnas['desbalanceo'] >= UMBRAL_PRINCIPAL):>12s}"
                    f"{porcentaje(columnas['desalineacion_paralela'] >= UMBRAL_PRINCIPAL):>9s}{porcentaje(columnas['desalineacion_angular'] >= UMBRAL_PRINCIPAL):>9s}"
                    f"  {porcentaje(ninguna):>13s}  {grupo['razon_2x_1x'].median():.2f}"
                )
        lineas.append("")
    destino.write_text("\n".join(lineas), encoding="utf-8")
    print("\n".join(lineas))


if __name__ == "__main__":
    main()
