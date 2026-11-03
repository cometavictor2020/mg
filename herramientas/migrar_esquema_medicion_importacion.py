"""
Herramienta para migrar la tabla medicion: agrega las columnas archivo_origen
y mapeo_importacion (D-061), donde queda registrado el nombre del archivo
original y el mapeo confirmado cuando una medicion se importo desde un formato
distinto al interno. Ambas son opcionales.

La tabla nueva plantilla_importacion la crea crear_tablas_basedatos.py.

No destruye la tabla ni sus filas. Es seguro ejecutarla varias veces:
revisa si ya se aplico antes de intentarlo. Las mediciones existentes quedan
con ambas columnas en NULL (= el archivo ya venia en el formato interno).
"""

from pathlib import Path
import sys

RUTA_PROYECTO = Path(__file__).parent.parent
sys.path.append(str(RUTA_PROYECTO))

from sqlalchemy import inspect, text

from basedatos.conexion import engine

COLUMNAS_NUEVAS = {
    "archivo_origen": "VARCHAR(255)",
    "mapeo_importacion": "JSON",
}


def columnas_actuales():
    inspector = inspect(engine)
    return {columna["name"] for columna in inspector.get_columns("medicion")}


def main():
    columnas = columnas_actuales()

    with engine.begin() as conexion:
        for nombre, tipo in COLUMNAS_NUEVAS.items():
            if nombre not in columnas:
                conexion.execute(text(f"ALTER TABLE medicion ADD COLUMN {nombre} {tipo}"))
                print(f"Columna '{nombre}' agregada.")
            else:
                print(f"Columna '{nombre}' ya existia.")

    print("Migracion completada.")


if __name__ == "__main__":
    main()
