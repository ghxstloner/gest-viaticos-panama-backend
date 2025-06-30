from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File, BackgroundTasks
from sqlalchemy.orm import Session
from datetime import date
import os
import uuid

from ...core.database import get_db_financiero
from ...schemas.mission import (
    Mision, MisionCreate, MisionUpdate, MisionApprovalRequest, 
    MisionRejectionRequest, MisionListResponse, MisionDetail,
    SubsanacionRequest, SubsanacionResponse, GestionCobroCreate,
    AttachmentUpload, WorkflowState, Subsanacion
)
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


@router.post("/", response_model=Mision)
async def create_mission(
    mission_data: MisionCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db_financiero),
    current_user: Usuario = Depends(get_current_user)
):
    """Crear nueva misión/solicitud"""
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
    
    return mission


@router.get("/", response_model=MisionListResponse)
async def get_missions(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    estado_id: Optional[int] = None,
    tipo_mision: Optional[TipoMision] = None,
    fecha_desde: Optional[date] = None,
    fecha_hasta: Optional[date] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db_financiero),
    current_user: Usuario = Depends(get_current_user)
):
    """Obtener lista de misiones con filtros"""
    mission_service = MissionService(db)
    return mission_service.get_missions(
        user=current_user,
        skip=skip,
        limit=limit,
        estado_id=estado_id,
        tipo_mision=tipo_mision,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta
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