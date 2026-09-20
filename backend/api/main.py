from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.procesamiento.frecuencia import calcular_fft
from backend.procesamiento.lectura_csv import leer_muestra_csv, leer_ventana_segundos
from backend.procesamiento.estadisticos import calcular_estadisticos
from backend.procesamiento.diagnostico import cargar_normativa
from backend.procesamiento.diagnostico_rodamientos import (
    calcular_datos_grafico,
    evaluar_rodamiento,
    geometria_completa,
    serializar_datos_grafico,
)
from basedatos.conexion import SesionLocal
from basedatos.modelos import Usuario, Sensor, Medicion
from seguridad.auth import verificar_password, crear_token_acceso, obtener_usuario_actual
from backend.api.administracion import usuarios, equipos, sensores, modelos_ml, tipos_sensor, reportes, rodamientos, mediciones


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
app.include_router(tipos_sensor.router)
app.include_router(reportes.router)
app.include_router(rodamientos.router)
app.include_router(mediciones.router)


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


@app.get("/api/envolvente")
def obtener_envolvente(equipo_id: int, usuario_actual: dict = Depends(obtener_usuario_actual)):
    """
    Espectro de envolvente + señal cruda con su envolvente, para el
    sensor con la medicion mas reciente de este equipo - mismos datos
    que ya se calculan al generar un reporte (reportes.py), pero
    disponibles sin tener que generar uno (D-043, ver PROYECTO.md).
    """
    sesion = SesionLocal()
    try:
        medicion = obtener_medicion_mas_reciente(sesion, equipo_id)
        if not medicion:
            raise HTTPException(status_code=404, detail="Este equipo no tiene mediciones registradas")

        sensor = medicion.sensor
        if not sensor.rodamiento:
            raise HTTPException(
                status_code=422,
                detail="El sensor de este equipo no tiene un rodamiento vinculado (Configuración → Sensores).",
            )

        if not geometria_completa(sensor.rodamiento):
            raise HTTPException(
                status_code=422,
                detail=(
                    f"El rodamiento {sensor.rodamiento.codigo} no tiene su geometría completa "
                    "(Configuración → Rodamientos)."
                ),
            )

        rpm_nominal = (sensor.equipo.atributos or {}).get("rpm_nominal")
        if not rpm_nominal:
            raise HTTPException(
                status_code=422,
                detail="El equipo no tiene RPM nominal registrado (Configuración → Equipos).",
            )

        datos_crudos = leer_ventana_segundos(
            medicion.ruta_archivo_local, medicion.frecuencia_muestreo, duracion_segundos=2.0
        )

        normativa = cargar_normativa()
        hipotesis = evaluar_rodamiento(
            datos_crudos, medicion.frecuencia_muestreo, rpm_nominal, sensor.rodamiento, normativa
        )
        datos_grafico = calcular_datos_grafico(
            datos_crudos, medicion.frecuencia_muestreo, rpm_nominal, sensor.rodamiento, hipotesis
        )

        return {
            "rodamiento_codigo": sensor.rodamiento.codigo,
            "hipotesis": hipotesis,
            "grafico": serializar_datos_grafico(datos_grafico),
        }
    finally:
        sesion.close()
