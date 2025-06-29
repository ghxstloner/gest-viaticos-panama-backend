# app/main.py

from fastapi import FastAPI
from app.api.v1 import api_router
from app.core.config import settings
from app.models.base import Base

# ✅ CORRECCIÓN: Importamos 'engine_financiero' en lugar de 'engine'.
# Este es el motor de la base de datos para la cual este proyecto define los modelos.
from app.core.database import engine_financiero

# Esta línea crea las tablas definidas en tus modelos (User, Mission, etc.)
# en la base de datos 'aitsa_financiero' si no existen.
# ✅ CORRECCIÓN: Usamos 'engine_financiero' como el motor.
Base.metadata.create_all(bind=engine_financiero)

# Inicialización de la aplicación FastAPI
app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    description="API para la Gestión de Viáticos y Solicitudes de AITSA",
)

# Incluir todas las rutas de la API definidas en /api/v1/__init__.py
app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/", tags=["Root"])
async def root():
    """
    Endpoint de bienvenida que verifica que la API está funcionando.
    """
    return {"message": "Bienvenido a la API de Gestión de Misiones de AITSA"}

