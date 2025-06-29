# app/services/auth.py

from sqlalchemy.orm import Session
from typing import Optional

from app.core.security import verify_password, create_access_token
# ✅ CORRECCIÓN: Se importa el módulo completo y luego se usa con el prefijo.
# Esto evita problemas de importación y es más claro.
from app.models import User as UserModel
from app.schemas.auth import LoginResponse

class AuthService:
    def __init__(self, db: Session):
        self.db = db

    def authenticate_user(self, username: str, password: str) -> Optional[UserModel.User]:
        """
        Autentica a un usuario del sistema financiero.
        """
        # Se busca al usuario por su nombre de usuario
        user = self.db.query(UserModel.User).filter(UserModel.User.username == username).first()
        
        # Si no se encuentra el usuario o la contraseña no coincide, se retorna None
        if not user or not verify_password(password, user.hashed_password):
            return None
            
        return user

    def login(self, user: UserModel.User) -> LoginResponse:
        """
        Genera una respuesta de login con un token de acceso.
        """
        # El "subject" del token identifica al usuario y su tipo
        token_subject = f"user:{user.id}"
        access_token = create_access_token(subject=token_subject)
        
        # Basado en la imagen de roles que proporcionaste, el rol se obtiene de la relación
        role_name = "N/A"
        if user.role:
            # Asumiendo que la relación 'role' en tu modelo User tiene un campo 'nombre_rol'
            # Si el campo se llama diferente, ajústalo aquí.
            role_name = user.role.nombre_rol

        return LoginResponse(
            access_token=access_token,
            user={
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "role": role_name
            }
        )

