from fastapi import APIRouter, Depends, Query, Response, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from typing import Optional, Dict, Any
from datetime import date, datetime
import io

from ...core.database import get_db_financiero
from ...services.reports import ReportService
from ...services.pdf_reports import PDFReportService
from ...services.pdf_report_viaticos import PDFReportViaticosService
from ...api.deps import get_current_user, get_current_user_universal
from ...models.user import Usuario
from ...models.enums import TipoMision, TipoTransporte
from ...models.mission import Mision, EstadoFlujo, MisionCajaMenuda

router = APIRouter()

# ===============================================
# FUNCIONES HELPER PARA PERMISOS
# ===============================================

def has_permission(user, permission_code: str) -> bool:
    """Función helper para verificar permisos - versión universal"""
    if isinstance(user, dict):
        # Para empleados, verificar permisos en el dict con estructura anidada
        permissions = user.get('permisos_usuario', {})
        
        # Mapeo de códigos de permisos a la estructura de empleados
        permission_mapping = {
            'MISSION_APPROVE': permissions.get('misiones', {}).get('aprobar', False),
            'MISSION_REJECT': permissions.get('misiones', {}).get('aprobar', False),
            'MISSION_CREATE': permissions.get('misiones', {}).get('crear', False),
            'MISSION_EDIT': permissions.get('misiones', {}).get('editar', False),
            'MISSION_VIEW': permissions.get('misiones', {}).get('ver', False),
            'MISSION_PAYMMENT': permissions.get('misiones', {}).get('pagar', False),
            'MISSION_SUBSANAR': permissions.get('misiones', {}).get('subsanar', False),
            'GESTION_SOLICITUDES_VIEW': permissions.get('gestion_solicitudes', {}).get('ver', False),
            'REPORT_EXPORT': permissions.get('reportes', {}).get('exportar', False),
            'REPORT_EXPORT_CAJA': permissions.get('reportes', {}).get('exportar.caja', False),  # Permiso específico para caja menuda
            'REPORT_EXPORT_VIATICOS': permissions.get('reportes', {}).get('exportar.viaticos', False),  # Permiso específico para viáticos

        }
        
        return permission_mapping.get(permission_code, False)
    else:
        # Para usuarios financieros, usar el método del modelo
        try:
            if hasattr(user, 'has_permission'):
                return user.has_permission(permission_code)
            elif hasattr(user, 'rol') and hasattr(user.rol, 'permisos'):
                permisos = user.rol.permisos
                for permiso in permisos:
                    if hasattr(permiso, 'codigo') and permiso.codigo == permission_code:
                        return True
                return False
            elif hasattr(user, 'rol') and hasattr(user.rol, 'nombre_rol'):
                if user.rol.nombre_rol == 'Administrador Sistema':
                    return True
            
            return False
        except Exception as e:
            return False

def is_jefe_inmediato(user) -> bool:
    """Función para verificar si el usuario es jefe inmediato usando permisos"""
    if isinstance(user, dict):
        has_approve_permission = has_permission(user, 'MISSION_APPROVE')
        is_department_head = user.get('is_department_head', False)
        return has_approve_permission and is_department_head
    else:
        return has_permission(user, 'MISSION_APPROVE')


@router.get("/missions/excel")
async def generate_missions_excel_report(
    fecha_desde: Optional[date] = Query(None),
    fecha_hasta: Optional[date] = Query(None),
    tipo_mision: Optional[TipoMision] = Query(None),
    estado_id: Optional[int] = Query(None),
    db: Session = Depends(get_db_financiero),
    current_user = Depends(get_current_user_universal)
):
    """Generar reporte de misiones en Excel"""
    # Verificar permisos
    if not has_permission(current_user, "REPORT_EXPORT"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene permisos para exportar reportes"
        )
    
    report_service = ReportService(db, current_user)
    
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


@router.get("/missions/pdf")
async def generate_missions_pdf_report(
    fecha_desde: Optional[date] = Query(None),
    fecha_hasta: Optional[date] = Query(None),
    tipo_mision: Optional[TipoMision] = Query(None),
    estado_id: Optional[int] = Query(None),
    db: Session = Depends(get_db_financiero),
    current_user = Depends(get_current_user_universal)
):
    """Generar reporte de misiones en PDF"""
    # Verificar permisos
    if not has_permission(current_user, "REPORT_EXPORT"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene permisos para exportar reportes"
        )
    
    report_service = ReportService(db, current_user)
    
    pdf_file = report_service.generate_missions_report(
        user=current_user,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        tipo_mision=tipo_mision,
        estado_id=estado_id,
        formato="pdf"
    )
    
    filename = f"reporte_misiones_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    
    return Response(
        content=pdf_file.getvalue(),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )


@router.get("/financial-summary")
async def get_financial_summary(
    fecha_desde: date = Query(...),
    fecha_hasta: date = Query(...),
    formato: str = Query("json", description="Formato del reporte: json, pdf"),
    db: Session = Depends(get_db_financiero),
    current_user = Depends(get_current_user_universal)
):
    """Obtener resumen financiero"""
    # Verificar permisos
    if not has_permission(current_user, "REPORT_EXPORT"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene permisos para ver reportes financieros"
        )
    
    report_service = ReportService(db, current_user)
    summary_data = report_service.generate_financial_summary(fecha_desde, fecha_hasta)
    
    if formato == "pdf":
        pdf_service = PDFReportService(db)
        pdf_file = pdf_service.generate_financial_summary_pdf(fecha_desde, fecha_hasta, summary_data)
        
        filename = f"resumen_financiero_{fecha_desde.strftime('%Y%m%d')}_{fecha_hasta.strftime('%Y%m%d')}.pdf"
        
        return Response(
            content=pdf_file.getvalue(),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
    
    return summary_data


@router.get("/missions/{mission_id}/audit-trail")
async def get_mission_audit_trail(
    mission_id: int,
    formato: str = Query("json", description="Formato del reporte: json, pdf"),
    db: Session = Depends(get_db_financiero),
    current_user = Depends(get_current_user_universal)
):
    """Obtener historial de auditoría de una misión"""
    # Obtener la misión
    mission = db.query(Mision).filter(Mision.id_mision == mission_id).first()
    if not mission:
        raise HTTPException(status_code=404, detail="Misión no encontrada")
    
    # Verificar permisos
    if not has_permission(current_user, "REPORT_EXPORT"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene permisos para ver el historial de auditoría"
        )
    
    report_service = ReportService(db, current_user)
    audit_data = report_service.generate_audit_trail(mission_id)
    
    if formato == "pdf":
        pdf_service = PDFReportService(db)
        
        # Aquí deberías implementar el método para generar PDF del audit trail
        # Por ahora retornamos JSON
        return audit_data
    
    return audit_data


@router.get("/missions/{mission_id}/detail")
async def get_mission_detail_report(
    mission_id: int,
    formato: str = Query("json", description="Formato del reporte: json, pdf"),
    db: Session = Depends(get_db_financiero),
    current_user = Depends(get_current_user_universal)
):
    """Obtener reporte detallado de una misión"""
    # Obtener la misión
    mission = db.query(Mision).filter(Mision.id_mision == mission_id).first()
    if not mission:
        raise HTTPException(status_code=404, detail="Misión no encontrada")
    
    # Verificar permisos
    if not has_permission(current_user, "REPORT_EXPORT"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene permisos para ver detalles de misiones"
        )
    
    if formato == "pdf":
        pdf_service = PDFReportService(db)
        pdf_file = pdf_service.generate_mission_detail_pdf(mission, include_audit_trail=True)
        
        filename = f"detalle_mision_{mission_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        
        return Response(
            content=pdf_file.getvalue(),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
    
    # Retornar datos en formato JSON
    return {
        "id_mision": mission.id_mision,
        "numero_solicitud": mission.numero_solicitud,
        "tipo_mision": mission.tipo_mision.value,
        "beneficiario": mission.beneficiario_nombre,
        "destino": mission.destino_mision,
        "objetivo": mission.objetivo_mision,
        "fecha_salida": mission.fecha_salida,
        "fecha_retorno": mission.fecha_retorno,
        "monto_total": float(mission.monto_total_calculado),
        "estado": mission.estado_flujo.nombre_estado,
        "items_viaticos": [
            {
                "fecha": item.fecha,
                "desayuno": float(item.monto_desayuno) if item.monto_desayuno else 0,
                "almuerzo": float(item.monto_almuerzo) if item.monto_almuerzo else 0,
                "cena": float(item.monto_cena) if item.monto_cena else 0,
                "hospedaje": float(item.monto_hospedaje) if item.monto_hospedaje else 0
            } for item in mission.items_viaticos
        ],
        "items_transporte": [
            {
                "fecha": item.fecha,
                "tipo": item.tipo.value,
                "origen": item.origen,
                "destino": item.destino,
                "monto": float(item.monto)
            } for item in mission.items_transporte
        ],
        "historial_flujo": [
            {
                "fecha": item.fecha_accion,
                "usuario": item.usuario_accion.login_username,
                "accion": str(item.tipo_accion) if hasattr(item.tipo_accion, 'value') else item.tipo_accion,
                "estado_anterior": item.estado_anterior.nombre_estado if item.estado_anterior else None,
                "estado_nuevo": item.estado_nuevo.nombre_estado,
                "comentarios": item.comentarios
            } for item in mission.historial_flujo
        ]
    }


@router.get("/dashboard")
async def get_dashboard_stats(
    db: Session = Depends(get_db_financiero),
    current_user = Depends(get_current_user_universal)
):
    """Obtener estadísticas del dashboard"""
    report_service = ReportService(db, current_user)
    return report_service.get_dashboard_stats(current_user)


@router.get("/caja-menuda/{mission_id}/pdf")
async def generate_caja_menuda_pdf(
    mission_id: int,
    db: Session = Depends(get_db_financiero),
    current_user = Depends(get_current_user_universal)
):
    """Generar reporte PDF de caja menuda"""
    # Obtener la misión
    mission = db.query(Mision).filter(Mision.id_mision == mission_id).first()
    if not mission:
        raise HTTPException(status_code=404, detail="Misión no encontrada")
    
    # Verificar que sea una misión de tipo caja menuda
    if mission.tipo_mision != TipoMision.CAJA_MENUDA:
        raise HTTPException(status_code=400, detail="La misión especificada no es de tipo caja menuda")
    
    # Obtener los datos de caja menuda asociados
    caja_menuda_items = db.query(MisionCajaMenuda).filter(
        MisionCajaMenuda.id_mision == mission_id
    ).all()
    
    if not caja_menuda_items:
        raise HTTPException(status_code=404, detail="No se encontraron datos de caja menuda para esta misión")
    
    # Verificar permisos específicos para reportes de caja menuda
    if not has_permission(current_user, "REPORT_EXPORT_CAJA"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene permisos para exportar reportes de caja menuda"
        )
    
    # Verificar permisos adicionales para empleados
    if isinstance(current_user, dict):
        # Para empleados, verificar que sea el beneficiario o tenga permisos de jefe
        if mission.beneficiario_personal_id != current_user.get('personal_id'):
            # Si no es el beneficiario, verificar si es jefe inmediato
            if not is_jefe_inmediato(current_user):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="No tiene permisos para ver esta caja menuda"
                )
    else:
        # Para usuarios financieros, verificar permisos específicos
        if hasattr(current_user, 'rol') and current_user.rol.nombre_rol == "Solicitante":
            if mission.beneficiario_personal_id != current_user.personal_id_rrhh:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="No tiene permisos para ver esta caja menuda"
                )
    
    # Comentado: Validación de estado removida para permitir exportación en cualquier momento
    # if mission.estado_flujo.nombre_estado != "PAGADO":
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN,
    #         detail="Solo se puede generar el reporte PDF de caja menuda para misiones con estado 'pagado'"
    #     )
    
    # Generar PDF
    pdf_service = PDFReportService(db)
    pdf_file = pdf_service.generate_caja_menuda_pdf(caja_menuda_items, mission, current_user)
    
    filename = f"caja_menuda_{mission_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    
    return Response(
        content=pdf_file.getvalue(),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )


@router.get("/missions/{mission_id}/viaticos/pdf")
async def generate_viaticos_pdf(
    mission_id: int,
    db: Session = Depends(get_db_financiero),
    current_user = Depends(get_current_user_universal)
):
    """Generar reporte PDF de viáticos"""
    # Obtener la misión
    mission = db.query(Mision).filter(Mision.id_mision == mission_id).first()
    if not mission:
        raise HTTPException(status_code=404, detail="Misión no encontrada")
    
    # Verificar permisos específicos para reportes de viáticos
    if not has_permission(current_user, "REPORT_EXPORT_VIATICOS"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene permisos para exportar reportes de viáticos"
        )

    # Verificar permisos adicionales para empleados
    if isinstance(current_user, dict):
        # Para empleados, verificar que sea el beneficiario o tenga permisos de jefe
        if mission.beneficiario_personal_id != current_user.get('personal_id'):
            # Si no es el beneficiario, verificar si es jefe inmediato
            if not is_jefe_inmediato(current_user):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="No tiene permisos para ver estos viáticos"
                )
    else:
        # Para usuarios financieros, verificar permisos específicos
        if hasattr(current_user, 'rol') and current_user.rol.nombre_rol == "Solicitante":
            if mission.beneficiario_personal_id != current_user.personal_id_rrhh:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="No tiene permisos para ver estos viáticos"
                )
    
    # Verificar que la misión tenga items de viáticos
    if not mission.items_viaticos:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se encontraron viáticos para esta misión"
        )
    
    # Comentado: Validación de estado removida para permitir exportación en cualquier momento
    # if mission.estado_flujo.nombre_estado != "PAGADO":
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN,
    #         detail="Solo se puede generar el reporte PDF de viáticos para misiones con estado 'pagado'"
    #     )
    
    # Generar PDF
    pdf_service = PDFReportService(db)
    pdf_file = pdf_service.generate_viaticos_pdf(mission, current_user)
    
    filename = f"viaticos_{mission_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    
    return Response(
        content=pdf_file.getvalue(),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )


@router.get("/missions/{mission_id}/transporte/pdf")
async def generate_transporte_pdf(
    mission_id: int,
    db: Session = Depends(get_db_financiero),
    current_user = Depends(get_current_user_universal)
):
    """Generar reporte PDF de transporte"""
    # Obtener la misión
    mission = db.query(Mision).filter(Mision.id_mision == mission_id).first()
    if not mission:
        raise HTTPException(status_code=404, detail="Misión no encontrada")
    
    # Verificar permisos específicos para reportes de transporte
    if not has_permission(current_user, "REPORT_EXPORT_VIATICOS"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene permisos para exportar reportes de transporte"
        )
    
    # Verificar permisos adicionales para empleados
    if isinstance(current_user, dict):
        # Para empleados, verificar que sea el beneficiario o tenga permisos de jefe
        if mission.beneficiario_personal_id != current_user.get('personal_id'):
            # Si no es el beneficiario, verificar si es jefe inmediato
            if not is_jefe_inmediato(current_user):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="No tiene permisos para ver este transporte"
                )
    else:
        # Para usuarios financieros, verificar permisos específicos
        if hasattr(current_user, 'rol') and current_user.rol.nombre_rol == "Solicitante":
            if mission.beneficiario_personal_id != current_user.personal_id_rrhh:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="No tiene permisos para ver este transporte"
                )
    
    # Verificar que la misión tenga items de transporte
    if not mission.items_transporte:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se encontró transporte para esta misión"
        )
    
    # Comentado: Validación de estado removida para permitir exportación en cualquier momento
    # if mission.estado_flujo.nombre_estado != "PAGADO":
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN,
    #         detail="Solo se puede generar el reporte PDF de transporte para misiones con estado 'pagado'"
    #     )
    
    # Generar PDF
    pdf_service = PDFReportService(db)
    pdf_file = pdf_service.generate_transporte_pdf(mission, current_user)
    
    filename = f"transporte_{mission_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    
    return Response(
        content=pdf_file.getvalue(),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )


@router.get("/missions/{mission_id}/viaticos-transporte/pdf")
async def generate_viaticos_transporte_pdf(
    mission_id: int,
    numero_solicitud: Optional[str] = Query(None, description="Número de solicitud personalizado"),
    db: Session = Depends(get_db_financiero),
    current_user = Depends(get_current_user_universal)
):
    """Generar reporte PDF de viáticos y transporte con formato oficial de Tocumen"""
    # Obtener la misión con estado_flujo cargado
    mission = db.query(Mision).options(joinedload(Mision.estado_flujo)).filter(Mision.id_mision == mission_id).first()
    if not mission:
        raise HTTPException(status_code=404, detail="Misión no encontrada")
    

    
    # Verificar permisos específicos para reportes de viáticos y transporte
    if not has_permission(current_user, "REPORT_EXPORT_VIATICOS"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene permisos para exportar reportes de viáticos y transporte"
        )
    
    # Verificar permisos adicionales para empleados
    if isinstance(current_user, dict):
        # Para empleados, verificar que sea el beneficiario o tenga permisos de jefe
        if mission.beneficiario_personal_id != current_user.get('personal_id'):
            # Si no es el beneficiario, verificar si es jefe inmediato
            if not is_jefe_inmediato(current_user):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="No tiene permisos para ver estos viáticos y transporte"
                )
    else:
        # Para usuarios financieros, verificar permisos específicos
        if hasattr(current_user, 'rol') and current_user.rol.nombre_rol == "Solicitante":
            if mission.beneficiario_personal_id != current_user.personal_id_rrhh:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="No tiene permisos para ver estos viáticos y transporte"
                )
    
    # Verificar que la misión tenga items de viáticos o transporte
    if not mission.items_viaticos and not mission.items_transporte:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se encontraron viáticos o transporte para esta misión"
        )
    
    # Comentado: Validación de estado removida para permitir exportación en cualquier momento
    # if mission.estado_flujo.nombre_estado != "PAGADO":
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN,
    #         detail="Solo se puede generar el reporte PDF de viáticos y transporte para misiones con estado 'pagado'"
    #     )
    
    # Generar PDF
    pdf_service = PDFReportViaticosService(db)
    pdf_file = pdf_service.generate_viaticos_transporte_pdf(mission, current_user, numero_solicitud)
    
    filename = f"viaticos_transporte_{mission_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    
    return Response(
        content=pdf_file.getvalue(),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )


@router.get("/employee/requests/{mission_id}/export/viaticos")
async def export_employee_viaticos(
    mission_id: int,
    numero_solicitud: Optional[str] = Query(None, description="Número de solicitud personalizado"),
    db: Session = Depends(get_db_financiero),
    current_user = Depends(get_current_user_universal)
):
    """Exportar solicitud de viáticos del empleado en PDF"""
    
    # Verificar que sea un empleado
    if not isinstance(current_user, dict):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Este endpoint es solo para empleados"
        )
    
    # Obtener la misión con estado_flujo cargado
    mission = db.query(Mision).options(joinedload(Mision.estado_flujo)).filter(Mision.id_mision == mission_id).first()
    if not mission:
        raise HTTPException(status_code=404, detail="Misión no encontrada")
    
    # Verificar que el empleado sea el beneficiario
    if mission.beneficiario_personal_id != current_user.get('personal_id'):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo puedes exportar tus propias solicitudes"
        )
    
    # Verificar que sea una misión de viáticos
    if mission.tipo_mision != TipoMision.VIATICOS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Esta misión no es de viáticos"
        )
    
    try:
        # Generar PDF de viáticos usando el servicio específico
        pdf_service = PDFReportViaticosService(db)
        pdf_buffer = pdf_service.generate_viaticos_transporte_pdf(mission, current_user, numero_solicitud)
        
        # Configurar headers para descarga
        filename = f"viaticos_{mission_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        
        return Response(
            content=pdf_buffer.getvalue(),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generando el PDF: {str(e)}"
        )


@router.get("/employee/requests/{mission_id}/export/caja-menuda")
async def export_employee_caja_menuda(
    mission_id: int,
    numero_solicitud: Optional[str] = Query(None, description="Número de solicitud personalizado"),
    db: Session = Depends(get_db_financiero),
    current_user = Depends(get_current_user_universal)
):
    """Exportar solicitud de caja menuda del empleado en PDF"""
    
    # Verificar que sea un empleado
    if not isinstance(current_user, dict):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Este endpoint es solo para empleados"
        )
    
    # Obtener la misión
    mission = db.query(Mision).filter(Mision.id_mision == mission_id).first()
    if not mission:
        raise HTTPException(status_code=404, detail="Misión no encontrada")
    
    # Verificar que el empleado sea el beneficiario
    if mission.beneficiario_personal_id != current_user.get('personal_id'):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo puedes exportar tus propias solicitudes"
        )
    
    # Verificar que sea una misión de caja menuda
    if mission.tipo_mision != TipoMision.CAJA_MENUDA:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Esta misión no es de caja menuda"
        )
    
    try:
        # Obtener los items de caja menuda
        caja_menuda_items = db.query(MisionCajaMenuda).filter(
            MisionCajaMenuda.id_mision == mission.id_mision
        ).all()
        
        if not caja_menuda_items:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No se encontraron datos de caja menuda para esta misión"
            )
        
        # Generar PDF de caja menuda
        pdf_service = PDFReportService(db)
        pdf_buffer = pdf_service.generate_caja_menuda_pdf(caja_menuda_items, mission, current_user)
        
        # Configurar headers para descarga
        filename = f"caja_menuda_{mission_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        
        return Response(
            content=pdf_buffer.getvalue(),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generando el PDF: {str(e)}"
        )