"""
Trabajos de optimizacion PSO de la ventana de envolvente (D-046, ver
PROYECTO.md), ejecutados en segundo plano: con enjambre=30 e
iteraciones=30, una sola frecuencia objetivo tarda del orden de minutos
(medido: ~3 min sobre una señal de ~240.000 muestras) - demasiado para
una respuesta HTTP sincrona normal, que bloquearia el servidor y
terminaria cortada por timeout del navegador.

Router separado de laboratorio.py a proposito (pedido explicito del
desarrollador): no modifica ni depende de /analizar-mat, solo reutiliza
el mismo modulo de lectura de .mat (lectura_mat.py, D-045) para obtener
la señal, y el modulo pso_envolvente.py (tambien separado) para el
calculo.

El estado de los trabajos vive en un diccionario en memoria del propio
proceso - no hay cola ni tabla en base de datos: es una herramienta de
laboratorio de un solo desarrollador, no un servicio multiusuario. Si
el backend se reinicia a mitad de un trabajo, se pierde - limitacion
aceptada a proposito.
"""

import uuid
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile

from backend.procesamiento.envolvente import calcular_espectro_envolvente
from backend.procesamiento.lectura_mat import extraer_variable, leer_señal_cwru
from backend.procesamiento.pso_envolvente import amplitud_en_frecuencia, optimizar_ventana
from seguridad.auth import obtener_usuario_actual

router = APIRouter(
    prefix="/api/laboratorio/pso",
    tags=["laboratorio-pso"],
    dependencies=[Depends(obtener_usuario_actual)],
)

# {job_id: {"estado": "en_progreso"|"completado"|"error", "progreso": 0..1,
#           "resultado": dict|None, "error": str|None}}
TRABAJOS = {}


def _serializar_espectro(frecuencias, amplitudes):
    return [
        {"frecuencia": round(float(f), 4), "amplitud": round(float(a), 6)}
        for f, a in zip(frecuencias, amplitudes)
    ]


def _ejecutar_trabajo(job_id, señal, frecuencia_muestreo, frecuencia_objetivo, enjambre, iteraciones):
    try:
        frecuencia_maxima = max(500.0, frecuencia_objetivo * 1.5)

        # Espectro TRADICIONAL (sin filtrar) para la comparacion - el
        # mismo calculo que ya usa el resto de la aplicacion, solo
        # lectura, no se modifica nada existente. Se lee con el mismo
        # criterio de ventana de tolerancia que el fitness de PSO
        # (amplitud_en_frecuencia), para que la comparacion sea
        # consistente entre ambos lados.
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
async def iniciar_pso(
    background_tasks: BackgroundTasks,
    archivo: UploadFile = File(...),
    frecuencia_muestreo: int = Form(...),
    frecuencia_objetivo: float = Form(...),
    variable_señal: Optional[str] = Form(None),
    enjambre: int = Form(30),
    iteraciones: int = Form(30),
):
    if not archivo.filename.lower().endswith(".mat"):
        raise HTTPException(status_code=422, detail="El archivo debe ser un .mat")

    contenido = await archivo.read()

    if variable_señal:
        try:
            señal = extraer_variable(contenido, variable_señal)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error))
    else:
        try:
            señal = leer_señal_cwru(contenido)["señal"]
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error))

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
