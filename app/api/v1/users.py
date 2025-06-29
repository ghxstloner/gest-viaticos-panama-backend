from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ...core.database import get_db
from ...schemas.user import Usuario, UsuarioCreate, UsuarioUpdate, Rol
from ...services.user import UserService
from ...api.deps import get_admin_user, get_finance_user
from ...models.user import Usuario as UsuarioModel

router = APIRouter()


@router.post("/", response_model=Usuario)
async def create_user(
    user_data: UsuarioCreate,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(get_admin_user)
):
    """Create new user (Admin only)"""
    user_service = UserService(db)
    return user_service.create_user(user_data)


@router.get("/", response_model=List[Usuario])
async def get_users(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(get_finance_user)
):
    """Get all users"""
    user_service = UserService(db)
    return user_service.get_users(skip=skip, limit=limit)


@router.get("/roles", response_model=List[Rol])
async def get_roles(
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(get_finance_user)
):
    """Get all roles"""
    user_service = UserService(db)
    return user_service.get_roles()


@router.get("/{user_id}", response_model=Usuario)
async def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(get_finance_user)
):
    """Get user by ID"""
    user_service = UserService(db)
    user = user_service.get_user(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return user


@router.patch("/{user_id}", response_model=Usuario)
async def update_user(
    user_id: int,
    user_data: UsuarioUpdate,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(get_admin_user)
):
    """Update user (Admin only)"""
    user_service = UserService(db)
    return user_service.update_user(user_id, user_data)


@router.patch("/{user_id}/toggle-active", response_model=Usuario)
async def toggle_user_active(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(get_admin_user)
):
    """Toggle user active status (Admin only)"""
    user_service = UserService(db)
    return user_service.toggle_user_active(user_id)