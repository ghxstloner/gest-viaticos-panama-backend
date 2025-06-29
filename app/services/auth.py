# app/services/auth.py

from sqlalchemy.orm import Session
from typing import Optional

from app.core.security import verify_password, create_access_token
# ✅ CORRECCIÓN: usar user en minúscula
from app.models.user import Usuario
from app.schemas.auth import LoginResponse

class AuthService:
    def __init__(self, db: Session):
        self.db = db

    def authenticate_user(self, username: str, password: str) -> Optional[Usuario]:
        """
        Autentica a un usuario del sistema financiero.
        """
        user = self.db.query(Usuario).filter(Usuario.login_username == username).first()
        
        if not user or not verify_password(password, user.password_hash):
            return None
            
        return user

    def login(self, user: Usuario) -> LoginResponse:
        """
        Genera una respuesta de login con un token de acceso.
        """
        token_subject = f"user:{user.id_usuario}"
        access_token = create_access_token(subject=token_subject)
        
        role_name = "N/A"
        if user.rol:
            role_name = user.rol.nombre_rol

        return LoginResponse(
            access_token=access_token,
            user={
                "id": user.id_usuario,
                "username": user.login_username,
                "email": "N/A",
                "role": role_name
            }
        )