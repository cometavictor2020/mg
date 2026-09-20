"""
Endpoint de carga de mediciones (D-040).

Responsabilidad:
    Recibir un CSV subido por el operador, validarlo (backend/
    procesamiento/validacion_medicion.py) ANTES de aceptarlo, y solo
    si pasa la validacion guardarlo en datos/ y registrarlo en la
    tabla medicion. Si falla la validacion, no se guarda nada.
"""

from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from basedatos.conexion import SesionLocal
from basedatos.modelos import Medicion, Sensor
from backend.procesamiento.validacion_medicion import (
    ErrorValidacionMedicion,
    determinar_perfil,
    validar_archivo_medicion,
)
from seguridad.auth import obtener_usuario_actual

router = APIRouter(
    prefix="/api/mediciones",
    tags=["mediciones"],
    dependencies=[Depends(obtener_usuario_actual)],
)

RUTA_PROYECTO = Path(__file__).parent.parent.parent.parent
RUTA_DATOS = RUTA_PROYECTO / "datos"


def serializar(medicion):
    return {
        "id": medicion.id,
        "sensor_id": medicion.sensor_id,
        "fecha_captura": medicion.fecha_captura,
        "frecuencia_muestreo": medicion.frecuencia_muestreo,
        "unidad": medicion.unidad,
        "ruta_archivo_local": medicion.ruta_archivo_local,
    }


@router.post("")
async def cargar_medicion(
    sensor_id: int = Form(...),
    frecuencia_muestreo: int = Form(...),
    unidad: str = Form(...),
    archivo: UploadFile = File(...),
):
    sesion = SesionLocal()
    try:
        sensor = sesion.query(Sensor).filter(Sensor.id == sensor_id).first()
        if not sensor:
            raise HTTPException(status_code=404, detail="Sensor no encontrado")

        perfil = determinar_perfil(sensor)
        if not perfil:
            nombre_tipo = sensor.tipo_sensor.nombre if sensor.tipo_sensor else "desconocido"
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Todavia no se pueden cargar mediciones para este tipo de sensor "
                    f"('{nombre_tipo}') - por ahora solo se admite vibracion triaxial."
                ),
            )

        unidades_disponibles = (sensor.configuracion or {}).get("unidades", [])
        if unidad not in unidades_disponibles:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"'{unidad}' no es una unidad configurada para este sensor. "
                    f"Disponibles: {', '.join(unidades_disponibles) or 'ninguna'}."
                ),
            )

        if not archivo.filename.lower().endswith(".csv"):
            raise HTTPException(status_code=422, detail="El archivo debe ser un CSV (.csv)")

        RUTA_DATOS.mkdir(exist_ok=True)
        marca_tiempo = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        nombre_archivo = f"medicion_sensor{sensor.id}_{marca_tiempo}.csv"
        ruta_destino = RUTA_DATOS / nombre_archivo

        contenido = await archivo.read()
        ruta_destino.write_bytes(contenido)

        try:
            validar_archivo_medicion(ruta_destino, perfil=perfil)
        except ErrorValidacionMedicion as error:
            ruta_destino.unlink(missing_ok=True)
            raise HTTPException(status_code=422, detail={"errores": error.errores})

        medicion = Medicion(
            sensor_id=sensor.id,
            frecuencia_muestreo=frecuencia_muestreo,
            unidad=unidad,
            ruta_archivo_local=f"datos/{nombre_archivo}",
            estado_respaldo_s3="pendiente",
        )
        sesion.add(medicion)
        sesion.commit()
        sesion.refresh(medicion)

        return serializar(medicion)
    finally:
        sesion.close()
