"""
Endpoints de administracion de rodamientos.

Responsabilidad:
    CRUD de la tabla rodamiento. Cada rodamiento pertenece a un equipo y
    tiene un codigo nemotecnico (ej. "ROD-01") unico dentro de ese
    equipo, no globalmente (D-038). La geometria es opcional: sin ella
    no se pueden calcular las frecuencias de falla (BPFO/BPFI/BSF/FTF) -
    eso es un paso posterior, este modulo solo administra el catalogo.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from basedatos.conexion import SesionLocal
from basedatos.modelos import Rodamiento, Equipo, Sensor
from seguridad.auth import obtener_usuario_actual

router = APIRouter(
    prefix="/api/rodamientos",
    tags=["rodamientos"],
    dependencies=[Depends(obtener_usuario_actual)],
)


class RodamientoEntrada(BaseModel):
    equipo_id: int
    ubicacion: Optional[str] = None
    modelo: Optional[str] = None
    numero_elementos_rodantes: Optional[int] = None
    diametro_elemento_mm: Optional[float] = None
    diametro_paso_mm: Optional[float] = None
    angulo_contacto_grados: Optional[float] = None


def serializar(rodamiento):
    return {
        "id": rodamiento.id,
        "codigo": rodamiento.codigo,
        "equipo_id": rodamiento.equipo_id,
        "equipo_nombre": rodamiento.equipo.nombre if rodamiento.equipo else None,
        "ubicacion": rodamiento.ubicacion,
        "modelo": rodamiento.modelo,
        "numero_elementos_rodantes": rodamiento.numero_elementos_rodantes,
        "diametro_elemento_mm": rodamiento.diametro_elemento_mm,
        "diametro_paso_mm": rodamiento.diametro_paso_mm,
        "angulo_contacto_grados": rodamiento.angulo_contacto_grados,
        "geometria_completa": all(
            valor is not None
            for valor in [
                rodamiento.numero_elementos_rodantes,
                rodamiento.diametro_elemento_mm,
                rodamiento.diametro_paso_mm,
                rodamiento.angulo_contacto_grados,
            ]
        ),
    }


def generar_codigo(sesion, equipo_id, excluir_rodamiento_id=None):
    """Siguiente ROD-{NN} disponible para este equipo."""
    consulta = sesion.query(Rodamiento).filter(Rodamiento.equipo_id == equipo_id)
    if excluir_rodamiento_id:
        consulta = consulta.filter(Rodamiento.id != excluir_rodamiento_id)

    numero_maximo = 0
    for rodamiento in consulta.all():
        if rodamiento.codigo and rodamiento.codigo.startswith("ROD-"):
            sufijo = rodamiento.codigo[len("ROD-"):]
            if sufijo.isdigit():
                numero_maximo = max(numero_maximo, int(sufijo))

    return f"ROD-{numero_maximo + 1:02d}"


@router.get("")
def listar_rodamientos(equipo_id: Optional[int] = None):
    sesion = SesionLocal()
    try:
        consulta = sesion.query(Rodamiento)
        if equipo_id is not None:
            consulta = consulta.filter(Rodamiento.equipo_id == equipo_id)

        rodamientos = consulta.order_by(Rodamiento.equipo_id, Rodamiento.codigo).all()
        return [serializar(r) for r in rodamientos]
    finally:
        sesion.close()


@router.post("")
def crear_rodamiento(datos: RodamientoEntrada):
    sesion = SesionLocal()
    try:
        equipo = sesion.query(Equipo).filter(Equipo.id == datos.equipo_id).first()
        if not equipo:
            raise HTTPException(status_code=404, detail="Equipo no encontrado")

        rodamiento = Rodamiento(
            equipo_id=datos.equipo_id,
            codigo=generar_codigo(sesion, datos.equipo_id),
            ubicacion=datos.ubicacion,
            modelo=datos.modelo,
            numero_elementos_rodantes=datos.numero_elementos_rodantes,
            diametro_elemento_mm=datos.diametro_elemento_mm,
            diametro_paso_mm=datos.diametro_paso_mm,
            angulo_contacto_grados=datos.angulo_contacto_grados,
        )
        sesion.add(rodamiento)
        sesion.commit()
        sesion.refresh(rodamiento)
        return serializar(rodamiento)
    finally:
        sesion.close()


@router.put("/{rodamiento_id}")
def actualizar_rodamiento(rodamiento_id: int, datos: RodamientoEntrada):
    sesion = SesionLocal()
    try:
        rodamiento = sesion.query(Rodamiento).filter(Rodamiento.id == rodamiento_id).first()
        if not rodamiento:
            raise HTTPException(status_code=404, detail="Rodamiento no encontrado")

        equipo = sesion.query(Equipo).filter(Equipo.id == datos.equipo_id).first()
        if not equipo:
            raise HTTPException(status_code=404, detail="Equipo no encontrado")

        if rodamiento.equipo_id != datos.equipo_id:
            rodamiento.codigo = generar_codigo(
                sesion, datos.equipo_id, excluir_rodamiento_id=rodamiento.id
            )

        rodamiento.equipo_id = datos.equipo_id
        rodamiento.ubicacion = datos.ubicacion
        rodamiento.modelo = datos.modelo
        rodamiento.numero_elementos_rodantes = datos.numero_elementos_rodantes
        rodamiento.diametro_elemento_mm = datos.diametro_elemento_mm
        rodamiento.diametro_paso_mm = datos.diametro_paso_mm
        rodamiento.angulo_contacto_grados = datos.angulo_contacto_grados

        sesion.commit()
        sesion.refresh(rodamiento)
        return serializar(rodamiento)
    finally:
        sesion.close()


@router.delete("/{rodamiento_id}")
def eliminar_rodamiento(rodamiento_id: int):
    sesion = SesionLocal()
    try:
        rodamiento = sesion.query(Rodamiento).filter(Rodamiento.id == rodamiento_id).first()
        if not rodamiento:
            raise HTTPException(status_code=404, detail="Rodamiento no encontrado")

        sesion.query(Sensor).filter(Sensor.rodamiento_id == rodamiento_id).update(
            {Sensor.rodamiento_id: None}
        )

        sesion.delete(rodamiento)
        sesion.commit()
        return {"mensaje": "Rodamiento eliminado"}
    finally:
        sesion.close()
