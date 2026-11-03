"""
Endpoint de laboratorio/validacion (D-044/D-045, ver PROYECTO.md):
analiza un archivo .mat cualquiera con el mismo motor de diagnostico de
rodamientos que ya usa la app
(backend/procesamiento/diagnostico_rodamientos.py), sin pasar por el
modelo Equipo/Sensor/Medicion de la base de datos - un .mat externo no
es una medicion real de planta (D-009/D-011: separado del flujo
principal). Nacio para validar el motor contra un caso del CWRU Bearing
Data Center con resultado ya publicado (Tyagi & Panigrahi, 2017), pero
es generico: no asume ninguna convencion de nombres ni una geometria de
rodamiento en particular - quien sube el archivo puede inspeccionarlo
(/inspeccionar-mat) y elegir manualmente que variable analizar y con
que geometria, en vez de que el sistema lo adivine a ciegas.

No persiste nada en la base de datos ni en disco: la señal se procesa
en memoria y se descarta al responder (mismo criterio efimero que
datos_fft/grafico de envolvente, D-042).
"""

from typing import Optional
from types import SimpleNamespace

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from backend.procesamiento.diagnostico import cargar_normativa
from backend.procesamiento.diagnostico_rodamientos import (
    calcular_datos_grafico,
    evaluar_rodamiento,
    serializar_datos_grafico,
)
from backend.procesamiento.lectura_mat import extraer_variable, inspeccionar_mat, leer_señal_cwru, sugerir_lectura
from seguridad.auth import obtener_usuario_actual

router = APIRouter(
    prefix="/api/laboratorio",
    tags=["laboratorio"],
    dependencies=[Depends(obtener_usuario_actual)],
)

# Valores de EJEMPLO para prellenar el formulario (SKF 6205-2RS JEM, el
# rodamiento del dataset de CWRU y el paper que motivo esta pantalla -
# mismos valores que ya usa herramientas/
# registrar_prueba_falla_rodamiento_envolvente.py). No son un limite:
# son editables en cada analisis para cualquier otro rodamiento/archivo.
GEOMETRIA_SKF_6205_DEFAULT = dict(
    numero_elementos_rodantes=9,
    diametro_elemento_mm=7.94,
    diametro_paso_mm=39.04,
    angulo_contacto_grados=0.0,
)

FRECUENCIA_MAXIMA_ESPECTRO_CRUDO = 5000


def _calcular_espectro_crudo(señal, frecuencia_muestreo, frecuencia_maxima):
    """FFT de una sola señal (no triaxial) - CWRU entrega un unico eje por acelerometro."""
    cantidad_muestras = len(señal)
    frecuencias = np.fft.rfftfreq(cantidad_muestras, d=1 / frecuencia_muestreo)
    amplitudes = 2 * np.abs(np.fft.rfft(señal)) / cantidad_muestras

    mascara = frecuencias <= frecuencia_maxima
    return [
        {"frecuencia": round(float(f), 4), "amplitud": round(float(a), 6)}
        for f, a in zip(frecuencias[mascara], amplitudes[mascara])
    ]


@router.post("/inspeccionar-mat")
async def inspeccionar_mat_endpoint(archivo: UploadFile = File(...)):
    """
    Describe el contenido de cualquier .mat (nombre, forma, tipo de
    dato y una vista previa de cada variable) sin asumir ninguna
    convencion de nombres - para que quien lo sube vea que hay adentro
    antes de elegir que variable analizar en /analizar-mat.
    """
    if not archivo.filename.lower().endswith(".mat"):
        raise HTTPException(status_code=422, detail="El archivo debe ser un .mat")

    contenido = await archivo.read()
    try:
        variables = inspeccionar_mat(contenido)
    except NotImplementedError:
        raise HTTPException(
            status_code=422,
            detail=(
                "El archivo es un .mat de Matlab v7.3 (formato HDF5), que el lector todavía no soporta. "
                "Guárdalo desde Matlab con la opción -v7 (save archivo.mat variables -v7) o conviértelo a CSV."
            ),
        )
    except Exception:
        raise HTTPException(status_code=422, detail="No fue posible leer el archivo como .mat")

    # D-060: "sugerencias" propone (sin aplicar nada) que variable es la
    # señal, la frecuencia de muestreo y la velocidad; "variables" no cambia.
    return {"variables": variables, "sugerencias": sugerir_lectura(variables)}


@router.post("/analizar-mat")
async def analizar_mat(
    archivo: UploadFile = File(...),
    frecuencia_muestreo: Optional[int] = Form(None),
    variable_frecuencia_muestreo: Optional[str] = Form(None),
    variable_señal: Optional[str] = Form(None),
    variable_rpm: Optional[str] = Form(None),
    unidad_variable_rpm: str = Form("rpm"),
    rpm: Optional[float] = Form(None),
    numero_elementos_rodantes: int = Form(GEOMETRIA_SKF_6205_DEFAULT["numero_elementos_rodantes"]),
    diametro_elemento_mm: float = Form(GEOMETRIA_SKF_6205_DEFAULT["diametro_elemento_mm"]),
    diametro_paso_mm: float = Form(GEOMETRIA_SKF_6205_DEFAULT["diametro_paso_mm"]),
    angulo_contacto_grados: float = Form(GEOMETRIA_SKF_6205_DEFAULT["angulo_contacto_grados"]),
):
    if not archivo.filename.lower().endswith(".mat"):
        raise HTTPException(status_code=422, detail="El archivo debe ser un .mat")

    contenido = await archivo.read()

    if unidad_variable_rpm not in ("rpm", "hz"):
        raise HTTPException(status_code=422, detail="La unidad de la variable de velocidad debe ser 'rpm' o 'hz'.")

    # D-060: la frecuencia de muestreo puede venir de una variable del archivo
    # (datasets que la declaran, como los del MFPT). Si se elige, manda sobre
    # el valor manual; si no, se usa el manual como siempre.
    origen_frecuencia_muestreo = "manual"
    if variable_frecuencia_muestreo:
        try:
            frecuencia_muestreo = round(float(extraer_variable(contenido, variable_frecuencia_muestreo)[0]))
        except (ValueError, IndexError) as error:
            raise HTTPException(status_code=422, detail=str(error) or "La variable de frecuencia de muestreo está vacía.")
        origen_frecuencia_muestreo = variable_frecuencia_muestreo

    if not frecuencia_muestreo or frecuencia_muestreo <= 0:
        raise HTTPException(
            status_code=422,
            detail="Indica la frecuencia de muestreo (o elige la variable del archivo que la trae).",
        )

    # Si se elige una variable de señal manualmente (D-045), se usa esa
    # - sin depender de que el archivo siga la convencion de nombres de
    # CWRU. Si no, se autodetecta como antes (leer_señal_cwru).
    if variable_señal:
        try:
            señal = extraer_variable(contenido, variable_señal)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error))

        rpm_archivo = None
        if variable_rpm:
            try:
                rpm_archivo = float(extraer_variable(contenido, variable_rpm)[0])
            except ValueError as error:
                raise HTTPException(status_code=422, detail=str(error))
            # Un archivo que declara la velocidad de giro en Hz (rev/s) en vez
            # de r/min (ej. "rate" = 25 en el MFPT): se convierte a r/min.
            if unidad_variable_rpm == "hz":
                rpm_archivo *= 60

        nombre_variable_señal = variable_señal
    else:
        try:
            datos_mat = leer_señal_cwru(contenido)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error))

        señal = datos_mat["señal"]
        rpm_archivo = datos_mat["rpm"]
        nombre_variable_señal = datos_mat["variable_señal"]

    rpm_final = rpm or rpm_archivo
    if not rpm_final:
        raise HTTPException(
            status_code=422,
            detail="No se pudo determinar el RPM: el archivo no lo trae (o no se indicó la "
            "variable correcta) y tampoco se indicó uno manualmente.",
        )

    rodamiento = SimpleNamespace(
        numero_elementos_rodantes=numero_elementos_rodantes,
        diametro_elemento_mm=diametro_elemento_mm,
        diametro_paso_mm=diametro_paso_mm,
        angulo_contacto_grados=angulo_contacto_grados,
    )
    # calcular_datos_grafico()/evaluar_rodamiento() esperan un DataFrame
    # con columnas vibracion_x/y/z (D-021 del motor de rodamientos);
    # CWRU entrega un solo eje, asi que se envuelve como "vibracion_x"
    # en vez de modificar esas funciones para que acepten un solo eje.
    datos_crudos = pd.DataFrame({"vibracion_x": señal})

    normativa = cargar_normativa()
    hipotesis = evaluar_rodamiento(datos_crudos, frecuencia_muestreo, rpm_final, rodamiento, normativa)
    datos_grafico = calcular_datos_grafico(datos_crudos, frecuencia_muestreo, rpm_final, rodamiento, hipotesis)

    return {
        "variable_señal": nombre_variable_señal,
        "rpm": rpm_final,
        "frecuencia_muestreo": frecuencia_muestreo,
        "origen_frecuencia_muestreo": origen_frecuencia_muestreo,
        "cantidad_muestras": len(señal),
        "espectro_crudo": _calcular_espectro_crudo(señal, frecuencia_muestreo, FRECUENCIA_MAXIMA_ESPECTRO_CRUDO),
        "hipotesis": hipotesis,
        "grafico": serializar_datos_grafico(datos_grafico) if datos_grafico else None,
    }
