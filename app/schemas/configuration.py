# app/schemas/configuration.py

from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, Dict, Any, Literal
from datetime import datetime

class ConfiguracionGeneralBase(BaseModel):
    nombre_empresa: str
    ruc: str
    direccion: Optional[str] = None
    telefono: Optional[str] = None
    email_empresa: Optional[str] = None
    logo_empresa: Optional[str] = None  # Ruta del archivo
    smtp_servidor: str
    smtp_puerto: int = 587
    smtp_usuario: str
    smtp_password: str
    smtp_seguridad: Literal['none', 'tls', 'ssl'] = "tls"
    email_remitente: str
    nombre_remitente: str
    moneda_default: Optional[str] = "USD"
    idioma_default: Optional[str] = "es"
    zona_horaria: Optional[str] = "America/Panama"
    usuario_creacion: Optional[int] = None
    usuario_actualizacion: Optional[int] = None

class ConfiguracionGeneralCreate(ConfiguracionGeneralBase):
    pass

class ConfiguracionGeneralUpdate(BaseModel):
    nombre_empresa: Optional[str] = None
    ruc: Optional[str] = None
    direccion: Optional[str] = None
    telefono: Optional[str] = None
    email_empresa: Optional[str] = None
    logo_empresa: Optional[str] = None
    smtp_servidor: Optional[str] = None
    smtp_puerto: Optional[int] = None
    smtp_usuario: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_seguridad: Optional[Literal['none', 'tls', 'ssl']] = None
    email_remitente: Optional[str] = None
    nombre_remitente: Optional[str] = None
    moneda_default: Optional[str] = None
    idioma_default: Optional[str] = None
    zona_horaria: Optional[str] = None
    usuario_creacion: Optional[int] = None
    usuario_actualizacion: Optional[int] = None

class ConfiguracionGeneral(ConfiguracionGeneralBase):
    model_config = ConfigDict(from_attributes=True)
    
    id_configuracion_general: int
    created_at: datetime
    updated_at: datetime

# Configuración Sistema
class ConfiguracionSistemaBase(BaseModel):
    clave: str
    valor: str
    tipo_dato: Literal['STRING', 'NUMBER', 'BOOLEAN', 'JSON', 'TIME'] = "STRING"
    descripcion: Optional[str] = None
    es_modificable: bool = True

class ConfiguracionSistemaCreate(ConfiguracionSistemaBase):
    pass

class ConfiguracionSistemaUpdate(BaseModel):
    clave: Optional[str] = None
    valor: Optional[str] = None
    tipo_dato: Optional[Literal['STRING', 'NUMBER', 'BOOLEAN', 'JSON', 'TIME']] = None
    descripcion: Optional[str] = None
    es_modificable: Optional[bool] = None

class ConfiguracionSistema(ConfiguracionSistemaBase):
    model_config = ConfigDict(from_attributes=True)
    
    id_configuracion: int
    created_at: datetime
    updated_at: datetime

# === SCHEMAS PARA NOTIFICACIONES ===

class ConfiguracionNotificacionBase(BaseModel):
    tipo_notificacion: str
    titulo: str
    descripcion: Optional[str] = None
    email_habilitado: bool = True
    sistema_habilitado: bool = True
    sms_habilitado: bool = False
    frecuencia: Literal['inmediato', 'diario', 'semanal', 'nunca'] = 'inmediato'
    prioridad_minima: Literal['todas', 'normal', 'alta', 'critica'] = 'todas'
    template_email: Optional[str] = None
    es_modificable: bool = True

class ConfiguracionNotificacionCreate(ConfiguracionNotificacionBase):
    pass

class ConfiguracionNotificacionUpdate(BaseModel):
    tipo_notificacion: Optional[str] = None
    titulo: Optional[str] = None
    descripcion: Optional[str] = None
    email_habilitado: Optional[bool] = None
    sistema_habilitado: Optional[bool] = None
    sms_habilitado: Optional[bool] = None
    frecuencia: Optional[Literal['inmediato', 'diario', 'semanal', 'nunca']] = None
    prioridad_minima: Optional[Literal['todas', 'normal', 'alta', 'critica']] = None
    template_email: Optional[str] = None
    es_modificable: Optional[bool] = None

class ConfiguracionNotificacion(ConfiguracionNotificacionBase):
    model_config = ConfigDict(from_attributes=True)
    
    id_configuracion_notificacion: int
    created_at: datetime
    updated_at: datetime

# === SCHEMAS PARA PERSONAL RRHH ===

class PersonalRRHH(BaseModel):
    personal_id: int
    apenom: str
    ficha: str
    
    
class PersonalRRHHSearch(BaseModel):
    query: str = Field(min_length=2, description="Mínimo 2 caracteres para buscar")