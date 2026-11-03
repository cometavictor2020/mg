"""
Modelos ORM de MotorGuardian.

Responsabilidad:
    Definir la estructura de las tablas de la base de datos: equipos,
    sensores, mediciones, resultados de analisis y usuarios.
"""

from datetime import datetime

from sqlalchemy import Boolean, Column, Integer, Float, String, ForeignKey, DateTime, JSON, Text, UniqueConstraint
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class TipoEquipo(Base):
    """Catalogo abierto de tipos de equipo (motor monofasico, bomba, etc.)."""

    __tablename__ = "tipo_equipo"

    id = Column(Integer, primary_key=True)
    nombre = Column(String(100), nullable=False, unique=True)
    descripcion = Column(Text)

    equipos = relationship("Equipo", back_populates="tipo_equipo")


class Planta(Base):
    __tablename__ = "planta"

    id = Column(Integer, primary_key=True)
    nombre = Column(String(100), nullable=False)
    ubicacion = Column(String(200))

    equipos = relationship("Equipo", back_populates="planta")


class Equipo(Base):
    """El activo fisico monitoreado."""

    __tablename__ = "equipo"

    id = Column(Integer, primary_key=True)
    planta_id = Column(Integer, ForeignKey("planta.id"))
    tipo_equipo_id = Column(Integer, ForeignKey("tipo_equipo.id"), nullable=False)
    nombre = Column(String(150), nullable=False)
    estado = Column(String(30), default="normal")
    fecha_instalacion = Column(DateTime)
    # Atributos especificos por tipo de equipo (potencia_kw, caudal_m3h, etc.)
    atributos = Column(JSON)
    fecha_creacion = Column(DateTime, default=datetime.utcnow)

    planta = relationship("Planta", back_populates="equipos")
    tipo_equipo = relationship("TipoEquipo", back_populates="equipos")
    sensores = relationship("Sensor", back_populates="equipo")
    rodamientos = relationship("Rodamiento", back_populates="equipo")


class Rodamiento(Base):
    """
    Rodamiento fisico instalado en un equipo. Se identifica con un codigo
    (ej. "ROD-01") unico dentro de su equipo, no globalmente (D-038).

    La geometria (numero_elementos_rodantes, diametro_elemento_mm,
    diametro_paso_mm, angulo_contacto_grados) es opcional: se completa
    cuando se conoce la ficha tecnica del rodamiento. Sin ella no se
    pueden calcular BPFO/BPFI/BSF/FTF (ver conocimiento/
    normativa_motorguardian.yaml, seccion rodamientos) - el motor de
    diagnostico de rodamientos es un paso posterior a este modelo.
    """

    __tablename__ = "rodamiento"

    id = Column(Integer, primary_key=True)
    equipo_id = Column(Integer, ForeignKey("equipo.id"), nullable=False)
    codigo = Column(String(30), nullable=False)
    ubicacion = Column(String(150))
    modelo = Column(String(100))
    numero_elementos_rodantes = Column(Integer)
    diametro_elemento_mm = Column(Float)
    diametro_paso_mm = Column(Float)
    angulo_contacto_grados = Column(Float)
    fecha_creacion = Column(DateTime, default=datetime.utcnow)

    equipo = relationship("Equipo", back_populates="rodamientos")
    sensores = relationship("Sensor", back_populates="rodamiento")


class TipoSensor(Base):
    """
    Catalogo abierto de tipos de sensor (acelerometro triaxial, RTD, etc.).

    Se siembra desde conocimiento/catalogo_sensores.csv (herramientas/
    sembrar_catalogo_sensores.py). Los tipos creados manualmente por el
    usuario (no vienen del catalogo) quedan en familia "Personalizado".
    """

    __tablename__ = "tipo_sensor"

    id = Column(Integer, primary_key=True)
    nombre = Column(String(100), nullable=False, unique=True)
    nemonico = Column(String(20), unique=True)
    familia = Column(String(60))
    parametros_fisicos = Column(Text)
    # Lista de unidades que este tipo de sensor puede reportar (crece con
    # el tiempo: agregar una unidad nueva queda disponible retroactivamente
    # para todos los sensores existentes de este tipo).
    unidades_disponibles = Column(JSON)
    descripcion = Column(Text)

    sensores = relationship("Sensor", back_populates="tipo_sensor")


class Sensor(Base):
    """Instancia de un sensor instalado en un equipo."""

    __tablename__ = "sensor"

    id = Column(Integer, primary_key=True)
    equipo_id = Column(Integer, ForeignKey("equipo.id"), nullable=False)
    tipo_sensor_id = Column(Integer, ForeignKey("tipo_sensor.id"), nullable=False)
    # Codigo nemotecnico legible, ej. "VIBPZO-01". Unico dentro del
    # equipo, no globalmente: dos equipos distintos pueden tener cada
    # uno un VIBPZO-01 (D-038).
    codigo = Column(String(30))
    # Donde esta montado fisicamente dentro del equipo, ej. "lado acople".
    ubicacion = Column(String(150))
    # Si este sensor monitorea un rodamiento especifico del equipo.
    rodamiento_id = Column(Integer, ForeignKey("rodamiento.id"), nullable=True)
    estado = Column(String(30), default="activo")
    # Configuracion especifica del sensor (ejes, unidad, etc.)
    configuracion = Column(JSON)
    fecha_instalacion = Column(DateTime)

    equipo = relationship("Equipo", back_populates="sensores")
    tipo_sensor = relationship("TipoSensor", back_populates="sensores")
    rodamiento = relationship("Rodamiento", back_populates="sensores")
    mediciones = relationship("Medicion", back_populates="sensor")


class Medicion(Base):
    """
    Una sesion/lote de captura de datos crudos.

    No almacena las muestras individuales: son demasiado pesadas para
    una base de datos relacional. Guarda metadata y un puntero a donde
    vive el archivo real (local o S3).
    """

    __tablename__ = "medicion"

    id = Column(Integer, primary_key=True)
    sensor_id = Column(Integer, ForeignKey("sensor.id"), nullable=False)
    fecha_captura = Column(DateTime, default=datetime.utcnow)
    frecuencia_muestreo = Column(Integer)
    duracion_segundos = Column(Integer)
    # Unidad declarada por el operador al cargar el archivo (una de las
    # unidades_disponibles del tipo de sensor). Se registra tal cual,
    # sin verificar todavia que los valores del archivo correspondan
    # realmente a ella (D-040 - ver limitaciones en validacion_medicion.py).
    unidad = Column(String(30))
    # Velocidad de giro real al tomar la medicion (r/min), opcional (D-057).
    # Un motor de induccion con carga gira por debajo de su velocidad
    # nominal; si no se declara, el motor la estima desde el espectro.
    rpm_real = Column(Float)
    # Trazabilidad del importador (D-061): si el archivo original no tenia el
    # formato interno y se adapto, aqui queda el nombre del archivo subido y el
    # mapeo confirmado (columna -> eje, unidad, frecuencia). NULL = el archivo
    # ya venia en el formato interno.
    archivo_origen = Column(String(255))
    mapeo_importacion = Column(JSON)
    ruta_archivo_local = Column(String(500))
    clave_s3 = Column(String(500))
    estado_respaldo_s3 = Column(String(30), default="pendiente")

    sensor = relationship("Sensor", back_populates="mediciones")
    resultados = relationship("ResultadoAnalisis", back_populates="medicion")


class ResultadoAnalisis(Base):
    """Resultado ya calculado sobre una medicion (fft, curtosis, diagnostico, etc.)."""

    __tablename__ = "resultado_analisis"

    id = Column(Integer, primary_key=True)
    medicion_id = Column(Integer, ForeignKey("medicion.id"), nullable=False)
    tipo_analisis = Column(String(50), nullable=False)
    resultado = Column(JSON)
    fecha_calculo = Column(DateTime, default=datetime.utcnow)

    medicion = relationship("Medicion", back_populates="resultados")


class Usuario(Base):
    __tablename__ = "usuario"

    id = Column(Integer, primary_key=True)
    nombre = Column(String(150), nullable=False)
    email = Column(String(150), nullable=False, unique=True)
    password_hash = Column(String(255), nullable=False)
    rol = Column(String(30), default="visualizador")
    fecha_creacion = Column(DateTime, default=datetime.utcnow)


class Modelo(Base):
    """
    Registro de un modelo de aprendizaje (metadata unicamente).

    No entrena ni ejecuta inferencia todavia - eso queda para cuando
    se aborde la Fase 9 del roadmap (autoencoders), despriorizada por D-019.
    Esta tabla solo cataloga que modelos existen/estan planificados.
    """

    __tablename__ = "modelo"

    id = Column(Integer, primary_key=True)
    nombre = Column(String(150), nullable=False)
    tipo = Column(String(80), nullable=False)
    version = Column(String(30), default="0.1")
    estado = Column(String(30), default="planificado")
    descripcion = Column(Text)
    fecha_creacion = Column(DateTime, default=datetime.utcnow)


class Reporte(Base):
    """
    Reporte de diagnostico de un equipo en un momento dado: agrupa el
    resultado del motor de reglas (backend/procesamiento/diagnostico.py)
    sobre todos los sensores del equipo, y el PDF generado a partir de el.

    No envia correo ni Telegram todavia (ver Ideas futuras en PROYECTO.md).
    """

    __tablename__ = "reporte"

    id = Column(Integer, primary_key=True)
    equipo_id = Column(Integer, ForeignKey("equipo.id"), nullable=False)
    fecha_generacion = Column(DateTime, default=datetime.utcnow)
    # Hipotesis de falla, evidencias, confianza y limitaciones por sensor.
    resultado = Column(JSON)
    ruta_pdf = Column(String(500))

    equipo = relationship("Equipo")


class Notificacion(Base):
    """
    Registro de cada aviso de alerta enviado (o que fallo al enviarse) por
    un canal (correo, telegram) - sirve para no repetir el mismo aviso y
    para auditar que se aviso y cuando (D-054, ver PROYECTO.md).
    """

    __tablename__ = "notificacion"

    id = Column(Integer, primary_key=True)
    equipo_id = Column(Integer, ForeignKey("equipo.id"), nullable=False)
    medicion_id = Column(Integer, ForeignKey("medicion.id"))
    # Identifica el hallazgo (ej. "falla:rodamiento_pista_exterior:sensor1",
    # "iso_20816_3"), para detectar repeticiones.
    clave = Column(String(200), nullable=False, index=True)
    # Gravedad del hallazgo al avisar (1 = alta/zona C, 2 = muy alta/zona D).
    nivel = Column(Integer, nullable=False)
    canal = Column(String(20), nullable=False)
    # Correo o chat id al que se envio: el "ya avisado" se lleva por
    # destinatario, asi quien se agrega despues tambien recibe lo vigente.
    destinatario = Column(String(200))
    estado = Column(String(20), nullable=False)  # "enviada" | "fallida"
    detalle = Column(Text)
    fecha_envio = Column(DateTime, default=datetime.utcnow)

    equipo = relationship("Equipo")


class DestinatarioNotificacion(Base):
    """
    A quien se le envian las alertas (D-055): un correo o un chat de
    Telegram, administrable desde Configuracion -> Notificaciones. Lista
    global (no por equipo todavia). Se suman a los destinatarios "base" que
    pueda haber en .env (NOTIF_CORREO_DESTINO, TELEGRAM_CHAT_ID).
    """

    __tablename__ = "destinatario_notificacion"
    __table_args__ = (UniqueConstraint("canal", "direccion", name="uq_destinatario_canal_direccion"),)

    id = Column(Integer, primary_key=True)
    nombre = Column(String(150), nullable=False)
    canal = Column(String(20), nullable=False)  # "correo" | "telegram"
    # Correo electronico, o chat id numerico de Telegram (negativo en grupos).
    direccion = Column(String(200), nullable=False)
    activo = Column(Boolean, nullable=False, default=True)
    fecha_creacion = Column(DateTime, default=datetime.utcnow)


class PlantillaImportacion(Base):
    """
    Mapeo de importacion confirmado por una persona y guardado para reutilizarlo
    (D-061): como leer los archivos de un mismo origen (instrumento, exportador,
    investigador) y llevarlos al formato interno. "huella" identifica la forma
    del archivo (nombres de columna en orden + delimitador): al subir otro
    archivo con la misma huella, el sistema ofrece esta plantilla ya aplicada.
    """

    __tablename__ = "plantilla_importacion"

    id = Column(Integer, primary_key=True)
    nombre = Column(String(150), nullable=False, unique=True)
    huella = Column(String(64), nullable=False, index=True)
    # {"version", "formato", "columnas": {rol: nombre_de_columna}, "unidad", "frecuencia_muestreo", ...}
    mapeo = Column(JSON, nullable=False)
    fecha_creacion = Column(DateTime, default=datetime.utcnow)


class LineaBase(Base):
    """
    Referencia de un sensor: valores medidos en una condicion SANA
    confirmada por el usuario, contra los que se compara cada medicion
    posterior (D-056, ver PROYECTO.md). Sin ella, el motor de reglas solo
    sabe si "hay un pico" en 1x/2x/3x, no si es anormal para esa maquina.

    No guarda la senal: guarda los valores resumidos (amplitud en 1x, 2x y
    3x por eje) y apunta a la medicion de origen. Un sensor tiene a lo mas
    una linea base activa; marcar otra desactiva la anterior (queda como
    historial). Si se elimina el sensor o la medicion, se elimina la fila.

    Puede resumir varias mediciones sanas (criterios_proyecto.
    linea_base_varios_registros): medicion_id apunta a la mas reciente y las
    demas (con n_registros, la regla y los avisos) quedan en valores, sin
    cambiar el formato de "amplitudes" - no hace falta migrar la tabla, y una
    fila sin esos campos es una linea base de un solo registro.
    """

    __tablename__ = "linea_base"

    id = Column(Integer, primary_key=True)
    sensor_id = Column(Integer, ForeignKey("sensor.id", ondelete="CASCADE"), nullable=False, index=True)
    medicion_id = Column(Integer, ForeignKey("medicion.id", ondelete="CASCADE"), nullable=False)
    # {"rpm", "tolerancia_pct", "amplitudes": {"1x": {"x","y","z"}, "2x": ..., "3x": ...}}
    valores = Column(JSON, nullable=False)
    activa = Column(Boolean, nullable=False, default=True)
    fecha_creacion = Column(DateTime, default=datetime.utcnow)

    sensor = relationship("Sensor")
    medicion = relationship("Medicion")
