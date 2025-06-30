from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session
from typing import Optional
from datetime import date, datetime
import io

from ...core.database import get_db_financiero
from ...services.reports import ReportService
from ...api.deps import get_current_user
from ...models.user import Usuario
from ...models.enums import TipoMision

router = APIRouter()


@router.get("/missions/excel")
async def generate_missions_excel_report(
    fecha_desde: Optional[date] = Query(None),
    fecha_hasta: Optional[date] = Query(None),
    tipo_mision: Optional[TipoMision] = Query(None),
    estado_id: Optional[int] = Query(None),
    db: Session = Depends(get_db_financiero),
    current_user: Usuario = Depends(get_current_user)
):
    """Generar reporte de misiones en Excel"""
    report_service = ReportService(db)
    
    excel_file = report_service.generate_missions_report(
        user=current_user,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        tipo_mision=tipo_mision,
        estado_id=estado_id,
        formato="excel"
    )
    
    filename = f"reporte_misiones_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    
    return Response(
        content=excel_file.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )


@router.get("/financial-summary")
async def get_financial_summary(
    fecha_desde: date = Query(...),
    fecha_hasta: date = Query(...),
    db: Session = Depends(get_db_financiero),
    current_user: Usuario = Depends(get_current_user)
):
    """Obtener resumen financiero"""
    # Verificar permisos
    if current_user.rol.nombre_rol not in ["Director Finanzas", "Administrador Sistema"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene permisos para ver reportes financieros"
        )
    
    report_service = ReportService(db)
    return report_service.generate_financial_summary(fecha_desde, fecha_hasta)


@router.get("/missions/{mission_id}/audit-trail")
async def get_mission_audit_trail(
    mission_id: int,
    db: Session = Depends(get_db_financiero),
    current_user: Usuario = Depends(get_current_user)
):
    """Obtener rastro de auditoría de una misión"""
    report_service = ReportService(db)
    return report_service.generate_audit_trail(mission_id)