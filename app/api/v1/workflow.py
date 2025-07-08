# app/api/v1/workflow.py

from typing import List, Optional, Dict, Any
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from sqlalchemy.orm import Session
from sqlalchemy import text, and_
from pydantic import BaseModel

from ...core.database import get_db_financiero, get_db_rrhh
from ...core.exceptions import BusinessException, WorkflowException
from ...api.deps import get_current_user, get_current_employee_with_role
from ...models.mission import Mision as MisionModel, EstadoFlujo, TransicionFlujo, HistorialFlujo
from ...models.user import Usuario
from ...models.enums import TipoAccion
from ...services.mission import MissionService
from ...schemas.mission import MisionListResponse, MisionListResponseItem

router = APIRouter(tags=["Workflow"])

# Esquemas para las acciones de workflow
class WorkflowActionRequest(BaseModel):
    action: str
    comentarios: Optional[str] = None
    monto_aprobado: Optional[float] = None

class PartidaPresupuestaria(BaseModel):
    codigo_partida: str
    monto: float

class PresupuestoActionRequest(BaseModel):
    partidas: List[PartidaPresupuestaria]
    comentarios: Optional[str] = None

# ===============================================
# FUNCIÓN HELPER PARA OBTENER NOMBRES DE BENEFICIARIOS
# ===============================================

def get_beneficiary_names(db_rrhh: Session, personal_ids: List[int]) -> Dict[int, str]:
    """Helper para obtener nombres de beneficiarios desde RRHH"""
    print(f"🔍 get_beneficiary_names called with personal_ids: {personal_ids}")
    
    if not personal_ids:
        print("❌ No personal_ids provided, returning empty dict")
        return {}
    
    # Construir consulta SQL dinámica
    if len(personal_ids) == 1:
        condition = "= :personal_id"
        params = {"personal_id": personal_ids[0]}
    else:
        placeholders = ','.join(str(pid) for pid in personal_ids)
        condition = f"IN ({placeholders})"
        params = {}
    
    query = text(f"""
        SELECT personal_id, apenom
        FROM aitsa_rrhh.nompersonal 
        WHERE personal_id {condition}
        AND estado != 'De Baja'
    """)
    
    print(f"🔍 SQL Query: {query}")
    print(f"🔍 SQL Params: {params}")
    
    try:
        result = db_rrhh.execute(query, params)
        rows = result.fetchall()
        print(f"🔍 Raw SQL result: {[(row.personal_id, row.apenom) for row in rows]}")
        
        names_dict = {row.personal_id: row.apenom for row in rows}
        print(f"✅ Final names dict: {names_dict}")
        return names_dict
    except Exception as e:
        print(f"❌ Error obteniendo nombres de beneficiarios: {e}")
        return {}

# ===============================================
# ENDPOINTS PARA JEFE INMEDIATO (EMPLEADOS)
# ===============================================

@router.get("/jefe/pendientes", response_model=MisionListResponse, summary="Obtener solicitudes pendientes para jefe")
async def get_jefe_pending_missions(
    page: int = Query(1, ge=1),
    size: int = Query(100, ge=1, le=1000),
    estado_id: Optional[int] = Query(None, description="Filtrar por ID de estado de flujo"),
    tipo_mision: Optional[str] = Query(None, description="Filtrar por tipo de misión"),
    fecha_desde: Optional[date] = Query(None),
    fecha_hasta: Optional[date] = Query(None),
    search: Optional[str] = Query(None, description="Buscar por objetivo o beneficiario"),
    db_financiero: Session = Depends(get_db_financiero),
    db_rrhh: Session = Depends(get_db_rrhh),
    current_employee: dict = Depends(get_current_employee_with_role)
):
    """
    Obtiene las solicitudes pendientes para el jefe inmediato.
    Solo muestra las solicitudes de los empleados en su departamento.
    """
    try:
        # ✅ VERIFICAR QUE ES JEFE DE DEPARTAMENTO
        if not current_employee.get("is_department_head"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="El usuario no es jefe de ningún departamento"
            )
        
        # ✅ OBTENER LOS IDS DE DEPARTAMENTOS GESTIONADOS
        managed_departments = current_employee.get("managed_departments", [])
        if not managed_departments:
            return MisionListResponse(
                items=[],
                total=0,
                page=page,
                size=size,
                pages=0
            )
        
        managed_dept_ids = [dept["id"] for dept in managed_departments]
        
        # ✅ OBTENER EMPLEADOS EN ESOS DEPARTAMENTOS
        if len(managed_dept_ids) == 1:
            # Caso especial para un solo departamento
            dept_condition = "= :dept_id"
            dept_params = {"dept_id": managed_dept_ids[0]}
        else:
            # Múltiples departamentos
            dept_condition = f"IN ({','.join(str(d) for d in managed_dept_ids)})"
            dept_params = {}
        
        employee_query = text(f"""
            SELECT personal_id
            FROM aitsa_rrhh.nompersonal 
            WHERE IdDepartamento {dept_condition}
            AND estado != 'De Baja'
        """)
        
        employee_result = db_rrhh.execute(employee_query, dept_params)
        employees = employee_result.fetchall()
        
        if not employees:
            return MisionListResponse(
                items=[],
                total=0,
                page=page,
                size=size,
                pages=0
            )
        
        # ✅ OBTENER SOLO LOS IDS DE EMPLEADOS
        employee_ids = [emp.personal_id for emp in employees]
        
        # ✅ CONSTRUIR CONSULTA BASE PARA MISIONES
        query = db_financiero.query(MisionModel).join(EstadoFlujo).filter(
            MisionModel.beneficiario_personal_id.in_(employee_ids)
        )
        
        # ✅ FILTRAR POR ESTADO ESPECÍFICO O PENDIENTE_JEFE POR DEFECTO
        if estado_id:
            query = query.filter(MisionModel.id_estado_flujo == estado_id)
        else:
            # Por defecto, solo mostrar solicitudes pendientes del jefe
            estado_pendiente_jefe = db_financiero.query(EstadoFlujo).filter(
                EstadoFlujo.nombre_estado == "PENDIENTE_JEFE"
            ).first()
            if estado_pendiente_jefe:
                query = query.filter(MisionModel.id_estado_flujo == estado_pendiente_jefe.id_estado_flujo)
        
        # ✅ APLICAR FILTROS ADICIONALES
        if tipo_mision:
            query = query.filter(MisionModel.tipo_mision == tipo_mision)
        if fecha_desde:
            query = query.filter(MisionModel.fecha_salida >= fecha_desde)
        if fecha_hasta:
            query = query.filter(MisionModel.fecha_retorno <= fecha_hasta)
        if search:
            search_term = f"%{search}%"
            query = query.filter(
                MisionModel.objetivo_mision.ilike(search_term)
            )
        
        # ✅ CALCULAR PAGINACIÓN
        total = query.count()
        skip = (page - 1) * size
        items = query.order_by(MisionModel.created_at.desc()).offset(skip).limit(size).all()
        
        # ✅ OBTENER NOMBRES DE BENEFICIARIOS (USANDO LA FUNCIÓN QUE FUNCIONA)
        personal_ids = [m.beneficiario_personal_id for m in items if m.beneficiario_personal_id]
        beneficiary_names = get_beneficiary_names(db_rrhh, personal_ids)
        
        # ✅ CONSTRUIR RESPUESTA
        response_items = []
        for mission in items:
            beneficiary_name = beneficiary_names.get(mission.beneficiario_personal_id, "Empleado no encontrado")
            
            mission_dict = {
                "id_mision": mission.id_mision,
                "numero_solicitud": mission.numero_solicitud or f"SOL-{mission.id_mision:06d}",
                "tipo_mision": mission.tipo_mision,
                "objetivo_mision": mission.objetivo_mision,
                "destino_mision": mission.destino_mision,
                "fecha_salida": mission.fecha_salida,
                "created_at": mission.created_at,
                "monto_total_calculado": float(mission.monto_total_calculado) if mission.monto_total_calculado else 0.0,
                "beneficiario_nombre": beneficiary_name,  # ✅ AHORA SÍ APARECERÁ
                "estado_flujo": {
                    "id_estado_flujo": mission.estado_flujo.id_estado_flujo,
                    "nombre_estado": mission.estado_flujo.nombre_estado,
                    "descripcion": mission.estado_flujo.descripcion
                } if mission.estado_flujo else None
            }
            response_items.append(MisionListResponseItem.model_validate(mission_dict))
        
        return MisionListResponse(
            items=response_items,
            total=total,
            page=page,
            size=size,
            pages=(total + size - 1) // size if size > 0 else 0
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error obteniendo solicitudes pendientes para jefe: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno del servidor: {str(e)}"
        )

@router.post("/jefe/{mission_id}/aprobar")
async def jefe_approve_mission(
    mission_id: int,
    request: WorkflowActionRequest,
    db_financiero: Session = Depends(get_db_financiero),
    db_rrhh: Session = Depends(get_db_rrhh),
    current_employee: dict = Depends(get_current_employee_with_role)
):
    """Jefe inmediato aprueba una misión"""
    
    # ✅ VERIFICAR QUE ES JEFE
    if not current_employee.get("is_department_head"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo los jefes de departamento pueden aprobar solicitudes"
        )
    
    # ✅ VERIFICAR QUE LA MISIÓN EXISTE Y ESTÁ EN ESTADO CORRECTO
    mision = db_financiero.query(MisionModel).join(EstadoFlujo).filter(
        MisionModel.id_mision == mission_id
    ).first()
    
    if not mision:
        raise HTTPException(status_code=404, detail="Misión no encontrada")
    
    if mision.estado_flujo.nombre_estado != "PENDIENTE_JEFE":
        raise HTTPException(
            status_code=400, 
            detail=f"La misión no está pendiente de aprobación del jefe. Estado actual: {mision.estado_flujo.nombre_estado}"
        )
    
    # ✅ VERIFICAR QUE EL EMPLEADO BENEFICIARIO ESTÁ BAJO SU SUPERVISIÓN
    cedula = current_employee.get("cedula")
    
    # Verificar departamento del empleado beneficiario
    employee_dept_query = text("""
        SELECT np.IdDepartamento, d.IdJefe, np.apenom
        FROM aitsa_rrhh.nompersonal np
        JOIN aitsa_rrhh.departamento d ON np.IdDepartamento = d.IdDepartamento
        WHERE np.personal_id = :personal_id
    """)
    
    dept_result = db_rrhh.execute(employee_dept_query, {"personal_id": mision.beneficiario_personal_id})
    dept_info = dept_result.fetchone()
    
    if not dept_info:
        raise HTTPException(
            status_code=404, 
            detail="No se encontró información del departamento del empleado beneficiario"
        )
    
    if dept_info.IdJefe != cedula:
        raise HTTPException(
            status_code=403, 
            detail=f"No tienes autorización para aprobar esta solicitud. El jefe autorizado es: {dept_info.IdJefe}"
        )
    
    # ✅ PROCESAR APROBACIÓN
    try:
        # Cambiar estado a PENDIENTE_REVISION_TESORERIA
        nuevo_estado = db_financiero.query(EstadoFlujo).filter(
            EstadoFlujo.nombre_estado == "PENDIENTE_REVISION_TESORERIA"
        ).first()
        
        if not nuevo_estado:
            raise HTTPException(status_code=500, detail="Estado PENDIENTE_REVISION_TESORERIA no configurado")
        
        estado_anterior = mision.id_estado_flujo
        mision.id_estado_flujo = nuevo_estado.id_estado_flujo
        
        # ✅ REGISTRAR EN HISTORIAL
        historial = HistorialFlujo(
            id_mision=mission_id,
            id_usuario_accion=1,  # Usuario sistema para empleados
            id_estado_anterior=estado_anterior,
            id_estado_nuevo=nuevo_estado.id_estado_flujo,
            tipo_accion=TipoAccion.APROBAR,
            comentarios=f"Aprobado por Jefe Inmediato ({current_employee.get('apenom', 'Desconocido')} - {cedula}): {request.comentarios or 'Sin comentarios'}",
            datos_adicionales={
                "jefe_cedula": cedula,
                "jefe_nombre": current_employee.get("apenom"),
                "beneficiario_nombre": dept_info.apenom,
                "departamento_id": dept_info.IdDepartamento
            }
        )
        
        db_financiero.add(historial)
        db_financiero.commit()
        
        return {
            "success": True,
            "message": "Misión aprobada exitosamente",
            "nuevo_estado": nuevo_estado.nombre_estado,
            "mission_id": mission_id
        }
        
    except Exception as e:
        db_financiero.rollback()
        print(f"Error procesando aprobación: {e}")
        raise HTTPException(status_code=500, detail=f"Error procesando aprobación: {str(e)}")

@router.post("/jefe/{mission_id}/rechazar")
async def jefe_reject_mission(
    mission_id: int,
    request: WorkflowActionRequest,
    db_financiero: Session = Depends(get_db_financiero),
    db_rrhh: Session = Depends(get_db_rrhh),
    current_employee: dict = Depends(get_current_employee_with_role)
):
    """Jefe inmediato rechaza una misión"""
    
    # ✅ VERIFICAR QUE ES JEFE
    if not current_employee.get("is_department_head"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo los jefes de departamento pueden rechazar solicitudes"
        )
    
    mision = db_financiero.query(MisionModel).join(EstadoFlujo).filter(
        MisionModel.id_mision == mission_id
    ).first()
    
    if not mision:
        raise HTTPException(status_code=404, detail="Misión no encontrada")
    
    if mision.estado_flujo.nombre_estado != "PENDIENTE_JEFE":
        raise HTTPException(
            status_code=400, 
            detail=f"La misión no está pendiente de aprobación del jefe. Estado actual: {mision.estado_flujo.nombre_estado}"
        )
    
    # ✅ VERIFICAR AUTORIZACIÓN IGUAL QUE EN APROBAR
    cedula = current_employee.get("cedula")
    
    employee_dept_query = text("""
        SELECT np.IdDepartamento, d.IdJefe, np.apenom
        FROM aitsa_rrhh.nompersonal np
        JOIN aitsa_rrhh.departamento d ON np.IdDepartamento = d.IdDepartamento
        WHERE np.personal_id = :personal_id
    """)
    
    dept_result = db_rrhh.execute(employee_dept_query, {"personal_id": mision.beneficiario_personal_id})
    dept_info = dept_result.fetchone()
    
    if not dept_info or dept_info.IdJefe != cedula:
        raise HTTPException(status_code=403, detail="No tienes autorización para rechazar esta solicitud")
    
    try:
        # ✅ CAMBIAR ESTADO A RECHAZADO
        estado_rechazado = db_financiero.query(EstadoFlujo).filter(
            EstadoFlujo.nombre_estado == "RECHAZADO"
        ).first()
        
        if not estado_rechazado:
            raise HTTPException(status_code=500, detail="Estado RECHAZADO no configurado")
        
        estado_anterior = mision.id_estado_flujo
        mision.id_estado_flujo = estado_rechazado.id_estado_flujo
        
        # ✅ REGISTRAR EN HISTORIAL
        historial = HistorialFlujo(
            id_mision=mission_id,
            id_usuario_accion=1,  # Usuario sistema
            id_estado_anterior=estado_anterior,
            id_estado_nuevo=estado_rechazado.id_estado_flujo,
            tipo_accion=TipoAccion.RECHAZAR,
            comentarios=f"Rechazado por Jefe Inmediato ({current_employee.get('apenom', 'Desconocido')} - {cedula}): {request.comentarios or 'Sin motivo especificado'}",
            datos_adicionales={
                "jefe_cedula": cedula,
                "jefe_nombre": current_employee.get("apenom"),
                "beneficiario_nombre": dept_info.apenom,
                "departamento_id": dept_info.IdDepartamento
            }
        )
        
        db_financiero.add(historial)
        db_financiero.commit()
        
        return {
            "success": True,
            "message": "Misión rechazada",
            "nuevo_estado": estado_rechazado.nombre_estado,
            "mission_id": mission_id
        }
        
    except Exception as e:
        db_financiero.rollback()
        print(f"Error procesando rechazo: {e}")
        raise HTTPException(status_code=500, detail=f"Error procesando rechazo: {str(e)}")

# ===============================================
# ENDPOINTS PARA ANALISTA TESORERÍA (USUARIOS FINANCIEROS)
# ===============================================

@router.get("/tesoreria/pendientes")
async def get_tesoreria_pending_missions(
    page: int = Query(1, ge=1),
    size: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db_financiero),
    db_rrhh: Session = Depends(get_db_rrhh),  # ✅ AGREGADO
    current_user: Usuario = Depends(get_current_user)
):
    """Obtiene misiones pendientes de revisión de tesorería"""
    
    if current_user.rol.nombre_rol != "Analista Tesorería":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    estado_pendiente = db.query(EstadoFlujo).filter(
        EstadoFlujo.nombre_estado == "PENDIENTE_REVISION_TESORERIA"
    ).first()
    
    if not estado_pendiente:
        return MisionListResponse(items=[], total=0, page=page, size=size, pages=0)
    
    query = db.query(MisionModel).filter(
        MisionModel.id_estado_flujo == estado_pendiente.id_estado_flujo
    )
    
    total = query.count()
    skip = (page - 1) * size
    misiones = query.order_by(MisionModel.created_at.desc()).offset(skip).limit(size).all()
    
    # ✅ OBTENER NOMBRES DE BENEFICIARIOS
    personal_ids = [m.beneficiario_personal_id for m in misiones if m.beneficiario_personal_id]
    beneficiary_names = get_beneficiary_names(db_rrhh, personal_ids)
    
    response_items = []
    for m in misiones:
        beneficiary_name = beneficiary_names.get(m.beneficiario_personal_id, "Empleado no encontrado")
        
        mission_dict = {
            "id_mision": m.id_mision,
            "numero_solicitud": m.numero_solicitud or f"SOL-{m.id_mision:06d}",
            "tipo_mision": m.tipo_mision,
            "objetivo_mision": m.objetivo_mision,
            "destino_mision": m.destino_mision,
            "fecha_salida": m.fecha_salida,
            "created_at": m.created_at,
            "monto_total_calculado": float(m.monto_total_calculado) if m.monto_total_calculado else 0.0,
            "beneficiario_nombre": beneficiary_name,  # ✅ NOMBRE REAL
            "estado_flujo": {
                "id_estado_flujo": m.estado_flujo.id_estado_flujo,
                "nombre_estado": m.estado_flujo.nombre_estado,
                "descripcion": m.estado_flujo.descripcion
            } if m.estado_flujo else None
        }
        response_items.append(MisionListResponseItem.model_validate(mission_dict))
    
    return MisionListResponse(
        items=response_items,
        total=total,
        page=page,
        size=size,
        pages=(total + size - 1) // size if size > 0 else 0
    )

@router.post("/tesoreria/{mission_id}/aprobar")
async def tesoreria_approve_mission(
    mission_id: int,
    request: WorkflowActionRequest,
    db: Session = Depends(get_db_financiero),
    current_user: Usuario = Depends(get_current_user)
):
    """Analista de tesorería aprueba una misión"""
    
    if current_user.rol.nombre_rol != "Analista Tesorería":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    service = MissionService(db)
    mision = service.process_workflow_action(
        mission_id=mission_id,
        user=current_user,
        action=TipoAccion.APROBAR,
        comentarios=request.comentarios
    )
    
    return {
        "success": True,
        "message": "Misión aprobada por Tesorería",
        "nuevo_estado": mision.estado_flujo.nombre_estado
    }

# ===============================================
# ENDPOINTS PARA ANALISTA PRESUPUESTO (USUARIOS FINANCIEROS)
# ===============================================

@router.get("/presupuesto/pendientes")
async def get_presupuesto_pending_missions(
    page: int = Query(1, ge=1),
    size: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db_financiero),
    db_rrhh: Session = Depends(get_db_rrhh),  # ✅ AGREGADO
    current_user: Usuario = Depends(get_current_user)
):
    """Obtiene misiones pendientes de asignación presupuestaria"""
    
    if current_user.rol.nombre_rol != "Analista Presupuesto":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    estado_pendiente = db.query(EstadoFlujo).filter(
        EstadoFlujo.nombre_estado == "PENDIENTE_ASIGNACION_PRESUPUESTO"
    ).first()
    
    if not estado_pendiente:
        return MisionListResponse(items=[], total=0, page=page, size=size, pages=0)
    
    query = db.query(MisionModel).filter(
        MisionModel.id_estado_flujo == estado_pendiente.id_estado_flujo
    )
    
    total = query.count()
    skip = (page - 1) * size
    misiones = query.order_by(MisionModel.created_at.desc()).offset(skip).limit(size).all()
    
    # ✅ OBTENER NOMBRES DE BENEFICIARIOS
    personal_ids = [m.beneficiario_personal_id for m in misiones if m.beneficiario_personal_id]
    beneficiary_names = get_beneficiary_names(db_rrhh, personal_ids)
    
    response_items = []
    for m in misiones:
        beneficiary_name = beneficiary_names.get(m.beneficiario_personal_id, "Empleado no encontrado")
        
        mission_dict = {
            "id_mision": m.id_mision,
            "numero_solicitud": m.numero_solicitud or f"SOL-{m.id_mision:06d}",
            "tipo_mision": m.tipo_mision,
            "objetivo_mision": m.objetivo_mision,
            "destino_mision": m.destino_mision,
            "fecha_salida": m.fecha_salida,
            "created_at": m.created_at,
            "monto_total_calculado": float(m.monto_total_calculado) if m.monto_total_calculado else 0.0,
            "beneficiario_nombre": beneficiary_name,  # ✅ NOMBRE REAL
            "estado_flujo": {
                "id_estado_flujo": m.estado_flujo.id_estado_flujo,
                "nombre_estado": m.estado_flujo.nombre_estado,
                "descripcion": m.estado_flujo.descripcion
            } if m.estado_flujo else None
        }
        response_items.append(MisionListResponseItem.model_validate(mission_dict))
    
    return MisionListResponse(
        items=response_items,
        total=total,
        page=page,
        size=size,
        pages=(total + size - 1) // size if size > 0 else 0
    )

@router.post("/presupuesto/{mission_id}/asignar")
async def presupuesto_assign_budget(
    mission_id: int,
    request: PresupuestoActionRequest,
    db: Session = Depends(get_db_financiero),
    current_user: Usuario = Depends(get_current_user)
):
    """Analista de presupuesto asigna partidas presupuestarias"""
    
    if current_user.rol.nombre_rol != "Analista Presupuesto":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    service = MissionService(db)
    
    # Convertir partidas al formato esperado
    from app.schemas.mission import PresupuestoAssignRequest, MisionPartidaPresupuestariaCreate
    
    partidas = [
        MisionPartidaPresupuestariaCreate(
            codigo_partida=p.codigo_partida,
            monto=p.monto
        )
        for p in request.partidas
    ]
    
    assign_request = PresupuestoAssignRequest(
        partidas=partidas,
        comentarios=request.comentarios
    )
    
    mision = service.assign_budget_items(mission_id, assign_request, current_user)
    
    return {
        "success": True,
        "message": "Partidas presupuestarias asignadas",
        "nuevo_estado": mision.estado_flujo.nombre_estado
    }

# ===============================================
# ENDPOINTS PARA ANALISTA CONTABILIDAD (USUARIOS FINANCIEROS)
# ===============================================

@router.get("/contabilidad/pendientes")
async def get_contabilidad_pending_missions(
    page: int = Query(1, ge=1),
    size: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db_financiero),
    db_rrhh: Session = Depends(get_db_rrhh),  # ✅ AGREGADO
    current_user: Usuario = Depends(get_current_user)
):
    """Obtiene misiones pendientes de contabilidad"""
    
    if current_user.rol.nombre_rol != "Analista Contabilidad":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    estado_pendiente = db.query(EstadoFlujo).filter(
        EstadoFlujo.nombre_estado == "PENDIENTE_CONTABILIDAD"
    ).first()
    
    if not estado_pendiente:
        return MisionListResponse(items=[], total=0, page=page, size=size, pages=0)
    
    query = db.query(MisionModel).filter(
        MisionModel.id_estado_flujo == estado_pendiente.id_estado_flujo
    )
    
    total = query.count()
    skip = (page - 1) * size
    misiones = query.order_by(MisionModel.created_at.desc()).offset(skip).limit(size).all()
    
    # ✅ OBTENER NOMBRES DE BENEFICIARIOS
    personal_ids = [m.beneficiario_personal_id for m in misiones if m.beneficiario_personal_id]
    beneficiary_names = get_beneficiary_names(db_rrhh, personal_ids)
    
    response_items = []
    for m in misiones:
        beneficiary_name = beneficiary_names.get(m.beneficiario_personal_id, "Empleado no encontrado")
        
        mission_dict = {
            "id_mision": m.id_mision,
            "numero_solicitud": m.numero_solicitud or f"SOL-{m.id_mision:06d}",
            "tipo_mision": m.tipo_mision,
            "objetivo_mision": m.objetivo_mision,
            "destino_mision": m.destino_mision,
            "fecha_salida": m.fecha_salida,
            "created_at": m.created_at,
            "monto_total_calculado": float(m.monto_total_calculado) if m.monto_total_calculado else 0.0,
            "beneficiario_nombre": beneficiary_name,  # ✅ NOMBRE REAL
            "estado_flujo": {
                "id_estado_flujo": m.estado_flujo.id_estado_flujo,
                "nombre_estado": m.estado_flujo.nombre_estado,
                "descripcion": m.estado_flujo.descripcion
            } if m.estado_flujo else None
        }
        response_items.append(MisionListResponseItem.model_validate(mission_dict))
    
    return MisionListResponse(
        items=response_items,
        total=total,
        page=page,
        size=size,
        pages=(total + size - 1) // size if size > 0 else 0
    )

@router.post("/contabilidad/{mission_id}/aprobar")
async def contabilidad_approve_mission(
    mission_id: int,
    request: WorkflowActionRequest,
    db: Session = Depends(get_db_financiero),
    current_user: Usuario = Depends(get_current_user)
):
    """Analista de contabilidad aprueba una misión"""
    
    if current_user.rol.nombre_rol != "Analista Contabilidad":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    service = MissionService(db)
    mision = service.process_workflow_action(
        mission_id=mission_id,
        user=current_user,
        action=TipoAccion.APROBAR,
        comentarios=request.comentarios
    )
    
    return {
        "success": True,
        "message": "Misión aprobada por Contabilidad",
        "nuevo_estado": mision.estado_flujo.nombre_estado
    }

# ===============================================
# ENDPOINTS PARA DIRECTOR FINANZAS (USUARIOS FINANCIEROS)
# ===============================================

@router.get("/finanzas/pendientes")
async def get_finanzas_pending_missions(
    page: int = Query(1, ge=1),
    size: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db_financiero),
    db_rrhh: Session = Depends(get_db_rrhh),  # ✅ AGREGADO
    current_user: Usuario = Depends(get_current_user)
):
    """Obtiene misiones pendientes de aprobación de finanzas"""
    
    if current_user.rol.nombre_rol != "Director Finanzas":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    estado_pendiente = db.query(EstadoFlujo).filter(
        EstadoFlujo.nombre_estado == "PENDIENTE_APROBACION_FINANZAS"
    ).first()
    
    if not estado_pendiente:
        return MisionListResponse(items=[], total=0, page=page, size=size, pages=0)
    
    query = db.query(MisionModel).filter(
        MisionModel.id_estado_flujo == estado_pendiente.id_estado_flujo
    )
    
    total = query.count()
    skip = (page - 1) * size
    misiones = query.order_by(MisionModel.created_at.desc()).offset(skip).limit(size).all()
    
    # ✅ OBTENER NOMBRES DE BENEFICIARIOS
    personal_ids = [m.beneficiario_personal_id for m in misiones if m.beneficiario_personal_id]
    beneficiary_names = get_beneficiary_names(db_rrhh, personal_ids)
    
    response_items = []
    for m in misiones:
        beneficiary_name = beneficiary_names.get(m.beneficiario_personal_id, "Empleado no encontrado")
        
        mission_dict = {
            "id_mision": m.id_mision,
            "numero_solicitud": m.numero_solicitud or f"SOL-{m.id_mision:06d}",
            "tipo_mision": m.tipo_mision,
            "objetivo_mision": m.objetivo_mision,
            "destino_mision": m.destino_mision,
            "fecha_salida": m.fecha_salida,
            "created_at": m.created_at,
            "monto_total_calculado": float(m.monto_total_calculado) if m.monto_total_calculado else 0.0,
            "beneficiario_nombre": beneficiary_name,  # ✅ NOMBRE REAL
            "estado_flujo": {
                "id_estado_flujo": m.estado_flujo.id_estado_flujo,
                "nombre_estado": m.estado_flujo.nombre_estado,
                "descripcion": m.estado_flujo.descripcion
            } if m.estado_flujo else None
        }
        response_items.append(MisionListResponseItem.model_validate(mission_dict))
    
    return MisionListResponse(
        items=response_items,
        total=total,
        page=page,
        size=size,
        pages=(total + size - 1) // size if size > 0 else 0
    )

@router.post("/finanzas/{mission_id}/aprobar")
async def finanzas_approve_mission(
    mission_id: int,
    request: WorkflowActionRequest,
    db: Session = Depends(get_db_financiero),
    current_user: Usuario = Depends(get_current_user)
):
    """Director de finanzas aprueba una misión"""
    
    if current_user.rol.nombre_rol != "Director Finanzas":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    mision = db.query(MisionModel).filter(MisionModel.id_mision == mission_id).first()
    if not mision:
        raise HTTPException(status_code=404, detail="Misión no encontrada")
    
    # Si se especifica monto aprobado, guardarlo
    if request.monto_aprobado:
        mision.monto_aprobado = request.monto_aprobado
    
    try:
        # Determinar próximo estado basado en si requiere refrendo CGR
        if mision.requiere_refrendo_cgr:
            # Va a PENDIENTE_REFRENDO_CGR
            nuevo_estado_nombre = "PENDIENTE_REFRENDO_CGR"
            mensaje = "Misión enviada a refrendo CGR"
        else:
            # Va directo a APROBADO_PARA_PAGO
            nuevo_estado_nombre = "APROBADO_PARA_PAGO"
            mensaje = "Misión aprobada para pago"
        
        nuevo_estado = db.query(EstadoFlujo).filter(
            EstadoFlujo.nombre_estado == nuevo_estado_nombre
        ).first()
        
        if not nuevo_estado:
            raise HTTPException(status_code=500, detail=f"Estado {nuevo_estado_nombre} no configurado")
        
        estado_anterior = mision.id_estado_flujo
        mision.id_estado_flujo = nuevo_estado.id_estado_flujo
        
        # Registrar en historial
        historial = HistorialFlujo(
            id_mision=mission_id,
            id_usuario_accion=current_user.id_usuario,
            id_estado_anterior=estado_anterior,
            id_estado_nuevo=nuevo_estado.id_estado_flujo,
            tipo_accion=TipoAccion.APROBAR,
            comentarios=f"Aprobado por Director Finanzas: {request.comentarios or 'Sin comentarios'}",
            datos_adicionales={"monto_aprobado": request.monto_aprobado} if request.monto_aprobado else None
        )
        
        db.add(historial)
        db.commit()
        
        return {
            "success": True,
            "message": mensaje,
            "nuevo_estado": nuevo_estado.nombre_estado,
            "requiere_refrendo_cgr": mision.requiere_refrendo_cgr
        }
        
    except Exception as e:
        db.rollback()
        print(f"Error procesando aprobación de finanzas: {e}")
        raise HTTPException(status_code=500, detail=f"Error procesando aprobación: {str(e)}")

# ===============================================
# ENDPOINTS PARA FISCALIZADOR CGR (USUARIOS FINANCIEROS)
# ===============================================

@router.get("/cgr/pendientes")
async def get_cgr_pending_missions(
    page: int = Query(1, ge=1),
    size: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db_financiero),
    db_rrhh: Session = Depends(get_db_rrhh),  # ✅ AGREGADO
    current_user: Usuario = Depends(get_current_user)
):
    """Obtiene misiones pendientes de refrendo CGR"""
    
    if current_user.rol.nombre_rol != "Fiscalizador CGR":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    estado_pendiente = db.query(EstadoFlujo).filter(
        EstadoFlujo.nombre_estado == "PENDIENTE_REFRENDO_CGR"
    ).first()
    
    if not estado_pendiente:
        return MisionListResponse(items=[], total=0, page=page, size=size, pages=0)
    
    query = db.query(MisionModel).filter(
        MisionModel.id_estado_flujo == estado_pendiente.id_estado_flujo
    )
    
    total = query.count()
    skip = (page - 1) * size
    misiones = query.order_by(MisionModel.created_at.desc()).offset(skip).limit(size).all()
    
    # ✅ OBTENER NOMBRES DE BENEFICIARIOS
    personal_ids = [m.beneficiario_personal_id for m in misiones if m.beneficiario_personal_id]
    beneficiary_names = get_beneficiary_names(db_rrhh, personal_ids)
    
    response_items = []
    for m in misiones:
        beneficiary_name = beneficiary_names.get(m.beneficiario_personal_id, "Empleado no encontrado")
        
        mission_dict = {
            "id_mision": m.id_mision,
            "numero_solicitud": m.numero_solicitud or f"SOL-{m.id_mision:06d}",
            "tipo_mision": m.tipo_mision,
            "objetivo_mision": m.objetivo_mision,
            "destino_mision": m.destino_mision,
            "fecha_salida": m.fecha_salida,
            "created_at": m.created_at,
            "monto_total_calculado": float(m.monto_total_calculado) if m.monto_total_calculado else 0.0,
            "beneficiario_nombre": beneficiary_name,  # ✅ NOMBRE REAL
            "estado_flujo": {
                "id_estado_flujo": m.estado_flujo.id_estado_flujo,
                "nombre_estado": m.estado_flujo.nombre_estado,
                "descripcion": m.estado_flujo.descripcion
            } if m.estado_flujo else None
        }
        response_items.append(MisionListResponseItem.model_validate(mission_dict))
    
    return MisionListResponse(
        items=response_items,
        total=total,
        page=page,
        size=size,
        pages=(total + size - 1) // size if size > 0 else 0
    )

@router.post("/cgr/{mission_id}/refrendar")
async def cgr_approve_mission(
    mission_id: int,
    request: WorkflowActionRequest,
    db: Session = Depends(get_db_financiero),
    current_user: Usuario = Depends(get_current_user)
):
    """Fiscalizador CGR refrenda una misión"""
    
    if current_user.rol.nombre_rol != "Fiscalizador CGR":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    service = MissionService(db)
    mision = service.process_workflow_action(
        mission_id=mission_id,
        user=current_user,
        action=TipoAccion.APROBAR,
        comentarios=request.comentarios
    )
    
    return {
        "success": True,
        "message": "Misión refrendada por CGR",
        "nuevo_estado": mision.estado_flujo.nombre_estado
    }

# ===============================================
# ENDPOINT PARA PAGO (TESORERÍA/CUSTODIO)
# ===============================================

@router.post("/pago/{mission_id}/procesar")
async def process_payment(
    mission_id: int,
    request: WorkflowActionRequest,
    db: Session = Depends(get_db_financiero),
    current_user: Usuario = Depends(get_current_user)
):
    """Procesa el pago de una misión aprobada"""
    
    allowed_roles = ["Analista Tesorería", "Custodio Caja Menuda"]
    if current_user.rol.nombre_rol not in allowed_roles:
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    mision = db.query(MisionModel).filter(MisionModel.id_mision == mission_id).first()
    if not mision:
        raise HTTPException(status_code=404, detail="Misión no encontrada")
    
    if mision.estado_flujo.nombre_estado != "APROBADO_PARA_PAGO":
        raise HTTPException(
            status_code=400, 
            detail=f"La misión no está aprobada para pago. Estado actual: {mision.estado_flujo.nombre_estado}"
        )
    
    try:
        # Cambiar estado a PAGADO
        estado_pagado = db.query(EstadoFlujo).filter(
            EstadoFlujo.nombre_estado == "PAGADO"
        ).first()
        
        if not estado_pagado:
            raise HTTPException(status_code=500, detail="Estado PAGADO no configurado")
        
        estado_anterior = mision.id_estado_flujo
        mision.id_estado_flujo = estado_pagado.id_estado_flujo
        
        # Registrar en historial
        historial = HistorialFlujo(
            id_mision=mission_id,
            id_usuario_accion=current_user.id_usuario,
            id_estado_anterior=estado_anterior,
            id_estado_nuevo=estado_pagado.id_estado_flujo,
            tipo_accion=TipoAccion.APROBAR,
            comentarios=f"Pago procesado por {current_user.rol.nombre_rol}: {request.comentarios or 'Sin comentarios'}"
        )
        
        db.add(historial)
        db.commit()
        
        return {
            "success": True,
            "message": "Pago procesado exitosamente",
            "nuevo_estado": estado_pagado.nombre_estado
        }
        
    except Exception as e:
        db.rollback()
        print(f"Error procesando pago: {e}")
        raise HTTPException(status_code=500, detail=f"Error procesando pago: {str(e)}")