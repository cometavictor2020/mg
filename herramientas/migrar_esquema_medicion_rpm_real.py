"""
Herramienta para migrar la tabla medicion: agrega la columna rpm_real
(D-057), donde queda registrada la velocidad de giro real (r/min) que el
operador declara al cargar una medicion. Es opcional.

No destruye la tabla ni sus filas. Es seguro ejecutarla varias veces:
revisa si ya se aplico antes de intentarlo. Las mediciones existentes
quedan con rpm_real en NULL: el motor de diagnostico estima la velocidad
desde el espectro, o usa la nominal del equipo si no puede.
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
        if "rpm_real" not in columnas:
            conexion.execute(text("ALTER TABLE medicion ADD COLUMN rpm_real FLOAT"))
            print("Columna 'rpm_real' agregada.")
        else:
            print("Columna 'rpm_real' ya existia.")

    print("Migracion completada.")


if __name__ == "__main__":
    main()
