from typing import List, Dict, Any, Union
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db_financiero
from app.schemas.user import Usuario, UsuarioCreate, UsuarioUpdate, Rol, RolCreate, RolUpdate, Permiso, EmpleadoInfo
from app.services.user import UserService
from app.api.deps import get_current_user, get_current_user_universal
from app.models.user import Usuario as UsuarioModel

router = APIRouter()

# === ENDPOINTS DE USUARIOS ===

@router.post("/", response_model=Usuario)
async def create_user(
    user_data: UsuarioCreate,
    db: Session = Depends(get_db_financiero),
    current_user: UsuarioModel = Depends(get_current_user)
):
    """Create new user (Admin only)"""
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
    """Update user"""
    user_service = UserService(db)
    return user_service.update_user(user_id, user_data)

@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    db: Session = Depends(get_db_financiero),
    current_user: UsuarioModel = Depends(get_current_user)
):
    """Delete user"""
    if user_id == current_user.id_usuario:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own user account"
        )
    
    user_service = UserService(db)
    try:
        user_service.delete_user(user_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )

# === ENDPOINTS DE ROLES ===

@router.get("/roles/", response_model=List[Rol])
async def get_roles(
    db: Session = Depends(get_db_financiero),
    current_user: Union[UsuarioModel, dict] = Depends(get_current_user_universal)
):
    """Get all roles with their permissions"""
    user_service = UserService(db)
    return user_service.get_roles()

@router.post("/roles/", response_model=Rol)
async def create_role(
    role_data: RolCreate,
    db: Session = Depends(get_db_financiero),
    current_user: UsuarioModel = Depends(get_current_user)
):
    """Create new role"""
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
    """Update role"""
    user_service = UserService(db)
    return user_service.update_role(role_id, role_data)

@router.delete("/roles/{role_id}")
async def delete_role(
    role_id: int,
    db: Session = Depends(get_db_financiero),
    current_user: UsuarioModel = Depends(get_current_user)
):
    """Delete role"""
    user_service = UserService(db)
    success = user_service.delete_role(role_id)
    return {"message": "Role deleted successfully"}

# === ENDPOINTS DE PERMISOS ===

@router.get("/permisos/", response_model=List[Permiso])
async def get_permisos(
    db: Session = Depends(get_db_financiero),
    current_user: UsuarioModel = Depends(get_current_user)
):
    """Get all available permissions"""
    user_service = UserService(db)
    return user_service.get_permisos()

@router.get("/permisos/estructura")
async def get_permisos_estructura(
    db: Session = Depends(get_db_financiero),
    current_user: Union[UsuarioModel, dict] = Depends(get_current_user_universal)
):
    """Get user permissions organized by module and action"""
    user_service = UserService(db)
    
    # Obtener el ID del rol del usuario
    if isinstance(current_user, dict):  # Es empleado
        # ✅ DINÁMICO: Usar el rol que viene del token del empleado
        user_role_id = current_user.get('id_rol', 1)  # Fallback al rol 1 si no existe
    else:  # Es usuario financiero
        user_role_id = current_user.id_rol
    
    # Obtener los permisos específicos del usuario
    permisos_usuario = user_service.get_user_permissions_by_role(user_role_id)
    
    # ✅ SIMPLEMENTE RETORNAR LA ESTRUCTURA QUE YA VIENE CONSTRUIDA
    return permisos_usuario["estructura"]

@router.post("/roles/{role_id}/permisos/{permission_id}")
async def assign_permission_to_role(
    role_id: int,
    permission_id: int,
    db: Session = Depends(get_db_financiero),
    current_user: UsuarioModel = Depends(get_current_user)
):
    """Assign permission to role"""
    user_service = UserService(db)
    success = user_service.assign_permission_to_role(role_id, permission_id)
    return {"message": "Permission assigned successfully"}

@router.delete("/roles/{role_id}/permisos/{permission_id}")
async def remove_permission_from_role(
    role_id: int,
    permission_id: int,
    db: Session = Depends(get_db_financiero),
    current_user: UsuarioModel = Depends(get_current_user)
):
    """Remove permission from role"""
    user_service = UserService(db)
    success = user_service.remove_permission_from_role(role_id, permission_id)
    return {"message": "Permission removed successfully"}

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

@router.get("/roles/{role_id}/permisos", response_model=List[Permiso])
async def get_role_permissions(
    role_id: int,
    db: Session = Depends(get_db_financiero),
    current_user: UsuarioModel = Depends(get_current_user)
):
    """Get all permissions for a specific role"""
    user_service = UserService(db)
    return user_service.get_role_permissions(role_id)

@router.put("/roles/{role_id}/permisos", response_model=Rol)
async def update_role_permissions(
    role_id: int,
    permission_data: Dict[str, List[int]],  # {"permission_ids": [1, 2, 3]}
    db: Session = Depends(get_db_financiero),
    current_user: UsuarioModel = Depends(get_current_user)
):
    """Update all permissions for a role"""
    user_service = UserService(db)
    permission_ids = permission_data.get("permission_ids", [])
    return user_service.update_role_permissions(role_id, permission_ids)

@router.get("/permisos/all", response_model=List[Permiso])
async def get_all_permisos(
    db: Session = Depends(get_db_financiero),
    current_user: UsuarioModel = Depends(get_current_user)
):
    """Get ALL available permissions (for admin use)"""
    user_service = UserService(db)
    return user_service.get_all_permisos()

# Agregar este endpoint a tu router
@router.get("/empleado/{personal_id}", response_model=EmpleadoInfo)
async def get_employee_info(
    personal_id: int,
    db: Session = Depends(get_db_financiero),
    current_user: UsuarioModel = Depends(get_current_user_universal)
):
    """Get complete employee information from RRHH system"""
    user_service = UserService(db)
    employee_info = user_service.get_employee_complete_info(personal_id)
    
    if not employee_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found"
        )
    
    return employee_info