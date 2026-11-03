"""
Valida desbalanceo y desalineacion con MAFAULDA usando LOS DOS acelerometros (columnas 2-4 = sensor 1 y 5-7 = sensor 2),
sin pasar por la base de datos y sin modificar el motor.

validar_mafaulda.py solo le entrega al motor el sensor 1, pero la firma de la desalineacion aparece sobre todo en el
sensor 2 (2x radial/tangencial y 1x radial). Aqui el motor actual (diagnosticar_sensor) se ejecuta una vez por sensor,
cada uno con su propia linea base (el archivo normal de velocidad mas cercana, leido en ese mismo sensor), y las
confianzas por falla se combinan con distintas reglas:
    sensor1, sensor2   uno solo (referencia)
    promedio           media de las dos confianzas
    maximo             la mayor de las dos
    minimo             la menor (exige que ambos sensores coincidan)

El diagnostico de cada archivo se resume en un resultado: "desbalanceo", "desalineacion" (paralela o angular, la de
mayor confianza), "empate" o "ninguna" (nada llega a 0,70). La regla de combinacion se fijo ANTES de mirar los
resultados (las cuatro de arriba, sin ajustar pesos) y se evalua en el conjunto de reserva (velocidades fuera de
44,5-46 Hz); la calibracion (18 a 27 archivos) solo se muestra como referencia.

Escenarios: solo_relacion (sin orientacion de ejes) y relacion_y_ejes (con la orientacion declarada: columna axial,
radial y tangencial -> eje axial, radial vertical y radial horizontal), los dos con la relacion 2x/1x activa.

Uso:
    cd C:\\Users\\comet\\Documents\\mg
    .\\venv\\Scripts\\python.exe herramientas\\validar_mafaulda_dos_sensores.py
"""

import argparse
import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd

RUTA_PROYECTO = Path(__file__).parent.parent
sys.path.insert(0, str(RUTA_PROYECTO))
sys.path.insert(0, str(Path(__file__).parent))

from backend.procesamiento.diagnostico import diagnosticar_sensor  # noqa: E402
from backend.procesamiento.frecuencia import calcular_fft  # noqa: E402
from generar_reportes_mafaulda_corte import (  # noqa: E402
    DATOS_POR_DEFECTO,
    DURACION_VENTANA_S,
    FRECUENCIA_MUESTREO,
    linea_base_de,
)
from validar_mafaulda import (  # noqa: E402
    CARPETAS_POR_DEFECTO,
    FALLAS,
    RANGO_CALIBRACION_HZ,
    UMBRAL_PRINCIPAL,
    listar_archivos,
)

SENSORES = {1: [1, 2, 3], 2: [4, 5, 6]}  # sensor -> columnas (axial, radial, tangencial) -> X, Y, Z
ORIENTACION_EJES = {"x": "axial", "y": "radial_vertical", "z": "radial_horizontal"}
ESCENARIOS = (("solo_relacion", None), ("relacion_y_ejes", ORIENTACION_EJES))
COMBINACIONES = ("sensor1", "sensor2", "promedio", "maximo", "minimo")
RESULTADOS = ("ninguna", "desbalanceo", "desalineacion", "empate")
CONDICIONES_ORDEN = ("normal", "desbalanceo", "desalineacion_horizontal", "desalineacion_vertical")

_normales = []
_cache_lineas_base = {}


def leer_archivo(ruta):
    """Devuelve ({sensor: ventana de 2 s con vibracion_x/y/z}, r/min medidas con el tacometro en los 5 s)."""
    tabla = pd.read_csv(ruta, header=None)
    tacometro = tabla[0].to_numpy()
    centrado = tacometro - (tacometro.max() + tacometro.min()) / 2
    flancos = np.where((centrado[:-1] < 0) & (centrado[1:] >= 0))[0]
    rpm_medidas = 60.0 / (np.diff(flancos).mean() / FRECUENCIA_MUESTREO)

    filas = round(FRECUENCIA_MUESTREO * DURACION_VENTANA_S)
    ventanas = {}
    for sensor, columnas in SENSORES.items():
        ventana = tabla.iloc[:filas, columnas].copy()
        ventana.columns = ["vibracion_x", "vibracion_y", "vibracion_z"]
        ventanas[sensor] = ventana
    return ventanas, rpm_medidas


def iniciar_proceso(normales):
    global _normales
    _normales = normales


def lineas_base_para(archivo):
    """Linea base de cada sensor: el normal de velocidad mas cercana (otro archivo distinto del evaluado)."""
    candidatos = [n for n in _normales if n["ruta"] != archivo["ruta"]]
    referencia = min(candidatos, key=lambda n: abs(n["velocidad_hz"] - archivo["velocidad_hz"]))
    clave = referencia["ruta"]
    if clave not in _cache_lineas_base:
        ventanas, rpm = leer_archivo(clave)
        _cache_lineas_base[clave] = {s: linea_base_de(v, referencia["velocidad_hz"] * 60, rpm) for s, v in ventanas.items()}
    return _cache_lineas_base[clave], referencia["ruta"].stem


def evaluar_archivo(archivo):
    try:
        ventanas, rpm_medidas = leer_archivo(archivo["ruta"])
        lineas_base, referencia = lineas_base_para(archivo)
        rpm_nominal = archivo["velocidad_hz"] * 60
        fila = {
            "condicion": archivo["condicion"], "severidad": archivo["severidad"], "velocidad_hz": archivo["velocidad_hz"],
            "conjunto": "calibracion" if RANGO_CALIBRACION_HZ[0] <= archivo["velocidad_hz"] <= RANGO_CALIBRACION_HZ[1] else "reserva",
            "linea_base": referencia, "rpm_tacometro": round(rpm_medidas, 1),
        }
        for sensor, ventana in ventanas.items():
            fft = calcular_fft(datos=ventana, frecuencia_muestreo=FRECUENCIA_MUESTREO, frecuencia_maxima=300)
            for escenario, orientacion in ESCENARIOS:
                d = diagnosticar_sensor(
                    fft, rpm_nominal, datos_crudos=ventana, frecuencia_muestreo=FRECUENCIA_MUESTREO, rodamiento=None,
                    orientacion_ejes=orientacion, linea_base=lineas_base[sensor], rpm_real=rpm_medidas,
                )
                hipotesis = {h["falla"]: h["confianza"] for h in d["hipotesis"]}
                for falla in FALLAS:
                    fila[f"{escenario}:s{sensor}:{falla}"] = hipotesis.get(falla, 0.0)
        return fila
    except Exception as error:  # un archivo defectuoso no detiene la corrida
        print(f"{archivo['ruta']}: {error}", flush=True)
        return None


def combinar(c1, c2, regla):
    return {"sensor1": c1, "sensor2": c2, "promedio": (c1 + c2) / 2, "maximo": np.maximum(c1, c2), "minimo": np.minimum(c1, c2)}[regla]


def resultado_por_archivo(tabla, escenario, regla):
    """Serie con 'ninguna' | 'desbalanceo' | 'desalineacion' | 'empate' segun la hipotesis de mayor confianza >= 0,70."""
    conf = {falla: combinar(tabla[f"{escenario}:s1:{falla}"], tabla[f"{escenario}:s2:{falla}"], regla) for falla in FALLAS}
    desbalanceo = conf["desbalanceo"]
    desalineacion = np.maximum(conf["desalineacion_paralela"], conf["desalineacion_angular"])
    resultado = pd.Series("ninguna", index=tabla.index)
    resultado[(desbalanceo >= UMBRAL_PRINCIPAL) & (desbalanceo > desalineacion)] = "desbalanceo"
    resultado[(desalineacion >= UMBRAL_PRINCIPAL) & (desalineacion > desbalanceo)] = "desalineacion"
    resultado[(desbalanceo >= UMBRAL_PRINCIPAL) & (desbalanceo == desalineacion)] = "empate"
    return resultado


def escribir_resumen(tabla, destino):
    lineas = [
        "Validacion con MAFAULDA usando los dos acelerometros (ventana de 2 s, velocidad del tacometro, linea base del normal mas cercano, por sensor)",
        "",
        f"Archivos evaluados: {len(tabla)} (calibracion: {(tabla['conjunto'] == 'calibracion').sum()}, reserva: {(tabla['conjunto'] == 'reserva').sum()})",
        "Cada fila: % de archivos de esa condicion cuyo diagnostico principal (mayor confianza, >= 0,70) cae en cada resultado.",
        "Lo correcto es: normal -> ninguna; desbalanceo -> desbalanceo; desalineacion (horizontal o vertical) -> desalineacion.",
        "",
    ]
    for escenario, _ in ESCENARIOS:
        for conjunto in ("reserva", "calibracion"):
            sub = tabla[tabla["conjunto"] == conjunto]
            for regla in COMBINACIONES:
                resultado = resultado_por_archivo(sub, escenario, regla)
                lineas.append(f"== {escenario} | {conjunto} | combinacion: {regla}")
                lineas.append(f"{'condicion':26s}{'N':>5s}" + "".join(f"{r:>15s}" for r in RESULTADOS))
                for condicion in CONDICIONES_ORDEN:
                    mascara = sub["condicion"] == condicion
                    if not mascara.any():
                        continue
                    cuenta = resultado[mascara].value_counts(normalize=True)
                    lineas.append(f"{condicion:26s}{mascara.sum():>5d}" + "".join(f"{100 * cuenta.get(r, 0.0):>14.0f}%" for r in RESULTADOS))
                lineas.append("")
    destino.write_text("\n".join(lineas), encoding="utf-8")
    print("\n".join(lineas))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--datos", default=DATOS_POR_DEFECTO, help="carpeta que contiene normal/, imbalance/, ... (la de Descargas)")
    parser.add_argument("--carpetas", nargs="+", default=CARPETAS_POR_DEFECTO + ["vertical-misalignment/vertical-misalignment"])
    parser.add_argument("--salida", default=str(RUTA_PROYECTO / "validacion" / "resultados_dos_sensores"))
    parser.add_argument("--procesos", type=int, default=6)
    argumentos = parser.parse_args()

    salida = Path(argumentos.salida)
    salida.mkdir(parents=True, exist_ok=True)
    archivos = listar_archivos(argumentos.datos, argumentos.carpetas)
    normales = [a for a in archivos if a["condicion"] == "normal"]
    if not normales:
        raise SystemExit("Hace falta la carpeta normal/normal para tomar las lineas base.")

    filas = []
    with Pool(argumentos.procesos, initializer=iniciar_proceso, initargs=(normales,)) as pool:
        for indice, fila in enumerate(pool.imap_unordered(evaluar_archivo, archivos, chunksize=4), start=1):
            if fila is not None:
                filas.append(fila)
            if indice % 50 == 0:
                print(f"[{indice}/{len(archivos)}] listo", flush=True)

    tabla = pd.DataFrame(filas)
    tabla.to_csv(salida / "mafaulda_dos_sensores_por_archivo.csv", index=False)
    escribir_resumen(tabla, salida / "resumen.txt")
    print(f"\nGuardado en {salida}")


if __name__ == "__main__":
    main()
