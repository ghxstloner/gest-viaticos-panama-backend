# app/services/workflow_service.py

from typing import List, Dict, Any, Optional, Tuple, Union
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import text, and_, or_, bindparam
from decimal import Decimal
from datetime import datetime
from fastapi import HTTPException, status

from ..models.mission import (
    Mision, EstadoFlujo, TransicionFlujo, HistorialFlujo, 
    MisionPartidaPresupuestaria
)
from ..models.user import Usuario, Rol
from ..models.enums import TipoAccion, TipoMision, TipoFlujo
from ..schemas.workflow import *
from ..core.exceptions import (
    WorkflowException, BusinessException, ValidationException,
    PermissionException
)
from ..services.configuration import ConfigurationService

class WorkflowService:
    """
    Servicio central para gestionar el flujo de trabajo de misiones.
    Maneja todas las transiciones de estado dinámicamente usando permisos.
    """
    
    def __init__(self, db_financiero: Session, db_rrhh: Optional[Session] = None):
        self.db = db_financiero
        self.db_rrhh = db_rrhh
        self._states_cache: Dict[str, EstadoFlujo] = {}
        self._roles_cache: Dict[str, Rol] = {}
        self._config_service = ConfigurationService(db_financiero)
        self._load_caches()
    
    def _load_caches(self):
        """Cargar estados y roles en caché para mejor performance"""
        # Cargar estados
        estados = self.db.query(EstadoFlujo).all()
        self._states_cache = {estado.nombre_estado: estado for estado in estados}
        
        # Cargar roles
        roles = self.db.query(Rol).all()
        self._roles_cache = {rol.nombre_rol: rol for rol in roles}
    
    def _get_system_configuration(self, clave: str, default_value: Any = None) -> Any:
        """Obtiene una configuración del sistema por clave"""
        try:
            config = self._config_service.get_configuracion_sistema_by_clave(clave)
            if config:
                # Convertir el valor según el tipo de dato
                if config.tipo_dato == 'DECIMAL' or config.tipo_dato == 'FLOAT':
                    return Decimal(config.valor)
                elif config.tipo_dato == 'INTEGER':
                    return int(config.valor)
                elif config.tipo_dato == 'BOOLEAN':
                    return config.valor.lower() in ('true', '1', 'yes', 'on')
                else:
                    return config.valor
            return default_value
        except Exception:
            return default_value
    
    # ===============================================
    # MÉTODOS DE VERIFICACIÓN DE PERMISOS
    # ===============================================
    
    def _has_permission(self, user: Union[Usuario, dict], permission_code: str) -> bool:
        """
        Verifica si un usuario tiene un permiso específico - VERSIÓN CORREGIDA.
        """
        if isinstance(user, dict):
            # Para empleados, verificar permisos en el dict con estructura anidada
            permissions = user.get('permisos_usuario', {})
            
            # Mapeo de códigos de permisos a la estructura de empleados
            permission_mapping = {
                'MISSION_APPROVE': permissions.get('misiones', {}).get('aprobar', False),
                'MISSION_REJECT': permissions.get('misiones', {}).get('aprobar', False),  # Mismo permiso para aprobar/rechazar
                'MISSION_CREATE': permissions.get('misiones', {}).get('crear', False),
                'MISSION_EDIT': permissions.get('misiones', {}).get('editar', False),
                'MISSION_VIEW': permissions.get('misiones', {}).get('ver', False),
                'MISSION_PAYMMENT': permissions.get('misiones', {}).get('pagar', False),
                'MISSION_TESORERIA_APPROVE': permissions.get('misiones', {}).get('aprobar_tesoreria', False),
                'GESTION_SOLICITUDES_VIEW': permissions.get('gestion_solicitudes', {}).get('ver', False),
                'REPORT_EXPORT_VIATICOS': permissions.get('reportes', {}).get('exportar.viaticos', False),
                'REPORT_EXPORT_CAJA': permissions.get('reportes', {}).get('exportar.caja', False),
                'MISSION_DIR_FINANZAS_APPROVE': permissions.get('misiones', {}).get('aprobar_finanzas', False),
                'MISSION_CGR_APPROVE': permissions.get('fiscalizacion', {}).get('aprobar_cgr', False),
                'MISSION_VIATICOS_PAYMENT': permissions.get('misiones', {}).get('pagar.viaticos', False),

            }
            
            result = permission_mapping.get(permission_code, False)
            print(f"🔍 DEBUG WorkflowService._has_permission - {permission_code}: {result}")
            return result
        else:
            # Para usuarios financieros, usar el método del modelo
            try:
                # MÉTODO 1: Usar el método has_permission del modelo
                if hasattr(user, 'has_permission'):
                    result = user.has_permission(permission_code)
                    print(f"🔍 DEBUG WorkflowService._has_permission - {permission_code}: {result}")
                    return result
                
                # MÉTODO 2: Buscar en user.rol.permisos
                elif hasattr(user, 'rol') and hasattr(user.rol, 'permisos'):
                    permisos = user.rol.permisos
                    for permiso in permisos:
                        if hasattr(permiso, 'codigo') and permiso.codigo == permission_code:
                            print(f"🔍 DEBUG WorkflowService rol.permisos - {permission_code}: True")
                            return True
                    print(f"🔍 DEBUG WorkflowService rol.permisos - {permission_code}: False")
                    return False
                
                print(f"🔍 DEBUG WorkflowService - No se encontró método para verificar permisos")
                return False
                
            except Exception as e:
                print(f"🔍 ERROR WorkflowService verificando permisos: {e}")
                return False
    
    def _get_user_permissions(self, user: Union[Usuario, dict]) -> Dict[str, Any]:
        """
        Obtiene todos los permisos del usuario - VERSIÓN CORREGIDA.
        """
        if isinstance(user, dict):
            return user.get('permisos_usuario', {})
        else:
            try:
                # MÉTODO 1: Usar get_permissions del modelo
                if hasattr(user, 'get_permissions'):
                    permisos_list = user.get_permissions()
                    # Convertir lista a dict (asumiendo que todos son True)
                    return {permiso: True for permiso in permisos_list}
                
                # MÉTODO 2: Extraer códigos de user.rol.permisos
                elif hasattr(user, 'rol') and hasattr(user.rol, 'permisos'):
                    permisos_dict = {}
                    for permiso in user.rol.permisos:
                        if hasattr(permiso, 'codigo'):
                            permisos_dict[permiso.codigo] = True
                    return permisos_dict
                
                return {}
            except Exception as e:
                print(f"🔍 ERROR WorkflowService obteniendo permisos: {e}")
                return {}
    
    def _can_approve_missions(self, user: Union[Usuario, dict]) -> bool:
        """Verifica si puede aprobar misiones"""
        return self._has_permission(user, 'MISSION_APPROVE')

    def _can_reject_missions(self, user: Union[Usuario, dict]) -> bool:
        """Verifica si puede rechazar misiones"""
        return self._has_permission(user, 'MISSION_REJECT')

    def _can_pay_missions(self, user: Union[Usuario, dict]) -> bool:
        """Verifica si puede pagar misiones"""
        return self._has_permission(user, 'MISSION_PAYMMENT') or self._has_permission(user, 'MISSION_VIATICOS_PAYMENT')

    def _can_view_contabilidad(self, user: Union[Usuario, dict]) -> bool:
        """Verifica si puede ver contabilidad"""
        return self._has_permission(user, 'CONTABILIDAD_VIEW')

    def _can_view_presupuesto(self, user: Union[Usuario, dict]) -> bool:
        """Verifica si puede ver presupuesto"""
        return self._has_permission(user, 'MISSION_PRESUPUESTO_VIEW')

    def _can_view_fiscalizacion(self, user: Union[Usuario, dict]) -> bool:
        """Verifica si puede ver fiscalización"""
        return self._has_permission(user, 'FISCALIZACION_VIEW')

    def _can_view_pagos(self, user: Union[Usuario, dict]) -> bool:
        """Verifica si puede ver pagos"""
        return self._has_permission(user, 'PAGOS_VIEW')

    def _can_view_gestion_solicitudes(self, user: Union[Usuario, dict]) -> bool:
        """Verifica si puede ver gestión de solicitudes"""
        return self._has_permission(user, 'GESTION_SOLICITUDES_VIEW')

    def _can_return_missions(self, user: Union[Usuario, dict]) -> bool:
        """Verifica si el usuario puede devolver misiones para corrección"""
        # Verificar permiso específico para subsanar/devolver
        return self._has_permission(user, 'MISSION_SUBSANAR')

    def _is_jefe_inmediato(self, user: Union[Usuario, dict]) -> bool:
        """
        Verifica si el usuario es jefe inmediato.
        Un jefe puede aprobar si tiene MISSION_APPROVE y es empleado con is_department_head.
        """
        if isinstance(user, dict):
            has_approve_permission = self._has_permission(user, 'MISSION_APPROVE')
            is_department_head = user.get('is_department_head', False)
            return has_approve_permission and is_department_head
        else:
            # Para usuarios financieros, verificar solo el permiso
            return self._has_permission(user, 'MISSION_APPROVE')
        # ===============================================
    # MÉTODOS PRINCIPALES DEL WORKFLOW
    # ===============================================
    
    def get_available_actions(self, mission_id: int, user: Union[Usuario, dict]) -> AvailableActionsResponse:
        """
        Obtiene las acciones disponibles para un usuario en una misión específica.
        Soporta tanto usuarios financieros como empleados usando sistema de permisos.
        """
        mision = self._get_mission_with_validation(mission_id, user)
        estado_actual = mision.estado_flujo.nombre_estado
        
        acciones_disponibles = []
        
        # ===== LÓGICA BASADA EN PERMISOS Y ESTADO =====
        
        if estado_actual == 'BORRADOR' or estado_actual == 'DEVUELTO_CORRECCION':
            if self._has_permission(user, 'MISSION_CREATE') or self._has_permission(user, 'MISSION_EDIT'):
                acciones_disponibles.append({
                    "accion": "ENVIAR",
                    "estado_destino": "PENDIENTE_JEFE",
                    "descripcion": "Enviar solicitud para aprobación",
                    "requiere_datos_adicionales": False
                })
        
        elif estado_actual == 'PENDIENTE_JEFE':
            if self._is_jefe_inmediato(user):
                acciones_disponibles.extend([
                    {
                        "accion": "APROBAR",
                        "estado_destino": "PENDIENTE_REVISION_TESORERIA",
                        "descripcion": "Aprobar solicitud",
                        "requiere_datos_adicionales": False
                    },
                    {
                        "accion": "APROBAR_DIRECTO",
                        "estado_destino": "APROBADO_PARA_PAGO",
                        "descripcion": "Aprobar directamente para pago",
                        "requiere_datos_adicionales": True
                    },
                    {
                        "accion": "RECHAZAR",
                        "estado_destino": "RECHAZADO",
                        "descripcion": "Rechazar solicitud",
                        "requiere_datos_adicionales": True
                    },
                    {
                        "accion": "DEVOLVER",
                        "estado_destino": "DEVUELTO_CORRECCION",
                        "descripcion": "Devolver para corrección",
                        "requiere_datos_adicionales": True
                    }
                ])
        
        elif estado_actual == 'PENDIENTE_REVISION_TESORERIA':
            if self._can_view_pagos(user) and self._can_approve_missions(user):
                if mision.tipo_mision == TipoMision.CAJA_MENUDA:
                    # Caja menuda va directo a pago
                    acciones_disponibles.append({
                        "accion": "APROBAR",
                        "estado_destino": "APROBADO_PARA_PAGO",
                        "descripcion": "Aprobar para pago (Caja Menuda)",
                        "requiere_datos_adicionales": False
                    })
                else:
                    # Viáticos va a presupuesto
                    acciones_disponibles.append({
                        "accion": "APROBAR",
                        "estado_destino": "PENDIENTE_ASIGNACION_PRESUPUESTO",
                        "descripcion": "Aprobar y enviar a presupuesto",
                        "requiere_datos_adicionales": False
                    })
                
                acciones_disponibles.extend([
                    {
                        "accion": "RECHAZAR",
                        "estado_destino": "RECHAZADO",
                        "descripcion": "Rechazar solicitud",
                        "requiere_datos_adicionales": True
                    }
                ])
                   # Agregar acción de devolver si tiene permisos
                if self._can_return_missions(user):
                    acciones_disponibles.append({
                        "accion": "DEVOLVER",
                        "estado_destino": "DEVUELTO_CORRECCION_JEFE",
                        "descripcion": "Devolver para corrección al jefe",
                        "requiere_datos_adicionales": True
                    })
        
        # Estados de devolución específicos - permitir aprobar desde devoluciones
        elif estado_actual == 'DEVUELTO_CORRECCION_JEFE':
            if self._is_jefe_inmediato(user):
                acciones_disponibles.extend([
                    {
                        "accion": "APROBAR",
                        "estado_destino": "PENDIENTE_REVISION_TESORERIA",
                        "descripcion": "Aprobar solicitud corregida",
                        "requiere_datos_adicionales": False
                    },
                    {
                        "accion": "APROBAR_DIRECTO",
                        "estado_destino": "APROBADO_PARA_PAGO",
                        "descripcion": "Aprobar directamente para pago",
                        "requiere_datos_adicionales": True
                    },
                    {
                        "accion": "RECHAZAR",
                        "estado_destino": "RECHAZADO",
                        "descripcion": "Rechazar solicitud corregida",
                        "requiere_datos_adicionales": True
                    }
                ])
        
        elif estado_actual == 'DEVUELTO_CORRECCION_TESORERIA':
            if self._can_view_pagos(user) and self._can_approve_missions(user):
                if mision.tipo_mision == TipoMision.CAJA_MENUDA:
                    acciones_disponibles.append({
                        "accion": "APROBAR",
                        "estado_destino": "APROBADO_PARA_PAGO",
                        "descripcion": "Aprobar para pago (Caja Menuda) - Corregido",
                        "requiere_datos_adicionales": False
                    })
                else:
                    acciones_disponibles.append({
                        "accion": "APROBAR",
                        "estado_destino": "PENDIENTE_ASIGNACION_PRESUPUESTO",
                        "descripcion": "Aprobar y enviar a presupuesto - Corregido",
                        "requiere_datos_adicionales": False
                    })
                
                acciones_disponibles.extend([
                    {
                        "accion": "RECHAZAR",
                        "estado_destino": "RECHAZADO",
                        "descripcion": "Rechazar solicitud corregida",
                        "requiere_datos_adicionales": True
                    }
                ])
        
        elif estado_actual == 'DEVUELTO_CORRECCION_PRESUPUESTO':
            if self._can_view_presupuesto(user) and self._can_approve_missions(user):
                acciones_disponibles.extend([
                    {
                        "accion": "APROBAR",
                        "estado_destino": "PENDIENTE_CONTABILIDAD",
                        "descripcion": "Asignar presupuesto y aprobar - Corregido",
                        "requiere_datos_adicionales": True  # Requiere partidas
                    },
                    {
                        "accion": "RECHAZAR",
                        "estado_destino": "RECHAZADO",
                        "descripcion": "Rechazar por presupuesto - Corregido",
                        "requiere_datos_adicionales": True
                    }
                ])
        
        elif estado_actual == 'DEVUELTO_CORRECCION_CONTABILIDAD':
            if self._can_view_contabilidad(user) and self._can_approve_missions(user):
                acciones_disponibles.extend([
                    {
                        "accion": "APROBAR",
                        "estado_destino": "PENDIENTE_APROBACION_FINANZAS",
                        "descripcion": "Procesar contabilidad - Corregido",
                        "requiere_datos_adicionales": False
                    },
                    {
                        "accion": "RECHAZAR",
                        "estado_destino": "RECHAZADO",
                        "descripcion": "Rechazar por contabilidad - Corregido",
                        "requiere_datos_adicionales": True
                    }
                ])
        
        elif estado_actual == 'DEVUELTO_CORRECCION_FINANZAS':
            if self._can_approve_missions(user):  # Director de Finanzas
                acciones_disponibles.extend([
                    {
                        "accion": "APROBAR",
                        "estado_destino": "APROBADO_PARA_PAGO",  # O CGR si monto alto
                        "descripcion": "Aprobación final de finanzas - Corregido",
                        "requiere_datos_adicionales": True  # Puede requerir monto
                    },
                    {
                        "accion": "RECHAZAR",
                        "estado_destino": "RECHAZADO",
                        "descripcion": "Rechazar por finanzas - Corregido",
                        "requiere_datos_adicionales": True
                    }
                ])
        
        elif estado_actual == 'DEVUELTO_CORRECCION_CGR':
            if self._can_view_fiscalizacion(user) and self._can_approve_missions(user):
                acciones_disponibles.extend([
                    {
                        "accion": "APROBAR",
                        "estado_destino": "APROBADO_PARA_PAGO",
                        "descripcion": "Refrendar por CGR - Corregido",
                        "requiere_datos_adicionales": False
                    },
                    {
                        "accion": "RECHAZAR",
                        "estado_destino": "RECHAZADO",
                        "descripcion": "Rechazar refrendo CGR - Corregido",
                        "requiere_datos_adicionales": True
                    }
                ])
        
        elif estado_actual == 'PENDIENTE_ASIGNACION_PRESUPUESTO':
            if self._can_view_presupuesto(user) and self._can_approve_missions(user):
                acciones_disponibles.extend([
                    {
                        "accion": "APROBAR",
                        "estado_destino": "PENDIENTE_CONTABILIDAD",
                        "descripcion": "Asignar presupuesto y aprobar",
                        "requiere_datos_adicionales": True  # Requiere partidas
                    },
                    {
                        "accion": "RECHAZAR",
                        "estado_destino": "RECHAZADO",
                        "descripcion": "Rechazar por presupuesto",
                        "requiere_datos_adicionales": True
                    }
                ])
                
                # Agregar acción de devolver si tiene permisos
                if self._can_return_missions(user):
                    acciones_disponibles.append({
                        "accion": "DEVOLVER",
                        "estado_destino": "DEVUELTO_CORRECCION_TESORERIA",
                        "descripcion": "Devolver para corrección a tesorería",
                        "requiere_datos_adicionales": True
                    })
        
        elif estado_actual == 'PENDIENTE_CONTABILIDAD':
            if self._can_view_contabilidad(user) and self._can_approve_missions(user):
                acciones_disponibles.extend([
                    {
                        "accion": "APROBAR",
                        "estado_destino": "PENDIENTE_APROBACION_FINANZAS",
                        "descripcion": "Procesar contabilidad",
                        "requiere_datos_adicionales": False
                    },
                    {
                        "accion": "RECHAZAR",
                        "estado_destino": "RECHAZADO",
                        "descripcion": "Rechazar por contabilidad",
                        "requiere_datos_adicionales": True
                    }
                ])
                
                # Agregar acción de devolver si tiene permisos
                if self._can_return_missions(user):
                    acciones_disponibles.append({
                        "accion": "DEVOLVER",
                        "estado_destino": "DEVUELTO_CORRECCION_PRESUPUESTO",
                        "descripcion": "Devolver para corrección a presupuesto",
                        "requiere_datos_adicionales": True
                    })
        
        elif estado_actual == 'PENDIENTE_APROBACION_FINANZAS':
            if self._can_approve_missions(user):  # Director de Finanzas
                acciones_disponibles.extend([
                    {
                        "accion": "APROBAR",
                        "estado_destino": "APROBADO_PARA_PAGO",  # O CGR si monto alto
                        "descripcion": "Aprobación final de finanzas",
                        "requiere_datos_adicionales": True  # Puede requerir monto
                    },
                    {
                        "accion": "RECHAZAR",
                        "estado_destino": "RECHAZADO",
                        "descripcion": "Rechazar por finanzas",
                        "requiere_datos_adicionales": True
                    }
                ])
                
                # Agregar acción de devolver si tiene permisos
                if self._can_return_missions(user):
                    acciones_disponibles.append({
                        "accion": "DEVOLVER",
                        "estado_destino": "DEVUELTO_CORRECCION_CONTABILIDAD",
                        "descripcion": "Devolver para corrección a contabilidad",
                        "requiere_datos_adicionales": True
                    })
        
        elif estado_actual == 'PENDIENTE_REFRENDO_CGR':
            if self._can_view_fiscalizacion(user) and self._can_approve_missions(user):
                acciones_disponibles.extend([
                    {
                        "accion": "APROBAR",
                        "estado_destino": "APROBADO_PARA_PAGO",
                        "descripcion": "Refrendar por CGR",
                        "requiere_datos_adicionales": False
                    },
                    {
                        "accion": "RECHAZAR",
                        "estado_destino": "RECHAZADO",
                        "descripcion": "Rechazar refrendo CGR",
                        "requiere_datos_adicionales": True
                    }
                ])
                
                # Agregar acción de devolver si tiene permisos
                if self._can_return_missions(user):
                    acciones_disponibles.append({
                        "accion": "DEVOLVER",
                        "estado_destino": "DEVUELTO_CORRECCION_FINANZAS",
                        "descripcion": "Devolver para corrección a finanzas",
                        "requiere_datos_adicionales": True
                    })
        
        elif estado_actual == 'APROBADO_PARA_PAGO':
            if self._can_pay_missions(user):
                acciones_disponibles.append({
                    "accion": "PROCESAR_PAGO",
                    "estado_destino": "PAGADO",
                    "descripcion": "Procesar pago",
                    "requiere_datos_adicionales": True  # Requiere datos de pago
                })
                
                # Agregar acción de devolver si tiene permisos
                if self._can_return_missions(user):
                    # Determinar el estado de devolución según si requiere CGR
                    monto_refrendo = self._get_system_configuration('MONTO_REFRENDO_CGR', Decimal('5000.00'))
                    if isinstance(monto_refrendo, str):
                        monto_refrendo = Decimal(monto_refrendo)
                    
                    if mision.monto_aprobado and mision.monto_aprobado >= monto_refrendo:
                        estado_devolucion = "DEVUELTO_CORRECCION_CGR"
                        descripcion = "Devolver para corrección a CGR"
                    else:
                        estado_devolucion = "DEVUELTO_CORRECCION_FINANZAS"
                        descripcion = "Devolver para corrección a finanzas"
                    
                    acciones_disponibles.append({
                        "accion": "DEVOLVER",
                        "estado_destino": estado_devolucion,
                        "descripcion": descripcion,
                        "requiere_datos_adicionales": True
                    })
        
        elif estado_actual == 'PENDIENTE_FIRMA_ELECTRONICA':
            if self._can_pay_missions(user):
                acciones_disponibles.append({
                    "accion": "CONFIRMAR_PAGO",
                    "estado_destino": "PAGADO",
                    "descripcion": "Confirmar pago electrónico",
                    "requiere_datos_adicionales": False
                })
        
        return AvailableActionsResponse(
            mission_id=mission_id,
            estado_actual=estado_actual,
            acciones_disponibles=acciones_disponibles,
            puede_editar=self._can_edit_mission(mision, user),
            puede_eliminar=self._can_delete_mission(mision, user)
        )
    
    def execute_workflow_action(
        self, 
        mission_id: int, 
        action: str, 
        user: Union[Usuario, dict],
        request_data: WorkflowActionBase,
        client_ip: Optional[str] = None
    ) -> WorkflowTransitionResponse:
        """
        Ejecuta una acción específica del workflow.
        """
        mision = self._get_mission_with_validation(mission_id, user)
        
        # Validar que la acción es permitida
        transicion = self._validate_and_get_transition(mision, action, user)
        
        # Determinar el tipo específico de acción y procesarla
        estado_anterior = mision.estado_flujo.nombre_estado
        
        try:
            # Procesar la acción según el tipo y permisos
            resultado = self._process_specific_action(
                mision, transicion, request_data, user, client_ip
            )
            
            # Commit de la transacción
            self.db.commit()
            self.db.refresh(mision)
            print(f"DEBUG POST-COMMIT: id_estado_flujo={mision.id_estado_flujo} para mision {mision.id_mision}")
            
            return WorkflowTransitionResponse(
                success=True,
                message=resultado.get('message', 'Acción ejecutada exitosamente'),
                mission_id=mission_id,
                estado_anterior=estado_anterior,
                estado_nuevo=mision.estado_flujo.nombre_estado,
                accion_ejecutada=action,
                requiere_accion_adicional=resultado.get('requiere_accion_adicional', False),
                datos_transicion=resultado.get('datos_adicionales')
            )
            
        except Exception as e:
            self.db.rollback()
            raise WorkflowException(f"Error ejecutando acción {action}: {str(e)}")
    
    def _process_specific_action(
        self, 
        mision: Mision, 
        transicion: TransicionFlujo, 
        request_data: WorkflowActionBase,
        user: Union[Usuario, dict],
        client_ip: Optional[str]
    ) -> Dict[str, Any]:
        """
        Procesa acciones específicas según los permisos y tipo de acción.
        """
        # Normalizar el tipo de acción a string
        accion_str = transicion.tipo_accion.value if hasattr(transicion.tipo_accion, 'value') else str(transicion.tipo_accion)
        
        # Determinar el tipo de procesador basado en permisos y estado
        estado_actual = mision.estado_flujo.nombre_estado
        
        if accion_str == 'APROBAR':
            if estado_actual == 'PENDIENTE_JEFE':
                return self._process_jefe_approval(mision, transicion, request_data, user, client_ip)
            elif estado_actual == 'PENDIENTE_REVISION_TESORERIA':
                return self._process_tesoreria_approval(mision, transicion, request_data, user)
            elif estado_actual == 'PENDIENTE_ASIGNACION_PRESUPUESTO':
                return self._process_presupuesto_approval(mision, transicion, request_data, user)
            elif estado_actual == 'PENDIENTE_CONTABILIDAD':
                return self._process_contabilidad_approval(mision, transicion, request_data, user)
            elif estado_actual == 'PENDIENTE_APROBACION_FINANZAS':
                return self._process_finanzas_approval(mision, transicion, request_data, user)
            elif estado_actual == 'PENDIENTE_REFRENDO_CGR':
                return self._process_cgr_approval(mision, transicion, request_data, user)
            elif estado_actual == 'APROBADO_PARA_PAGO':
                return self._process_payment(mision, transicion, request_data, user)
            elif estado_actual == 'PENDIENTE_FIRMA_ELECTRONICA':
                return self._process_payment_confirmation(mision, transicion, request_data, user)
            # Estados de devolución específicos - permitir aprobar desde devoluciones
            elif estado_actual == 'DEVUELTO_CORRECCION_JEFE':
                return self._process_jefe_approval(mision, transicion, request_data, user, client_ip)
            elif estado_actual == 'DEVUELTO_CORRECCION_TESORERIA':
                return self._process_tesoreria_approval(mision, transicion, request_data, user)
            elif estado_actual == 'DEVUELTO_CORRECCION_PRESUPUESTO':
                return self._process_presupuesto_approval(mision, transicion, request_data, user)
            elif estado_actual == 'DEVUELTO_CORRECCION_CONTABILIDAD':
                return self._process_contabilidad_approval(mision, transicion, request_data, user)
            elif estado_actual == 'DEVUELTO_CORRECCION_FINANZAS':
                return self._process_finanzas_approval(mision, transicion, request_data, user)
            elif estado_actual == 'DEVUELTO_CORRECCION_CGR':
                return self._process_cgr_approval(mision, transicion, request_data, user)
        elif accion_str == 'RECHAZAR':
            return self._process_rejection(mision, transicion, request_data, user)
        elif accion_str == 'DEVOLVER':
            return self._process_return_for_correction(mision, transicion, request_data, user)
        
        # Cambiar estado de la misión
        mision.id_estado_flujo = transicion.id_estado_destino
        
        # Registrar en historial
        self._create_history_record(mision, transicion, request_data, user, client_ip)
        
        return {
            'message': f'Acción {accion_str} ejecutada exitosamente',
            'datos_adicionales': {}
        }
    
    def _process_jefe_approval(
        self, 
        mision: Mision, 
        transicion: TransicionFlujo, 
        request_data: WorkflowActionBase,
        user: Union[Usuario, dict],
        client_ip: Optional[str] = None
    ) -> Dict[str, Any]:
        """Procesa aprobación del jefe inmediato"""
        # Solo validar supervisión si es empleado (dict)
        if isinstance(user, dict):
            self._validate_employee_supervision(mision, user)
            user_name = user.get("apenom", "Jefe Inmediato")
            user_cedula = user.get('cedula')
        else:
            # Para usuarios financieros, no validar supervisión
            user_name = user.login_username if hasattr(user, 'login_username') else "Usuario Financiero"
            user_cedula = None
        
        mision.id_estado_flujo = transicion.id_estado_destino
        self._create_history_record(mision, transicion, request_data, user, client_ip)
        return {
            'message': f'Solicitud aprobada por {user_name}',
            'datos_adicionales': {
                'jefe_cedula': user_cedula,
                'jefe_nombre': user_name,
                'departamentos_gestionados': user.get('managed_departments', []) if isinstance(user, dict) else []
            }
        }
    
    def _process_jefe_rejection(
        self, 
        mision: Mision, 
        transicion: TransicionFlujo, 
        request_data: JefeRejectionRequest,
        user: Union[Usuario, dict]
    ) -> Dict[str, Any]:
        """Procesa rechazo del jefe inmediato"""
        # Solo validar supervisión si es empleado (dict)
        if isinstance(user, dict):
            self._validate_employee_supervision(mision, user)
            user_name = user.get("apenom", "Jefe Inmediato")
            user_cedula = user.get('cedula')
        else:
            # Para usuarios financieros, no validar supervisión
            user_name = user.login_username if hasattr(user, 'login_username') else "Usuario Financiero"
            user_cedula = None
        
        return {
            'message': f'Solicitud rechazada por {user_name}',
            'datos_adicionales': {
                'motivo_rechazo': request_data.motivo,
                'jefe_cedula': user_cedula
            }
        }
    
    def _process_tesoreria_approval(
        self, 
        mision: Mision, 
        transicion: TransicionFlujo, 
        request_data: WorkflowActionBase,
        user: Union[Usuario, dict]
    ) -> Dict[str, Any]:
        """Procesa aprobación de tesorería"""
        mensaje = 'Solicitud aprobada por Tesorería'
        
        # Para caja menuda, ir directo a aprobado para pago
        if mision.tipo_mision == TipoMision.CAJA_MENUDA:
            estado_pago = self._states_cache.get('APROBADO_PARA_PAGO')
            if estado_pago:
                transicion.id_estado_destino = estado_pago.id_estado_flujo
            mensaje += ' - Caja menuda aprobada para pago'
        else:
            # Para viáticos, seguir el flujo normal a presupuesto
            mensaje += ' - Enviada a asignación presupuestaria'
        
        mision.id_estado_flujo = transicion.id_estado_destino
        print(f"DEBUG TESORERIA: transicion.id_estado_destino={transicion.id_estado_destino}")
        
        # Crear historial de flujo
        self._create_history_record(mision, transicion, request_data, user, None)
        
        # Determinar nombre del usuario
        if isinstance(user, dict):
            user_name = user.get('apenom', 'Analista Tesorería')
        else:
            user_name = user.login_username if hasattr(user, 'login_username') else "Analista Tesorería"
        
        return {
            'message': mensaje,
            'datos_adicionales': {
                'analista_tesoreria': user_name,
                'tipo_flujo': 'SIMPLIFICADO' if mision.tipo_mision == TipoMision.CAJA_MENUDA else 'COMPLETO'
            }
        }
    
    def _process_payment_confirmation(
        self, 
        mision: Mision, 
        transicion: TransicionFlujo, 
        request_data: WorkflowActionBase,
        user: Union[Usuario, dict]
    ) -> Dict[str, Any]:
        """Procesa confirmación de pago (cuando está en PENDIENTE_FIRMA_ELECTRONICA)"""
        # Ir al estado final PAGADO
        estado_pagado = self._states_cache.get('PAGADO')
        if estado_pagado:
            transicion.id_estado_destino = estado_pagado.id_estado_flujo
        
        # Crear historial de flujo
        self._create_history_record(mision, transicion, request_data, user, None)
        
        # Determinar nombre del usuario
        if isinstance(user, dict):
            user_name = user.get('apenom', 'Analista Pago')
        else:
            user_name = user.login_username if hasattr(user, 'login_username') else "Analista Pago"
        
        return {
            'message': 'Pago confirmado exitosamente - Proceso completado',
            'datos_adicionales': {
                'confirmado_por': user_name,
                'fecha_confirmacion': datetime.now().isoformat()
            }
        }
    
    def _process_presupuesto_approval(
        self, 
        mision: Mision, 
        transicion: TransicionFlujo, 
        request_data: PresupuestoActionRequest,
        user: Union[Usuario, dict]
    ) -> Dict[str, Any]:
        """Procesa asignación de partidas presupuestarias"""
        mision.id_estado_flujo = transicion.id_estado_destino
        
        # Validar que las partidas existen en el sistema
        self._validate_budget_items(request_data.partidas)
        
        # Obtener el monto total original de la misión
        monto_total_original = mision.monto_total_calculado
        
        # Calcular el monto total de las partidas existentes antes de borrarlas
        partidas_existentes = self.db.query(MisionPartidaPresupuestaria).filter(
            MisionPartidaPresupuestaria.id_mision == mision.id_mision
        ).all()
        
        monto_partidas_existentes = sum(partida.monto for partida in partidas_existentes)
        
        # Limpiar partidas existentes
        self.db.query(MisionPartidaPresupuestaria).filter(
            MisionPartidaPresupuestaria.id_mision == mision.id_mision
        ).delete()
        
        # Crear nuevas partidas
        total_asignado = Decimal('0.00')
        for partida_data in request_data.partidas:
            partida = MisionPartidaPresupuestaria(
                id_mision=mision.id_mision,
                codigo_partida=partida_data.codigo_partida,
                monto=partida_data.monto
            )
            self.db.add(partida)
            total_asignado += partida_data.monto
        
        # IMPORTANTE: NO modificar el monto_total_calculado
        # Las partidas presupuestarias solo distribuyen el monto existente
        # El monto_total_calculado debe permanecer igual
        
        # Crear historial de flujo
        self._create_history_record(mision, transicion, request_data, user, None)
        
        # Determinar nombre del usuario
        if isinstance(user, dict):
            user_name = user.get('apenom', 'Analista Presupuesto')
        else:
            user_name = user.login_username if hasattr(user, 'login_username') else "Analista Presupuesto"
        
        return {
            'message': f'Partidas presupuestarias asignadas. Total distribuido: B/. {total_asignado} en {len(request_data.partidas)} partidas',
            'datos_adicionales': {
                'total_asignado': float(total_asignado),
                'monto_partidas_eliminadas': float(monto_partidas_existentes),
                'monto_total_mision': float(mision.monto_total_calculado),
                'cantidad_partidas': len(request_data.partidas),
                'analista_presupuesto': user_name
            }
        }
    
    def _process_contabilidad_approval(
        self, 
        mision: Mision, 
        transicion: TransicionFlujo, 
        request_data: ContabilidadApprovalRequest,
        user: Union[Usuario, dict]
    ) -> Dict[str, Any]:
        mision.id_estado_flujo = transicion.id_estado_destino
        datos_adicionales = {}
        
        # Determinar nombre del usuario
        if isinstance(user, dict):
            user_name = user.get('apenom', 'Analista Contabilidad')
        else:
            user_name = user.login_username if hasattr(user, 'login_username') else "Analista Contabilidad"
        
        datos_adicionales['analista_contabilidad'] = user_name
        
        if hasattr(request_data, 'numero_comprobante') and request_data.numero_comprobante:
            datos_adicionales['numero_comprobante'] = request_data.numero_comprobante
        
        # Crear historial de flujo
        self._create_history_record(mision, transicion, request_data, user, None)
        
        return {
            'message': 'Solicitud procesada por Contabilidad',
            'datos_adicionales': datos_adicionales
        }
    
    def _process_finanzas_approval(
        self, 
        mision: Mision, 
        transicion: TransicionFlujo, 
        request_data: FinanzasApprovalRequest,
        user: Union[Usuario, dict]
    ) -> Dict[str, Any]:
        """Procesa aprobación final de finanzas"""
        # Si se especifica monto aprobado, actualizarlo
        if hasattr(request_data, 'monto_aprobado') and request_data.monto_aprobado:
            mision.monto_aprobado = request_data.monto_aprobado
        else:
            # Si no se especifica, usar el monto calculado
            mision.monto_aprobado = mision.monto_total_calculado
        
        # Obtener configuración del monto para refrendo CGR
        monto_refrendo_cgr = self._get_system_configuration('MONTO_REFRENDO_CGR', Decimal('5000.00'))
        if isinstance(monto_refrendo_cgr, str):
            monto_refrendo_cgr = Decimal(monto_refrendo_cgr)
        
        # Determinar si requiere refrendo CGR basado en el monto
        requiere_cgr = mision.monto_aprobado >= monto_refrendo_cgr
        
        # Actualizar el campo en la misión
        mision.requiere_refrendo_cgr = requiere_cgr
        
        # Determinar próximo estado basado en si requiere CGR
        if requiere_cgr:
            # Si requiere CGR, cambiar a estado de refrendo
            estado_cgr = self._states_cache.get('PENDIENTE_REFRENDO_CGR')
            if estado_cgr:
                transicion.id_estado_destino = estado_cgr.id_estado_flujo
                mision.id_estado_flujo = estado_cgr.id_estado_flujo  # <-- Forzar cambio de estado
            mensaje = f"Solicitud aprobada por Director Finanzas - Enviada a refrendo CGR (monto: ${mision.monto_aprobado} >= ${monto_refrendo_cgr})"
        else:
            # Si no requiere CGR, ir directo a aprobado para pago
            estado_pago = self._states_cache.get('APROBADO_PARA_PAGO')
            if estado_pago:
                transicion.id_estado_destino = estado_pago.id_estado_flujo
                mision.id_estado_flujo = estado_pago.id_estado_flujo  # <-- Forzar cambio de estado
            mensaje = f"Solicitud aprobada por Director Finanzas - Aprobada para pago (monto: ${mision.monto_aprobado} < ${monto_refrendo_cgr})"
        
        # Crear historial de flujo
        self._create_history_record(mision, transicion, request_data, user, None)
        
        # Determinar nombre del usuario
        if isinstance(user, dict):
            user_name = user.get('apenom', 'Director Finanzas')
        else:
            user_name = user.login_username if hasattr(user, 'login_username') else "Director Finanzas"

        return {
            'message': mensaje,
            'requiere_accion_adicional': requiere_cgr,
            'datos_adicionales': {
                'director_finanzas': user_name,
                'monto_aprobado': float(mision.monto_aprobado),
                'monto_refrendo_cgr': float(monto_refrendo_cgr),
                'requiere_refrendo_cgr': requiere_cgr
            }
        }
    
    def _process_cgr_approval(
        self, 
        mision: Mision, 
        transicion: TransicionFlujo, 
        request_data: CGRApprovalRequest,
        user: Union[Usuario, dict]
    ) -> Dict[str, Any]:
        """Procesa refrendo de CGR"""
        # Forzar que CGR vaya directo a APROBADO_PARA_PAGO
        estado_pago = self._states_cache.get('APROBADO_PARA_PAGO')
        if estado_pago:
            transicion.id_estado_destino = estado_pago.id_estado_flujo
            mision.id_estado_flujo = estado_pago.id_estado_flujo  # <-- Forzar cambio de estado
        
        datos_adicionales = {}
        
        # Determinar nombre del usuario
        if isinstance(user, dict):
            user_name = user.get('apenom', 'Fiscalizador CGR')
        else:
            user_name = user.login_username if hasattr(user, 'login_username') else "Fiscalizador CGR"
        
        datos_adicionales['fiscalizador_cgr'] = user_name
        
        if hasattr(request_data, 'numero_refrendo') and request_data.numero_refrendo:
            datos_adicionales['numero_refrendo'] = request_data.numero_refrendo
        
        # Crear historial de flujo
        self._create_history_record(mision, transicion, request_data, user, None)
        
        return {
            'message': 'Refrendo CGR completado exitosamente - Solicitud aprobada para pago',
            'datos_adicionales': datos_adicionales
        }
    
    def _process_payment(
        self, 
        mision: Mision, 
        transicion: TransicionFlujo, 
        request_data: PaymentProcessRequest,
        user: Union[Usuario, dict]
    ) -> Dict[str, Any]:
        """Procesa el pago de la misión"""

        # Determinar el próximo estado basado en el método de pago
        estado_destino_final = None

        if request_data.metodo_pago == 'EFECTIVO':
            # Para efectivo, ir directo a PAGADO
            estado_pagado = self._states_cache.get('PAGADO')
            if estado_pagado:
                estado_destino_final = estado_pagado.id_estado_flujo
        else:
            # Para transferencias/ACH, ir a PENDIENTE_FIRMA_ELECTRONICA
            estado_firma = self._states_cache.get('PENDIENTE_FIRMA_ELECTRONICA')
            if estado_firma:
                estado_destino_final = estado_firma.id_estado_flujo

        # Si no se pudo determinar el estado, usar el de la transición original
        if estado_destino_final is None:
            estado_destino_final = transicion.id_estado_destino

        # Actualizar la misión directamente con el estado final
        estado_anterior_id = mision.id_estado_flujo
        mision.id_estado_flujo = estado_destino_final

        # Actualizar datos de pago en la misión
        mision.monto_aprobado = mision.monto_total_calculado
        fecha_pago = request_data.fecha_pago or datetime.now()

        # Crear historial manualmente con los estados correctos
        user_id = user.id_usuario if isinstance(user, Usuario) else 1

        historial = HistorialFlujo(
            id_mision=mision.id_mision,
            id_usuario_accion=user_id,
            id_estado_anterior=estado_anterior_id,
            id_estado_nuevo=estado_destino_final,
            tipo_accion="APROBAR",
            comentarios=request_data.comentarios,
            datos_adicionales={
                'procesado_por': user.login_username if isinstance(user, Usuario) else user.get('apenom', 'Analista Pago'),
                'metodo_pago': request_data.metodo_pago,
                'monto_pagado': float(mision.monto_aprobado),
                'numero_transaccion': getattr(request_data, 'numero_transaccion', None),
                'banco_origen': getattr(request_data, 'banco_origen', None),
                'fecha_pago': fecha_pago.isoformat() if fecha_pago else None
            },
            ip_usuario=None
        )

        self.db.add(historial)

        # Preparar datos adicionales para respuesta
        datos_adicionales = {
            'procesado_por': user.login_username if isinstance(user, Usuario) else user.get('apenom', 'Analista Pago'),
            'metodo_pago': request_data.metodo_pago,
            'monto_pagado': float(mision.monto_aprobado)
        }

        if hasattr(request_data, 'numero_transaccion') and request_data.numero_transaccion:
            datos_adicionales['numero_transaccion'] = request_data.numero_transaccion

        if hasattr(request_data, 'banco_origen') and request_data.banco_origen:
            datos_adicionales['banco_origen'] = request_data.banco_origen

        if fecha_pago:
            datos_adicionales['fecha_pago'] = fecha_pago.isoformat()

        # Mensaje según el método de pago
        mensaje = f'Pago procesado exitosamente vía {request_data.metodo_pago}'
        if request_data.metodo_pago == 'EFECTIVO':
            mensaje += ' - Pago completado'
        else:
            mensaje += ' - Pendiente firma electrónica'

        return {
            'message': mensaje,
            'datos_adicionales': datos_adicionales
        }
    
    def _process_return_for_correction(
        self, 
        mision: Mision, 
        transicion: TransicionFlujo, 
        request_data: WorkflowActionBase,
        user: Union[Usuario, dict]
    ) -> Dict[str, Any]:
        """Procesa devolución para corrección"""
        user_name = user.get('apenom') if isinstance(user, dict) else user.login_username
        
        datos_adicionales = {}
        # Solo tomar 'observaciones_correccion' y guardarlo como 'observacion'
        observacion = getattr(request_data, 'observaciones_correccion', None)
        if observacion:
            datos_adicionales['observacion'] = observacion

        # Crear historial de flujo
        self._create_history_record(mision, transicion, request_data, user, None)

        return {
            'message': f'Solicitud devuelta para corrección por {user_name}',
            'requiere_accion_adicional': True,
            'datos_adicionales': datos_adicionales
        }
    
    def _process_rejection(
        self, 
        mision: Mision, 
        transicion: TransicionFlujo, 
        request_data: WorkflowActionBase,
        user: Union[Usuario, dict]
    ) -> Dict[str, Any]:
        """Procesa rechazo definitivo"""
        user_name = user.get('apenom') if isinstance(user, dict) else user.login_username
        
        # Crear historial de flujo
        self._create_history_record(mision, transicion, request_data, user, None)

        return {
            'message': f'Solicitud rechazada definitivamente por {user_name}'
        }
    
    def get_budget_items_catalog(self) -> List[PartidaPresupuestariaResponse]:
        """
        Obtiene el catálogo de partidas presupuestarias desde aitsa_rrhh.cwprecue
        """
        if not self.db_rrhh:
            raise BusinessException("No hay conexión con la base de datos de RRHH")
        
        try:
            result = self.db_rrhh.execute(text("""
                SELECT CodCue, Denominacion
                FROM aitsa_rrhh.cwprecue 
                ORDER BY CodCue
            """))
            
            partidas = []
            for row in result.fetchall():
                partidas.append(PartidaPresupuestariaResponse(
                    codigo_partida=row.CodCue,
                    descripcion=row.Denominacion,
                    es_activa=True
                ))
            return partidas
            
        except Exception as e:
            raise BusinessException(f"Error obteniendo catálogo de partidas: {str(e)}")
    
    def get_workflow_states_by_role(self, user: Union[Usuario, dict]) -> List[WorkflowStateInfo]:
        """
        Obtiene los estados de workflow relevantes según los permisos del usuario
        """
        permissions = self._get_user_permissions(user)
        
        # Obtener estados donde el usuario puede tomar acciones basado en permisos
        estados_relevantes = []
        
        if self._is_jefe_inmediato(user):
            estados_relevantes.append('PENDIENTE_JEFE')
        
        if self._can_view_pagos(user) and self._can_approve_missions(user):
            estados_relevantes.extend(['PENDIENTE_REVISION_TESORERIA', 'PENDIENTE_FIRMA_ELECTRONICA'])
        
        if self._can_view_presupuesto(user) and self._can_approve_missions(user):
            estados_relevantes.append('PENDIENTE_ASIGNACION_PRESUPUESTO')
        
        if self._can_view_contabilidad(user) and self._can_approve_missions(user):
            estados_relevantes.append('PENDIENTE_CONTABILIDAD')
        
        if self._can_approve_missions(user):
            estados_relevantes.append('PENDIENTE_APROBACION_FINANZAS')
        
        if self._can_view_fiscalizacion(user) and self._can_approve_missions(user):
            estados_relevantes.append('PENDIENTE_REFRENDO_CGR')
        
        if self._can_pay_missions(user):
            estados_relevantes.append('APROBADO_PARA_PAGO')
        
        # Obtener objetos EstadoFlujo
        estados = self.db.query(EstadoFlujo).filter(
            EstadoFlujo.nombre_estado.in_(estados_relevantes)
        ).order_by(EstadoFlujo.orden_flujo).all()
        
        estados_info = []
        for estado in estados:
            # Determinar acciones posibles basado en permisos
            acciones = []
            if self._can_approve_missions(user):
                acciones.append("APROBAR")
            if self._can_reject_missions(user):
                acciones.append("RECHAZAR")
            if self._can_pay_missions(user) and estado.nombre_estado == 'APROBADO_PARA_PAGO':
                acciones.append("PROCESAR_PAGO")
            
            estados_info.append(WorkflowStateInfo(
                id_estado=estado.id_estado_flujo,
                nombre_estado=estado.nombre_estado,
                descripcion=estado.descripcion or "",
                es_estado_final=estado.es_estado_final,
                tipo_flujo=estado.tipo_flujo.value if hasattr(estado.tipo_flujo, 'value') else str(estado.tipo_flujo),
                orden_flujo=estado.orden_flujo,
                acciones_posibles=acciones
            ))
        
        return estados_info
    
    def get_pending_missions_by_permission(
        self, 
        user: Union[Usuario, dict], 
        filters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Obtiene las misiones pendientes según los permisos del usuario.
        """
        # Determinar qué estados puede gestionar basado en permisos
        target_states = []
        
        if self._is_jefe_inmediato(user):
            target_states.append('PENDIENTE_JEFE')
            # Jefes pueden ver sus propias devoluciones
            if self._has_permission(user, 'MISSION_APPROVE'):
                target_states.append('DEVUELTO_CORRECCION_JEFE')
        
        if self._can_view_pagos(user) and self._can_approve_missions(user):
            target_states.extend(['PENDIENTE_REVISION_TESORERIA', 'PENDIENTE_FIRMA_ELECTRONICA'])
        # Permitir a usuarios con permiso MISSION_TESORERIA_APPROVE ver PENDIENTE_REVISION_TESORERIA
        if self._has_permission(user, 'MISSION_TESORERIA_APPROVE') and 'PENDIENTE_REVISION_TESORERIA' not in target_states:
            target_states.append('PENDIENTE_REVISION_TESORERIA')
            # Tesorería puede ver devoluciones de tesorería
            target_states.append('DEVUELTO_CORRECCION_TESORERIA')
        
        # Solo permitir ver PENDIENTE_ASIGNACION_PRESUPUESTO si tiene el permiso MISSION_PRESUPUESTO_VIEW
        if self._has_permission(user, 'MISSION_PRESUPUESTO_VIEW'):  
            target_states.append('PENDIENTE_ASIGNACION_PRESUPUESTO')
            # Presupuesto puede ver devoluciones de presupuesto
            target_states.append('DEVUELTO_CORRECCION_PRESUPUESTO')
        
        if self._can_view_contabilidad(user):
            target_states.append('PENDIENTE_CONTABILIDAD')
            # Contabilidad puede ver devoluciones de contabilidad
            target_states.append('DEVUELTO_CORRECCION_CONTABILIDAD')
        
        # Agregar PENDIENTE_APROBACION_FINANZAS si tiene el permiso MISSION_DIR_FINANZAS_APPROVE
        if self._has_permission(user, 'MISSION_DIR_FINANZAS_APPROVE') and 'PENDIENTE_APROBACION_FINANZAS' not in target_states:
            target_states.append('PENDIENTE_APROBACION_FINANZAS')
            # Finanzas puede ver devoluciones de finanzas
            target_states.append('DEVUELTO_CORRECCION_FINANZAS')
        elif self._can_approve_missions(user):
            target_states.append('PENDIENTE_APROBACION_FINANZAS')
            # Si tiene permiso general de aprobación, puede ver devoluciones de finanzas
            target_states.append('DEVUELTO_CORRECCION_FINANZAS')

        if self._has_permission(user, 'MISSION_CGR_APPROVE') and 'PENDIENTE_REFRENDO_CGR' not in target_states:
            target_states.append('PENDIENTE_REFRENDO_CGR')
            # CGR puede ver devoluciones de CGR
            target_states.append('DEVUELTO_CORRECCION_CGR')
            
        
        if self._can_view_fiscalizacion(user) and self._can_approve_missions(user):
            target_states.append('PENDIENTE_REFRENDO_CGR')
            # Si tiene permisos de fiscalización, puede ver devoluciones de CGR
            target_states.append('DEVUELTO_CORRECCION_CGR')
        
        if self._can_pay_missions(user):
            target_states.append('APROBADO_PARA_PAGO')
            target_states.append('PAGADO')
        
        # Agregar estados de devolución específicos según permisos
        if self._has_permission(user, 'MISSION_APPROVE'):
            target_states.append('DEVUELTO_CORRECCION_JEFE')
        
        if self._has_permission(user, 'MISSION_TESORERIA_APPROVE'):
            target_states.append('DEVUELTO_CORRECCION_TESORERIA')
        
        if self._has_permission(user, 'MISSION_PRESUPUESTO_VIEW'):
            target_states.append('DEVUELTO_CORRECCION_PRESUPUESTO')
        
        if self._has_permission(user, 'CONTABILIDAD_VIEW'):
            target_states.append('DEVUELTO_CORRECCION_CONTABILIDAD')
        
        if self._has_permission(user, 'MISSION_DIR_FINANZAS_APPROVE'):
            target_states.append('DEVUELTO_CORRECCION_FINANZAS')
        
        if self._has_permission(user, 'MISSION_CGR_APPROVE'):
            target_states.append('DEVUELTO_CORRECCION_CGR')
        
        if not target_states:
            return {
                'items': [],
                'total': 0,
                'page': filters.get('page', 1),
                'size': filters.get('size', 20),
                'total_pages': 0,
                'stats': {'total_pendientes': 0, 'urgentes': 0, 'antiguos': 0}
            }
        
        # --- LÓGICA CORREGIDA PARA ESTADOS DE PAGO ---
        pago_filters = []
        if 'APROBADO_PARA_PAGO' in target_states:
            if self._has_permission(user, 'MISSION_VIATICOS_PAYMENT'):
                pago_filters.append(and_(EstadoFlujo.nombre_estado == 'APROBADO_PARA_PAGO', Mision.tipo_mision == TipoMision.VIATICOS))
            if self._has_permission(user, 'MISSION_PAYMMENT'):
                pago_filters.append(and_(EstadoFlujo.nombre_estado == 'APROBADO_PARA_PAGO', Mision.tipo_mision == TipoMision.CAJA_MENUDA))
        if 'PAGADO' in target_states:
            if self._has_permission(user, 'MISSION_VIATICOS_PAYMENT'):
                pago_filters.append(and_(EstadoFlujo.nombre_estado == 'PAGADO', Mision.tipo_mision == TipoMision.VIATICOS))
            if self._has_permission(user, 'MISSION_PAYMMENT'):
                pago_filters.append(and_(EstadoFlujo.nombre_estado == 'PAGADO', Mision.tipo_mision == TipoMision.CAJA_MENUDA))
        # Quitar los estados de pago de non_pago_states para que no se dupliquen
        non_pago_states = [s for s in target_states if s not in ['APROBADO_PARA_PAGO', 'PAGADO']]
        print(f"DEBUG pago_filters: {pago_filters}")
        print(f"DEBUG filters recibidos: {filters}")
        query = self.db.query(Mision).options(
            joinedload(Mision.estado_flujo)
        ).join(EstadoFlujo, Mision.id_estado_flujo == EstadoFlujo.id_estado_flujo)
        # Si hay estados normales y filtros de pago, unirlos con OR
        if non_pago_states and pago_filters:
            query = query.filter(or_(EstadoFlujo.nombre_estado.in_(non_pago_states), *pago_filters))
        elif pago_filters:
            query = query.filter(or_(*pago_filters))
        elif non_pago_states:
            query = query.filter(EstadoFlujo.nombre_estado.in_(non_pago_states))
        else:
            # Si no hay nada, devolver vacío
            query = query.filter(text('1=0'))
        
        # Aplicar filtros específicos por permisos
        if self._is_jefe_inmediato(user) and isinstance(user, dict):
            # Para jefes, solo mostrar solicitudes de sus subordinados
            query = self._apply_supervisor_filter(query, user)
        
        # Aplicar filtros generales
        if filters.get('search'):
            search_term = f"%{filters['search']}%"
            query = query.filter(
                or_(
                    Mision.objetivo_mision.ilike(search_term),
                    Mision.destino_mision.ilike(search_term),
                    Mision.numero_solicitud.ilike(search_term)
                )
            )
        
        if filters.get('estado'):
            query = query.filter(EstadoFlujo.nombre_estado == filters['estado'])
        
        if filters.get('tipo_mision'):
            # Convertir string a enum si es necesario
            tipo_enum = TipoMision(filters['tipo_mision']) if isinstance(filters['tipo_mision'], str) else filters['tipo_mision']
            query = query.filter(Mision.tipo_mision == tipo_enum)
        
        if filters.get('fecha_desde'):
            query = query.filter(Mision.created_at >= filters['fecha_desde'])
        
        if filters.get('fecha_hasta'):
            query = query.filter(Mision.created_at <= filters['fecha_hasta'])
        
        if filters.get('monto_min'):
            query = query.filter(Mision.monto_total_calculado >= filters['monto_min'])
        
        if filters.get('monto_max'):
            query = query.filter(Mision.monto_total_calculado <= filters['monto_max'])
        
        # Ordenar por fecha de creación (más recientes primero)
        query = query.order_by(Mision.created_at.desc())
        
        # Obtener total para paginación
        total_count = query.count()
        
        # Aplicar paginación
        page = filters.get('page', 1)
        size = filters.get('size', 20)
        offset = (page - 1) * size
        
        missions = query.offset(offset).limit(size).all()
        
        # Calcular estadísticas básicas simplificadas
        total_query = self.db.query(Mision).join(
            EstadoFlujo, Mision.id_estado_flujo == EstadoFlujo.id_estado_flujo
        )
        if non_pago_states and pago_filters:
            total_query = total_query.filter(or_(EstadoFlujo.nombre_estado.in_(non_pago_states), *pago_filters))
        elif pago_filters:
            total_query = total_query.filter(or_(*pago_filters))
        elif non_pago_states:
            total_query = total_query.filter(EstadoFlujo.nombre_estado.in_(non_pago_states))
        else:
            total_query = total_query.filter(text('1=0'))
        
        stats = {
            'total_pendientes': total_query.count(),
            'urgentes': 0,  # Simplificado por ahora
            'antiguos': 0   # Simplificado por ahora
        }
        
        return {
            'items': missions,
            'total': total_count,
            'page': page,
            'size': size,
            'total_pages': (total_count + size - 1) // size,
            'stats': stats
        }
    
    def _apply_supervisor_filter(self, query, jefe: dict):
        """
        Aplica filtro para que los jefes solo vean solicitudes de sus subordinados.
        """
        if not self.db_rrhh:
            raise BusinessException("No hay conexión con RRHH para validar supervisión")
        
        jefe_cedula = jefe.get('cedula')
        
        # Obtener los empleados bajo la supervisión del jefe
        result = self.db_rrhh.execute(text("""
            SELECT np.personal_id
            FROM aitsa_rrhh.nompersonal np
            JOIN aitsa_rrhh.departamento d ON np.IdDepartamento = d.IdDepartamento
            WHERE d.IdJefe = :jefe_cedula
        """), {"jefe_cedula": jefe_cedula})
        
        supervised_employees = [row.personal_id for row in result.fetchall()]
        
        if supervised_employees:
            query = query.filter(Mision.beneficiario_personal_id.in_(supervised_employees))
        else:
            # Si no tiene empleados bajo supervisión, no mostrar nada
            query = query.filter(text("1=0"))
        
        return query
    
    # ===============================================
    # MÉTODOS AUXILIARES Y VALIDACIONES
    # ===============================================
    
    def _get_mission_with_validation(self, mission_id: int, user: Union[Usuario, dict]) -> Mision:
        """Obtiene una misión con validaciones de acceso"""
        mision = self.db.query(Mision).options(
            joinedload(Mision.estado_flujo)
        ).filter(Mision.id_mision == mission_id).first()
        
        if not mision:
            raise HTTPException(status_code=404, detail="Misión no encontrada")
        
        # Validar acceso según permisos
        if not self._can_access_mission(mision, user):
            raise PermissionException("No tiene permisos para acceder a esta misión")
        
        return mision
    
    def _validate_and_get_transition(
        self, 
        mision: Mision, 
        action: str, 
        user: Union[Usuario, dict]
    ) -> TransicionFlujo:
        """Valida y obtiene la transición correspondiente basado en permisos"""
        # En lugar de usar transiciones de BD, validar basado en lógica de permisos
        estado_actual = mision.estado_flujo.nombre_estado
        
        # Crear transición ficticia para compatibilidad
        transicion = TransicionFlujo()
        transicion.id_estado_origen = mision.id_estado_flujo
        transicion.tipo_accion = action.upper()
        
        # Determinar estado destino basado en acción y estado actual
        estado_destino_id = self._determine_next_state(estado_actual, action, mision, user)
        transicion.id_estado_destino = estado_destino_id
        
        # Validar que el usuario tiene permisos para esta acción
        if not self._can_perform_action(estado_actual, action, user):
            raise WorkflowException(
                f"La acción '{action}' no está permitida en el estado actual '{estado_actual}' para sus permisos"
            )
        
        return transicion
    
    def _determine_next_state(self, estado_actual: str, action: str, mision: Mision, user: Union[Usuario, dict]) -> int:
        """Determina el próximo estado basado en la acción y estado actual"""
        action_upper = action.upper()
        
        if action_upper == 'ENVIAR':
            return self._states_cache['PENDIENTE_JEFE'].id_estado_flujo
        elif action_upper == 'APROBAR':
            if estado_actual == 'PENDIENTE_JEFE':
                print(f"DEBUG: tipo_mision={mision.tipo_mision} ({type(mision.tipo_mision)}), estado_actual={estado_actual}")
                if mision.tipo_mision == TipoMision.VIATICOS:
                    print("DEBUG: Transición a PENDIENTE_REVISION_TESORERIA")
                    return self._states_cache['PENDIENTE_REVISION_TESORERIA'].id_estado_flujo
                elif mision.tipo_mision == TipoMision.CAJA_MENUDA:
                    print("DEBUG: Transición a APROBADO_PARA_PAGO")
                    return self._states_cache['APROBADO_PARA_PAGO'].id_estado_flujo
                else:
                    print("DEBUG: Transición por defecto a PENDIENTE_REVISION_TESORERIA")
                    return self._states_cache['PENDIENTE_REVISION_TESORERIA'].id_estado_flujo
            elif estado_actual == 'PENDIENTE_REVISION_TESORERIA':
                if mision.tipo_mision == TipoMision.CAJA_MENUDA:
                    return self._states_cache['APROBADO_PARA_PAGO'].id_estado_flujo
                else:
                    return self._states_cache['PENDIENTE_ASIGNACION_PRESUPUESTO'].id_estado_flujo
            elif estado_actual == 'PENDIENTE_ASIGNACION_PRESUPUESTO':
                print("DEBUG: _states_cache keys:", list(self._states_cache.keys()))
                print("DEBUG: PENDIENTE_CONTABILIDAD in cache?", 'PENDIENTE_CONTABILIDAD' in self._states_cache)
                if 'PENDIENTE_CONTABILIDAD' in self._states_cache:
                    return self._states_cache['PENDIENTE_CONTABILIDAD'].id_estado_flujo
                else:
                    print("ERROR: Estado 'PENDIENTE_CONTABILIDAD' no encontrado en _states_cache")
                    return mision.id_estado_flujo
            elif estado_actual == 'PENDIENTE_CONTABILIDAD':
                return self._states_cache['PENDIENTE_APROBACION_FINANZAS'].id_estado_flujo
            elif estado_actual == 'PENDIENTE_APROBACION_FINANZAS':
                return self._states_cache['APROBADO_PARA_PAGO'].id_estado_flujo  # O CGR según monto
            elif estado_actual == 'PENDIENTE_REFRENDO_CGR':
                return self._states_cache['APROBADO_PARA_PAGO'].id_estado_flujo
            elif estado_actual == 'APROBADO_PARA_PAGO':
                return self._states_cache['PAGADO'].id_estado_flujo
            # Estados de devolución específicos - permitir aprobar desde devoluciones
            elif estado_actual == 'DEVUELTO_CORRECCION_JEFE':
                return self._states_cache['PENDIENTE_REVISION_TESORERIA'].id_estado_flujo
            elif estado_actual == 'DEVUELTO_CORRECCION_TESORERIA':
                if mision.tipo_mision == TipoMision.CAJA_MENUDA:
                    return self._states_cache['APROBADO_PARA_PAGO'].id_estado_flujo
                else:
                    return self._states_cache['PENDIENTE_ASIGNACION_PRESUPUESTO'].id_estado_flujo
            elif estado_actual == 'DEVUELTO_CORRECCION_PRESUPUESTO':
                return self._states_cache['PENDIENTE_CONTABILIDAD'].id_estado_flujo
            elif estado_actual == 'DEVUELTO_CORRECCION_CONTABILIDAD':
                return self._states_cache['PENDIENTE_APROBACION_FINANZAS'].id_estado_flujo
            elif estado_actual == 'DEVUELTO_CORRECCION_FINANZAS':
                return self._states_cache['APROBADO_PARA_PAGO'].id_estado_flujo
            elif estado_actual == 'DEVUELTO_CORRECCION_CGR':
                return self._states_cache['APROBADO_PARA_PAGO'].id_estado_flujo
        elif action_upper == 'RECHAZAR':
            return self._states_cache['RECHAZADO'].id_estado_flujo
        elif action_upper == 'DEVOLVER':
            # Nueva lógica de devolución específica según el estado actual
            return self._determine_return_state(estado_actual, mision)
        elif action_upper == 'APROBAR_DIRECTO':
            return self._states_cache['APROBADO_PARA_PAGO'].id_estado_flujo
        
        # Estado por defecto
        return mision.id_estado_flujo
    
    def _determine_return_state(self, estado_actual: str, mision: Mision) -> int:
        """
        Determina el estado de devolución específico según el estado actual.
        Implementa la lógica de devolución según el flujo de trabajo.
        """
        if estado_actual == 'PENDIENTE_JEFE':
            # Si está en PENDIENTE JEFE, devuelve a DEVUELTO_CORRECCION (estado general)
            return self._states_cache['DEVUELTO_CORRECCION'].id_estado_flujo
        
        elif estado_actual == 'PENDIENTE_REVISION_TESORERIA':
            # Si está en PENDIENTE TESORERIA, pasa a DEVUELTO_CORRECCION_JEFE
            if 'DEVUELTO_CORRECCION_JEFE' in self._states_cache:
                return self._states_cache['DEVUELTO_CORRECCION_JEFE'].id_estado_flujo
            else:
                # Fallback a DEVUELTO_CORRECCION si no existe DEVUELTO_CORRECCION_JEFE
                return self._states_cache['DEVUELTO_CORRECCION'].id_estado_flujo
        
        elif estado_actual == 'PENDIENTE_ASIGNACION_PRESUPUESTO':
            # Si está en PENDIENTE PRESUPUESTO, pasa a DEVUELTO_CORRECCION_TESORERIA
            if 'DEVUELTO_CORRECCION_TESORERIA' in self._states_cache:
                return self._states_cache['DEVUELTO_CORRECCION_TESORERIA'].id_estado_flujo
            else:
                # Fallback a DEVUELTO_CORRECCION si no existe DEVUELTO_CORRECCION_TESORERIA
                return self._states_cache['DEVUELTO_CORRECCION'].id_estado_flujo
        
        elif estado_actual == 'PENDIENTE_CONTABILIDAD':
            # Si está en PENDIENTE CONTABILIDAD, pasa a DEVUELTO_CORRECCION_PRESUPUESTO
            if 'DEVUELTO_CORRECCION_PRESUPUESTO' in self._states_cache:
                return self._states_cache['DEVUELTO_CORRECCION_PRESUPUESTO'].id_estado_flujo
            else:
                # Fallback a DEVUELTO_CORRECCION si no existe DEVUELTO_CORRECCION_PRESUPUESTO
                return self._states_cache['DEVUELTO_CORRECCION'].id_estado_flujo
        
        elif estado_actual == 'PENDIENTE_APROBACION_FINANZAS':
            # Si está en PENDIENTE FINANZAS, pasa a DEVUELTO_CORRECCION_CONTABILIDAD
            if 'DEVUELTO_CORRECCION_CONTABILIDAD' in self._states_cache:
                return self._states_cache['DEVUELTO_CORRECCION_CONTABILIDAD'].id_estado_flujo
            else:
                # Fallback a DEVUELTO_CORRECCION si no existe DEVUELTO_CORRECCION_CONTABILIDAD
                return self._states_cache['DEVUELTO_CORRECCION'].id_estado_flujo
        
        elif estado_actual == 'PENDIENTE_REFRENDO_CGR':
            # Si está en PENDIENTE CGR, pasa a DEVUELTO_CORRECCION_FINANZAS
            if 'DEVUELTO_CORRECCION_FINANZAS' in self._states_cache:
                return self._states_cache['DEVUELTO_CORRECCION_FINANZAS'].id_estado_flujo
            else:
                # Fallback a DEVUELTO_CORRECCION si no existe DEVUELTO_CORRECCION_FINANZAS
                return self._states_cache['DEVUELTO_CORRECCION'].id_estado_flujo
        
        elif estado_actual == 'APROBADO_PARA_PAGO':
            # Si está en APROBADO PAGO, determina si va a DEVUELTO_CORRECCION_CGR o DEVUELTO_CORRECCION_FINANZAS
            # según la misma validación que determina si va a PENDIENTE_CGR
            monto_refrendo = self._get_system_configuration('MONTO_REFRENDO_CGR', 5000.0)
            
            if mision.monto_aprobado and float(mision.monto_aprobado) > float(monto_refrendo):
                # Si el monto requiere refrendo CGR, devuelve a DEVUELTO_CORRECCION_CGR
                if 'DEVUELTO_CORRECCION_CGR' in self._states_cache:
                    return self._states_cache['DEVUELTO_CORRECCION_CGR'].id_estado_flujo
                else:
                    # Fallback a DEVUELTO_CORRECCION_FINANZAS si no existe DEVUELTO_CORRECCION_CGR
                    if 'DEVUELTO_CORRECCION_FINANZAS' in self._states_cache:
                        return self._states_cache['DEVUELTO_CORRECCION_FINANZAS'].id_estado_flujo
                    else:
                        return self._states_cache['DEVUELTO_CORRECCION'].id_estado_flujo
            else:
                # Si no requiere refrendo CGR, devuelve a DEVUELTO_CORRECCION_FINANZAS
                if 'DEVUELTO_CORRECCION_FINANZAS' in self._states_cache:
                    return self._states_cache['DEVUELTO_CORRECCION_FINANZAS'].id_estado_flujo
                else:
                    return self._states_cache['DEVUELTO_CORRECCION'].id_estado_flujo
        
        # Estados de devolución - cuando ya está devuelto, devolver al estado anterior
        elif estado_actual == 'DEVUELTO_CORRECCION_CGR':
            # Si está en DEVUELTO CGR, pasa a DEVUELTO_CORRECCION_FINANZAS
            if 'DEVUELTO_CORRECCION_FINANZAS' in self._states_cache:
                return self._states_cache['DEVUELTO_CORRECCION_FINANZAS'].id_estado_flujo
            else:
                return self._states_cache['DEVUELTO_CORRECCION'].id_estado_flujo
        
        elif estado_actual == 'DEVUELTO_CORRECCION_FINANZAS':
            # Si está en DEVUELTO FINANZAS, pasa a DEVUELTO_CORRECCION_CONTABILIDAD
            if 'DEVUELTO_CORRECCION_CONTABILIDAD' in self._states_cache:
                return self._states_cache['DEVUELTO_CORRECCION_CONTABILIDAD'].id_estado_flujo
            else:
                return self._states_cache['DEVUELTO_CORRECCION'].id_estado_flujo
        
        elif estado_actual == 'DEVUELTO_CORRECCION_CONTABILIDAD':
            # Si está en DEVUELTO CONTABILIDAD, pasa a DEVUELTO_CORRECCION_PRESUPUESTO
            if 'DEVUELTO_CORRECCION_PRESUPUESTO' in self._states_cache:
                return self._states_cache['DEVUELTO_CORRECCION_PRESUPUESTO'].id_estado_flujo
            else:
                return self._states_cache['DEVUELTO_CORRECCION'].id_estado_flujo
        
        elif estado_actual == 'DEVUELTO_CORRECCION_PRESUPUESTO':
            # Si está en DEVUELTO PRESUPUESTO, pasa a DEVUELTO_CORRECCION_TESORERIA
            if 'DEVUELTO_CORRECCION_TESORERIA' in self._states_cache:
                return self._states_cache['DEVUELTO_CORRECCION_TESORERIA'].id_estado_flujo
            else:
                return self._states_cache['DEVUELTO_CORRECCION'].id_estado_flujo
        
        elif estado_actual == 'DEVUELTO_CORRECCION_TESORERIA':
            # Si está en DEVUELTO TESORERIA, pasa a DEVUELTO_CORRECCION_JEFE
            if 'DEVUELTO_CORRECCION_JEFE' in self._states_cache:
                return self._states_cache['DEVUELTO_CORRECCION_JEFE'].id_estado_flujo
            else:
                return self._states_cache['DEVUELTO_CORRECCION'].id_estado_flujo
        
        elif estado_actual == 'DEVUELTO_CORRECCION_JEFE':
            # Si está en DEVUELTO JEFE, pasa a DEVUELTO_CORRECCION (estado general)
            return self._states_cache['DEVUELTO_CORRECCION'].id_estado_flujo
        
        # Para cualquier otro estado, usar DEVUELTO_CORRECCION como fallback
        return self._states_cache['DEVUELTO_CORRECCION'].id_estado_flujo
    
    def _can_perform_action(self, estado_actual: str, action: str, user: Union[Usuario, dict]) -> bool:
        """Verifica si el usuario puede realizar una acción específica en el estado actual"""
        action_upper = action.upper()
        
        # Estados editables (solo BORRADOR y DEVUELTO_CORRECCION general)
        estados_editables = ['BORRADOR', 'DEVUELTO_CORRECCION']
        
        if estado_actual in estados_editables:
            return action_upper == 'ENVIAR' and (
                self._has_permission(user, 'MISSION_CREATE') or 
                self._has_permission(user, 'MISSION_EDIT')
            )
        
        elif estado_actual == 'PENDIENTE_JEFE':
            is_jefe = self._is_jefe_inmediato(user)
            print(f"🔍 DEBUG _can_perform_action - PENDIENTE_JEFE: is_jefe={is_jefe}, action_upper={action_upper}")
            return is_jefe and action_upper in ['APROBAR', 'RECHAZAR', 'DEVOLVER', 'APROBAR_DIRECTO']
        
        elif estado_actual == 'DEVUELTO_CORRECCION_JEFE':
            is_jefe = self._is_jefe_inmediato(user)
            return is_jefe and action_upper in ['APROBAR', 'RECHAZAR', 'APROBAR_DIRECTO', 'DEVOLVER']
        
        elif estado_actual == 'DEVUELTO_CORRECCION_TESORERIA':
            return (
                self._has_permission(user, 'MISSION_TESORERIA_APPROVE')
                and action_upper in ['APROBAR', 'RECHAZAR', 'DEVOLVER']
            )
        
        elif estado_actual == 'DEVUELTO_CORRECCION_PRESUPUESTO':
            return (self._can_view_presupuesto(user) and action_upper in ['APROBAR', 'RECHAZAR', 'DEVOLVER'])
        
        elif estado_actual == 'DEVUELTO_CORRECCION_CONTABILIDAD':
            return (self._can_view_contabilidad(user) and action_upper in ['APROBAR', 'RECHAZAR', 'DEVOLVER'])
        
        elif estado_actual == 'DEVUELTO_CORRECCION_FINANZAS':
            return (
                (self._can_approve_missions(user) or self._has_permission(user, 'MISSION_DIR_FINANZAS_APPROVE'))
                and action_upper in ['APROBAR', 'RECHAZAR', 'DEVOLVER']
            )
        
        elif estado_actual == 'DEVUELTO_CORRECCION_CGR':
            return (
                (self._can_view_fiscalizacion(user) and self._can_approve_missions(user) or self._has_permission(user, 'MISSION_CGR_APPROVE'))
                and action_upper in ['APROBAR', 'RECHAZAR', 'DEVOLVER']
            )
        
        elif estado_actual == 'PENDIENTE_REVISION_TESORERIA':
            return (
                self._has_permission(user, 'MISSION_TESORERIA_APPROVE')
                and action_upper in ['APROBAR', 'RECHAZAR', 'DEVOLVER']
            )
        
        elif estado_actual == 'PENDIENTE_ASIGNACION_PRESUPUESTO':
            return (self._can_view_presupuesto(user) and action_upper in ['APROBAR', 'RECHAZAR', 'DEVOLVER'])
        
        elif estado_actual == 'PENDIENTE_CONTABILIDAD':
            return (self._can_view_contabilidad(user) and action_upper in ['APROBAR', 'RECHAZAR', 'DEVOLVER'])
        
        elif estado_actual == 'PENDIENTE_APROBACION_FINANZAS':
            return (
                (self._can_approve_missions(user) or self._has_permission(user, 'MISSION_DIR_FINANZAS_APPROVE'))
                and action_upper in ['APROBAR', 'RECHAZAR', 'DEVOLVER']
            )
        
        elif estado_actual == 'PENDIENTE_REFRENDO_CGR':
            return (
                (self._can_view_fiscalizacion(user) and self._can_approve_missions(user) or self._has_permission(user, 'MISSION_CGR_APPROVE'))
                and action_upper in ['APROBAR', 'RECHAZAR', 'DEVOLVER']
            )
        
        elif estado_actual == 'APROBADO_PARA_PAGO':
            return (self._can_pay_missions(user) and action_upper in ['APROBAR', 'PROCESAR_PAGO', 'DEVOLVER'])
        
        elif estado_actual == 'PENDIENTE_FIRMA_ELECTRONICA':
            return (self._can_pay_missions(user) and action_upper in ['APROBAR', 'CONFIRMAR_PAGO'])
        
        return False
    
    def _validate_employee_supervision(self, mision: Mision, jefe: dict):
        """Valida que el empleado beneficiario está bajo la supervisión del jefe"""
        if not self.db_rrhh:
            raise BusinessException("No hay conexión con RRHH para validar supervisión")
        
        # Obtener información del empleado beneficiario
        result = self.db_rrhh.execute(text("""
            SELECT np.IdDepartamento, d.IdJefe, np.apenom
            FROM aitsa_rrhh.nompersonal np
            JOIN aitsa_rrhh.departamento d ON np.IdDepartamento = d.IdDepartamento
            WHERE np.personal_id = :personal_id
        """), {"personal_id": mision.beneficiario_personal_id})
        
        employee_info = result.fetchone()
        if not employee_info:
            raise BusinessException("No se encontró información del empleado beneficiario")
        
        jefe_cedula = jefe.get('cedula')
        if employee_info.IdJefe != jefe_cedula:
            raise PermissionException(
                f"No tiene autorización para aprobar esta solicitud. "
                f"El jefe autorizado es: {employee_info.IdJefe}"
            )
    
    def _validate_budget_items(self, partidas: List[PartidaPresupuestariaBase]):
        """Valida que las partidas presupuestarias existan en el sistema"""
        if not self.db_rrhh:
            raise BusinessException("No hay conexión con RRHH para validar partidas")
        
        codigos = [p.codigo_partida for p in partidas]
        
        result = self.db_rrhh.execute(
            text("SELECT CodCue FROM aitsa_rrhh.cwprecue WHERE CodCue IN :codigos").bindparams(bindparam("codigos", expanding=True)),
            {"codigos": codigos}
        )
        
        codigos_validos = [row.CodCue for row in result.fetchall()]
        codigos_invalidos = [c for c in codigos if c not in codigos_validos]
        
        if codigos_invalidos:
            raise ValidationException(
                f"Las siguientes partidas presupuestarias no existen: {', '.join(codigos_invalidos)}"
            )
    
    def _can_access_mission(self, mision: Mision, user: Union[Usuario, dict]) -> bool:
        """Determina si un usuario puede acceder a una misión"""
        if isinstance(user, dict):  # Empleado
            # Los empleados solo pueden ver sus propias misiones
            # o las de sus subordinados si son jefes
            cedula = user.get('cedula')
            if self._is_jefe_inmediato(user):
                # Los jefes pueden ver solicitudes de sus subordinados
                return True  # Se validará en _apply_supervisor_filter
            else:
                # Verificar que sea su propia misión
                if self.db_rrhh:
                    result = self.db_rrhh.execute(text("""
                        SELECT personal_id FROM aitsa_rrhh.nompersonal 
                        WHERE cedula = :cedula
                    """), {"cedula": cedula})
                    employee = result.fetchone()
                    return employee and employee.personal_id == mision.beneficiario_personal_id
                return False
        else:  # Usuario financiero
            # Los usuarios financieros tienen acceso según sus permisos
            return self._has_permission(user, 'GESTION_SOLICITUDES_VIEW')
    
    def _can_edit_mission(self, mision: Mision, user: Union[Usuario, dict]) -> bool:
        """Determina si una misión puede ser editada"""
        # Solo se puede editar en estados iniciales
        estados_editables = ['BORRADOR', 'DEVUELTO_CORRECCION']
        can_edit_state = mision.estado_flujo.nombre_estado in estados_editables
        has_permission = self._has_permission(user, 'MISSION_EDIT')
        return can_edit_state and has_permission
    
    def _can_delete_mission(self, mision: Mision, user: Union[Usuario, dict]) -> bool:
        """Determina si una misión puede ser eliminada"""
        if isinstance(user, dict):
            return False  # Los empleados no pueden eliminar
        
        can_delete_state = mision.estado_flujo.nombre_estado == 'BORRADOR'
        has_permission = self._has_permission(user, 'MISSION_DELETE')
        is_owner = mision.id_usuario_prepara == user.id_usuario
        
        return can_delete_state and has_permission and is_owner
    
    def _create_history_record(
        self, 
        mision: Mision, 
        transicion: TransicionFlujo, 
        request_data: WorkflowActionBase,
        user: Union[Usuario, dict],
        client_ip: Optional[str]
    ):
        """Crea un registro en el historial de flujo"""
        user_id = user.id_usuario if isinstance(user, Usuario) else 1  # Usuario sistema para empleados
        
        # Determinar qué usar como observación
        observacion = None
        if hasattr(request_data, 'observacion') and request_data.observacion:
            observacion = request_data.observacion
        elif hasattr(request_data, 'comentarios') and request_data.comentarios:
            observacion = request_data.comentarios
        elif hasattr(request_data, 'motivo') and request_data.motivo:
            observacion = request_data.motivo
        
        historial = HistorialFlujo(
            id_mision=mision.id_mision,
            id_usuario_accion=user_id,
            id_estado_anterior=transicion.id_estado_origen,
            id_estado_nuevo=transicion.id_estado_destino,
            tipo_accion=transicion.tipo_accion,
            comentarios=request_data.comentarios,
            observacion=observacion,
            datos_adicionales=request_data.datos_adicionales,
            ip_usuario=client_ip
        )
        
        self.db.add(historial)
    
    def _process_jefe_return_for_correction(
        self, 
        mision: Mision, 
        request_data,
        user: dict
    ) -> Dict[str, Any]:
        """Procesa devolución para corrección por parte del jefe"""
        self._validate_employee_supervision(mision, user)
        
        motivo = getattr(request_data, 'motivo', 'Sin motivo especificado')
        observaciones = getattr(request_data, 'observaciones_correccion', None)
        
        return {
            'message': f'Solicitud devuelta para corrección por {user.get("apenom", "Jefe Inmediato")}',
            'requiere_accion_adicional': True,
            'datos_adicionales': {
                'motivo': motivo,
                'observaciones_correccion': observaciones,
                'jefe_cedula': user.get('cedula'),
                'jefe_nombre': user.get('apenom'),
                'accion_requerida': 'CORREGIR_SOLICITUD'
            }
        }
    
    def _process_jefe_direct_approval(
        self, 
        mision: Mision, 
        request_data,
        user: dict
    ) -> Dict[str, Any]:
        """Procesa aprobación directa para pago por parte del jefe"""
        self._validate_employee_supervision(mision, user)
        
        monto_aprobado = getattr(request_data, 'monto_aprobado', None)
        if monto_aprobado:
            mision.monto_aprobado = monto_aprobado
        else:
            mision.monto_aprobado = mision.monto_total_calculado
        
        justificacion = getattr(request_data, 'justificacion', 'Aprobación directa por jefe inmediato')
        es_emergencia = getattr(request_data, 'es_emergencia', False)
        
        return {
            'message': f'Solicitud aprobada directamente para pago por {user.get("apenom", "Jefe Inmediato")}',
            'datos_adicionales': {
                'justificacion': justificacion,
                'es_emergencia': es_emergencia,
                'monto_aprobado': float(mision.monto_aprobado),
                'jefe_cedula': user.get('cedula'),
                'jefe_nombre': user.get('apenom'),
                'flujo_simplificado': True
            }
        }
    
    def _create_manual_history_record(
        self, 
        mision: Mision, 
        estado_anterior_id: int,
        estado_nuevo_id: int,
        accion: str,
        request_data,
        user: Union[Usuario, dict],
        client_ip: Optional[str]
    ):
        """Crea un registro manual en el historial"""
        user_id = user.id_usuario if isinstance(user, Usuario) else 1
        
        # Determinar qué usar como observación
        observacion = None
        if hasattr(request_data, 'observacion') and request_data.observacion:
            observacion = request_data.observacion
        elif hasattr(request_data, 'comentarios') and request_data.comentarios:
            observacion = request_data.comentarios
        elif hasattr(request_data, 'motivo') and request_data.motivo:
            observacion = request_data.motivo
        
        historial = HistorialFlujo(
            id_mision=mision.id_mision,
            id_usuario_accion=user_id,
            id_estado_anterior=estado_anterior_id,
            id_estado_nuevo=estado_nuevo_id,
            tipo_accion=accion,
            comentarios=getattr(request_data, 'comentarios', None),
            observacion=observacion,
            datos_adicionales=getattr(request_data, 'datos_adicionales', None),
            ip_usuario=client_ip
        )
        
        self.db.add(historial)
    
    def get_employee_missions(
        self, 
        employee: dict, 
        filters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Obtiene las misiones del empleado (solicitudes propias).
        """
        if not self.db_rrhh:
            raise BusinessException("No hay conexión con RRHH para obtener datos del empleado")
        
        # Obtener personal_id del empleado
        cedula = employee.get('cedula')
        result = self.db_rrhh.execute(text("""
            SELECT personal_id FROM aitsa_rrhh.nompersonal 
            WHERE cedula = :cedula
        """), {"cedula": cedula})
        
        employee_info = result.fetchone()
        if not employee_info:
            raise BusinessException("No se encontró información del empleado")
        
        personal_id = employee_info.personal_id
        
        # Construir query para las misiones del empleado
        query = self.db.query(Mision).options(
            joinedload(Mision.estado_flujo)
        ).filter(Mision.beneficiario_personal_id == personal_id)
        
        # Aplicar filtros
        if filters.get('search'):
            search_term = f"%{filters['search']}%"
            query = query.filter(
                or_(
                    Mision.objetivo_mision.ilike(search_term),
                    Mision.destino_mision.ilike(search_term),
                    Mision.numero_solicitud.ilike(search_term)
                )
            )
        
        if filters.get('estado'):
            query = query.join(EstadoFlujo).filter(
                EstadoFlujo.nombre_estado == filters['estado']
            )
        
        if filters.get('tipo_mision'):
            tipo_enum = TipoMision(filters['tipo_mision']) if isinstance(filters['tipo_mision'], str) else filters['tipo_mision']
            query = query.filter(Mision.tipo_mision == tipo_enum)
        
        # Ordenar por fecha de creación (más recientes primero)
        query = query.order_by(Mision.created_at.desc())
        
        # Obtener total para paginación
        total_count = query.count()
        
        # Aplicar paginación
        page = filters.get('page', 1)
        size = filters.get('size', 20)
        offset = (page - 1) * size
        
        missions = query.offset(offset).limit(size).all()
        
        return {
            'items': missions,
            'total': total_count,
            'page': page,
            'size': size,
            'total_pages': (total_count + size - 1) // size,
            'employee_info': {
                'cedula': cedula,
                'nombre': employee.get('apenom'),
                'personal_id': personal_id
            }
        }