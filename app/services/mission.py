# ===============================================================
# app/services/mission.py (COMPLETO Y FINAL v3)
# ===============================================================

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc, text, and_
from decimal import Decimal
from datetime import datetime, date, timedelta

from ..models.mission import (
    Mision, EstadoFlujo, HistorialFlujo, TransicionFlujo,
    GestionCobro, Subsanacion, ItemViatico, ItemTransporte, Adjunto,
    MisionPartidaPresupuestaria
)
from ..models.user import Usuario
from ..models.configuration import ConfiguracionSistema
from ..models.enums import TipoMision, TipoAccion, EstadoGestion, EstadoSubsanacion
from ..schemas.mission import (
    MisionCreate, MisionUpdate, PresupuestoAssignRequest
)
from fastapi import HTTPException, status
from ..core.exceptions import (
    BusinessException, WorkflowException, ValidationException,
    PermissionException, MissionException
)
from ..services.notifaction_service import NotificationService

class MissionService:
    """
    Contiene toda la lógica de negocio para la gestión de misiones (viáticos y caja menuda).
    """
    def __init__(self, db: Session, db_rrhh: Optional[Session] = None):
        self.db = db
        self.db_rrhh = db_rrhh
        self._notification_service = NotificationService(db)

    def create_mission(self, mission_data: MisionCreate, preparer_id: int) -> Mision:
        """
        Crea una nueva misión en la base de datos, validando la información
        y estableciendo los valores iniciales según el tipo de misión.
        """
        if mission_data.tipo_mision == TipoMision.VIATICOS:
            if not (mission_data.fecha_salida and mission_data.fecha_retorno):
                raise ValidationException("Las fechas de salida y retorno son obligatorias para viáticos.")
            self._validate_mission_dates(mission_data.fecha_salida, mission_data.fecha_retorno)

        estado_inicial = self.db.query(EstadoFlujo).filter(EstadoFlujo.nombre_estado == "PENDIENTE_REVISION_TESORERIA").first()
        if not estado_inicial:
            raise BusinessException("Configuración de flujo inválida: No se encontró el estado inicial.")

        # Generar número de solicitud automáticamente
        from app.api.v1.employee_missions import generate_request_number
        numero_solicitud = generate_request_number(self.db)
        
        mision = Mision(
            tipo_mision=mission_data.tipo_mision,
            beneficiario_personal_id=mission_data.beneficiario_personal_id,
            id_usuario_prepara=preparer_id,
            objetivo_mision=mission_data.objetivo_mision,
            observaciones_especiales=mission_data.observaciones_especiales,
            id_estado_flujo=estado_inicial.id_estado_flujo,
            numero_solicitud=numero_solicitud,
            codnivel1_solicitante=mission_data.codnivel1_solicitante,
            destino_mision=mission_data.destino_mision,
            fecha_salida=mission_data.fecha_salida,
            fecha_retorno=mission_data.fecha_retorno,
            categoria_beneficiario=mission_data.categoria_beneficiario,
            tipo_viaje=mission_data.tipo_viaje,
            region_exterior=mission_data.region_exterior,
            transporte_oficial=mission_data.transporte_oficial,
            codnivel1_destino_cm=mission_data.codnivel1_destino_cm,
            codnivel2_destino_cm=mission_data.codnivel2_destino_cm
        )

        self.db.add(mision)
        self.db.flush()

        total_viaticos = self._process_viaticos_items(mision.id_mision, mission_data.items_viaticos)
        total_transporte = self._process_transporte_items(mision.id_mision, mission_data.items_transporte)
        self._process_partidas_items(mision.id_mision, mission_data.partidas_presupuestarias)

        if mission_data.tipo_mision == TipoMision.CAJA_MENUDA:
            mision.monto_total_calculado = mission_data.monto_solicitado
        else:
            mision.monto_total_calculado = total_viaticos + total_transporte

        config_monto_cgr = self._get_config_value("MONTO_REFRENDO_CGR", "1000.00")
        mision.requiere_refrendo_cgr = mision.monto_total_calculado >= Decimal(config_monto_cgr)

        self._create_history_record(
            mision_id=mision.id_mision,
            user_id=None,
            new_state_id=estado_inicial.id_estado_flujo,
            action_type=TipoAccion.CREAR,
            comments="Solicitud creada exitosamente."
        )

        self.db.commit()
        self.db.refresh(mision)
        
        # Crear notificación para el jefe inmediato
        print(f"🔔 Intentando crear notificación para misión {mision.id_mision}")
        print(f"🔔 Beneficiario personal_id: {mision.beneficiario_personal_id}")
        
        # Verificar que el servicio de notificaciones esté disponible
        if not hasattr(self, '_notification_service'):
            print("❌ Servicio de notificaciones no disponible")
            return mision
            
        if not self.db_rrhh:
            print("⚠️ No hay conexión a RRHH, no se puede crear notificación")
            return mision
            
        try:
            jefe_personal_id = self._get_jefe_inmediato_personal_id(mision.beneficiario_personal_id)
            print(f"🔔 Jefe personal_id obtenido: {jefe_personal_id}")
            
            if jefe_personal_id:
                print(f"🔔 Creando notificación para jefe {jefe_personal_id}")
                notification = self._notification_service.create_mission_created_notification(
                    mission_id=mision.id_mision,
                    jefe_personal_id=jefe_personal_id,
                    numero_solicitud=mision.numero_solicitud
                )
                print(f"✅ Notificación creada exitosamente: {notification.notificacion_id}")
            else:
                print("⚠️ No se pudo obtener el jefe inmediato, no se crea notificación")
        except Exception as e:
            print(f"❌ Error creating notification: {str(e)}")
            import traceback
            traceback.print_exc()
        
        return mision

    def get_mission_detail(self, mission_id: int, user: Usuario) -> Dict[str, Any]:
        """
        Obtiene el detalle completo de una misión, incluyendo datos relacionados
        y las acciones que el usuario actual puede realizar.
        """
        mision = self.db.query(Mision).options(
            joinedload(Mision.estado_flujo),
            joinedload(Mision.items_viaticos),
            joinedload(Mision.items_viaticos_completos),  # <-- Agregado
            joinedload(Mision.items_transporte),
            joinedload(Mision.partidas_presupuestarias),
            joinedload(Mision.historial_flujo).joinedload(HistorialFlujo.usuario_accion).joinedload(Usuario.rol),
            joinedload(Mision.adjuntos),
            joinedload(Mision.subsanaciones),
            joinedload(Mision.items_misiones_exterior),
        ).filter(Mision.id_mision == mission_id).first()

        if not mision:
            raise MissionException("Misión no encontrada", status_code=status.HTTP_404_NOT_FOUND)

        print("DEBUG OBSERVACION (service):", getattr(mision, 'observacion', 'NO ATRIBUTO'))

        beneficiary_info = self._get_rrhh_data(mision.beneficiario_personal_id)
        preparer_user = self.db.query(Usuario).filter(Usuario.id_usuario == mision.id_usuario_prepara).first()
        preparer_info = self._get_rrhh_data(preparer_user.personal_id_rrhh) if preparer_user else None

        available_actions = self._get_available_actions(mision, user)
        can_edit = mision.estado_flujo.nombre_estado == "PENDIENTE_REVISION_TESORERIA" and mision.id_usuario_prepara == user.id_usuario
        can_delete = can_edit and len(mision.historial_flujo) <= 1

        # Serializar viaticos completos (siempre presente)
        viaticos_completos = []
        for item in getattr(mision, 'items_viaticos_completos', []) or []:
            viaticos_completos.append({
                'id_item_viatico_completo': item.id_item_viatico_completo,
                'id_mision': item.id_mision,
                'cantidad_dias': item.cantidad_dias,
                'monto_por_dia': float(item.monto_por_dia)
            })
        # Siempre incluir el campo aunque esté vacío
        mission_dict = Mision.model_validate(mision).model_dump()
        mission_dict['viaticosCompletos'] = viaticos_completos

        return {
            "mission": mission_dict,
            "beneficiary": beneficiary_info,
            "preparer": preparer_info,
            "available_actions": available_actions,
            "can_edit": can_edit,
            "can_delete": can_delete
        }

    def get_missions(self, user: Usuario, **filters) -> Dict[str, Any]:
        """
        Obtiene una lista paginada de misiones, aplicando filtros y permisos
        basados en el rol del usuario.
        """
        query = self.db.query(Mision).options(joinedload(Mision.estado_flujo))

        # Lógica de filtrado por rol
        if user.rol.nombre_rol == 'Jefe Inmediato':
            # 1. Obtener la cédula del jefe actual
            jefe_cedula = self.db.query(text("cedula")).from_statement(
                text("SELECT cedula FROM aitsa_rrhh.nompersonal WHERE personal_id = :pid")
            ).params(pid=user.personal_id_rrhh).scalar()

            if jefe_cedula:
                # 2. Obtener los IDs de los departamentos donde es jefe inmediato (orden_aprobador = 1)
                deptos_managed_query = self.db.query(text("IdDepartamento")).from_statement(
                    text(
                        """
                        SELECT d.IdDepartamento
                        FROM aitsa_rrhh.departamento d
                        JOIN aitsa_rrhh.departamento_aprobadores_maestros dam
                          ON dam.id_departamento = d.IdDepartamento
                         AND dam.orden_aprobador = 1
                        WHERE dam.cedula_aprobador = :jefe_cedula
                        """
                    )
                ).params(jefe_cedula=jefe_cedula)
                deptos_managed_ids = [row[0] for row in deptos_managed_query.all()]

                if deptos_managed_ids:
                    # 3. Obtener los IDs de todos los empleados en esos departamentos
                    employees_in_depts_query = self.db.query(text("personal_id")).from_statement(
                        text("SELECT personal_id FROM aitsa_rrhh.nompersonal WHERE IdDepartamento IN :depto_ids")
                    ).params(depto_ids=tuple(deptos_managed_ids))
                    employee_ids = [row[0] for row in employees_in_depts_query.all()]
                    
                    # 4. Filtrar misiones por los empleados gestionados
                    if employee_ids:
                        query = query.filter(Mision.beneficiario_personal_id.in_(employee_ids))
                    else: # Si no hay empleados, no mostrar nada
                        return {"items": [], "total": 0, "page": 1, "size": filters.get('limit', 100), "pages": 0}
        
        elif user.rol.nombre_rol == 'Solicitante':
            # El solicitante solo ve sus propias misiones
            query = query.filter(Mision.beneficiario_personal_id == user.personal_id_rrhh)
        
        # Para otros roles (Admin, Finanzas, etc.), no se aplica filtro de personal, ven todo.

        # Aplicar filtros adicionales de la solicitud
        if filters.get('estado_id'):
            query = query.filter(Mision.id_estado_flujo == filters['estado_id'])
        if filters.get('tipo_mision'):
            query = query.filter(Mision.tipo_mision == filters['tipo_mision'])
        if filters.get('fecha_desde'):
            # Convertir date a datetime para comparación correcta
            fecha_desde_dt = datetime.combine(filters['fecha_desde'], datetime.min.time())
            query = query.filter(Mision.fecha_salida >= fecha_desde_dt)
        if filters.get('fecha_hasta'):
            # Convertir date a datetime para comparación correcta
            fecha_hasta_dt = datetime.combine(filters['fecha_hasta'], datetime.max.time())
            query = query.filter(Mision.fecha_salida <= fecha_hasta_dt)  # ✅ CORREGIDO: usar fecha_salida en lugar de fecha_retorno

        skip = filters.get('skip', 0)
        limit = filters.get('limit', 100)

        total = query.count()
        items = query.order_by(desc(Mision.created_at)).offset(skip).limit(limit).all()

        return {
            "items": items,
            "total": total,
            "page": (skip // limit) + 1,
            "size": limit,
            "pages": (total + limit - 1) // limit if limit > 0 else 0
        }

    def process_workflow_action(self, mission_id: int, user: Usuario, action: TipoAccion,
                                comentarios: str = None, datos_adicionales: Dict = None) -> Mision:
        mision = self.db.query(Mision).filter(Mision.id_mision == mission_id).first()
        if not mision:
            raise MissionException("Misión no encontrada", status_code=status.HTTP_404_NOT_FOUND)

        transicion = self._find_valid_transition(mision.id_estado_flujo, user.id_rol, action)
        if not transicion:
            raise WorkflowException(f"La acción '{action.value}' no es permitida para su rol en el estado actual.")

        estado_anterior_id = mision.id_estado_flujo
        mision.id_estado_flujo = transicion.id_estado_destino

        if transicion.estado_destino.nombre_estado == "PENDIENTE_ASIGNACION_PRESUPUESTO":
            self._generate_gestion_cobro(mision, user.id_usuario)

        self._create_history_record(
            mision_id=mission_id, user_id=user.id_usuario, new_state_id=transicion.id_estado_destino,
            old_state_id=estado_anterior_id, action_type=action, comments=comentarios, extra_data=datos_adicionales
        )

        self.db.commit()
        self.db.refresh(mision)
        return mision

    def assign_budget_items(self, mission_id: int, data: PresupuestoAssignRequest, user: Usuario) -> Mision:
        mision = self.db.query(Mision).filter(Mision.id_mision == mission_id).first()
        if not mision:
            raise MissionException("Misión no encontrada", status_code=status.HTTP_404_NOT_FOUND)

        if mision.estado_flujo.nombre_estado != "PENDIENTE_ASIGNACION_PRESUPUESTO":
            raise WorkflowException("La asignación de presupuesto solo es válida en el estado correspondiente.")

        self.db.query(MisionPartidaPresupuestaria).filter(MisionPartidaPresupuestaria.id_mision == mission_id).delete()
        self._process_partidas_items(mission_id, data.partidas)

        return self.process_workflow_action(
            mission_id=mission_id, user=user, action=TipoAccion.APROBAR, comentarios=data.comentarios
        )

    # --- Métodos Privados Auxiliares ---

    def _create_history_record(self, mision_id: int, user_id: Optional[int], new_state_id: int, action_type: TipoAccion,
                               old_state_id: Optional[int] = None, comments: Optional[str] = None,
                               extra_data: Optional[Dict] = None):
        # Permitir NULL en id_usuario_accion (por ejemplo, cuando el actor es empleado externo al módulo financiero)
        historial = HistorialFlujo(
            id_mision=mision_id,
            id_usuario_accion=user_id,
            id_estado_anterior=old_state_id,
            id_estado_nuevo=new_state_id,
            tipo_accion=action_type,
            comentarios=comments,
            observacion=comments,
            datos_adicionales=extra_data
        )
        self.db.add(historial)

    def _process_viaticos_items(self, mission_id: int, items: List[ItemViatico]) -> Decimal:
        total = Decimal("0.00")
        if items:
            for item_data in items:
                item = ItemViatico(id_mision=mission_id, **item_data.model_dump())
                total += (item.monto_desayuno + item.monto_almuerzo + item.monto_cena + item.monto_hospedaje)
                self.db.add(item)
        return total

    def _process_transporte_items(self, mission_id: int, items: List[ItemTransporte]) -> Decimal:
        total = Decimal("0.00")
        if items:
            for item_data in items:
                item = ItemTransporte(id_mision=mission_id, **item_data.model_dump())
                total += item.monto
                self.db.add(item)
        return total

    def _process_partidas_items(self, mission_id: int, items: List[MisionPartidaPresupuestaria]):
        if items:
            for partida_data in items:
                partida = MisionPartidaPresupuestaria(id_mision=mission_id, **partida_data.model_dump())
                self.db.add(partida)

    def _find_valid_transition(self, current_state_id: int, user_role_id: int, action: TipoAccion) -> Optional[TransicionFlujo]:
        return self.db.query(TransicionFlujo).options(joinedload(TransicionFlujo.estado_destino)).filter(
            TransicionFlujo.id_estado_origen == current_state_id,
            TransicionFlujo.id_rol_autorizado == user_role_id,
            TransicionFlujo.tipo_accion == action,
            TransicionFlujo.es_activa == True
        ).first()

    def _get_available_actions(self, mision: Mision, user: Usuario) -> List[str]:
        transiciones = self.db.query(TransicionFlujo).filter(
            TransicionFlujo.id_estado_origen == mision.id_estado_flujo,
            TransicionFlujo.id_rol_autorizado == user.id_rol,
            TransicionFlujo.es_activa == True
        ).all()
        return [t.tipo_accion.value for t in transiciones]

    def _validate_mission_dates(self, fecha_salida: datetime, fecha_retorno: datetime):
        if fecha_retorno < fecha_salida:
            raise ValidationException("La fecha de retorno no puede ser anterior a la fecha de salida.")

    def _get_config_value(self, clave: str, default: str) -> str:
        config = self.db.query(ConfiguracionSistema).filter(ConfiguracionSistema.clave == clave).first()
        return config.valor if config else default

    def _generate_gestion_cobro(self, mision: Mision, usuario_id: int):
        if mision.tipo_mision == TipoMision.VIATICOS and not mision.numero_gestion_cobro:
            numero_gestion = f"GC-{mision.id_mision:06d}-{datetime.now().year}"
            gestion = GestionCobro(
                id_mision=mision.id_mision, numero_gestion=numero_gestion, id_usuario_genero=usuario_id,
                monto_autorizado=mision.monto_total_calculado, estado=EstadoGestion.PENDIENTE
            )
            self.db.add(gestion)
            mision.numero_gestion_cobro = numero_gestion

    def _get_rrhh_data(self, personal_id: int) -> Optional[Dict[str, Any]]:
        if not personal_id:
            return None
        try:
            sql_query = text("""
                SELECT
                    p.personal_id, p.apenom, p.ficha, p.cedula,
                    p.codcargo, p.nomposicion_id, f.descripcion_funcion,
                    p.codnivel1, p.codnivel2
                FROM aitsa_rrhh.nompersonal AS p
                LEFT JOIN aitsa_rrhh.nomfuncion AS f ON p.nomfuncion_id = f.nomfuncion_id
                WHERE p.personal_id = :personal_id AND p.estado != 'De Baja'
            """)
            result = self.db.execute(sql_query, {"personal_id": personal_id})
            row = result.mappings().first()
            return dict(row) if row else None
        except Exception as e:
            print(f"Error crítico al consultar la base de datos de RRHH: {e}")
            raise BusinessException("No se pudo obtener la información del empleado desde RRHH.")

    def _get_jefe_inmediato_personal_id(self, beneficiary_personal_id: int) -> Optional[int]:
        """
        Obtiene el personal_id del jefe inmediato del beneficiario
        
        Args:
            beneficiary_personal_id: personal_id del beneficiario/solicitante
            
        Returns:
            int: personal_id del jefe inmediato o None si no se encuentra
        """
        try:
            if not self.db_rrhh:
                print("No hay conexión a la base de datos RRHH")
                return None
                
            # Obtener el departamento del empleado
            dept_query = text("""
                SELECT IdDepartamento 
                FROM nompersonal 
                WHERE personal_id = :personal_id
            """)
            
            dept_result = self.db_rrhh.execute(dept_query, {"personal_id": beneficiary_personal_id})
            dept_row = dept_result.fetchone()
            
            if not dept_row or not dept_row[0]:
                print(f"No se encontró departamento para personal_id {beneficiary_personal_id}")
                return None
            
            departamento_id = dept_row[0]
            print(f"Departamento encontrado: {departamento_id}")
            
            # Obtener el jefe inmediato del departamento (orden_aprobador = 1)
            jefe_query = text("""
                SELECT np.personal_id, np.apenom
                FROM nompersonal np
                JOIN departamento_aprobadores_maestros dam ON dam.cedula_aprobador = np.cedula
                WHERE dam.id_departamento = :departamento_id
                  AND dam.orden_aprobador = 1
                  AND np.estado != 'De Baja'
            """)
            
            jefe_result = self.db_rrhh.execute(jefe_query, {"departamento_id": departamento_id})
            jefe_row = jefe_result.fetchone()
            
            if jefe_row and jefe_row[0]:
                print(f"Jefe inmediato encontrado: {jefe_row[1]} (personal_id: {jefe_row[0]})")
                return jefe_row[0]
            
            print(f"No se encontró jefe inmediato para departamento {departamento_id}")
            return None
            
        except Exception as e:
            print(f"Error obteniendo jefe inmediato: {str(e)}")
            return None
