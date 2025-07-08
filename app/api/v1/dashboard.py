from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional, Union
from datetime import date

from ...core.database import get_db_financiero
from ...schemas.mission import DashboardStats
from ...services.dashboard import DashboardService
from ...api.deps import get_current_user_universal
from ...models.user import Usuario

router = APIRouter()


@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats(
    fecha_desde: Optional[date] = Query(None),
    fecha_hasta: Optional[date] = Query(None),
    db: Session = Depends(get_db_financiero),
    current_user: Union[Usuario, dict] = Depends(get_current_user_universal)
):
    """Obtener estadísticas del dashboard según el rol del usuario"""
    dashboard_service = DashboardService(db)
    return dashboard_service.get_dashboard_stats(current_user)


@router.get("/export/excel")
async def export_dashboard_excel(
    fecha_desde: Optional[date] = Query(None),
    fecha_hasta: Optional[date] = Query(None),
    db: Session = Depends(get_db_financiero),
    current_user: Union[Usuario, dict] = Depends(get_current_user_universal)
):
    """Exportar estadísticas del dashboard a Excel"""
    # TODO: Implementar exportación a Excel
    return {"message": "Funcionalidad en desarrollo"}


@router.get("/notifications/count")
async def get_notifications_count(
    db: Session = Depends(get_db_financiero),
    current_user: Union[Usuario, dict] = Depends(get_current_user_universal)
):
    """Obtener contador de notificaciones no leídas"""
    # TODO: Implementar sistema de notificaciones
    return {"unread_count": 0}