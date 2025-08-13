from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import HTTPException, status, UploadFile
from ..models.department import Department
from ..schemas.department import DepartmentCreate, DepartmentUpdate
import os
import uuid
from datetime import datetime


class DepartmentService:
    def __init__(self, db: Session):
        self.db = db
        self.seals_directory = "uploads/sellos"
        
        # Crear directorio si no existe
        os.makedirs(self.seals_directory, exist_ok=True)

    def create_department(self, department_data: DepartmentCreate) -> Department:
        """Create new department"""
        # Check if department name already exists
        existing_department = self.db.query(Department).filter(
            Department.nombre == department_data.nombre
        ).first()
        
        if existing_department:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Department name already exists"
            )

        db_department = Department(
            nombre=department_data.nombre,
            ruta_sello=None  # Se asigna automáticamente cuando se sube un sello
        )

        self.db.add(db_department)
        self.db.commit()
        self.db.refresh(db_department)
        return db_department

    def get_departments(self, skip: int = 0, limit: int = 100) -> List[Department]:
        """Get all departments"""
        return self.db.query(Department).offset(skip).limit(limit).all()

    def get_departments_with_counts(self, skip: int = 0, limit: int = 100) -> List[dict]:
        """Get all departments including number of users in each one"""
        from ..models.user import Usuario
        query = (
            self.db.query(
                Department,
                func.count(Usuario.id_usuario).label("usuarios_count")
            )
            .outerjoin(Usuario, Usuario.id_departamento == Department.id_departamento)
            .group_by(Department.id_departamento)
            .offset(skip)
            .limit(limit)
        )
        rows = query.all()
        return [
            {
                "id_departamento": dep.id_departamento,
                "nombre": dep.nombre,
                "ruta_sello": dep.ruta_sello,
                "usuarios_count": int(count or 0),
            }
            for dep, count in rows
        ]

    def get_department(self, department_id: int) -> Optional[Department]:
        """Get department by ID"""
        return self.db.query(Department).filter(
            Department.id_departamento == department_id
        ).first()

    def update_department(self, department_id: int, department_data: DepartmentUpdate) -> Department:
        """Update department"""
        department = self.get_department(department_id)
        if not department:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Department not found"
            )

        # Check if new name conflicts with existing departments
        if department_data.nombre and department_data.nombre != department.nombre:
            existing_department = self.db.query(Department).filter(
                Department.nombre == department_data.nombre,
                Department.id_departamento != department_id
            ).first()
            
            if existing_department:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Department name already exists"
                )

        # Update fields - solo actualizar nombre, ruta_sello se maneja por separado
        if department_data.nombre is not None:
            department.nombre = department_data.nombre
        # NOTA: ruta_sello no se actualiza aquí, se maneja solo a través de upload_seal()

        self.db.commit()
        self.db.refresh(department)
        return department

    def delete_department(self, department_id: int) -> bool:
        """Delete department"""
        department = self.get_department(department_id)
        if not department:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Department not found"
            )

        # Delete associated seal file if exists
        if department.ruta_sello and os.path.exists(department.ruta_sello):
            try:
                os.remove(department.ruta_sello)
            except OSError:
                pass  # Ignore errors if file deletion fails

        self.db.delete(department)
        self.db.commit()
        return True

    def upload_seal(self, department_id: int, seal_file: UploadFile) -> str:
        """Upload seal image for a department"""
        department = self.get_department(department_id)
        if not department:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Department not found"
            )

        # Validate file type
        if not seal_file.content_type.startswith('image/'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File must be an image"
            )

        # Generate unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_extension = os.path.splitext(seal_file.filename)[1] if seal_file.filename else '.png'
        filename = f"sello_dep_{department_id}_{timestamp}_{uuid.uuid4().hex[:8]}{file_extension}"
        file_path = os.path.join(self.seals_directory, filename)

        # Delete old seal file if exists
        if department.ruta_sello and os.path.exists(department.ruta_sello):
            try:
                os.remove(department.ruta_sello)
            except OSError:
                pass

        # Save new file
        try:
            with open(file_path, "wb") as buffer:
                content = seal_file.file.read()
                buffer.write(content)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error saving file: {str(e)}"
            )

        # Update department record
        department.ruta_sello = file_path
        self.db.commit()
        self.db.refresh(department)

        return file_path

    def delete_seal(self, department_id: int) -> bool:
        """Delete seal image for a department"""
        department = self.get_department(department_id)
        if not department:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Department not found"
            )

        if not department.ruta_sello:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Department has no seal image"
            )

        # Delete file
        if os.path.exists(department.ruta_sello):
            try:
                os.remove(department.ruta_sello)
            except OSError:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Error deleting file"
                )

        # Update department record
        department.ruta_sello = None
        self.db.commit()
        self.db.refresh(department)

        return True

    def get_seal_path(self, department_id: int) -> Optional[str]:
        """Get seal image path for a department"""
        department = self.get_department(department_id)
        if not department:
            return None
        
        if not department.ruta_sello or not os.path.exists(department.ruta_sello):
            return None
            
        return department.ruta_sello

    # === MÉTODOS PARA MANEJO DE USUARIOS EN DEPARTAMENTOS ===

    def assign_user_to_department(self, user_id: int, department_id: int) -> bool:
        """Assign user to department"""
        from ..models.user import Usuario
        
        # Verificar que el departamento existe
        department = self.get_department(department_id)
        if not department:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Department not found"
            )
        
        # Verificar que el usuario existe
        user = self.db.query(Usuario).filter(Usuario.id_usuario == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Asignar usuario al departamento
        user.id_departamento = department_id
        self.db.commit()
        self.db.refresh(user)
        
        return True

    def remove_user_from_department(self, user_id: int) -> bool:
        """Remove user from department (set id_departamento to None)"""
        from ..models.user import Usuario
        
        # Verificar que el usuario existe
        user = self.db.query(Usuario).filter(Usuario.id_usuario == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Quitar usuario del departamento
        user.id_departamento = None
        self.db.commit()
        self.db.refresh(user)
        
        return True

    def get_users_in_department(self, department_id: int, skip: int = 0, limit: int = 100) -> List[dict]:
        """Get all users in a specific department"""
        from ..models.user import Usuario
        
        # Verificar que el departamento existe
        department = self.get_department(department_id)
        if not department:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Department not found"
            )
        
        # Obtener usuarios del departamento
        users = self.db.query(Usuario).filter(
            Usuario.id_departamento == department_id,
            Usuario.is_active == True
        ).offset(skip).limit(limit).all()
        
        # Convertir a lista de diccionarios con información básica
        users_data = []
        for user in users:
            users_data.append({
                "id_usuario": user.id_usuario,
                "login_username": user.login_username,
                "personal_id_rrhh": user.personal_id_rrhh,
                "id_rol": user.id_rol,
                "is_active": user.is_active,
                "ultimo_acceso": user.ultimo_acceso,
                "created_at": user.created_at,
                "updated_at": user.updated_at
            })
        
        return users_data

    def get_department_with_users(self, department_id: int) -> dict:
        """Get department information with its users"""
        department = self.get_department(department_id)
        if not department:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Department not found"
            )
        
        # Obtener usuarios del departamento
        users = self.get_users_in_department(department_id)
        
        return {
            "id_departamento": department.id_departamento,
            "nombre": department.nombre,
            "ruta_sello": department.ruta_sello,
            "usuarios": users,
            "total_usuarios": len(users)
        }
