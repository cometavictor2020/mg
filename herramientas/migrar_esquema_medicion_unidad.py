"""
Herramienta para migrar la tabla medicion: agrega la columna unidad
(D-040), donde queda registrada la unidad que el operador declara al
cargar un archivo desde la nueva pantalla de carga de mediciones.

No destruye la tabla ni sus filas. Es seguro ejecutarla varias veces:
revisa si ya se aplico antes de intentarlo. Las mediciones existentes
(cargadas antes de este cambio, a mano vía herramientas/) quedan con
unidad en NULL - no se puede inferir retroactivamente cual usaron.
"""

from pathlib import Path
import sys

RUTA_PROYECTO = Path(__file__).parent.parent
sys.path.append(str(RUTA_PROYECTO))

from sqlalchemy import inspect, text

from basedatos.conexion import engine


def columnas_actuales():
    inspector = inspect(engine)
    return {columna["name"] for columna in inspector.get_columns("medicion")}


def main():
    columnas = columnas_actuales()

    with engine.begin() as conexion:
        if "unidad" not in columnas:
            conexion.execute(text("ALTER TABLE medicion ADD COLUMN unidad VARCHAR(30)"))
            print("Columna 'unidad' agregada.")
        else:
            print("Columna 'unidad' ya existia.")

    print("Migracion completada.")


if __name__ == "__main__":
    main()
