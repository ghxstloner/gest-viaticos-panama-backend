# app/core/security.py

import hashlib
import bcrypt
from datetime import datetime, timedelta, timezone
from typing import Any, Union, Dict
from jose import jwt, JWTError
from app.core.config import settings

# ✅ NUEVO: Función para verificar contraseñas en formato MD5
def verify_md5_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifica una contraseña en texto plano contra un hash MD5.
    """
    if not plain_password or not hashed_password or len(hashed_password) != 32:
        return False
    
    password_hash = hashlib.md5(plain_password.encode('utf-8')).hexdigest()
    return password_hash == hashed_password.lower()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifica una contraseña en texto plano contra un hash bcrypt usando bcrypt directamente.
    """
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def get_password_hash(password: str) -> str:
    """
    Hashea una contraseña usando bcrypt directamente.
    """
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def create_access_token(
    subject: Union[str, Any] = None, 
    data: Dict[str, Any] = None,
    expires_delta: timedelta = None
) -> str:
    """
    Crea un nuevo token de acceso JWT.
    Acepta tanto subject como data para compatibilidad.
    """
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    
    # Si se pasa data (diccionario), usarlo directamente
    if data:
        to_encode = data.copy()
        to_encode.update({"exp": expire})
    else:
        # Si se pasa subject (string), usar el formato anterior
        to_encode = {"exp": expire, "sub": str(subject)}
    
    encoded_jwt = jwt.encode(
        to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )
    return encoded_jwt

# ✅ FUNCIÓN FALTANTE que causaba el error de importación
def decode_access_token(token: str) -> Dict[str, Any]:
    """
    Decodifica y valida un token JWT.
    """
    try:
        payload = jwt.decode(
            token, 
            settings.SECRET_KEY, 
            algorithms=[settings.ALGORITHM]
        )
        return payload
    except JWTError:
        raise ValueError("Token inválido o expirado")

def get_md5_hash(password: str) -> str:
    """
    Genera hash MD5 de contraseña (para empleados).
    """
    return hashlib.md5(password.encode('utf-8')).hexdigest()