# app/main.py

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.api.v1 import api_router
from app.core.config import settings
from app.models.base import Base
from app.core.database import engine_financiero
from app.core.exceptions import (
    BusinessException, WorkflowException, ValidationException,
    PermissionException, ConfigurationException, MissionException
)

# Importar todos los modelos para que SQLAlchemy los reconozca
from app.models.user import Usuario, Rol
from app.models.mission import *
from app.models.configuration import ConfiguracionGeneral, ConfiguracionSistema  # ← NUEVO

Base.metadata.create_all(bind=engine_financiero)

# Inicialización de la aplicación FastAPI
app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    description="API para la Gestión de Viáticos y Solicitudes de AITSA",
)

# Exception Handlers for Custom Business Exceptions
@app.exception_handler(BusinessException)
async def business_exception_handler(request: Request, exc: BusinessException):
    """Handle business logic exceptions with detailed error responses."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "Business Rule Violation",
            "message": exc.message,
            "details": exc.details,
            "type": "business_error"
        }
    )

@app.exception_handler(WorkflowException)
async def workflow_exception_handler(request: Request, exc: WorkflowException):
    """Handle workflow-specific exceptions."""
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error": "Workflow Error",
            "message": exc.message,
            "details": exc.details,
            "type": "workflow_error"
        }
    )

@app.exception_handler(ValidationException)
async def validation_exception_handler(request: Request, exc: ValidationException):
    """Handle validation exceptions."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "Validation Error",
            "message": exc.message,
            "details": exc.details,
            "type": "validation_error"
        }
    )

@app.exception_handler(PermissionException)
async def permission_exception_handler(request: Request, exc: PermissionException):
    """Handle permission-related exceptions."""
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={
            "error": "Permission Denied",
            "message": exc.message,
            "details": exc.details,
            "type": "permission_error"
        }
    )

@app.exception_handler(ConfigurationException)
async def configuration_exception_handler(request: Request, exc: ConfigurationException):
    """Handle configuration-related exceptions."""
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Configuration Error",
            "message": exc.message,
            "details": exc.details,
            "type": "configuration_error"
        }
    )

@app.exception_handler(MissionException)
async def mission_exception_handler(request: Request, exc: MissionException):
    """Handle mission-specific exceptions."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "Mission Error",
            "message": exc.message,
            "details": exc.details,
            "type": "mission_error"
        }
    )

# Configuración de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["*"],
)

# Incluir todas las rutas de la API definidas en /api/v1/__init__.py
app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/", tags=["Root"])
async def root():
    """
    Endpoint de bienvenida que verifica que la API está funcionando.
    """
    return {"message": "Bienvenido a la API de Gestión de Misiones de AITSA"}