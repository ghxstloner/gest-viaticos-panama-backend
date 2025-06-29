from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.orm import Session

from ...core.database import get_db
from ...core.config import settings
from ...schemas.mission import WebhookMisionAprobada, Mision
from ...services.mission import MissionService

router = APIRouter()


@router.post("/rrhh/mission-approved", response_model=dict)
async def handle_mission_approved(
    payload: WebhookMisionAprobada,
    db: Session = Depends(get_db),
    x_webhook_secret: str = Header(None)
):
    """Handle webhook for mission approved from RRHH"""
    # Validate webhook secret
    if x_webhook_secret != settings.WEBHOOK_SECRET_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook token"
        )

    try:
        mission_service = MissionService(db)
        mission = mission_service.process_approved_mission_webhook(payload)
        
        return {
            "success": True,
            "message": "Mission processed successfully",
            "data": {
                "mission_id": mission.id_mision,
                "estado": mission.estado_flujo.nombre_estado
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )