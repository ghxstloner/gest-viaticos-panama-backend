from pydantic import BaseModel, ConfigDict
from typing import Optional, Dict, Any
from datetime import datetime


class RolBase(BaseModel):
    nombre_rol: str
    descripcion: Optional[str] = None
    permisos_json: Optional[Dict[str, Any]] = None


class RolCreate(RolBase):
    pass


class RolUpdate(BaseModel):
    nombre_rol: Optional[str] = None
    descripcion: Optional[str] = None
    permisos_json: Optional[Dict[str, Any]] = None


class Rol(RolBase):
    model_config = ConfigDict(from_attributes=True)
    
    id_rol: int
    created_at: datetime
    updated_at: datetime


class UsuarioBase(BaseModel):
    personal_id_rrhh: Optional[int] = None
    login_username: str
    id_rol: int
    is_active: bool = True


class UsuarioCreate(UsuarioBase):
    password: str


class UsuarioUpdate(BaseModel):
    personal_id_rrhh: Optional[int] = None
    login_username: Optional[str] = None
    password: Optional[str] = None
    id_rol: Optional[int] = None
    is_active: Optional[bool] = None


class Usuario(UsuarioBase):
    model_config = ConfigDict(from_attributes=True)
    
    id_usuario: int
    ultimo_acceso: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    rol: Rol


class UsuarioInDB(Usuario):
    password_hash: str