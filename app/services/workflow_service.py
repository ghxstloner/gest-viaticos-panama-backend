# app/services/workflow_service.py

from typing import List, Dict, Any, Optional, Tuple, Union
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import text, and_, or_
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
    Maneja todas las transiciones de estado dinámicamente.
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
    
    def get_available_actions(self, mission_id: int, user: Union[Usuario, dict]) -> AvailableActionsResponse:
        """
        Obtiene las acciones disponibles para un usuario en una misión específica.
        Soporta tanto usuarios financieros como empleados.
        """
        mision = self._get_mission_with_validation(mission_id, user)
        
        # Determinar el rol del usuario
        if isinstance(user, dict):  # Es empleado
            user_role_id = user.get('id_rol', 1)
            user_role_name = user.get('role_name', 'Solicitante')
        else:  # Es usuario financiero
            user_role_id = user.id_rol
            user_role_name = user.rol.nombre_rol
        
        # Obtener transiciones disponibles
        transiciones = self.db.query(TransicionFlujo).filter(
            and_(
                TransicionFlujo.id_estado_origen == mision.id_estado_flujo,
                TransicionFlujo.id_rol_autorizado == user_role_id,
                TransicionFlujo.es_activa == True
            )
        ).all()
        
        acciones_disponibles = []
        for trans in transiciones:
            accion_info = {
                "accion": trans.tipo_accion.value,
                "estado_destino": trans.estado_destino.nombre_estado,
                "descripcion": trans.estado_destino.descripcion,
                "requiere_datos_adicionales": self._requires_additional_data(trans.tipo_accion, user_role_name)
            }
            acciones_disponibles.append(accion_info)
        
        return AvailableActionsResponse(
            mission_id=mission_id,
            estado_actual=mision.estado_flujo.nombre_estado,
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
            # Procesar la acción según el tipo y rol
            resultado = self._process_specific_action(
                mision, transicion, request_data, user, client_ip
            )
            
            # Commit de la transacción
            self.db.commit()
            
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
        Procesa acciones específicas según el rol y tipo de acción.
        """
        accion = transicion.tipo_accion
        rol_nombre = user.get('role_name') if isinstance(user, dict) else user.rol.nombre_rol
        
        # Mapeo de procesadores específicos
        processors = {
            ('APROBAR', 'Jefe Inmediato'): self._process_jefe_approval,
            ('RECHAZAR', 'Jefe Inmediato'): self._process_jefe_rejection,
            ('APROBAR', 'Analista Tesorería'): self._process_tesoreria_or_payment,
            ('APROBAR', 'Analista Presupuesto'): self._process_presupuesto_approval,
            ('APROBAR', 'Analista Contabilidad'): self._process_contabilidad_approval,
            ('APROBAR', 'Director Finanzas'): self._process_finanzas_approval,
            ('APROBAR', 'Fiscalizador CGR'): self._process_cgr_approval,
            ('APROBAR', 'Custodio Caja Menuda'): self._process_payment,
            ('DEVOLVER', '*'): self._process_return_for_correction,
            ('RECHAZAR', '*'): self._process_rejection,
        }
        
        # Buscar procesador específico
        processor_key = (accion.value, rol_nombre)
        processor = processors.get(processor_key)
        
        # Si no hay procesador específico, buscar genérico
        if not processor:
            processor = processors.get((accion.value, '*'))
        
        if not processor:
            raise WorkflowException(f"No hay procesador definido para {accion.value} - {rol_nombre}")
        
        # Ejecutar el procesador específico
        resultado = processor(mision, transicion, request_data, user)
        
        # Cambiar estado de la misión
        mision.id_estado_flujo = transicion.id_estado_destino
        
        # Registrar en historial
        self._create_history_record(mision, transicion, request_data, user, client_ip)
        
        return resultado
    
    def _process_jefe_approval(
        self, 
        mision: Mision, 
        transicion: TransicionFlujo, 
        request_data: WorkflowActionBase,
        user: dict
    ) -> Dict[str, Any]:
        """Procesa aprobación del jefe inmediato"""
        # Validar que el empleado está bajo su supervisión
        self._validate_employee_supervision(mision, user)
        
        return {
            'message': f'Solicitud aprobada por {user.get("apenom", "Jefe Inmediato")}',
            'datos_adicionales': {
                'jefe_cedula': user.get('cedula'),
                'jefe_nombre': user.get('apenom'),
                'departamentos_gestionados': user.get('managed_departments', [])
            }
        }
    
    def _process_jefe_rejection(
        self, 
        mision: Mision, 
        transicion: TransicionFlujo, 
        request_data: JefeRejectionRequest,
        user: dict
    ) -> Dict[str, Any]:
        """Procesa rechazo del jefe inmediato"""
        self._validate_employee_supervision(mision, user)
        
        return {
            'message': f'Solicitud rechazada por {user.get("apenom", "Jefe Inmediato")}',
            'datos_adicionales': {
                'motivo_rechazo': request_data.motivo,
                'jefe_cedula': user.get('cedula')
            }
        }
    
    def _process_tesoreria_or_payment(
        self, 
        mision: Mision, 
        transicion: TransicionFlujo, 
        request_data: WorkflowActionBase,
        user: Usuario
    ) -> Dict[str, Any]:
        """Procesa aprobación de tesorería o procesamiento/confirmación de pago"""
        estado_actual = mision.estado_flujo.nombre_estado
        
        if estado_actual == 'PENDIENTE_REVISION_TESORERIA':
            # Es una aprobación normal de tesorería
            return self._process_tesoreria_approval(mision, transicion, request_data, user)
        elif estado_actual == 'APROBADO_PARA_PAGO':
            # Es un procesamiento de pago
            if isinstance(request_data, PaymentProcessRequest):
                return self._process_payment(mision, transicion, request_data, user)
            else:
                raise WorkflowException("Para procesar pago se requieren datos de PaymentProcessRequest")
        elif estado_actual == 'PENDIENTE_FIRMA_ELECTRONICA':
            # Es una confirmación de pago
            return self._process_payment_confirmation(mision, transicion, request_data, user)
        else:
            raise WorkflowException(f"Estado {estado_actual} no válido para Analista Tesorería")
    
    def _process_tesoreria_approval(
        self, 
        mision: Mision, 
        transicion: TransicionFlujo, 
        request_data: WorkflowActionBase,
        user: Usuario
    ) -> Dict[str, Any]:
        """Procesa aprobación de tesorería"""
        mensaje = 'Solicitud aprobada por Tesorería'
        
        # Para caja menuda, ir directo a aprobado para pago
        if mision.tipo_mision == 'CAJA_MENUDA':
            estado_pago = self._states_cache.get('APROBADO_PARA_PAGO')
            if estado_pago:
                transicion.id_estado_destino = estado_pago.id_estado_flujo
            mensaje += ' - Caja menuda aprobada para pago'
        else:
            # Para viáticos, seguir el flujo normal a presupuesto
            mensaje += ' - Enviada a asignación presupuestaria'
        
        return {
            'message': mensaje,
            'datos_adicionales': {
                'analista_tesoreria': user.login_username,
                'tipo_flujo': 'SIMPLIFICADO' if mision.tipo_mision == 'CAJA_MENUDA' else 'COMPLETO'
            }
        }
    
    def _process_payment_confirmation(
        self, 
        mision: Mision, 
        transicion: TransicionFlujo, 
        request_data: WorkflowActionBase,
        user: Usuario
    ) -> Dict[str, Any]:
        """Procesa confirmación de pago (cuando está en PENDIENTE_FIRMA_ELECTRONICA)"""
        # Ir al estado final PAGADO
        estado_pagado = self._states_cache.get('PAGADO')
        if estado_pagado:
            transicion.id_estado_destino = estado_pagado.id_estado_flujo
        
        return {
            'message': 'Pago confirmado exitosamente - Proceso completado',
            'datos_adicionales': {
                'confirmado_por': user.login_username,
                'fecha_confirmacion': datetime.now().isoformat()
            }
        }
    
    def _process_presupuesto_approval(
        self, 
        mision: Mision, 
        transicion: TransicionFlujo, 
        request_data: PresupuestoActionRequest,
        user: Usuario
    ) -> Dict[str, Any]:
        """Procesa asignación de partidas presupuestarias"""
        # Validar que las partidas existen en el sistema
        self._validate_budget_items(request_data.partidas)
        
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
                monto=partida_data.monto,
                descripcion=partida_data.descripcion
            )
            self.db.add(partida)
            total_asignado += partida_data.monto
        
        return {
            'message': f'Partidas presupuestarias asignadas. Total: B/. {total_asignado}',
            'datos_adicionales': {
                'total_asignado': float(total_asignado),
                'cantidad_partidas': len(request_data.partidas),
                'analista_presupuesto': user.login_username
            }
        }
    
    def _process_contabilidad_approval(
        self, 
        mision: Mision, 
        transicion: TransicionFlujo, 
        request_data: ContabilidadApprovalRequest,
        user: Usuario
    ) -> Dict[str, Any]:
        """Procesa aprobación de contabilidad"""
        datos_adicionales = {
            'analista_contabilidad': user.login_username
        }
        
        if hasattr(request_data, 'numero_comprobante') and request_data.numero_comprobante:
            datos_adicionales['numero_comprobante'] = request_data.numero_comprobante
        
        return {
            'message': 'Solicitud procesada por Contabilidad',
            'datos_adicionales': datos_adicionales
        }
    
    def _process_finanzas_approval(
        self, 
        mision: Mision, 
        transicion: TransicionFlujo, 
        request_data: FinanzasApprovalRequest,
        user: Usuario
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
            mensaje = f"Solicitud aprobada por Director Finanzas - Enviada a refrendo CGR (monto: ${mision.monto_aprobado} >= ${monto_refrendo_cgr})"
        else:
            # Si no requiere CGR, ir directo a aprobado para pago
            estado_pago = self._states_cache.get('APROBADO_PARA_PAGO')
            if estado_pago:
                transicion.id_estado_destino = estado_pago.id_estado_flujo
            mensaje = f"Solicitud aprobada por Director Finanzas - Aprobada para pago (monto: ${mision.monto_aprobado} < ${monto_refrendo_cgr})"
        
        return {
            'message': mensaje,
            'requiere_accion_adicional': requiere_cgr,
            'datos_adicionales': {
                'director_finanzas': user.login_username,
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
        user: Usuario
    ) -> Dict[str, Any]:
        """Procesa refrendo de CGR"""
        # Forzar que CGR vaya directo a APROBADO_PARA_PAGO
        estado_pago = self._states_cache.get('APROBADO_PARA_PAGO')
        if estado_pago:
            transicion.id_estado_destino = estado_pago.id_estado_flujo
        
        datos_adicionales = {
            'fiscalizador_cgr': user.login_username
        }
        
        if hasattr(request_data, 'numero_refrendo') and request_data.numero_refrendo:
            datos_adicionales['numero_refrendo'] = request_data.numero_refrendo
        
        return {
            'message': 'Refrendo CGR completado exitosamente - Solicitud aprobada para pago',
            'datos_adicionales': datos_adicionales
        }
    
    def _process_payment(
        self, 
        mision: Mision, 
        transicion: TransicionFlujo, 
        request_data: PaymentProcessRequest,
        user: Usuario
    ) -> Dict[str, Any]:
        """Procesa el pago de la misión"""
        # Determinar el próximo estado basado en el método de pago
        if request_data.metodo_pago == 'EFECTIVO':
            # Para efectivo, ir directo a PAGADO
            estado_pagado = self._states_cache.get('PAGADO')
            if estado_pagado:
                transicion.id_estado_destino = estado_pagado.id_estado_flujo
        else:
            # Para transferencias/ACH, ir a PENDIENTE_FIRMA_ELECTRONICA
            estado_firma = self._states_cache.get('PENDIENTE_FIRMA_ELECTRONICA')
            if estado_firma:
                transicion.id_estado_destino = estado_firma.id_estado_flujo
        
        # Actualizar monto pagado
        mision.monto_pagado = mision.monto_aprobado
        mision.fecha_pago = request_data.fecha_pago or datetime.now()
        
        datos_adicionales = {
            'procesado_por': user.login_username,
            'metodo_pago': request_data.metodo_pago,
            'monto_pagado': float(mision.monto_pagado)
        }
        
        if hasattr(request_data, 'numero_transaccion') and request_data.numero_transaccion:
            datos_adicionales['numero_transaccion'] = request_data.numero_transaccion
        
        if hasattr(request_data, 'banco_origen') and request_data.banco_origen:
            datos_adicionales['banco_origen'] = request_data.banco_origen
        
        if mision.fecha_pago:
            datos_adicionales['fecha_pago'] = mision.fecha_pago.isoformat()
        
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
        
        return {
            'message': f'Solicitud devuelta para corrección por {user_name}',
            'requiere_accion_adicional': True
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
                SELECT CodCue, DesCue
                FROM aitsa_rrhh.cwprecue 
                ORDER BY CodCue
            """))
            
            partidas = []
            for row in result.fetchall():
                partidas.append(PartidaPresupuestariaResponse(
                    codigo_partida=row.CodCue,
                    descripcion=row.DesCue,
                    es_activa=True
                ))
            
            return partidas
            
        except Exception as e:
            raise BusinessException(f"Error obteniendo catálogo de partidas: {str(e)}")
    
    def get_workflow_states_by_role(self, user: Union[Usuario, dict]) -> List[WorkflowStateInfo]:
        """
        Obtiene los estados de workflow relevantes para un rol específico
        """
        user_role_id = user.get('id_rol') if isinstance(user, dict) else user.id_rol
        
        # Obtener estados donde el usuario puede tomar acciones
        transiciones = self.db.query(TransicionFlujo).filter(
            and_(
                TransicionFlujo.id_rol_autorizado == user_role_id,
                TransicionFlujo.es_activa == True
            )
        ).all()
        
        estado_ids = list(set([t.id_estado_origen for t in transiciones]))
        
        estados = self.db.query(EstadoFlujo).filter(
            EstadoFlujo.id_estado_flujo.in_(estado_ids)
        ).order_by(EstadoFlujo.orden_flujo).all()
        
        estados_info = []
        for estado in estados:
            acciones = [t.tipo_accion.value for t in transiciones if t.id_estado_origen == estado.id_estado_flujo]
            
            estados_info.append(WorkflowStateInfo(
                id_estado=estado.id_estado_flujo,
                nombre_estado=estado.nombre_estado,
                descripcion=estado.descripcion or "",
                es_estado_final=estado.es_estado_final,
                tipo_flujo=estado.tipo_flujo.value,
                orden_flujo=estado.orden_flujo,
                acciones_posibles=acciones
            ))
        
        return estados_info
    
    def get_pending_missions_by_role(
        self, 
        role_name: str, 
        user: Union[Usuario, dict], 
        filters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Obtiene las misiones pendientes según el rol específico.
        """
        # Mapeo de roles a estados de workflow
        role_state_mapping = {
            'Jefe Inmediato': ['PENDIENTE_JEFE'],
            'Analista Tesorería': ['PENDIENTE_REVISION_TESORERIA', 'APROBADO_PARA_PAGO'],
            'Analista Presupuesto': ['PENDIENTE_ASIGNACION_PRESUPUESTO'],
            'Analista Contabilidad': ['PENDIENTE_CONTABILIDAD'],
            'Director Finanzas': ['PENDIENTE_APROBACION_FINANZAS'],
            'Fiscalizador CGR': ['PENDIENTE_REFRENDO_CGR'],
            'Custodio Caja Menuda': ['APROBADO_PARA_PAGO']
        }
        
        # Obtener estados relevantes para el rol
        target_states = role_state_mapping.get(role_name, [])
        if not target_states:
            raise WorkflowException(f"No hay estados definidos para el rol {role_name}")
        
        # Construir query base
        query = self.db.query(Mision).options(
            joinedload(Mision.estado_flujo),
            joinedload(Mision.tipo_mision_enum)
        ).join(EstadoFlujo, Mision.id_estado_flujo == EstadoFlujo.id_estado_flujo).filter(
            EstadoFlujo.nombre_estado.in_(target_states)
        )
        
        # Aplicar filtros específicos por rol
        if role_name == 'Jefe Inmediato' and isinstance(user, dict):
            # Para jefes, solo mostrar solicitudes de sus subordinados
            query = self._apply_supervisor_filter(query, user)
        elif role_name == 'Analista Tesorería':
            # Para tesorería, filtrar por tipo de misión si es necesario
            if filters.get('tipo_mision') == 'CAJA_MENUDA':
                # Para caja menuda, solo mostrar las que están en APROBADO_PARA_PAGO
                query = query.filter(EstadoFlujo.nombre_estado == 'APROBADO_PARA_PAGO')
            else:
                # Para viáticos, mostrar las pendientes de revisión
                query = query.filter(EstadoFlujo.nombre_estado == 'PENDIENTE_REVISION_TESORERIA')
        elif role_name == 'Custodio Caja Menuda':
            # Solo mostrar solicitudes de caja menuda listas para pago
            query = query.filter(
                and_(
                    EstadoFlujo.nombre_estado == 'APROBADO_PARA_PAGO',
                    Mision.tipo_mision == 'CAJA_MENUDA'
                )
            )
        
        # Aplicar filtros generales
        if filters.get('search'):
            search_term = f"%{filters['search']}%"
            query = query.filter(
                or_(
                    Mision.objetivo_mision.ilike(search_term),
                    Mision.destino_mision.ilike(search_term),
                    Mision.beneficiario_nombre.ilike(search_term)
                )
            )
        
        if filters.get('tipo_mision'):
            query = query.filter(Mision.tipo_mision == filters['tipo_mision'])
        
        if filters.get('fecha_desde'):
            query = query.filter(Mision.created_at >= filters['fecha_desde'])
        
        if filters.get('fecha_hasta'):
            query = query.filter(Mision.created_at <= filters['fecha_hasta'])
        
        if filters.get('monto_min'):
            query = query.filter(Mision.monto_total_calculado >= filters['monto_min'])
        
        if filters.get('monto_max'):
            query = query.filter(Mision.monto_total_calculado <= filters['monto_max'])
        
        # Ordenar por fecha de creación (más antiguos primero para priorizar)
        query = query.order_by(Mision.created_at.asc())
        
        # Obtener total para paginación
        total_count = query.count()
        
        # Aplicar paginación
        page = filters.get('page', 1)
        size = filters.get('size', 20)
        offset = (page - 1) * size
        
        missions = query.offset(offset).limit(size).all()
        
        # Calcular estadísticas básicas
        total_query = self.db.query(Mision).join(
            EstadoFlujo, Mision.id_estado_flujo == EstadoFlujo.id_estado_flujo
        ).filter(EstadoFlujo.nombre_estado.in_(target_states))
        
        if role_name == 'Jefe Inmediato' and isinstance(user, dict):
            total_query = self._apply_supervisor_filter(total_query, user)
        
        stats = {
            'total_pendientes': total_query.count(),
            'urgentes': total_query.filter(
                text("DATEDIFF(NOW(), created_at) > 10")
            ).count(),
            'antiguos': total_query.filter(
                text("DATEDIFF(NOW(), created_at) BETWEEN 5 AND 10")
            ).count()
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
        
        # Validar acceso según el rol
        if not self._can_access_mission(mision, user):
            raise PermissionException("No tiene permisos para acceder a esta misión")
        
        return mision
    
    def _validate_and_get_transition(
        self, 
        mision: Mision, 
        action: str, 
        user: Union[Usuario, dict]
    ) -> TransicionFlujo:
        """Valida y obtiene la transición correspondiente"""
        user_role_id = user.get('id_rol') if isinstance(user, dict) else user.id_rol
        
        transicion = self.db.query(TransicionFlujo).options(
            joinedload(TransicionFlujo.estado_destino)
        ).filter(
            and_(
                TransicionFlujo.id_estado_origen == mision.id_estado_flujo,
                TransicionFlujo.id_rol_autorizado == user_role_id,
                TransicionFlujo.tipo_accion == action.upper(),
                TransicionFlujo.es_activa == True
            )
        ).first()
        
        if not transicion:
            raise WorkflowException(
                f"La acción '{action}' no está permitida en el estado actual '{mision.estado_flujo.nombre_estado}' para su rol"
            )
        
        return transicion
    
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
        
        result = self.db_rrhh.execute(text("""
            SELECT CodCue FROM aitsa_rrhh.cwprecue 
            WHERE CodCue IN :codigos
        """), {"codigos": tuple(codigos)})
        
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
            if user.get('is_department_head'):
                # TODO: Implementar lógica para jefes
                return True
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
            # Los usuarios financieros tienen acceso según su rol
            return True  # Simplificado, puede refinarse según reglas específicas
    
    def _can_edit_mission(self, mision: Mision, user: Union[Usuario, dict]) -> bool:
        """Determina si una misión puede ser editada"""
        # Solo se puede editar en estados iniciales
        estados_editables = ['BORRADOR', 'DEVUELTO_CORRECCION']
        return mision.estado_flujo.nombre_estado in estados_editables
    
    def _can_delete_mission(self, mision: Mision, user: Union[Usuario, dict]) -> bool:
        """Determina si una misión puede ser eliminada"""
        # Solo el creador puede eliminar y solo en estado inicial
        if isinstance(user, dict):
            return False  # Los empleados no pueden eliminar
        
        return (
            mision.estado_flujo.nombre_estado == 'BORRADOR' and
            mision.id_usuario_prepara == user.id_usuario
        )
    
    def _requires_additional_data(self, action: TipoAccion, role_name: str) -> bool:
        """Determina si una acción requiere datos adicionales específicos"""
        additional_data_required = {
            ('APROBAR', 'Analista Presupuesto'): True,  # Requiere partidas
            ('APROBAR', 'Director Finanzas'): True,     # Puede requerir monto_aprobado
            ('APROBAR', 'Fiscalizador CGR'): True,      # Puede requerir número de refrendo
            ('RECHAZAR', 'Jefe Inmediato'): True,       # Requiere motivo
            ('DEVOLVER', '*'): True,                    # Requiere comentarios
        }
        
        return additional_data_required.get((action.value, role_name), False) or \
               additional_data_required.get((action.value, '*'), False)
    
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
        
        historial = HistorialFlujo(
            id_mision=mision.id_mision,
            id_usuario_accion=user_id,
            id_estado_anterior=transicion.id_estado_origen,
            id_estado_nuevo=transicion.id_estado_destino,
            tipo_accion=transicion.tipo_accion,
            comentarios=request_data.comentarios,
            datos_adicionales=request_data.datos_adicionales,
            ip_usuario=client_ip
        )
        
        self.db.add(historial)