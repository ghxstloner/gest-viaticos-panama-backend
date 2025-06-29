from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ...core.database import get_db_financiero
from ...schemas.mission import Mision, MisionApprovalRequest, MisionRejectionRequest
from ...services.mission import MissionService
from ...api.deps import get_current_user
# ✅ CORRECCIÓN: usar user en minúscula
from ...models.user import Usuario

router = APIRouter()


@router.get("/", response_model=List[Mision])
async def get_missions(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db_financiero),
    current_user: Usuario = Depends(get_current_user)
):
    """Get missions"""
    return []


@router.get("/{mission_id}", response_model=Mision)
async def get_mission(
    mission_id: int,
    db: Session = Depends(get_db_financiero),
    current_user: Usuario = Depends(get_current_user)
):
    """Get mission by ID"""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Not implemented yet"
    )


@router.post("/{mission_id}/approve", response_model=Mision)
async def approve_mission(
    mission_id: int,
    approval_data: MisionApprovalRequest,
    db: Session = Depends(get_db_financiero),
    current_user: Usuario = Depends(get_current_user)
):
    """Approve mission"""
    mission_service = MissionService(db)
    return mission_service.approve_mission(mission_id, current_user.id_usuario, approval_data)


@router.post("/{mission_id}/reject", response_model=Mision)
async def reject_mission(
    mission_id: int,
    rejection_data: MisionRejectionRequest,
    db: Session = Depends(get_db_financiero),
    current_user: Usuario = Depends(get_current_user)
):
    """Reject mission"""
    mission_service = MissionService(db)
    return mission_service.reject_mission(mission_id, current_user.id_usuario, rejection_data)