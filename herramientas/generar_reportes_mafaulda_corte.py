"""
Genera el PDF de diagnostico del sistema para archivos del dataset MAFAULDA (UFRJ/COPPE: desbalanceo y desalineacion
con masa o desplazamiento conocidos y tacometro), con una LINEA BASE tomada del archivo "normal" de la misma
velocidad, SIN pasar por la base de datos.

Hace lo mismo que la aplicacion (ver generar_reportes_rotor_corte.py): marcar la linea base replica
lineas_base.py::marcar_linea_base y el reporte replica reportes.py::generar_reporte (primeros 2 s de la medicion,
FFT hasta 300 Hz, diagnosticar_sensor y generar_pdf_reporte). No escribe nada en la base de datos ni dispara avisos.

Datos del dataset (MAFAULDA, http://www02.smt.ufrj.br/~offshore/mfs/): CSV de 8 columnas sin encabezado, 50 kHz, 5 s:
tacometro, acelerometro del lado del acople (axial, radial, tangencial; columnas 2-4), acelerometro del otro lado
(columnas 5-7) y microfono. El nombre del archivo es la velocidad nominal en Hz; la velocidad REAL se mide con el
tacometro (un pulso por vuelta), que es lo que un operador declararia como r/min reales al cargar la medicion.

La pagina del dataset no declara la unidad de las columnas del acelerometro, por eso aqui no se declara unidad,
potencia ni tipo de soporte: no se calcula la severidad ISO 20816-3 (el reporte lo indica) y no se inventan datos
del equipo.

Uso:
    cd C:\\Users\\comet\\Documents\\mg
    .\\venv\\Scripts\\python.exe herramientas\\generar_reportes_mafaulda_corte.py
    .\\venv\\Scripts\\python.exe herramientas\\generar_reportes_mafaulda_corte.py --velocidad-hz 40
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

RUTA_PROYECTO = Path(__file__).parent.parent
sys.path.insert(0, str(RUTA_PROYECTO))

from backend.procesamiento.cambio_linea_base import calcular_valores_velocidad_linea_base  # noqa: E402
from backend.procesamiento.diagnostico import (  # noqa: E402
    TOLERANCIA_FRECUENCIA_PCT,
    cargar_normativa,
    diagnosticar_sensor,
    resolver_velocidad,
)
from backend.procesamiento.frecuencia import calcular_fft  # noqa: E402
from backend.procesamiento.linea_base import calcular_valores_linea_base  # noqa: E402
from backend.procesamiento.pdf_reporte import generar_pdf_reporte  # noqa: E402

# Ruta por defecto (equipo del desarrollador); se puede pasar por argumento.
DATOS_POR_DEFECTO = str(Path.home() / "Downloads")

FRECUENCIA_MUESTREO = 50000
DURACION_VENTANA_S = 2.0  # igual que reportes.py::DURACION_VENTANA_SEGUNDOS
COLUMNAS_ACELEROMETRO = [1, 2, 3]  # lado del acople: axial, radial, tangencial -> X, Y, Z
# Lo que la pagina del dataset dice de cada columna: 2 axial, 3 radial, 4 tangencial. Los ejes radial y tangencial
# son perpendiculares al eje del rotor; cual es horizontal y cual vertical no esta declarado, y al motor solo le
# importa "radial" frente a "axial". Se declara como lo haria un operador al configurar el sensor.
ORIENTACION_EJES = {"x": "axial", "y": "radial_vertical", "z": "radial_horizontal"}

# (carpeta de la condicion, etiqueta del archivo de salida, descripcion)
SANO = ("normal/normal", "normal")
CONDICIONES = [
    ("imbalance/imbalance/6g", "desbalanceo_6g", "desbalanceo, masa de 6 g"),
    ("imbalance/imbalance/20g", "desbalanceo_20g", "desbalanceo, masa de 20 g"),
    ("imbalance/imbalance/35g", "desbalanceo_35g", "desbalanceo, masa de 35 g"),
]


def velocidad_de_archivo(ruta):
    return float(ruta.stem)


def elegir_archivos(base, velocidad_objetivo_hz):
    """Un archivo por condicion, todos con la MISMA velocidad nominal (la comun mas cercana al objetivo)."""
    carpetas = [SANO[0]] + [c[0] for c in CONDICIONES]
    velocidades = [{velocidad_de_archivo(p) for p in (Path(base) / carpeta).glob("*.csv")} for carpeta in carpetas]
    comunes = set.intersection(*velocidades)
    if not comunes:
        raise SystemExit("No hay una velocidad nominal presente en todas las condiciones.")
    velocidad = min(comunes, key=lambda v: abs(v - velocidad_objetivo_hz))
    return velocidad, {carpeta: Path(base) / carpeta / f"{velocidad:g}.csv" for carpeta in carpetas}


def leer_archivo(ruta):
    """Devuelve (ventana de 2 s con vibracion_x/y/z, r/min medidas con el tacometro en los 5 s completos)."""
    tabla = pd.read_csv(ruta, header=None)
    tacometro = tabla[0].to_numpy()
    centrado = tacometro - (tacometro.max() + tacometro.min()) / 2
    flancos = np.where((centrado[:-1] < 0) & (centrado[1:] >= 0))[0]
    rpm_medidas = 60.0 / (np.diff(flancos).mean() / FRECUENCIA_MUESTREO)

    ventana = tabla.iloc[: round(FRECUENCIA_MUESTREO * DURACION_VENTANA_S), COLUMNAS_ACELEROMETRO].copy()
    ventana.columns = ["vibracion_x", "vibracion_y", "vibracion_z"]
    return ventana, rpm_medidas


def linea_base_de(datos_crudos, rpm_nominal, rpm_real):
    """Lo que guarda lineas_base.py::marcar_linea_base para una medicion sana con velocidad declarada."""
    datos_fft = calcular_fft(datos=datos_crudos, frecuencia_muestreo=FRECUENCIA_MUESTREO, frecuencia_maxima=300)
    velocidad = resolver_velocidad(datos_fft, rpm_nominal, rpm_real)
    valores = calcular_valores_linea_base(datos_fft, velocidad["rpm"], TOLERANCIA_FRECUENCIA_PCT)
    valores["velocidad_origen"] = velocidad["origen"]
    valores["velocidad_rms"] = calcular_valores_velocidad_linea_base(
        datos_crudos, FRECUENCIA_MUESTREO, None, velocidad["rpm"], cargar_normativa()
    )
    return {"valores": valores, "fecha": "referencia"}


def generar(ruta, etiqueta, descripcion, velocidad_hz, linea_base, salida):
    rpm_nominal = velocidad_hz * 60
    datos_crudos, rpm_medidas = leer_archivo(ruta)
    datos_fft = calcular_fft(datos=datos_crudos, frecuencia_muestreo=FRECUENCIA_MUESTREO, frecuencia_maxima=300)
    diagnostico = diagnosticar_sensor(
        datos_fft,
        rpm_nominal,
        datos_crudos=datos_crudos,
        frecuencia_muestreo=FRECUENCIA_MUESTREO,
        rodamiento=None,
        potencia_kw=None,
        tipo_soporte=None,
        unidad_señal=None,
        orientacion_ejes=None,  # declararla empeora MAFAULDA: ver validacion/resultados_2x1x/resumen.txt
        linea_base=linea_base,
        rpm_real=rpm_medidas,
    )
    diagnostico.pop("datos_grafico_rodamiento", None)

    reporte = {
        "equipo": {
            "nombre": f"MAFAULDA {ruta.parent.name}/{ruta.name} — {descripcion}",
            "tipo": "Simulador de fallas SpectraQuest (dataset MAFAULDA)",
            "planta": "Validación del motor de diagnóstico",
            "rpm_nominal": rpm_nominal,
        },
        "fecha_generacion": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "sensores": [
            {
                "sensor_id": 1,
                "nombre_tipo": "Acelerómetro triaxial (axial, radial, tangencial; 50 kHz)",
                "tiene_medicion": True,
                "diagnostico": diagnostico,
                "datos_fft": datos_fft,
            }
        ],
    }
    destino = salida / f"reporte_mafaulda_{etiqueta}.pdf"
    destino.write_bytes(generar_pdf_reporte(reporte, {}))
    return destino, diagnostico, rpm_medidas


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--datos", default=DATOS_POR_DEFECTO, help="carpeta que contiene normal/, imbalance/ (la de Descargas)")
    parser.add_argument("--velocidad-hz", type=float, default=30.0, help="velocidad nominal objetivo; se usa la comun mas cercana")
    parser.add_argument("--salida", default=str(RUTA_PROYECTO / "validacion" / "resultados_corte" / "reportes"), help="carpeta donde se guardan los PDF")
    argumentos = parser.parse_args()

    salida = Path(argumentos.salida)
    salida.mkdir(parents=True, exist_ok=True)
    velocidad_hz, archivos = elegir_archivos(argumentos.datos, argumentos.velocidad_hz)
    print(f"Velocidad nominal comun elegida: {velocidad_hz:g} Hz ({velocidad_hz * 60:.0f} r/min)")

    ruta_sana = archivos[SANO[0]]
    ventana_sana, rpm_sana = leer_archivo(ruta_sana)
    linea_base = linea_base_de(ventana_sana, velocidad_hz * 60, rpm_sana)
    print(f"Línea base: {ruta_sana} (tacómetro {rpm_sana:.0f} r/min; velocidad {linea_base['valores']['velocidad_origen']}: {linea_base['valores']['rpm']:.0f} r/min)")

    for carpeta, etiqueta, descripcion in CONDICIONES:
        ruta = archivos[carpeta]
        destino, diagnostico, rpm_medidas = generar(ruta, etiqueta, descripcion, velocidad_hz, linea_base, salida)
        hipotesis = "; ".join(f"{h['falla']} {h['confianza']:.2f}" for h in diagnostico["hipotesis"]) or "(ninguna)"
        cambio = diagnostico.get("cambio_linea_base") or {}
        print(f"{ruta}\n  -> {destino.name}: {hipotesis} | cambio vs línea base: ×{cambio.get('razon')} ({cambio.get('nivel')}) | tacómetro {rpm_medidas:.0f} r/min, velocidad usada {diagnostico['velocidad']['rpm']:.0f} r/min ({diagnostico['velocidad']['origen']})")
    print(f"\nGuardado en {salida}")


if __name__ == "__main__":
    main()
