# app/core/security.py

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any, Union
from passlib.context import CryptContext
from jose import jwt
from app.core.config import settings

# Contexto para Bcrypt (para usuarios del sistema financiero, más seguro)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ✅ NUEVO: Función para verificar contraseñas en formato MD5
def verify_md5_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifica una contraseña en texto plano contra un hash MD5.
    """
    # El hash MD5 siempre es hexadecimal de 32 caracteres.
    if not plain_password or not hashed_password or len(hashed_password) != 32:
        return False
    
    # Crea el hash MD5 de la contraseña proporcionada y lo compara
    password_hash = hashlib.md5(plain_password.encode('utf-8')).hexdigest()
    return password_hash == hashed_password.lower()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifica una contraseña en texto plano contra un hash bcrypt.
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """
    Hashea una contraseña usando bcrypt.
    """
    return pwd_context.hash(password)


def create_access_token(
    subject: Union[str, Any], expires_delta: timedelta = None
) -> str:
    """
    Crea un nuevo token de acceso JWT.
    """
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    to_encode = {"exp": expire, "sub": str(subject)}
    encoded_jwt = jwt.encode(
        to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )
    return encoded_jwt
