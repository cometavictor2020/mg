from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.procesamiento.frecuencia import calcular_fft
from backend.procesamiento.lectura_csv import leer_muestra_csv
from backend.procesamiento.estadisticos import calcular_estadisticos


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


RUTA_ARCHIVO_DATOS = "datos/datos_vibracion_motor.csv"
FRECUENCIA_MUESTREO = 10000


@app.get("/")
def inicio():
    return {
        "mensaje": "Backend de MotorGuardian funcionando"
    }


@app.get("/api/datos")
def obtener_datos():
    datos = leer_muestra_csv(
        RUTA_ARCHIVO_DATOS,
        cantidad_filas=1000,
    )

    return {
        "columnas": list(datos.columns),
        "cantidad_registros": len(datos),
        "datos": datos.to_dict(orient="records"),
    }


@app.get("/api/fft")
def obtener_fft():
    datos = leer_muestra_csv(
        RUTA_ARCHIVO_DATOS,
        cantidad_filas=1000,
    )

    resultado_fft = calcular_fft(
        datos=datos,
        frecuencia_muestreo=FRECUENCIA_MUESTREO,
        frecuencia_maxima=300,
    )

    return {
        "frecuencia_muestreo": FRECUENCIA_MUESTREO,
        "frecuencia_maxima": 300,
        "cantidad_puntos": len(resultado_fft),
        "datos": resultado_fft,
    }


@app.get("/api/estadisticos")
def obtener_estadisticos():
    datos = leer_muestra_csv(
        RUTA_ARCHIVO_DATOS,
        cantidad_filas=1000,
    )

    resultado = calcular_estadisticos(datos)

    return resultado
