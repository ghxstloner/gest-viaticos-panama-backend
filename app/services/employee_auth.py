# app/services/employee_auth.py

from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional

# ✅ Se importa la nueva función de verificación MD5
from app.core.security import verify_md5_password, create_access_token
from app.schemas.auth import LoginResponse

class EmployeeAuthService:
    def __init__(self, db: Session):
        self.db = db

    def authenticate_employee(self, cedula: str, password: str) -> Optional[dict]:
        """Autentica a un empleado desde la tabla nompersonal de aitsa_rrhh."""
        try:
            query = text("""
                SELECT personal_id, cedula, apenom, estado, usr_password
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

        # El subject del token identifica al usuario y su tipo
        token_subject = f"employee:{employee['cedula']}"
        access_token = create_access_token(subject=token_subject)

        return LoginResponse(
            access_token=access_token,
            user={
                "id": employee['personal_id'],
                "cedula": employee['cedula'],
                "nombre": employee['apenom'],
                "role": "Empleado"
            }
        )
