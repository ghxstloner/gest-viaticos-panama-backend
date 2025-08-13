from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.core.database import get_db_financiero
from app.schemas.notification import Notificacion, NotificacionVistoUpdate, NotificacionResponse, NotificacionCountResponse, NotificacionFilteredResponse
from app.services.notifaction_service import NotificationService
from app.api.deps import get_current_user, get_current_user_universal
from app.models.user import Usuario as UsuarioModel

router = APIRouter()

# === ENDPOINTS DE NOTIFICACIONES ===

@router.get("/", response_model=List[Notificacion])
async def get_notifications(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db_financiero),
    current_user = Depends(get_current_user_universal)
):
    """Get all notifications"""
    notification_service = NotificationService(db)
    return notification_service.get_notifications(skip=skip, limit=limit)

@router.get("/{notificacion_id}", response_model=Notificacion)
async def get_notification(
    notificacion_id: int,
    db: Session = Depends(get_db_financiero),
    current_user = Depends(get_current_user_universal)
):
    """Get notification by ID"""
    notification_service = NotificationService(db)
    notification = notification_service.get_notification(notificacion_id)
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )
    return notification

@router.get("/personal/{personal_id}", response_model=List[Notificacion])
async def get_notifications_by_personal_id(
    personal_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db_financiero),
    current_user = Depends(get_current_user_universal)
):
    """Get notifications by personal_id"""
    notification_service = NotificationService(db)
    return notification_service.get_notifications_by_personal_id(
        personal_id=personal_id, 
        skip=skip, 
        limit=limit
    )

@router.get("/personal/{personal_id}/unread", response_model=List[Notificacion])
async def get_unread_notifications_by_personal_id(
    personal_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db_financiero),
    current_user = Depends(get_current_user_universal)
):
    """Get unread notifications by personal_id"""
    notification_service = NotificationService(db)
    return notification_service.get_unread_notifications_by_personal_id(
        personal_id=personal_id, 
        skip=skip, 
        limit=limit
    )

@router.get("/mission/{id_mision}", response_model=List[Notificacion])
async def get_notifications_by_mission(
    id_mision: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db_financiero),
    current_user = Depends(get_current_user_universal)
):
    """Get notifications by mission ID"""
    notification_service = NotificationService(db)
    return notification_service.get_notifications_by_mission(
        id_mision=id_mision, 
        skip=skip, 
        limit=limit
    )

@router.put("/{notificacion_id}/visto", response_model=Notificacion)
async def mark_notification_as_read(
    notificacion_id: int,
    db: Session = Depends(get_db_financiero),
    current_user = Depends(get_current_user_universal)
):
    """Mark notification as read (visto = True)"""
    notification_service = NotificationService(db)
    return notification_service.mark_notification_as_read(notificacion_id)

@router.put("/{notificacion_id}/mark-read", response_model=Notificacion)
async def mark_notification_as_read(
    notificacion_id: int,
    db: Session = Depends(get_db_financiero),
    current_user = Depends(get_current_user_universal)
):
    """Mark notification as read"""
    notification_service = NotificationService(db)
    return notification_service.mark_notification_as_read(notificacion_id)

@router.put("/{notificacion_id}/mark-unread", response_model=Notificacion)
async def mark_notification_as_unread(
    notificacion_id: int,
    db: Session = Depends(get_db_financiero),
    current_user = Depends(get_current_user_universal)
):
    """Mark notification as unread"""
    notification_service = NotificationService(db)
    return notification_service.mark_notification_as_unread(notificacion_id)

@router.get("/personal/{personal_id}/count")
async def get_notification_count_by_personal_id(
    personal_id: int,
    unread_only: bool = Query(False, description="Count only unread notifications"),
    db: Session = Depends(get_db_financiero),
    current_user = Depends(get_current_user_universal)
):
    """Get notification count by personal_id"""
    notification_service = NotificationService(db)
    count = notification_service.get_notification_count_by_personal_id(
        personal_id=personal_id, 
        unread_only=unread_only
    )
    return {"personal_id": personal_id, "count": count, "unread_only": unread_only}

@router.get("/me/notifications", response_model=NotificacionResponse)
async def get_my_notifications(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db_financiero),
    current_user = Depends(get_current_user_universal)
):
    """
    Obtiene todas las notificaciones no vistas donde el usuario loggeado es el destinatario (personal_id)
    Incluye un contador con la cantidad total de notificaciones no vistas
    """
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no autenticado"
        )
    
    # Obtener personal_id según el tipo de usuario
    if isinstance(current_user, dict):
        # Para empleados
        personal_id = current_user.get('personal_id')
    else:
        # Para usuarios financieros
        personal_id = current_user.personal_id_rrhh
    
    if not personal_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se pudo obtener el personal_id del usuario"
        )
    
    notification_service = NotificationService(db)
    result = notification_service.get_notifications_for_logged_user_with_count(
        personal_id=personal_id,
        skip=skip,
        limit=limit
    )
    return result

@router.get("/me/notifications/with-missions", response_model=NotificacionResponse)
async def get_my_notifications_with_created_missions(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db_financiero),
    current_user = Depends(get_current_user_universal)
):
    """
    Obtiene todas las notificaciones no vistas donde el usuario loggeado es el destinatario (personal_id)
    más todas las notificaciones no vistas de las misiones que él creó (como beneficiario/solicitante)
    Incluye un contador con la cantidad total de notificaciones no vistas
    """
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no autenticado"
        )
    
    # Obtener personal_id según el tipo de usuario
    if isinstance(current_user, dict):
        # Para empleados
        personal_id = current_user.get('personal_id')
    else:
        # Para usuarios financieros
        personal_id = current_user.personal_id_rrhh
    
    if not personal_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se pudo obtener el personal_id del usuario"
        )
    
    notification_service = NotificationService(db)
    result = notification_service.get_notifications_for_logged_user_with_created_missions_with_count(
        personal_id=personal_id,
        skip=skip,
        limit=limit
    )
    return result

@router.get("/me/notifications/count", response_model=NotificacionCountResponse)
async def get_my_notification_count(
    db: Session = Depends(get_db_financiero),
    current_user = Depends(get_current_user_universal)
):
    """
    Obtiene el conteo de notificaciones no vistas donde el usuario loggeado es el destinatario
    """
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no autenticado"
        )
    
    # Obtener personal_id según el tipo de usuario
    if isinstance(current_user, dict):
        # Para empleados
        personal_id = current_user.get('personal_id')
    else:
        # Para usuarios financieros
        personal_id = current_user.personal_id_rrhh
    
    if not personal_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se pudo obtener el personal_id del usuario"
        )
    
    notification_service = NotificationService(db)
    count = notification_service.get_notification_count_for_logged_user(
        personal_id=personal_id,
        unread_only=True  # Solo no vistas
    )
    return {
        "personal_id": personal_id,
        "count": count,
        "unread_only": True
    }

@router.get("/me/notifications/with-missions/count", response_model=NotificacionCountResponse)
async def get_my_notification_count_with_created_missions(
    db: Session = Depends(get_db_financiero),
    current_user = Depends(get_current_user_universal)
):
    """
    Obtiene el conteo de notificaciones no vistas donde el usuario loggeado es el destinatario
    más las notificaciones no vistas de las misiones que él creó
    """
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no autenticado"
        )
    
    # Obtener personal_id según el tipo de usuario
    if isinstance(current_user, dict):
        # Para empleados
        personal_id = current_user.get('personal_id')
    else:
        # Para usuarios financieros
        personal_id = current_user.personal_id_rrhh
    
    if not personal_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se pudo obtener el personal_id del usuario"
        )
    
    notification_service = NotificationService(db)
    count = notification_service.get_notification_count_for_logged_user_with_created_missions(
        personal_id=personal_id,
        unread_only=True  # Solo no vistas
    )
    return {
        "personal_id": personal_id,
        "count": count,
        "unread_only": True
    }

@router.get("/me/all-notifications", response_model=NotificacionFilteredResponse)
async def get_all_my_notifications_with_filters(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    start_date: Optional[str] = Query(None, description="Fecha de inicio en formato YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="Fecha de fin en formato YYYY-MM-DD"),
    visto: Optional[bool] = Query(None, description="Filtrar por estado visto: true=leídas, false=no leídas, null=todas"),
    db: Session = Depends(get_db_financiero),
    current_user = Depends(get_current_user_universal)
):
    """
    Obtiene todas las notificaciones del usuario loggeado con filtros opcionales por fecha y estado visto
    
    - start_date: Fecha de inicio en formato YYYY-MM-DD (opcional)
    - end_date: Fecha de fin en formato YYYY-MM-DD (opcional)  
    - visto: Filtrar por estado visto (true=leídas, false=no leídas, null=todas)
    """
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no autenticado"
        )
    
    # Obtener personal_id según el tipo de usuario
    if isinstance(current_user, dict):
        # Para empleados
        personal_id = current_user.get('personal_id')
    else:
        # Para usuarios financieros
        personal_id = current_user.personal_id_rrhh
    
    if not personal_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se pudo obtener el personal_id del usuario"
        )
    
    notification_service = NotificationService(db)
    result = notification_service.get_all_notifications_for_logged_user_with_filters(
        personal_id=personal_id,
        skip=skip,
        limit=limit,
        start_date=start_date,
        end_date=end_date,
        visto=visto
    )
    return result

@router.get("/debug/auth-test")
async def debug_auth_test(
    current_user = Depends(get_current_user_universal)
):
    """
    Endpoint de debug para verificar que la autenticación funciona correctamente
    tanto para empleados como para usuarios financieros
    """
    if not current_user:
        return {
            "status": "error",
            "message": "Usuario no autenticado",
            "user_type": None,
            "personal_id": None
        }
    
    if isinstance(current_user, dict):
        # Para empleados
        return {
            "status": "success",
            "message": "Empleado autenticado correctamente",
            "user_type": "employee",
            "personal_id": current_user.get('personal_id'),
            "cedula": current_user.get('cedula'),
            "nombre": current_user.get('apenom'),
            "departamento": current_user.get('departamento')
        }
    else:
        # Para usuarios financieros
        return {
            "status": "success",
            "message": "Usuario financiero autenticado correctamente",
            "user_type": "financial_user",
            "personal_id": getattr(current_user, 'personal_id_rrhh', None),
            "username": getattr(current_user, 'login_username', None),
            "user_id": getattr(current_user, 'id_usuario', None)
        }
