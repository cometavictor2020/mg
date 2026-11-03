"""
Genera el PDF de diagnostico del sistema para archivos del dataset de rotor de Ottawa (desbalanceo y
desalineacion), con una LINEA BASE tomada del archivo sano de la misma velocidad, SIN pasar por la base de datos.

Hace lo mismo que la aplicacion (ver generar_reportes_corte.py): marcar la linea base replica
lineas_base.py::marcar_linea_base (velocidad de esa medicion, amplitud en 1x/2x/3x y velocidad RMS de banda) y el
reporte replica reportes.py::generar_reporte (primeros 2 s de la medicion, FFT hasta 300 Hz, diagnosticar_sensor y
generar_pdf_reporte). No escribe nada en la base de datos ni dispara avisos.

Con linea base el sistema puede decir si el 1x/2x/3x esta ELEVADO respecto de la maquina sana; sin ella, la
confianza de desbalanceo y desalineacion queda acotada a 50 % (D-056). Aun con linea base, en este dataset el sistema
no distingue desbalanceo de desalineacion: ver validacion/resultados_d066/resumen.txt.

Datos del dataset (Ottawa, Mendeley): 3 acelerometros (columnas 1, 3 y 4 del CSV, m/s2) como X, Y, Z; 42 kHz; el
codigo de velocidad 4 es 60 Hz (3600 r/min) constante. Potencia 2,2 kW y soporte rigido: los valores que uso la
validacion (validar_motor.py).

Uso:
    cd C:\\Users\\comet\\Documents\\mg
    .\\venv\\Scripts\\python.exe herramientas\\generar_reportes_rotor_corte.py
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

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
DATOS_POR_DEFECTO = r"C:\Todo\Usach\Proyecto-titulo\Titulo\Datasets-csv\05.-Mendeley\2_CSV_Data_Files"

FRECUENCIA_MUESTREO = 42000
DURACION_VENTANA_S = 2.0  # igual que reportes.py::DURACION_VENTANA_SEGUNDOS
VELOCIDAD_HZ = {1: 15, 2: 30, 3: 45, 4: 60}
POTENCIA_KW = 2.2
TIPO_SOPORTE = "rigido"
UNIDAD = "m/s2"

# (clase, codigo de velocidad, nombre del equipo ficticio)
SANO = ("H_H", 4)
ARCHIVOS = [
    ("R_U", 4, "Ottawa R_U_4_0 — desbalanceo de rotor, 60 Hz sin carga"),
    ("R_M", 4, "Ottawa R_M_4_0 — desalineación de rotor, 60 Hz sin carga"),
]


def leer_ventana(base, clase, codigo):
    ruta = Path(base) / "1_Unloaded_Condition" / f"{clase}_{codigo}_0.csv"
    tabla = pd.read_csv(ruta, usecols=[0, 2, 3], nrows=round(FRECUENCIA_MUESTREO * DURACION_VENTANA_S))
    tabla.columns = ["vibracion_x", "vibracion_y", "vibracion_z"]
    return tabla


def linea_base_de(datos_crudos, rpm_nominal):
    """Lo que guarda lineas_base.py::marcar_linea_base para una medicion sana sin velocidad declarada."""
    datos_fft = calcular_fft(datos=datos_crudos, frecuencia_muestreo=FRECUENCIA_MUESTREO, frecuencia_maxima=300)
    velocidad = resolver_velocidad(datos_fft, rpm_nominal, None)
    valores = calcular_valores_linea_base(datos_fft, velocidad["rpm"], TOLERANCIA_FRECUENCIA_PCT)
    valores["velocidad_origen"] = velocidad["origen"]
    valores["velocidad_rms"] = calcular_valores_velocidad_linea_base(
        datos_crudos, FRECUENCIA_MUESTREO, UNIDAD, velocidad["rpm"], cargar_normativa()
    )
    return {"valores": valores, "fecha": "referencia"}


def generar(base, clase, codigo, nombre_equipo, linea_base, salida):
    rpm_nominal = VELOCIDAD_HZ[codigo] * 60
    datos_crudos = leer_ventana(base, clase, codigo)
    datos_fft = calcular_fft(datos=datos_crudos, frecuencia_muestreo=FRECUENCIA_MUESTREO, frecuencia_maxima=300)
    diagnostico = diagnosticar_sensor(
        datos_fft,
        rpm_nominal,
        datos_crudos=datos_crudos,
        frecuencia_muestreo=FRECUENCIA_MUESTREO,
        rodamiento=None,
        potencia_kw=POTENCIA_KW,
        tipo_soporte=TIPO_SOPORTE,
        unidad_señal=UNIDAD,
        orientacion_ejes=None,
        linea_base=linea_base,
        rpm_real=None,
    )
    diagnostico.pop("datos_grafico_rodamiento", None)

    reporte = {
        "equipo": {"nombre": nombre_equipo, "tipo": "Banco de ensayo de rotor (dataset Ottawa)", "planta": "Validación del motor de diagnóstico", "rpm_nominal": rpm_nominal},
        "fecha_generacion": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "sensores": [
            {
                "sensor_id": 1,
                "nombre_tipo": "Acelerómetro triaxial (X, Y, Z; 42 kHz)",
                "tiene_medicion": True,
                "diagnostico": diagnostico,
                "datos_fft": datos_fft,
            }
        ],
    }
    destino = salida / f"reporte_{clase}_{codigo}_0.pdf"
    destino.write_bytes(generar_pdf_reporte(reporte, {}))
    return destino, diagnostico


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--datos", default=DATOS_POR_DEFECTO, help="carpeta 2_CSV_Data_Files del dataset de Ottawa")
    parser.add_argument("--salida", default=str(RUTA_PROYECTO / "validacion" / "resultados_corte" / "reportes"), help="carpeta donde se guardan los PDF")
    argumentos = parser.parse_args()

    salida = Path(argumentos.salida)
    salida.mkdir(parents=True, exist_ok=True)
    clase_sana, codigo_sano = SANO
    linea_base = linea_base_de(leer_ventana(argumentos.datos, clase_sana, codigo_sano), VELOCIDAD_HZ[codigo_sano] * 60)
    print(f"Línea base: {clase_sana}_{codigo_sano}_0 (velocidad {linea_base['valores']['velocidad_origen']}: {linea_base['valores']['rpm']:.0f} r/min)")

    for clase, codigo, nombre in ARCHIVOS:
        destino, diagnostico = generar(argumentos.datos, clase, codigo, nombre, linea_base, salida)
        hipotesis = "; ".join(f"{h['falla']} {h['confianza']:.2f}" for h in diagnostico["hipotesis"]) or "(ninguna)"
        cambio = diagnostico.get("cambio_linea_base") or {}
        print(f"{destino.name}: {hipotesis} | cambio vs línea base: ×{cambio.get('razon')} ({cambio.get('nivel')}) | velocidad usada {diagnostico['velocidad']['rpm']:.0f} r/min ({diagnostico['velocidad']['origen']})")
    print(f"\nGuardado en {salida}")


if __name__ == "__main__":
    main()
