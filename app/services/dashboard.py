from typing import Dict, Any, List, Union
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, extract, text
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
        stats = {
            "resumen": self._get_resumen_general(user),
            "por_estado": self._get_misiones_por_estado(user),
            "por_tipo": self._get_misiones_por_tipo(user),
            "tendencia_mensual": self._get_tendencia_mensual(user),
            "proximas_acciones": self._get_proximas_acciones(user),
            "alertas": self._get_alertas(user)
        }

        # Agregar estadísticas específicas por rol
        if user.rol.nombre_rol == "Director Finanzas":
            stats["resumen_financiero"] = self._get_resumen_financiero()
        elif user.rol.nombre_rol == "Analista Tesorería":
            stats["pagos_pendientes"] = self._get_pagos_pendientes()

        return stats

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
        
        return {
            "empleado": {
                "cedula": employee.get('cedula'),
                "nombre": employee.get('apenom'),
            },
            "resumen_general": {
                "total_misiones": total_misiones,
                "misiones_mes": misiones_mes,
                "misiones_ano": base_query.filter(
                    extract('year', Mision.created_at) == datetime.now().year
                ).count(),
                "pendientes_revision": base_query.join(EstadoFlujo).filter(
                    EstadoFlujo.es_estado_final == False
                ).count(),
                "aprobadas_total": base_query.join(EstadoFlujo).filter(
                    EstadoFlujo.nombre_estado == "APROBADO"
                ).count(),
                "pagadas_total": base_query.join(EstadoFlujo).filter(
                    EstadoFlujo.nombre_estado == "PAGADO"
                ).count(),
                "rechazadas_total": base_query.join(EstadoFlujo).filter(
                    EstadoFlujo.nombre_estado == "RECHAZADO"
                ).count()
            },
            "montos": {
                "total_solicitado": float(montos.total_solicitado or 0),
                "total_aprobado": float(montos.total_aprobado or 0),
                "monto_mes": float(monto_mes)
            },
            "estadisticas": {
                "misiones_por_estado": misiones_por_estado,
                "misiones_por_tipo": misiones_por_tipo
            }
        }

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
                SELECT apenom FROM aitsa_rrhh.nompersonal 
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