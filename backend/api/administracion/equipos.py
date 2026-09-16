"""
Endpoints de administracion de equipos.

Responsabilidad:
    CRUD de la tabla equipo. El tipo de equipo y la planta se registran
    automaticamente si no existen (catalogos abiertos, D-021).
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from basedatos.conexion import SesionLocal
from basedatos.modelos import Equipo, TipoEquipo, Planta
from basedatos.utilidades import obtener_o_crear
from seguridad.auth import obtener_usuario_actual

router = APIRouter(
    prefix="/api/equipos",
    tags=["equipos"],
    dependencies=[Depends(obtener_usuario_actual)],
)


class EquipoEntrada(BaseModel):
    nombre: str
    tipo: str
    planta: Optional[str] = None
    estado: str = "normal"
    potencia_kw: Optional[float] = None


def serializar(equipo):
    return {
        "id": equipo.id,
        "nombre": equipo.nombre,
        "tipo": equipo.tipo_equipo.nombre if equipo.tipo_equipo else None,
        "planta": equipo.planta.nombre if equipo.planta else None,
        "estado": equipo.estado,
        "potencia_kw": (equipo.atributos or {}).get("potencia_kw"),
        "fecha_creacion": equipo.fecha_creacion,
    }


@router.get("")
def listar_equipos():
    sesion = SesionLocal()
    try:
        equipos = sesion.query(Equipo).order_by(Equipo.id).all()
        return [serializar(e) for e in equipos]
    finally:
        sesion.close()


@router.post("")
def crear_equipo(datos: EquipoEntrada):
    sesion = SesionLocal()
    try:
        tipo_equipo = obtener_o_crear(sesion, TipoEquipo, datos.tipo)
        planta = (
            obtener_o_crear(sesion, Planta, datos.planta) if datos.planta else None
        )

        equipo = Equipo(
            nombre=datos.nombre,
            tipo_equipo_id=tipo_equipo.id,
            planta_id=planta.id if planta else None,
            estado=datos.estado,
            atributos=(
                {"potencia_kw": datos.potencia_kw}
                if datos.potencia_kw is not None
                else None
            ),
        )
        sesion.add(equipo)
        sesion.commit()
        sesion.refresh(equipo)
        return serializar(equipo)
    finally:
        sesion.close()


@router.put("/{equipo_id}")
def actualizar_equipo(equipo_id: int, datos: EquipoEntrada):
    sesion = SesionLocal()
    try:
        equipo = sesion.query(Equipo).filter(Equipo.id == equipo_id).first()
        if not equipo:
            raise HTTPException(status_code=404, detail="Equipo no encontrado")

        tipo_equipo = obtener_o_crear(sesion, TipoEquipo, datos.tipo)
        planta = (
            obtener_o_crear(sesion, Planta, datos.planta) if datos.planta else None
        )

        equipo.nombre = datos.nombre
        equipo.tipo_equipo_id = tipo_equipo.id
        equipo.planta_id = planta.id if planta else None
        equipo.estado = datos.estado
        equipo.atributos = (
            {"potencia_kw": datos.potencia_kw}
            if datos.potencia_kw is not None
            else None
        )

        sesion.commit()
        sesion.refresh(equipo)
        return serializar(equipo)
    finally:
        sesion.close()


@router.delete("/{equipo_id}")
def eliminar_equipo(equipo_id: int):
    sesion = SesionLocal()
    try:
        equipo = sesion.query(Equipo).filter(Equipo.id == equipo_id).first()
        if not equipo:
            raise HTTPException(status_code=404, detail="Equipo no encontrado")

        sesion.delete(equipo)
        sesion.commit()
        return {"mensaje": "Equipo eliminado"}
    finally:
        sesion.close()
