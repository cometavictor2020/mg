from typing import Optional

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.procesamiento.frecuencia import calcular_fft
from backend.procesamiento.lectura_csv import leer_muestra_csv, leer_ventana_segundos
from backend.procesamiento.estadisticos import calcular_estadisticos
from backend.procesamiento.diagnostico import cargar_normativa, resolver_velocidad
from backend.procesamiento.diagnostico_rodamientos import (
    calcular_datos_grafico,
    evaluar_rodamiento,
    geometria_completa,
    serializar_datos_grafico,
)
from basedatos.conexion import SesionLocal
from basedatos.modelos import Usuario, Sensor, Medicion
from seguridad.auth import verificar_password, crear_token_acceso, obtener_usuario_actual
from backend.api.administracion import usuarios, equipos, sensores, modelos_ml, tipos_sensor, reportes, rodamientos, mediciones, laboratorio, laboratorio_pso, alertas, analizador_pso, notificaciones, lineas_base, importacion


# La API no arranca si no puede leer los dos archivos de conocimiento (normativa y criterios del proyecto).
cargar_normativa()

# Duracion de la ventana que leen los estadisticos (curtosis, factor de cresta y skewness): la misma que usan la FFT,
# los reportes y las alertas (reportes.py::DURACION_VENTANA_SEGUNDOS), para que describan la misma señal.
DURACION_VENTANA_SEGUNDOS = 2.0

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    # El reporte de Laboratorio avisa por estos encabezados si la IA no pudo redactar (ver /api/laboratorio/reporte-mat).
    expose_headers=["X-Aviso-IA", "X-Con-IA", "Content-Disposition"],
)

app.include_router(usuarios.router)
app.include_router(equipos.router)
app.include_router(sensores.router)
app.include_router(modelos_ml.router)
app.include_router(tipos_sensor.router)
app.include_router(reportes.router)
app.include_router(rodamientos.router)
app.include_router(mediciones.router)
app.include_router(laboratorio.router)
app.include_router(laboratorio_pso.router)
app.include_router(alertas.router)
app.include_router(analizador_pso.router)
app.include_router(notificaciones.router)
app.include_router(lineas_base.router)
app.include_router(importacion.router)


def obtener_medicion_mas_reciente(sesion, equipo_id):
    return (
        sesion.query(Medicion)
        .join(Sensor, Medicion.sensor_id == Sensor.id)
        .filter(Sensor.equipo_id == equipo_id)
        .order_by(Medicion.fecha_captura.desc())
        .first()
    )


def obtener_medicion(sesion, equipo_id, sensor_id):
    """
    Si se indica sensor_id (selector de sensor/rodamiento en el
    frontend), usa la medicion mas reciente de ESE sensor puntual -
    validando que pertenezca al equipo pedido, para no mostrar datos de
    un sensor de otro equipo. Sin sensor_id, mantiene el comportamiento
    anterior (medicion mas reciente entre todos los sensores del
    equipo) para no romper otros posibles llamadores.
    """
    if sensor_id is None:
        return obtener_medicion_mas_reciente(sesion, equipo_id)

    sensor = sesion.query(Sensor).filter(Sensor.id == sensor_id, Sensor.equipo_id == equipo_id).first()
    if not sensor:
        return None

    return (
        sesion.query(Medicion)
        .filter(Medicion.sensor_id == sensor_id)
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
def obtener_datos(
    equipo_id: int, sensor_id: Optional[int] = None, usuario_actual: dict = Depends(obtener_usuario_actual)
):
    sesion = SesionLocal()
    try:
        medicion = obtener_medicion(sesion, equipo_id, sensor_id)
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
def obtener_fft(
    equipo_id: int,
    sensor_id: Optional[int] = None,
    rango_completo: bool = False,
    usuario_actual: dict = Depends(obtener_usuario_actual),
):
    """
    rango_completo=False (por defecto): comportamiento de siempre - 1000
    filas fijas, tope 300 Hz. rango_completo=True (D-049, ver
    PROYECTO.md): lee una ventana de 2s (igual que /api/envolvente,
    D-039) y sube el tope hasta el Nyquist real de la medicion (fs/2) -
    para ver los picos de alta frecuencia (resonancias) que el tope de
    300 Hz nunca mostraba. El frontend no necesita saber de antemano la
    frecuencia de muestreo del sensor: el Nyquist se calcula aca.
    """
    sesion = SesionLocal()
    try:
        medicion = obtener_medicion(sesion, equipo_id, sensor_id)
        if not medicion:
            raise HTTPException(
                status_code=404,
                detail="Este equipo no tiene mediciones registradas",
            )

        if rango_completo:
            datos = leer_ventana_segundos(
                medicion.ruta_archivo_local, medicion.frecuencia_muestreo, duracion_segundos=2.0
            )
            frecuencia_maxima = medicion.frecuencia_muestreo / 2
        else:
            datos = leer_muestra_csv(
                medicion.ruta_archivo_local,
                cantidad_filas=1000,
            )
            frecuencia_maxima = 300

        resultado_fft = calcular_fft(
            datos=datos,
            frecuencia_muestreo=medicion.frecuencia_muestreo,
            frecuencia_maxima=frecuencia_maxima,
        )

        # Velocidad con la que la pantalla marca 1x, 2x y 3x: la que se declaro al cargar la medicion
        # o, si no se declaro, la nominal del equipo (la que usa el reporte para "1x esperado").
        equipo = medicion.sensor.equipo if medicion.sensor else None
        rpm_nominal = (equipo.atributos or {}).get("rpm_nominal") if equipo else None
        rpm_referencia = medicion.rpm_real or rpm_nominal

        return {
            "frecuencia_muestreo": medicion.frecuencia_muestreo,
            "frecuencia_maxima": frecuencia_maxima,
            "cantidad_puntos": len(resultado_fft),
            "rpm_referencia": rpm_referencia,
            "origen_rpm": "declarada" if medicion.rpm_real else ("nominal" if rpm_nominal else None),
            "datos": resultado_fft,
        }
    finally:
        sesion.close()


@app.get("/api/estadisticos")
def obtener_estadisticos(
    equipo_id: int, sensor_id: Optional[int] = None, usuario_actual: dict = Depends(obtener_usuario_actual)
):
    sesion = SesionLocal()
    try:
        medicion = obtener_medicion(sesion, equipo_id, sensor_id)
        if not medicion:
            raise HTTPException(
                status_code=404,
                detail="Este equipo no tiene mediciones registradas",
            )

        datos = leer_ventana_segundos(
            medicion.ruta_archivo_local,
            medicion.frecuencia_muestreo,
            duracion_segundos=DURACION_VENTANA_SEGUNDOS,
        )

        resultado = calcular_estadisticos(datos)
        resultado["cantidad_muestras"] = len(datos)
        resultado["duracion_segundos"] = round(len(datos) / medicion.frecuencia_muestreo, 6)
        return resultado
    finally:
        sesion.close()


@app.get("/api/envolvente")
def obtener_envolvente(
    equipo_id: int, sensor_id: Optional[int] = None, usuario_actual: dict = Depends(obtener_usuario_actual)
):
    """
    Espectro de envolvente + señal cruda con su envolvente, para el
    sensor elegido en el selector (o, sin sensor_id, el que tenga la
    medicion mas reciente del equipo) - mismos datos que ya se calculan
    al generar un reporte (reportes.py), pero disponibles sin tener que
    generar uno (D-043, ver PROYECTO.md).
    """
    sesion = SesionLocal()
    try:
        medicion = obtener_medicion(sesion, equipo_id, sensor_id)
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

        # Misma velocidad que usa el diagnostico automatico (D-057): la
        # declarada en la medicion, o la estimada desde el espectro, o la
        # nominal - asi las frecuencias de falla marcadas en el grafico
        # coinciden con las que evaluo el motor.
        datos_fft = calcular_fft(
            datos=datos_crudos, frecuencia_muestreo=medicion.frecuencia_muestreo, frecuencia_maxima=300
        )
        rpm_uso = resolver_velocidad(
            datos_fft, rpm_nominal, medicion.rpm_real, normativa,
            datos_crudos=datos_crudos, frecuencia_muestreo=medicion.frecuencia_muestreo, rodamiento=sensor.rodamiento,
        )["rpm"]

        hipotesis = evaluar_rodamiento(
            datos_crudos, medicion.frecuencia_muestreo, rpm_uso, sensor.rodamiento, normativa
        )
        datos_grafico = calcular_datos_grafico(
            datos_crudos, medicion.frecuencia_muestreo, rpm_uso, sensor.rodamiento, hipotesis
        )

        return {
            "rodamiento_codigo": sensor.rodamiento.codigo,
            "hipotesis": hipotesis,
            "grafico": serializar_datos_grafico(datos_grafico),
        }
    finally:
        sesion.close()
