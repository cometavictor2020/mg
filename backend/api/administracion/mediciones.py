"""
Endpoint de carga de mediciones (D-040).

Responsabilidad:
    Recibir un CSV subido por el operador, validarlo (backend/
    procesamiento/validacion_medicion.py) ANTES de aceptarlo, y solo
    si pasa la validacion guardarlo en datos/ y registrarlo en la
    tabla medicion. Si falla la validacion, no se guarda nada.

    D-061: si el archivo no tiene el formato interno, se puede enviar
    con un "mapeo" confirmado (backend/procesamiento/importador.py): se
    convierte primero y el resultado pasa por la MISMA validacion. El
    archivo guardado es siempre el convertido; el mapeo y el nombre del
    original quedan en la medicion.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile

from backend.notificaciones.servicio import notificar_si_corresponde
from backend.procesamiento.diagnostico import cargar_normativa
from backend.procesamiento.importador import aplicar_mapeo
from basedatos.conexion import SesionLocal
from basedatos.modelos import Medicion, Sensor
from backend.procesamiento.validacion_medicion import (
    ErrorValidacionMedicion,
    determinar_perfil,
    ejes_del_perfil,
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

EXTENSIONES_IMPORTABLES = (".csv", ".txt", ".tsv", ".mat")


def _validar_rpm_real(rpm_real, rpm_nominal):
    """
    La velocidad real es opcional, pero si se declara no puede ser absurda:
    debe ser positiva y, si el equipo tiene velocidad nominal, no alejarse de
    ella mas de desviacion_maxima_valida_pct (YAML) - un valor muy distinto
    casi siempre es un error de tipeo (ej. 14500 en vez de 1450).
    """
    if rpm_real <= 0:
        raise HTTPException(status_code=422, detail="La velocidad real debe ser mayor que cero (r/min).")

    if rpm_nominal:
        maxima = cargar_normativa()["criterios_proyecto"]["velocidad_real"]["desviacion_maxima_valida_pct"]
        desviacion = abs(rpm_real - rpm_nominal) / rpm_nominal * 100
        if desviacion > maxima:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"La velocidad real ({rpm_real:g} r/min) se aleja {desviacion:.0f} % de la nominal del "
                    f"equipo ({rpm_nominal:g} r/min): revisa el valor. Un motor con carga suele girar "
                    "unos pocos por ciento por debajo de su velocidad nominal."
                ),
            )


def serializar(medicion):
    return {
        "id": medicion.id,
        "sensor_id": medicion.sensor_id,
        "fecha_captura": medicion.fecha_captura,
        "frecuencia_muestreo": medicion.frecuencia_muestreo,
        "unidad": medicion.unidad,
        "rpm_real": medicion.rpm_real,
        "archivo_origen": medicion.archivo_origen,
        "ruta_archivo_local": medicion.ruta_archivo_local,
    }


@router.post("")
async def cargar_medicion(
    tareas_en_segundo_plano: BackgroundTasks,
    sensor_id: int = Form(...),
    frecuencia_muestreo: int = Form(...),
    unidad: str = Form(...),
    archivo: UploadFile = File(...),
    rpm_real: Optional[float] = Form(None),
    mapeo: Optional[str] = Form(None),
):
    sesion = SesionLocal()
    try:
        sensor = sesion.query(Sensor).filter(Sensor.id == sensor_id).first()
        if not sensor:
            raise HTTPException(status_code=404, detail="Sensor no encontrado")

        if rpm_real is not None:
            _validar_rpm_real(rpm_real, (sensor.equipo.atributos or {}).get("rpm_nominal") if sensor.equipo else None)

        perfil = determinar_perfil(sensor)
        if not perfil:
            nombre_tipo = sensor.tipo_sensor.nombre if sensor.tipo_sensor else "desconocido"
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Todavia no se pueden cargar mediciones para este tipo de sensor "
                    f"('{nombre_tipo}') - por ahora solo se admite vibracion de 1 o 3 ejes."
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

        # D-061: con "mapeo" el archivo puede venir en otro formato (otros
        # nombres de columna, sin timestamp, etc.) y se convierte al interno
        # antes de validarlo. Sin "mapeo" el flujo es exactamente el de siempre.
        mapeo_importacion = None
        if mapeo:
            try:
                mapeo_importacion = json.loads(mapeo)
            except json.JSONDecodeError:
                raise HTTPException(status_code=422, detail={"errores": ["El mapeo de importación no es un JSON válido."]})

        # El importador no convierte unidades: la que declara el mapeo debe ser
        # la misma que se registra, o las amplitudes quedarian mal rotuladas
        # (ej. m/s2 como cm/s2 = un error de 100x en todo lo que sigue).
        if isinstance(mapeo_importacion, dict) and mapeo_importacion.get("unidad") and mapeo_importacion["unidad"] != unidad:
            raise HTTPException(
                status_code=422,
                detail={
                    "errores": [
                        f"El mapeo declara la unidad '{mapeo_importacion['unidad']}' pero la medición se registraría "
                        f"como '{unidad}'. Deben coincidir: el sistema no convierte unidades."
                    ]
                },
            )

        if mapeo_importacion is None:
            if not archivo.filename.lower().endswith(".csv"):
                raise HTTPException(status_code=422, detail="El archivo debe ser un CSV (.csv)")
        elif not archivo.filename.lower().endswith(EXTENSIONES_IMPORTABLES):
            raise HTTPException(status_code=422, detail="El archivo debe ser una tabla de texto (.csv, .txt o .tsv) o un .mat")

        contenido = await archivo.read()

        if mapeo_importacion is not None:
            try:
                contenido, _ = aplicar_mapeo(
                    contenido, mapeo_importacion, frecuencia_muestreo, ejes=ejes_del_perfil(perfil)
                )
            except ValueError as error:
                raise HTTPException(status_code=422, detail={"errores": [str(error)]})

        RUTA_DATOS.mkdir(exist_ok=True)
        marca_tiempo = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        nombre_archivo = f"medicion_sensor{sensor.id}_{marca_tiempo}.csv"
        ruta_destino = RUTA_DATOS / nombre_archivo

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
            rpm_real=rpm_real,
            archivo_origen=archivo.filename if mapeo_importacion is not None else None,
            mapeo_importacion=mapeo_importacion,
            ruta_archivo_local=f"datos/{nombre_archivo}",
            estado_respaldo_s3="pendiente",
        )
        sesion.add(medicion)
        sesion.commit()
        sesion.refresh(medicion)

        # D-054: evalua el equipo y avisa por correo/Telegram si corresponde,
        # DESPUES de responder al operador (no lo hace esperar ni puede
        # hacer fallar la carga si el envio falla).
        tareas_en_segundo_plano.add_task(notificar_si_corresponde, sensor.equipo_id, medicion.id)

        return serializar(medicion)
    finally:
        sesion.close()
