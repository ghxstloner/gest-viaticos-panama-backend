# app/api/deps.py

from typing import Generator
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt, JWTError
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.core.config import settings
# ✅ CORRECCIÓN: usar user en minúscula
from app.models.user import Usuario
from app.core.database import get_db_financiero, get_db_rrhh

# Esquema de seguridad para los endpoints
security = HTTPBearer()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login/financiero")

def get_current_user(
    db: Session = Depends(get_db_financiero),
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> Usuario:
    """
    Obtiene el usuario actual (del sistema financiero) a partir del token JWT.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            credentials.credentials, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        username: str = payload.get("sub")
        if username is None or not username.startswith("user:"):
             raise credentials_exception
        
        user_id = int(username.split(":")[1])
        
    except (JWTError, IndexError, ValueError):
        raise credentials_exception
        
    user = db.get(Usuario, user_id)
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
        if subject is None or not subject.startswith("employee:"):
            raise credentials_exception
            
        cedula = subject.split(":")[1]
        
    except (JWTError, IndexError):
        raise credentials_exception
    
    query = text("SELECT personal_id, cedula, apenom, email FROM nompersonal WHERE cedula = :cedula AND estado != 'De Baja'")
    result = db.execute(query, {"cedula": cedula})
    employee = result.fetchone()

    if employee is None:
        raise credentials_exception
        
    return dict(employee._mapping)