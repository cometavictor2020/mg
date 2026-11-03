"""
Endpoints de notificaciones (D-054/D-055, ver PROYECTO.md).

Responsabilidad:
    - Administrar a quien se le envian las alertas (tabla
      destinatario_notificacion): listar, agregar, editar/activar-desactivar,
      eliminar y enviar un mensaje de prueba a uno.
    - Estado de los canales (si .env tiene las credenciales) y deteccion de
      chats de Telegram (quien le escribio al bot), para agregar a alguien
      nuevo sin buscar su chat id a mano.
    - Interruptor general: activar o desactivar todas las notificaciones de
      una vez (servicio.py::fijar_habilitado).
    - Mensaje de prueba a todos los activos e historial de avisos.

Las credenciales (servidor SMTP, token del bot) NUNCA se reciben ni se
devuelven por aqui: viven solo en .env.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError

from backend.notificaciones import canales
from backend.notificaciones.servicio import cargar_configuracion, enviar_prueba, estado_global, fijar_habilitado
from basedatos.conexion import SesionLocal
from basedatos.modelos import DestinatarioNotificacion, Notificacion
from seguridad.auth import obtener_usuario_actual

router = APIRouter(
    prefix="/api/notificaciones",
    tags=["notificaciones"],
    dependencies=[Depends(obtener_usuario_actual)],
)


class DestinatarioEntrada(BaseModel):
    nombre: str
    canal: str
    direccion: str
    activo: bool = True


class DestinatarioEdicion(BaseModel):
    nombre: str
    direccion: str
    activo: bool


class InterruptorEntrada(BaseModel):
    habilitado: bool


def serializar_destinatario(fila):
    return {
        "id": fila.id,
        "nombre": fila.nombre,
        "canal": fila.canal,
        "direccion": fila.direccion,
        "activo": fila.activo,
        "origen": "aplicacion",
        "fecha_creacion": fila.fecha_creacion,
    }


def serializar_aviso(notificacion):
    return {
        "id": notificacion.id,
        "equipo_id": notificacion.equipo_id,
        "equipo_nombre": notificacion.equipo.nombre if notificacion.equipo else None,
        "medicion_id": notificacion.medicion_id,
        "clave": notificacion.clave,
        "nivel": notificacion.nivel,
        "canal": notificacion.canal,
        "destinatario": notificacion.destinatario,
        "estado": notificacion.estado,
        "detalle": notificacion.detalle,
        "fecha_envio": notificacion.fecha_envio,
    }


def _limpiar_entrada(nombre, direccion, canal):
    nombre = (nombre or "").strip()
    direccion = (direccion or "").strip()
    if not nombre or len(nombre) > 150:
        raise HTTPException(status_code=422, detail="El nombre es obligatorio (máximo 150 caracteres).")
    error = canales.validar_direccion(canal, direccion)
    if error:
        raise HTTPException(status_code=422, detail=error)
    return nombre, direccion


# ----------------------------------------------------------- destinatarios
@router.get("/destinatarios")
def listar_destinatarios():
    """Los de la base de datos mas los "base" definidos en .env (solo lectura)."""
    sesion = SesionLocal()
    try:
        filas = sesion.query(DestinatarioNotificacion).order_by(DestinatarioNotificacion.id).all()
        resultado = [serializar_destinatario(f) for f in filas]
        en_tabla = {(f.canal, f.direccion) for f in filas}

        base = [("correo", d) for d in canales.destinatarios_correo_base()]
        if canales.chat_id_base():
            base.append(("telegram", canales.chat_id_base()))
        for canal, direccion in base:
            if (canal, direccion) not in en_tabla:
                resultado.append(
                    {
                        "id": None,
                        "nombre": "(definido en .env)",
                        "canal": canal,
                        "direccion": direccion,
                        "activo": True,
                        "origen": "env",
                        "fecha_creacion": None,
                    }
                )
        return resultado
    finally:
        sesion.close()


@router.post("/destinatarios")
def agregar_destinatario(entrada: DestinatarioEntrada):
    nombre, direccion = _limpiar_entrada(entrada.nombre, entrada.direccion, entrada.canal)
    sesion = SesionLocal()
    try:
        fila = DestinatarioNotificacion(nombre=nombre, canal=entrada.canal, direccion=direccion, activo=entrada.activo)
        sesion.add(fila)
        try:
            sesion.commit()
        except IntegrityError:
            sesion.rollback()
            raise HTTPException(status_code=409, detail="Ese destinatario ya está registrado para ese canal.")
        sesion.refresh(fila)
        return serializar_destinatario(fila)
    finally:
        sesion.close()


@router.put("/destinatarios/{destinatario_id}")
def editar_destinatario(destinatario_id: int, entrada: DestinatarioEdicion):
    sesion = SesionLocal()
    try:
        fila = sesion.query(DestinatarioNotificacion).filter(DestinatarioNotificacion.id == destinatario_id).first()
        if not fila:
            raise HTTPException(status_code=404, detail="Destinatario no encontrado")
        nombre, direccion = _limpiar_entrada(entrada.nombre, entrada.direccion, fila.canal)
        fila.nombre = nombre
        fila.direccion = direccion
        fila.activo = entrada.activo
        try:
            sesion.commit()
        except IntegrityError:
            sesion.rollback()
            raise HTTPException(status_code=409, detail="Ese destinatario ya está registrado para ese canal.")
        sesion.refresh(fila)
        return serializar_destinatario(fila)
    finally:
        sesion.close()


@router.delete("/destinatarios/{destinatario_id}")
def eliminar_destinatario(destinatario_id: int):
    sesion = SesionLocal()
    try:
        fila = sesion.query(DestinatarioNotificacion).filter(DestinatarioNotificacion.id == destinatario_id).first()
        if not fila:
            raise HTTPException(status_code=404, detail="Destinatario no encontrado")
        sesion.delete(fila)
        sesion.commit()
        return {"eliminado": destinatario_id}
    finally:
        sesion.close()


@router.post("/destinatarios/{destinatario_id}/prueba")
def probar_destinatario(destinatario_id: int):
    sesion = SesionLocal()
    try:
        existe = sesion.query(DestinatarioNotificacion).filter(DestinatarioNotificacion.id == destinatario_id).first()
        if not existe:
            raise HTTPException(status_code=404, detail="Destinatario no encontrado")
    finally:
        sesion.close()
    return enviar_prueba(destinatario_id)


# ------------------------------------------------- interruptor general
@router.put("/interruptor")
def fijar_interruptor(entrada: InterruptorEntrada, usuario=Depends(obtener_usuario_actual)):
    """Activa o desactiva TODAS las notificaciones (correo y Telegram, avisos y mensajes de prueba)."""
    return fijar_habilitado(entrada.habilitado, usuario.get("email"))


# -------------------------------------------------------- canales y Telegram
@router.get("/estado")
def estado_canales():
    config = cargar_configuracion()
    resultado = estado_global(config)
    for canal in ("correo", "telegram"):
        faltantes = canales.variables_faltantes(canal)
        resultado[canal] = {
            "habilitado": bool(config.get("canales", {}).get(canal, {}).get("habilitado", False)),
            "configurado": not faltantes,
            "variables_faltantes": faltantes,
        }
    if resultado["telegram"]["configurado"]:
        usuario, error = canales.informacion_bot_telegram()
        resultado["telegram"]["bot_usuario"] = f"@{usuario}" if usuario else None
        resultado["telegram"]["bot_error"] = error
    return resultado


@router.get("/telegram/chats")
def chats_de_telegram():
    """
    Personas o grupos que le escribieron al bot en las ultimas ~24 h. Para
    agregar a alguien: que le escriba /start al bot y aparecera aqui.
    """
    if not canales.telegram_configurado():
        raise HTTPException(
            status_code=409,
            detail="Falta TELEGRAM_BOT_TOKEN en .env: crea el bot con @BotFather y configúralo primero.",
        )
    chats, error = canales.detectar_chats_telegram()
    if error:
        raise HTTPException(status_code=502, detail=f"No se pudo consultar Telegram: {error}")

    sesion = SesionLocal()
    try:
        ya = {f.direccion for f in sesion.query(DestinatarioNotificacion).filter(DestinatarioNotificacion.canal == "telegram").all()}
    finally:
        sesion.close()
    if canales.chat_id_base():
        ya.add(canales.chat_id_base())
    return [{**chat, "ya_agregado": chat["chat_id"] in ya} for chat in chats]


# ------------------------------------------------------------ prueba e historial
@router.post("/prueba")
def probar_canales():
    return enviar_prueba()


@router.get("")
def listar_notificaciones(limite: int = 50):
    sesion = SesionLocal()
    try:
        filas = (
            sesion.query(Notificacion)
            .order_by(Notificacion.fecha_envio.desc())
            .limit(max(1, min(limite, 500)))
            .all()
        )
        return [serializar_aviso(fila) for fila in filas]
    finally:
        sesion.close()
