"""
Herramienta para crear (o actualizar) las tablas de la base de datos
de MotorGuardian a partir de los modelos definidos en basedatos/modelos.py.

Es seguro ejecutarla varias veces: solo crea las tablas que no existan.
"""

from pathlib import Path
import sys

RUTA_PROYECTO = Path(__file__).parent.parent
sys.path.append(str(RUTA_PROYECTO))

from basedatos.conexion import engine
from basedatos.modelos import Base


def main():
    Base.metadata.create_all(engine)
    print("Tablas creadas (o ya existentes) en la base de datos 'motorguardian'.")


if __name__ == "__main__":
    main()
