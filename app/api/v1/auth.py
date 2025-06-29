# app/api/v1/auth.py

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.schemas.auth import LoginResponse
from app.services.auth import AuthService
# ✅ Se importan los nuevos módulos necesarios
from app.services.employee_auth import EmployeeAuthService
from app.core.database import get_db_financiero, get_db_rrhh

router = APIRouter()

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
    db: Session = Depends(get_db_rrhh) # <<< Usa la conexión a RRHH
):
    """
    Login para empleados/colaboradores.
    Usa la cédula como username y la contraseña en formato MD5.
    """
    auth_service = EmployeeAuthService(db)
    # El username del formulario será la cédula del empleado
    result = auth_service.login(cedula=form_data.username, password=form_data.password)
    
    if not result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Cédula o contraseña incorrecta, o el usuario no está activo.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return result
