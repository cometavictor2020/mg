"""
Valida las reglas de desbalanceo y desalineacion del motor con TODOS los archivos de MAFAULDA descargados
(normal, desbalanceo de 6 a 35 g y desalineacion horizontal de 0,5 a 2,0 mm), sin pasar por la base de datos.

Para cada archivo: ventana de 2 s, velocidad medida con el tacometro (como la declararia un operador) y linea base
tomada del archivo "normal" de velocidad nominal mas cercana (para los propios archivos normales, el mas cercano
OTRO). Se corre el diagnostico en tres escenarios, para separar el efecto de cada cambio:
    antes            sin relacion 2x/1x y sin orientacion de ejes (como estaba)
    solo_relacion    con relacion 2x/1x, sin orientacion
    relacion_y_ejes  con relacion 2x/1x y orientacion de ejes declarada (el reporte actual)

Los umbrales de criterios_proyecto.relacion_2x_1x se fijaron con los archivos de ~45 Hz: el conjunto
"calibracion" son los de velocidad nominal entre 44,5 y 46 Hz; el resto (otras velocidades) es "reserva" y es el
que dice si la regla generaliza.

Uso:
    cd C:\\Users\\comet\\Documents\\mg
    .\\venv\\Scripts\\python.exe herramientas\\validar_mafaulda.py
    .\\venv\\Scripts\\python.exe herramientas\\validar_mafaulda.py --carpetas normal/normal vertical-misalignment/vertical-misalignment
"""

import argparse
import sys
from pathlib import Path

import pandas as pd

RUTA_PROYECTO = Path(__file__).parent.parent
sys.path.insert(0, str(RUTA_PROYECTO))
sys.path.insert(0, str(Path(__file__).parent))

import backend.procesamiento.diagnostico as modulo_diagnostico  # noqa: E402
from backend.procesamiento.diagnostico import calcular_relacion_2x_1x, diagnosticar_sensor  # noqa: E402
from backend.procesamiento.frecuencia import calcular_fft  # noqa: E402
from generar_reportes_mafaulda_corte import (  # noqa: E402
    DATOS_POR_DEFECTO,
    FRECUENCIA_MUESTREO,
    ORIENTACION_EJES,
    leer_archivo,
    linea_base_de,
)

CARPETAS_POR_DEFECTO = ["normal/normal", "imbalance/imbalance", "horizontal-misalignment/horizontal-misalignment"]
RANGO_CALIBRACION_HZ = (44.5, 46.0)
FALLAS = ["desbalanceo", "desalineacion_paralela", "desalineacion_angular"]
UMBRAL_PRINCIPAL = 0.70  # confianza_diagnostico.reglas_salida.marcar_diagnostico_principal_desde_confianza


def condicion_y_severidad(carpeta, archivo):
    """('normal'|'desbalanceo'|'desalineacion_horizontal'|..., severidad) segun la carpeta del archivo."""
    partes = archivo.relative_to(carpeta).parts
    if carpeta.name == "normal":
        return "normal", "-"
    nombre = {"imbalance": "desbalanceo", "horizontal-misalignment": "desalineacion_horizontal", "vertical-misalignment": "desalineacion_vertical"}[carpeta.name]
    return nombre, partes[0]


def listar_archivos(base, carpetas):
    archivos = []
    for carpeta in carpetas:
        raiz = Path(base) / carpeta
        for ruta in sorted(raiz.rglob("*.csv")):
            condicion, severidad = condicion_y_severidad(raiz, ruta)
            archivos.append({"ruta": ruta, "condicion": condicion, "severidad": severidad, "velocidad_hz": float(ruta.stem)})
    return archivos


def diagnosticar(fft, datos, rpm_nominal, rpm_medidas, linea_base, con_relacion, con_ejes):
    original = modulo_diagnostico.calcular_relacion_2x_1x
    if not con_relacion:
        modulo_diagnostico.calcular_relacion_2x_1x = lambda hallazgos: None
    try:
        d = diagnosticar_sensor(
            fft, rpm_nominal, datos_crudos=datos, frecuencia_muestreo=FRECUENCIA_MUESTREO, rodamiento=None,
            orientacion_ejes=ORIENTACION_EJES if con_ejes else None, linea_base=linea_base, rpm_real=rpm_medidas,
        )
    finally:
        modulo_diagnostico.calcular_relacion_2x_1x = original
    return {h["falla"]: h["confianza"] for h in d["hipotesis"]}, d


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--datos", default=DATOS_POR_DEFECTO, help="carpeta que contiene normal/, imbalance/, ... (la de Descargas)")
    parser.add_argument("--carpetas", nargs="+", default=CARPETAS_POR_DEFECTO)
    parser.add_argument("--salida", default=str(RUTA_PROYECTO / "validacion" / "resultados_2x1x"))
    argumentos = parser.parse_args()

    salida = Path(argumentos.salida)
    salida.mkdir(parents=True, exist_ok=True)
    archivos = listar_archivos(argumentos.datos, argumentos.carpetas)
    normales = [a for a in archivos if a["condicion"] == "normal"]
    if not normales:
        raise SystemExit("Hace falta la carpeta normal/normal para tomar las lineas base.")

    lineas_base = {}  # por archivo normal: (linea base, rpm medidas)

    def linea_base_para(archivo):
        candidatos = [n for n in normales if n["ruta"] != archivo["ruta"]]
        referencia = min(candidatos, key=lambda n: abs(n["velocidad_hz"] - archivo["velocidad_hz"]))
        clave = referencia["ruta"]
        if clave not in lineas_base:
            ventana, rpm = leer_archivo(clave)
            lineas_base[clave] = linea_base_de(ventana, referencia["velocidad_hz"] * 60, rpm)
        return lineas_base[clave], referencia["ruta"].stem

    filas = []
    for indice, archivo in enumerate(archivos, start=1):
        try:
            datos, rpm_medidas = leer_archivo(archivo["ruta"])
            linea_base, referencia = linea_base_para(archivo)
            fft = calcular_fft(datos=datos, frecuencia_muestreo=FRECUENCIA_MUESTREO, frecuencia_maxima=300)
            rpm_nominal = archivo["velocidad_hz"] * 60
            fila = {
                "condicion": archivo["condicion"], "severidad": archivo["severidad"], "velocidad_hz": archivo["velocidad_hz"],
                "conjunto": "calibracion" if RANGO_CALIBRACION_HZ[0] <= archivo["velocidad_hz"] <= RANGO_CALIBRACION_HZ[1] else "reserva",
                "linea_base": referencia, "rpm_tacometro": round(rpm_medidas, 1),
            }
            for escenario, con_relacion, con_ejes in (("antes", False, False), ("solo_relacion", True, False), ("relacion_y_ejes", True, True)):
                hipotesis, detalle = diagnosticar(fft, datos, rpm_nominal, rpm_medidas, linea_base, con_relacion, con_ejes)
                for falla in FALLAS:
                    fila[f"{escenario}:{falla}"] = hipotesis.get(falla, 0.0)
            razon = calcular_relacion_2x_1x(modulo_diagnostico.analizar_espectro_fft(fft, rpm_medidas)[0])
            fila["razon_2x_1x"] = None if razon is None else round(razon, 3)
            filas.append(fila)
        except Exception as error:  # un archivo defectuoso no detiene la corrida
            print(f"[{indice}/{len(archivos)}] {archivo['ruta']}: {error}", flush=True)
            continue
        if indice % 25 == 0:
            print(f"[{indice}/{len(archivos)}] listo", flush=True)

    tabla = pd.DataFrame(filas)
    tabla.to_csv(salida / "mafaulda_por_archivo.csv", index=False)
    escribir_resumen(tabla, salida / "resumen.txt")
    print(f"\nGuardado en {salida}")


def porcentaje(serie_booleana):
    return f"{100 * serie_booleana.mean():.0f} %"


def escribir_resumen(tabla, destino):
    lineas = ["Validacion de desbalanceo y desalineacion con MAFAULDA (ventana de 2 s, velocidad del tacometro, linea base del normal mas cercano)", ""]
    lineas.append(f"Archivos evaluados: {len(tabla)} (calibracion: {(tabla['conjunto'] == 'calibracion').sum()}, reserva: {(tabla['conjunto'] == 'reserva').sum()})")
    lineas.append("Cada celda: % de archivos con esa hipotesis en confianza >= 0,70 (diagnostico principal). N entre parentesis.")
    lineas.append("")
    for escenario in ("antes", "solo_relacion", "relacion_y_ejes"):
        lineas.append(f"== Escenario: {escenario}")
        for conjunto in ("reserva", "calibracion"):
            sub = tabla[tabla["conjunto"] == conjunto]
            lineas.append(f"-- {conjunto}")
            lineas.append(f"{'condicion':26s}{'severidad':>10s}{'N':>5s}  {'desbalanceo':>12s}{'parale.':>9s}{'angular':>9s}  {'ninguna>=0,3':>13s}  razon 2x/1x (mediana)")
            for (condicion, severidad), grupo in sub.groupby(["condicion", "severidad"], sort=False):
                columnas = {falla: grupo[f"{escenario}:{falla}"] for falla in FALLAS}
                ninguna = (pd.concat(columnas, axis=1) < 0.30).all(axis=1)
                lineas.append(
                    f"{condicion:26s}{severidad:>10s}{len(grupo):>5d}  {porcentaje(columnas['desbalanceo'] >= UMBRAL_PRINCIPAL):>12s}"
                    f"{porcentaje(columnas['desalineacion_paralela'] >= UMBRAL_PRINCIPAL):>9s}{porcentaje(columnas['desalineacion_angular'] >= UMBRAL_PRINCIPAL):>9s}"
                    f"  {porcentaje(ninguna):>13s}  {grupo['razon_2x_1x'].median():.2f}"
                )
        lineas.append("")
    destino.write_text("\n".join(lineas), encoding="utf-8")
    print("\n".join(lineas))


if __name__ == "__main__":
    main()
