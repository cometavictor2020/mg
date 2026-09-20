"""
Deja lista, en la base de datos real, la prueba end-to-end del motor de
diagnostico de rodamientos (backend/procesamiento/diagnostico_rodamientos.py):

    1. Crea (si no existe) un Rodamiento SKF 6205 en "Motor Bomba
       Principal", con la misma geometria que usa herramientas/
       generar_csv_falla_rodamiento_envolvente.py.
    2. Vincula el sensor existente del equipo a ese rodamiento
       (Sensor.rodamiento_id).
    3. Registra el CSV de falla por impactos (datos/
       datos_vibracion_falla_rodamiento_envolvente.csv, 8000 Hz) como
       medicion de prueba de ese sensor.

Con esto, generar un reporte para "Motor Bomba Principal" desde la app
debería mostrar la hipotesis "rodamiento_pista_exterior".

Es seguro ejecutarla varias veces (no duplica el rodamiento ni la
medicion si ya existen).
"""

from pathlib import Path
import sys

RUTA_PROYECTO = Path(__file__).parent.parent
sys.path.append(str(RUTA_PROYECTO))

from basedatos.conexion import SesionLocal
from basedatos.modelos import Equipo, Medicion, Rodamiento, Sensor
from backend.api.administracion.rodamientos import generar_codigo as generar_codigo_rodamiento

NOMBRE_EQUIPO = "Motor Bomba Principal"
RUTA_ARCHIVO_DATOS = "datos/datos_vibracion_falla_rodamiento_envolvente.csv"
FRECUENCIA_MUESTREO = 8000

GEOMETRIA_SKF_6205 = dict(
    modelo="SKF 6205-2RS",
    ubicacion="Lado acople",
    numero_elementos_rodantes=9,
    diametro_elemento_mm=7.94,
    diametro_paso_mm=39.04,
    angulo_contacto_grados=0.0,
)


def main():
    sesion = SesionLocal()

    try:
        equipo = sesion.query(Equipo).filter(Equipo.nombre == NOMBRE_EQUIPO).first()
        if not equipo:
            print(f"No existe el equipo '{NOMBRE_EQUIPO}'. Nada que hacer.")
            return

        sensor = sesion.query(Sensor).filter(Sensor.equipo_id == equipo.id).first()
        if not sensor:
            print(f"El equipo '{NOMBRE_EQUIPO}' no tiene ningun sensor. Nada que hacer.")
            return

        rodamiento = (
            sesion.query(Rodamiento)
            .filter(Rodamiento.equipo_id == equipo.id, Rodamiento.modelo == GEOMETRIA_SKF_6205["modelo"])
            .first()
        )
        if not rodamiento:
            rodamiento = Rodamiento(
                equipo_id=equipo.id,
                codigo=generar_codigo_rodamiento(sesion, equipo.id),
                **GEOMETRIA_SKF_6205,
            )
            sesion.add(rodamiento)
            sesion.commit()
            sesion.refresh(rodamiento)
            print(f"Rodamiento creado: {rodamiento.codigo} ({rodamiento.modelo}) en equipo id={equipo.id}.")
        else:
            print(f"Rodamiento ya existia: {rodamiento.codigo}.")

        if sensor.rodamiento_id != rodamiento.id:
            sensor.rodamiento_id = rodamiento.id
            sesion.commit()
            print(f"Sensor {sensor.codigo} vinculado a {rodamiento.codigo}.")
        else:
            print(f"Sensor {sensor.codigo} ya estaba vinculado a {rodamiento.codigo}.")

        existente = (
            sesion.query(Medicion)
            .filter(Medicion.sensor_id == sensor.id, Medicion.ruta_archivo_local == RUTA_ARCHIVO_DATOS)
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
        print(f"Medicion de prueba registrada (id={medicion.id}). Es la mas reciente: reemplaza a la anterior como vista por defecto.")

    finally:
        sesion.close()


if __name__ == "__main__":
    main()
