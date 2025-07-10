# app/api/v1/workflow.py

from typing import List, Dict, Any, Optional, Union
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query, Body
from sqlalchemy.orm import Session
from sqlalchemy import text

from ...core.database import get_db_financiero, get_db_rrhh
from ...core.exceptions import WorkflowException, BusinessException, PermissionException
from ...api.deps import get_current_user, get_current_employee_with_role
from ...models.user import Usuario
from ...models.mission import EstadoFlujo, TransicionFlujo
from ...schemas.workflow import *
from ...services.workflow_service import WorkflowService

router = APIRouter(prefix="/workflow", tags=["Workflow Management"])

# ===============================================
# DEPENDENCY FUNCTIONS
# ===============================================

def get_workflow_service(
    db_financiero: Session = Depends(get_db_financiero),
    db_rrhh: Session = Depends(get_db_rrhh)
) -> WorkflowService:
    """Dependency para obtener el servicio de workflow"""
    return WorkflowService(db_financiero, db_rrhh)

def get_client_ip(request: Request) -> str:
    """Dependency para obtener la IP del cliente"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    
    return request.client.host if request.client else "127.0.0.1"

# ===============================================
# ENDPOINTS UNIVERSALES (EMPLEADOS Y FINANCIEROS)
# ===============================================

@router.get("/missions/{mission_id}/actions", response_model=AvailableActionsResponse)
async def get_available_actions(
    mission_id: int,
    workflow_service: WorkflowService = Depends(get_workflow_service),
    current_user: Optional[Usuario] = Depends(get_current_user),
    current_employee: Optional[dict] = Depends(get_current_employee_with_role)
):
    """
    Obtiene las acciones disponibles para un usuario en una misión específica.
    Funciona tanto para usuarios financieros como empleados.
    """
    try:
        # Determinar qué tipo de usuario es
        user = current_user if current_user else current_employee
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuario no autenticado"
            )
        
        return workflow_service.get_available_actions(mission_id, user)
        
    except (WorkflowException, PermissionException) as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/states/my-relevant", response_model=List[WorkflowStateInfo])
async def get_my_relevant_states(
    workflow_service: WorkflowService = Depends(get_workflow_service),
    current_user: Optional[Usuario] = Depends(get_current_user),
    current_employee: Optional[dict] = Depends(get_current_employee_with_role)
):
    """
    Obtiene los estados de workflow relevantes para el usuario actual.
    """
    try:
        user = current_user if current_user else current_employee
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario no autenticado")
        
        return workflow_service.get_workflow_states_by_role(user)
        
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

# ===============================================
# ENDPOINTS ESPECÍFICOS PARA JEFES INMEDIATOS (EMPLEADOS)
# ===============================================

@router.post("/missions/{mission_id}/jefe/aprobar", response_model=WorkflowTransitionResponse)
async def jefe_approve_mission(
    mission_id: int,
    request_data: JefeApprovalRequest,
    workflow_service: WorkflowService = Depends(get_workflow_service),
    current_employee: dict = Depends(get_current_employee_with_role),
    client_ip: str = Depends(get_client_ip)
):
    """
    Permite al jefe inmediato aprobar una solicitud.
    Solo disponible para empleados con rol de Jefe Inmediato.
    """
    try:
        if not current_employee.get("is_department_head"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Solo los jefes de departamento pueden aprobar solicitudes"
            )
        
        return workflow_service.execute_workflow_action(
            mission_id=mission_id,
            action="APROBAR",
            user=current_employee,
            request_data=request_data,
            client_ip=client_ip
        )
        
    except (WorkflowException, PermissionException) as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post("/missions/{mission_id}/jefe/rechazar", response_model=WorkflowTransitionResponse)
async def jefe_reject_mission(
    mission_id: int,
    request_data: JefeRejectionRequest,
    workflow_service: WorkflowService = Depends(get_workflow_service),
    current_employee: dict = Depends(get_current_employee_with_role),
    client_ip: str = Depends(get_client_ip)
):
    """
    Permite al jefe inmediato rechazar una solicitud.
    Requiere especificar el motivo del rechazo.
    """
    try:
        if not current_employee.get("is_department_head"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Solo los jefes de departamento pueden rechazar solicitudes"
            )
        
        return workflow_service.execute_workflow_action(
            mission_id=mission_id,
            action="RECHAZAR",
            user=current_employee,
            request_data=request_data,
            client_ip=client_ip
        )
        
    except (WorkflowException, PermissionException) as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

# ===============================================
# ENDPOINTS PARA ANALISTAS FINANCIEROS
# ===============================================

@router.post("/missions/{mission_id}/tesoreria/aprobar", response_model=WorkflowTransitionResponse)
async def tesoreria_approve_mission(
    mission_id: int,
    request_data: TesoreriaApprovalRequest,
    workflow_service: WorkflowService = Depends(get_workflow_service),
    current_user: Usuario = Depends(get_current_user),
    client_ip: str = Depends(get_client_ip)
):
    """
    Permite al Analista de Tesorería aprobar una solicitud.
    """
    try:
        if current_user.rol.nombre_rol != "Analista Tesorería":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado")
        
        return workflow_service.execute_workflow_action(
            mission_id=mission_id,
            action="APROBAR",
            user=current_user,
            request_data=request_data,
            client_ip=client_ip
        )
        
    except (WorkflowException, PermissionException) as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post("/missions/{mission_id}/presupuesto/asignar", response_model=WorkflowTransitionResponse)
async def presupuesto_assign_budget(
    mission_id: int,
    request_data: PresupuestoActionRequest,
    workflow_service: WorkflowService = Depends(get_workflow_service),
    current_user: Usuario = Depends(get_current_user),
    client_ip: str = Depends(get_client_ip)
):
    """
    Permite al Analista de Presupuesto asignar partidas presupuestarias.
    Requiere especificar las partidas y montos correspondientes.
    """
    try:
        if current_user.rol.nombre_rol != "Analista Presupuesto":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado")
        
        return workflow_service.execute_workflow_action(
            mission_id=mission_id,
            action="APROBAR",
            user=current_user,
            request_data=request_data,
            client_ip=client_ip
        )
        
    except (WorkflowException, PermissionException) as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post("/missions/{mission_id}/contabilidad/aprobar", response_model=WorkflowTransitionResponse)
async def contabilidad_approve_mission(
    mission_id: int,
    request_data: ContabilidadApprovalRequest,
    workflow_service: WorkflowService = Depends(get_workflow_service),
    current_user: Usuario = Depends(get_current_user),
    client_ip: str = Depends(get_client_ip)
):
    """
    Permite al Analista de Contabilidad aprobar una solicitud.
    Puede incluir información contable específica.
    """
    try:
        if current_user.rol.nombre_rol != "Analista Contabilidad":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado")
        
        return workflow_service.execute_workflow_action(
            mission_id=mission_id,
            action="APROBAR",
            user=current_user,
            request_data=request_data,
            client_ip=client_ip
        )
        
    except (WorkflowException, PermissionException) as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post("/missions/{mission_id}/finanzas/aprobar", response_model=WorkflowTransitionResponse)
async def finanzas_approve_mission(
    mission_id: int,
    request_data: FinanzasApprovalRequest,
    workflow_service: WorkflowService = Depends(get_workflow_service),
    current_user: Usuario = Depends(get_current_user),
    client_ip: str = Depends(get_client_ip)
):
    """
    Permite al Director de Finanzas realizar la aprobación final.
    Puede especificar el monto final aprobado y determina si requiere refrendo CGR.
    """
    try:
        if current_user.rol.nombre_rol != "Director Finanzas":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado")
        
        return workflow_service.execute_workflow_action(
            mission_id=mission_id,
            action="APROBAR",
            user=current_user,
            request_data=request_data,
            client_ip=client_ip
        )
        
    except (WorkflowException, PermissionException) as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post("/missions/{mission_id}/cgr/refrendar", response_model=WorkflowTransitionResponse)
async def cgr_approve_mission(
    mission_id: int,
    request_data: CGRApprovalRequest,
    workflow_service: WorkflowService = Depends(get_workflow_service),
    current_user: Usuario = Depends(get_current_user),
    client_ip: str = Depends(get_client_ip)
):
    """
    Permite al Fiscalizador CGR realizar el refrendo de solicitudes de alto monto.
    """
    try:
        if current_user.rol.nombre_rol != "Fiscalizador CGR":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado")
        
        return workflow_service.execute_workflow_action(
            mission_id=mission_id,
            action="APROBAR",
            user=current_user,
            request_data=request_data,
            client_ip=client_ip
        )
        
    except (WorkflowException, PermissionException) as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post("/missions/{mission_id}/pago/procesar", response_model=WorkflowTransitionResponse)
async def process_payment(
    mission_id: int,
    request_data: PaymentProcessRequest,
    workflow_service: WorkflowService = Depends(get_workflow_service),
    current_user: Usuario = Depends(get_current_user),
    client_ip: str = Depends(get_client_ip)
):
    """
    Permite procesar el pago de una solicitud aprobada.
    Disponible para Analista Tesorería y Custodio Caja Menuda.
    """
    try:
        allowed_roles = ["Analista Tesorería", "Custodio Caja Menuda"]
        if current_user.rol.nombre_rol not in allowed_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado")
        
        return workflow_service.execute_workflow_action(
            mission_id=mission_id,
            action="APROBAR",
            user=current_user,
            request_data=request_data,
            client_ip=client_ip
        )
        
    except (WorkflowException, PermissionException) as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post("/missions/{mission_id}/pago/confirmar", response_model=WorkflowTransitionResponse)
async def confirm_payment(
    mission_id: int,
    request_data: WorkflowActionBase,
    workflow_service: WorkflowService = Depends(get_workflow_service),
    current_user: Usuario = Depends(get_current_user),
    client_ip: str = Depends(get_client_ip)
):
    """
    Permite confirmar el pago cuando está pendiente de firma electrónica.
    Disponible para Analista Tesorería.
    """
    try:
        if current_user.rol.nombre_rol != "Analista Tesorería":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado")
        
        return workflow_service.execute_workflow_action(
            mission_id=mission_id,
            action="APROBAR",
            user=current_user,
            request_data=request_data,
            client_ip=client_ip
        )
        
    except (WorkflowException, PermissionException) as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

# ===============================================
# ENDPOINTS PARA ACCIONES GENÉRICAS
# ===============================================

@router.post("/missions/{mission_id}/devolver", response_model=WorkflowTransitionResponse)
async def return_mission_for_correction(
    mission_id: int,
    request_data: WorkflowActionBase,
    workflow_service: WorkflowService = Depends(get_workflow_service),
    current_user: Optional[Usuario] = Depends(get_current_user),
    current_employee: Optional[dict] = Depends(get_current_employee_with_role),
    client_ip: str = Depends(get_client_ip)
):
    """
    Permite devolver una solicitud para corrección.
    Disponible para cualquier rol autorizado en el flujo.
    """
    try:
        user = current_user if current_user else current_employee
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario no autenticado")
        
        return workflow_service.execute_workflow_action(
            mission_id=mission_id,
            action="DEVOLVER",
            user=user,
            request_data=request_data,
            client_ip=client_ip
        )
        
    except (WorkflowException, PermissionException) as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

# ===============================================
# ENDPOINTS PARA OBTENER PENDIENTES POR ROL
# ===============================================

@router.get("/jefe/pendientes")
async def get_jefe_pendientes(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    tipo_mision: Optional[str] = Query(None),
    workflow_service: WorkflowService = Depends(get_workflow_service),
    current_employee: dict = Depends(get_current_employee_with_role)
):
    """
    Obtiene las solicitudes pendientes de aprobación para jefes inmediatos.
    """
    try:
        if not current_employee.get("is_department_head"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Solo los jefes de departamento pueden acceder a esta cola"
            )
        
        filters = {
            "page": page,
            "size": size,
            "search": search,
            "tipo_mision": tipo_mision
        }
        
        return workflow_service.get_pending_missions_by_role("Jefe Inmediato", current_employee, filters)
        
    except (WorkflowException, PermissionException) as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/tesoreria/pendientes")
async def get_tesoreria_pendientes(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    tipo_mision: Optional[str] = Query(None),
    workflow_service: WorkflowService = Depends(get_workflow_service),
    current_user: Usuario = Depends(get_current_user)
):
    """
    Obtiene las solicitudes pendientes de revisión para Analista Tesorería.
    """
    try:
        if current_user.rol.nombre_rol != "Analista Tesorería":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado")
        
        filters = {
            "page": page,
            "size": size,
            "search": search,
            "tipo_mision": tipo_mision
        }
        
        return workflow_service.get_pending_missions_by_role("Analista Tesorería", current_user, filters)
        
    except (WorkflowException, PermissionException) as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/presupuesto/pendientes")
async def get_presupuesto_pendientes(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    tipo_mision: Optional[str] = Query(None),
    workflow_service: WorkflowService = Depends(get_workflow_service),
    current_user: Usuario = Depends(get_current_user)
):
    """
    Obtiene las solicitudes pendientes de asignación presupuestaria.
    """
    try:
        if current_user.rol.nombre_rol != "Analista Presupuesto":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado")
        
        filters = {
            "page": page,
            "size": size,
            "search": search,
            "tipo_mision": tipo_mision
        }
        
        return workflow_service.get_pending_missions_by_role("Analista Presupuesto", current_user, filters)
        
    except (WorkflowException, PermissionException) as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/contabilidad/pendientes")
async def get_contabilidad_pendientes(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    tipo_mision: Optional[str] = Query(None),
    workflow_service: WorkflowService = Depends(get_workflow_service),
    current_user: Usuario = Depends(get_current_user)
):
    """
    Obtiene las solicitudes pendientes de procesamiento contable.
    """
    try:
        if current_user.rol.nombre_rol != "Analista Contabilidad":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado")
        
        filters = {
            "page": page,
            "size": size,
            "search": search,
            "tipo_mision": tipo_mision
        }
        
        return workflow_service.get_pending_missions_by_role("Analista Contabilidad", current_user, filters)
        
    except (WorkflowException, PermissionException) as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/finanzas/pendientes")
async def get_finanzas_pendientes(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    tipo_mision: Optional[str] = Query(None),
    workflow_service: WorkflowService = Depends(get_workflow_service),
    current_user: Usuario = Depends(get_current_user)
):
    """
    Obtiene las solicitudes pendientes de aprobación final del Director Finanzas.
    """
    try:
        if current_user.rol.nombre_rol != "Director Finanzas":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado")
        
        filters = {
            "page": page,
            "size": size,
            "search": search,
            "tipo_mision": tipo_mision
        }
        
        return workflow_service.get_pending_missions_by_role("Director Finanzas", current_user, filters)
        
    except (WorkflowException, PermissionException) as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/cgr/pendientes")
async def get_cgr_pendientes(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    tipo_mision: Optional[str] = Query(None),
    workflow_service: WorkflowService = Depends(get_workflow_service),
    current_user: Usuario = Depends(get_current_user)
):
    """
    Obtiene las solicitudes pendientes de refrendo CGR.
    """
    try:
        if current_user.rol.nombre_rol != "Fiscalizador CGR":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado")
        
        filters = {
            "page": page,
            "size": size,
            "search": search,
            "tipo_mision": tipo_mision
        }
        
        return workflow_service.get_pending_missions_by_role("Fiscalizador CGR", current_user, filters)
        
    except (WorkflowException, PermissionException) as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

# ===============================================
# ENDPOINTS DE CONSULTA Y UTILIDADES
# ===============================================

@router.get("/budget-items", response_model=List[PartidaPresupuestariaResponse])
async def get_budget_items_catalog(
    search: Optional[str] = Query(None, description="Buscar partidas por código o descripción"),
    workflow_service: WorkflowService = Depends(get_workflow_service),
    current_user: Usuario = Depends(get_current_user)
):
    """
    Obtiene el catálogo de partidas presupuestarias disponibles.
    Solo disponible para roles financieros.
    """
    try:
        financial_roles = ["Analista Presupuesto", "Director Finanzas", "Administrador Sistema"]
        if current_user.rol.nombre_rol not in financial_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado")
        
        partidas = workflow_service.get_budget_items_catalog()
        
        # Aplicar filtro de búsqueda si se proporciona
        if search:
            search_lower = search.lower()
            partidas = [
                p for p in partidas 
                if search_lower in p.codigo_partida.lower() or search_lower in p.descripcion.lower()
            ]
        
        return partidas
        
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/missions/{mission_id}/next-states")
async def get_next_possible_states(
    mission_id: int,
    workflow_service: WorkflowService = Depends(get_workflow_service),
    current_user: Optional[Usuario] = Depends(get_current_user),
    current_employee: Optional[dict] = Depends(get_current_employee_with_role)
):
    """
    Obtiene los posibles próximos estados para una misión específica.
    """
    try:
        user = current_user if current_user else current_employee
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario no autenticado")
        
        actions = workflow_service.get_available_actions(mission_id, user)
        
        return {
            "mission_id": mission_id,
            "current_state": actions.estado_actual,
            "next_possible_states": [
                {
                    "action": accion["accion"],
                    "next_state": accion["estado_destino"],
                    "description": accion["descripcion"]
                }
                for accion in actions.acciones_disponibles
            ]
        }
        
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

# ===============================================
# ENDPOINTS DE INFORMACIÓN DEL SISTEMA
# ===============================================

@router.get("/info/workflow-summary")
async def get_workflow_system_info(
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db_financiero)
):
    """
    Obtiene información general del sistema de workflow.
    Solo disponible para administradores.
    """
    try:
        if current_user.rol.nombre_rol != "Administrador Sistema":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado")
        
        # Estadísticas básicas del sistema
        total_estados = db.query(EstadoFlujo).count()
        total_transiciones = db.query(TransicionFlujo).filter(TransicionFlujo.es_activa == True).count()
        
        return {
            "total_estados": total_estados,
            "total_transiciones_activas": total_transiciones,
            "tipos_flujo_soportados": ["VIATICOS", "CAJA_MENUDA", "AMBOS"],
            "roles_con_acceso": [
                "Solicitante", "Jefe Inmediato", "Analista Tesorería",
                "Analista Presupuesto", "Analista Contabilidad", 
                "Director Finanzas", "Fiscalizador CGR", "Custodio Caja Menuda"
            ]
        }
        
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))