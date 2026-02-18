# ===============================================================
# app/api/v1/missions.py (COMPLETO Y FINAL)
# ===============================================================

import os
import uuid
from typing import List, Optional, Dict
from datetime import date, datetime

from fastapi import (
    APIRouter, Depends, HTTPException, status, Query,
    UploadFile, File, BackgroundTasks, Body
)
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import text, or_

from ...core.database import get_db_financiero, get_db_rrhh
from ...core.exceptions import BusinessException, MissionException, WorkflowException, ValidationException
from ...services.mission import MissionService
from ...api.deps import get_current_user, get_current_employee

from ...models.mission import Mision as MisionModel, Adjunto, EstadoFlujo, HistorialFlujo
from ...models.user import Usuario
from ...models.enums import TipoMision, TipoDocumento, TipoAccion

from ...schemas.mission import (
    MisionCreate, MisionUpdate, MisionListResponse, MisionDetail,
    MisionListResponseItem, AttachmentUpload, WorkflowState,
    PresupuestoAssignRequest, MisionRejectionRequest, MisionApprovalRequest, Mision
)


router = APIRouter(
    tags=["Missions"],
)

# --- Configuración de Archivos ---
UPLOAD_DIR = "uploads/missions"
ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".png", ".jpg", ".jpeg"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

os.makedirs(UPLOAD_DIR, exist_ok=True)


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
    
    try:
        result = db_rrhh.execute(query, params)
        rows = result.fetchall()
        
        names_dict = {row.personal_id: row.apenom for row in rows}
        return names_dict
    except Exception as e:
        print(f"❌ Error obteniendo nombres de beneficiarios: {e}")
        return {}


# --- Endpoints Principales de Misiones (Para usuarios financieros) ---

@router.post("/", status_code=status.HTTP_201_CREATED, summary="Crear una nueva misión")
async def create_mission(
    mission_data: MisionCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db_financiero),
    db_rrhh: Session = Depends(get_db_rrhh),
    current_user: Usuario = Depends(get_current_user)
):
    """
    Crea una nueva solicitud, ya sea para **Viáticos** o para **Caja Menuda**.
    El `tipo_mision` determina qué campos son requeridos.
    """
    try:
        mission_service = MissionService(db, db_rrhh)
        
        # Si el beneficiario no se especifica, se asume que es el usuario que crea la solicitud.
        if not mission_data.beneficiario_personal_id:
            if not current_user.personal_id_rrhh:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="El usuario actual no tiene un ID de personal de RRHH asociado para ser beneficiario."
                )
            mission_data.beneficiario_personal_id = current_user.personal_id_rrhh
        
        mission = mission_service.create_mission(
            mission_data=mission_data,
            preparer_id=current_user.id_usuario
        )
        
        # Enviar notificación al jefe inmediato
        try:
            from app.services.email_service import EmailService
            
            email_service = EmailService(db)
            
            # Preparar datos para el email
            email_data = {
                'numero_solicitud': mission.numero_solicitud,
                'tipo': mission.tipo_mision.value if hasattr(mission.tipo_mision, 'value') else str(mission.tipo_mision),
                'solicitante': current_user.login_username,
                'departamento': 'Departamento del Solicitante',  # TODO: Obtener nombre del departamento
                'fecha': mission.created_at.strftime('%Y-%m-%d %H:%M:%S') if mission.created_at else datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'monto': f"${float(mission.monto_total_calculado):,.2f}" if mission.monto_total_calculado else 'N/A',
                'objetivo': mission.objetivo_mision or 'N/A'
            }
            
            # Enviar notificación al jefe inmediato en background
            import asyncio
            asyncio.create_task(email_service.send_new_request_notification(
                mission.id_mision, email_data, db_rrhh
            ))
                
        except Exception as e:
            # Log del error pero no fallar la operación principal
            print(f"Error enviando notificación al jefe inmediato: {str(e)}")
        
        return {
            "success": True,
            "message": "Solicitud creada exitosamente.",
            "data": {
                "id_mision": mission.id_mision,
                "numero_solicitud": mission.numero_solicitud,
                "estado": mission.estado_flujo.nombre_estado,
                "monto_total": float(mission.monto_total_calculado)
            }
        }
    except (ValidationException, ValueError) as ve:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(ve))
    except BusinessException as be:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(be))
    except Exception as e:
        # Loggear el error en un sistema de monitoreo
        print(f"Error inesperado al crear misión: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Ocurrió un error interno.")


@router.get("", response_model=MisionListResponse, summary="Obtener lista de misiones")
@router.get("/", response_model=MisionListResponse, summary="Obtener lista de misiones")
async def get_missions(
    page: int = Query(1, ge=1),
    size: int = Query(100, ge=1, le=1000),
    estado_id: Optional[int] = Query(None, description="Filtrar por ID de estado de flujo"),
    tipo_mision: Optional[TipoMision] = Query(None, description="Filtrar por tipo de misión"),
    fecha_desde: Optional[date] = Query(None),
    fecha_hasta: Optional[date] = Query(None),
    db: Session = Depends(get_db_financiero),
    db_rrhh: Session = Depends(get_db_rrhh),  # ✅ AGREGADO
    current_user: Usuario = Depends(get_current_user)
):
    """
    Obtiene una lista paginada de misiones. Los resultados se filtran
    automáticamente según los permisos del rol del usuario actual.
    - **Jefes Inmediatos**: Ven las solicitudes de los empleados en sus departamentos.
    - **Solicitantes**: Ven solo sus propias solicitudes.
    - **Roles Financieros/Admin**: Ven todas las solicitudes.
    """
    mission_service = MissionService(db)
    result = mission_service.get_missions(
        user=current_user, skip=(page - 1) * size, limit=size, estado_id=estado_id,
        tipo_mision=tipo_mision, fecha_desde=fecha_desde, fecha_hasta=fecha_hasta
    )
    
    # ✅ OBTENER NOMBRES DE BENEFICIARIOS
    personal_ids = [m.beneficiario_personal_id for m in result["items"] if m.beneficiario_personal_id]
    beneficiary_names = get_beneficiary_names(db_rrhh, personal_ids)
    
    response_items = []
    for m in result["items"]:
        beneficiary_name = beneficiary_names.get(m.beneficiario_personal_id, "Empleado no encontrado")
        
        mission_dict = {
            "id_mision": m.id_mision,
            "numero_solicitud": m.numero_solicitud,
            "tipo_mision": m.tipo_mision,
            "objetivo_mision": m.objetivo_mision,
            "destino_mision": m.destino_mision,
            "beneficiario_nombre": beneficiary_name,  # ✅ INCLUIDO
            "fecha_salida": m.fecha_salida,
            "monto_total_calculado": m.monto_total_calculado,
            "estado_flujo": {
                "id_estado_flujo": m.estado_flujo.id_estado_flujo,
                "nombre_estado": m.estado_flujo.nombre_estado,
                "descripcion": m.estado_flujo.descripcion
            } if m.estado_flujo else None,
            "created_at": m.created_at,
            "observacion": m.observacion
        }
        response_items.append(MisionListResponseItem.model_validate(mission_dict))
    
    return MisionListResponse(
        items=response_items,
        total=result["total"],
        page=result["page"],
        size=result["size"],
        pages=result["pages"]
    )


# --- NUEVOS ENDPOINTS PARA EMPLEADOS ---

@router.get("/employee", response_model=MisionListResponse, summary="Obtener misiones del empleado")
async def get_employee_missions(
    page: int = Query(1, ge=1),
    size: int = Query(100, ge=1, le=1000),
    search: Optional[str] = Query(None),
    estado_id: Optional[int] = Query(None, description="Filtrar por ID de estado de flujo"),
    estado: Optional[str] = Query(None, description="Filtrar por nombre de estado de flujo"),
    tipo_mision: Optional[TipoMision] = Query(None, description="Filtrar por tipo de misión"),
    fecha_desde: Optional[str] = Query(None, description="Filtrar desde esta fecha (YYYY-MM-DD)"),
    fecha_hasta: Optional[str] = Query(None, description="Filtrar hasta esta fecha (YYYY-MM-DD)"),
    monto_min: Optional[float] = Query(None, description="Filtrar por monto mínimo"),
    monto_max: Optional[float] = Query(None, description="Filtrar por monto máximo"),
    db_financiero: Session = Depends(get_db_financiero),
    db_rrhh: Session = Depends(get_db_rrhh),
    current_employee: dict = Depends(get_current_employee)
):
    """
    Obtiene las misiones del empleado autenticado.
    Busca por personal_id basado en la cédula del empleado.
    """
    try:
        # Obtener personal_id desde la cédula del empleado
        cedula = current_employee.get("cedula")
        if not cedula:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se pudo identificar la cédula del empleado"
            )
        
        # Buscar personal_id en RRHH usando esquema completo
        result = db_rrhh.execute(text("""
            SELECT personal_id FROM aitsa_rrhh.nompersonal 
            WHERE cedula = :cedula AND estado != 'De Baja'
        """), {"cedula": cedula})
        
        employee_record = result.fetchone()
        if not employee_record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Empleado no encontrado en RRHH"
            )
        
        personal_id = employee_record.personal_id
        
        # Construir query con relaciones cargadas
        query = db_financiero.query(MisionModel).options(
            joinedload(MisionModel.estado_flujo)
        ).filter(
            MisionModel.beneficiario_personal_id == personal_id
        )
        
        # Aplicar filtros
        if search:
            search_term = f"%{search}%"
            query = query.filter(
                or_(
                    MisionModel.objetivo_mision.ilike(search_term),
                    MisionModel.destino_mision.ilike(search_term),
                    MisionModel.numero_solicitud.ilike(search_term)
                )
            )
        if estado_id:
            query = query.filter(MisionModel.id_estado_flujo == estado_id)
        if estado:
            query = query.filter(MisionModel.estado_flujo.has(nombre_estado=estado))
        if tipo_mision:
            query = query.filter(MisionModel.tipo_mision == tipo_mision)
        if fecha_desde:
            query = query.filter(MisionModel.created_at >= fecha_desde)
        if fecha_hasta:
            query = query.filter(MisionModel.created_at <= fecha_hasta)
        if monto_min:
            query = query.filter(MisionModel.monto_total_calculado >= monto_min)
        if monto_max:
            query = query.filter(MisionModel.monto_total_calculado <= monto_max)
        
        # Paginación
        skip = (page - 1) * size
        total = query.count()
        missions = query.order_by(MisionModel.created_at.desc()).offset(skip).limit(size).all()
        
        # ✅ OBTENER NOMBRES DE BENEFICIARIOS
        personal_ids = [m.beneficiario_personal_id for m in missions if m.beneficiario_personal_id]
        beneficiary_names = get_beneficiary_names(db_rrhh, personal_ids)
        
        # Construir respuesta
        response_items = []
        for mission in missions:
            # Buscar la última observación de devolución
            last_return = (
                db_financiero.query(HistorialFlujo)
                .filter(
                    HistorialFlujo.id_mision == mission.id_mision,
                    HistorialFlujo.tipo_accion == "DEVOLVER"
                )
                .order_by(HistorialFlujo.fecha_accion.desc())
                .first()
            )
            observacion = last_return.observacion if last_return else None
            observacion = str(observacion) if observacion is not None else None
            # Asegurar que estado_flujo está cargado
            if not mission.estado_flujo:
                estado = db_financiero.query(EstadoFlujo).filter(
                    EstadoFlujo.id_estado_flujo == mission.id_estado_flujo
                ).first()
                mission.estado_flujo = estado
            
            beneficiary_name = beneficiary_names.get(mission.beneficiario_personal_id, "Empleado no encontrado")
            
            # Crear objeto con TODOS los campos requeridos
            mission_item = {
                "id_mision": mission.id_mision,
                "numero_solicitud": mission.numero_solicitud,
                "tipo_mision": mission.tipo_mision,
                "objetivo_mision": mission.objetivo_mision,
                "destino_mision": mission.destino_mision,
                "beneficiario_nombre": beneficiary_name,  # ✅ INCLUIDO
                "fecha_salida": mission.fecha_salida,
                "monto_total_calculado": mission.monto_total_calculado,
                "estado_flujo": {
                    "id_estado_flujo": mission.estado_flujo.id_estado_flujo,
                    "nombre_estado": mission.estado_flujo.nombre_estado,
                    "descripcion": mission.estado_flujo.descripcion
                } if mission.estado_flujo else None,
                "created_at": mission.created_at,
                "observacion": observacion
            }
            
            response_items.append(MisionListResponseItem.model_validate(mission_item))
        
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
        print(f"Error obteniendo misiones del empleado: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )


@router.get("/employee/{mission_id}", response_model=MisionDetail, summary="Obtener detalle de misión del empleado")
async def get_employee_mission_detail(
    mission_id: int,
    db_financiero: Session = Depends(get_db_financiero),
    db_rrhh: Session = Depends(get_db_rrhh),
    current_employee: dict = Depends(get_current_employee)
):
    """
    Obtiene el detalle de una misión específica del empleado autenticado.
    """
    try:
        # Verificar que la misión pertenece al empleado
        cedula = current_employee.get("cedula")
        result = db_rrhh.execute(text("""
            SELECT personal_id FROM aitsa_rrhh.nompersonal 
            WHERE cedula = :cedula AND estado != 'De Baja'
        """), {"cedula": cedula})
        
        employee_record = result.fetchone()
        if not employee_record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Empleado no encontrado")
        
        personal_id = employee_record.personal_id
        
        # Buscar la misión
        mission = db_financiero.query(MisionModel).options(
            joinedload(MisionModel.items_viaticos_completos),
            joinedload(MisionModel.misiones_caja_menuda),  # Agregado para caja menuda
            joinedload(MisionModel.estado_flujo)
        ).filter(
            MisionModel.id_mision == mission_id,
            MisionModel.beneficiario_personal_id == personal_id
        ).first()
        
        if not mission:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Misión no encontrada")
        
        # Buscar la última observación de devolución
        last_return = (
            db_financiero.query(HistorialFlujo)
            .filter(
                HistorialFlujo.id_mision == mission.id_mision,
                HistorialFlujo.tipo_accion == "DEVOLVER"
            )
            .order_by(HistorialFlujo.fecha_accion.desc())
            .first()
        )
        observacion = last_return.observacion if last_return else None
        observacion = str(observacion) if observacion is not None else None
        # Serializar usando el objeto ORM directamente
        mission_obj = Mision.model_validate(mission)
        mission_obj.observacion = observacion
        
        # Convertir a dict para agregar datos adicionales
        mission_dict = mission_obj.model_dump()
        
        # Agregar datos de caja menuda
        caja_menuda_items = []
        for item in getattr(mission, 'misiones_caja_menuda', []) or []:
            caja_menuda_items.append({
                'id_caja_menuda': item.id_caja_menuda,
                'id_mision': item.id_mision,
                'fecha': item.fecha.isoformat() if item.fecha else None,
                'hora_de': item.hora_de,
                'hora_hasta': item.hora_hasta,
                'desayuno': float(item.desayuno) if item.desayuno else 0.0,
                'almuerzo': float(item.almuerzo) if item.almuerzo else 0.0,
                'cena': float(item.cena) if item.cena else 0.0,
                'transporte': float(item.transporte) if item.transporte else 0.0
            })
        mission_dict['items_caja_menuda_detallados'] = caja_menuda_items
        
        print("DEBUG MISSION_DICT:", mission_dict)
        return {
            "mission": mission_dict,
            "beneficiary": current_employee,
            "preparer": None,
            "available_actions": [],  # Los empleados no pueden hacer acciones de workflow
            "can_edit": False,
            "can_delete": False
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error obteniendo detalle de misión del empleado: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno")


# --- Resto de endpoints originales ---

@router.get("/{mission_id}", response_model=MisionDetail, summary="Obtener detalle de una misión")
async def get_mission(
    mission_id: int,
    db: Session = Depends(get_db_financiero)
):
    """
    Obtiene el detalle completo de una misión, incluyendo ítems, historial,
    datos del beneficiario y las acciones disponibles.
    """
    try:
        # Obtener la misión con todas las relaciones
        mision = db.query(MisionModel).options(
            joinedload(MisionModel.estado_flujo),
            joinedload(MisionModel.items_viaticos),
            joinedload(MisionModel.items_viaticos_completos),
            joinedload(MisionModel.items_transporte),
            joinedload(MisionModel.partidas_presupuestarias),
            joinedload(MisionModel.historial_flujo),
            joinedload(MisionModel.adjuntos),
            joinedload(MisionModel.subsanaciones),
            joinedload(MisionModel.items_misiones_exterior),
            joinedload(MisionModel.misiones_caja_menuda),  # Agregado para caja menuda
            joinedload(MisionModel.gestiones_cobro),       # Agregado para gestiones
            joinedload(MisionModel.firmas_electronicas),   # Agregado para firmas
        ).filter(MisionModel.id_mision == mission_id).first()

        if not mision:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Misión no encontrada")

        # Obtener datos del beneficiario desde RRHH
        beneficiary_info = None
        if mision.beneficiario_personal_id:
            try:
                db_rrhh = next(get_db_rrhh())
                result = db_rrhh.execute(text("""
                    SELECT personal_id, apenom, cedula, IdDepartamento
                    FROM aitsa_rrhh.nompersonal 
                    WHERE personal_id = :personal_id AND estado != 'De Baja'
                """), {"personal_id": mision.beneficiario_personal_id})
                
                employee_record = result.fetchone()
                if employee_record:
                    beneficiary_info = {
                        "personal_id": employee_record.personal_id,
                        "nombre": employee_record.apenom,
                        "cedula": employee_record.cedula,
                        "departamento_id": employee_record.IdDepartamento
                    }
            except Exception as e:
                print(f"Error obteniendo datos del beneficiario: {e}")
                beneficiary_info = {"error": "No se pudo obtener información del beneficiario"}

        # Obtener datos del preparador
        preparer_info = None
        if mision.id_usuario_prepara:
            try:
                preparer_user = db.query(Usuario).filter(Usuario.id_usuario == mision.id_usuario_prepara).first()
                if preparer_user and preparer_user.personal_id_rrhh:
                    db_rrhh = next(get_db_rrhh())
                    result = db_rrhh.execute(text("""
                        SELECT personal_id, apenom, cedula
                        FROM aitsa_rrhh.nompersonal 
                        WHERE personal_id = :personal_id AND estado != 'De Baja'
                    """), {"personal_id": preparer_user.personal_id_rrhh})
                    
                    preparer_record = result.fetchone()
                    if preparer_record:
                        preparer_info = {
                            "personal_id": preparer_record.personal_id,
                            "nombre": preparer_record.apenom,
                            "cedula": preparer_record.cedula
                        }
            except Exception as e:
                print(f"Error obteniendo datos del preparador: {e}")

        # Obtener última observación de devolución
        last_return = (
            db.query(HistorialFlujo)
            .filter(
                HistorialFlujo.id_mision == mision.id_mision,
                HistorialFlujo.tipo_accion == "DEVOLVER"
            )
            .order_by(HistorialFlujo.fecha_accion.desc())
            .first()
        )
        observacion = last_return.observacion if last_return else None

        # Serializar la misión
        mission_dict = Mision.model_validate(mision).model_dump()
        mission_dict["observacion"] = observacion

        # Agregar viáticos completos
        viaticos_completos = []
        for item in getattr(mision, 'items_viaticos_completos', []) or []:
            viaticos_completos.append({
                'id_item_viatico_completo': item.id_item_viatico_completo,
                'id_mision': item.id_mision,
                'cantidad_dias': item.cantidad_dias,
                'monto_por_dia': float(item.monto_por_dia)
            })
        mission_dict['viaticosCompletos'] = viaticos_completos

        # Agregar datos de caja menuda
        caja_menuda_items = []
        for item in getattr(mision, 'misiones_caja_menuda', []) or []:
            caja_menuda_items.append({
                'id_caja_menuda': item.id_caja_menuda,
                'id_mision': item.id_mision,
                'fecha': item.fecha.isoformat() if item.fecha else None,
                'hora_de': item.hora_de,
                'hora_hasta': item.hora_hasta,
                'desayuno': float(item.desayuno) if item.desayuno else 0.0,
                'almuerzo': float(item.almuerzo) if item.almuerzo else 0.0,
                'cena': float(item.cena) if item.cena else 0.0,
                'transporte': float(item.transporte) if item.transporte else 0.0
            })
        mission_dict['items_caja_menuda_detallados'] = caja_menuda_items

        # Agregar datos específicos según el tipo de misión
        if mision.tipo_mision == TipoMision.VIATICOS:
            # Datos específicos para viáticos
            mission_dict['items_viaticos_detallados'] = []
            for item in getattr(mision, 'items_viaticos', []) or []:
                mission_dict['items_viaticos_detallados'].append({
                    'id_item_viatico': item.id_item_viatico,
                    'id_mision': item.id_mision,
                    'fecha': item.fecha.isoformat(),
                    'monto_desayuno': float(item.monto_desayuno) if item.monto_desayuno else 0.0,
                    'monto_almuerzo': float(item.monto_almuerzo) if item.monto_almuerzo else 0.0,
                    'monto_cena': float(item.monto_cena) if item.monto_cena else 0.0,
                    'monto_hospedaje': float(item.monto_hospedaje) if item.monto_hospedaje else 0.0
                })
            
            # Datos de transporte
            mission_dict['items_transporte_detallados'] = []
            for item in getattr(mision, 'items_transporte', []) or []:
                mission_dict['items_transporte_detallados'].append({
                    'id_item_transporte': item.id_item_transporte,
                    'id_mision': item.id_mision,
                    'fecha': item.fecha.isoformat(),
                    'tipo': item.tipo,
                    'origen': item.origen,
                    'destino': item.destino,
                    'monto': float(item.monto)
                })
            
            # Datos de misiones exterior
            mission_dict['items_misiones_exterior_detallados'] = []
            for item in getattr(mision, 'items_misiones_exterior', []) or []:
                mission_dict['items_misiones_exterior_detallados'].append({
                    'id_item_mision_exterior': item.id_item_mision_exterior,
                    'id_mision': item.id_mision,
                    'region': item.region,
                    'destino': item.destino,
                    'fecha_salida': item.fecha_salida.isoformat(),
                    'fecha_retorno': item.fecha_retorno.isoformat(),
                    'porcentaje': float(item.porcentaje) if item.porcentaje else 100.0
                 })
             
             # Agregar información adicional específica para viáticos
            mission_dict['info_viaticos'] = {
                 'total_items_viaticos': len(getattr(mision, 'items_viaticos', []) or []),
                 'total_items_transporte': len(getattr(mision, 'items_transporte', []) or []),
                 'total_items_exterior': len(getattr(mision, 'items_misiones_exterior', []) or []),
                 'monto_total_calculado': float(mision.monto_total_calculado) if mision.monto_total_calculado else 0.0,
                 'total_items_caja_menuda': len(getattr(mision, 'misiones_caja_menuda', []) or []),
                 'total_items_gestiones_cobro': len(getattr(mision, 'gestiones_cobro', []) or []),
                 'total_items_firmas_electronicas': len(getattr(mision, 'firmas_electronicas', []) or [])
             }
         
        elif mision.tipo_mision == TipoMision.CAJA_MENUDA:
             # Datos específicos para caja menuda
             mission_dict['items_caja_menuda_detallados'] = []
             for item in getattr(mision, 'misiones_caja_menuda', []) or []:
                 mission_dict['items_caja_menuda_detallados'].append({
                     'id_caja_menuda': item.id_caja_menuda,
                     'id_mision': item.id_mision,
                     'fecha': item.fecha.isoformat() if item.fecha else None,
                     'hora_de': item.hora_de,
                     'hora_hasta': item.hora_hasta,
                     'desayuno': float(item.desayuno) if item.desayuno else 0.0,
                     'almuerzo': float(item.almuerzo) if item.almuerzo else 0.0,
                     'cena': float(item.cena) if item.cena else 0.0,
                     'transporte': float(item.transporte) if item.transporte else 0.0
                 })
             
             # Agregar información adicional específica para caja menuda
             mission_dict['info_caja_menuda'] = {
                 'destino_codnivel2': mision.destino_codnivel2,
                 'total_items': len(getattr(mision, 'misiones_caja_menuda', []) or []),
                 'monto_total_calculado': float(mision.monto_total_calculado) if mision.monto_total_calculado else 0.0
             }
 
         # Agregar datos de partidas presupuestarias
        mission_dict['partidas_presupuestarias_detalladas'] = []
        for item in getattr(mision, 'partidas_presupuestarias', []) or []:
             mission_dict['partidas_presupuestarias_detalladas'].append({
                 'id_partida_mision': item.id_partida_mision,
                 'id_mision': item.id_mision,
                 'codigo_partida': item.codigo_partida,
                 'monto': float(item.monto)
             })
 
         # Agregar datos de adjuntos
        mission_dict['adjuntos_detallados'] = []
        for item in getattr(mision, 'adjuntos', []) or []:
             mission_dict['adjuntos_detallados'].append({
                 'id_adjunto': item.id_adjunto,
                 'id_mision': item.id_mision,
                 'nombre_archivo': item.nombre_archivo,
                 'nombre_original': item.nombre_original,
                 'url_almacenamiento': item.url_almacenamiento,
                 'tipo_mime': item.tipo_mime,
                 'tamano_bytes': item.tamano_bytes,
                 'tipo_documento': item.tipo_documento,
                 'fecha_carga': item.fecha_carga.isoformat() if item.fecha_carga else None
             })
 
         # Agregar datos de historial
        mission_dict['historial_detallado'] = []
        for item in getattr(mision, 'historial_flujo', []) or []:
             mission_dict['historial_detallado'].append({
                 'id_historial': item.id_historial,
                 'id_mision': item.id_mision,
                 'id_usuario_accion': item.id_usuario_accion,
                 'id_estado_anterior': item.id_estado_anterior,
                 'id_estado_nuevo': item.id_estado_nuevo,
                 'tipo_accion': item.tipo_accion,
                 'fecha_accion': item.fecha_accion.isoformat() if item.fecha_accion else None,
                 'comentarios': item.comentarios,
                 'datos_adicionales': item.datos_adicionales,
                 'ip_usuario': item.ip_usuario,
                 'observacion': item.observacion
             })
 
        return {
             "mission": mission_dict,
             "beneficiary": beneficiary_info,
             "preparer": preparer_info,
             "available_actions": [],  # Sin permisos por ahora
             "can_edit": False,
             "can_delete": False
         }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error inesperado al obtener detalle de misión: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Ocurrió un error interno.")


# --- Endpoints para Acciones del Flujo de Trabajo ---

@router.post("/{mission_id}/approve", summary="Aprobar una misión")
async def approve_mission(
    mission_id: int,
    data: MisionApprovalRequest,
    db: Session = Depends(get_db_financiero),
    current_user: Usuario = Depends(get_current_user)
):
    """Endpoint genérico para aprobar y avanzar una misión al siguiente estado."""
    try:
        service = MissionService(db)
        mission = service.process_workflow_action(
            mission_id=mission_id, user=current_user, action=TipoAccion.APROBAR,
            comentarios=data.comentarios, datos_adicionales=data.datos_adicionales
        )
        return {"success": True, "message": "Misión aprobada.", "new_state": mission.estado_flujo.nombre_estado}
    except (WorkflowException, MissionException) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{mission_id}/reject", summary="Rechazar una misión")
async def reject_mission(
    mission_id: int,
    data: MisionRejectionRequest,
    db: Session = Depends(get_db_financiero),
    current_user: Usuario = Depends(get_current_user)
):
    """Rechaza una misión, moviéndola a un estado final de 'RECHAZADO'."""
    try:
        service = MissionService(db)
        mission = service.process_workflow_action(
            mission_id=mission_id, user=current_user, action=TipoAccion.RECHAZAR,
            comentarios=f"Motivo: {data.motivo}. {data.comentarios or ''}"
        )
        return {"success": True, "message": "Misión rechazada.", "new_state": mission.estado_flujo.nombre_estado}
    except (WorkflowException, MissionException) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{mission_id}/return", summary="Devolver una misión para corrección")
async def return_mission(
    mission_id: int,
    data: MisionRejectionRequest, # Reutilizamos el schema para el motivo
    db: Session = Depends(get_db_financiero),
    current_user: Usuario = Depends(get_current_user)
):
    """Devuelve una misión al solicitante para que la corrija."""
    try:
        service = MissionService(db)
        mission = service.process_workflow_action(
            mission_id=mission_id, user=current_user, action=TipoAccion.DEVOLVER,
            comentarios=f"Motivo de devolución: {data.motivo}. {data.comentarios or ''}"
        )
        return {"success": True, "message": "Misión devuelta para corrección.", "new_state": mission.estado_flujo.nombre_estado}
    except (WorkflowException, MissionException) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{mission_id}/assign-budget", summary="Asignar partidas presupuestarias")
async def assign_budget(
    mission_id: int,
    data: PresupuestoAssignRequest,
    db: Session = Depends(get_db_financiero),
    current_user: Usuario = Depends(get_current_user)
):
    """
    Endpoint específico para que Presupuesto asigne las partidas
    y apruebe la solicitud para continuar el flujo.
    """
    if current_user.rol.nombre_rol != "Analista Presupuesto":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acción no permitida para este rol.")
    try:
        service = MissionService(db)
        mission = service.assign_budget_items(mission_id, data, current_user)
        return {"success": True, "message": "Partidas asignadas y flujo avanzado.", "new_state": mission.estado_flujo.nombre_estado}
    except (WorkflowException, MissionException) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# --- Endpoints de Utilidad ---

@router.get("/states/", response_model=List[WorkflowState], summary="Obtener todos los estados de flujo")
async def get_workflow_states(db: Session = Depends(get_db_financiero)):
    """Obtiene la lista de todos los posibles estados del flujo de trabajo."""
    return db.query(EstadoFlujo).order_by(EstadoFlujo.orden_flujo).all()


@router.post("/{mission_id}/attachments/", response_model=List[AttachmentUpload], summary="Subir archivos adjuntos a una misión")
async def upload_attachments(
    mission_id: int,
    files: List[UploadFile] = File(..., description="Lista de archivos a subir (máximo 10 en total por solicitud)"),
    tipo_documento: TipoDocumento = Query(TipoDocumento.OTRO),
    db: Session = Depends(get_db_financiero),
    current_user: Usuario = Depends(get_current_user)
):
    """
    Sube uno o varios archivos y los asocia a una misión existente.
    
    **Restricciones:**
    - Máximo 10 archivos por solicitud (contando los existentes)
    - Cada archivo máximo 10MB
    - Solo el usuario que creó la solicitud puede adjuntar archivos
    - Tipos permitidos: pdf, doc, docx, xls, xlsx, png, jpg, jpeg
    """
    # Verificar que la misión existe
    mission = db.query(MisionModel).filter(MisionModel.id_mision == mission_id).first()
    if not mission:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Misión no encontrada")
    
    # Verificar que el usuario es el creador de la solicitud
    if mission.id_usuario_prepara != current_user.id_usuario:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo el usuario que creó la solicitud puede adjuntar archivos."
        )
    
    # Contar archivos existentes
    archivos_existentes = db.query(Adjunto).filter(Adjunto.id_mision == mission_id).count()
    
    # Validar que no se exceda el límite de 10 archivos
    if archivos_existentes >= 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"La solicitud ya tiene el máximo de 10 archivos permitidos."
        )
    
    if archivos_existentes + len(files) > 10:
        archivos_disponibles = 10 - archivos_existentes
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Solo puede subir {archivos_disponibles} archivo(s) más. La solicitud ya tiene {archivos_existentes} archivo(s)."
        )
    
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debe proporcionar al menos un archivo."
        )
    
    uploaded_attachments = []
    
    for file in files:
        # Validar que el archivo tenga nombre
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uno de los archivos no tiene nombre válido."
            )
        
        # Validar extensión
        file_extension = os.path.splitext(file.filename)[1].lower()
        if file_extension not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Tipo de archivo no permitido: {file.filename}. Extensiones permitidas: {', '.join(ALLOWED_EXTENSIONS)}"
            )
        
        # Leer contenido
        contents = await file.read()
        
        # Validar tamaño
        if len(contents) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Archivo demasiado grande: {file.filename}. Tamaño máximo: 10MB."
            )
        
        # Generar nombre único y guardar
        unique_filename = f"{mission_id}_{uuid.uuid4()}{file_extension}"
        file_path = os.path.join(UPLOAD_DIR, unique_filename)
        
        with open(file_path, "wb") as buffer:
            buffer.write(contents)
        
        # Crear registro en base de datos
        attachment = Adjunto(
            id_mision=mission_id,
            nombre_archivo=unique_filename,
            nombre_original=file.filename,
            url_almacenamiento=f"/uploads/missions/{unique_filename}",
            tipo_mime=file.content_type or "application/octet-stream",
            tamano_bytes=len(contents),
            tipo_documento=tipo_documento,
            id_usuario_subio=current_user.id_usuario
        )
        db.add(attachment)
        uploaded_attachments.append(attachment)
    
    db.commit()
    
    # Refrescar todos los objetos adjuntos
    for attachment in uploaded_attachments:
        db.refresh(attachment)
    
    return uploaded_attachments