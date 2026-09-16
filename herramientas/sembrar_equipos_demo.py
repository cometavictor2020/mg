"""
Herramienta para (re)cargar los equipos de demostracion de MotorGuardian.

Util para dejar la base de datos con equipos de ejemplo antes de una demo,
por ejemplo despues de haberlos borrado durante pruebas en Configuracion.
Es seguro ejecutarla varias veces: si un equipo ya existe (por nombre), se
deja tal cual - no se sobrescribe (podria tener ediciones manuales).
"""

from pathlib import Path
import sys

RUTA_PROYECTO = Path(__file__).parent.parent
sys.path.append(str(RUTA_PROYECTO))

from basedatos.conexion import SesionLocal
from basedatos.modelos import Equipo, TipoEquipo, Planta
from basedatos.utilidades import obtener_o_crear

EQUIPOS_DEMO = [
    {
        "nombre": "Motor Bomba Principal",
        "tipo": "Motor eléctrico",
        "planta": "Planta principal",
        "estado": "critico",
        "potencia_kw": 75,
    },
    {
        "nombre": "Compresor Aire N°2",
        "tipo": "Compresor",
        "planta": "Sala de compresores",
        "estado": "advertencia",
        "potencia_kw": 55,
    },
    {
        "nombre": "Motor Ventilador Torre",
        "tipo": "Motor eléctrico",
        "planta": "Torre de enfriamiento",
        "estado": "normal",
        "potencia_kw": 30,
    },
    {
        "nombre": "Motor Cinta Transportadora",
        "tipo": "Motor eléctrico",
        "planta": "Línea de transporte",
        "estado": "normal",
        "potencia_kw": 22,
    },
    {
        "nombre": "Bomba Centrífuga N°1",
        "tipo": "Bomba centrífuga",
        "planta": "Sala de bombas",
        "estado": "advertencia",
        "potencia_kw": 45,
    },
    {
        "nombre": "Motor Grúa Puente",
        "tipo": "Motor eléctrico",
        "planta": "Área de carga",
        "estado": "inactivo",
        "potencia_kw": 15,
    },
]


def main():
    sesion = SesionLocal()

    try:
        for datos in EQUIPOS_DEMO:
            existente = (
                sesion.query(Equipo)
                .filter(Equipo.nombre == datos["nombre"])
                .first()
            )

            if existente:
                print(f"Ya existe, se deja tal cual: {datos['nombre']}")
                continue

            tipo_equipo = obtener_o_crear(sesion, TipoEquipo, datos["tipo"])
            planta = obtener_o_crear(sesion, Planta, datos["planta"])

            equipo = Equipo(
                nombre=datos["nombre"],
                tipo_equipo_id=tipo_equipo.id,
                planta_id=planta.id,
                estado=datos["estado"],
                atributos={"potencia_kw": datos["potencia_kw"]},
            )
            sesion.add(equipo)
            print(f"Equipo creado: {datos['nombre']}")

        sesion.commit()

    finally:
        sesion.close()


if __name__ == "__main__":
    main()
