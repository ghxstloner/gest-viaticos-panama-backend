# app/api/v1/auth.py

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import Optional

from app.schemas.auth import LoginResponse, Token, UserResponse, UserRegister
from app.services.auth import AuthService
from app.services.employee_auth import EmployeeAuthService
from app.core.database import get_db_financiero, get_db_rrhh
from app.core.exceptions import AuthenticationException

router = APIRouter(tags=["Authentication"])

@router.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db_financiero)
):
    """
    Endpoint para autenticación de usuarios.
    Retorna un token JWT y datos del usuario si las credenciales son válidas.
    """
    try:
        auth_service = AuthService(db)
        user = auth_service.authenticate_user(form_data.username, form_data.password)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuario o contraseña incorrecta",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return auth_service.create_access_token(user)
    except AuthenticationException as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )

@router.post("/login/financiero", response_model=LoginResponse, tags=["Authentication"])
def login_financiero(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db_financiero)
):
    """
    Login para usuarios del sistema financiero (Tesorería, Contabilidad, etc.).
    Usa username y password con hash bcrypt.
    """
    auth_service = AuthService(db)
    user = auth_service.authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrecta",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return auth_service.login(user)


@router.post("/login/empleado", response_model=LoginResponse, tags=["Authentication"])
def login_empleado(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db_rrhh: Session = Depends(get_db_rrhh),
    db_financiero: Session = Depends(get_db_financiero)
):
    """
    Login para empleados/colaboradores.
    Usa la cédula como username y la contraseña en formato MD5.
    """
    auth_service = EmployeeAuthService(db_rrhh, db_financiero)
    # El username del formulario será la cédula del empleado
    result = auth_service.login(cedula=form_data.username, password=form_data.password)
    
    if not result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Cédula o contraseña incorrecta, o el usuario no está activo.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return result

@router.post("/register/employee", response_model=UserResponse)
async def register_employee(
    user_data: UserRegister,
    db: Session = Depends(get_db_financiero)
):
    """
    Register a new employee user
    """
    auth_service = AuthService(db)
    try:
        user = auth_service.register_employee(
            username=user_data.username,
            password=user_data.password,
            personal_id=user_data.personal_id
        )
        return UserResponse.from_orm(user)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/logout")
async def logout():
    """
    Logout endpoint - En JWT stateless, solo es informativo
    """
    return {"message": "Logout exitoso"}