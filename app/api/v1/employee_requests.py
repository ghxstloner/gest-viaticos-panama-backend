# app/api/v1/employee_requests.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from datetime import date, datetime, timedelta
from decimal import Decimal

from app.core.database import get_db_rrhh, get_db_financiero
from app.services.employee_request_service import EmployeeRequestService
from app.api.deps import get_current_employee
from app.models.mission import Mision, EstadoFlujo
from app.models.user import Usuario
from sqlalchemy import and_, func, extract

router = APIRouter()

@router.get("/mis-solicitudes", response_model=List[Dict[str, Any]])
def get_my_requests(
    current_employee: dict = Depends(get_current_employee),
    db: Session = Depends(get_db_rrhh)
):
    """
    Endpoint protegido que obtiene la lista de solicitudes del empleado
    actualmente autenticado.
    """
    service = EmployeeRequestService(db)
    cedula = current_employee.get("cedula")
    
    if not cedula:
         raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="No se pudo identificar la cédula del empleado desde el token."
        )
         
    return service.get_requests_by_cedula(cedula)

@router.get("/dashboard", response_model=Dict[str, Any])
def get_employee_dashboard(
    current_employee: dict = Depends(get_current_employee),
    db_financiero: Session = Depends(get_db_financiero)
):
    """
    Dashboard específico para empleados con sus estadísticas personales
    """
    cedula = current_employee.get("cedula")
    
    if not cedula:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="No se pudo identificar la cédula del empleado desde el token."
        )
    
    # Obtener fechas para el mes actual
    today = date.today()
    start_of_month = today.replace(day=1)
    start_of_year = today.replace(month=1, day=1)
    
    # Filtrar misiones por cédula del empleado
    base_query = db_financiero.query(Mision).filter(
        Mision.cedula_beneficiario == cedula
    )
    
    # Estadísticas generales
    total_misiones = base_query.count()
    
    # Misiones del mes actual
    misiones_mes = base_query.filter(
        Mision.created_at >= start_of_month
    ).count()
    
    # Misiones del año actual
    misiones_ano = base_query.filter(
        Mision.created_at >= start_of_year
    ).count()
    
    # Estadísticas por estado
    estado_counts = db_financiero.query(
        EstadoFlujo.nombre_estado,
        func.count(Mision.id_mision).label('count')
    ).join(
        Mision, EstadoFlujo.id_estado_flujo == Mision.id_estado_flujo
    ).filter(
        Mision.cedula_beneficiario == cedula
    ).group_by(EstadoFlujo.nombre_estado).all()
    
    # Organizar estadísticas por categorías
    pendientes_revision = 0
    aprobadas_total = 0
    rechazadas_total = 0
    pagadas_total = 0
    
    misiones_por_estado = {}
    for estado, count in estado_counts:
        misiones_por_estado[estado] = count
        if estado in ['PENDIENTE_JEFE', 'PENDIENTE_REVISION_TESORERIA', 'PENDIENTE_ASIGNACION_PRESUPUESTO', 
                     'PENDIENTE_CONTABILIDAD', 'PENDIENTE_APROBACION_FINANZAS', 'PENDIENTE_REFRENDO_CGR']:
            pendientes_revision += count
        elif estado in ['APROBADO_PARA_PAGO']:
            aprobadas_total += count
        elif estado in ['PAGADO']:
            pagadas_total += count
        elif estado in ['RECHAZADO', 'DEVUELTO_CORRECCION']:
            rechazadas_total += count
    
    # Monto total solicitado
    monto_total_solicitado = db_financiero.query(
        func.sum(Mision.monto_total_calculado)
    ).filter(
        Mision.cedula_beneficiario == cedula
    ).scalar() or Decimal('0.00')
    
    # Monto total aprobado
    monto_total_aprobado = db_financiero.query(
        func.sum(Mision.monto_aprobado)
    ).filter(
        and_(
            Mision.cedula_beneficiario == cedula,
            Mision.monto_aprobado.isnot(None)
        )
    ).scalar() or Decimal('0.00')
    
    # Monto del mes actual
    monto_total_mes = db_financiero.query(
        func.sum(Mision.monto_total_calculado)
    ).filter(
        and_(
            Mision.cedula_beneficiario == cedula,
            Mision.created_at >= start_of_month
        )
    ).scalar() or Decimal('0.00')
    
    # Estadísticas por tipo de misión
    tipo_counts = db_financiero.query(
        Mision.tipo_mision,
        func.count(Mision.id_mision).label('count')
    ).filter(
        Mision.cedula_beneficiario == cedula
    ).group_by(Mision.tipo_mision).all()
    
    misiones_por_tipo = {}
    for tipo, count in tipo_counts:
        misiones_por_tipo[tipo.value] = count
    
    # Misiones recientes (últimas 5)
    misiones_recientes = db_financiero.query(Mision).filter(
        Mision.cedula_beneficiario == cedula
    ).order_by(Mision.created_at.desc()).limit(5).all()
    
    # Formatear misiones recientes
    recientes_data = []
    for mision in misiones_recientes:
        recientes_data.append({
            "id_mision": mision.id_mision,
            "tipo_mision": mision.tipo_mision.value,
            "destino_mision": mision.destino_mision,
            "fecha_salida": mision.fecha_salida.isoformat() if mision.fecha_salida else None,
            "fecha_regreso": mision.fecha_regreso.isoformat() if mision.fecha_regreso else None,
            "monto_total_calculado": float(mision.monto_total_calculado or 0),
            "monto_aprobado": float(mision.monto_aprobado or 0),
            "estado_flujo": {
                "nombre_estado": mision.estado_flujo.nombre_estado,
                "es_estado_final": mision.estado_flujo.es_estado_final
            } if mision.estado_flujo else None,
            "created_at": mision.created_at.isoformat() if mision.created_at else None
        })
    
    return {
        "empleado": {
            "cedula": cedula,
            "nombre": current_employee.get("nombre", ""),
            "apellido": current_employee.get("apellido", "")
        },
        "resumen_general": {
            "total_misiones": total_misiones,
            "misiones_mes": misiones_mes,
            "misiones_ano": misiones_ano,
            "pendientes_revision": pendientes_revision,
            "aprobadas_total": aprobadas_total,
            "pagadas_total": pagadas_total,
            "rechazadas_total": rechazadas_total
        },
        "montos": {
            "total_solicitado": float(monto_total_solicitado),
            "total_aprobado": float(monto_total_aprobado),
            "monto_mes": float(monto_total_mes)
        },
        "estadisticas": {
            "misiones_por_estado": misiones_por_estado,
            "misiones_por_tipo": misiones_por_tipo
        },
        "misiones_recientes": recientes_data
    }
