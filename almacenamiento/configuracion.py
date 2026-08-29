"""
Módulo de configuración de MotorGuardian.

Responsabilidad:
    Leer los archivos de configuración del proyecto.
"""

from pathlib import Path
import yaml


def cargar_configuracion():

    ruta_config = (
        Path(__file__).parent.parent
        / "config"
        / "aws.yaml"
    )

    with open(ruta_config, "r", encoding="utf-8") as archivo:

        configuracion = yaml.safe_load(archivo)

    return configuracion
