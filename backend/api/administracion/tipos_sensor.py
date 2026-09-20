"""
Endpoints de administracion del catalogo de tipos de sensor.

Responsabilidad:
    Listar/buscar el catalogo (sembrado desde conocimiento/
    catalogo_sensores.csv), crear tipos nuevos (quedan en familia
    "Personalizado") y agregar unidades a un tipo existente. El CRUD de
    sensores concretos (instancias en un equipo) vive en sensores.py;
    este modulo administra el catalogo del que eligen.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from basedatos.conexion import SesionLocal
from basedatos.modelos import TipoSensor
from seguridad.auth import obtener_usuario_actual

router = APIRouter(
    prefix="/api/tipos-sensor",
    tags=["tipos_sensor"],
    dependencies=[Depends(obtener_usuario_actual)],
)

FAMILIA_PERSONALIZADO = "Personalizado"


class TipoSensorEntrada(BaseModel):
    nombre: str
    nemonico: str
    parametros_fisicos: Optional[str] = None
    unidad_inicial: str


class UnidadEntrada(BaseModel):
    unidad: str


def serializar(tipo_sensor):
    return {
        "id": tipo_sensor.id,
        "nombre": tipo_sensor.nombre,
        "nemonico": tipo_sensor.nemonico,
        "familia": tipo_sensor.familia,
        "parametros_fisicos": tipo_sensor.parametros_fisicos,
        "unidades_disponibles": tipo_sensor.unidades_disponibles or [],
    }


@router.get("")
def listar_tipos_sensor(buscar: Optional[str] = None, familia: Optional[str] = None):
    sesion = SesionLocal()
    try:
        consulta = sesion.query(TipoSensor)

        if familia:
            consulta = consulta.filter(TipoSensor.familia == familia)

        if buscar:
            patron = f"%{buscar}%"
            consulta = consulta.filter(
                (TipoSensor.nombre.ilike(patron)) | (TipoSensor.familia.ilike(patron))
            )

        tipos = consulta.order_by(TipoSensor.familia, TipoSensor.nombre).all()
        return [serializar(t) for t in tipos]
    finally:
        sesion.close()


@router.post("")
def crear_tipo_sensor(datos: TipoSensorEntrada):
    sesion = SesionLocal()
    try:
        existente = (
            sesion.query(TipoSensor)
            .filter(TipoSensor.nombre == datos.nombre)
            .first()
        )
        if existente:
            raise HTTPException(
                status_code=409, detail="Ya existe un tipo de sensor con ese nombre"
            )

        nemonico = datos.nemonico.strip().upper()
        if not nemonico:
            raise HTTPException(status_code=422, detail="El nemónico no puede estar vacío")

        nemonico_existente = (
            sesion.query(TipoSensor)
            .filter(TipoSensor.nemonico == nemonico)
            .first()
        )
        if nemonico_existente:
            raise HTTPException(
                status_code=409, detail=f"Ya existe un tipo de sensor con el nemónico '{nemonico}'"
            )

        tipo_sensor = TipoSensor(
            nombre=datos.nombre,
            nemonico=nemonico,
            familia=FAMILIA_PERSONALIZADO,
            parametros_fisicos=datos.parametros_fisicos,
            unidades_disponibles=[datos.unidad_inicial],
        )
        sesion.add(tipo_sensor)
        sesion.commit()
        sesion.refresh(tipo_sensor)
        return serializar(tipo_sensor)
    finally:
        sesion.close()


@router.post("/{tipo_sensor_id}/unidades")
def agregar_unidad(tipo_sensor_id: int, datos: UnidadEntrada):
    sesion = SesionLocal()
    try:
        tipo_sensor = (
            sesion.query(TipoSensor)
            .filter(TipoSensor.id == tipo_sensor_id)
            .first()
        )
        if not tipo_sensor:
            raise HTTPException(status_code=404, detail="Tipo de sensor no encontrado")

        unidades = list(tipo_sensor.unidades_disponibles or [])
        unidad_nueva = datos.unidad.strip()

        if unidad_nueva and unidad_nueva not in unidades:
            unidades.append(unidad_nueva)
            tipo_sensor.unidades_disponibles = unidades
            sesion.commit()
            sesion.refresh(tipo_sensor)

        return serializar(tipo_sensor)
    finally:
        sesion.close()
