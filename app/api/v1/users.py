from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ...core.database import get_db_financiero
from ...schemas.User import Usuario, UsuarioCreate, UsuarioUpdate, Rol, RolCreate, RolUpdate
from ...services.user import UserService
from ...api.deps import get_current_user
# ✅ CORRECCIÓN: usar user en minúscula
from ...models.user import Usuario as UsuarioModel

router = APIRouter()

# === ENDPOINTS DE USUARIOS ===

@router.post("/", response_model=Usuario)
async def create_user(
    user_data: UsuarioCreate,
    db: Session = Depends(get_db_financiero),
    current_user: UsuarioModel = Depends(get_current_user)
):
    """Create new user (Admin only)"""
    # TODO: Add admin permission check
    user_service = UserService(db)
    return user_service.create_user(user_data)


@router.get("/", response_model=List[Usuario])
async def get_users(
    skip: int = 0,
    limit: int = 100,
    include_inactive: bool = False,
    db: Session = Depends(get_db_financiero),
    current_user: UsuarioModel = Depends(get_current_user)
):
    """Get all users"""
    user_service = UserService(db)
    return user_service.get_users(skip=skip, limit=limit, include_inactive=include_inactive)


@router.get("/{user_id}", response_model=Usuario)
async def get_user(
    user_id: int,
    db: Session = Depends(get_db_financiero),
    current_user: UsuarioModel = Depends(get_current_user)
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


@router.put("/{user_id}", response_model=Usuario)
async def update_user(
    user_id: int,
    user_data: UsuarioUpdate,
    db: Session = Depends(get_db_financiero),
    current_user: UsuarioModel = Depends(get_current_user)
):
    """Update user (Admin only)"""
    # TODO: Add admin permission check
    user_service = UserService(db)
    return user_service.update_user(user_id, user_data)


@router.delete("/{user_id}")
async def delete_user(
    user_id: int,
    db: Session = Depends(get_db_financiero),
    current_user: UsuarioModel = Depends(get_current_user)
):
    """Delete user (Admin only)"""
    # TODO: Add admin permission check
    if user_id == current_user.id_usuario:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own user account"
        )
    
    user_service = UserService(db)
    success = user_service.delete_user(user_id)
    return {"message": "User deleted successfully"}


# === ENDPOINTS DE ROLES ===

@router.get("/roles/", response_model=List[Rol])
async def get_roles(
    db: Session = Depends(get_db_financiero),
    current_user: UsuarioModel = Depends(get_current_user)
):
    """Get all roles"""
    user_service = UserService(db)
    return user_service.get_roles()


@router.post("/roles/", response_model=Rol)
async def create_role(
    role_data: RolCreate,
    db: Session = Depends(get_db_financiero),
    current_user: UsuarioModel = Depends(get_current_user)
):
    """Create new role (Admin only)"""
    # TODO: Add admin permission check
    user_service = UserService(db)
    return user_service.create_role(role_data)


@router.get("/roles/{role_id}", response_model=Rol)
async def get_role(
    role_id: int,
    db: Session = Depends(get_db_financiero),
    current_user: UsuarioModel = Depends(get_current_user)
):
    """Get role by ID"""
    user_service = UserService(db)
    role = user_service.get_role(role_id)
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found"
        )
    return role


@router.put("/roles/{role_id}", response_model=Rol)
async def update_role(
    role_id: int,
    role_data: RolUpdate,
    db: Session = Depends(get_db_financiero),
    current_user: UsuarioModel = Depends(get_current_user)
):
    """Update role (Admin only)"""
    # TODO: Add admin permission check
    user_service = UserService(db)
    return user_service.update_role(role_id, role_data)


@router.delete("/roles/{role_id}")
async def delete_role(
    role_id: int,
    db: Session = Depends(get_db_financiero),
    current_user: UsuarioModel = Depends(get_current_user)
):
    """Delete role (Admin only)"""
    # TODO: Add admin permission check
    user_service = UserService(db)
    success = user_service.delete_role(role_id)
    return {"message": "Role deleted successfully"}


# === ENDPOINTS DE UTILIDADES ===

@router.get("/{user_id}/permissions")
async def get_user_permissions(
    user_id: int,
    db: Session = Depends(get_db_financiero),
    current_user: UsuarioModel = Depends(get_current_user)
):
    """Get user permissions"""
    user_service = UserService(db)
    permissions = user_service.get_user_permissions(user_id)
    return {"permissions": permissions}


@router.get("/verify-rrhh/{personal_id}")
async def verify_personal_in_rrhh(
    personal_id: int,
    db: Session = Depends(get_db_financiero),
    current_user: UsuarioModel = Depends(get_current_user)
):
    """Verify if personal ID exists in RRHH system"""
    user_service = UserService(db)
    exists = user_service.verify_personal_in_rrhh(personal_id)
    return {"exists": exists, "personal_id": personal_id}