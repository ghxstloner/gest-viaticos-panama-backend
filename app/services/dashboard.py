from typing import Dict, Any, List, Union
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, extract, text, or_
from datetime import datetime, date, timedelta
from decimal import Decimal

from ..models.mission import Mision, EstadoFlujo, HistorialFlujo
from ..models.user import Usuario, Rol
from ..models.enums import TipoMision, EstadoGestion


class DashboardService:
    def __init__(self, db: Session):
        self.db = db

    def get_dashboard_stats(self, user: Union[Usuario, dict]) -> Dict[str, Any]:
        """Obtener estadísticas del dashboard según el rol del usuario"""
        
        # Si es un empleado (dict)
        if isinstance(user, dict):
            return self._get_employee_stats(user)
            
        # Si es un usuario financiero (Usuario)
        return self._get_financial_user_stats(user)

    def _get_financial_user_stats(self, user: Usuario) -> Dict[str, Any]:
        """Obtener estadísticas para usuarios financieros según permisos"""
        
        # Determinar qué estados puede gestionar basado en permisos
        target_states = self._get_target_states_by_permissions(user)
        
        if not target_states:
            return self._get_empty_stats()
        
        # Obtener estadísticas según los estados permitidos
        resumen = self._get_resumen_general_by_states(user, target_states)
        por_estado = self._get_misiones_por_estado_by_states(user, target_states)
        por_tipo = self._get_misiones_por_tipo_by_states(user, target_states)
        
        # Convertir a formato esperado por DashboardStats
        missions_by_state = {item['estado']: item['cantidad'] for item in por_estado}
        missions_by_type = {item['tipo']: item['cantidad'] for item in por_tipo}
        
        # Obtener misiones recientes
        recent_missions = self._get_proximas_acciones_by_states(user, target_states)
        
        # Calcular montos totales (pendientes + aprobadas)
        total_amount = self._get_total_amount_by_permissions(user)
        approved_amount = self._get_approved_amount_by_permissions(user)
        pending_amount = max(0, total_amount - approved_amount)
        
        # Calcular misiones aprobadas (estados posteriores al estado permitido)
        missions_approved = self._count_approved_missions_by_permissions(user)
        
        # Construir respuesta según el schema DashboardStats
        stats = {
            "total_missions": resumen.get('total_misiones', 0),
            "missions_pending": resumen.get('pendientes', 0),
            "missions_approved": missions_approved,
            "missions_rejected": self._count_missions_by_states(user, "RECHAZADO", target_states),
            "missions_in_progress": resumen.get('pendientes', 0),
            "total_amount": total_amount,
            "approved_amount": approved_amount,
            "pending_amount": pending_amount,
            "missions_by_type": missions_by_type,
            "missions_by_state": missions_by_state,
            "recent_missions": recent_missions
        }

        return stats

    def _get_target_states_by_permissions(self, user: Usuario) -> List[str]:
        """Determinar qué estados puede gestionar basado en permisos del dashboard"""
        target_states = set()  # Usar set para evitar duplicados
        
        # Verificar permisos específicos del dashboard
        if self._has_permission(user, 'DASHBOARD_PENDIENTE_JEFE'):
            target_states.update(['PENDIENTE_JEFE', 'DEVUELTO_CORRECCION_JEFE'])
        
        if self._has_permission(user, 'DASHBOARD_TESORERIA'):
            target_states.update(['PENDIENTE_REVISION_TESORERIA', 'DEVUELTO_CORRECCION_TESORERIA'])
        
        if self._has_permission(user, 'DASHBOARD_PRESUPUESTO'):
            target_states.update(['PENDIENTE_ASIGNACION_PRESUPUESTO', 'DEVUELTO_CORRECCION_PRESUPUESTO'])
        
        if self._has_permission(user, 'DASHBOARD_CONTABILIDAD'):
            target_states.update(['PENDIENTE_CONTABILIDAD', 'DEVUELTO_CORRECCION_CONTABILIDAD'])
        
        if self._has_permission(user, 'DASHBOARD_FINANZAS'):
            target_states.update(['PENDIENTE_APROBACION_FINANZAS', 'DEVUELTO_CORRECCION_FINANZAS'])
        
        if self._has_permission(user, 'DASHBOARD_CGR'):
            target_states.update(['PENDIENTE_REFRENDO_CGR', 'DEVUELTO_CORRECCION_CGR'])
        
        if self._has_permission(user, 'DASHBOARD_CAJA'):
            target_states.update(['APROBADO_PARA_PAGO', 'PAGADO'])
        
        return list(target_states)

    def _has_permission(self, user: Usuario, permission_code: str) -> bool:
        """Verificar si el usuario tiene un permiso específico"""
        try:
            if hasattr(user, 'has_permission'):
                return user.has_permission(permission_code)
            
            elif hasattr(user, 'rol') and hasattr(user.rol, 'permisos'):
                permisos = user.rol.permisos
                for permiso in permisos:
                    if hasattr(permiso, 'codigo') and permiso.codigo == permission_code:
                        return True
                return False
            
            elif hasattr(user, 'rol') and hasattr(user.rol, 'nombre_rol'):
                if user.rol.nombre_rol == 'Administrador Sistema':
                    return True
            
            return False
            
        except Exception as e:
            print(f"🔍 ERROR verificando permisos: {e}")
            return False

    def _get_empty_stats(self) -> Dict[str, Any]:
        """Retornar estadísticas vacías cuando no hay permisos"""
        return {
            "total_missions": 0,
            "missions_pending": 0,
            "missions_approved": 0,
            "missions_rejected": 0,
            "missions_in_progress": 0,
            "total_amount": 0,
            "approved_amount": 0,
            "pending_amount": 0,
            "missions_by_type": {},
            "missions_by_state": {},
            "recent_missions": []
        }

    def _get_resumen_general_by_states(self, user: Usuario, target_states: List[str]) -> Dict[str, Any]:
        """Obtener resumen general de misiones según estados permitidos"""
        query = self._get_base_query_by_states(user, target_states)
        
        total_misiones = query.count()
        
        # Misiones por estado general
        pendientes = query.join(EstadoFlujo).filter(
            EstadoFlujo.es_estado_final == False
        ).count()
        
        completadas = query.join(EstadoFlujo).filter(
            EstadoFlujo.nombre_estado == "PAGADO"
        ).count()
        
        # Montos
        monto_total = query.with_entities(
            func.sum(Mision.monto_total_calculado)
        ).scalar() or Decimal('0.00')
        
        monto_aprobado = query.filter(
            Mision.monto_aprobado.isnot(None)
        ).with_entities(
            func.sum(Mision.monto_aprobado)
        ).scalar() or Decimal('0.00')
        
        return {
            "total_misiones": total_misiones,
            "pendientes": pendientes,
            "completadas": completadas,
            "tasa_completado": round((completadas / total_misiones * 100) if total_misiones > 0 else 0, 2),
            "monto_total_solicitado": float(monto_total),
            "monto_total_aprobado": float(monto_aprobado)
        }

    def _get_misiones_por_estado_by_states(self, user: Usuario, target_states: List[str]) -> List[Dict[str, Any]]:
        """Obtener distribución de misiones por estado según estados permitidos"""
        query = self._get_base_query_by_states(user, target_states)
        
        results = query.join(EstadoFlujo).group_by(
            EstadoFlujo.id_estado_flujo,
            EstadoFlujo.nombre_estado
        ).with_entities(
            EstadoFlujo.nombre_estado,
            func.count(Mision.id_mision).label('cantidad'),
            func.sum(Mision.monto_total_calculado).label('monto_total')
        ).all()
        
        return [
            {
                "estado": r.nombre_estado,
                "cantidad": r.cantidad,
                "monto_total": float(r.monto_total or 0)
            }
            for r in results
        ]

    def _get_misiones_por_tipo_by_states(self, user: Usuario, target_states: List[str]) -> List[Dict[str, Any]]:
        """Obtener distribución de misiones por tipo según estados permitidos"""
        query = self._get_base_query_by_states(user, target_states)
        
        results = query.group_by(
            Mision.tipo_mision
        ).with_entities(
            Mision.tipo_mision,
            func.count(Mision.id_mision).label('cantidad'),
            func.sum(Mision.monto_total_calculado).label('monto_total')
        ).all()
        
        return [
            {
                "tipo": r.tipo_mision.value,
                "cantidad": r.cantidad,
                "monto_total": float(r.monto_total or 0)
            }
            for r in results
        ]

    def _get_proximas_acciones_by_states(self, user: Usuario, target_states: List[str]) -> List[Dict[str, Any]]:
        """Obtener misiones que requieren acción del usuario según estados permitidos"""
        query = self.db.query(Mision).filter(
            Mision.id_estado_flujo.in_([self._get_estado_id(estado) for estado in target_states])
        )
        
        # Aplicar filtros según rol
        query = self._apply_role_filters(query, user)
        
        # Obtener las 10 más recientes
        misiones = query.order_by(
            Mision.updated_at.desc()
        ).limit(10).all()
        
        return [
            {
                "id_mision": m.id_mision,
                "tipo": m.tipo_mision.value,
                "objetivo": m.objetivo_mision[:100],
                "beneficiario": self._get_nombre_beneficiario(m.beneficiario_personal_id),
                "monto": float(m.monto_total_calculado),
                "dias_pendiente": (datetime.now().date() - m.updated_at.date()).days,
                "estado_actual": m.estado_flujo.nombre_estado
            }
            for m in misiones
        ]

    def _get_base_query_by_states(self, user: Usuario, target_states: List[str]) -> Any:
        """Obtener query base según estados permitidos"""
        query = self.db.query(Mision).filter(
            Mision.id_estado_flujo.in_([self._get_estado_id(estado) for estado in target_states])
        )
        return self._apply_role_filters(query, user)

    def _get_estado_id(self, estado_nombre: str) -> int:
        """Obtener ID del estado por nombre"""
        estado = self.db.query(EstadoFlujo).filter(
            EstadoFlujo.nombre_estado == estado_nombre
        ).first()
        return estado.id_estado_flujo if estado else 0

    def _count_missions_by_states(self, user: Usuario, state_name: str, target_states: List[str]) -> int:
        """Contar misiones por estado específico según estados permitidos"""
        query = self._get_base_query_by_states(user, target_states)
        return query.join(EstadoFlujo).filter(
            EstadoFlujo.nombre_estado == state_name
        ).count()

    def _count_approved_missions_by_permissions(self, user: Usuario) -> int:
        """Contar misiones aprobadas (estados posteriores al estado permitido)"""
        approved_states = self._get_approved_states_by_permissions(user)
        
        if not approved_states:
            return 0
        
        # Contar misiones en estados aprobados
        query = self.db.query(Mision).filter(
            Mision.id_estado_flujo.in_([self._get_estado_id(estado) for estado in approved_states])
        )
        
        # Aplicar filtros según rol
        query = self._apply_role_filters(query, user)
        
        return query.count()

    def _get_total_amount_by_permissions(self, user: Usuario) -> float:
        """Obtener monto total (pendientes + aprobadas) según permisos"""
        all_states = set()  # Usar set para evitar duplicados
        
        # Obtener estados permitidos (pendientes)
        target_states = self._get_target_states_by_permissions(user)
        all_states.update(target_states)
        
        # Obtener estados aprobados (posteriores)
        approved_states = self._get_approved_states_by_permissions(user)
        all_states.update(approved_states)
        
        if not all_states:
            return 0.0
        
        # Calcular monto total de todos los estados
        query = self.db.query(Mision).filter(
            Mision.id_estado_flujo.in_([self._get_estado_id(estado) for estado in all_states])
        )
        
        # Aplicar filtros según rol
        query = self._apply_role_filters(query, user)
        
        total_amount = query.with_entities(
            func.sum(Mision.monto_total_calculado)
        ).scalar() or Decimal('0.00')
        
        return float(total_amount)

    def _get_approved_amount_by_permissions(self, user: Usuario) -> float:
        """Obtener monto de misiones aprobadas según permisos"""
        approved_states = self._get_approved_states_by_permissions(user)
        
        if not approved_states:
            return 0.0
        
        # Calcular monto de estados aprobados
        query = self.db.query(Mision).filter(
            Mision.id_estado_flujo.in_([self._get_estado_id(estado) for estado in approved_states])
        )
        
        # Aplicar filtros según rol
        query = self._apply_role_filters(query, user)
        
        approved_amount = query.with_entities(
            func.sum(Mision.monto_total_calculado)
        ).scalar() or Decimal('0.00')
        
        return float(approved_amount)

    def _get_approved_states_by_permissions(self, user: Usuario) -> List[str]:
        """Obtener estados aprobados según permisos del dashboard"""
        # Determinar el permiso más alto del usuario
        highest_permission = self._get_highest_permission(user)
        
        approved_states = set()  # Usar set para evitar duplicados
        
        # Solo agregar estados posteriores al permiso más alto
        if highest_permission == 'DASHBOARD_PENDIENTE_JEFE':
            # Para jefes, aprobadas son las que están después de PENDIENTE_JEFE
            approved_states.update([
                'PENDIENTE_REVISION_TESORERIA', 'DEVUELTO_CORRECCION_TESORERIA',
                'PENDIENTE_ASIGNACION_PRESUPUESTO', 'DEVUELTO_CORRECCION_PRESUPUESTO',
                'PENDIENTE_CONTABILIDAD', 'DEVUELTO_CORRECCION_CONTABILIDAD',
                'PENDIENTE_APROBACION_FINANZAS', 'DEVUELTO_CORRECCION_FINANZAS',
                'PENDIENTE_REFRENDO_CGR', 'DEVUELTO_CORRECCION_CGR',
                'APROBADO_PARA_PAGO', 'PAGADO'
            ])
        
        elif highest_permission == 'DASHBOARD_TESORERIA':
            # Para tesorería, aprobadas son las que están después de PENDIENTE_REVISION_TESORERIA
            approved_states.update([
                'PENDIENTE_ASIGNACION_PRESUPUESTO', 'DEVUELTO_CORRECCION_PRESUPUESTO',
                'PENDIENTE_CONTABILIDAD', 'DEVUELTO_CORRECCION_CONTABILIDAD',
                'PENDIENTE_APROBACION_FINANZAS', 'DEVUELTO_CORRECCION_FINANZAS',
                'PENDIENTE_REFRENDO_CGR', 'DEVUELTO_CORRECCION_CGR',
                'APROBADO_PARA_PAGO', 'PAGADO'
            ])
        
        elif highest_permission == 'DASHBOARD_PRESUPUESTO':
            # Para presupuesto, aprobadas son las que están después de PENDIENTE_ASIGNACION_PRESUPUESTO
            approved_states.update([
                'PENDIENTE_CONTABILIDAD', 'DEVUELTO_CORRECCION_CONTABILIDAD',
                'PENDIENTE_APROBACION_FINANZAS', 'DEVUELTO_CORRECCION_FINANZAS',
                'PENDIENTE_REFRENDO_CGR', 'DEVUELTO_CORRECCION_CGR',
                'APROBADO_PARA_PAGO', 'PAGADO'
            ])
        
        elif highest_permission == 'DASHBOARD_CONTABILIDAD':
            # Para contabilidad, aprobadas son las que están después de PENDIENTE_CONTABILIDAD
            approved_states.update([
                'PENDIENTE_APROBACION_FINANZAS', 'DEVUELTO_CORRECCION_FINANZAS',
                'PENDIENTE_REFRENDO_CGR', 'DEVUELTO_CORRECCION_CGR',
                'APROBADO_PARA_PAGO', 'PAGADO'
            ])
        
        elif highest_permission == 'DASHBOARD_FINANZAS':
            # Para finanzas, aprobadas son las que están después de PENDIENTE_APROBACION_FINANZAS
            approved_states.update([
                'PENDIENTE_REFRENDO_CGR', 'DEVUELTO_CORRECCION_CGR',
                'APROBADO_PARA_PAGO', 'PAGADO'
            ])
        
        elif highest_permission == 'DASHBOARD_CGR':
            # Para CGR, aprobadas son las que están después de PENDIENTE_REFRENDO_CGR
            approved_states.update([
                'APROBADO_PARA_PAGO', 'PAGADO'
            ])
        
        elif highest_permission == 'DASHBOARD_CAJA':
            # Para caja, aprobadas son las que están pagadas
            approved_states.update([
                'PAGADO'
            ])
        
        return list(approved_states)

    def _get_highest_permission(self, user: Usuario) -> str:
        """Determinar el permiso más alto del usuario según jerarquía del flujo"""
        user_permissions = []
        
        # Recolectar todos los permisos del dashboard que tiene el usuario
        dashboard_permissions = [
            'DASHBOARD_PENDIENTE_JEFE',
            'DASHBOARD_TESORERIA', 
            'DASHBOARD_PRESUPUESTO',
            'DASHBOARD_CONTABILIDAD',
            'DASHBOARD_FINANZAS',
            'DASHBOARD_CGR',
            'DASHBOARD_CAJA'
        ]
        
        for permission in dashboard_permissions:
            if self._has_permission(user, permission):
                user_permissions.append(permission)
        
        if not user_permissions:
            return None
        
        # Si solo tiene un permiso, ese es el más alto
        if len(user_permissions) == 1:
            return user_permissions[0]
        
        # Si tiene múltiples permisos, determinar el más alto según jerarquía
        # La jerarquía va de menor a mayor: JEFE -> TESORERIA -> PRESUPUESTO -> CONTABILIDAD -> FINANZAS -> CGR -> CAJA
        hierarchy = {
            'DASHBOARD_PENDIENTE_JEFE': 1,
            'DASHBOARD_TESORERIA': 2,
            'DASHBOARD_PRESUPUESTO': 3,
            'DASHBOARD_CONTABILIDAD': 4,
            'DASHBOARD_FINANZAS': 5,
            'DASHBOARD_CGR': 6,
            'DASHBOARD_CAJA': 7
        }
        
        # Encontrar el permiso con el nivel más alto
        highest_permission = user_permissions[0]
        highest_level = hierarchy.get(highest_permission, 0)
        
        for permission in user_permissions:
            level = hierarchy.get(permission, 0)
            if level > highest_level:
                highest_level = level
                highest_permission = permission
        
        return highest_permission

    def _get_employee_stats(self, employee: dict) -> Dict[str, Any]:
        """Obtener estadísticas específicas para empleados"""
        personal_id = employee.get('personal_id')
        
        # Consulta base para misiones del empleado
        base_query = self.db.query(Mision).filter(
            Mision.beneficiario_personal_id == personal_id
        )
        
        # Estadísticas generales
        total_misiones = base_query.count()
        misiones_mes = base_query.filter(
            extract('month', Mision.created_at) == datetime.now().month,
            extract('year', Mision.created_at) == datetime.now().year
        ).count()
        
        # Estadísticas por estado
        estados_query = base_query.join(EstadoFlujo).group_by(
            EstadoFlujo.nombre_estado
        ).with_entities(
            EstadoFlujo.nombre_estado,
            func.count(Mision.id_mision).label('cantidad')
        )
        
        misiones_por_estado = {
            estado: cantidad
            for estado, cantidad in estados_query.all()
        }
        
        # Estadísticas por tipo
        tipos_query = base_query.group_by(
            Mision.tipo_mision
        ).with_entities(
            Mision.tipo_mision,
            func.count(Mision.id_mision).label('cantidad')
        )
        
        misiones_por_tipo = {
            tipo.value: cantidad
            for tipo, cantidad in tipos_query.all()
        }
        
        # Montos
        montos = base_query.with_entities(
            func.sum(Mision.monto_total_calculado).label('total_solicitado'),
            func.sum(Mision.monto_aprobado).label('total_aprobado')
        ).first()
        
        monto_mes = base_query.filter(
            extract('month', Mision.created_at) == datetime.now().month,
            extract('year', Mision.created_at) == datetime.now().year
        ).with_entities(
            func.sum(Mision.monto_total_calculado)
        ).scalar() or Decimal('0.00')
        
        # Calcular montos
        total_amount = float(montos.total_solicitado or 0)
        approved_amount = float(montos.total_aprobado or 0)
        pending_amount = max(0, total_amount - approved_amount)
        
        # Contar estados específicos
        missions_approved = base_query.join(EstadoFlujo).filter(
            EstadoFlujo.nombre_estado == "APROBADO"
        ).count()
        
        missions_rejected = base_query.join(EstadoFlujo).filter(
            EstadoFlujo.nombre_estado == "RECHAZADO"
        ).count()
        
        missions_pending = base_query.join(EstadoFlujo).filter(
            EstadoFlujo.es_estado_final == False
        ).count()
        
        # Obtener misiones recientes (últimas 5)
        recent_missions = base_query.order_by(
            Mision.updated_at.desc()
        ).limit(5).all()
        
        recent_missions_data = [
            {
                "id_mision": m.id_mision,
                "tipo": m.tipo_mision.value,
                "objetivo": m.objetivo_mision[:100] if m.objetivo_mision else "",
                "monto": float(m.monto_total_calculado),
                "estado": m.estado_flujo.nombre_estado,
                "fecha_actualizacion": m.updated_at.isoformat()
            }
            for m in recent_missions
        ]
        
        return {
            "total_missions": total_misiones,
            "missions_pending": missions_pending,
            "missions_approved": missions_approved,
            "missions_rejected": missions_rejected,
            "missions_in_progress": missions_pending,
            "total_amount": total_amount,
            "approved_amount": approved_amount,
            "pending_amount": pending_amount,
            "missions_by_type": misiones_por_tipo,
            "missions_by_state": misiones_por_estado,
            "recent_missions": recent_missions_data,
        }


        
        class SimulatedRole:
            def __init__(self):
                self.nombre_rol = "Solicitante"
                self.permisos = []
        
        return SimulatedUser()

    def _get_resumen_general(self, user: Usuario) -> Dict[str, Any]:
        """Obtener resumen general de misiones"""
        query = self._get_base_query(user)
        
        total_misiones = query.count()
        
        # Misiones por estado general
        pendientes = query.join(EstadoFlujo).filter(
            EstadoFlujo.es_estado_final == False
        ).count()
        
        completadas = query.join(EstadoFlujo).filter(
            EstadoFlujo.nombre_estado == "PAGADO"
        ).count()
        
        # Montos
        monto_total = query.with_entities(
            func.sum(Mision.monto_total_calculado)
        ).scalar() or Decimal('0.00')
        
        monto_aprobado = query.filter(
            Mision.monto_aprobado.isnot(None)
        ).with_entities(
            func.sum(Mision.monto_aprobado)
        ).scalar() or Decimal('0.00')
        
        return {
            "total_misiones": total_misiones,
            "pendientes": pendientes,
            "completadas": completadas,
            "tasa_completado": round((completadas / total_misiones * 100) if total_misiones > 0 else 0, 2),
            "monto_total_solicitado": float(monto_total),
            "monto_total_aprobado": float(monto_aprobado)
        }

    def _get_misiones_por_estado(self, user: Usuario) -> List[Dict[str, Any]]:
        """Obtener distribución de misiones por estado"""
        query = self._get_base_query(user)
        
        results = query.join(EstadoFlujo).group_by(
            EstadoFlujo.id_estado_flujo,
            EstadoFlujo.nombre_estado
        ).with_entities(
            EstadoFlujo.nombre_estado,
            func.count(Mision.id_mision).label('cantidad'),
            func.sum(Mision.monto_total_calculado).label('monto_total')
        ).all()
        
        return [
            {
                "estado": r.nombre_estado,
                "cantidad": r.cantidad,
                "monto_total": float(r.monto_total or 0)
            }
            for r in results
        ]

    def _get_misiones_por_tipo(self, user: Usuario) -> List[Dict[str, Any]]:
        """Obtener distribución de misiones por tipo"""
        query = self._get_base_query(user)
        
        results = query.group_by(
            Mision.tipo_mision
        ).with_entities(
            Mision.tipo_mision,
            func.count(Mision.id_mision).label('cantidad'),
            func.sum(Mision.monto_total_calculado).label('monto_total')
        ).all()
        
        return [
            {
                "tipo": r.tipo_mision.value,
                "cantidad": r.cantidad,
                "monto_total": float(r.monto_total or 0)
            }
            for r in results
        ]

    def _get_tendencia_mensual(self, user: Usuario) -> List[Dict[str, Any]]:
        """Obtener tendencia de misiones por mes (últimos 6 meses)"""
        query = self._get_base_query(user)
        
        # Filtrar últimos 6 meses
        fecha_inicio = datetime.now() - timedelta(days=180)
        query = query.filter(Mision.created_at >= fecha_inicio)
        
        results = query.group_by(
            extract('year', Mision.created_at),
            extract('month', Mision.created_at)
        ).with_entities(
            extract('year', Mision.created_at).label('año'),
            extract('month', Mision.created_at).label('mes'),
            func.count(Mision.id_mision).label('cantidad'),
            func.sum(Mision.monto_total_calculado).label('monto_total')
        ).order_by('año', 'mes').all()
        
        return [
            {
                "periodo": f"{int(r.año)}-{int(r.mes):02d}",
                "cantidad": r.cantidad,
                "monto_total": float(r.monto_total or 0)
            }
            for r in results
        ]

    def _get_proximas_acciones(self, user: Usuario) -> List[Dict[str, Any]]:
        """Obtener misiones que requieren acción del usuario"""
        # Obtener estados donde el usuario puede actuar
        estados_accion = self._get_estados_accion_usuario(user)
        
        if not estados_accion:
            return []
        
        query = self.db.query(Mision).filter(
            Mision.id_estado_flujo.in_([e.id_estado_flujo for e in estados_accion])
        )
        
        # Aplicar filtros según rol
        query = self._apply_role_filters(query, user)
        
        # Obtener las 10 más recientes
        misiones = query.order_by(
            Mision.updated_at.desc()
        ).limit(10).all()
        
        return [
            {
                "id_mision": m.id_mision,
                "tipo": m.tipo_mision.value,
                "objetivo": m.objetivo_mision[:100],
                "beneficiario": self._get_nombre_beneficiario(m.beneficiario_personal_id),
                "monto": float(m.monto_total_calculado),
                "dias_pendiente": (datetime.now().date() - m.updated_at.date()).days,
                "estado_actual": m.estado_flujo.nombre_estado
            }
            for m in misiones
        ]

    def _get_alertas(self, user: Usuario) -> List[Dict[str, Any]]:
        """Obtener alertas según el rol del usuario"""
        alertas = []
        
        # Alertas de subsanaciones pendientes
        if user.rol.nombre_rol in ["Solicitante", "Jefe Inmediato"]:
            from ..models.mission import Subsanacion
            from ..models.enums import EstadoSubsanacion
            
            subsanaciones = self.db.query(Subsanacion).filter(
                and_(
                    Subsanacion.id_usuario_responsable == user.id_usuario,
                    Subsanacion.estado == EstadoSubsanacion.PENDIENTE
                )
            ).all()
            
            for s in subsanaciones:
                dias_restantes = (s.fecha_limite - date.today()).days
                alertas.append({
                    "tipo": "subsanacion",
                    "nivel": "warning" if dias_restantes > 2 else "danger",
                    "mensaje": f"Subsanación pendiente para misión #{s.id_mision}",
                    "dias_restantes": dias_restantes,
                    "enlace": f"/missions/{s.id_mision}/subsanations/{s.id_subsanacion}"
                })
        
        # Alertas de misiones próximas a vencer
        if user.rol.nombre_rol == "Analista Tesorería":
            misiones_proximas = self.db.query(Mision).filter(
                and_(
                    Mision.fecha_salida <= datetime.now() + timedelta(days=3),
                    Mision.fecha_salida >= datetime.now(),
                    Mision.id_estado_flujo != 7  # No pagadas
                )
            ).all()
            
            for m in misiones_proximas:
                dias_para_viaje = (m.fecha_salida.date() - date.today()).days
                alertas.append({
                    "tipo": "viaje_proximo",
                    "nivel": "warning" if dias_para_viaje > 1 else "danger",
                    "mensaje": f"Viaje próximo sin pagar - Misión #{m.id_mision}",
                    "dias_restantes": dias_para_viaje,
                    "enlace": f"/missions/{m.id_mision}"
                })
        
        return alertas

    def _get_resumen_financiero(self) -> Dict[str, Any]:
        """Resumen financiero para directores"""
        mes_actual = datetime.now().month
        año_actual = datetime.now().year
        
        # Montos del mes actual
        monto_mes_actual = self.db.query(
            func.sum(Mision.monto_total_calculado)
        ).filter(
            extract('month', Mision.created_at) == mes_actual,
            extract('year', Mision.created_at) == año_actual
        ).scalar() or Decimal('0.00')
        
        # Montos del mes anterior
        mes_anterior = mes_actual - 1 if mes_actual > 1 else 12
        año_mes_anterior = año_actual if mes_actual > 1 else año_actual - 1
        
        monto_mes_anterior = self.db.query(
            func.sum(Mision.monto_total_calculado)
        ).filter(
            extract('month', Mision.created_at) == mes_anterior,
            extract('year', Mision.created_at) == año_mes_anterior
        ).scalar() or Decimal('0.00')
        
        # Calcular variación
        variacion = 0
        if monto_mes_anterior > 0:
            variacion = ((monto_mes_actual - monto_mes_anterior) / monto_mes_anterior * 100)
        
        return {
            "monto_mes_actual": float(monto_mes_actual),
            "monto_mes_anterior": float(monto_mes_anterior),
            "variacion_porcentual": round(float(variacion), 2),
            "presupuesto_disponible": self._get_presupuesto_disponible(),
            "ejecucion_presupuestaria": self._get_ejecucion_presupuestaria()
        }

    def _get_pagos_pendientes(self) -> Dict[str, Any]:
        """Obtener resumen de pagos pendientes"""
        pagos_efectivo = self.db.query(Mision).join(EstadoFlujo).filter(
            and_(
                EstadoFlujo.nombre_estado == "APROBADO_PARA_PAGO",
                Mision.monto_total_calculado <= 200  # Límite para efectivo
            )
        ).count()
        
        pagos_transferencia = self.db.query(Mision).join(EstadoFlujo).filter(
            and_(
                EstadoFlujo.nombre_estado == "APROBADO_PARA_PAGO",
                Mision.monto_total_calculado > 200
            )
        ).count()
        
        monto_total_pendiente = self.db.query(
            func.sum(Mision.monto_aprobado)
        ).join(EstadoFlujo).filter(
            EstadoFlujo.nombre_estado == "APROBADO_PARA_PAGO"
        ).scalar() or Decimal('0.00')
        
        return {
            "pagos_efectivo_pendientes": pagos_efectivo,
            "pagos_transferencia_pendientes": pagos_transferencia,
            "monto_total_pendiente": float(monto_total_pendiente)
        }

    # Métodos auxiliares
    def _get_base_query(self, user: Usuario):
        """Obtener query base según el rol del usuario"""
        query = self.db.query(Mision)
        return self._apply_role_filters(query, user)

    def _apply_role_filters(self, query, user: Usuario):
        """Aplicar filtros según el rol del usuario"""
        if user.rol.nombre_rol == "Solicitante":
            query = query.filter(Mision.beneficiario_personal_id == user.personal_id_rrhh)
        elif user.rol.nombre_rol == "Jefe Inmediato":
            # TODO: Filtrar por subordinados
            pass
        elif user.rol.nombre_rol in ["Analista Tesorería", "Analista Presupuesto", "Analista Contabilidad"]:
            estados = self._get_estados_for_role(user.rol.nombre_rol)
            if estados:
                query = query.filter(Mision.id_estado_flujo.in_([e.id_estado_flujo for e in estados]))
        
        return query

    def _get_estados_for_role(self, role_name: str) -> List[EstadoFlujo]:
        """Obtener estados según el rol"""
        # Similar al método en MissionService
        pass

    def _get_estados_accion_usuario(self, user: Usuario) -> List[EstadoFlujo]:
        """Obtener estados donde el usuario puede tomar acción"""
        from ..models.mission import TransicionFlujo
        
        transiciones = self.db.query(TransicionFlujo).filter(
            and_(
                TransicionFlujo.id_rol_autorizado == user.id_rol,
                TransicionFlujo.es_activa == True
            )
        ).all()
        
        estado_ids = list(set([t.id_estado_origen for t in transiciones]))
        
        return self.db.query(EstadoFlujo).filter(
            EstadoFlujo.id_estado_flujo.in_(estado_ids)
        ).all()

    def _get_nombre_beneficiario(self, personal_id: int) -> str:
        """Obtener nombre del beneficiario"""
        try:
            from sqlalchemy import text
            result = self.db.execute(text("""
                SELECT apenom FROM nompersonal 
                WHERE personal_id = :personal_id
            """), {"personal_id": personal_id})
            row = result.fetchone()
            return row.apenom if row else "Desconocido"
        except:
            return "Desconocido"

    def _get_presupuesto_disponible(self) -> float:
        """Obtener presupuesto disponible (placeholder)"""
        # TODO: Implementar conexión con sistema de presupuesto
        return 100000.00

    def _get_ejecucion_presupuestaria(self) -> float:
        """Obtener porcentaje de ejecución presupuestaria"""
        # TODO: Implementar cálculo real
        return 65.5