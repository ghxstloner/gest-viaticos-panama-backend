from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ...core.database import get_db
from ...schemas.mission import Mision, MisionApprovalRequest, MisionRejectionRequest
from ...services.mission import MissionService
from ...api.deps import get_current_active_user, get_finance_user
from ...models.user import Usuario

router = APIRouter()


@router.get("/", response_model=List[Mision])
async def get_missions(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user)
):
    """Get missions"""
    # This would implement filtering based on user role and permissions
    # For now, returning empty list as placeholder
    return []


@router.get("/{mission_id}", response_model=Mision)
async def get_mission(
    mission_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user)
):
    """Get mission by ID"""
    mission = db.query(Mision).filter(Mision.id_mision == mission_id).first()
    if not mission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mission not found"
        )
    return mission


@router.post("/{mission_id}/approve", response_model=Mision)
async def approve_mission(
    mission_id: int,
    approval_data: MisionApprovalRequest,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_finance_user)
):
    """Approve mission"""
    mission_service = MissionService(db)
    return mission_service.approve_mission(mission_id, current_user.id_usuario, approval_data)


@router.post("/{mission_id}/reject", response_model=Mision)
async def reject_mission(
    mission_id: int,
    rejection_data: MisionRejectionRequest,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_finance_user)
):
    """Reject mission"""
    mission_service = MissionService(db)
    return mission_service.reject_mission(mission_id, current_user.id_usuario, rejection_data)