"""
Endpoints de administracion de sensores.

Responsabilidad:
    CRUD de la tabla sensor. El tipo de sensor se registra automaticamente
    si no existe (catalogo abierto, D-021).
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from basedatos.conexion import SesionLocal
from basedatos.modelos import Sensor, TipoSensor, Equipo
from basedatos.utilidades import obtener_o_crear
from seguridad.auth import obtener_usuario_actual

router = APIRouter(
    prefix="/api/sensores",
    tags=["sensores"],
    dependencies=[Depends(obtener_usuario_actual)],
)


class SensorEntrada(BaseModel):
    equipo_id: int
    tipo: str
    estado: str = "activo"


def serializar(sensor):
    return {
        "id": sensor.id,
        "equipo_id": sensor.equipo_id,
        "equipo_nombre": sensor.equipo.nombre if sensor.equipo else None,
        "tipo": sensor.tipo_sensor.nombre if sensor.tipo_sensor else None,
        "estado": sensor.estado,
        "fecha_instalacion": sensor.fecha_instalacion,
    }


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

        tipo_sensor = obtener_o_crear(sesion, TipoSensor, datos.tipo)

        sensor = Sensor(
            equipo_id=datos.equipo_id,
            tipo_sensor_id=tipo_sensor.id,
            estado=datos.estado,
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

        tipo_sensor = obtener_o_crear(sesion, TipoSensor, datos.tipo)

        sensor.equipo_id = datos.equipo_id
        sensor.tipo_sensor_id = tipo_sensor.id
        sensor.estado = datos.estado

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
