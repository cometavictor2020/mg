"""
Modulo de seguridad de MotorGuardian.

Responsabilidad:
    Hashear/verificar contrasenas y crear/verificar tokens de acceso (JWT).
    No contiene endpoints ni logica de negocio.
"""

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import bcrypt
import jwt
from dotenv import load_dotenv
from fastapi import Header, HTTPException

RUTA_PROYECTO = Path(__file__).parent.parent
load_dotenv(RUTA_PROYECTO / ".env")

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITMO = "HS256"
HORAS_EXPIRACION_TOKEN = 8


def crear_hash_password(password):
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verificar_password(password, password_hash):
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def crear_token_acceso(datos):
    payload = datos.copy()
    payload["exp"] = datetime.now(timezone.utc) + timedelta(hours=HORAS_EXPIRACION_TOKEN)
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITMO)


def verificar_token(token):
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITMO])
    except jwt.PyJWTError:
        return None


def obtener_usuario_actual(authorization: str = Header(default=None)):
    """
    Dependencia de FastAPI: exige un token JWT valido en el header
    Authorization ("Bearer <token>"). Los endpoints protegidos la
    declaran con Depends(obtener_usuario_actual) - ellos no contienen
    la logica de verificacion, solo la orquestan (mismo principio que
    D-012/D-024).
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="No autenticado")

    payload = verificar_token(authorization.removeprefix("Bearer "))

    if not payload:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")

    return payload
