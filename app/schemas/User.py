from pydantic import BaseModel, ConfigDict, computed_field
from typing import Optional, List, Dict
from datetime import datetime

class PermisoBase(BaseModel):
    codigo: str
    nombre: str
    descripcion: Optional[str] = None
    modulo: str
    accion: str
    es_permiso_empleado: Optional[bool] = False

class Permiso(PermisoBase):
    model_config = ConfigDict(from_attributes=True)
    
    id_permiso: int

class RolBase(BaseModel):
    nombre_rol: str
    descripcion: Optional[str] = None

class RolCreate(RolBase):
    pass

class RolUpdate(BaseModel):
    nombre_rol: Optional[str] = None
    descripcion: Optional[str] = None

class Rol(RolBase):
    model_config = ConfigDict(from_attributes=True)
    
    id_rol: int
    created_at: datetime
    updated_at: datetime
    permisos: List[Permiso] = []
    
    @computed_field
    @property
    def permisos_estructurados(self) -> Dict[str, Dict[str, bool]]:
        """Estructura los permisos en formato módulo -> acción -> bool"""
        estructura = {}
        for permiso in self.permisos:
            if permiso.modulo not in estructura:
                estructura[permiso.modulo] = {}
            estructura[permiso.modulo][permiso.accion] = True
        return estructura

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
    
    @computed_field
    @property
    def permisos_usuario(self) -> Dict[str, Dict[str, bool]]:
        """Permisos del usuario basados en su rol"""
        return self.rol.permisos_estructurados if self.rol else {}

class UsuarioInDB(Usuario):
    password_hash: str