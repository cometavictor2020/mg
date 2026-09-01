from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.procesamiento.frecuencia import calcular_fft
from backend.procesamiento.lectura_csv import leer_muestra_csv
from backend.procesamiento.estadisticos import calcular_estadisticos
from basedatos.conexion import SesionLocal
from basedatos.modelos import Usuario
from seguridad.auth import verificar_password, crear_token_acceso


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


class CredencialesLogin(BaseModel):
    email: str
    password: str


@app.post("/api/auth/login")
def iniciar_sesion(credenciales: CredencialesLogin):
    sesion = SesionLocal()

    try:
        usuario = (
            sesion.query(Usuario)
            .filter(Usuario.email == credenciales.email)
            .first()
        )

        if not usuario or not verificar_password(
            credenciales.password, usuario.password_hash
        ):
            raise HTTPException(
                status_code=401,
                detail="Correo electrónico o contraseña incorrectos",
            )

        token = crear_token_acceso(
            {"sub": str(usuario.id), "email": usuario.email}
        )

        return {
            "access_token": token,
            "token_type": "bearer",
            "usuario": {
                "id": usuario.id,
                "nombre": usuario.nombre,
                "email": usuario.email,
                "rol": usuario.rol,
            },
        }

    finally:
        sesion.close()


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
