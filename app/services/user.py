from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text
from ..models.user import Usuario, Rol
from ..schemas.user import UsuarioCreate, UsuarioUpdate
from ..core.security import get_password_hash
from fastapi import HTTPException, status


class UserService:
    def __init__(self, db: Session):
        self.db = db

    def create_user(self, user_data: UsuarioCreate) -> Usuario:
        """Create new user"""
        # Check if personal ID exists in RRHH
        if not self.verify_personal_in_rrhh(user_data.personal_id_rrhh):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Personal ID not found in RRHH system"
            )

        # Check if user already exists
        existing_user = self.db.query(Usuario).filter(
            Usuario.personal_id_rrhh == user_data.personal_id_rrhh
        ).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User already exists for this employee"
            )

        # Check if username is taken
        existing_username = self.db.query(Usuario).filter(
            Usuario.login_username == user_data.login_username
        ).first()
        if existing_username:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Username already taken"
            )

        # Create user
        db_user = Usuario(
            personal_id_rrhh=user_data.personal_id_rrhh,
            login_username=user_data.login_username,
            password_hash=get_password_hash(user_data.password),
            id_rol=user_data.id_rol,
            is_active=user_data.is_active
        )

        self.db.add(db_user)
        self.db.commit()
        self.db.refresh(db_user)
        return db_user

    def get_users(self, skip: int = 0, limit: int = 100) -> List[Usuario]:
        """Get all users"""
        return self.db.query(Usuario).offset(skip).limit(limit).all()

    def get_user(self, user_id: int) -> Optional[Usuario]:
        """Get user by ID"""
        return self.db.query(Usuario).filter(Usuario.id_usuario == user_id).first()

    def update_user(self, user_id: int, user_data: UsuarioUpdate) -> Usuario:
        """Update user"""
        user = self.get_user(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        # Update fields
        if user_data.login_username and user_data.login_username != user.login_username:
            # Check if new username is taken
            existing = self.db.query(Usuario).filter(
                Usuario.login_username == user_data.login_username
            ).first()
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Username already taken"
                )
            user.login_username = user_data.login_username

        if user_data.password:
            user.password_hash = get_password_hash(user_data.password)

        if user_data.id_rol is not None:
            user.id_rol = user_data.id_rol

        if user_data.is_active is not None:
            user.is_active = user_data.is_active

        self.db.commit()
        self.db.refresh(user)
        return user

    def toggle_user_active(self, user_id: int) -> Usuario:
        """Toggle user active status"""
        user = self.get_user(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        user.is_active = not user.is_active
        self.db.commit()
        self.db.refresh(user)
        return user

    def get_roles(self) -> List[Rol]:
        """Get all roles"""
        return self.db.query(Rol).order_by(Rol.nombre_rol).all()

    def verify_personal_in_rrhh(self, personal_id: int) -> bool:
        """Verify if personal ID exists in RRHH system"""
        try:
            result = self.db.execute(text("""
                SELECT personal_id 
                FROM aitsa_rrhh.nompersonal 
                WHERE personal_id = :personal_id AND estado = 'ACTIVO'
            """), {"personal_id": personal_id})
            
            return result.fetchone() is not None
        except Exception as e:
            print(f"Error verifying personal in RRHH: {e}")
            return False