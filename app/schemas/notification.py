from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class NotificacionBase(BaseModel):
    titulo: str = Field(..., max_length=100)
    descripcion: str = Field(..., max_length=200)
    personal_id: int
    id_mision: Optional[int] = None
    visto: bool = False

class NotificacionCreate(NotificacionBase):
    pass

class NotificacionUpdate(BaseModel):
    titulo: Optional[str] = None
    descripcion: Optional[str] = None
    personal_id: Optional[int] = None
    id_mision: Optional[int] = None
    visto: Optional[bool] = None

class NotificacionVistoUpdate(BaseModel):
    visto: bool

class Notificacion(NotificacionBase):
    model_config = ConfigDict(from_attributes=True)
    
    notificacion_id: int
    created_at: datetime
    updated_at: datetime

class NotificacionResponse(BaseModel):
    """Respuesta para endpoints que retornan notificaciones con contador"""
    notifications: List[Notificacion]
    total_count: int
    skip: int
    limit: int

class NotificacionCountResponse(BaseModel):
    """Respuesta para endpoints que retornan solo el contador"""
    personal_id: int
    count: int
    unread_only: bool

class NotificacionFilteredResponse(BaseModel):
    """Respuesta para endpoints que retornan notificaciones con filtros"""
    notifications: List[Notificacion]
    total_count: int
    skip: int
    limit: int
    filters: Dict[str, Any]
