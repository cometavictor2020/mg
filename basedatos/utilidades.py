"""
Utilidades compartidas para trabajar con la base de datos.

Responsabilidad:
    Funciones auxiliares reutilizadas por los endpoints de administracion.
"""


def obtener_o_crear(sesion, clase_modelo, nombre):
    """
    Busca una fila por nombre; si no existe, la crea.

    Se usa para los catalogos abiertos (tipo_equipo, tipo_sensor, planta):
    un tipo nuevo se registra automaticamente la primera vez que se usa,
    sin necesidad de una pantalla de administracion separada (D-021).
    """

    nombre = nombre.strip()

    instancia = (
        sesion.query(clase_modelo)
        .filter(clase_modelo.nombre == nombre)
        .first()
    )

    if instancia:
        return instancia

    instancia = clase_modelo(nombre=nombre)
    sesion.add(instancia)
    sesion.flush()

    return instancia
