"""
Herramienta para respaldar la base de datos MySQL de MotorGuardian.

Genera un volcado (mysqldump) con fecha y hora en respaldos/, una
carpeta local excluida de Git (D-022: la base de datos nunca se
respalda via Git/GitHub, ni el archivo de datos ni un dump).

Uso:
    python herramientas/respaldar_basedatos.py
"""

import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

RUTA_PROYECTO = Path(__file__).parent.parent
load_dotenv(RUTA_PROYECTO / ".env")

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_NAME = os.getenv("DB_NAME", "motorguardian")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

RUTA_MYSQLDUMP_CONOCIDA = r"C:\Program Files\MySQL\MySQL Server 8.4\bin\mysqldump.exe"
RUTA_RESPALDOS = RUTA_PROYECTO / "respaldos"


def encontrar_mysqldump():
    encontrado = shutil.which("mysqldump")
    if encontrado:
        return encontrado

    if Path(RUTA_MYSQLDUMP_CONOCIDA).exists():
        return RUTA_MYSQLDUMP_CONOCIDA

    raise FileNotFoundError(
        "No se encontro mysqldump. Verifica que MySQL Server este instalado."
    )


def main():
    RUTA_RESPALDOS.mkdir(exist_ok=True)

    marca_tiempo = datetime.now().strftime("%Y%m%d_%H%M%S")
    ruta_salida = RUTA_RESPALDOS / f"{DB_NAME}_{marca_tiempo}.sql"

    comando = [
        encontrar_mysqldump(),
        f"--host={DB_HOST}",
        f"--port={DB_PORT}",
        f"--user={DB_USER}",
        DB_NAME,
    ]

    # La contrasena se pasa por variable de entorno, no como argumento de
    # linea de comandos (evita que quede visible en el listado de procesos).
    entorno = os.environ.copy()
    entorno["MYSQL_PWD"] = DB_PASSWORD

    with open(ruta_salida, "w", encoding="utf-8") as archivo_salida:
        resultado = subprocess.run(
            comando,
            stdout=archivo_salida,
            stderr=subprocess.PIPE,
            env=entorno,
            text=True,
        )

    if resultado.returncode != 0:
        ruta_salida.unlink(missing_ok=True)
        raise RuntimeError(f"mysqldump fallo:\n{resultado.stderr}")

    tamano_kb = ruta_salida.stat().st_size / 1024
    print(f"Respaldo creado: {ruta_salida} ({tamano_kb:.1f} KB)")


if __name__ == "__main__":
    main()
