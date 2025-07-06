from typing import Dict, Optional, Any, List
from pydantic import BaseModel, EmailStr
from datetime import datetime


class PermissionBase(BaseModel):
    id_permiso: int
    codigo: str
    nombre: str


class RoleBase(BaseModel):
    id_rol: int
    nombre_rol: str
    descripcion: Optional[str] = None
    permisos: List[PermissionBase]


class UserBase(BaseModel):
    login_username: str
    personal_id_rrhh: Optional[int] = None
    email: Optional[EmailStr] = None
    nombre_completo: Optional[str] = None


class UserCreate(UserBase):
    password: str
    id_rol: int
    personal_id_rrhh: Optional[int] = None


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    nombre_completo: Optional[str] = None
    password: Optional[str] = None
    id_rol: Optional[int] = None
    esta_activo: Optional[bool] = None


class UserInDB(UserBase):
    id: int
    esta_activo: bool
    id_rol: Optional[int] = None
    personal_id_rrhh: Optional[int] = None

    class Config:
        from_attributes = True


class UserRegister(BaseModel):
    username: str
    password: str
    personal_id: Optional[int] = None
    email: Optional[EmailStr] = None
    nombre_completo: Optional[str] = None


class UserResponse(UserBase):
    id_usuario: int
    rol: RoleBase
    is_active: bool
    ultimo_acceso: Optional[datetime] = None

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse


class TokenData(BaseModel):
    username: Optional[str] = None
    permissions: Optional[Dict[str, Dict[str, bool]]] = None


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    user: Dict[str, Any]