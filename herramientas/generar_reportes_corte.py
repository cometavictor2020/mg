"""
Genera el PDF de diagnostico del sistema para archivos .mat de CWRU, SIN pasar por la base de datos.

El endpoint POST /api/reportes (backend/api/administracion/reportes.py) lee de la base de datos el equipo, el
sensor y la medicion y luego hace exactamente lo que hace este script: toma los primeros 2 s de la medicion,
calcula la FFT, corre diagnosticar_sensor() y arma el PDF con generar_pdf_reporte(). Aqui esas dos funciones se
llaman con los datos del .mat y un equipo/sensor ficticios, por lo que:
    - el PDF es el mismo que genera la aplicacion para una medicion con esos datos;
    - no se escribe nada en la base de datos ni se dispara ningun aviso por correo o Telegram (la carga real de
      una medicion los dispara en segundo plano si el hallazgo supera los umbrales de config/notificaciones.yaml).

Datos del equipo ficticio (de la documentacion de CWRU): rodamiento SKF 6205-2RS del lado de accionamiento, 9
elementos rodantes, d = 7,94 mm, D = 39,04 mm, contacto 0 grados; 48 kHz; velocidad nominal 1797 r/min a 0 hp; la
velocidad real es la que declara cada archivo. No se declara potencia, por lo que la severidad ISO 20816-3 sale
"no evaluable".

Uso:
    cd C:\\Users\\comet\\Documents\\mg
    .\\venv\\Scripts\\python.exe herramientas\\generar_reportes_corte.py
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

RUTA_PROYECTO = Path(__file__).parent.parent
sys.path.insert(0, str(RUTA_PROYECTO))

from backend.procesamiento.diagnostico import diagnosticar_sensor  # noqa: E402
from backend.procesamiento.frecuencia import calcular_fft  # noqa: E402
from backend.procesamiento.importador_mat import leer_canales_y_escalares  # noqa: E402
from backend.procesamiento.pdf_reporte import generar_pdf_reporte  # noqa: E402

# Ruta por defecto (equipo del desarrollador); se puede pasar por argumento.
DATOS_POR_DEFECTO = (
    r"C:\Todo\Usach\Proyecto-titulo\Datasets\Vibraciones-Kaggle\Dataset02-MFPT-Mechanical Failure Prevention "
    r"Technology\Paper-Envolvente-Transformada-Hilbert"
)

FRECUENCIA_MUESTREO = 48000
DURACION_VENTANA_S = 2.0  # igual que reportes.py::DURACION_VENTANA_SEGUNDOS
RPM_NOMINAL = 1797
RODAMIENTO_SKF_6205 = SimpleNamespace(
    codigo="SKF-6205", numero_elementos_rodantes=9, diametro_elemento_mm=7.94, diametro_paso_mm=39.04, angulo_contacto_grados=0.0,
)

# (carpeta, archivo, nombre del equipo ficticio)
ARCHIVOS = [
    ("48K-Drive/Set01-07plg1707RPM", "135.mat", "CWRU 135 — pista exterior 7 mils"),
    ("48K-Drive/Set02-021plg1707RPM", "238.mat", "CWRU 238 — pista exterior 21 mils"),
    ("48K-Drive/Set01-07plg1707RPM", "109.mat", "CWRU 109 — pista interior 7 mils"),
    ("48K-Drive/Set02-021plg1707RPM", "213.mat", "CWRU 213 — pista interior 21 mils"),
    ("Normal-Dataset", "97.mat", "CWRU 97 — rodamiento sano"),
]


def generar(ruta_mat, nombre_equipo, salida):
    canales, escalares = leer_canales_y_escalares(ruta_mat.read_bytes())
    señal = canales[next(n for n in canales if "de_time" in n.lower())]
    rpm_real = next(v for n, v in escalares.items() if "rpm" in n.lower())

    # Primeros 2 s de la medicion, como leer_ventana_segundos().
    datos_crudos = pd.DataFrame({"vibracion_x": señal[: round(FRECUENCIA_MUESTREO * DURACION_VENTANA_S)]})
    datos_fft = calcular_fft(datos=datos_crudos, frecuencia_muestreo=FRECUENCIA_MUESTREO, frecuencia_maxima=300)
    diagnostico = diagnosticar_sensor(
        datos_fft,
        RPM_NOMINAL,
        datos_crudos=datos_crudos,
        frecuencia_muestreo=FRECUENCIA_MUESTREO,
        rodamiento=RODAMIENTO_SKF_6205,
        potencia_kw=None,
        tipo_soporte=None,
        unidad_señal="g",
        orientacion_ejes=None,
        linea_base=None,
        rpm_real=rpm_real,
    )
    grafico_crudo = diagnostico.pop("datos_grafico_rodamiento", None)
    graficos = {1: grafico_crudo} if grafico_crudo is not None else {}

    reporte = {
        "equipo": {"nombre": nombre_equipo, "tipo": "Banco de ensayo (CWRU Bearing Data Center)", "planta": "Validación del motor de diagnóstico", "rpm_nominal": RPM_NOMINAL},
        "fecha_generacion": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "sensores": [
            {
                "sensor_id": 1,
                "nombre_tipo": "Acelerómetro lado de accionamiento (eje X, 48 kHz)",
                "tiene_medicion": True,
                "diagnostico": diagnostico,
                "datos_fft": datos_fft,
            }
        ],
    }
    destino = salida / f"reporte_{ruta_mat.stem}.pdf"
    destino.write_bytes(generar_pdf_reporte(reporte, graficos))
    return destino, diagnostico["hipotesis"]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--datos", default=DATOS_POR_DEFECTO, help="carpeta Paper-Envolvente-Transformada-Hilbert")
    parser.add_argument("--salida", default=str(RUTA_PROYECTO / "validacion" / "resultados_corte" / "reportes"), help="carpeta donde se guardan los PDF")
    argumentos = parser.parse_args()

    salida = Path(argumentos.salida)
    salida.mkdir(parents=True, exist_ok=True)
    for subcarpeta, archivo, nombre in ARCHIVOS:
        destino, hipotesis = generar(Path(argumentos.datos) / subcarpeta / archivo, nombre, salida)
        resumen = "; ".join(f"{h['falla'].replace('rodamiento_', '')} {h['confianza']:.2f}" for h in hipotesis) or "(ninguna)"
        print(f"{destino.name}: {resumen}")
    print(f"\nGuardado en {salida}")


if __name__ == "__main__":
    main()
