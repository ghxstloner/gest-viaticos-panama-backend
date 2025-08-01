# app/services/user.py

from typing import List, Optional, Union
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import text, and_
from ..models.user import Usuario, Rol, Permiso, RolPermiso
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
        return self.db.query(Usuario).options(
            joinedload(Usuario.rol).joinedload(Rol.permisos)
        ).filter(Usuario.login_username == username).first()


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
        if 'password' in update_data and update_data['password']:
            update_data['password_hash'] = get_password_hash(update_data.pop('password'))
        else:
            update_data.pop('password', None)


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
        return self.db.query(Rol).options(joinedload(Rol.permisos)).filter(Rol.id_rol == role_id).first()

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
            descripcion=role_data.descripcion
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

    # === GESTIÓN DE PERMISOS ===
    def get_permisos(self) -> List[Permiso]:
        """Get all permissions"""
        return self.db.query(Permiso).order_by(Permiso.modulo, Permiso.accion).all()

    def get_user_permissions_by_role(self, role_id: int) -> dict:
        """
        Get permissions for a specific role and return them in a
        structured dictionary for the frontend.
        """
        # --- CORRECCIÓN APLICADA AQUÍ ---
        # Se usa .c.<column_name> para acceder a las columnas de la tabla RolPermiso
        permisos_query = self.db.query(
            Permiso.modulo,
            Permiso.accion,
            Permiso.codigo
        ).join(
            RolPermiso, Permiso.id_permiso == RolPermiso.c.id_permiso
        ).filter(
            RolPermiso.c.id_rol == role_id
        ).all()

        estructura = {}
        codigos = []
        for modulo, accion, codigo in permisos_query:
            if modulo not in estructura:
                estructura[modulo] = {}
            estructura[modulo][accion] = True
            codigos.append(codigo)

        return {"codes": codigos, "estructura": estructura}

    def assign_permission_to_role(self, role_id: int, permission_id: int) -> bool:
        """Assign permission to role"""
        role = self.get_role(role_id)
        if not role:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")

        permission = self.db.query(Permiso).filter(Permiso.id_permiso == permission_id).first()
        if not permission:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Permission not found")

        if permission not in role.permisos:
            role.permisos.append(permission)
            self.db.commit()

        return True

    def remove_permission_from_role(self, role_id: int, permission_id: int) -> bool:
        """Remove permission from role"""
        role = self.get_role(role_id)
        if not role:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")

        permission = self.db.query(Permiso).filter(Permiso.id_permiso == permission_id).first()
        if not permission:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Permission not found")

        if permission in role.permisos:
            role.permisos.remove(permission)
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
            # En un entorno de desarrollo, podría ser útil permitir que esto falle
            # sin bloquear la creación de usuarios. En producción, podría ser False.
            return True

    def get_user_permissions(self, user_id: int) -> dict:
        """Get user permissions from role"""
        user = self.db.query(Usuario).options(
            joinedload(Usuario.rol).joinedload(Rol.permisos)
        ).filter(Usuario.id_usuario == user_id).first()
        
        if not user or not user.rol:
            return {}
        return user.get_permissions()


    # === MÉTODOS FALTANTES PARA GESTIÓN COMPLETA DE PERMISOS ===
    
    def get_all_permisos(self) -> List[Permiso]:
        """Get ALL available permissions (for admin use)"""
        return self.db.query(Permiso).order_by(Permiso.modulo, Permiso.accion).all()
    
    def get_role_permissions(self, role_id: int) -> List[Permiso]:
        """Get all permissions for a specific role"""
        role = self.db.query(Rol).options(
            joinedload(Rol.permisos)
        ).filter(Rol.id_rol == role_id).first()
        
        if not role:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Role not found"
            )
        
        return role.permisos
    
    def update_role_permissions(self, role_id: int, permission_ids: List[int]) -> Rol:
        """Update all permissions for a role (replace existing permissions)"""
        role = self.db.query(Rol).options(
            joinedload(Rol.permisos)
        ).filter(Rol.id_rol == role_id).first()
        
        if not role:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Role not found"
            )
        
        # Obtener todos los permisos por IDs
        new_permissions = self.db.query(Permiso).filter(
            Permiso.id_permiso.in_(permission_ids)
        ).all()
        
        # Verificar que todos los permisos existen
        if len(new_permissions) != len(permission_ids):
            found_ids = [p.id_permiso for p in new_permissions]
            missing_ids = [pid for pid in permission_ids if pid not in found_ids]
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Permissions not found: {missing_ids}"
            )
        
        # Reemplazar todos los permisos del rol
        role.permisos = new_permissions
        self.db.commit()
        self.db.refresh(role)
        
        return role

    def get_employee_complete_info(self, personal_id: int) -> Optional[dict]:
        """Get complete employee information from RRHH system"""
        try:
            query = text("""
                SELECT 
                    p.personal_id,
                    p.apenom as nombre_completo,
                    p.cedula,
                    p.ficha as numero_trabajador,
                    n1.descrip as vicepresidencia,
                    d.Descripcion as departamento,
                    -- ✅ CORRECCIÓN: JOIN por cédula, no por personal_id
                    jefe.apenom as jefe_inmediato,
                    -- ✅ CORRECCIÓN: Comparar como string
                    CASE 
                        WHEN j.es_rotativo = '1' THEN 'Rotativo'
                        ELSE 'Administrativo'
                    END as tipo_trabajador,
                    f.descripcion_funcion as cargo,
                    f.titulo_puesto,
                    j.des_jor as turno,
                    -- ✅ CORRECCIÓN: Obtener horas reales del turno
                    CONCAT(
                        IFNULL(t.hora_entrada, '08:00:00'), 
                        ' - ', 
                        IFNULL(t.hora_salida, '16:30:00')
                    ) as horario_trabajo
                FROM aitsa_rrhh.nompersonal p
                LEFT JOIN aitsa_rrhh.nomnivel1 n1 ON p.codnivel1 = n1.codorg
                LEFT JOIN aitsa_rrhh.departamento d ON p.IdDepartamento = d.IdDepartamento
                -- ✅ CORRECCIÓN: JOIN correcto para jefe
                LEFT JOIN aitsa_rrhh.nompersonal jefe ON d.IdJefe = jefe.cedula
                LEFT JOIN aitsa_rrhh.nomfuncion f ON p.nomfuncion_id = f.nomfuncion_id + 0
                LEFT JOIN aitsa_rrhh.jornadas j ON p.cod_jor = j.cod_jor AND j.activo = 1
                LEFT JOIN aitsa_rrhh.turnos t ON p.turno_id = t.id
                WHERE p.personal_id = :personal_id AND p.estado != 'De Baja'
            """)
            
            result = self.db.execute(query, {"personal_id": personal_id})
            row = result.fetchone()
            
            if not row:
                return None
                
            return {
                "personal_id": row.personal_id,
                "nombre_completo": row.nombre_completo,
                "cedula": row.cedula,
                "numero_trabajador": row.numero_trabajador,
                "vicepresidencia": row.vicepresidencia or "No asignada",
                "departamento": row.departamento or "No asignado", 
                "jefe_inmediato": row.jefe_inmediato or "No asignado",
                "tipo_trabajador": row.tipo_trabajador,
                "cargo": row.cargo or "No asignado",
                "titulo_puesto": row.titulo_puesto or "No especificado",
                "horario_trabajo": row.horario_trabajo,
                "turno": row.turno or "Diurno"
            }
            
        except Exception as e:
            print(f"Error getting employee info: {e}")
            return None