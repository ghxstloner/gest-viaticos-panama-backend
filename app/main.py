# app/main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1 import api_router
from app.core.config import settings
from app.models.base import Base
from app.core.database import engine_financiero

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