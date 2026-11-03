"""
Endpoints del importador de archivos de medicion (D-061, ver PROYECTO.md).

/analizar lee un archivo (sin guardar nada) y devuelve que trae, una propuesta
de mapeo hacia el formato interno y las plantillas guardadas que calzan con su
forma. La conversion en si ocurre al cargar la medicion (POST /api/mediciones
con "mapeo"), no aqui. Las plantillas son mapeos ya confirmados que se
reutilizan para los archivos siguientes del mismo origen.
"""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError

from backend.procesamiento.importador import analizar_archivo, validar_mapeo
from basedatos.conexion import SesionLocal
from basedatos.modelos import PlantillaImportacion
from seguridad.auth import obtener_usuario_actual

router = APIRouter(
    prefix="/api/importacion",
    tags=["importacion"],
    dependencies=[Depends(obtener_usuario_actual)],
)

EXTENSIONES_TABULARES = (".csv", ".txt", ".tsv", ".mat")


class PlantillaEntrada(BaseModel):
    nombre: str
    huella: str
    mapeo: dict


def serializar(plantilla):
    return {
        "id": plantilla.id,
        "nombre": plantilla.nombre,
        "huella": plantilla.huella,
        "mapeo": plantilla.mapeo,
        "fecha_creacion": plantilla.fecha_creacion,
    }


@router.post("/analizar")
async def analizar(archivo: UploadFile = File(...)):
    if not (archivo.filename or "").lower().endswith(EXTENSIONES_TABULARES):
        raise HTTPException(
            status_code=422,
            detail={"errores": ["El archivo debe ser una tabla de texto (.csv, .txt o .tsv) o un .mat de Matlab."]},
        )

    contenido = await archivo.read()
    try:
        resultado = analizar_archivo(contenido, archivo.filename)
    except ValueError as error:
        raise HTTPException(status_code=422, detail={"errores": [str(error)]})

    sesion = SesionLocal()
    try:
        plantillas = (
            sesion.query(PlantillaImportacion)
            .filter(PlantillaImportacion.huella == resultado["huella"])
            .order_by(PlantillaImportacion.fecha_creacion.desc())
            .all()
        )
        resultado["plantillas_coincidentes"] = [serializar(plantilla) for plantilla in plantillas]
    finally:
        sesion.close()

    resultado["nombre_archivo"] = archivo.filename
    return resultado


@router.get("/plantillas")
def listar_plantillas():
    sesion = SesionLocal()
    try:
        plantillas = sesion.query(PlantillaImportacion).order_by(PlantillaImportacion.nombre).all()
        return [serializar(plantilla) for plantilla in plantillas]
    finally:
        sesion.close()


@router.post("/plantillas")
def guardar_plantilla(datos: PlantillaEntrada):
    nombre = datos.nombre.strip()
    if not nombre:
        raise HTTPException(status_code=422, detail="Escribe un nombre para la plantilla.")

    errores = validar_mapeo(datos.mapeo)
    if errores:
        raise HTTPException(status_code=422, detail=" ".join(errores))

    sesion = SesionLocal()
    try:
        plantilla = PlantillaImportacion(nombre=nombre, huella=datos.huella, mapeo=datos.mapeo)
        sesion.add(plantilla)
        try:
            sesion.commit()
        except IntegrityError:
            sesion.rollback()
            raise HTTPException(status_code=409, detail=f"Ya existe una plantilla llamada '{nombre}'.")
        sesion.refresh(plantilla)
        return serializar(plantilla)
    finally:
        sesion.close()


@router.delete("/plantillas/{plantilla_id}")
def eliminar_plantilla(plantilla_id: int):
    sesion = SesionLocal()
    try:
        plantilla = sesion.query(PlantillaImportacion).filter(PlantillaImportacion.id == plantilla_id).first()
        if not plantilla:
            raise HTTPException(status_code=404, detail="Plantilla no encontrada")

        sesion.delete(plantilla)
        sesion.commit()
        return {"mensaje": "Plantilla eliminada"}
    finally:
        sesion.close()
