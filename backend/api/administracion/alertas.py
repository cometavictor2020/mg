"""
Endpoint de alerta automatica por equipo (D-048, ver PROYECTO.md):
evalua todos los sensores de un equipo contra la normativa (mismo motor
que ya usa "Generar reporte" en reportes.py - D-036/D-039/D-041) y
devuelve las hipotesis de falla encontradas, para que el detalle del
equipo pueda mostrar una alerta real en vez de depender solo del campo
Equipo.estado (manual, ver D-047 en PROYECTO.md).

Se calcula al entrar al detalle de UN equipo (bajo demanda), no para
todos los equipos a la vez - se midio el costo antes de implementar
(ver BITACORA.md): ~10s para 50 equipos x 5 sensores si se hiciera para
todos juntos, muy por encima de lo aceptable para el Resumen General;
para un solo equipo el costo es de decenas de milisegundos.

Efimero, no se persiste nada (mismo criterio que datos_fft/D-042): no
crea un Reporte ni un PDF, a diferencia de POST /api/reportes.
"""

from fastapi import APIRouter, Depends

from basedatos.conexion import SesionLocal
from basedatos.modelos import Equipo, Medicion, Sensor
from backend.procesamiento.diagnostico import diagnosticar_sensor
from backend.procesamiento.frecuencia import calcular_fft
from backend.procesamiento.lectura_csv import leer_ventana_segundos
from seguridad.auth import obtener_usuario_actual

router = APIRouter(
    prefix="/api/alertas",
    tags=["alertas"],
    dependencies=[Depends(obtener_usuario_actual)],
)

# Misma ventana que reportes.py (D-039): duracion en vez de filas fijas,
# para que se ajuste a la frecuencia de muestreo real de cada medicion.
DURACION_VENTANA_SEGUNDOS = 2.0


def _medicion_mas_reciente_de_sensor(sesion, sensor_id):
    return (
        sesion.query(Medicion)
        .filter(Medicion.sensor_id == sensor_id)
        .order_by(Medicion.fecha_captura.desc())
        .first()
    )


@router.get("")
def obtener_alerta_equipo(equipo_id: int):
    """
    Devuelve {"hipotesis": [...], "advertencia": str|None, "severidad_iso": dict|None}.
    "hipotesis" trae, de TODOS los sensores del equipo con medicion,
    todas sus hipotesis de falla (cada una con su sensor_id/sensor_codigo
    agregado), ordenadas por confianza descendente - la primera es la
    peor encontrada en cualquier sensor/rodamiento del equipo.
    "severidad_iso" trae la peor zona ISO 20816-3 (D-050, ver
    PROYECTO.md) encontrada entre los sensores donde fue aplicable, o
    None si ningun sensor tenia los datos necesarios (potencia, tipo de
    soporte, unidad de medicion reconocida).
    "advertencia" explica por que no se pudo evaluar (sin RPM nominal,
    sin sensores) en vez de fallar con un error - es informacion de
    fondo al entrar a la pantalla, no una accion que el usuario pidio.
    """
    sesion = SesionLocal()
    try:
        equipo = sesion.query(Equipo).filter(Equipo.id == equipo_id).first()
        if not equipo:
            return {"hipotesis": [], "advertencia": "Equipo no encontrado", "severidad_iso": None}

        atributos_equipo = equipo.atributos or {}
        rpm_nominal = atributos_equipo.get("rpm_nominal")
        if not rpm_nominal:
            return {
                "hipotesis": [],
                "advertencia": (
                    "No se puede calcular el diagnóstico automático: falta el RPM nominal del "
                    "equipo. Sin él no se puede ubicar 1x/2x/3x en el espectro FFT (desbalanceo, "
                    "desalineación) ni calcular las frecuencias de falla de rodamiento "
                    "(BPFO/BPFI/BSF/FTF) para el espectro de envolvente (Hilbert) — "
                    "configúralo en Configuración → Equipos."
                ),
                "severidad_iso": None,
            }
        potencia_kw = atributos_equipo.get("potencia_kw")
        tipo_soporte = atributos_equipo.get("tipo_soporte")

        sensores = sesion.query(Sensor).filter(Sensor.equipo_id == equipo_id).all()
        if not sensores:
            return {
                "hipotesis": [],
                "advertencia": "Este equipo no tiene sensores registrados.",
                "severidad_iso": None,
            }

        ORDEN_ZONAS_ISO = {"A": 0, "B": 1, "C": 2, "D": 3}

        hipotesis_totales = []
        severidades_aplicables = []
        for sensor in sensores:
            medicion = _medicion_mas_reciente_de_sensor(sesion, sensor.id)
            if not medicion:
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
            )

            for hipotesis in diagnostico["hipotesis"]:
                hipotesis_totales.append(
                    {
                        **hipotesis,
                        "sensor_id": sensor.id,
                        "sensor_codigo": sensor.codigo,
                    }
                )

            severidad = diagnostico.get("severidad_iso")
            if severidad and severidad["aplicable"]:
                severidades_aplicables.append({**severidad, "sensor_id": sensor.id, "sensor_codigo": sensor.codigo})

        hipotesis_totales.sort(key=lambda h: h["confianza"], reverse=True)

        # Igual criterio que las hipotesis de falla: se reporta el peor
        # hallazgo entre todos los sensores del equipo, no un promedio.
        peor_severidad = None
        if severidades_aplicables:
            peor_severidad = max(
                severidades_aplicables, key=lambda s: ORDEN_ZONAS_ISO.get(s["zona"], -1)
            )

        return {"hipotesis": hipotesis_totales, "advertencia": None, "severidad_iso": peor_severidad}
    finally:
        sesion.close()
