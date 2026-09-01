"""
Modelos ORM de MotorGuardian.

Responsabilidad:
    Definir la estructura de las tablas de la base de datos: equipos,
    sensores, mediciones, resultados de analisis y usuarios.
"""

from datetime import datetime

from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, JSON, Text
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


class TipoSensor(Base):
    """Catalogo abierto de tipos de sensor (acelerometro triaxial, temperatura, etc.)."""

    __tablename__ = "tipo_sensor"

    id = Column(Integer, primary_key=True)
    nombre = Column(String(100), nullable=False, unique=True)
    unidad_medida_default = Column(String(30))
    descripcion = Column(Text)

    sensores = relationship("Sensor", back_populates="tipo_sensor")


class Sensor(Base):
    """Instancia de un sensor instalado en un equipo."""

    __tablename__ = "sensor"

    id = Column(Integer, primary_key=True)
    equipo_id = Column(Integer, ForeignKey("equipo.id"), nullable=False)
    tipo_sensor_id = Column(Integer, ForeignKey("tipo_sensor.id"), nullable=False)
    estado = Column(String(30), default="activo")
    # Configuracion especifica del sensor (ejes, unidad, etc.)
    configuracion = Column(JSON)
    fecha_instalacion = Column(DateTime)

    equipo = relationship("Equipo", back_populates="sensores")
    tipo_sensor = relationship("TipoSensor", back_populates="sensores")
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
