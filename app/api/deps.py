# app/api/deps.py

from typing import Generator, List, Union, Optional
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
    credentials: HTTPAuthorizationCredentials = Depends(security)  # ← CAMBIO AQUÍ
) -> Usuario:
    """
    Obtiene el usuario actual (del sistema financiero) a partir del token JWT.
    """
    print("🚨 GET_CURRENT_USER EJECUTÁNDOSE")
    
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudieron validar las credenciales",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    if not credentials:  # ← AGREGAR validación
        raise credentials_exception
    
    try:
        # ← CAMBIO: usar credentials.credentials
        payload = jwt.decode(
            credentials.credentials,  # ← CAMBIO AQUÍ
            settings.SECRET_KEY, 
            algorithms=[settings.ALGORITHM]
        )
        
        username: str = payload.get("sub")
        token_type: str = payload.get("type", "")
        
        print(f"🚨 Username: {username}, Type: {token_type}")
        
        if username is None or token_type != "financiero":
            raise credentials_exception
            
    except JWTError as e:  # ← CAMBIO: capturar JWTError
        print(f"🚨 JWTError: {e}")
        raise credentials_exception
    except Exception as e:
        print(f"🚨 Error: {e}")
        raise credentials_exception
        
    user = db.query(Usuario).filter(Usuario.login_username == username).first()
    
    if user is None:
        raise credentials_exception
        
    print(f"🚨 ÉXITO: {user.login_username} - {user.rol.nombre_rol}")
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
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db_financiero: Session = Depends(get_db_financiero),
    db_rrhh: Session = Depends(get_db_rrhh)
) -> Union[Usuario, dict]:
    """
    Obtiene el usuario actual, ya sea empleado o financiero.
    VERSIÓN CORREGIDA que maneja ambos tipos de tokens.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudieron validar las credenciales",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    if not credentials:
        raise credentials_exception
    
    try:
        # Decodificar el token JWT directamente
        payload = jwt.decode(
            credentials.credentials, 
            settings.SECRET_KEY, 
            algorithms=[settings.ALGORITHM]
        )
        
        token_type: str = payload.get("type", "")
        print(f"DEBUG - Token type: {token_type}")
        print(f"DEBUG - Payload: {payload}")
        
        if token_type == "financiero":
            # Usuario del sistema financiero
            username: str = payload.get("sub")
            if username is None:
                raise credentials_exception
            user = db_financiero.query(Usuario).filter(Usuario.login_username == username).first()
            if user is None:
                raise credentials_exception
            return user
            
        elif token_type == "employee":
            # Empleado - extraer datos directamente del token
            personal_id = payload.get("personal_id")
            cedula = payload.get("cedula")
            nombre = payload.get("nombre")
            is_department_head = payload.get("is_department_head", False)
            managed_departments = payload.get("managed_departments", [])
            id_rol = payload.get("id_rol")
            permisos_usuario = payload.get("permisos_usuario", {})
            
            if not personal_id or not cedula:
                raise credentials_exception
            
            # Buscar el nombre del rol en la base de datos
            role_query = text("SELECT nombre_rol FROM roles WHERE id_rol = :id_rol")
            role_result = db_financiero.execute(role_query, {"id_rol": id_rol})
            role_row = role_result.fetchone()
            role_name = role_row.nombre_rol if role_row else "Empleado"
            
            employee_data = {
                "personal_id": personal_id,
                "cedula": cedula,
                "apenom": nombre,
                "is_department_head": is_department_head,
                "managed_departments": managed_departments,
                "id_rol": id_rol,
                "role_name": role_name,
                "user_type": "employee",
                "permisos_usuario": permisos_usuario
            }
            
            print(f"DEBUG - Employee data: {employee_data}")
            return employee_data
        else:
            print(f"DEBUG - Token type no válido: {token_type}")
            raise credentials_exception
            
    except JWTError as e:
        print(f"DEBUG - JWT Error: {e}")
        raise credentials_exception
    except Exception as e:
        print(f"DEBUG - Error general: {e}")
        raise credentials_exception
    
def get_current_employee_with_role(
    db_financiero: Session = Depends(get_db_financiero),
    db_rrhh: Session = Depends(get_db_rrhh),
    credentials: HTTPAuthorizationCredentials = Depends(security)
    ) -> dict:
    """
    Obtiene el empleado actual con información de rol (jefe o empleado regular)
    VERSIÓN CORREGIDA que extrae datos del token directamente.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudieron validar las credenciales del empleado",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not credentials:
        raise credentials_exception

    try:
        payload = jwt.decode(
            credentials.credentials, 
            settings.SECRET_KEY, 
            algorithms=[settings.ALGORITHM]
        )
        
        token_type: str = payload.get("type", "")
        
        if token_type != "employee":
            raise credentials_exception
        
        # Extraer datos directamente del token (como en tu ejemplo)
        personal_id = payload.get("personal_id")
        cedula = payload.get("cedula")
        nombre = payload.get("nombre")
        is_department_head = payload.get("is_department_head", False)
        managed_departments = payload.get("managed_departments", [])
        id_rol = payload.get("id_rol")
        permisos_usuario = payload.get("permisos_usuario", {})
        
        if not personal_id or not cedula:
            raise credentials_exception
        
        # Buscar el nombre del rol en la base de datos
        role_query = text("SELECT nombre_rol FROM roles WHERE id_rol = :id_rol")
        role_result = db_financiero.execute(role_query, {"id_rol": id_rol})
        role_row = role_result.fetchone()
        role_name = role_row.nombre_rol if role_row else "Empleado"
        
        employee_data = {
            "personal_id": personal_id,
            "cedula": cedula,
            "apenom": nombre,
            "is_department_head": is_department_head,
            "managed_departments": managed_departments,
            "id_rol": id_rol,
            "role_name": role_name,
            "user_type": "employee",
            "permisos_usuario": permisos_usuario
        }
        
        return employee_data
        
    except (JWTError, IndexError) as e:
        print(f"DEBUG - Error en get_current_employee_with_role: {e}")
        raise credentials_exception

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

def get_current_user_or_employee(
    current_user: Optional[Usuario] = Depends(get_current_user),
    current_employee: Optional[dict] = Depends(get_current_employee)
) -> Union[Usuario, dict]:
    """
    Dependency que retorna el usuario actual, ya sea financiero o empleado.
    Útil para endpoints que pueden ser accedidos por ambos tipos de usuarios.
    """
    if current_user:
        return current_user
    elif current_employee:
        return current_employee
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no autenticado"
        )

def require_financial_user(
    current_user: Usuario = Depends(get_current_user)
) -> Usuario:
    """
    Dependency que requiere específicamente un usuario financiero.
    """
    financial_roles = [
        "Analista Tesorería", "Analista Presupuesto", "Analista Contabilidad",
        "Director Finanzas", "Fiscalizador CGR", "Custodio Caja Menuda",
        "Administrador Sistema"
    ]
    
    if current_user.rol.nombre_rol not in financial_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requiere un usuario con rol financiero"
        )
    
    return current_user

def require_department_head(
    current_employee: dict = Depends(get_current_employee_with_role)
) -> dict:
    """
    Dependency que requiere específicamente un jefe de departamento.
    """
    if not current_employee.get("is_department_head"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requiere ser jefe de departamento"
        )
    
    return current_employee