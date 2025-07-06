# ===============================================================
# app/api/v1/missions.py (COMPLETO Y FINAL)
# ===============================================================

import os
import uuid
from typing import List, Optional
from datetime import date

from fastapi import (
    APIRouter, Depends, HTTPException, status, Query,
    UploadFile, File, BackgroundTasks, Body
)
from sqlalchemy.orm import Session

from ...core.database import get_db_financiero
from ...core.exceptions import BusinessException, MissionException, WorkflowException, ValidationException
from ...services.mission import MissionService
from ...api.deps import get_current_user

from ...models.mission import Mision as MisionModel, Adjunto, EstadoFlujo
from ...models.user import Usuario
from ...models.enums import TipoMision, TipoDocumento, TipoAccion

from ...schemas.mission import (
    MisionCreate, MisionUpdate, MisionListResponse, MisionDetail,
    MisionListResponseItem, AttachmentUpload, WorkflowState,
    PresupuestoAssignRequest, MisionRejectionRequest, MisionApprovalRequest
)


router = APIRouter(
    prefix="/missions",
    tags=["Missions"],
)

# --- Configuración de Archivos ---
UPLOAD_DIR = "uploads/missions"
ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".png", ".jpg", ".jpeg"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

os.makedirs(UPLOAD_DIR, exist_ok=True)


# --- Endpoints Principales de Misiones ---

@router.post("/", status_code=status.HTTP_201_CREATED, summary="Crear una nueva misión")
async def create_mission(
    mission_data: MisionCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db_financiero),
    current_user: Usuario = Depends(get_current_user)
):
    """
    Crea una nueva solicitud, ya sea para **Viáticos** o para **Caja Menuda**.
    El `tipo_mision` determina qué campos son requeridos.
    """
    try:
        mission_service = MissionService(db)
        
        # Si el beneficiario no se especifica, se asume que es el usuario que crea la solicitud.
        if not mission_data.beneficiario_personal_id:
            if not current_user.personal_id_rrhh:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="El usuario actual no tiene un ID de personal de RRHH asociado para ser beneficiario."
                )
            mission_data.beneficiario_personal_id = current_user.personal_id_rrhh
        
        mission = mission_service.create_mission(
            mission_data=mission_data,
            preparer_id=current_user.id_usuario
        )
        
        # TODO: Implementar notificaciones en segundo plano
        # background_tasks.add_task(send_notification, mission.id_mision, "created")
        
        return {
            "success": True,
            "message": "Solicitud creada exitosamente.",
            "data": {
                "id_mision": mission.id_mision,
                "numero_solicitud": mission.numero_solicitud,
                "estado": mission.estado_flujo.nombre_estado,
                "monto_total": float(mission.monto_total_calculado)
            }
        }
    except (ValidationException, ValueError) as ve:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(ve))
    except BusinessException as be:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(be))
    except Exception as e:
        # Loggear el error en un sistema de monitoreo
        print(f"Error inesperado al crear misión: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Ocurrió un error interno.")


@router.get("/", response_model=MisionListResponse, summary="Obtener lista de misiones")
async def get_missions(
    page: int = Query(1, ge=1),
    size: int = Query(100, ge=1, le=1000),
    estado_id: Optional[int] = Query(None, description="Filtrar por ID de estado de flujo"),
    tipo_mision: Optional[TipoMision] = Query(None, description="Filtrar por tipo de misión"),
    fecha_desde: Optional[date] = Query(None),
    fecha_hasta: Optional[date] = Query(None),
    db: Session = Depends(get_db_financiero),
    current_user: Usuario = Depends(get_current_user)
):
    """
    Obtiene una lista paginada de misiones. Los resultados se filtran
    automáticamente según los permisos del rol del usuario actual.
    - **Jefes Inmediatos**: Ven las solicitudes de los empleados en sus departamentos.
    - **Solicitantes**: Ven solo sus propias solicitudes.
    - **Roles Financieros/Admin**: Ven todas las solicitudes.
    """
    mission_service = MissionService(db)
    result = mission_service.get_missions(
        user=current_user, skip=(page - 1) * size, limit=size, estado_id=estado_id,
        tipo_mision=tipo_mision, fecha_desde=fecha_desde, fecha_hasta=fecha_hasta
    )
    
    response_items = [MisionListResponseItem.model_validate(m) for m in result["items"]]
    
    return MisionListResponse(
        items=response_items,
        total=result["total"],
        page=result["page"],
        size=result["size"],
        pages=result["pages"]
    )


@router.get("/{mission_id}", response_model=MisionDetail, summary="Obtener detalle de una misión")
async def get_mission(
    mission_id: int,
    db: Session = Depends(get_db_financiero),
    current_user: Usuario = Depends(get_current_user)
):
    """
    Obtiene el detalle completo de una misión, incluyendo ítems, historial,
    datos del beneficiario y las acciones disponibles para el usuario actual.
    """
    try:
        mission_service = MissionService(db)
        return mission_service.get_mission_detail(mission_id, current_user)
    except MissionException as me:
        raise HTTPException(status_code=me.status_code, detail=str(me))
    except Exception as e:
        print(f"Error inesperado al obtener detalle de misión: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Ocurrió un error interno.")


# --- Endpoints para Acciones del Flujo de Trabajo ---

@router.post("/{mission_id}/approve", summary="Aprobar una misión")
async def approve_mission(
    mission_id: int,
    data: MisionApprovalRequest,
    db: Session = Depends(get_db_financiero),
    current_user: Usuario = Depends(get_current_user)
):
    """Endpoint genérico para aprobar y avanzar una misión al siguiente estado."""
    try:
        service = MissionService(db)
        mission = service.process_workflow_action(
            mission_id=mission_id, user=current_user, action=TipoAccion.APROBAR,
            comentarios=data.comentarios, datos_adicionales=data.datos_adicionales
        )
        return {"success": True, "message": "Misión aprobada.", "new_state": mission.estado_flujo.nombre_estado}
    except (WorkflowException, MissionException) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{mission_id}/reject", summary="Rechazar una misión")
async def reject_mission(
    mission_id: int,
    data: MisionRejectionRequest,
    db: Session = Depends(get_db_financiero),
    current_user: Usuario = Depends(get_current_user)
):
    """Rechaza una misión, moviéndola a un estado final de 'RECHAZADO'."""
    try:
        service = MissionService(db)
        mission = service.process_workflow_action(
            mission_id=mission_id, user=current_user, action=TipoAccion.RECHAZAR,
            comentarios=f"Motivo: {data.motivo}. {data.comentarios or ''}"
        )
        return {"success": True, "message": "Misión rechazada.", "new_state": mission.estado_flujo.nombre_estado}
    except (WorkflowException, MissionException) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{mission_id}/return", summary="Devolver una misión para corrección")
async def return_mission(
    mission_id: int,
    data: MisionRejectionRequest, # Reutilizamos el schema para el motivo
    db: Session = Depends(get_db_financiero),
    current_user: Usuario = Depends(get_current_user)
):
    """Devuelve una misión al solicitante para que la corrija."""
    try:
        service = MissionService(db)
        mission = service.process_workflow_action(
            mission_id=mission_id, user=current_user, action=TipoAccion.DEVOLVER,
            comentarios=f"Motivo de devolución: {data.motivo}. {data.comentarios or ''}"
        )
        return {"success": True, "message": "Misión devuelta para corrección.", "new_state": mission.estado_flujo.nombre_estado}
    except (WorkflowException, MissionException) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{mission_id}/assign-budget", summary="Asignar partidas presupuestarias")
async def assign_budget(
    mission_id: int,
    data: PresupuestoAssignRequest,
    db: Session = Depends(get_db_financiero),
    current_user: Usuario = Depends(get_current_user)
):
    """
    Endpoint específico para que Presupuesto asigne las partidas
    y apruebe la solicitud para continuar el flujo.
    """
    if current_user.rol.nombre_rol != "Analista Presupuesto":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acción no permitida para este rol.")
    try:
        service = MissionService(db)
        mission = service.assign_budget_items(mission_id, data, current_user)
        return {"success": True, "message": "Partidas asignadas y flujo avanzado.", "new_state": mission.estado_flujo.nombre_estado}
    except (WorkflowException, MissionException) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# --- Endpoints de Utilidad ---

@router.get("/states/", response_model=List[WorkflowState], summary="Obtener todos los estados de flujo")
async def get_workflow_states(db: Session = Depends(get_db_financiero)):
    """Obtiene la lista de todos los posibles estados del flujo de trabajo."""
    return db.query(EstadoFlujo).order_by(EstadoFlujo.orden_flujo).all()


@router.post("/{mission_id}/attachments/", response_model=AttachmentUpload, summary="Subir un archivo adjunto")
async def upload_attachment(
    mission_id: int,
    file: UploadFile = File(...),
    tipo_documento: TipoDocumento = Query(TipoDocumento.OTRO),
    db: Session = Depends(get_db_financiero),
    current_user: Usuario = Depends(get_current_user)
):
    """Sube un archivo y lo asocia a una misión existente."""
    mission = db.query(MisionModel).filter(MisionModel.id_mision == mission_id).first()
    if not mission:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Misión no encontrada")

    file_extension = os.path.splitext(file.filename)[1].lower()
    if file_extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Tipo de archivo no permitido.")

    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Archivo demasiado grande.")

    unique_filename = f"{mission_id}_{uuid.uuid4()}{file_extension}"
    file_path = os.path.join(UPLOAD_DIR, unique_filename)

    with open(file_path, "wb") as buffer:
        buffer.write(contents)

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

    return attachment
