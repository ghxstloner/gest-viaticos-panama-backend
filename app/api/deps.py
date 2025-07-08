# app/api/deps.py

from typing import Generator, List, Union
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt, JWTError
from sqlalchemy.orm import Session
from sqlalchemy import text
from functools import wraps

from app.core.config import settings
from app.models.user import Usuario
from app.core.database import get_db_financiero, get_db_rrhh
from app.core.security import decode_access_token

# Esquema de seguridad para los endpoints
security = HTTPBearer()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")

def get_current_user(
    db: Session = Depends(get_db_financiero),
    token: str = Depends(oauth2_scheme)
) -> Usuario:
    """
    Obtiene el usuario actual (del sistema financiero) a partir del token JWT.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudieron validar las credenciales",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = decode_access_token(token)
        username: str = payload.get("sub")
        token_type: str = payload.get("type", "")
        
        if username is None or token_type != "financiero":
            raise credentials_exception
            
    except ValueError:
        raise credentials_exception
        
    user = db.query(Usuario).filter(Usuario.login_username == username).first()
    if user is None:
        raise credentials_exception
    return user

def get_current_employee(
    db: Session = Depends(get_db_rrhh),
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """
    Obtiene el empleado actual (de RRHH) a partir del token JWT.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudieron validar las credenciales del empleado",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(
            credentials.credentials, 
            settings.SECRET_KEY, 
            algorithms=[settings.ALGORITHM]
        )
        subject: str = payload.get("sub")
        token_type: str = payload.get("type", "")
        
        if subject is None or not subject.startswith("employee:") or token_type != "employee":
            raise credentials_exception
            
        cedula = subject.split(":")[1]
        
    except (JWTError, IndexError):
        raise credentials_exception
    
    # Usar esquema completo para consulta cross-database
    query = text("SELECT personal_id, cedula, apenom, email FROM nompersonal WHERE cedula = :cedula AND estado != 'De Baja'")
    result = db.execute(query, {"cedula": cedula})
    employee = result.fetchone()

    if employee is None:
        raise credentials_exception
        
    return dict(employee._mapping)

def get_current_user_universal(
    token: str = Depends(oauth2_scheme),
    db_financiero: Session = Depends(get_db_financiero),
    db_rrhh: Session = Depends(get_db_rrhh)
) -> Union[Usuario, dict]:
    """
    Obtiene el usuario actual, ya sea empleado o financiero
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudieron validar las credenciales",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = decode_access_token(token)
        token_type: str = payload.get("type", "")
        
        if token_type == "financiero":
            username: str = payload.get("sub")
            if username is None:
                raise credentials_exception
            user = db_financiero.query(Usuario).filter(Usuario.login_username == username).first()
            if user is None:
                raise credentials_exception
            return user
            
        elif token_type == "employee":
            subject: str = payload.get("sub")
            if subject is None or not subject.startswith("employee:"):
                raise credentials_exception
            cedula = subject.split(":")[1]
            
            query = text("SELECT personal_id, cedula, apenom, email FROM nompersonal WHERE cedula = :cedula AND estado != 'De Baja'")
            result = db_rrhh.execute(query, {"cedula": cedula})
            employee = result.fetchone()
            
            if employee is None:
                raise credentials_exception
            return dict(employee._mapping)
        else:
            raise credentials_exception
            
    except ValueError:
        raise credentials_exception
    
def get_current_employee_with_role(
    db_financiero: Session = Depends(get_db_financiero),
    db_rrhh: Session = Depends(get_db_rrhh),
    credentials: HTTPAuthorizationCredentials = Depends(security)
    ) -> dict:
    """
    Obtiene el empleado actual con información de rol (jefe o empleado regular)
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudieron validar las credenciales del empleado",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            credentials.credentials, 
            settings.SECRET_KEY, 
            algorithms=[settings.ALGORITHM]
        )
        subject: str = payload.get("sub")
        token_type: str = payload.get("type", "")
        
        if subject is None or not subject.startswith("employee:") or token_type != "employee":
            raise credentials_exception
            
        cedula = subject.split(":")[1]
        
    except (JWTError, IndexError):
        raise credentials_exception

    # Obtener datos del empleado
    query = text("SELECT personal_id, cedula, apenom, email, IdDepartamento FROM nompersonal WHERE cedula = :cedula AND estado != 'De Baja'")
    result = db_rrhh.execute(query, {"cedula": cedula})
    employee = result.fetchone()

    if employee is None:
        raise credentials_exception

    employee_data = dict(employee._mapping)

    # Verificar si es jefe de departamento
    jefe_query = text("SELECT COUNT(*) as count FROM departamento WHERE IdJefe = :cedula")
    jefe_result = db_rrhh.execute(jefe_query, {"cedula": cedula})
    is_department_head = jefe_result.fetchone().count > 0

    # Obtener departamentos gestionados si es jefe
    managed_departments = []
    if is_department_head:
        dept_query = text("SELECT IdDepartamento, Descripcion FROM departamento WHERE IdJefe = :cedula")
        dept_result = db_rrhh.execute(dept_query, {"cedula": cedula})
        managed_departments = [{"id": row.IdDepartamento, "descripcion": row.Descripcion} for row in dept_result.fetchall()]

    employee_data.update({
        "is_department_head": is_department_head,
        "managed_departments": managed_departments,
        "role_id": 2 if is_department_head else 1,
        "role_name": "Jefe Inmediato" if is_department_head else "Solicitante"
    })
        
    return employee_data

def check_permissions(required_permissions: List[str]):
    """
    Decorator para verificar permisos específicos
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, current_user: Usuario = Depends(get_current_user), **kwargs):
            for permission in required_permissions:
                if not current_user.has_permission(permission):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"No tienes permiso para realizar esta acción: {permission}"
                    )
            return await func(*args, current_user=current_user, **kwargs)
        return wrapper
    return decorator

def require_role(allowed_roles: List[int]):
    """
    Decorator para verificar roles específicos
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, current_user: Usuario = Depends(get_current_user), **kwargs):
            if current_user.id_rol not in allowed_roles:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="No tienes el rol necesario para realizar esta acción"
                )
            return await func(*args, current_user=current_user, **kwargs)
        return wrapper
    return decorator