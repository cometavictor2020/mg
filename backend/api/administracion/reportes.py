"""
Endpoints de reportes de diagnostico.

Responsabilidad:
    Generar un reporte de diagnostico para un equipo (recorre todos sus
    sensores, corre el motor de reglas de backend/procesamiento/
    diagnostico.py), guardarlo como PDF local (reportes/, excluida de
    Git) y su metadata en la tabla reporte. Envio por correo/Telegram
    queda pendiente (ver Ideas futuras en PROYECTO.md).
"""

from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from basedatos.conexion import SesionLocal
from basedatos.modelos import Equipo, Sensor, Medicion, Reporte
from basedatos.utilidades import obtener_linea_base_activa
from backend.procesamiento.lectura_csv import leer_ventana_segundos
from backend.procesamiento.frecuencia import calcular_fft
from backend.procesamiento.diagnostico import diagnosticar_sensor
from backend.procesamiento.diagnostico_rodamientos import serializar_datos_grafico
from backend.procesamiento.pdf_reporte import generar_pdf_reporte
from backend.procesamiento.redaccion_ia import ErrorIA, estado_ia, redactar_resumen
from seguridad.auth import obtener_usuario_actual

router = APIRouter(
    prefix="/api/reportes",
    tags=["reportes"],
    dependencies=[Depends(obtener_usuario_actual)],
)

RUTA_PROYECTO = Path(__file__).parent.parent.parent.parent
RUTA_REPORTES = RUTA_PROYECTO / "reportes"

# Antes se leian 1000 filas fijas sin importar la frecuencia de
# muestreo de la medicion (con un sensor de 10 kHz eso era apenas 0.1s
# de señal - insuficiente para el motor de rodamientos). Ahora la
# ventana se define por duracion, y se ajusta sola a cada medicion via
# leer_ventana_segundos(). Todavia no es configurable por el usuario
# (eso queda para cuando se aborde el rango de frecuencia ajustable en
# el Analizador de Vibraciones, ver PROYECTO.md).
DURACION_VENTANA_SEGUNDOS = 2.0


class ReporteEntrada(BaseModel):
    equipo_id: int
    # True: se agrega al reporte UNA pagina "Resumen redactado por IA" (redaccion_ia.py). Apagado por defecto.
    con_ia: bool = False


class EliminarLoteEntrada(BaseModel):
    reporte_ids: list[int]


def serializar(reporte):
    resultado = reporte.resultado or {}
    return {
        "id": reporte.id,
        "equipo_id": reporte.equipo_id,
        "equipo_nombre": reporte.equipo.nombre if reporte.equipo else None,
        "fecha_generacion": reporte.fecha_generacion,
        "cantidad_hipotesis": sum(
            len(s.get("diagnostico", {}).get("hipotesis", []))
            for s in resultado.get("sensores", [])
        ),
        "tiene_pdf": bool(reporte.ruta_pdf),
    }


def obtener_medicion_mas_reciente_de_sensor(sesion, sensor_id):
    return (
        sesion.query(Medicion)
        .filter(Medicion.sensor_id == sensor_id)
        .order_by(Medicion.fecha_captura.desc())
        .first()
    )


@router.get("")
def listar_reportes():
    sesion = SesionLocal()
    try:
        reportes = sesion.query(Reporte).order_by(Reporte.fecha_generacion.desc()).all()
        return [serializar(r) for r in reportes]
    finally:
        sesion.close()


@router.get("/ia/estado")
def estado_redaccion_ia():
    """Si el interruptor "Redactar con IA" se puede usar ahora (clave, modelo, paquete) y, si no, por que."""
    return estado_ia()


@router.get("/{reporte_id}")
def obtener_reporte(reporte_id: int):
    sesion = SesionLocal()
    try:
        reporte = sesion.query(Reporte).filter(Reporte.id == reporte_id).first()
        if not reporte:
            raise HTTPException(status_code=404, detail="Reporte no encontrado")

        detalle = serializar(reporte)
        detalle["resultado"] = reporte.resultado
        return detalle
    finally:
        sesion.close()


@router.get("/{reporte_id}/pdf")
def descargar_pdf(reporte_id: int):
    sesion = SesionLocal()
    try:
        reporte = sesion.query(Reporte).filter(Reporte.id == reporte_id).first()
        if not reporte or not reporte.ruta_pdf:
            raise HTTPException(status_code=404, detail="Reporte o PDF no encontrado")

        ruta = Path(reporte.ruta_pdf)
        if not ruta.exists():
            raise HTTPException(status_code=404, detail="El archivo PDF ya no existe en disco")

        return Response(
            content=ruta.read_bytes(),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{ruta.name}"'},
        )
    finally:
        sesion.close()


@router.post("")
def generar_reporte(datos: ReporteEntrada):
    sesion = SesionLocal()
    try:
        equipo = sesion.query(Equipo).filter(Equipo.id == datos.equipo_id).first()
        if not equipo:
            raise HTTPException(status_code=404, detail="Equipo no encontrado")

        atributos_equipo = equipo.atributos or {}
        rpm_nominal = atributos_equipo.get("rpm_nominal")
        if not rpm_nominal:
            raise HTTPException(
                status_code=422,
                detail=(
                    "No se puede calcular el diagnóstico: falta el RPM nominal del equipo. Sin "
                    "él no se puede ubicar 1x/2x/3x en el espectro FFT (desbalanceo, "
                    "desalineación) ni calcular las frecuencias de falla de rodamiento "
                    "(BPFO/BPFI/BSF/FTF) para el espectro de envolvente (Hilbert) — "
                    "configúralo en Configuración → Equipos."
                ),
            )
        potencia_kw = atributos_equipo.get("potencia_kw")
        tipo_soporte = atributos_equipo.get("tipo_soporte")

        sensores = sesion.query(Sensor).filter(Sensor.equipo_id == equipo.id).all()
        if not sensores:
            raise HTTPException(status_code=422, detail="El equipo no tiene sensores registrados")

        resultado_sensores = []
        # Datos crudos (numpy, sin serializar) del grafico de envolvente
        # por sensor, para que pdf_reporte.py los grafique a resolucion
        # completa - se mantienen fuera de resultado_sensores para que
        # nunca terminen ni en la respuesta JSON ni persistidos tal
        # cual (ver serializar_datos_grafico mas abajo).
        graficos_rodamiento_crudos = {}
        for sensor in sensores:
            nombre_tipo = sensor.tipo_sensor.nombre if sensor.tipo_sensor else "Sensor sin tipo"
            medicion = obtener_medicion_mas_reciente_de_sensor(sesion, sensor.id)

            if not medicion:
                resultado_sensores.append({
                    "sensor_id": sensor.id,
                    "nombre_tipo": nombre_tipo,
                    "tiene_medicion": False,
                    "mensaje": "Este sensor no tiene mediciones registradas.",
                })
                continue

            datos_crudos = leer_ventana_segundos(
                medicion.ruta_archivo_local,
                medicion.frecuencia_muestreo,
                duracion_segundos=DURACION_VENTANA_SEGUNDOS,
            )
            datos_fft = calcular_fft(
                datos=datos_crudos,
                frecuencia_muestreo=medicion.frecuencia_muestreo,
                frecuencia_maxima=300,
            )
            diagnostico = diagnosticar_sensor(
                datos_fft,
                rpm_nominal,
                datos_crudos=datos_crudos,
                frecuencia_muestreo=medicion.frecuencia_muestreo,
                rodamiento=sensor.rodamiento,
                potencia_kw=potencia_kw,
                tipo_soporte=tipo_soporte,
                unidad_señal=medicion.unidad,
                orientacion_ejes=(sensor.configuracion or {}).get("orientacion_ejes"),
                linea_base=obtener_linea_base_activa(sesion, sensor.id),
                rpm_real=medicion.rpm_real,
            )

            # El grafico de rodamiento (si se calculo) trae arreglos
            # numpy sin serializar - se guarda aparte para el PDF (a
            # resolucion completa) y se reemplaza en el diagnostico por
            # una version liviana y JSON-serializable para la respuesta.
            grafico_crudo = diagnostico.pop("datos_grafico_rodamiento", None)
            if grafico_crudo is not None:
                graficos_rodamiento_crudos[sensor.id] = grafico_crudo
            diagnostico["grafico_rodamiento"] = serializar_datos_grafico(grafico_crudo)

            resultado_sensores.append({
                "sensor_id": sensor.id,
                "nombre_tipo": nombre_tipo,
                "tiene_medicion": True,
                "diagnostico": diagnostico,
                "datos_fft": datos_fft,
            })

        fecha_generacion = datetime.utcnow()
        reporte_payload = {
            "equipo": {
                "nombre": equipo.nombre,
                "tipo": equipo.tipo_equipo.nombre if equipo.tipo_equipo else None,
                "planta": equipo.planta.nombre if equipo.planta else None,
                "rpm_nominal": rpm_nominal,
            },
            "fecha_generacion": fecha_generacion.strftime("%Y-%m-%d %H:%M"),
            "sensores": resultado_sensores,
        }

        # Redaccion con IA (opcional): un solo reporte, el de siempre mas una pagina "Resumen redactado por IA". Si la
        # IA falla o su texto no pasa la comprobacion de cifras, el reporte sale igual, sin esa pagina, y se avisa.
        aviso_ia = None
        if datos.con_ia:
            try:
                reporte_payload["resumen_ia"] = redactar_resumen(reporte_payload)
            except ErrorIA as error:
                aviso_ia = str(error)

        pdf_bytes = generar_pdf_reporte(reporte_payload, graficos_rodamiento_crudos)

        RUTA_REPORTES.mkdir(exist_ok=True)
        marca_tiempo = fecha_generacion.strftime("%Y%m%d_%H%M%S")
        ruta_pdf = RUTA_REPORTES / f"reporte_equipo{equipo.id}_{marca_tiempo}.pdf"
        ruta_pdf.write_bytes(pdf_bytes)

        # Se guarda el grafico (liviano, ya serializado) de cada sensor
        # para reponerlo solo en ESTA respuesta puntual - no se persiste
        # (ver mas abajo), asi que despues de generado el reporte no
        # vuelve a estar disponible (misma logica que datos_fft).
        graficos_para_respuesta = {
            sr["sensor_id"]: sr["diagnostico"]["grafico_rodamiento"]
            for sr in resultado_sensores
            if sr.get("diagnostico", {}).get("grafico_rodamiento") is not None
        }

        # El espectro FFT completo y el grafico de envolvente (señal en
        # el tiempo incluida) no se persisten en la base de datos (son
        # pesados y no hay pantalla que los vuelva a mostrar despues de
        # generado el reporte) - quedan solo en el PDF y en esta misma
        # respuesta, la vez que se genera.
        for sensor_resultado in resultado_sensores:
            sensor_resultado.pop("datos_fft", None)
            sensor_resultado.get("diagnostico", {}).pop("grafico_rodamiento", None)

        resultado_guardado = {
            "equipo": reporte_payload["equipo"],
            "fecha_generacion": reporte_payload["fecha_generacion"],
            "sensores": resultado_sensores,
        }
        if reporte_payload.get("resumen_ia"):
            resultado_guardado["resumen_ia"] = reporte_payload["resumen_ia"]
        if aviso_ia:
            resultado_guardado["aviso_ia"] = aviso_ia

        reporte = Reporte(
            equipo_id=equipo.id,
            fecha_generacion=fecha_generacion,
            resultado=resultado_guardado,
            ruta_pdf=str(ruta_pdf),
        )
        sesion.add(reporte)
        sesion.commit()
        sesion.refresh(reporte)

        detalle = serializar(reporte)
        detalle["resultado"] = reporte.resultado
        for sensor_resultado in detalle["resultado"]["sensores"]:
            grafico = graficos_para_respuesta.get(sensor_resultado.get("sensor_id"))
            if grafico is not None:
                sensor_resultado["diagnostico"]["grafico_rodamiento"] = grafico
        return detalle
    finally:
        sesion.close()


@router.post("/eliminar-lote")
def eliminar_reportes_lote(datos: EliminarLoteEntrada):
    """
    Borrado por lote (checkbox "Seleccionar todos" en Reportes.jsx) -
    misma logica que eliminar_reporte() para cada id, en una sola
    transaccion. Ids que no existan se ignoran en silencio (ej. si el
    historial ya se recargo y un reporte seleccionado fue borrado por
    otra pestaña) en vez de fallar todo el lote.
    """
    sesion = SesionLocal()
    try:
        reportes = sesion.query(Reporte).filter(Reporte.id.in_(datos.reporte_ids)).all()
        for reporte in reportes:
            if reporte.ruta_pdf:
                Path(reporte.ruta_pdf).unlink(missing_ok=True)
            sesion.delete(reporte)
        sesion.commit()
        return {"mensaje": f"{len(reportes)} reporte(s) eliminado(s)", "cantidad": len(reportes)}
    finally:
        sesion.close()


@router.delete("/{reporte_id}")
def eliminar_reporte(reporte_id: int):
    sesion = SesionLocal()
    try:
        reporte = sesion.query(Reporte).filter(Reporte.id == reporte_id).first()
        if not reporte:
            raise HTTPException(status_code=404, detail="Reporte no encontrado")

        if reporte.ruta_pdf:
            Path(reporte.ruta_pdf).unlink(missing_ok=True)

        sesion.delete(reporte)
        sesion.commit()
        return {"mensaje": "Reporte eliminado"}
    finally:
        sesion.close()
