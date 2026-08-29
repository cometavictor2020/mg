"""
Herramienta para subir manualmente un archivo de vibración a Amazon S3.

Control manual de acceso a AWS:
    La llamada real de subida (subir_archivo_s3) queda comentada
    a propósito. El módulo de almacenamiento es completamente
    funcional, pero no se ejecuta ningún acceso a AWS de forma
    automática. Para subir el archivo, descomenta manualmente el
    bloque "EJECUCIÓN" al final de este archivo.
"""

from pathlib import Path
import sys

RUTA_PROYECTO = Path(__file__).parent.parent
sys.path.append(str(RUTA_PROYECTO))

from almacenamiento.configuracion import cargar_configuracion
from almacenamiento.almacenamiento_s3 import subir_archivo_s3


def main():

    configuracion = cargar_configuracion()

    bucket = configuracion["aws"]["bucket"]
    raiz_storage = configuracion["storage"]["root"]

    ruta_local = (
        RUTA_PROYECTO
        / "datos"
        / "datos_vibracion_motor.csv"
    )

    clave_s3 = f"{raiz_storage}/PL0001/MTR00001/vibration/datos_vibracion_motor.csv"

    # --- EJECUCIÓN (control manual: descomentar para subir a AWS) ---
    # resultado = subir_archivo_s3(ruta_local, bucket, clave_s3)
    #
    # if resultado:
    #     print("Archivo subido correctamente a S3.")
    # else:
    #     print("El archivo no fue subido porque ya existía en S3.")

    print(
        "Acceso a AWS deshabilitado por control manual. "
        "Descomenta el bloque EJECUCIÓN en subir_archivo_s3.py para subir "
        f"'{ruta_local.name}' al bucket '{bucket}' bajo la clave '{clave_s3}'."
    )


if __name__ == "__main__":
    main()
