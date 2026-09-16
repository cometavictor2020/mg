"""
Herramienta para registrar la medicion real de vibracion existente en
la base de datos, asociandola al sensor de "Motor Bomba Principal".

Hoy solo existe un archivo de datos reales (datos/datos_vibracion_motor.csv),
compartido por el equipo/sensor que ya se creo al probar Configuracion.
Es seguro ejecutarla varias veces: si ya existe una medicion para ese
sensor con la misma ruta de archivo, no se duplica.
"""

from pathlib import Path
import sys

RUTA_PROYECTO = Path(__file__).parent.parent
sys.path.append(str(RUTA_PROYECTO))

from basedatos.conexion import SesionLocal
from basedatos.modelos import Equipo, Medicion, Sensor

NOMBRE_EQUIPO = "Motor Bomba Principal"
RUTA_ARCHIVO_DATOS = "datos/datos_vibracion_motor.csv"
FRECUENCIA_MUESTREO = 10000


def main():
    sesion = SesionLocal()

    try:
        equipo = (
            sesion.query(Equipo)
            .filter(Equipo.nombre == NOMBRE_EQUIPO)
            .first()
        )
        if not equipo:
            print(f"No existe el equipo '{NOMBRE_EQUIPO}'. Nada que hacer.")
            return

        sensor = (
            sesion.query(Sensor)
            .filter(Sensor.equipo_id == equipo.id)
            .first()
        )
        if not sensor:
            print(f"El equipo '{NOMBRE_EQUIPO}' no tiene ningun sensor. Nada que hacer.")
            return

        existente = (
            sesion.query(Medicion)
            .filter(
                Medicion.sensor_id == sensor.id,
                Medicion.ruta_archivo_local == RUTA_ARCHIVO_DATOS,
            )
            .first()
        )
        if existente:
            print(f"Ya existe la medicion (id={existente.id}). No se duplica.")
            return

        medicion = Medicion(
            sensor_id=sensor.id,
            frecuencia_muestreo=FRECUENCIA_MUESTREO,
            ruta_archivo_local=RUTA_ARCHIVO_DATOS,
            estado_respaldo_s3="pendiente",
        )
        sesion.add(medicion)
        sesion.commit()
        print(f"Medicion registrada (id={medicion.id}) para sensor id={sensor.id}.")

    finally:
        sesion.close()


if __name__ == "__main__":
    main()
