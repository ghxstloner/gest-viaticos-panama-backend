# app/api/v1/employee_requests.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Dict, Any

from app.core.database import get_db_rrhh
from app.services.employee_request_service import EmployeeRequestService
from app.api.deps import get_current_employee

router = APIRouter()

@router.get("/mis-solicitudes", response_model=List[Dict[str, Any]])
def get_my_requests(
    current_employee: dict = Depends(get_current_employee),
    db: Session = Depends(get_db_rrhh)
):
    """
    Endpoint protegido que obtiene la lista de solicitudes del empleado
    actualmente autenticado.
    """
    service = EmployeeRequestService(db)
    cedula = current_employee.get("cedula")
    
    if not cedula:
         raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="No se pudo identificar la cédula del empleado desde el token."
        )
         
    return service.get_requests_by_cedula(cedula)
