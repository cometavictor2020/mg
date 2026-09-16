"""
Endpoints de administracion de usuarios.

Responsabilidad:
    CRUD de la tabla usuario. Nunca expone password_hash en las respuestas.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from basedatos.conexion import SesionLocal
from basedatos.modelos import Usuario
from seguridad.auth import crear_hash_password, obtener_usuario_actual

router = APIRouter(
    prefix="/api/usuarios",
    tags=["usuarios"],
    dependencies=[Depends(obtener_usuario_actual)],
)


class UsuarioEntrada(BaseModel):
    nombre: str
    email: str
    password: str
    rol: str = "visualizador"


class UsuarioActualizacion(BaseModel):
    nombre: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None
    rol: Optional[str] = None


def serializar(usuario):
    return {
        "id": usuario.id,
        "nombre": usuario.nombre,
        "email": usuario.email,
        "rol": usuario.rol,
        "fecha_creacion": usuario.fecha_creacion,
    }


@router.get("")
def listar_usuarios():
    sesion = SesionLocal()
    try:
        usuarios = sesion.query(Usuario).order_by(Usuario.id).all()
        return [serializar(u) for u in usuarios]
    finally:
        sesion.close()


@router.post("")
def crear_usuario(datos: UsuarioEntrada):
    sesion = SesionLocal()
    try:
        existente = (
            sesion.query(Usuario).filter(Usuario.email == datos.email).first()
        )
        if existente:
            raise HTTPException(
                status_code=409, detail="Ya existe un usuario con ese correo"
            )

        usuario = Usuario(
            nombre=datos.nombre,
            email=datos.email,
            password_hash=crear_hash_password(datos.password),
            rol=datos.rol,
        )
        sesion.add(usuario)
        sesion.commit()
        sesion.refresh(usuario)
        return serializar(usuario)
    finally:
        sesion.close()


@router.put("/{usuario_id}")
def actualizar_usuario(usuario_id: int, datos: UsuarioActualizacion):
    sesion = SesionLocal()
    try:
        usuario = sesion.query(Usuario).filter(Usuario.id == usuario_id).first()
        if not usuario:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")

        if datos.nombre is not None:
            usuario.nombre = datos.nombre
        if datos.email is not None:
            usuario.email = datos.email
        if datos.rol is not None:
            usuario.rol = datos.rol
        if datos.password:
            usuario.password_hash = crear_hash_password(datos.password)

        sesion.commit()
        sesion.refresh(usuario)
        return serializar(usuario)
    finally:
        sesion.close()


@router.delete("/{usuario_id}")
def eliminar_usuario(usuario_id: int):
    sesion = SesionLocal()
    try:
        usuario = sesion.query(Usuario).filter(Usuario.id == usuario_id).first()
        if not usuario:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")

        sesion.delete(usuario)
        sesion.commit()
        return {"mensaje": "Usuario eliminado"}
    finally:
        sesion.close()
