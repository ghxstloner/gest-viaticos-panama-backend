import hashlib
import bcrypt
from datetime import datetime, timedelta, timezone
from typing import Any, Union
from jose import jwt
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