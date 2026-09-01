"""
Modulo de conexion a la base de datos de MotorGuardian (MySQL).

Responsabilidad:
    Crear el engine y las sesiones de SQLAlchemy a partir de las
    credenciales definidas en .env (nunca hardcodeadas en el codigo).
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

RUTA_PROYECTO = Path(__file__).parent.parent
load_dotenv(RUTA_PROYECTO / ".env")

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_NAME = os.getenv("DB_NAME", "motorguardian")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

URL_BASE_DATOS = (
    f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

engine = create_engine(URL_BASE_DATOS, echo=False)
SesionLocal = sessionmaker(bind=engine)
