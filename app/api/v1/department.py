from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.database import get_db_financiero
from app.schemas.department import Department, DepartmentCreate, DepartmentUpdate, DepartmentWithCount
from app.services.department_service import DepartmentService
from app.api.deps import get_current_user
from app.models.user import Usuario

router = APIRouter()

# === ENDPOINTS DE DEPARTAMENTOS ===

@router.post("/", response_model=Department)
async def create_department(
    department_data: DepartmentCreate,
    db: Session = Depends(get_db_financiero),
    current_user: Usuario = Depends(get_current_user)
):
    """Create new department (Admin only)"""
    department_service = DepartmentService(db)
    return department_service.create_department(department_data)

@router.get("/", response_model=List[DepartmentWithCount])
async def get_departments(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db_financiero),
    current_user: Usuario = Depends(get_current_user)
):
    """Get all departments with user counts"""
    department_service = DepartmentService(db)
    return department_service.get_departments_with_counts(skip=skip, limit=limit)

@router.get("/{department_id}", response_model=Department)
async def get_department(
    department_id: int,
    db: Session = Depends(get_db_financiero),
    current_user: Usuario = Depends(get_current_user)
):
    """Get department by ID"""
    department_service = DepartmentService(db)
    department = department_service.get_department(department_id)
    if not department:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Department not found"
        )
    return department

@router.put("/{department_id}", response_model=Department)
async def update_department(
    department_id: int,
    department_data: DepartmentUpdate,
    db: Session = Depends(get_db_financiero),
    current_user: Usuario = Depends(get_current_user)
):
    """Update department (only name, seal path is managed separately)"""
    department_service = DepartmentService(db)
    return department_service.update_department(department_id, department_data)

@router.delete("/{department_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_department(
    department_id: int,
    db: Session = Depends(get_db_financiero),
    current_user: Usuario = Depends(get_current_user)
):
    """Delete department"""
    department_service = DepartmentService(db)
    try:
        department_service.delete_department(department_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )

# === ENDPOINTS DE SELLOS ===

@router.post("/{department_id}/seal")
async def upload_seal(
    department_id: int,
    seal_file: UploadFile = File(...),
    db: Session = Depends(get_db_financiero),
    current_user: Usuario = Depends(get_current_user)
):
    """Upload seal image for a department"""
    department_service = DepartmentService(db)
    seal_path = department_service.upload_seal(department_id, seal_file)
    return {
        "message": "Seal uploaded successfully",
        "seal_path": seal_path
    }

@router.delete("/{department_id}/seal")
async def delete_seal(
    department_id: int,
    db: Session = Depends(get_db_financiero),
    current_user: Usuario = Depends(get_current_user)
):
    """Delete seal image for a department"""
    department_service = DepartmentService(db)
    try:
        department_service.delete_seal(department_id)
        return {"message": "Seal deleted successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )

@router.get("/{department_id}/seal")
async def get_seal(
    department_id: int,
    db: Session = Depends(get_db_financiero),
    current_user: Usuario = Depends(get_current_user)
):
    """Get seal image for a department"""
    department_service = DepartmentService(db)
    seal_path = department_service.get_seal_path(department_id)
    
    if not seal_path:
        return {"message": "No seal found for this department", "has_seal": False}
    
    return FileResponse(seal_path)

# === ENDPOINTS DE USUARIOS EN DEPARTAMENTOS ===

@router.post("/{department_id}/users/{user_id}")
async def assign_user_to_department(
    department_id: int,
    user_id: int,
    db: Session = Depends(get_db_financiero),
    current_user: Usuario = Depends(get_current_user)
):
    """Assign user to department"""
    department_service = DepartmentService(db)
    success = department_service.assign_user_to_department(user_id, department_id)
    return {"message": "User assigned to department successfully"}

@router.delete("/{department_id}/users/{user_id}")
async def remove_user_from_department(
    department_id: int,
    user_id: int,
    db: Session = Depends(get_db_financiero),
    current_user: Usuario = Depends(get_current_user)
):
    """Remove user from department"""
    department_service = DepartmentService(db)
    success = department_service.remove_user_from_department(user_id)
    return {"message": "User removed from department successfully"}

@router.get("/{department_id}/users")
async def get_users_in_department(
    department_id: int,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db_financiero),
    current_user: Usuario = Depends(get_current_user)
):
    """Get all users in a specific department"""
    department_service = DepartmentService(db)
    users = department_service.get_users_in_department(department_id, skip, limit)
    return {"users": users, "total": len(users)}

@router.get("/{department_id}/with-users")
async def get_department_with_users(
    department_id: int,
    db: Session = Depends(get_db_financiero),
    current_user: Usuario = Depends(get_current_user)
):
    """Get department information with its users"""
    department_service = DepartmentService(db)
    return department_service.get_department_with_users(department_id)
