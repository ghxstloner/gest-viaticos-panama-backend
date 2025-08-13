# app/api/v1/__init__.py

from fastapi import APIRouter

from .auth import router as auth_router
from .users import router as users_router
from .missions import router as missions_router
from .webhooks import router as webhooks_router
from .employee_requests import router as employee_requests_router
from .employee_missions import router as employee_missions_router
from .configuration import router as configuration_router
from .dashboard import router as dashboard_router
from .reports import router as reports_router
from .admin import router as admin_router
from .workflow import router as workflow_router
from .department import router as department_router
from .notification import router as notification_router

api_router = APIRouter()

# Registrar los routers
api_router.include_router(auth_router, prefix="/auth", tags=["Auth"])
api_router.include_router(users_router, prefix="/users", tags=["Users"])
api_router.include_router(missions_router, prefix="/missions", tags=["Missions"])
api_router.include_router(employee_missions_router)
api_router.include_router(employee_requests_router, prefix="/employee/requests", tags=["Employee Requests"])
api_router.include_router(configuration_router, prefix="/configuration", tags=["Configuration"])
api_router.include_router(admin_router, prefix="/admin", tags=["Administration"])
api_router.include_router(reports_router, prefix="/reports", tags=["Reports"])
api_router.include_router(dashboard_router, prefix="/dashboard", tags=["Dashboard"])
api_router.include_router(webhooks_router, prefix="/webhooks", tags=["Webhooks"])
api_router.include_router(workflow_router)
api_router.include_router(department_router, prefix="/departments", tags=["Departments"])
api_router.include_router(notification_router, prefix="/notifications", tags=["Notifications"])  