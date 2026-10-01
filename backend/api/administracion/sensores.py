"""
Endpoints de administracion de sensores.

Responsabilidad:
    CRUD de la tabla sensor. El tipo de sensor se elige de un catalogo
    (ver tipos_sensor.py) en vez de escribirse libremente; las unidades
    que efectivamente usa cada sensor, y los ejes que le corresponden
    segun su tipo, se guardan en Sensor.configuracion (JSON).
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from basedatos.conexion import SesionLocal
from basedatos.modelos import Sensor, TipoSensor, Equipo, Rodamiento
from seguridad.auth import obtener_usuario_actual

router = APIRouter(
    prefix="/api/sensores",
    tags=["sensores"],
    dependencies=[Depends(obtener_usuario_actual)],
)


VALORES_ORIENTACION_VALIDOS = {"radial_horizontal", "radial_vertical", "axial"}


class SensorEntrada(BaseModel):
    equipo_id: int
    tipo_sensor_id: int
    unidades_seleccionadas: list[str] = []
    estado: str = "activo"
    ubicacion: Optional[str] = None
    rodamiento_id: Optional[int] = None
    # {"x": "radial_horizontal", "y": "radial_vertical", "z": "axial"} -
    # opcional, una entrada por cada eje que el sensor realmente tenga
    # (ver derivar_ejes). Sin ella, el motor de diagnostico sigue
    # funcionando igual que hoy (D-051, ver PROYECTO.md).
    orientacion_ejes: Optional[dict[str, str]] = None


def derivar_ejes(parametros_fisicos):
    """
    Un sensor es triaxial si sus parametros fisicos describen los 3 ejes
    por separado (ej. "Aceleracion en eje X, aceleracion en eje Y,
    aceleracion en eje Z"); en cualquier otro caso es uniaxial.
    """
    texto = (parametros_fisicos or "").lower()

    if "eje x" in texto and "eje y" in texto and "eje z" in texto:
        return ["X", "Y", "Z"]

    return ["X"]


def serializar(sensor):
    configuracion = sensor.configuracion or {}

    return {
        "id": sensor.id,
        "codigo": sensor.codigo,
        "equipo_id": sensor.equipo_id,
        "equipo_nombre": sensor.equipo.nombre if sensor.equipo else None,
        "tipo_sensor_id": sensor.tipo_sensor_id,
        "tipo": sensor.tipo_sensor.nombre if sensor.tipo_sensor else None,
        "familia": sensor.tipo_sensor.familia if sensor.tipo_sensor else None,
        "unidades": configuracion.get("unidades", []),
        "ejes": configuracion.get("ejes", []),
        "orientacion_ejes": configuracion.get("orientacion_ejes"),
        "ubicacion": sensor.ubicacion,
        "rodamiento_id": sensor.rodamiento_id,
        "rodamiento_codigo": sensor.rodamiento.codigo if sensor.rodamiento else None,
        "estado": sensor.estado,
        "fecha_instalacion": sensor.fecha_instalacion,
    }


def generar_codigo(sesion, equipo_id, tipo_sensor, excluir_sensor_id=None):
    """Siguiente {nemonico}-{NN} disponible para este equipo y tipo de sensor."""
    consulta = sesion.query(Sensor).filter(
        Sensor.equipo_id == equipo_id,
        Sensor.tipo_sensor_id == tipo_sensor.id,
    )
    if excluir_sensor_id:
        consulta = consulta.filter(Sensor.id != excluir_sensor_id)

    prefijo = f"{tipo_sensor.nemonico}-"
    numero_maximo = 0
    for sensor in consulta.all():
        if sensor.codigo and sensor.codigo.startswith(prefijo):
            sufijo = sensor.codigo[len(prefijo):]
            if sufijo.isdigit():
                numero_maximo = max(numero_maximo, int(sufijo))

    return f"{prefijo}{numero_maximo + 1:02d}"


def validar_rodamiento(sesion, equipo_id, rodamiento_id):
    if rodamiento_id is None:
        return None

    rodamiento = sesion.query(Rodamiento).filter(Rodamiento.id == rodamiento_id).first()
    if not rodamiento:
        raise HTTPException(status_code=404, detail="Rodamiento no encontrado")
    if rodamiento.equipo_id != equipo_id:
        raise HTTPException(
            status_code=422, detail="El rodamiento seleccionado pertenece a otro equipo"
        )
    return rodamiento


def validar_orientacion_ejes(orientacion_ejes, ejes_del_sensor):
    """
    orientacion_ejes: {"x": "radial_horizontal", ...} o None (no
    declarada - el sistema sigue funcionando igual que hoy, D-051).
    Cada clave debe ser uno de los ejes reales del sensor (en
    minuscula, para calzar con backend/procesamiento/diagnostico.py::
    EJES) y cada valor uno de VALORES_ORIENTACION_VALIDOS.
    """
    if not orientacion_ejes:
        return None

    ejes_validos = {eje.lower() for eje in ejes_del_sensor}
    for eje, orientacion in orientacion_ejes.items():
        if eje.lower() not in ejes_validos:
            raise HTTPException(
                status_code=422,
                detail=f"El eje '{eje}' no corresponde a este sensor (ejes válidos: {', '.join(ejes_del_sensor)})",
            )
        if orientacion not in VALORES_ORIENTACION_VALIDOS:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Orientación no válida para el eje '{eje}': '{orientacion}' — valores "
                    f"aceptados: {', '.join(sorted(VALORES_ORIENTACION_VALIDOS))}."
                ),
            )

    return {eje.lower(): orientacion for eje, orientacion in orientacion_ejes.items()}


def construir_configuracion(sesion, datos):
    tipo_sensor = (
        sesion.query(TipoSensor)
        .filter(TipoSensor.id == datos.tipo_sensor_id)
        .first()
    )
    if not tipo_sensor:
        raise HTTPException(status_code=404, detail="Tipo de sensor no encontrado")

    disponibles = tipo_sensor.unidades_disponibles or []
    invalidas = [u for u in datos.unidades_seleccionadas if u not in disponibles]
    if invalidas:
        raise HTTPException(
            status_code=422,
            detail=f"Unidad(es) no disponible(s) para este tipo de sensor: {', '.join(invalidas)}",
        )

    ejes = derivar_ejes(tipo_sensor.parametros_fisicos)
    orientacion_ejes = validar_orientacion_ejes(datos.orientacion_ejes, ejes)

    configuracion = {
        "unidades": datos.unidades_seleccionadas,
        "ejes": ejes,
    }
    if orientacion_ejes:
        configuracion["orientacion_ejes"] = orientacion_ejes
    return tipo_sensor, configuracion


@router.get("")
def listar_sensores():
    sesion = SesionLocal()
    try:
        sensores = sesion.query(Sensor).order_by(Sensor.id).all()
        return [serializar(s) for s in sensores]
    finally:
        sesion.close()


@router.post("")
def crear_sensor(datos: SensorEntrada):
    sesion = SesionLocal()
    try:
        equipo = sesion.query(Equipo).filter(Equipo.id == datos.equipo_id).first()
        if not equipo:
            raise HTTPException(status_code=404, detail="Equipo no encontrado")

        tipo_sensor, configuracion = construir_configuracion(sesion, datos)
        validar_rodamiento(sesion, datos.equipo_id, datos.rodamiento_id)

        sensor = Sensor(
            equipo_id=datos.equipo_id,
            tipo_sensor_id=tipo_sensor.id,
            codigo=generar_codigo(sesion, datos.equipo_id, tipo_sensor),
            ubicacion=datos.ubicacion,
            rodamiento_id=datos.rodamiento_id,
            estado=datos.estado,
            configuracion=configuracion,
        )
        sesion.add(sensor)
        sesion.commit()
        sesion.refresh(sensor)
        return serializar(sensor)
    finally:
        sesion.close()


@router.put("/{sensor_id}")
def actualizar_sensor(sensor_id: int, datos: SensorEntrada):
    sesion = SesionLocal()
    try:
        sensor = sesion.query(Sensor).filter(Sensor.id == sensor_id).first()
        if not sensor:
            raise HTTPException(status_code=404, detail="Sensor no encontrado")

        equipo = sesion.query(Equipo).filter(Equipo.id == datos.equipo_id).first()
        if not equipo:
            raise HTTPException(status_code=404, detail="Equipo no encontrado")

        tipo_sensor, configuracion = construir_configuracion(sesion, datos)
        validar_rodamiento(sesion, datos.equipo_id, datos.rodamiento_id)

        cambia_ubicacion = (
            sensor.equipo_id != datos.equipo_id or sensor.tipo_sensor_id != tipo_sensor.id
        )

        sensor.equipo_id = datos.equipo_id
        sensor.tipo_sensor_id = tipo_sensor.id
        if cambia_ubicacion:
            sensor.codigo = generar_codigo(
                sesion, datos.equipo_id, tipo_sensor, excluir_sensor_id=sensor.id
            )
        sensor.ubicacion = datos.ubicacion
        sensor.rodamiento_id = datos.rodamiento_id
        sensor.estado = datos.estado
        sensor.configuracion = configuracion

        sesion.commit()
        sesion.refresh(sensor)
        return serializar(sensor)
    finally:
        sesion.close()


@router.delete("/{sensor_id}")
def eliminar_sensor(sensor_id: int):
    sesion = SesionLocal()
    try:
        sensor = sesion.query(Sensor).filter(Sensor.id == sensor_id).first()
        if not sensor:
            raise HTTPException(status_code=404, detail="Sensor no encontrado")

        sesion.delete(sensor)
        sesion.commit()
        return {"mensaje": "Sensor eliminado"}
    finally:
        sesion.close()
