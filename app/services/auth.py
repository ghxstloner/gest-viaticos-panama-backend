from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import or_, text
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status

from app.core.config import settings
from app.models.user import Usuario, Rol
from app.core.exceptions import AuthenticationException, ValidationException
from app.core.security import verify_password, get_password_hash, create_access_token
from app.schemas.auth import LoginResponse, Token, UserResponse
from app.services.user import UserService

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class AuthService:
    def __init__(self, db: Session, db_rrhh: Optional[Session] = None):
        self.db = db
        self.db_rrhh = db_rrhh

    def authenticate_user(self, username: str, password: str) -> Optional[Usuario]:
        """Autenticar usuario por username/password"""
        user = self.db.query(Usuario).filter(Usuario.login_username == username).first()
        if not user:
            return None
        if not verify_password(password, user.password_hash):
            return None
        return user

    def create_access_token(self, user: Usuario) -> Token:
        """Crear token de acceso JWT y retornar Token completo"""
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        to_encode = {
            "sub": user.login_username,
            "exp": expire,
            "id": user.id_usuario,
            "role": user.rol.nombre_rol,
            "type": "financiero"
        }
        encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        
        # Crear UserResponse (sin campos que no existen)
        user_response = UserResponse(
            login_username=user.login_username,
            personal_id_rrhh=user.personal_id_rrhh,
            id_usuario=user.id_usuario,
            rol=user.rol,
            is_active=user.is_active,
            ultimo_acceso=user.ultimo_acceso
        )
        
        return Token(
            access_token=encoded_jwt,
            token_type="bearer",
            user=user_response
        )

    def _normalize_employee_permissions(self, employee_permissions: Dict[str, Any]) -> Dict[str, bool]:
        """
        Convierte permisos de empleados a estructura estándar de códigos.
        """
        normalized_permissions = {}
        
        # Mapear permisos de empleados a códigos estándar
        misiones = employee_permissions.get('misiones', {})
        if misiones.get('ver'):
            normalized_permissions['MISSION_VIEW'] = True
        if misiones.get('crear'):
            normalized_permissions['MISSION_CREATE'] = True
        if misiones.get('editar'):
            normalized_permissions['MISSION_EDIT'] = True
        if misiones.get('aprobar'):
            normalized_permissions['MISSION_APPROVE'] = True
            normalized_permissions['MISSION_REJECT'] = True  # Aprobar incluye rechazar
        if misiones.get('pagar'):
            normalized_permissions['MISSION_PAYMMENT'] = True
            normalized_permissions['PAGOS_VIEW'] = True  # Pagar incluye ver pagos
        
        # Gestión de solicitudes
        gestion = employee_permissions.get('gestion_solicitudes', {})
        if gestion.get('ver'):
            normalized_permissions['GESTION_SOLICITUDES_VIEW'] = True
        
        # Reportes
        reportes = employee_permissions.get('reportes', {})
        if reportes.get('ver'):
            normalized_permissions['REPORT_VIEW'] = True
        
        # Si es jefe inmediato, agregar permisos adicionales de módulos
        if misiones.get('aprobar'):
            normalized_permissions['PRESUPUESTO_VIEW'] = True
            normalized_permissions['CONTABILIDAD_VIEW'] = True
            normalized_permissions['FISCALIZACION_VIEW'] = True
        
        return normalized_permissions

    def login(self, user: Usuario) -> LoginResponse:
        """
        Proceso completo de login para usuarios financieros
        """
        # Actualizar último acceso
        user.ultimo_acceso = datetime.utcnow()
        self.db.commit()
        
        # Crear token JWT con datos completos
        token_data = {
            "sub": user.login_username,
            "type": "financiero",
            "id": user.id_usuario,
            "role": user.rol.nombre_rol
        }
        
        expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(data=token_data, expires_delta=expires_delta)
        
        # Obtener permisos reales del rol usando el servicio correcto
        user_service = UserService(self.db)
        permisos_data = user_service.get_user_permissions_by_role(user.id_rol)
        permisos_usuario_simple = permisos_data["estructura"]
        
        # Estructura de respuesta para usuarios financieros
        user_data = {
            "id": user.id_usuario,
            "id_usuario": user.id_usuario,
            "personal_id_rrhh": user.personal_id_rrhh,
            "login_username": user.login_username,
            "username": user.login_username,  # Para compatibilidad
            "role": user.rol.nombre_rol,
            "userType": "financiero",
            "is_active": user.is_active,
            "id_rol": user.id_rol,
            "ultimo_acceso": user.ultimo_acceso.isoformat() if user.ultimo_acceso else None,
            "rol": {
                "id_rol": user.rol.id_rol,
                "nombre_rol": user.rol.nombre_rol,
                "descripcion": user.rol.descripcion,
            },
            "permisos_usuario": permisos_usuario_simple  # ← ESTRUCTURA SIMPLIFICADA (IGUAL QUE EMPLEADOS)
        }
        
        return LoginResponse(
            access_token=access_token,
            user=user_data
        )

    def login_employee(self, employee_data: Dict[str, Any], original_permissions: Dict[str, Any]) -> LoginResponse:
        """
        Proceso completo de login para empleados - NUEVA FUNCIÓN
        """
        # Normalizar permisos de empleados a estructura estándar
        normalized_permissions = self._normalize_employee_permissions(original_permissions)
        
        # Crear token JWT para empleado
        token_data = {
            "sub": f"employee:{employee_data['cedula']}",
            "type": "employee",
            "personal_id": employee_data['personal_id'],
            "cedula": employee_data['cedula'],
            "nombre": employee_data['apenom'],
            "is_department_head": employee_data.get('is_department_head', False),
            "managed_departments": employee_data.get('managed_departments', []),
            "id_rol": employee_data.get('id_rol'),
            "permisos_usuario": original_permissions,  # ← AGREGAR PERMISOS AL TOKEN
        }
        
        expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(data=token_data, expires_delta=expires_delta)
        
        # Estructura de respuesta NORMALIZADA para empleados
        user_data = {
            "id": employee_data['personal_id'],
            "id_usuario": employee_data['personal_id'],
            "personal_id_rrhh": employee_data['personal_id'],
            "cedula": employee_data['cedula'],
            "nombre": employee_data['apenom'],
            "email": employee_data.get('email'),
            "telefonos": employee_data.get('telefonos'),
            "username": employee_data['cedula'],
            "login_username": employee_data['cedula'],
            "nombre_completo": employee_data['apenom'],
            "role": employee_data.get('role_name', 'Empleado'),
            "userType": "empleado",
            "is_active": True,
            "id_rol": employee_data.get('id_rol'),
            "is_department_head": employee_data.get('is_department_head', False),
            "managed_departments": employee_data.get('managed_departments', []),
            "rol": {
                "id_rol": employee_data.get('id_rol'),
                "nombre_rol": employee_data.get('role_name', 'Empleado'),
                "descripcion": f"Empleado con rol de {employee_data.get('role_name', 'Empleado')}",
                "es_rol_empleado": True
            },
            "permissions": normalized_permissions,  # ← ESTRUCTURA ESTÁNDAR
            "permisos_usuario": normalized_permissions  # ← MISMA ESTRUCTURA QUE FINANCIEROS
        }
        
        return LoginResponse(
            access_token=access_token,
            user=user_data
        )

    def verify_token(self, token: str) -> Dict[str, Any]:
        """Verificar token JWT"""
        try:
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM]
            )
            return payload
        except JWTError:
            raise AuthenticationException("Token inválido o expirado")

    def check_permission(self, user: Usuario, required_permission: str) -> bool:
        """Verificar si el usuario tiene un permiso específico"""
        if not user.rol:
            return False

        permissions = user.get_permissions()
        module, action = required_permission.split('.')
        
        return bool(
            permissions.get(module, {}).get(action, False)
        )

    def register_employee(self, username: str, password: str, personal_id: Optional[int] = None) -> Usuario:
        """
        Registra un nuevo usuario con rol de empleado
        """
        # Verificar si el usuario ya existe
        existing_user = self.db.query(Usuario).filter(Usuario.login_username == username).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El nombre de usuario ya está registrado"
            )

        # Verificar si el personal_id ya está registrado
        if personal_id:
            existing_personal = self.db.query(Usuario).filter(Usuario.personal_id_rrhh == personal_id).first()
            if existing_personal:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="El ID de personal ya está registrado"
                )

        # Crear el nuevo usuario empleado
        hashed_password = get_password_hash(password)
        try:
            new_user = Usuario.create_employee(
                db_session=self.db,
                username=username,
                password_hash=hashed_password,
                personal_id=personal_id
            )
            return new_user
        except Exception as e:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error al crear el usuario: {str(e)}"
            )