from pydantic import BaseModel
from typing import Optional


class DepartmentBase(BaseModel):
    nombre: str
    ruta_sello: Optional[str] = None


class DepartmentCreate(BaseModel):
    nombre: str
    # NOTA: ruta_sello no se puede enviar al crear, se asigna automáticamente


class DepartmentUpdate(BaseModel):
    nombre: Optional[str] = None
    # NOTA: ruta_sello no se puede actualizar desde aquí, se maneja por separado


class Department(DepartmentBase):
    id_departamento: int
    
    class Config:
        from_attributes = True


class DepartmentWithCount(Department):
    usuarios_count: int
