from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text, and_
# ✅ CORRECCIÓN: usar user en minúscula
from ..models.user import Usuario, Rol
from ..schemas.user import UsuarioCreate, UsuarioUpdate, RolCreate, RolUpdate
from ..core.security import get_password_hash
from fastapi import HTTPException, status


class UserService:
    def __init__(self, db: Session):
        self.db = db

    # === GESTIÓN DE USUARIOS ===
    def create_user(self, user_data: UsuarioCreate) -> Usuario:
        """Create new user"""
        # Check if personal ID exists in RRHH (if provided)
        if user_data.personal_id_rrhh and not self.verify_personal_in_rrhh(user_data.personal_id_rrhh):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Personal ID not found in RRHH system"
            )

        # Check if personal_id_rrhh already exists (if provided)
        if user_data.personal_id_rrhh:
            existing_personal = self.db.query(Usuario).filter(
                Usuario.personal_id_rrhh == user_data.personal_id_rrhh
            ).first()
            if existing_personal:
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

        # Verify role exists
        role = self.db.query(Rol).filter(Rol.id_rol == user_data.id_rol).first()
        if not role:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Role not found"
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

    def get_users(self, skip: int = 0, limit: int = 100, include_inactive: bool = False) -> List[Usuario]:
        """Get all users"""
        query = self.db.query(Usuario)
        if not include_inactive:
            query = query.filter(Usuario.is_active == True)
        return query.offset(skip).limit(limit).all()

    def get_user(self, user_id: int) -> Optional[Usuario]:
        """Get user by ID"""
        return self.db.query(Usuario).filter(Usuario.id_usuario == user_id).first()

    def get_user_by_username(self, username: str) -> Optional[Usuario]:
        """Get user by username"""
        return self.db.query(Usuario).filter(Usuario.login_username == username).first()

    def update_user(self, user_id: int, user_data: UsuarioUpdate) -> Usuario:
        """Update user"""
        user = self.get_user(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        update_data = user_data.model_dump(exclude_unset=True)
        
        # Check username uniqueness if being updated
        if 'login_username' in update_data and update_data['login_username'] != user.login_username:
            existing = self.db.query(Usuario).filter(
                and_(
                    Usuario.login_username == update_data['login_username'],
                    Usuario.id_usuario != user_id
                )
            ).first()
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Username already taken"
                )

        # Check personal_id_rrhh uniqueness if being updated
        if 'personal_id_rrhh' in update_data and update_data['personal_id_rrhh'] != user.personal_id_rrhh:
            if update_data['personal_id_rrhh'] is not None:
                existing = self.db.query(Usuario).filter(
                    and_(
                        Usuario.personal_id_rrhh == update_data['personal_id_rrhh'],
                        Usuario.id_usuario != user_id
                    )
                ).first()
                if existing:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Personal ID already assigned to another user"
                    )

        # Verify role exists if being updated
        if 'id_rol' in update_data:
            role = self.db.query(Rol).filter(Rol.id_rol == update_data['id_rol']).first()
            if not role:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Role not found"
                )

        # Hash password if provided
        if 'password' in update_data:
            update_data['password_hash'] = get_password_hash(update_data.pop('password'))

        # Update user
        for field, value in update_data.items():
            setattr(user, field, value)

        self.db.commit()
        self.db.refresh(user)
        return user

    def delete_user(self, user_id: int) -> bool:
        """Delete user (soft delete by deactivating)"""
        user = self.get_user(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        user.is_active = False
        self.db.commit()
        return True

    # === GESTIÓN DE ROLES ===
    def get_roles(self) -> List[Rol]:
        """Get all roles"""
        return self.db.query(Rol).order_by(Rol.nombre_rol).all()

    def get_role(self, role_id: int) -> Optional[Rol]:
        """Get role by ID"""
        return self.db.query(Rol).filter(Rol.id_rol == role_id).first()

    def create_role(self, role_data: RolCreate) -> Rol:
        """Create new role"""
        # Check if role name already exists
        existing_role = self.db.query(Rol).filter(
            Rol.nombre_rol == role_data.nombre_rol
        ).first()
        if existing_role:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Role name already exists"
            )

        db_role = Rol(
            nombre_rol=role_data.nombre_rol,
            descripcion=role_data.descripcion,
            permisos_json=role_data.permisos_json
        )

        self.db.add(db_role)
        self.db.commit()
        self.db.refresh(db_role)
        return db_role

    def update_role(self, role_id: int, role_data: RolUpdate) -> Rol:
        """Update role"""
        role = self.get_role(role_id)
        if not role:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Role not found"
            )

        update_data = role_data.model_dump(exclude_unset=True)
        
        # Check role name uniqueness if being updated
        if 'nombre_rol' in update_data and update_data['nombre_rol'] != role.nombre_rol:
            existing = self.db.query(Rol).filter(
                and_(
                    Rol.nombre_rol == update_data['nombre_rol'],
                    Rol.id_rol != role_id
                )
            ).first()
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Role name already exists"
                )

        # Update role
        for field, value in update_data.items():
            setattr(role, field, value)

        self.db.commit()
        self.db.refresh(role)
        return role

    def delete_role(self, role_id: int) -> bool:
        """Delete role"""
        role = self.get_role(role_id)
        if not role:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Role not found"
            )

        # Check if role is being used by any user
        users_with_role = self.db.query(Usuario).filter(Usuario.id_rol == role_id).count()
        if users_with_role > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot delete role. {users_with_role} users are assigned to this role"
            )

        self.db.delete(role)
        self.db.commit()
        return True

    # === UTILIDADES ===
    def verify_personal_in_rrhh(self, personal_id: int) -> bool:
        """Verify if personal ID exists in RRHH system"""
        try:
            result = self.db.execute(text("""
                SELECT personal_id 
                FROM aitsa_rrhh.nompersonal 
                WHERE personal_id = :personal_id AND estado != 'De Baja'
            """), {"personal_id": personal_id})
            
            return result.fetchone() is not None
        except Exception as e:
            print(f"Error verifying personal in RRHH: {e}")
            return True  # Allow creation if RRHH check fails

    def get_user_permissions(self, user_id: int) -> dict:
        """Get user permissions from role"""
        user = self.get_user(user_id)
        if not user or not user.rol:
            return {}
        return user.rol.permisos_json or {}