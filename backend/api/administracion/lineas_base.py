"""
Endpoints de la linea base de un sensor (D-056, ver PROYECTO.md).

Responsabilidad:
    Marcar la medicion mas reciente de un sensor (o las ultimas n, o las que
    se indiquen) como referencia de una condicion SANA, consultar si un sensor
    la tiene y quitarla. Con varios registros la referencia de cada armonico es
    el maximo entre ellos (criterios_proyecto.linea_base_varios_registros); con
    uno, es la linea base de siempre. El calculo de
    los valores de referencia vive en backend/procesamiento/linea_base.py;
    aca solo se orquesta (D-012). Quien consume la linea base es el motor de
    diagnostico, via basedatos/utilidades.py::obtener_linea_base_activa.

Un sensor tiene a lo mas una linea base activa: marcar otra desactiva la
anterior (queda como historial, no se borra). Quitarla tambien solo la
desactiva.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from basedatos.conexion import SesionLocal
from basedatos.modelos import LineaBase, Medicion, Sensor
from backend.procesamiento.cambio_linea_base import calcular_valores_velocidad_linea_base
from backend.procesamiento.diagnostico import TOLERANCIA_FRECUENCIA_PCT, cargar_normativa, resolver_velocidad
from backend.procesamiento.frecuencia import calcular_fft
from backend.procesamiento.lectura_csv import leer_ventana_segundos
from backend.procesamiento.linea_base import (
    calcular_valores_linea_base,
    combinar_valores_linea_base,
    evaluar_registros_de_referencia,
)
from seguridad.auth import obtener_usuario_actual

router = APIRouter(
    prefix="/api/lineas-base",
    tags=["lineas-base"],
    dependencies=[Depends(obtener_usuario_actual)],
)

# Misma ventana que usa el motor de diagnostico (reportes.py/alertas.py), para
# que la referencia y la medicion que se compara contra ella sean comparables.
DURACION_VENTANA_SEGUNDOS = 2.0


class LineaBaseEntrada(BaseModel):
    sensor_id: int
    # YAML: gestion_condicion.baseline.requerir_condicion_sana_confirmada.
    # Marcar como referencia una medicion con falla haria que el sistema
    # considerara "normal" justo lo que debe detectar.
    confirmado_sano: bool = False
    # Con cuantas mediciones se arma la referencia: las ULTIMAS n del sensor, o las que se indiquen en
    # mediciones_ids (tienen prioridad). 1 = la linea base de un solo registro de siempre.
    cantidad_registros: int = Field(default=1, ge=1)
    mediciones_ids: list[int] | None = None


def serializar(linea_base):
    medicion = linea_base.medicion
    valores = linea_base.valores or {}
    return {
        "id": linea_base.id,
        "sensor_id": linea_base.sensor_id,
        "medicion_id": linea_base.medicion_id,
        "fecha_creacion": linea_base.fecha_creacion.isoformat() if linea_base.fecha_creacion else None,
        "fecha_medicion": medicion.fecha_captura.isoformat() if medicion and medicion.fecha_captura else None,
        "rpm": valores.get("rpm"),
        "amplitudes": valores.get("amplitudes"),
        "indicador_cambio_disponible": bool(valores.get("velocidad_rms")),
        "velocidad_rms_mm_s": (valores.get("velocidad_rms") or {}).get("por_eje_mm_s"),
        # Las lineas base marcadas antes de existir la de varios registros no traen estos campos: son de 1.
        "n_registros": valores.get("n_registros", 1),
        "regla_combinacion": valores.get("regla_combinacion"),
        "mediciones_origen": valores.get("mediciones_origen") or [linea_base.medicion_id],
        "avisos": valores.get("avisos") or [],
    }


def _linea_base_activa(sesion, sensor_id):
    return (
        sesion.query(LineaBase)
        .filter(LineaBase.sensor_id == sensor_id, LineaBase.activa.is_(True))
        .order_by(LineaBase.fecha_creacion.desc())
        .first()
    )


@router.get("")
def obtener_linea_base(sensor_id: int):
    sesion = SesionLocal()
    try:
        if not sesion.query(Sensor).filter(Sensor.id == sensor_id).first():
            raise HTTPException(status_code=404, detail="Sensor no encontrado")

        linea_base = _linea_base_activa(sesion, sensor_id)
        parametros = cargar_normativa()["criterios_proyecto"]["linea_base_varios_registros"]
        return {
            "sensor_id": sensor_id,
            "linea_base": serializar(linea_base) if linea_base else None,
            # Para que la pantalla ofrezca el rango y la cantidad recomendada sin repetir las cifras del YAML.
            "registros_minimos": parametros["registros_minimos"],
            "registros_maximos": parametros["registros_maximos"],
        }
    finally:
        sesion.close()


def _valores_de_medicion(medicion, rpm_nominal, normativa):
    """Valores de referencia (1x/2x/3x por eje y velocidad RMS) de UNA medicion."""
    try:
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
    except (FileNotFoundError, ValueError) as error:
        raise HTTPException(status_code=422, detail=f"No se pudo leer la medición {medicion.id}: {error}")

    # La referencia se mide en los armonicos de la velocidad de ESA
    # medicion (declarada o estimada), no de la nominal: con carga el
    # motor gira por debajo de ella (D-057).
    velocidad = resolver_velocidad(datos_fft, rpm_nominal, medicion.rpm_real)
    valores = calcular_valores_linea_base(datos_fft, velocidad["rpm"], TOLERANCIA_FRECUENCIA_PCT)
    valores["velocidad_origen"] = velocidad["origen"]
    # D-059: velocidad RMS de banda limitada por eje, para el indicador de
    # cambio. Queda en None si la medicion no declara una unidad de
    # aceleracion o velocidad reconocida (la linea base se guarda igual:
    # sirve para 1x/2x/3x, solo falta el indicador).
    valores["velocidad_rms"] = calcular_valores_velocidad_linea_base(
        datos_crudos, medicion.frecuencia_muestreo, medicion.unidad, velocidad["rpm"], normativa
    )
    return valores


def _mediciones_de_referencia(sesion, sensor, datos, maximo):
    """
    Las mediciones con que se arma la linea base, de la mas antigua a la mas reciente: las que el usuario
    indica (mediciones_ids) o, si no, las ultimas `cantidad_registros` del sensor.
    """
    consulta = sesion.query(Medicion).filter(Medicion.sensor_id == sensor.id)

    if datos.mediciones_ids:
        ids = list(dict.fromkeys(datos.mediciones_ids))
        if len(ids) > maximo:
            raise HTTPException(status_code=422, detail=f"Se pueden usar a lo más {maximo} mediciones como referencia.")
        mediciones = consulta.filter(Medicion.id.in_(ids)).all()
        faltantes = set(ids) - {m.id for m in mediciones}
        if faltantes:
            raise HTTPException(
                status_code=422,
                detail=f"Las mediciones {sorted(faltantes)} no existen o no pertenecen a este sensor.",
            )
    else:
        if datos.cantidad_registros > maximo:
            raise HTTPException(status_code=422, detail=f"Se pueden usar a lo más {maximo} mediciones como referencia.")
        mediciones = consulta.order_by(Medicion.fecha_captura.desc()).limit(datos.cantidad_registros).all()
        if not mediciones:
            raise HTTPException(status_code=422, detail="Este sensor no tiene mediciones registradas.")
        if len(mediciones) < datos.cantidad_registros:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Este sensor solo tiene {len(mediciones)} medición(es) registrada(s); "
                    f"no se pueden usar {datos.cantidad_registros} como referencia."
                ),
            )

    return sorted(mediciones, key=lambda m: (m.fecha_captura is None, m.fecha_captura, m.id))


@router.post("")
def marcar_linea_base(datos: LineaBaseEntrada):
    if not datos.confirmado_sano:
        raise HTTPException(
            status_code=422,
            detail=(
                "Confirma que el equipo estaba sano y operando en condiciones normales al "
                "tomar esta medición: una línea base tomada con una falla haría que el "
                "sistema la considere normal."
            ),
        )

    sesion = SesionLocal()
    try:
        sensor = sesion.query(Sensor).filter(Sensor.id == datos.sensor_id).first()
        if not sensor:
            raise HTTPException(status_code=404, detail="Sensor no encontrado")

        rpm_nominal = ((sensor.equipo.atributos or {}) if sensor.equipo else {}).get("rpm_nominal")
        if not rpm_nominal:
            raise HTTPException(
                status_code=422,
                detail=(
                    "No se puede calcular la línea base: falta el RPM nominal del equipo, necesario "
                    "para ubicar 1x/2x/3x en el espectro — configúralo en Configuración → Equipos."
                ),
            )

        normativa = cargar_normativa()
        criterios = normativa["criterios_proyecto"]
        parametros = criterios["linea_base_varios_registros"]

        mediciones = _mediciones_de_referencia(sesion, sensor, datos, parametros["registros_maximos"])
        valores_por_registro = [_valores_de_medicion(m, rpm_nominal, normativa) for m in mediciones]

        valores = combinar_valores_linea_base(valores_por_registro, parametros["regla_combinacion"])
        valores["mediciones_origen"] = [m.id for m in mediciones]
        valores["avisos"] = evaluar_registros_de_referencia(
            valores_por_registro,
            minimo=parametros["registros_minimos"],
            factor_atipico=criterios["definicion_cualitativa"]["muy_elevado"]["min_ratio_baseline"],
            tolerancia_velocidad_pct=criterios["tolerancias"]["coincidencia_frecuencia_pct_default"],
        )

        for anterior in sesion.query(LineaBase).filter(
            LineaBase.sensor_id == sensor.id, LineaBase.activa.is_(True)
        ):
            anterior.activa = False

        # medicion_id apunta a la mas reciente; las demas quedan en valores["mediciones_origen"].
        nueva = LineaBase(sensor_id=sensor.id, medicion_id=mediciones[-1].id, valores=valores, activa=True)
        sesion.add(nueva)
        sesion.commit()
        sesion.refresh(nueva)
        return serializar(nueva)
    finally:
        sesion.close()


@router.delete("/{linea_base_id}")
def quitar_linea_base(linea_base_id: int):
    sesion = SesionLocal()
    try:
        linea_base = sesion.query(LineaBase).filter(LineaBase.id == linea_base_id).first()
        if not linea_base:
            raise HTTPException(status_code=404, detail="Línea base no encontrada")

        linea_base.activa = False
        sesion.commit()
        return {"mensaje": "Línea base desactivada"}
    finally:
        sesion.close()
