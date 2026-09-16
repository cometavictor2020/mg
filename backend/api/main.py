from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.procesamiento.frecuencia import calcular_fft
from backend.procesamiento.lectura_csv import leer_muestra_csv
from backend.procesamiento.estadisticos import calcular_estadisticos
from basedatos.conexion import SesionLocal
from basedatos.modelos import Usuario, Sensor, Medicion
from seguridad.auth import verificar_password, crear_token_acceso, obtener_usuario_actual
from backend.api.administracion import usuarios, equipos, sensores, modelos_ml


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(usuarios.router)
app.include_router(equipos.router)
app.include_router(sensores.router)
app.include_router(modelos_ml.router)


def obtener_medicion_mas_reciente(sesion, equipo_id):
    return (
        sesion.query(Medicion)
        .join(Sensor, Medicion.sensor_id == Sensor.id)
        .filter(Sensor.equipo_id == equipo_id)
        .order_by(Medicion.fecha_captura.desc())
        .first()
    )


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
def obtener_datos(equipo_id: int, usuario_actual: dict = Depends(obtener_usuario_actual)):
    sesion = SesionLocal()
    try:
        medicion = obtener_medicion_mas_reciente(sesion, equipo_id)
        if not medicion:
            raise HTTPException(
                status_code=404,
                detail="Este equipo no tiene mediciones registradas",
            )

        datos = leer_muestra_csv(
            medicion.ruta_archivo_local,
            cantidad_filas=1000,
        )

        return {
            "columnas": list(datos.columns),
            "cantidad_registros": len(datos),
            "datos": datos.to_dict(orient="records"),
        }
    finally:
        sesion.close()


@app.get("/api/fft")
def obtener_fft(equipo_id: int, usuario_actual: dict = Depends(obtener_usuario_actual)):
    sesion = SesionLocal()
    try:
        medicion = obtener_medicion_mas_reciente(sesion, equipo_id)
        if not medicion:
            raise HTTPException(
                status_code=404,
                detail="Este equipo no tiene mediciones registradas",
            )

        datos = leer_muestra_csv(
            medicion.ruta_archivo_local,
            cantidad_filas=1000,
        )

        resultado_fft = calcular_fft(
            datos=datos,
            frecuencia_muestreo=medicion.frecuencia_muestreo,
            frecuencia_maxima=300,
        )

        return {
            "frecuencia_muestreo": medicion.frecuencia_muestreo,
            "frecuencia_maxima": 300,
            "cantidad_puntos": len(resultado_fft),
            "datos": resultado_fft,
        }
    finally:
        sesion.close()


@app.get("/api/estadisticos")
def obtener_estadisticos(equipo_id: int, usuario_actual: dict = Depends(obtener_usuario_actual)):
    sesion = SesionLocal()
    try:
        medicion = obtener_medicion_mas_reciente(sesion, equipo_id)
        if not medicion:
            raise HTTPException(
                status_code=404,
                detail="Este equipo no tiene mediciones registradas",
            )

        datos = leer_muestra_csv(
            medicion.ruta_archivo_local,
            cantidad_filas=1000,
        )

        return calcular_estadisticos(datos)
    finally:
        sesion.close()
