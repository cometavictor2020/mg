"""
Herramienta para migrar el esquema hacia el modelo de rodamientos (D-038):
crea la tabla rodamiento, agrega tipo_sensor.nemonico, y agrega
sensor.codigo / sensor.ubicacion / sensor.rodamiento_id.

Tambien hace el trabajo de backfill que un ALTER TABLE no puede resolver
solo, pero en una segunda pasada (flag --backfill), para no pisar los
nemonicos curados del catalogo:
    - A cualquier tipo_sensor que se quede sin nemonico (tipos creados a
      mano antes de este cambio, que no vienen del catalogo curado) se le
      genera uno de emergencia a partir del nombre, garantizando que sea
      unico. Se recomienda revisarlos despues en Configuracion.
    - A cada sensor existente se le arma un codigo ({nemonico}-{NN}),
      numerado por equipo y tipo de sensor, en el mismo orden en que
      fueron creados (por id).

Orden de uso (una sola vez):
    1. python herramientas\\migrar_esquema_rodamientos.py
       (crea la tabla rodamiento y agrega las columnas nuevas, vacias)
    2. python herramientas\\sembrar_catalogo_sensores.py
       (completa el nemonico curado de conocimiento/catalogo_sensores.csv)
    3. python herramientas\\migrar_esquema_rodamientos.py --backfill
       (nemonico de emergencia para tipos personalizados + codigo de
       cada sensor existente)

No destruye la tabla ni sus filas. Es seguro ejecutarla varias veces:
cada paso revisa si ya se aplico antes de intentarlo.
"""

import re
import sys
from collections import defaultdict
from pathlib import Path

RUTA_PROYECTO = Path(__file__).parent.parent
sys.path.append(str(RUTA_PROYECTO))

from sqlalchemy import inspect, text

from basedatos.conexion import engine, SesionLocal
from basedatos.modelos import Base, Sensor, TipoSensor


def columnas_actuales(tabla):
    inspector = inspect(engine)
    return {columna["name"] for columna in inspector.get_columns(tabla)}


def generar_nemonico_emergencia(nombre, usados):
    base = re.sub(r"[^A-Za-z]", "", nombre).upper()[:8] or "TIPO"

    candidato = base
    sufijo = 1
    while candidato in usados:
        sufijo += 1
        candidato = f"{base}{sufijo}"

    usados.add(candidato)
    return candidato


def backfill_nemonicos():
    sesion = SesionLocal()
    try:
        tipos = sesion.query(TipoSensor).all()
        usados = {t.nemonico for t in tipos if t.nemonico}

        pendientes = [t for t in tipos if not t.nemonico]
        for tipo in pendientes:
            tipo.nemonico = generar_nemonico_emergencia(tipo.nombre, usados)
            print(f"Nemonico de emergencia asignado: {tipo.nombre} -> {tipo.nemonico}")

        if pendientes:
            sesion.commit()
        else:
            print("Todos los tipos de sensor ya tenian nemonico.")
    finally:
        sesion.close()


def backfill_codigos_sensor():
    sesion = SesionLocal()
    try:
        sensores = sesion.query(Sensor).order_by(Sensor.equipo_id, Sensor.id).all()

        contadores = defaultdict(int)
        actualizados = 0

        for sensor in sensores:
            if sensor.codigo:
                continue

            clave = (sensor.equipo_id, sensor.tipo_sensor_id)
            contadores[clave] += 1
            numero = contadores[clave]

            nemonico = sensor.tipo_sensor.nemonico if sensor.tipo_sensor else "SENSOR"
            sensor.codigo = f"{nemonico}-{numero:02d}"
            actualizados += 1

        if actualizados:
            sesion.commit()
            print(f"{actualizados} sensor(es) recibieron codigo retroactivo.")
        else:
            print("Todos los sensores ya tenian codigo.")
    finally:
        sesion.close()


def main():
    # Crea la tabla rodamiento si todavia no existe. No toca las tablas
    # que ya existen (create_all solo crea las que faltan).
    Base.metadata.create_all(engine)
    print("Tabla 'rodamiento' verificada/creada.")

    columnas_tipo_sensor = columnas_actuales("tipo_sensor")
    columnas_sensor = columnas_actuales("sensor")

    with engine.begin() as conexion:
        if "nemonico" not in columnas_tipo_sensor:
            conexion.execute(text("ALTER TABLE tipo_sensor ADD COLUMN nemonico VARCHAR(20)"))
            print("Columna 'tipo_sensor.nemonico' agregada.")
        else:
            print("Columna 'tipo_sensor.nemonico' ya existia.")

        if "codigo" not in columnas_sensor:
            conexion.execute(text("ALTER TABLE sensor ADD COLUMN codigo VARCHAR(30)"))
            print("Columna 'sensor.codigo' agregada.")
        else:
            print("Columna 'sensor.codigo' ya existia.")

        if "ubicacion" not in columnas_sensor:
            conexion.execute(text("ALTER TABLE sensor ADD COLUMN ubicacion VARCHAR(150)"))
            print("Columna 'sensor.ubicacion' agregada.")
        else:
            print("Columna 'sensor.ubicacion' ya existia.")

        if "rodamiento_id" not in columnas_sensor:
            conexion.execute(text("ALTER TABLE sensor ADD COLUMN rodamiento_id INT NULL"))
            conexion.execute(
                text(
                    "ALTER TABLE sensor ADD CONSTRAINT fk_sensor_rodamiento "
                    "FOREIGN KEY (rodamiento_id) REFERENCES rodamiento(id)"
                )
            )
            print("Columna 'sensor.rodamiento_id' agregada (con llave foranea).")
        else:
            print("Columna 'sensor.rodamiento_id' ya existia.")

    if "--backfill" in sys.argv:
        # Se asume que sembrar_catalogo_sensores.py ya corrio antes: los
        # tipos del catalogo curado ya tienen su nemonico real, aqui solo
        # se completan los que quedaron sin uno (tipos personalizados).
        backfill_nemonicos()
        backfill_codigos_sensor()
    else:
        print(
            "Esquema listo. Ahora corre herramientas\\sembrar_catalogo_sensores.py "
            "y despues este mismo script de nuevo con --backfill."
        )

    print("Migracion completada.")


if __name__ == "__main__":
    main()
