# app/api/v1/__init__.py

from fastapi import APIRouter

from .auth import router as auth_router
from .users import router as users_router
from .missions import router as missions_router
from .webhooks import router as webhooks_router
# ✅ Se importa el nuevo router de empleados
from .employee_requests import router as employee_router

api_router = APIRouter()

# Se registran todos los routers en el router principal de la API
api_router.include_router(auth_router, prefix="/auth")
api_router.include_router(users_router, prefix="/users", tags=["Users"])
api_router.include_router(missions_router, prefix="/missions", tags=["Missions"])
api_router.include_router(webhooks_router, prefix="/webhooks", tags=["Webhooks"])

# ✅ Se registra el nuevo router con un prefijo
api_router.include_router(employee_router, prefix="/employee", tags=["Employee"])
