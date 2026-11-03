"""
Utilidades compartidas para trabajar con la base de datos.

Responsabilidad:
    Funciones auxiliares reutilizadas por los endpoints de administracion.
"""


def obtener_linea_base_activa(sesion, sensor_id):
    """
    La linea base activa de un sensor (D-056), en el formato que espera
    diagnosticar_sensor(): {"valores": {...}, "fecha": "dd/mm/aaaa"}, o None
    si el sensor no tiene ninguna. Un sensor tiene a lo mas una activa.
    """
    from basedatos.modelos import LineaBase

    fila = (
        sesion.query(LineaBase)
        .filter(LineaBase.sensor_id == sensor_id, LineaBase.activa.is_(True))
        .order_by(LineaBase.fecha_creacion.desc())
        .first()
    )
    if not fila:
        return None

    return {"valores": fila.valores, "fecha": fila.fecha_creacion.strftime("%d/%m/%Y")}


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
