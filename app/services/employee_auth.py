# app/services/employee_auth.py

from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional, Dict, Any
from datetime import timedelta

from app.core.security import verify_md5_password, create_access_token
from app.core.config import settings
from app.schemas.auth import LoginResponse

class EmployeeAuthService:
    def __init__(self, db: Session):
        self.db = db

    def authenticate_employee(self, cedula: str, password: str) -> Optional[dict]:
        """Autentica a un empleado desde la tabla nompersonal de aitsa_rrhh."""
        try:
            query = text("""
                SELECT personal_id, cedula, apenom, estado, usr_password, email, telefonos
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

    def login(self, cedula: str, password: str) -> Optional[LoginResponse]:
        """Realiza el login de un empleado y genera un token."""
        employee = self.authenticate_employee(cedula, password)
        if not employee:
            return None

        # Crear token con datos completos para empleado
        token_data = {
            "sub": f"employee:{employee['cedula']}",
            "type": "employee",
            "personal_id": employee["personal_id"],
            "cedula": employee["cedula"],
            "nombre": employee["apenom"]
        }
        
        expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(data=token_data, expires_delta=expires_delta)

        # Estructura de respuesta para empleados con permisos básicos
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
            "role": "Empleado",
            "userType": "empleado",
            "is_active": True,
            "id_rol": 1,  # Rol de empleado
            "rol": {
                "id_rol": 1,
                "nombre_rol": "Empleado",
                "descripcion": "Empleado del sistema",
                "es_rol_empleado": True,
            },
        }

        return LoginResponse(
            access_token=access_token,
            user=user_data
        )