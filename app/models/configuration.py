# app/models/configuration.py

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, JSON
from sqlalchemy.sql import func
from .base import Base, TimestampMixin
from .enums import TipoDato, SmtpSecurity

class ConfiguracionGeneral(Base, TimestampMixin):
    __tablename__ = "configuraciones_general"
    __table_args__ = {'extend_existing': True}

    id_configuracion_general = Column(Integer, primary_key=True, index=True)
    nombre_empresa = Column(String(255), nullable=False)
    ruc = Column(String(50), nullable=False)
    direccion = Column(Text, nullable=True)
    telefono = Column(String(50), nullable=True)
    email_empresa = Column(String(255), nullable=True)
    logo_empresa = Column(String(500), nullable=True)  # Ruta del archivo subido
    smtp_servidor = Column(String(255), nullable=False)
    smtp_puerto = Column(Integer, default=587, nullable=False)
    smtp_usuario = Column(String(255), nullable=False)
    smtp_password = Column(String(255), nullable=False)
    smtp_seguridad = Column(String(10), default='tls')
    email_remitente = Column(String(255), nullable=False)
    nombre_remitente = Column(String(255), nullable=False)
    moneda_default = Column(String(10), default='USD')
    idioma_default = Column(String(10), default='es')
    zona_horaria = Column(String(100), default='America/Panama')
    usuario_creacion = Column(Integer, nullable=True)
    usuario_actualizacion = Column(Integer, nullable=True)


class ConfiguracionSistema(Base, TimestampMixin):
    __tablename__ = "configuraciones_sistema"
    __table_args__ = {'extend_existing': True}

    id_configuracion = Column(Integer, primary_key=True, index=True)
    clave = Column(String(100), unique=True, nullable=False)
    valor = Column(Text, nullable=False)
    tipo_dato = Column(String(20), default=TipoDato.STRING)
    descripcion = Column(Text, nullable=True)
    es_modificable = Column(Boolean, default=True)


class ConfiguracionNotificacion(Base, TimestampMixin):
    __tablename__ = "configuraciones_notificaciones"
    __table_args__ = {'extend_existing': True}

    id_configuracion_notificacion = Column(Integer, primary_key=True, index=True)
    tipo_notificacion = Column(String(100), nullable=False)  # nueva_solicitud, solicitud_aprobada, etc.
    titulo = Column(String(255), nullable=False)
    descripcion = Column(Text, nullable=True)
    email_habilitado = Column(Boolean, default=True)
    sistema_habilitado = Column(Boolean, default=True)
    sms_habilitado = Column(Boolean, default=False)
    frecuencia = Column(String(50), default='inmediato')  # inmediato, diario, semanal, nunca
    prioridad_minima = Column(String(20), default='todas')  # todas, normal, alta, critica
    template_email = Column(Text, nullable=True)
    es_modificable = Column(Boolean, default=True)