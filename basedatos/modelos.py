"""
Modelos ORM de MotorGuardian.

Responsabilidad:
    Definir la estructura de las tablas de la base de datos: equipos,
    sensores, mediciones, resultados de analisis y usuarios.
"""

from datetime import datetime

from sqlalchemy import Column, Integer, Float, String, ForeignKey, DateTime, JSON, Text
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
