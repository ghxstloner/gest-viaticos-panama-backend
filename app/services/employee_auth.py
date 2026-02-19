# app/services/employee_auth.py

from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional, Dict, Any
from datetime import timedelta

from app.core.security import verify_md5_password, create_access_token
from app.core.config import settings
from app.schemas.auth import LoginResponse
from app.services.user import UserService

class EmployeeAuthService:
    def __init__(self, db: Session, db_financiero: Optional[Session] = None):
        self.db = db  # Base de datos de RRHH
        self.db_financiero = db_financiero  # Base de datos financiera para permisos

    def authenticate_employee(self, cedula: str, password: str) -> Optional[dict]:
        """Autentica a un empleado desde la tabla nompersonal de RRHH."""
        try:
            query = text("""
                SELECT personal_id, cedula, apenom, estado, usr_password, email, telefonos, IdDepartamento
                FROM nompersonal
                WHERE cedula = :cedula
            """)
            result = self.db.execute(query, {"cedula": cedula})
            employee = result.fetchone()

            if not employee:
                return None

            employee_dict = dict(employee._mapping)

            if employee_dict.get("estado") == "De Baja":
                print(f"Intento de login de empleado inactivo: {cedula}")
                return None

            # ✅ Se usa la nueva función para verificar el hash MD5
            if not verify_md5_password(password, employee_dict.get("usr_password", "")):
                return None

            return employee_dict

        except Exception as e:
            print(f"Error durante la autenticación del empleado: {e}")
            return None
    
    def check_if_department_head(self, cedula: str) -> bool:
        """Verifica si el empleado es jefe inmediato (orden_aprobador = 1) en algún departamento"""
        try:
            query = text("""
                SELECT COUNT(*) as count
                FROM departamento_aprobadores_maestros dam
                WHERE dam.cedula_aprobador = :cedula
                  AND dam.orden_aprobador = 1
            """)
            result = self.db.execute(query, {"cedula": cedula})
            count = result.fetchone()
            return count.count > 0 if count else False
        except Exception as e:
            print(f"Error verificando si es jefe de departamento: {e}")
            return False
    
    def get_managed_departments(self, cedula: str) -> list:
        """Obtiene los departamentos donde el empleado es jefe inmediato (orden_aprobador = 1)"""
        try:
            query = text("""
                SELECT d.IdDepartamento, d.Descripcion
                FROM departamento d
                JOIN departamento_aprobadores_maestros dam
                  ON dam.id_departamento = d.IdDepartamento
                 AND dam.orden_aprobador = 1
                WHERE dam.cedula_aprobador = :cedula
            """)
            result = self.db.execute(query, {"cedula": cedula})
            return [{"id": row.IdDepartamento, "descripcion": row.Descripcion} for row in result.fetchall()]
        except Exception as e:
            print(f"Error obteniendo departamentos gestionados: {e}")
            return []

    def login(self, cedula: str, password: str) -> Optional[LoginResponse]:
        """Realiza el login de un empleado y genera un token."""
        employee = self.authenticate_employee(cedula, password)
        if not employee:
            return None

        # ✅ CRÍTICO: Verificar si es jefe de departamento
        is_department_head = self.check_if_department_head(cedula)
        managed_departments = self.get_managed_departments(cedula) if is_department_head else []
        
        # Determinar el rol basado en si es jefe o no
        role_id = 2 if is_department_head else 1  # 2 = Jefe Inmediato, 1 = Solicitante
        role_name = "Jefe Inmediato" if is_department_head else "Solicitante"

        # ✅ OBTENER PERMISOS DINÁMICAMENTE SEGÚN EL ROL ASIGNADO
        # Usar la base de datos financiera si está disponible, sino usar la de RRHH
        db_for_permissions = self.db_financiero if self.db_financiero else self.db
        user_service = UserService(db_for_permissions)
        permisos_usuario = user_service.get_user_permissions_by_role(role_id)
        
        # Crear token con datos completos para empleado
        token_data = {
            "sub": f"employee:{employee['cedula']}",
            "type": "employee",
            "personal_id": employee["personal_id"],
            "cedula": employee["cedula"],
            "nombre": employee["apenom"],
            "is_department_head": is_department_head,
            "managed_departments": managed_departments,
            "id_rol": role_id,  # ✅ INCLUIR ID DEL ROL EN EL TOKEN
            "permisos_usuario": permisos_usuario["estructura"]  # ✅ INCLUIR PERMISOS EN EL TOKEN
        }
        
        expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(data=token_data, expires_delta=expires_delta)
        
        # Estructura de respuesta para empleados con permisos dinámicos
        user_data = {
            "id": employee['personal_id'],
            "id_usuario": employee['personal_id'],  # Para compatibilidad
            "personal_id_rrhh": employee['personal_id'],
            "cedula": employee['cedula'],
            "nombre": employee['apenom'],
            "email": employee.get('email'),
            "telefonos": employee.get('telefonos'),
            "username": employee['cedula'],  # Para compatibilidad con frontend
            "login_username": employee['cedula'],
            "nombre_completo": employee['apenom'],
            "role": role_name,
            "userType": "empleado",
            "is_active": True,
            "id_rol": role_id,
            "is_department_head": is_department_head,
            "managed_departments": managed_departments,
            "rol": {
                "id_rol": role_id,
                "nombre_rol": role_name,
                "descripcion": f"Empleado con rol de {role_name}",
                "es_rol_empleado": True,
            },
            "permisos_usuario": permisos_usuario["estructura"]  # ✅ PERMISOS DINÁMICOS
        }

        return LoginResponse(
            access_token=access_token,
            user=user_data
        )