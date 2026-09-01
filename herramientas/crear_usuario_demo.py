"""
Herramienta para crear (o actualizar) el usuario de demostracion de MotorGuardian.

La contrasena se guarda siempre hasheada (bcrypt) - nunca en texto plano.
Es seguro ejecutarla varias veces: si el usuario ya existe, actualiza su hash.
"""

from pathlib import Path
import sys

RUTA_PROYECTO = Path(__file__).parent.parent
sys.path.append(str(RUTA_PROYECTO))

from basedatos.conexion import SesionLocal
from basedatos.modelos import Usuario
from seguridad.auth import crear_hash_password

NOMBRE_DEMO = "Carlos Mendoza"
EMAIL_DEMO = "admin@motorguardian.io"
PASSWORD_DEMO = "mg2024"
ROL_DEMO = "administrador"


def main():
    sesion = SesionLocal()

    try:
        usuario = (
            sesion.query(Usuario)
            .filter(Usuario.email == EMAIL_DEMO)
            .first()
        )

        if usuario:
            usuario.password_hash = crear_hash_password(PASSWORD_DEMO)
            usuario.nombre = NOMBRE_DEMO
            usuario.rol = ROL_DEMO
            print(f"Usuario demo actualizado: {EMAIL_DEMO}")
        else:
            usuario = Usuario(
                nombre=NOMBRE_DEMO,
                email=EMAIL_DEMO,
                password_hash=crear_hash_password(PASSWORD_DEMO),
                rol=ROL_DEMO,
            )
            sesion.add(usuario)
            print(f"Usuario demo creado: {EMAIL_DEMO}")

        sesion.commit()

    finally:
        sesion.close()


if __name__ == "__main__":
    main()
