from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import text
from ..models.user import Usuario, Rol
from ..core.security import verify_password, get_password_hash, create_access_token
from ..schemas.auth import LoginResponse


class AuthService:
    def __init__(self, db: Session):
        self.db = db

    def authenticate_user(self, username: str, password: str) -> Optional[Usuario]:
        """Authenticate user with username and password"""
        user = self.get_user_by_username(username)
        if not user:
            return None
        if not verify_password(password, user.password_hash):
            return None
        return user

    def get_user_by_username(self, username: str) -> Optional[Usuario]:
        """Get user by username"""
        return self.db.query(Usuario).filter(
            Usuario.login_username == username,
            Usuario.is_active == True
        ).first()

    def login(self, username: str, password: str) -> Optional[LoginResponse]:
        """Login user and return token"""
        user = self.authenticate_user(username, password)
        if not user:
            return None

        # Update last access
        from sqlalchemy import func
        user.ultimo_acceso = func.now()
        self.db.commit()

        # Create access token
        access_token = create_access_token(subject=user.login_username)

        return LoginResponse(
            access_token=access_token,
            user={
                "id": user.id_usuario,
                "username": user.login_username,
                "role": user.rol.nombre_rol,
                "personalId": user.personal_id_rrhh
            }
        )

    def get_user_profile(self, user_id: int) -> Optional[dict]:
        """Get user profile with personal data from RRHH"""
        user = self.db.query(Usuario).filter(Usuario.id_usuario == user_id).first()
        if not user:
            return None

        # Get personal data from RRHH database
        personal_data = self.get_personal_data_from_rrhh(user.personal_id_rrhh)

        return {
            "id_usuario": user.id_usuario,
            "login_username": user.login_username,
            "personal_id_rrhh": user.personal_id_rrhh,
            "is_active": user.is_active,
            "ultimo_acceso": user.ultimo_acceso,
            "fecha_creacion": user.fecha_creacion,
            "rol": {
                "id_rol": user.rol.id_rol,
                "nombre_rol": user.rol.nombre_rol,
                "descripcion": user.rol.descripcion,
                "permisos_json": user.rol.permisos_json
            },
            "datos_personal": personal_data
        }

    def get_personal_data_from_rrhh(self, personal_id: int) -> Optional[dict]:
        """Get personal data from RRHH database using raw query"""
        try:
            result = self.db.execute(text("""
                SELECT 
                    personal_id,
                    cedula,
                    apenom,
                    nombres,
                    nombres2,
                    apellidos,
                    apellido_materno,
                    email,
                    nomposicion_id,
                    IdDepartamento,
                    estado
                FROM aitsa_rrhh.nompersonal 
                WHERE personal_id = :personal_id
            """), {"personal_id": personal_id})
            
            row = result.fetchone()
            if row:
                return {
                    "personal_id": row.personal_id,
                    "cedula": row.cedula,
                    "apenom": row.apenom,
                    "nombres": row.nombres,
                    "nombres2": row.nombres2,
                    "apellidos": row.apellidos,
                    "apellido_materno": row.apellido_materno,
                    "email": row.email,
                    "nomposicion_id": row.nomposicion_id,
                    "id_departamento": row.IdDepartamento,
                    "estado": row.estado
                }
            return None
        except Exception as e:
            print(f"Error getting personal data: {e}")
            return None