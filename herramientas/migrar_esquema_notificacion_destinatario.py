"""
Herramienta para migrar la tabla notificacion: agrega la columna
destinatario (D-055), donde queda registrado el correo o chat id al que se
envio cada aviso. La tabla destinatario_notificacion (lista de a quien
avisar) es nueva y la crea herramientas/crear_tablas_basedatos.py.

No destruye la tabla ni sus filas. Es seguro ejecutarla varias veces:
revisa si ya se aplico antes de intentarlo. Los avisos registrados antes de
este cambio (D-054, con destinatarios en .env) quedan con destinatario en
NULL: no cuentan como "ya avisado" para ningun destinatario puntual, asi que
lo vigente se reenvia una vez a cada destinatario tras la migracion.
"""

from pathlib import Path
import sys

RUTA_PROYECTO = Path(__file__).parent.parent
sys.path.append(str(RUTA_PROYECTO))

from sqlalchemy import inspect, text

from basedatos.conexion import engine


def columnas_actuales():
    inspector = inspect(engine)
    return {columna["name"] for columna in inspector.get_columns("notificacion")}


def main():
    columnas = columnas_actuales()

    with engine.begin() as conexion:
        if "destinatario" not in columnas:
            conexion.execute(text("ALTER TABLE notificacion ADD COLUMN destinatario VARCHAR(200)"))
            print("Columna 'destinatario' agregada.")
        else:
            print("Columna 'destinatario' ya existia.")

    print("Migracion completada.")


if __name__ == "__main__":
    main()
