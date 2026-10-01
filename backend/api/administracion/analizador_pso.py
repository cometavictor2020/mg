"""
Trabajos de optimizacion PSO de la ventana de envolvente (D-049, ver
PROYECTO.md) sobre la medicion real de un sensor - misma logica que
laboratorio_pso.py (D-046), pero sobre datos de un equipo/sensor real
en vez de un .mat subido. Router separado de laboratorio_pso.py a
proposito: ese modulo se mantiene deliberadamente aislado del modelo
Equipo/Sensor/Medicion (D-046), asi que la version para datos reales
vive en un archivo aparte, no ahi.

Reutiliza el mismo algoritmo (pso_envolvente.py) sin modificarlo - lo
unico que cambia es de donde sale la señal: leer_ventana_segundos()
sobre la medicion mas reciente del sensor, en vez de un archivo .mat
subido por el usuario.

Mismo criterio que laboratorio_pso.py: trabajo en segundo plano via
BackgroundTasks de FastAPI (con 30x30 toma minutos, no puede ser una
respuesta HTTP sincrona), estado de los trabajos en memoria del proceso
(sin cola ni tabla en base de datos - se pierde si el backend se
reinicia a mitad de un trabajo, aceptado a proposito).

Importante (D-049): la alerta automatica (D-048, backend/api/
administracion/alertas.py) y el diagnostico de rodamiento que ya corre
en segundo plano (diagnosticar_sensor -> evaluar_rodamiento, con su
propio calculo interno de Hilbert) NO dependen de este modulo ni de que
el usuario haya pedido aplicar Hilbert o PSO desde la pantalla - siguen
funcionando exactamente igual, este modulo solo agrega una
visualizacion bajo demanda.
"""

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from basedatos.conexion import SesionLocal
from basedatos.modelos import Medicion, Sensor
from backend.procesamiento.envolvente import calcular_espectro_envolvente
from backend.procesamiento.lectura_csv import leer_ventana_segundos
from backend.procesamiento.pso_envolvente import amplitud_en_frecuencia, optimizar_ventana
from seguridad.auth import obtener_usuario_actual

router = APIRouter(
    prefix="/api/analizador/pso",
    tags=["analizador-pso"],
    dependencies=[Depends(obtener_usuario_actual)],
)

TRABAJOS = {}


def _medicion_mas_reciente_de_sensor(sesion, sensor_id):
    return (
        sesion.query(Medicion)
        .filter(Medicion.sensor_id == sensor_id)
        .order_by(Medicion.fecha_captura.desc())
        .first()
    )


def _serializar_espectro(frecuencias, amplitudes):
    return [
        {"frecuencia": round(float(f), 4), "amplitud": round(float(a), 6)}
        for f, a in zip(frecuencias, amplitudes)
    ]


def _ejecutar_trabajo(job_id, señal, frecuencia_muestreo, frecuencia_objetivo, enjambre, iteraciones):
    try:
        frecuencia_maxima = max(500.0, frecuencia_objetivo * 1.5)

        # Espectro TRADICIONAL (sin filtrar), mismo calculo que ya usa
        # /api/envolvente - solo lectura, no se modifica nada existente.
        frecuencias_trad, amplitudes_trad = calcular_espectro_envolvente(señal, frecuencia_muestreo, frecuencia_maxima)
        amplitud_tradicional = amplitud_en_frecuencia(frecuencias_trad, amplitudes_trad, frecuencia_objetivo)

        def reportar_progreso(iteracion, _mejor_fitness):
            TRABAJOS[job_id]["progreso"] = iteracion / iteraciones

        resultado_pso = optimizar_ventana(
            señal,
            frecuencia_muestreo,
            frecuencia_objetivo,
            enjambre=enjambre,
            iteraciones=iteraciones,
            callback_progreso=reportar_progreso,
        )

        amplificacion = (
            resultado_pso["amplitud"] / amplitud_tradicional if amplitud_tradicional > 0 else None
        )

        TRABAJOS[job_id].update(
            estado="completado",
            progreso=1.0,
            resultado={
                "frecuencia_objetivo": frecuencia_objetivo,
                "tradicional": {
                    "amplitud": amplitud_tradicional,
                    "espectro": _serializar_espectro(frecuencias_trad, amplitudes_trad),
                },
                "pso": {
                    "frecuencia_central": resultado_pso["frecuencia_central"],
                    "ancho_banda": resultado_pso["ancho_banda"],
                    "amplitud": resultado_pso["amplitud"],
                    "espectro": _serializar_espectro(
                        resultado_pso["espectro_frecuencias"], resultado_pso["espectro_amplitudes"]
                    ),
                    "historial_fitness": resultado_pso["historial_fitness"],
                },
                "amplificacion": amplificacion,
            },
        )
    except Exception as error:
        TRABAJOS[job_id].update(estado="error", error=str(error))


@router.post("/iniciar")
def iniciar_pso(
    background_tasks: BackgroundTasks,
    equipo_id: int,
    sensor_id: int,
    frecuencia_objetivo: float,
    enjambre: int = 30,
    iteraciones: int = 30,
):
    sesion = SesionLocal()
    try:
        sensor = sesion.query(Sensor).filter(Sensor.id == sensor_id, Sensor.equipo_id == equipo_id).first()
        if not sensor:
            raise HTTPException(status_code=404, detail="Sensor no encontrado en este equipo")

        medicion = _medicion_mas_reciente_de_sensor(sesion, sensor_id)
        if not medicion:
            raise HTTPException(status_code=404, detail="Este sensor no tiene mediciones registradas")

        señal_df = leer_ventana_segundos(
            medicion.ruta_archivo_local, medicion.frecuencia_muestreo, duracion_segundos=2.0
        )
        # PSO trabaja sobre un solo eje - se usa vibracion_x, mismo
        # criterio de "un eje representativo" que ya usa
        # diagnostico_rodamientos.py para graficar.
        señal = señal_df["vibracion_x"].to_numpy()
        frecuencia_muestreo = medicion.frecuencia_muestreo
    finally:
        sesion.close()

    job_id = uuid.uuid4().hex
    TRABAJOS[job_id] = {"estado": "en_progreso", "progreso": 0.0, "resultado": None, "error": None}

    background_tasks.add_task(
        _ejecutar_trabajo, job_id, señal, frecuencia_muestreo, frecuencia_objetivo, enjambre, iteraciones
    )

    return {"job_id": job_id}


@router.get("/estado/{job_id}")
def estado_pso(job_id: str):
    trabajo = TRABAJOS.get(job_id)
    if not trabajo:
        raise HTTPException(status_code=404, detail="Trabajo no encontrado")
    return trabajo
