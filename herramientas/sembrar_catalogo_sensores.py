"""
Herramienta para sembrar el catalogo de tipos de sensor desde
conocimiento/catalogo_sensores.csv (familia, sensor, nemonico, parametros
fisicos, unidades tipicas separadas por coma).

Es seguro ejecutarla varias veces: si un tipo de sensor ya existe (mismo
nombre), no se sobrescriben sus datos - salvo el nemonico, que solo se
completa si todavia esta vacio (fue agregado despues, en D-038, y los
tipos ya sembrados no lo tenian).
"""

import csv
from pathlib import Path
import sys

RUTA_PROYECTO = Path(__file__).parent.parent
sys.path.append(str(RUTA_PROYECTO))

from basedatos.conexion import SesionLocal
from basedatos.modelos import TipoSensor

RUTA_CATALOGO = RUTA_PROYECTO / "conocimiento" / "catalogo_sensores.csv"


def main():
    sesion = SesionLocal()

    try:
        with open(RUTA_CATALOGO, encoding="utf-8") as archivo:
            filas = csv.DictReader(archivo, delimiter=";")

            for fila in filas:
                nombre = fila["Sensor"].strip()
                nemonico = fila["Nemonico"].strip()

                existente = (
                    sesion.query(TipoSensor)
                    .filter(TipoSensor.nombre == nombre)
                    .first()
                )
                if existente:
                    if not existente.nemonico and nemonico:
                        existente.nemonico = nemonico
                        print(f"Nemonico completado para tipo existente: {nombre} -> {nemonico}")
                    else:
                        print(f"Ya existe, se deja tal cual: {nombre}")
                    continue

                unidades = [
                    unidad.strip()
                    for unidad in fila["Unidad tipica"].split(",")
                    if unidad.strip()
                ]

                tipo_sensor = TipoSensor(
                    nombre=nombre,
                    nemonico=nemonico,
                    familia=fila["Familia"].strip(),
                    parametros_fisicos=fila["Parametros fisicos"].strip(),
                    unidades_disponibles=unidades,
                )
                sesion.add(tipo_sensor)
                print(f"Tipo de sensor creado: {nombre} ({nemonico})")

        sesion.commit()

    finally:
        sesion.close()


if __name__ == "__main__":
    main()
