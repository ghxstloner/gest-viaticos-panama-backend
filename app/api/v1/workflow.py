# app/api/v1/workflow.py

from typing import List, Dict, Any, Optional, Union
from datetime import date, datetime
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query, Body
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import text
import logging

from ...core.database import get_db_financiero, get_db_rrhh
from ...core.exceptions import WorkflowException, BusinessException, PermissionException
from ...api.deps import get_current_user, get_current_user_universal, get_current_employee
from ...models.user import Usuario
from ...models.mission import EstadoFlujo, TransicionFlujo, HistorialFlujo, Mision
from ...schemas.workflow import *
from ...services.workflow_service import WorkflowService
from ...api.v1.missions import get_beneficiary_names
from sqlalchemy import text
from ...schemas.workflow import PartidaPresupuestariaBase, PartidaPresupuestariaResponse
from ...api.deps import get_current_user
from ...models.user import Usuario
from ...schemas.workflow import PartidaPresupuestariaCatalogoCreate, PartidaPresupuestariaResponse

# Configurar logger
logger = logging.getLogger(__name__)
from ...schemas.workflow import (
    AvailableActionsResponse, WorkflowTransitionResponse, WorkflowActionBase,
    JefeApprovalRequest, JefeRejectionRequest, JefeReturnRequest, JefeDirectApprovalRequest,
    TesoreriaApprovalRequest, PresupuestoActionRequest, ContabilidadApprovalRequest,
    FinanzasApprovalRequest, CGRApprovalRequest, PaymentProcessRequest,
    DevolverRequest, WorkflowStateInfo, UserParticipationsResponse
)

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

def has_permission(user: Union[Usuario, dict], permission_code: str) -> bool:
    """Función helper para verificar permisos - versión CORRECTA"""
    print(f"🔍 DEBUG has_permission - Verificando {permission_code} para usuario tipo: {type(user)}")
    
    if isinstance(user, dict):
        # Para empleados, verificar permisos en el dict con estructura anidada
        permissions = user.get('permisos_usuario', {})
        print(f"🔍 DEBUG has_permission - permisos_usuario: {permissions}")
        
        # Mapeo de códigos de permisos a la estructura de empleados
        permission_mapping = {
            'MISSION_APPROVE': permissions.get('misiones', {}).get('aprobar', False),
            'MISSION_REJECT': permissions.get('misiones', {}).get('aprobar', False),  # Mismo permiso para aprobar/rechazar
            'MISSION_CREATE': permissions.get('misiones', {}).get('crear', False),
            'MISSION_EDIT': permissions.get('misiones', {}).get('editar', False),
            'MISSION_VIEW': permissions.get('misiones', {}).get('ver', False),
            'MISSION_PAYMMENT': permissions.get('misiones', {}).get('pagar', False),
            'MISSION_SUBSANAR': permissions.get('misiones', {}).get('subsanar', False),  # Permiso específico para subsanar
            'GESTION_SOLICITUDES_VIEW': permissions.get('gestion_solicitudes', {}).get('ver', False),
            'REPORTS_VIEW': permissions.get('reportes', {}).get('ver', False),
        }
        
        result = permission_mapping.get(permission_code, False)
        print(f"🔍 DEBUG has_permission - {permission_code}: {result}")
        return result
    else:
        # Para usuarios financieros, usar el método del modelo
        try:
            # MÉTODO 1: Usar el método has_permission del modelo
            if hasattr(user, 'has_permission'):
                result = user.has_permission(permission_code)
                print(f"🔍 DEBUG has_permission - Usando método has_permission: {result}")
                return result
            
            # MÉTODO 2: Buscar en user.rol.permisos
            elif hasattr(user, 'rol') and hasattr(user.rol, 'permisos'):
                permisos = user.rol.permisos
                for permiso in permisos:
                    if hasattr(permiso, 'codigo') and permiso.codigo == permission_code:
                        print(f"🔍 DEBUG has_permission - Encontrado en rol.permisos: True")
                        return True
                print(f"🔍 DEBUG has_permission - No encontrado en rol.permisos: False")
                return False
            
            # MÉTODO 3: Verificar si es administrador (tiene todos los permisos)
            elif hasattr(user, 'rol') and hasattr(user.rol, 'nombre_rol'):
                if user.rol.nombre_rol == 'Administrador Sistema':
                    print(f"🔍 DEBUG has_permission - Es administrador, permitiendo: True")
                    return True
            
            print(f"🔍 DEBUG has_permission - No se encontró método para verificar permisos: False")
            return False
            
        except Exception as e:
            print(f"🔍 ERROR verificando permisos: {e}")
            return False

def get_user_permissions(user: Union[Usuario, dict]) -> List[str]:
    """Obtiene lista de códigos de permisos del usuario - versión CORRECTA"""
    if isinstance(user, dict):
        permissions = user.get('permisos_usuario', {})
        if isinstance(permissions, dict):
            # Para empleados, convertir la estructura anidada a códigos de permisos
            permission_codes = []
            
            # Misiones
            misiones = permissions.get('misiones', {})
            if misiones.get('ver'):
                permission_codes.append('MISSION_VIEW')
            if misiones.get('crear'):
                permission_codes.append('MISSION_CREATE')
            if misiones.get('editar'):
                permission_codes.append('MISSION_EDIT')
            if misiones.get('aprobar'):
                permission_codes.append('MISSION_APPROVE')
                permission_codes.append('MISSION_REJECT')
            if misiones.get('pagar'):
                permission_codes.append('MISSION_PAYMMENT')
            if misiones.get('subsanar'):
                permission_codes.append('MISSION_SUBSANAR')
            
            # Gestión de solicitudes
            gestion = permissions.get('gestion_solicitudes', {})
            if gestion.get('ver'):
                permission_codes.append('GESTION_SOLICITUDES_VIEW')
            
            # Reportes
            reportes = permissions.get('reportes', {})
            if reportes.get('ver'):
                permission_codes.append('REPORTS_VIEW')
            
            return permission_codes
        elif isinstance(permissions, list):
            return permissions
        return []
    else:
        try:
            # MÉTODO 1: Usar get_permissions del modelo
            if hasattr(user, 'get_permissions'):
                permisos = user.get_permissions()
                return permisos
            
            # MÉTODO 2: Extraer códigos de user.rol.permisos
            elif hasattr(user, 'rol') and hasattr(user.rol, 'permisos'):
                codes = []
                for permiso in user.rol.permisos:
                    if hasattr(permiso, 'codigo'):
                        codes.append(permiso.codigo)
                return codes
            
            return []
        except Exception as e:
            print(f"🔍 ERROR obteniendo permisos: {e}")
            return []

def is_jefe_inmediato(user: Union[Usuario, dict]) -> bool:
    """Función para verificar si el usuario es jefe inmediato usando permisos"""
    if isinstance(user, dict):
        has_approve_permission = has_permission(user, 'MISSION_APPROVE')
        is_department_head = user.get('is_department_head', False)
        return has_approve_permission and is_department_head
    else:
        # Para usuarios financieros, solo verificar el permiso
        return has_permission(user, 'MISSION_APPROVE')

def validate_employee_user(user):
    """Valida que el usuario sea un empleado - DEPRECATED: Ahora se usa validación por permisos"""
    # Esta función se mantiene por compatibilidad pero ya no valida tipo de usuario
    return user

# ===============================================
# ENDPOINTS UNIVERSALES (EMPLEADOS Y FINANCIEROS)
# ===============================================

@router.get("/missions/{mission_id}/actions", response_model=AvailableActionsResponse)
async def get_available_actions(
    mission_id: int,
    workflow_service: WorkflowService = Depends(get_workflow_service),
    current_user = Depends(get_current_user_universal)
):
    """
    Obtiene las acciones disponibles para un usuario en una misión específica.
    Funciona tanto para usuarios financieros como empleados.
    """
    try:
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuario no autenticado"
            )
        
        return workflow_service.get_available_actions(mission_id, current_user)
        
    except (WorkflowException, PermissionException) as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/states/my-relevant", response_model=List[WorkflowStateInfo])
async def get_my_relevant_states(
    workflow_service: WorkflowService = Depends(get_workflow_service),
    current_user = Depends(get_current_user_universal)
):
    """
    Obtiene los estados de workflow relevantes para el usuario actual.
    """
    try:
        if not current_user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario no autenticado")
        
        return workflow_service.get_workflow_states_by_role(current_user)
        
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

# ===============================================
# ENDPOINTS PARA APROBACIONES Y ACCIONES DE WORKFLOW
# ===============================================

@router.post("/missions/{mission_id}/jefe/aprobar", response_model=WorkflowTransitionResponse)
async def jefe_approve_mission(
    mission_id: int,
    request_data: JefeApprovalRequest,
    workflow_service: WorkflowService = Depends(get_workflow_service),
    current_user = Depends(get_current_user_universal),
    client_ip: str = Depends(get_client_ip)
):
    """
    Permite aprobar una solicitud (empleados jefes o usuarios financieros con permisos).
    """
    try:
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuario no autenticado"
            )
        
        # Verificar permisos - solo verificar el permiso, no el rol específico
        if not has_permission(current_user, 'MISSION_APPROVE'):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permiso requerido: MISSION_APPROVE"
            )
        
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

@router.post("/missions/{mission_id}/jefe/rechazar", response_model=WorkflowTransitionResponse)
async def jefe_reject_mission(
    mission_id: int,
    request_data: JefeRejectionRequest,
    workflow_service: WorkflowService = Depends(get_workflow_service),
    current_user = Depends(get_current_user_universal),
    client_ip: str = Depends(get_client_ip)
):
    """
    Permite rechazar una solicitud (empleados jefes o usuarios financieros con permisos).
    """
    try:
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuario no autenticado"
            )
        
        # Verificar permisos - solo verificar el permiso, no el rol específico
        if not has_permission(current_user, 'MISSION_REJECT'):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permiso requerido: MISSION_REJECT"
            )
        
        return workflow_service.execute_workflow_action(
            mission_id=mission_id,
            action="RECHAZAR",
            user=current_user,
            request_data=request_data,
            client_ip=client_ip
        )
        
    except (WorkflowException, PermissionException) as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post("/missions/{mission_id}/jefe/devolver", response_model=WorkflowTransitionResponse)
async def jefe_return_for_correction(
    mission_id: int,
    request_data: JefeReturnRequest,
    workflow_service: WorkflowService = Depends(get_workflow_service),
    current_user = Depends(get_current_user_universal),
    client_ip: str = Depends(get_client_ip),
    db: Session = Depends(get_db_financiero)
):
    """
    Permite devolver una solicitud para corrección (empleados jefes o usuarios financieros con permisos).
    """
    try:
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuario no autenticado"
            )
        
        # Verificar permisos - usar permiso específico para devolver/subsanar
        if not has_permission(current_user, 'MISSION_SUBSANAR'):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permiso requerido: MISSION_SUBSANAR"
            )
        
        # Obtener y validar la misión
        mision = workflow_service._get_mission_with_validation(mission_id, current_user)
        
        # Solo validar supervisión si es empleado
        if isinstance(current_user, dict):
            workflow_service._validate_employee_supervision(mision, current_user)
        
        estado_anterior = mision.estado_flujo.nombre_estado
        estado_anterior_id = mision.id_estado_flujo
        
        # Determinar el nuevo estado usando la nueva lógica de devolución
        nuevo_estado_id = workflow_service._determine_return_state(estado_anterior, mision)
        
        # Obtener el nombre del nuevo estado
        nuevo_estado_nombre = "DEVUELTO_CORRECCION"  # Fallback
        for nombre, estado in workflow_service._states_cache.items():
            if estado.id_estado_flujo == nuevo_estado_id:
                nuevo_estado_nombre = nombre
                break
        
        # Cambiar estado usando la nueva lógica
        mision.id_estado_flujo = nuevo_estado_id
        
        # Crear historial
        # Para empleados (dict) dejar NULL en id_usuario_accion y registrar la cédula en datos_adicionales
        user_id = current_user.id_usuario if hasattr(current_user, 'id_usuario') else None
        user_name = current_user.login_username if hasattr(current_user, 'login_username') else current_user.get('apenom', 'Usuario')
        
        historial = HistorialFlujo(
            id_mision=mision.id_mision,
            id_usuario_accion=user_id,
            id_estado_anterior=estado_anterior_id,
            id_estado_nuevo=nuevo_estado_id,
            tipo_accion="DEVOLVER",
            comentarios=None,
            observacion=request_data.observacion,
            datos_adicionales={
                'usuario_cedula': current_user.get('cedula') if isinstance(current_user, dict) else None,
                'usuario_nombre': user_name,
                'estado_anterior': estado_anterior,
                'estado_nuevo': nuevo_estado_nombre
            },
            ip_usuario=client_ip
        )
        
        db.add(historial)
        db.commit()
        
        # Enviar notificación por email (asíncrono)
        try:
            import asyncio
            from app.api.v1.missions import get_beneficiary_names
            
            # Preparar datos para la notificación
            data = {
                'numero_solicitud': mision.numero_solicitud,
                'tipo': mision.tipo_mision.value,
                'solicitante': get_beneficiary_names(workflow_service.db_rrhh, [mision.beneficiario_personal_id]).get(mision.beneficiario_personal_id, 'N/A'),
                'fecha': mision.fecha_salida.strftime('%d/%m/%Y') if mision.fecha_salida else 'N/A',
                'monto': f"${mision.monto_total_calculado:,.2f}",
                'objetivo': mision.objetivo_mision or 'N/A'
            }
            
            print(f"DEBUG EMAIL: Enviando notificación de devolución para misión {mission_id}")
            print(f"DEBUG EMAIL: nuevo_estado_nombre={nuevo_estado_nombre}")
            print(f"DEBUG EMAIL: user_name={user_name}")
            
            # Enviar notificación de devolución
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Si ya hay un loop corriendo, crear una tarea
                    asyncio.create_task(
                        workflow_service._email_service.send_return_notification(
                            mission_id=mision.id_mision,
                            return_state=nuevo_estado_nombre,
                            returned_by=user_name,
                            observaciones=request_data.observacion,
                            data=data,
                            db_rrhh=workflow_service.db_rrhh
                        )
                    )
                else:
                    # Si no hay loop corriendo, ejecutar directamente
                    loop.run_until_complete(
                        workflow_service._email_service.send_return_notification(
                            mission_id=mision.id_mision,
                            return_state=nuevo_estado_nombre,
                            returned_by=user_name,
                            observaciones=request_data.observacion,
                            data=data,
                            db_rrhh=workflow_service.db_rrhh
                        )
                    )
            except Exception as e:
                print(f"DEBUG EMAIL ERROR en asyncio: {str(e)}")
                # Fallback: intentar ejecutar de forma síncrona
                try:
                    import asyncio
                    asyncio.run(
                        workflow_service._email_service.send_return_notification(
                            mission_id=mision.id_mision,
                            return_state=nuevo_estado_nombre,
                            returned_by=user_name,
                            observaciones=request_data.observacion,
                            data=data,
                            db_rrhh=workflow_service.db_rrhh
                        )
                    )
                except Exception as e2:
                    print(f"DEBUG EMAIL ERROR en fallback: {str(e2)}")
            
            print(f"DEBUG EMAIL: Tarea de notificación de devolución creada exitosamente")
            
        except Exception as e:
            logger.error(f"Error enviando notificación de devolución: {str(e)}")
            print(f"DEBUG EMAIL ERROR: {str(e)}")
        
        # Crear notificaciones según el tipo de devolución
        try:
            print(f"DEBUG NOTIFICATION: Creando notificaciones de devolución desde endpoint jefe/devolver")
            print(f"DEBUG NOTIFICATION: nuevo_estado_nombre={nuevo_estado_nombre}")
            
            from ...schemas.notification import NotificacionCreate
            
            # Determinar el tipo de solicitud para personalizar el mensaje
            tipo_solicitud = mision.tipo_mision.value if hasattr(mision.tipo_mision, 'value') else str(mision.tipo_mision)
            if tipo_solicitud == 'VIATICOS':
                tipo_descripcion = "Viáticos"
            elif tipo_solicitud == 'CAJA_MENUDA':
                tipo_descripcion = "Caja Menuda"
            else:
                tipo_descripcion = tipo_solicitud
            
            if nuevo_estado_nombre == "DEVUELTO_CORRECCION":
                # Para DEVUELTO_CORRECCION: notificación para el solicitante
                print(f"DEBUG NOTIFICATION: Creando notificación para solicitante (DEVUELTO_CORRECCION)")
                titulo = f"Solicitud de {tipo_descripcion} Devuelta - {mision.numero_solicitud}"
                descripcion = f"Solicitud de {tipo_descripcion} {mision.numero_solicitud} devuelta para corrección por {user_name}"
                
                notification_data = NotificacionCreate(
                    titulo=titulo,
                    descripcion=descripcion,
                    personal_id=mision.beneficiario_personal_id,
                    id_mision=mision.id_mision,
                    visto=False
                )
                
                workflow_service._notification_service.create_notification(notification_data)
                print(f"DEBUG NOTIFICATION: Notificación creada para solicitante")
                
            elif nuevo_estado_nombre == "DEVUELTO_CORRECCION_JEFE":
                # Para DEVUELTO_CORRECCION_JEFE: notificación para el jefe inmediato
                print(f"DEBUG NOTIFICATION: Creando notificación para jefe inmediato (DEVUELTO_CORRECCION_JEFE)")
                print(f"DEBUG NOTIFICATION: beneficiario_personal_id={mision.beneficiario_personal_id}")
                
                # Obtener el jefe inmediato del departamento del solicitante
                jefe_personal_id = workflow_service._get_jefe_inmediato_personal_id(mision.beneficiario_personal_id)
                print(f"DEBUG NOTIFICATION: jefe_personal_id encontrado={jefe_personal_id}")
                
                if jefe_personal_id:
                    titulo = f"Solicitud de {tipo_descripcion} Devuelta - {mision.numero_solicitud}"
                    descripcion = f"Solicitud de {tipo_descripcion} {mision.numero_solicitud} devuelta para corrección por {user_name}"
                    
                    notification_data = NotificacionCreate(
                        titulo=titulo,
                        descripcion=descripcion,
                        personal_id=jefe_personal_id,
                        id_mision=mision.id_mision,
                        visto=False
                    )
                    
                    try:
                        workflow_service._notification_service.create_notification(notification_data)
                        print(f"DEBUG NOTIFICATION: Notificación creada exitosamente para jefe inmediato (personal_id={jefe_personal_id})")
                    except Exception as e:
                        print(f"DEBUG NOTIFICATION ERROR: Error creando notificación para jefe: {str(e)}")
                else:
                    print(f"DEBUG NOTIFICATION: No se encontró jefe inmediato para personal_id={mision.beneficiario_personal_id}")
                    print(f"DEBUG NOTIFICATION: Verificar si el empleado tiene jefe asignado en departamento_aprobadores_maestros")
                    
            else:
                # Para otros estados de devolución: notificaciones para todos los usuarios del departamento anterior
                print(f"DEBUG NOTIFICATION: Creando notificaciones para departamento anterior ({nuevo_estado_nombre})")
                
                # Obtener el departamento anterior basado en el estado actual
                departamento_anterior_id = workflow_service._get_previous_department_id(estado_anterior)
                
                if departamento_anterior_id:
                    titulo = f"Solicitud de {tipo_descripcion} Devuelta - {mision.numero_solicitud}"
                    descripcion = f"Solicitud de {tipo_descripcion} {mision.numero_solicitud} devuelta para corrección por {user_name}"
                    
                    # Obtener personal_ids de usuarios del departamento anterior
                    department_personal_ids = workflow_service._notification_service.get_department_users_personal_ids(departamento_anterior_id)
                    print(f"DEBUG NOTIFICATION: Usuarios en departamento anterior {departamento_anterior_id}: {department_personal_ids}")
                    
                    # Crear notificaciones para cada usuario del departamento anterior
                    for personal_id in department_personal_ids:
                        notification_data = NotificacionCreate(
                            titulo=titulo,
                            descripcion=descripcion,
                            personal_id=personal_id,
                            id_mision=mision.id_mision,
                            visto=False
                        )
                        
                        workflow_service._notification_service.create_notification(notification_data)
                        print(f"DEBUG NOTIFICATION: Notificación creada para usuario {personal_id} del departamento anterior")
                    
                    print(f"DEBUG NOTIFICATION: {len(department_personal_ids)} notificaciones creadas para departamento anterior (id={departamento_anterior_id})")
                else:
                    print(f"DEBUG NOTIFICATION: No se encontró departamento anterior para estado={estado_anterior}")
            
        except Exception as e:
            logger.error(f"Error creando notificaciones de devolución: {str(e)}")
            print(f"DEBUG NOTIFICATION ERROR: {str(e)}")
        
        return WorkflowTransitionResponse(
            success=True,
            message=f'Solicitud devuelta para corrección por {user_name}',
            mission_id=mission_id,
            estado_anterior=estado_anterior,
            estado_nuevo=nuevo_estado_nombre,
            accion_ejecutada="DEVOLVER",
            requiere_accion_adicional=True,
            datos_transicion={
                'observacion': request_data.observacion,
                'estado_anterior': estado_anterior,
                'estado_nuevo': nuevo_estado_nombre
            }
        )
        
    except (WorkflowException, PermissionException) as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post("/missions/{mission_id}/jefe/aprobar-directo", response_model=WorkflowTransitionResponse)
async def jefe_approve_direct_payment(
    mission_id: int,
    request_data: JefeDirectApprovalRequest,
    workflow_service: WorkflowService = Depends(get_workflow_service),
    current_user = Depends(get_current_user_universal),
    client_ip: str = Depends(get_client_ip),
    db: Session = Depends(get_db_financiero)
):
    """
    Permite aprobar directamente para pago (empleados jefes o usuarios financieros con permisos).
    """
    try:
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuario no autenticado"
            )
        
        # Verificar permisos - solo verificar el permiso, no el rol específico
        if not has_permission(current_user, 'MISSION_APPROVE'):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permiso requerido: MISSION_APPROVE"
            )
        
        # Obtener y validar la misión
        mision = workflow_service._get_mission_with_validation(mission_id, current_user)
        
        # Solo validar supervisión si es empleado
        if isinstance(current_user, dict):
            workflow_service._validate_employee_supervision(mision, current_user)
        
        estado_anterior = mision.estado_flujo.nombre_estado
        estado_anterior_id = mision.id_estado_flujo
        
        # Actualizar monto si se especifica
        if hasattr(request_data, 'monto_aprobado') and request_data.monto_aprobado:
            mision.monto_aprobado = request_data.monto_aprobado
        else:
            mision.monto_aprobado = mision.monto_total_calculado
        
        # Cambiar estado directamente
        mision.id_estado_flujo = 6  # APROBADO_PARA_PAGO
        
        # Crear historial
        # Para empleados (dict) dejar NULL en id_usuario_accion y registrar la cédula en datos_adicionales
        user_id = current_user.id_usuario if isinstance(current_user, Usuario) else None
        user_name = current_user.login_username if isinstance(current_user, Usuario) else current_user.get('apenom', 'Usuario')
        
        historial = HistorialFlujo(
            id_mision=mision.id_mision,
            id_usuario_accion=user_id,
            id_estado_anterior=estado_anterior_id,
            id_estado_nuevo=6,
            tipo_accion="APROBAR_DIRECTO",
            comentarios=request_data.comentarios,
            observacion=request_data.comentarios,
            datos_adicionales={
                'justificacion': getattr(request_data, 'justificacion', 'Aprobación directa'),
                'es_emergencia': getattr(request_data, 'es_emergencia', False),
                'monto_aprobado': float(mision.monto_aprobado),
                'usuario_cedula': current_user.get('cedula') if isinstance(current_user, dict) else None,
                'usuario_nombre': user_name
            },
            ip_usuario=client_ip
        )
        
        db.add(historial)
        db.commit()
        
        return WorkflowTransitionResponse(
            success=True,
            message=f'Solicitud aprobada directamente para pago por {user_name}',
            mission_id=mission_id,
            estado_anterior=estado_anterior,
            estado_nuevo="APROBADO_PARA_PAGO",
            accion_ejecutada="APROBAR_DIRECTO",
            requiere_accion_adicional=False,
            datos_transicion={
                'justificacion': getattr(request_data, 'justificacion', 'Aprobación directa'),
                'monto_aprobado': float(mision.monto_aprobado)
            }
        )
        
    except Exception as e:
        db.rollback()
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
    Permite aprobar una solicitud en tesorería.
    """
    try:
        if not has_permission(current_user, 'MISSION_TESORERIA_APPROVE'):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permiso requerido: MISSION_TESORERIA_APPROVE"
            )
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
    Permite asignar partidas presupuestarias.
    """
    try:
        if not has_permission(current_user, 'MISSION_PRESUPUESTO_VIEW'):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permiso requerido: MISSION_PRESUPUESTO_VIEW"
            )
        
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
    Permite aprobar en contabilidad.
    """
    try:
        if not has_permission(current_user, 'CONTABILIDAD_VIEW'):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permiso requerido: CONTABILIDAD_VIEW"
            )
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
    Permite aprobación final de finanzas.
    """
    try:
        if not has_permission(current_user, 'MISSION_DIR_FINANZAS_APPROVE'):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permiso requerido: MISSION_DIR_FINANZAS_APPROVE"
            )
        
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
    Permite refrendo de CGR.
    """
    try:
        if not has_permission(current_user, 'MISSION_CGR_APPROVE'):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permiso requerido: MISSION_CGR_APPROVE"
            )
        
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
    Permite procesar el pago de una solicitud.
    """
    try:
        if not has_permission(current_user, 'MISSION_PAYMMENT'):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permiso requerido: MISSION_PAYMMENT"
            )
        
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
    """
    try:
        if not has_permission(current_user, 'MISSION_PAYMMENT'):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permiso requerido: MISSION_PAYMMENT"
            )
        
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
    request_data: DevolverRequest,
    workflow_service: WorkflowService = Depends(get_workflow_service),
    current_user = Depends(get_current_user_universal),
    client_ip: str = Depends(get_client_ip)
):
    """
    Permite devolver una solicitud para corrección.
    Disponible para cualquier rol autorizado en el flujo.
    """
    try:
        if not current_user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario no autenticado")
        
        return workflow_service.execute_workflow_action(
            mission_id=mission_id,
            action="DEVOLVER",
            user=current_user,
            request_data=request_data,
            client_ip=client_ip
        )
        
    except (WorkflowException, PermissionException) as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

# ===============================================
# ENDPOINT PRINCIPAL PARA OBTENER PENDIENTES
# ===============================================

@router.get("/pendientes")
async def get_pending_missions(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    tipo_mision: Optional[str] = Query(None),
    estado: Optional[str] = Query(None, description="Filtrar por nombre de estado de flujo"),
    fecha_desde: Optional[str] = Query(None, description="Filtrar desde esta fecha (YYYY-MM-DD)"),
    fecha_hasta: Optional[str] = Query(None, description="Filtrar hasta esta fecha (YYYY-MM-DD)"),
    workflow_service: WorkflowService = Depends(get_workflow_service),
    current_user = Depends(get_current_user_universal)
):
    """
    Obtiene las solicitudes pendientes según los permisos del usuario.
    Funciona tanto para usuarios financieros como empleados.
    """  
    try:
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuario no autenticado"
            )
        
        # Verificar permisos según el tipo de usuario
        if isinstance(current_user, dict):
            # Verificar permisos específicos
            mission_approve = has_permission(current_user, 'MISSION_APPROVE')
            gestion_view = has_permission(current_user, 'GESTION_SOLICITUDES_VIEW')
            is_jefe = is_jefe_inmediato(current_user)         
            # Para empleados, verificar si es jefe inmediato
            if not is_jefe:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Solo los jefes de departamento pueden acceder a las solicitudes pendientes"
                )
        else:
            # Para usuarios financieros, verificar permiso específico
            if not has_permission(current_user, 'GESTION_SOLICITUDES_VIEW'):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Permiso requerido: GESTION_SOLICITUDES_VIEW"
                )
        filters = {
            "page": page,
            "size": size,
            "search": search,
            "tipo_mision": tipo_mision,
            "estado": estado,
            "fecha_desde": fecha_desde,
            "fecha_hasta": fecha_hasta
        }
        
        result = workflow_service.get_pending_missions_by_permission(current_user, filters)
        # Obtener nombres de beneficiarios
        personal_ids = [m.beneficiario_personal_id for m in result['items'] if getattr(m, 'beneficiario_personal_id', None)]
        beneficiary_names = get_beneficiary_names(workflow_service.db_rrhh, personal_ids)
        missions_response = []
        for m in result['items']:
            if hasattr(m, 'model_dump'):
                m_dict = m.model_dump()
            elif hasattr(m, 'dict'):
                m_dict = m.dict()
            else:
                m_dict = vars(m)
            m_dict['beneficiario_nombre'] = beneficiary_names.get(getattr(m, 'beneficiario_personal_id', None), "No encontrado")
            missions_response.append(m_dict)
        result['items'] = missions_response
        return result
        
    except HTTPException:
        print(f"🔍 DEBUG - HTTPException capturada y re-lanzada")
        raise
    except Exception as e:
        print(f"🔍 ERROR en pendientes: {str(e)}")
        import traceback
        print(f"🔍 ERROR traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

# ===============================================
# ENDPOINTS DE CONSULTA Y UTILIDADES
# ===============================================

@router.get("/budget-items", response_model=List[PartidaPresupuestariaResponse])
async def get_budget_items_catalog(
    search: Optional[str] = Query(None, description="Buscar partidas por código o descripción"),
    workflow_service: WorkflowService = Depends(get_workflow_service),
    current_user = Depends(get_current_user_universal)
):
    """
    Obtiene el catálogo de partidas presupuestarias disponibles.
    Disponible para empleados y usuarios financieros con el permiso correspondiente.
    """
    try:
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuario no autenticado"
            )
        
        # Verificar permisos - funciona tanto para empleados como usuarios financieros
        if not has_permission(current_user, 'MISSION_PRESUPUESTO_VIEW'):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permiso requerido: MISSION_PRESUPUESTO_VIEW"
            )
        
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

@router.post("/budget-items", response_model=PartidaPresupuestariaResponse) 
async def create_budget_item(
    data: PartidaPresupuestariaCatalogoCreate,  # <--- usa el nuevo esquema aquí
    db_rrhh: Session = Depends(get_db_rrhh),
    current_user: Usuario = Depends(get_current_user)
):
    try:
        db_rrhh.execute(
            text("""
                INSERT INTO aitsa_rrhh.cwprecue (CodCue, Denominacion, Tipocta, Tipopuc)
                VALUES (:codcue, :denominacion, 0, '0')
            """),
            {
                "codcue": data.codigo_partida,
                "denominacion": data.descripcion
            }
        )
        db_rrhh.commit()
        return PartidaPresupuestariaResponse(
            codigo_partida=data.codigo_partida,
            descripcion=data.descripcion,
            es_activa=True
        )
    except Exception as e:
        db_rrhh.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/missions/{mission_id}/next-states")
async def get_next_possible_states(
    mission_id: int,
    workflow_service: WorkflowService = Depends(get_workflow_service),
    current_user = Depends(get_current_user_universal)
):
    """
    Obtiene los posibles próximos estados para una misión específica.
    """
    try:
        if not current_user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario no autenticado")
        
        actions = workflow_service.get_available_actions(mission_id, current_user)
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

@router.get("/user-participations")
async def get_user_participations(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    estado: Optional[str] = Query(None, description="Filtrar por estado de la misión (PENDIENTE_JEFE, APROBADO_PARA_PAGO, etc.)"),
    tipo_mision: Optional[str] = Query(None, description="Filtrar por tipo de misión"),
    fecha_desde: Optional[str] = Query(None, description="Filtrar desde esta fecha (YYYY-MM-DD)"),
    fecha_hasta: Optional[str] = Query(None, description="Filtrar hasta esta fecha (YYYY-MM-DD)"),
    workflow_service: WorkflowService = Depends(get_workflow_service),
    current_user = Depends(get_current_user_universal)
):
    """
    Obtiene todas las solicitudes en las que ha participado un usuario
    (aprobado, rechazado, devuelto, etc.) - agrupadas por misión para evitar duplicados
    """
    try:
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuario no autenticado"
            )

        filters = {
            "page": page,
            "size": size,
            "search": search,
            "estado": estado,
            "tipo_mision": tipo_mision,
            "fecha_desde": fecha_desde,
            "fecha_hasta": fecha_hasta
        }

        result = workflow_service.get_user_participations(current_user, filters)
        
        # Obtener nombres de beneficiarios
        personal_ids = [m.beneficiario_personal_id for m in result['items'] if getattr(m, 'beneficiario_personal_id', None)]
        beneficiary_names = get_beneficiary_names(workflow_service.db_rrhh, personal_ids)
        missions_response = []
        for m in result['items']:
            if hasattr(m, 'model_dump'):
                m_dict = m.model_dump()
            elif hasattr(m, 'dict'):
                m_dict = m.dict()
            else:
                m_dict = vars(m)
            m_dict['beneficiario_nombre'] = beneficiary_names.get(getattr(m, 'beneficiario_personal_id', None), "No encontrado")
            missions_response.append(m_dict)
        result['items'] = missions_response
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"🔍 ERROR en user-participations: {str(e)}")
        import traceback
        print(f"🔍 ERROR traceback: {traceback.format_exc()}")
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
        # Verificar permisos de administrador
        if not has_permission(current_user, 'SYSTEM_CONFIG'):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permiso requerido: SYSTEM_CONFIG"
            )
        
        # Estadísticas básicas del sistema
        total_estados = db.query(EstadoFlujo).count()
        total_transiciones = db.query(TransicionFlujo).filter(TransicionFlujo.es_activa == True).count()
        
        return {
            "total_estados": total_estados,
            "total_transiciones_activas": total_transiciones,
            "tipos_flujo_soportados": ["VIATICOS", "CAJA_MENUDA", "AMBOS"],
            "permisos_workflow": [
                "MISSION_APPROVE", "MISSION_REJECT", "MISSION_PAYMMENT",
                "GESTION_SOLICITUDES_VIEW", "PAGOS_VIEW", "MISSION_PRESUPUESTO_VIEW",
                "CONTABILIDAD_VIEW", "FISCALIZACION_VIEW"
            ]
        }
        
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

# ===============================================
# ENDPOINT DE DEBUG
# ===============================================

@router.get("/debug/user-permissions")
async def debug_user_permissions(
    current_user = Depends(get_current_user_universal)
):
    """
    Endpoint de debug para ver permisos del usuario.
    """
    try:
        if not current_user:
            return {"error": "No user authenticated"}
        
        if isinstance(current_user, dict):
            return {
                "user_type": "employee",
                "permissions": current_user.get('permisos_usuario', {}),
                "is_department_head": current_user.get('is_department_head', False),
                "relevant_permissions": {
                    "MISSION_APPROVE": has_permission(current_user, 'MISSION_APPROVE'),
                    "MISSION_REJECT": has_permission(current_user, 'MISSION_REJECT'),
                    "MISSION_PAYMMENT": has_permission(current_user, 'MISSION_PAYMMENT'),
                    "GESTION_SOLICITUDES_VIEW": has_permission(current_user, 'GESTION_SOLICITUDES_VIEW'),
                    "PAGOS_VIEW": has_permission(current_user, 'PAGOS_VIEW'),
                    "MISSION_PRESUPUESTO_VIEW": has_permission(current_user, 'MISSION_PRESUPUESTO_VIEW'),
                    "CONTABILIDAD_VIEW": has_permission(current_user, 'CONTABILIDAD_VIEW'),
                    "FISCALIZACION_VIEW": has_permission(current_user, 'FISCALIZACION_VIEW')
                },
                "is_jefe_inmediato": is_jefe_inmediato(current_user),
                "permission_mapping_test": {
                    "misiones.aprobar": current_user.get('permisos_usuario', {}).get('misiones', {}).get('aprobar', False),
                    "gestion_solicitudes.ver": current_user.get('permisos_usuario', {}).get('gestion_solicitudes', {}).get('ver', False),
                    "reportes.ver": current_user.get('permisos_usuario', {}).get('reportes', {}).get('ver', False)
                }
            }
        else:
            return {
                "user_type": "financial_user",
                "username": current_user.login_username,
                "permissions": getattr(current_user, 'permisos_usuario', {}),
                "relevant_permissions": {
                    "MISSION_APPROVE": has_permission(current_user, 'MISSION_APPROVE'),
                    "MISSION_REJECT": has_permission(current_user, 'MISSION_REJECT'),
                    "MISSION_PAYMMENT": has_permission(current_user, 'MISSION_PAYMMENT'),
                    "GESTION_SOLICITUDES_VIEW": has_permission(current_user, 'GESTION_SOLICITUDES_VIEW'),
                    "PAGOS_VIEW": has_permission(current_user, 'PAGOS_VIEW'),
                    "MISSION_PRESUPUESTO_VIEW": has_permission(current_user, 'MISSION_PRESUPUESTO_VIEW'),
                    "CONTABILIDAD_VIEW": has_permission(current_user, 'CONTABILIDAD_VIEW'),
                    "FISCALIZACION_VIEW": has_permission(current_user, 'FISCALIZACION_VIEW')
                },
                "is_jefe_inmediato": is_jefe_inmediato(current_user)
            }
            
    except Exception as e:
        return {"error": str(e)}

@router.get("/debug/user-permissions-complete")
async def debug_user_permissions_complete(
    current_user: Usuario = Depends(get_current_user)
):
    """
    Debug completo para ver TODOS los atributos del usuario financiero.
    """
    try:
        return {
            "user_type": "financial_user",
            "username": current_user.login_username,
            "user_id": current_user.id_usuario,
            "all_attributes": [attr for attr in dir(current_user) if not attr.startswith('_')],
            "permissions_attr_exists": hasattr(current_user, 'permissions'),
            "permisos_usuario_attr_exists": hasattr(current_user, 'permisos_usuario'),
            
            # Intentar acceder a diferentes posibles atributos de permisos
            "rol_object": {
                "nombre": current_user.rol.nombre_rol if hasattr(current_user, 'rol') else None,
                "rol_attributes": [attr for attr in dir(current_user.rol) if not attr.startswith('_')] if hasattr(current_user, 'rol') else []
            },
            
            # Verificar si los permisos están en el rol
            "rol_permissions": getattr(current_user.rol, 'permissions', None) if hasattr(current_user, 'rol') else None,
            "rol_permisos": getattr(current_user.rol, 'permisos', None) if hasattr(current_user, 'rol') else None,
            
            # Verificar atributos del usuario directamente
            "user_permissions": getattr(current_user, 'permissions', None),
            "user_permisos": getattr(current_user, 'permisos', None),
            "user_permisos_usuario": getattr(current_user, 'permisos_usuario', None),   
            
            # Intentar acceder a relationships
            "relationships": {
                attr: str(getattr(current_user, attr)) 
                for attr in dir(current_user) 
                if not attr.startswith('_') and hasattr(current_user, attr)
            }
        }
        
    except Exception as e:
        import traceback
        return {
            "error": str(e),
            "traceback": traceback.format_exc()
        }

@router.get("/debug/mission/{mission_id}/state")
async def debug_mission_state(
    mission_id: int,
    workflow_service: WorkflowService = Depends(get_workflow_service),
    current_user = Depends(get_current_user_universal)
):
    """
    Debug para verificar el estado de una misión específica.
    """
    try:
        if not current_user:
            return {"error": "No user authenticated"}
        
        # Obtener la misión sin validaciones de permisos para debug
        mision = workflow_service.db.query(Mision).options(
            joinedload(Mision.estado_flujo)
        ).filter(Mision.id_mision == mission_id).first()
        
        if not mision:
            return {"error": f"Misión {mission_id} no encontrada"}
        
        return {
            "mission_id": mission_id,
            "id_estado_flujo": mision.id_estado_flujo,
            "estado_flujo_loaded": mision.estado_flujo is not None,
            "estado_flujo_nombre": mision.estado_flujo.nombre_estado if mision.estado_flujo else None,
            "estado_flujo_descripcion": mision.estado_flujo.descripcion if mision.estado_flujo else None,
            "tipo_mision": mision.tipo_mision.value if mision.tipo_mision else None,
            "numero_solicitud": mision.numero_solicitud,
            "beneficiario_personal_id": mision.beneficiario_personal_id,
            "monto_total_calculado": float(mision.monto_total_calculado) if mision.monto_total_calculado else None,
            "created_at": mision.created_at.isoformat() if mision.created_at else None,
            "available_states_cache": list(workflow_service._states_cache.keys()),
            "states_cache_count": len(workflow_service._states_cache)
        }
        
    except Exception as e:
        import traceback
        return {
            "error": str(e),
            "traceback": traceback.format_exc()
        }