from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File, BackgroundTasks
from sqlalchemy.orm import Session
from datetime import date
import os
import uuid

from ...core.database import get_db_financiero
from ...schemas.mission import (
    MisionCreate, MisionUpdate, MisionApprovalRequest, 
    MisionRejectionRequest, MisionListResponse, MisionDetail,
    SubsanacionRequest, SubsanacionResponse, GestionCobroCreate,
    AttachmentUpload, WorkflowState, Subsanacion
)
from ...models.mission import Mision
from ...services.mission import MissionService
from ...api.deps import get_current_user
from ...models.user import Usuario
from ...models.enums import TipoMision, TipoDocumento
from ...models.mission import Adjunto

router = APIRouter()

# Configuración de archivos
UPLOAD_DIR = "uploads/missions"
ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".png", ".jpg", ".jpeg"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/")
async def create_mission(
    mission_data: MisionCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db_financiero),
    current_user: Usuario = Depends(get_current_user)
):
    """Crear nueva misión/solicitud"""
    try:
        mission_service = MissionService(db)
        
        # Si no se especifica el beneficiario, usar el usuario actual
        if not mission_data.beneficiario_personal_id:
            if not current_user.personal_id_rrhh:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="El usuario no tiene un ID de personal asociado"
                )
            mission_data.beneficiario_personal_id = current_user.personal_id_rrhh
        
        mission = mission_service.create_mission(mission_data, current_user.id_usuario)
        
        # Programar notificación en segundo plano
        background_tasks.add_task(
            send_mission_notification, 
            mission.id_mision, 
            "created",
            db
        )
        
        return {
            "success": True,
            "message": "Solicitud creada exitosamente",
            "data": {
                "id_mision": mission.id_mision,
                "numero_solicitud": f"SOL-{mission.id_mision:06d}",
                "estado": mission.estado_flujo.nombre_estado,
                "monto_total": float(mission.monto_total_calculado)
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/")
async def get_missions(
    page: int = Query(1, ge=1),
    size: int = Query(100, ge=1, le=1000),
    estado_id: Optional[int] = None,
    tipo_mision: Optional[TipoMision] = None,
    fecha_desde: Optional[date] = None,
    fecha_hasta: Optional[date] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db_financiero),
    current_user: Usuario = Depends(get_current_user)
):
    """Obtener lista de misiones con filtros"""
    try:
        mission_service = MissionService(db)
        skip = (page - 1) * size
        
        result = mission_service.get_missions(
            user=current_user,
            skip=skip,
            limit=size,
            estado_id=estado_id,
            tipo_mision=tipo_mision,
            fecha_desde=fecha_desde,
            fecha_hasta=fecha_hasta
        )
        
        # Transformar misiones a formato de respuesta
        missions_data = []
        for mission in result["items"]:
            missions_data.append({
                "id_mision": mission.id_mision,
                "numero_solicitud": f"SOL-{mission.id_mision:06d}",
                "tipo_mision": mission.tipo_mision,
                "destino_mision": mission.destino_mision,
                "fecha_salida": mission.fecha_salida.isoformat(),
                "fecha_retorno": mission.fecha_retorno.isoformat(),
                "monto_total_calculado": float(mission.monto_total_calculado),
                "estado_flujo": {
                    "id_estado_flujo": mission.estado_flujo.id_estado_flujo,
                    "nombre_estado": mission.estado_flujo.nombre_estado,
                    "descripcion": mission.estado_flujo.descripcion
                },
                "created_at": mission.created_at.isoformat() if mission.created_at else None,
                "requiere_refrendo_cgr": mission.requiere_refrendo_cgr
            })
        
        return {
            "items": missions_data,
            "total": result["total"],
            "page": result["page"],
            "size": result["size"],
            "pages": result["pages"]
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/states", response_model=List[WorkflowState])
async def get_workflow_states(
    db: Session = Depends(get_db_financiero),
    current_user: Usuario = Depends(get_current_user)
):
    """Obtener estados del flujo de trabajo"""
    from ...models.mission import EstadoFlujo
    
    estados = db.query(EstadoFlujo).order_by(EstadoFlujo.orden_flujo).all()
    return estados


@router.get("/calculate-viaticos")
async def calculate_viaticos(
    fecha_salida: date,
    fecha_retorno: date,
    destino: str,
    db: Session = Depends(get_db_financiero),
    current_user: Usuario = Depends(get_current_user)
):
    """Calcular montos de viáticos"""
    if fecha_retorno < fecha_salida:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La fecha de retorno no puede ser anterior a la fecha de salida"
        )
    
    mission_service = MissionService(db)
    return mission_service.calculate_viaticos(fecha_salida, fecha_retorno, destino)


@router.get("/{mission_id}", response_model=MisionDetail)
async def get_mission(
    mission_id: int,
    db: Session = Depends(get_db_financiero),
    current_user: Usuario = Depends(get_current_user)
):
    """Obtener detalle de una misión"""
    mission_service = MissionService(db)
    return mission_service.get_mission_detail(mission_id, current_user)


@router.put("/{mission_id}", response_model=Mision)
async def update_mission(
    mission_id: int,
    mission_data: MisionUpdate,
    db: Session = Depends(get_db_financiero),
    current_user: Usuario = Depends(get_current_user)
):
    """Actualizar misión (solo en estado inicial)"""
    mission_service = MissionService(db)
    
    # Verificar que existe
    mission = db.query(Mision).filter(Mision.id_mision == mission_id).first()
    if not mission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Misión no encontrada"
        )
    
    # Verificar permisos
    if mission.beneficiario_personal_id != current_user.personal_id_rrhh:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene permisos para editar esta misión"
        )
    
    # Verificar estado
    if mission.estado_flujo.nombre_estado != "PENDIENTE_REVISION_TESORERIA":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solo se pueden editar misiones en estado inicial"
        )
    
    # Actualizar
    for field, value in mission_data.model_dump(exclude_unset=True).items():
        setattr(mission, field, value)
    
    db.commit()
    db.refresh(mission)
    return mission


@router.delete("/{mission_id}")
async def delete_mission(
    mission_id: int,
    db: Session = Depends(get_db_financiero),
    current_user: Usuario = Depends(get_current_user)
):
    """Eliminar misión (solo en estado inicial sin historial)"""
    mission = db.query(Mision).filter(Mision.id_mision == mission_id).first()
    if not mission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Misión no encontrada"
        )
    
    # Verificar permisos y estado
    if mission.beneficiario_personal_id != current_user.personal_id_rrhh:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene permisos para eliminar esta misión"
        )
    
    if mission.estado_flujo.nombre_estado != "PENDIENTE_REVISION_TESORERIA":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solo se pueden eliminar misiones en estado inicial"
        )
    
    if mission.historial_flujo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se pueden eliminar misiones con historial de acciones"
        )
    
    db.delete(mission)
    db.commit()
    
    return {"message": "Misión eliminada exitosamente"}


@router.post("/{mission_id}/approve", response_model=Mision)
async def approve_mission(
    mission_id: int,
    approval_data: MisionApprovalRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db_financiero),
    current_user: Usuario = Depends(get_current_user)
):
    """Aprobar misión y avanzar al siguiente estado"""
    mission_service = MissionService(db)
    mission = mission_service.approve_mission(mission_id, current_user.id_usuario, approval_data)
    
    # Notificar cambio de estado
    background_tasks.add_task(
        send_mission_notification,
        mission_id,
        "approved",
        db
    )
    
    return mission


@router.post("/{mission_id}/reject", response_model=Mision)
async def reject_mission(
    mission_id: int,
    rejection_data: MisionRejectionRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db_financiero),
    current_user: Usuario = Depends(get_current_user)
):
    """Rechazar/devolver misión para corrección"""
    mission_service = MissionService(db)
    mission = mission_service.reject_mission(mission_id, current_user.id_usuario, rejection_data)
    
    # Notificar devolución
    background_tasks.add_task(
        send_mission_notification,
        mission_id,
        "rejected",
        db
    )
    
    return mission


@router.post("/{mission_id}/generate-gestion-cobro")
async def generate_gestion_cobro(
    mission_id: int,
    data: GestionCobroCreate,
    db: Session = Depends(get_db_financiero),
    current_user: Usuario = Depends(get_current_user)
):
    """Generar gestión de cobro"""
    # Verificar rol
    if current_user.rol.nombre_rol not in ["Analista Tesorería", "Director Finanzas"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo Tesorería puede generar gestiones de cobro"
        )
    
    mission_service = MissionService(db)
    return mission_service.generate_gestion_cobro(mission_id, current_user.id_usuario, data)


@router.get("/{mission_id}/subsanations", response_model=List[Subsanacion])
async def get_mission_subsanations(
    mission_id: int,
    db: Session = Depends(get_db_financiero),
    current_user: Usuario = Depends(get_current_user)
):
    """Obtener subsanaciones de una misión"""
    subsanations = db.query(Subsanacion).filter(
        Subsanacion.id_mision == mission_id
    ).order_by(Subsanacion.fecha_solicitud.desc()).all()
    
    return subsanations


@router.post("/subsanations/{subsanation_id}/complete", response_model=SubsanacionResponse)
async def complete_subsanation(
    subsanation_id: int,
    data: SubsanacionRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db_financiero),
    current_user: Usuario = Depends(get_current_user)
):
    """Completar una subsanación"""
    mission_service = MissionService(db)
    result = mission_service.complete_subsanation(
        subsanation_id, 
        current_user.id_usuario,
        data.respuesta
    )
    
    # Notificar completación
    background_tasks.add_task(
        send_subsanation_notification,
        subsanation_id,
        "completed",
        db
    )
    
    return result


@router.post("/{mission_id}/attachments", response_model=AttachmentUpload)
async def upload_attachment(
    mission_id: int,
    file: UploadFile = File(...),
    tipo_documento: TipoDocumento = Query(TipoDocumento.OTRO),
    db: Session = Depends(get_db_financiero),
    current_user: Usuario = Depends(get_current_user)
):
    """Subir archivo adjunto a una misión"""
    # Verificar que la misión existe
    mission = db.query(Mision).filter(Mision.id_mision == mission_id).first()
    if not mission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Misión no encontrada"
        )
    
    # Validar extensión
    file_extension = os.path.splitext(file.filename)[1].lower()
    if file_extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tipo de archivo no permitido. Extensiones válidas: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    
    # Validar tamaño
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Archivo muy grande. Tamaño máximo: {MAX_FILE_SIZE // (1024 * 1024)}MB"
        )
    
    # Generar nombre único
    unique_filename = f"{mission_id}_{uuid.uuid4()}{file_extension}"
    file_path = os.path.join(UPLOAD_DIR, unique_filename)
    
    # Guardar archivo
    with open(file_path, "wb") as buffer:
        buffer.write(contents)
    
    # Crear registro en BD
    attachment = Adjunto(
        id_mision=mission_id,
        nombre_archivo=unique_filename,
        nombre_original=file.filename,
        url_almacenamiento=f"/uploads/missions/{unique_filename}",
        tipo_mime=file.content_type,
        tamano_bytes=len(contents),
        tipo_documento=tipo_documento,
        id_usuario_subio=current_user.id_usuario
    )
    
    db.add(attachment)
    db.commit()
    db.refresh(attachment)
    
    return AttachmentUpload(
        id_adjunto=attachment.id_adjunto,
        nombre_archivo=attachment.nombre_original,
        url=attachment.url_almacenamiento
    )


@router.get("/{mission_id}/attachments")
async def get_attachments(
    mission_id: int,
    db: Session = Depends(get_db_financiero),
    current_user: Usuario = Depends(get_current_user)
):
    """Obtener archivos adjuntos de una misión"""
    attachments = db.query(Adjunto).filter(
        Adjunto.id_mision == mission_id
    ).order_by(Adjunto.fecha_carga.desc()).all()
    
    return attachments


@router.delete("/attachments/{attachment_id}")
async def delete_attachment(
    attachment_id: int,
    db: Session = Depends(get_db_financiero),
    current_user: Usuario = Depends(get_current_user)
):
    """Eliminar archivo adjunto"""
    attachment = db.query(Adjunto).filter(
        Adjunto.id_adjunto == attachment_id
    ).first()
    
    if not attachment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Archivo no encontrado"
        )
    
    # Verificar permisos
    if attachment.id_usuario_subio != current_user.id_usuario and current_user.rol.nombre_rol != "Administrador Sistema":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene permisos para eliminar este archivo"
        )
    
    # Eliminar archivo físico
    file_path = f".{attachment.url_almacenamiento}"
    if os.path.exists(file_path):
        os.remove(file_path)
    
    # Eliminar registro
    db.delete(attachment)
    db.commit()
    
    return {"message": "Archivo eliminado exitosamente"}


# Funciones auxiliares para notificaciones
async def send_mission_notification(mission_id: int, action: str, db: Session):
    """Enviar notificación sobre cambio en misión"""
    # TODO: Implementar envío real de notificaciones
    print(f"Notificación: Misión {mission_id} - Acción: {action}")


async def send_subsanation_notification(subsanation_id: int, action: str, db: Session):
    """Enviar notificación sobre subsanación"""
    # TODO: Implementar envío real de notificaciones
    print(f"Notificación: Subsanación {subsanation_id} - Acción: {action}")


# ======== ENDPOINTS ESPECÍFICOS PARA FLUJOS DE SIRCEL ========

@router.post("/{mission_id}/proceso-tesoreria")
async def process_tesoreria_action(
    mission_id: int,
    action: str = Query(..., description="APROBAR, RECHAZAR, DEVOLVER"),
    comentarios: str = Query(None, description="Comentarios opcionales"),
    db: Session = Depends(get_db_financiero),
    current_user: Usuario = Depends(get_current_user)
):
    """Procesar acción de Tesorería en el flujo SIRCEL"""
    if current_user.id_rol != 3:  # Analista Tesorería
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo el personal de Tesorería puede realizar esta acción"
        )
    
    try:
        mission_service = MissionService(db)
        mission = mission_service.process_workflow_action(
            mission_id=mission_id,
            user=current_user,
            action=action.upper(),
            comentarios=comentarios
        )
        
        return {
            "success": True,
            "message": f"Acción {action} procesada exitosamente",
            "data": {
                "nuevo_estado": mission.estado_flujo.nombre_estado,
                "requiere_gestion_cobro": action.upper() == "APROBAR" and mission.tipo_mision == "VIATICOS"
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/{mission_id}/proceso-presupuesto")
async def process_presupuesto_action(
    mission_id: int,
    action: str = Query(..., description="APROBAR, RECHAZAR, DEVOLVER"),
    codigo_presupuestario: str = Query(None, description="Código presupuestario"),
    comentarios: str = Query(None, description="Comentarios opcionales"),
    db: Session = Depends(get_db_financiero),
    current_user: Usuario = Depends(get_current_user)
):
    """Procesar acción de Presupuesto en el flujo SIRCEL"""
    if current_user.id_rol != 5:  # Analista Presupuesto
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo el personal de Presupuesto puede realizar esta acción"
        )
    
    try:
        mission_service = MissionService(db)
        mission = mission_service.process_workflow_action(
            mission_id=mission_id,
            user=current_user,
            action=action.upper(),
            comentarios=comentarios
        )
        
        # Si aprueba, asignar código presupuestario
        if action.upper() == "APROBAR" and codigo_presupuestario:
            # Actualizar gestión de cobro con código presupuestario
            gestion = db.query(GestionCobro).filter(
                GestionCobro.id_mision == mission_id
            ).first()
            if gestion:
                gestion.codigo_presupuestario = codigo_presupuestario
                db.commit()
        
        return {
            "success": True,
            "message": f"Acción {action} procesada exitosamente por Presupuesto",
            "data": {
                "nuevo_estado": mission.estado_flujo.nombre_estado,
                "codigo_presupuestario": codigo_presupuestario if action.upper() == "APROBAR" else None
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/{mission_id}/proceso-contabilidad")
async def process_contabilidad_action(
    mission_id: int,
    action: str = Query(..., description="APROBAR, RECHAZAR, DEVOLVER"),
    asiento_contable: str = Query(None, description="Número de asiento contable"),
    comentarios: str = Query(None, description="Comentarios opcionales"),
    db: Session = Depends(get_db_financiero),
    current_user: Usuario = Depends(get_current_user)
):
    """Procesar acción de Contabilidad en el flujo SIRCEL"""
    if current_user.id_rol != 6:  # Analista Contabilidad
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo el personal de Contabilidad puede realizar esta acción"
        )
    
    try:
        mission_service = MissionService(db)
        mission = mission_service.process_workflow_action(
            mission_id=mission_id,
            user=current_user,
            action=action.upper(),
            comentarios=comentarios
        )
        
        return {
            "success": True,
            "message": f"Acción {action} procesada exitosamente por Contabilidad",
            "data": {
                "nuevo_estado": mission.estado_flujo.nombre_estado,
                "asiento_contable": asiento_contable if action.upper() == "APROBAR" else None
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/{mission_id}/proceso-director-finanzas")
async def process_director_finanzas_action(
    mission_id: int,
    action: str = Query(..., description="APROBAR, RECHAZAR, DEVOLVER"),
    comentarios: str = Query(None, description="Comentarios del director"),
    db: Session = Depends(get_db_financiero),
    current_user: Usuario = Depends(get_current_user)
):
    """Procesar acción del Director de Finanzas en el flujo SIRCEL"""
    if current_user.id_rol != 7:  # Director Finanzas
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo el Director de Finanzas puede realizar esta acción"
        )
    
    try:
        mission_service = MissionService(db)
        mission = mission_service.process_workflow_action(
            mission_id=mission_id,
            user=current_user,
            action=action.upper(),
            comentarios=comentarios
        )
        
        return {
            "success": True,
            "message": f"Acción {action} procesada exitosamente por Director de Finanzas",
            "data": {
                "nuevo_estado": mission.estado_flujo.nombre_estado,
                "requiere_refrendo_cgr": mission.requiere_refrendo_cgr,
                "firma_director": action.upper() == "APROBAR"
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/{mission_id}/proceso-cgr")
async def process_cgr_action(
    mission_id: int,
    action: str = Query(..., description="APROBAR, RECHAZAR, SUBSANAR"),
    comentarios: str = Query(None, description="Comentarios del fiscalizador"),
    db: Session = Depends(get_db_financiero),
    current_user: Usuario = Depends(get_current_user)
):
    """Procesar acción del Fiscalizador CGR en el flujo SIRCEL"""
    if current_user.id_rol != 8:  # Fiscalizador CGR
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo el Fiscalizador de CGR puede realizar esta acción"
        )
    
    try:
        mission_service = MissionService(db)
        mission = mission_service.process_workflow_action(
            mission_id=mission_id,
            user=current_user,
            action=action.upper(),
            comentarios=comentarios
        )
        
        return {
            "success": True,
            "message": f"Refrendo CGR: {action} procesado exitosamente",
            "data": {
                "nuevo_estado": mission.estado_flujo.nombre_estado,
                "refrendo_cgr": action.upper() == "APROBAR",
                "requiere_subsanacion": action.upper() == "SUBSANAR"
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/{mission_id}/proceso-pago")
async def process_payment(
    mission_id: int,
    tipo_pago: str = Query(..., description="TRANSFERENCIA, EFECTIVO"),
    numero_transferencia: str = Query(None, description="Número de transferencia"),
    comentarios: str = Query(None, description="Comentarios del pago"),
    db: Session = Depends(get_db_financiero),
    current_user: Usuario = Depends(get_current_user)
):
    """Procesar pago final en el flujo SIRCEL"""
    if current_user.id_rol not in [3, 4]:  # Tesorería o Custodio Caja
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo personal autorizado puede procesar pagos"
        )
    
    try:
        mission_service = MissionService(db)
        mission = mission_service.process_workflow_action(
            mission_id=mission_id,
            user=current_user,
            action="PAGAR",
            comentarios=f"Pago {tipo_pago}: {comentarios or ''}"
        )
        
        return {
            "success": True,
            "message": f"Pago procesado exitosamente: {tipo_pago}",
            "data": {
                "nuevo_estado": mission.estado_flujo.nombre_estado,
                "tipo_pago": tipo_pago,
                "numero_transferencia": numero_transferencia,
                "monto_pagado": float(mission.monto_total_calculado)
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/mis-solicitudes")
async def get_my_requests(
    page: int = Query(1, ge=1),
    size: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db_financiero),
    current_user: Usuario = Depends(get_current_user)
):
    """Obtener solicitudes del usuario actual (para empleados)"""
    if not current_user.personal_id_rrhh:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Usuario no tiene ID de personal asociado"
        )
    
    try:
        mission_service = MissionService(db)
        skip = (page - 1) * size
        
        result = mission_service.get_missions(
            user=current_user,
            skip=skip,
            limit=size
        )
        
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )