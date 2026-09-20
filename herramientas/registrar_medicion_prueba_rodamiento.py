"""
Herramienta para registrar, como medicion de PRUEBA, el CSV sintetico de
falla de rodamiento (herramientas/generar_csv_falla_rodamiento.py) en el
sensor existente de "Motor Bomba Principal".

Ojo: al quedar con fecha_captura mas reciente que la medicion real
existente, esta medicion de prueba pasa a ser la que usan el Analizador
de Vibraciones y Reportes por defecto (siempre toman la mas reciente
por sensor). La medicion real no se borra ni se pierde - solo deja de
ser la "mas reciente" mientras esta quede registrada. Para volver a ver
la señal real, basta con eliminar esta medicion de prueba (por id, o
agregando aqui un DELETE) o generar una medicion real mas nueva.

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
RUTA_ARCHIVO_DATOS = "datos/datos_vibracion_falla_rodamiento_pista_externa.csv"
FRECUENCIA_MUESTREO = 1000


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
            print(f"Ya existe la medicion de prueba (id={existente.id}). No se duplica.")
            return

        medicion = Medicion(
            sensor_id=sensor.id,
            frecuencia_muestreo=FRECUENCIA_MUESTREO,
            ruta_archivo_local=RUTA_ARCHIVO_DATOS,
            estado_respaldo_s3="pendiente",
        )
        sesion.add(medicion)
        sesion.commit()
        print(f"Medicion de prueba registrada (id={medicion.id}) para sensor id={sensor.id} ({sensor.codigo}).")
        print("Recuerda: es la mas reciente ahora, asi que reemplaza a la real como vista por defecto.")

    finally:
        sesion.close()


if __name__ == "__main__":
    main()
