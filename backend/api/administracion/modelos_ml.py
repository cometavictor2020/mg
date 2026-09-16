"""
Endpoints de administracion de modelos de aprendizaje.

Responsabilidad:
    CRUD de la tabla modelo. Es solo un registro/catalogo (metadata):
    no entrena ni ejecuta inferencia todavia (ver docstring de Modelo
    en basedatos/modelos.py y D-019 en PROYECTO.md).
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from basedatos.conexion import SesionLocal
from basedatos.modelos import Modelo
from seguridad.auth import obtener_usuario_actual

router = APIRouter(
    prefix="/api/modelos-ml",
    tags=["modelos_ml"],
    dependencies=[Depends(obtener_usuario_actual)],
)


class ModeloEntrada(BaseModel):
    nombre: str
    tipo: str
    version: str = "0.1"
    estado: str = "planificado"
    descripcion: str = ""


def serializar(modelo):
    return {
        "id": modelo.id,
        "nombre": modelo.nombre,
        "tipo": modelo.tipo,
        "version": modelo.version,
        "estado": modelo.estado,
        "descripcion": modelo.descripcion,
        "fecha_creacion": modelo.fecha_creacion,
    }


@router.get("")
def listar_modelos():
    sesion = SesionLocal()
    try:
        modelos = sesion.query(Modelo).order_by(Modelo.id).all()
        return [serializar(m) for m in modelos]
    finally:
        sesion.close()


@router.post("")
def crear_modelo(datos: ModeloEntrada):
    sesion = SesionLocal()
    try:
        modelo = Modelo(**datos.model_dump())
        sesion.add(modelo)
        sesion.commit()
        sesion.refresh(modelo)
        return serializar(modelo)
    finally:
        sesion.close()


@router.put("/{modelo_id}")
def actualizar_modelo(modelo_id: int, datos: ModeloEntrada):
    sesion = SesionLocal()
    try:
        modelo = sesion.query(Modelo).filter(Modelo.id == modelo_id).first()
        if not modelo:
            raise HTTPException(status_code=404, detail="Modelo no encontrado")

        for campo, valor in datos.model_dump().items():
            setattr(modelo, campo, valor)

        sesion.commit()
        sesion.refresh(modelo)
        return serializar(modelo)
    finally:
        sesion.close()


@router.delete("/{modelo_id}")
def eliminar_modelo(modelo_id: int):
    sesion = SesionLocal()
    try:
        modelo = sesion.query(Modelo).filter(Modelo.id == modelo_id).first()
        if not modelo:
            raise HTTPException(status_code=404, detail="Modelo no encontrado")

        sesion.delete(modelo)
        sesion.commit()
        return {"mensaje": "Modelo eliminado"}
    finally:
        sesion.close()
