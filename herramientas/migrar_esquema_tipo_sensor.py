"""
Herramienta para migrar la tabla tipo_sensor al nuevo esquema de catalogo
de sensores: agrega familia, parametros_fisicos y unidades_disponibles;
retira unidad_medida_default (un solo valor ya no alcanza, un tipo de
sensor puede reportar en varias unidades).

No destruye la tabla ni sus filas. Es seguro ejecutarla varias veces:
cada paso revisa si ya se aplico antes de intentarlo.

Los tipos de sensor que ya existian (creados a mano, antes de este
cambio) quedan en familia "Personalizado", sin parametros_fisicos ni
unidades_disponibles conocidas - hay que completarlos manualmente en
Configuracion si se necesitan.
"""

from pathlib import Path
import sys

RUTA_PROYECTO = Path(__file__).parent.parent
sys.path.append(str(RUTA_PROYECTO))

from sqlalchemy import inspect, text

from basedatos.conexion import engine

FAMILIA_TIPOS_EXISTENTES = "Personalizado"


def columnas_actuales():
    inspector = inspect(engine)
    return {columna["name"] for columna in inspector.get_columns("tipo_sensor")}


def main():
    columnas = columnas_actuales()

    with engine.begin() as conexion:
        if "familia" not in columnas:
            conexion.execute(text("ALTER TABLE tipo_sensor ADD COLUMN familia VARCHAR(60)"))
            print("Columna 'familia' agregada.")
        else:
            print("Columna 'familia' ya existia.")

        if "parametros_fisicos" not in columnas:
            conexion.execute(text("ALTER TABLE tipo_sensor ADD COLUMN parametros_fisicos TEXT"))
            print("Columna 'parametros_fisicos' agregada.")
        else:
            print("Columna 'parametros_fisicos' ya existia.")

        if "unidades_disponibles" not in columnas:
            conexion.execute(text("ALTER TABLE tipo_sensor ADD COLUMN unidades_disponibles JSON"))
            print("Columna 'unidades_disponibles' agregada.")
        else:
            print("Columna 'unidades_disponibles' ya existia.")

        # Los tipos de sensor creados antes de este cambio no vienen del
        # catalogo curado: se marcan como "Personalizado" si aun no tienen
        # familia asignada.
        resultado = conexion.execute(
            text(
                "UPDATE tipo_sensor SET familia = :familia "
                "WHERE familia IS NULL"
            ),
            {"familia": FAMILIA_TIPOS_EXISTENTES},
        )
        if resultado.rowcount:
            print(f"{resultado.rowcount} tipo(s) de sensor existente(s) marcado(s) como '{FAMILIA_TIPOS_EXISTENTES}'.")

        if "unidad_medida_default" in columnas:
            conexion.execute(text("ALTER TABLE tipo_sensor DROP COLUMN unidad_medida_default"))
            print("Columna 'unidad_medida_default' eliminada (reemplazada por 'unidades_disponibles').")
        else:
            print("Columna 'unidad_medida_default' ya no existia.")

    print("Migracion completada.")


if __name__ == "__main__":
    main()
