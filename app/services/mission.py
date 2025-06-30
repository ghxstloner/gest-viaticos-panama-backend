from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import text, and_, or_, func, extract
from decimal import Decimal
from datetime import datetime, date, timedelta
from ..models.mission import (
    Mision, EstadoFlujo, HistorialFlujo, TransicionFlujo, 
    GestionCobro, Subsanacion, ItemViatico, ItemTransporte, Adjunto
)
from ..models.user import Usuario
from ..models.configuration import ConfiguracionSistema
from ..models.enums import TipoMision, TipoAccion, EstadoGestion, EstadoSubsanacion
from ..schemas.mission import (
    MisionCreate, MisionUpdate, MisionApprovalRequest, 
    MisionRejectionRequest, WebhookMisionAprobada, MisionDetail,
    MisionListResponse, SubsanacionResponse, GestionCobroCreate
)
from fastapi import HTTPException, status


class MissionService:
    def __init__(self, db: Session):
        self.db = db

    def create_mission(self, mission_data: MisionCreate, user_id: int) -> Mision:
        """Crear una nueva misión/solicitud"""
        try:
            # Verificar si el usuario puede crear solicitudes
            user = self.db.query(Usuario).filter(Usuario.id_usuario == user_id).first()
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Usuario no encontrado"
                )

            # Obtener el estado inicial
            initial_state = self.db.query(EstadoFlujo).filter(
                EstadoFlujo.nombre_estado == "PENDIENTE_REVISION_TESORERIA"
            ).first()

            if not initial_state:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Estado inicial no configurado en el sistema"
                )

            # Validar fechas
            if mission_data.fecha_retorno < mission_data.fecha_salida:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="La fecha de retorno no puede ser anterior a la fecha de salida"
                )

            # Verificar si requiere refrendo CGR según el monto
            monto_refrendo = self._get_config_value("MONTO_REFRENDO_CGR", 1000.00)
            
            # Crear la misión
            mission = Mision(
                solicitud_caso_id_rrhh=mission_data.solicitud_caso_id_rrhh,
                tipo_mision=mission_data.tipo_mision,
                beneficiario_personal_id=mission_data.beneficiario_personal_id,
                objetivo_mision=mission_data.objetivo_mision,
                destino_mision=mission_data.destino_mision,
                fecha_salida=mission_data.fecha_salida,
                fecha_retorno=mission_data.fecha_retorno,
                monto_total_calculado=Decimal('0.00'),
                id_estado_flujo=initial_state.id_estado_flujo,
                requiere_refrendo_cgr=False,
                observaciones_especiales=mission_data.observaciones_especiales
            )

            # Calcular fecha límite de presentación para viáticos
            if mission_data.tipo_mision == TipoMision.VIATICOS:
                dias_limite = int(self._get_config_value("DIAS_LIMITE_PRESENTACION", 10))
                mission.fecha_limite_presentacion = mission.fecha_retorno.date() + timedelta(days=dias_limite)

            self.db.add(mission)
            self.db.flush()

            # Agregar items de viáticos si los hay
            monto_total = Decimal('0.00')
            if mission_data.items_viaticos:
                for item_data in mission_data.items_viaticos:
                    item = ItemViatico(
                        id_mision=mission.id_mision,
                        fecha=item_data.fecha,
                        monto_desayuno=item_data.monto_desayuno,
                        monto_almuerzo=item_data.monto_almuerzo,
                        monto_cena=item_data.monto_cena,
                        monto_hospedaje=item_data.monto_hospedaje,
                        observaciones=item_data.observaciones
                    )
                    self.db.add(item)
                    monto_total += (
                        item.monto_desayuno + 
                        item.monto_almuerzo + 
                        item.monto_cena + 
                        item.monto_hospedaje
                    )

            # Agregar items de transporte si los hay
            if mission_data.items_transporte:
                for item_data in mission_data.items_transporte:
                    item = ItemTransporte(
                        id_mision=mission.id_mision,
                        fecha=item_data.fecha,
                        tipo=item_data.tipo,
                        origen=item_data.origen,
                        destino=item_data.destino,
                        monto=item_data.monto,
                        observaciones=item_data.observaciones
                    )
                    self.db.add(item)
                    monto_total += item.monto

            # Actualizar monto total y verificar si requiere refrendo
            mission.monto_total_calculado = monto_total
            mission.requiere_refrendo_cgr = monto_total >= monto_refrendo

            # Crear registro en el historial
            history = HistorialFlujo(
                id_mision=mission.id_mision,
                id_usuario_accion=user_id,
                id_estado_anterior=None,
                id_estado_nuevo=initial_state.id_estado_flujo,
                tipo_accion=TipoAccion.CREAR,
                comentarios=f"Solicitud creada por {user.login_username}",
                datos_adicionales={
                    "tipo_mision": mission_data.tipo_mision.value,
                    "monto_calculado": str(monto_total),
                    "requiere_refrendo": mission.requiere_refrendo_cgr
                }
            )
            self.db.add(history)

            self.db.commit()
            self.db.refresh(mission)
            return mission

        except Exception as e:
            self.db.rollback()
            raise e

    def get_missions(
        self, 
        user: Usuario,
        skip: int = 0, 
        limit: int = 100,
        estado_id: Optional[int] = None,
        tipo_mision: Optional[TipoMision] = None,
        fecha_desde: Optional[date] = None,
        fecha_hasta: Optional[date] = None
    ) -> MisionListResponse:
        """Obtener lista de misiones según el rol del usuario"""
        query = self.db.query(Mision).options(
            joinedload(Mision.estado_flujo),
            joinedload(Mision.items_viaticos),
            joinedload(Mision.items_transporte)
        )

        # Filtrar según el rol del usuario
        if user.rol.nombre_rol == "Solicitante":
            # Los solicitantes solo ven sus propias solicitudes
            query = query.filter(Mision.beneficiario_personal_id == user.personal_id_rrhh)
        elif user.rol.nombre_rol == "Jefe Inmediato":
            # Los jefes ven las solicitudes de su personal
            personal_ids = self._get_subordinates_ids(user.personal_id_rrhh)
            query = query.filter(Mision.beneficiario_personal_id.in_(personal_ids))
        elif user.rol.nombre_rol in ["Analista Tesorería", "Analista Presupuesto", "Analista Contabilidad"]:
            # Los analistas ven las solicitudes en sus estados correspondientes
            estados = self._get_estados_for_role(user.rol.nombre_rol)
            query = query.filter(Mision.id_estado_flujo.in_([e.id_estado_flujo for e in estados]))
        # Los directores y administradores ven todo

        # Aplicar filtros adicionales
        if estado_id:
            query = query.filter(Mision.id_estado_flujo == estado_id)
        if tipo_mision:
            query = query.filter(Mision.tipo_mision == tipo_mision)
        if fecha_desde:
            query = query.filter(Mision.fecha_salida >= fecha_desde)
        if fecha_hasta:
            query = query.filter(Mision.fecha_salida <= fecha_hasta)

        # Contar total
        total = query.count()

        # Aplicar paginación
        missions = query.order_by(Mision.created_at.desc()).offset(skip).limit(limit).all()

        return MisionListResponse(
            total=total,
            missions=missions,
            skip=skip,
            limit=limit
        )

    def get_mission_detail(self, mission_id: int, user: Usuario) -> MisionDetail:
        """Obtener detalle completo de una misión"""
        mission = self.db.query(Mision).options(
            joinedload(Mision.estado_flujo),
            joinedload(Mision.items_viaticos),
            joinedload(Mision.items_transporte),
            joinedload(Mision.adjuntos),
            joinedload(Mision.historial_flujo).joinedload(HistorialFlujo.usuario_accion),
            joinedload(Mision.gestiones_cobro),
            joinedload(Mision.subsanaciones)
        ).filter(Mision.id_mision == mission_id).first()

        if not mission:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Misión no encontrada"
            )

        # Verificar permisos de acceso
        if not self._can_access_mission(mission, user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tiene permisos para ver esta misión"
            )

        # Obtener datos del beneficiario
        beneficiary_data = self._get_employee_data(mission.beneficiario_personal_id)

        # Obtener acciones disponibles
        available_actions = self._get_available_actions(mission, user)

        return MisionDetail(
            mission=mission,
            beneficiary=beneficiary_data,
            available_actions=available_actions,
            can_edit=self._can_edit_mission(mission, user),
            can_delete=self._can_delete_mission(mission, user)
        )

    def approve_mission(self, mission_id: int, user_id: int, approval_data: MisionApprovalRequest) -> Mision:
        """Aprobar una misión y avanzar al siguiente estado"""
        try:
            # Obtener misión
            mission = self.db.query(Mision).filter(Mision.id_mision == mission_id).first()
            if not mission:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Misión no encontrada"
                )

            # Obtener usuario
            user = self.db.query(Usuario).filter(Usuario.id_usuario == user_id).first()
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Usuario no encontrado"
                )

            # Validar transición
            transition = self._get_valid_transition(
                mission.id_estado_flujo, 
                user.id_rol, 
                TipoAccion.APROBAR
            )
            if not transition:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="No tiene autorización para aprobar en este estado"
                )

            # Guardar estado anterior
            previous_state_id = mission.id_estado_flujo

            # Actualizar misión
            mission.id_estado_flujo = transition.id_estado_destino
            mission.updated_at = datetime.utcnow()
            
            if approval_data.monto_aprobado:
                mission.monto_aprobado = approval_data.monto_aprobado

            # Crear registro en el historial
            history = HistorialFlujo(
                id_mision=mission_id,
                id_usuario_accion=user_id,
                id_estado_anterior=previous_state_id,
                id_estado_nuevo=transition.id_estado_destino,
                tipo_accion=TipoAccion.APROBAR,
                comentarios=approval_data.comentarios,
                datos_adicionales={
                    "usuario_rol": user.rol.nombre_rol,
                    "estado_anterior": mission.estado_flujo.nombre_estado,
                    "estado_nuevo": transition.estado_destino.nombre_estado,
                    "monto_aprobado": str(approval_data.monto_aprobado) if approval_data.monto_aprobado else None
                }
            )
            self.db.add(history)

            # Ejecutar lógica especial según el estado
            self._execute_state_logic(mission, user, transition.estado_destino)

            self.db.commit()
            self.db.refresh(mission)
            return mission

        except Exception as e:
            self.db.rollback()
            raise e

    def reject_mission(self, mission_id: int, user_id: int, rejection_data: MisionRejectionRequest) -> Mision:
        """Rechazar una misión y crear subsanación"""
        try:
            mission = self.db.query(Mision).filter(Mision.id_mision == mission_id).first()
            if not mission:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Misión no encontrada"
                )

            user = self.db.query(Usuario).filter(Usuario.id_usuario == user_id).first()
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Usuario no encontrado"
                )

            # Validar que puede rechazar
            transition = self._get_valid_transition(
                mission.id_estado_flujo,
                user.id_rol,
                TipoAccion.DEVOLVER
            )
            if not transition:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="No tiene autorización para devolver en este estado"
                )

            # Guardar estado anterior
            previous_state_id = mission.id_estado_flujo

            # Actualizar misión
            mission.id_estado_flujo = transition.id_estado_destino
            mission.updated_at = datetime.utcnow()

            # Crear subsanación
            responsible_user_id = self._get_responsible_for_subsanation(mission, previous_state_id)
            subsanation = Subsanacion(
                id_mision=mission_id,
                id_usuario_solicita=user_id,
                id_usuario_responsable=responsible_user_id,
                motivo=rejection_data.motivo,
                fecha_limite=date.today() + timedelta(days=5)
            )
            self.db.add(subsanation)

            # Crear registro en el historial
            history = HistorialFlujo(
                id_mision=mission_id,
                id_usuario_accion=user_id,
                id_estado_anterior=previous_state_id,
                id_estado_nuevo=transition.id_estado_destino,
                tipo_accion=TipoAccion.DEVOLVER,
                comentarios=rejection_data.motivo,
                datos_adicionales={
                    "usuario_rol": user.rol.nombre_rol,
                    "subsanacion_creada": True,
                    "responsable_subsanacion": responsible_user_id
                }
            )
            self.db.add(history)

            self.db.commit()
            self.db.refresh(mission)
            return mission

        except Exception as e:
            self.db.rollback()
            raise e

    def complete_subsanation(self, subsanation_id: int, user_id: int, response: str) -> SubsanacionResponse:
        """Completar una subsanación"""
        try:
            subsanation = self.db.query(Subsanacion).filter(
                Subsanacion.id_subsanacion == subsanation_id
            ).first()
            
            if not subsanation:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Subsanación no encontrada"
                )

            if subsanation.id_usuario_responsable != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="No tiene autorización para responder esta subsanación"
                )

            if subsanation.estado != EstadoSubsanacion.PENDIENTE:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Esta subsanación ya fue completada"
                )

            # Actualizar subsanación
            subsanation.respuesta = response
            subsanation.fecha_respuesta = datetime.utcnow()
            subsanation.estado = EstadoSubsanacion.COMPLETADA

            # Retornar la misión al estado anterior
            mission = subsanation.mision
            
            # Buscar el estado anterior en el historial
            last_approval = self.db.query(HistorialFlujo).filter(
                and_(
                    HistorialFlujo.id_mision == mission.id_mision,
                    HistorialFlujo.tipo_accion == TipoAccion.APROBAR
                )
            ).order_by(HistorialFlujo.fecha_accion.desc()).first()

            if last_approval:
                mission.id_estado_flujo = last_approval.id_estado_anterior or 1
            else:
                # Si no hay aprobaciones previas, volver al estado inicial
                initial_state = self.db.query(EstadoFlujo).filter(
                    EstadoFlujo.nombre_estado == "PENDIENTE_REVISION_TESORERIA"
                ).first()
                mission.id_estado_flujo = initial_state.id_estado_flujo

            # Crear registro en el historial
            history = HistorialFlujo(
                id_mision=mission.id_mision,
                id_usuario_accion=user_id,
                id_estado_anterior=mission.id_estado_flujo,
                id_estado_nuevo=mission.id_estado_flujo,
                tipo_accion=TipoAccion.SUBSANAR,
                comentarios=f"Subsanación completada: {response[:100]}...",
                datos_adicionales={
                    "subsanacion_id": subsanation_id,
                    "fecha_limite": str(subsanation.fecha_limite)
                }
            )
            self.db.add(history)

            self.db.commit()
            self.db.refresh(subsanation)
            
            return SubsanacionResponse(
                subsanacion=subsanation,
                mission_status=mission.estado_flujo.nombre_estado
            )

        except Exception as e:
            self.db.rollback()
            raise e

    def generate_gestion_cobro(self, mission_id: int, user_id: int, data: GestionCobroCreate) -> GestionCobro:
        """Generar gestión de cobro para una misión"""
        try:
            mission = self.db.query(Mision).filter(Mision.id_mision == mission_id).first()
            if not mission:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Misión no encontrada"
                )

            # Verificar que no exista ya una gestión de cobro
            existing = self.db.query(GestionCobro).filter(
                GestionCobro.id_mision == mission_id
            ).first()
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Ya existe una gestión de cobro para esta misión"
                )

            # Generar número único
            numero_gestion = f"GC-{datetime.now().year}-{mission_id:06d}"

            # Crear gestión de cobro
            gestion = GestionCobro(
                id_mision=mission_id,
                numero_gestion=numero_gestion,
                id_usuario_genero=user_id,
                monto_autorizado=data.monto_autorizado or mission.monto_total_calculado,
                codigo_presupuestario=data.codigo_presupuestario,
                observaciones=data.observaciones,
                estado=EstadoGestion.PENDIENTE
            )
            self.db.add(gestion)

            # Actualizar misión
            mission.numero_gestion_cobro = numero_gestion

            self.db.commit()
            self.db.refresh(gestion)
            return gestion

        except Exception as e:
            self.db.rollback()
            raise e

    def calculate_viaticos(self, fecha_salida: date, fecha_retorno: date, destino: str) -> Dict[str, Any]:
        """Calcular montos de viáticos según tarifas configuradas"""
        # Obtener tarifas del sistema
        tarifa_desayuno = float(self._get_config_value("TARIFA_DESAYUNO", 10.00))
        tarifa_almuerzo = float(self._get_config_value("TARIFA_ALMUERZO", 15.00))
        tarifa_cena = float(self._get_config_value("TARIFA_CENA", 15.00))
        tarifa_hospedaje = float(self._get_config_value("TARIFA_HOSPEDAJE_LOCAL", 80.00))
        
        # Calcular días
        dias = (fecha_retorno - fecha_salida).days + 1
        
        # Crear detalle por día
        items = []
        current_date = fecha_salida
        monto_total = Decimal('0.00')
        
        while current_date <= fecha_retorno:
            item = {
                "fecha": current_date,
                "monto_desayuno": Decimal(str(tarifa_desayuno)),
                "monto_almuerzo": Decimal(str(tarifa_almuerzo)),
                "monto_cena": Decimal(str(tarifa_cena)),
                "monto_hospedaje": Decimal(str(tarifa_hospedaje)) if current_date < fecha_retorno else Decimal('0.00')
            }
            
            dia_total = sum(item.values())
            monto_total += dia_total
            items.append(item)
            
            current_date += timedelta(days=1)
        
        return {
            "dias": dias,
            "items": items,
            "monto_total": monto_total,
            "tarifas": {
                "desayuno": tarifa_desayuno,
                "almuerzo": tarifa_almuerzo,
                "cena": tarifa_cena,
                "hospedaje": tarifa_hospedaje
            }
        }

    # Métodos auxiliares privados
    def _get_config_value(self, key: str, default: Any) -> Any:
        """Obtener valor de configuración del sistema"""
        config = self.db.query(ConfiguracionSistema).filter(
            ConfiguracionSistema.clave == key
        ).first()
        
        if not config:
            return default
            
        # Convertir según tipo
        if config.tipo_dato == "NUMBER":
            return float(config.valor)
        elif config.tipo_dato == "BOOLEAN":
            return config.valor.lower() in ['true', '1', 'yes']
        return config.valor

    def _get_valid_transition(self, current_state_id: int, role_id: int, action: TipoAccion) -> Optional[TransicionFlujo]:
        """Obtener transición válida"""
        return self.db.query(TransicionFlujo).filter(
            and_(
                TransicionFlujo.id_estado_origen == current_state_id,
                TransicionFlujo.id_rol_autorizado == role_id,
                TransicionFlujo.tipo_accion == action,
                TransicionFlujo.es_activa == True
            )
        ).first()

    def _execute_state_logic(self, mission: Mision, user: Usuario, new_state: EstadoFlujo):
        """Ejecutar lógica especial según el nuevo estado"""
        if new_state.nombre_estado == "PENDIENTE_ASIGNACION_PRESUPUESTO":
            # Generar gestión de cobro automáticamente
            if not mission.numero_gestion_cobro:
                numero_gestion = f"GC-{datetime.now().year}-{mission.id_mision:06d}"
                gestion = GestionCobro(
                    id_mision=mission.id_mision,
                    numero_gestion=numero_gestion,
                    id_usuario_genero=user.id_usuario,
                    monto_autorizado=mission.monto_aprobado or mission.monto_total_calculado,
                    estado=EstadoGestion.EN_PROCESO
                )
                self.db.add(gestion)
                mission.numero_gestion_cobro = numero_gestion
                
        elif new_state.nombre_estado == "APROBADO_PARA_PAGO":
            # Actualizar gestión de cobro a completada
            if mission.gestiones_cobro:
                for gestion in mission.gestiones_cobro:
                    gestion.estado = EstadoGestion.COMPLETADA
                    
            # TODO: Enviar notificación para pago

    def _can_access_mission(self, mission: Mision, user: Usuario) -> bool:
        """Verificar si el usuario puede acceder a la misión"""
        # Administradores pueden ver todo
        if user.rol.nombre_rol == "Administrador Sistema":
            return True
            
        # Solicitante puede ver sus propias misiones
        if mission.beneficiario_personal_id == user.personal_id_rrhh:
            return True
            
        # Otros roles según el estado de la misión
        allowed_states = self._get_estados_for_role(user.rol.nombre_rol)
        if mission.estado_flujo in allowed_states:
            return True
            
        return False

    def _can_edit_mission(self, mission: Mision, user: Usuario) -> bool:
        """Verificar si el usuario puede editar la misión"""
        # Solo se puede editar en estado inicial y por el creador
        if mission.estado_flujo.nombre_estado != "PENDIENTE_REVISION_TESORERIA":
            return False
            
        return mission.beneficiario_personal_id == user.personal_id_rrhh

    def _can_delete_mission(self, mission: Mision, user: Usuario) -> bool:
        """Verificar si el usuario puede eliminar la misión"""
        # Similar a editar pero más restrictivo
        return self._can_edit_mission(mission, user) and not mission.historial_flujo

    def _get_estados_for_role(self, role_name: str) -> List[EstadoFlujo]:
        """Obtener estados que puede ver cada rol"""
        estados = []
        
        if role_name == "Analista Tesorería":
            estados = self.db.query(EstadoFlujo).filter(
                EstadoFlujo.nombre_estado.in_([
                    "PENDIENTE_REVISION_TESORERIA",
                    "APROBADO_PARA_PAGO"
                ])
            ).all()
        elif role_name == "Analista Presupuesto":
            estados = self.db.query(EstadoFlujo).filter(
                EstadoFlujo.nombre_estado == "PENDIENTE_ASIGNACION_PRESUPUESTO"
            ).all()
        elif role_name == "Analista Contabilidad":
            estados = self.db.query(EstadoFlujo).filter(
                EstadoFlujo.nombre_estado == "PENDIENTE_CONTABILIDAD"
            ).all()
        elif role_name == "Director Finanzas":
            estados = self.db.query(EstadoFlujo).filter(
                EstadoFlujo.nombre_estado == "PENDIENTE_APROBACION_FINANZAS"
            ).all()
        elif role_name == "Fiscalizador CGR":
            estados = self.db.query(EstadoFlujo).filter(
                EstadoFlujo.nombre_estado == "PENDIENTE_REFRENDO_CGR"
            ).all()
        else:
            # Otros roles ven todos los estados
            estados = self.db.query(EstadoFlujo).all()
            
        return estados

    def _get_subordinates_ids(self, manager_id: int) -> List[int]:
        """Obtener IDs de subordinados de un jefe"""
        # Esta función debería consultar la estructura organizacional en RRHH
        # Por ahora retorna una lista vacía
        # TODO: Implementar consulta real a RRHH
        return []

    def _get_employee_data(self, personal_id: int) -> Dict[str, Any]:
        """Obtener datos del empleado desde RRHH"""
        try:
            result = self.db.execute(text("""
                SELECT 
                    personal_id,
                    cedula,
                    apenom,
                    nombres,
                    apellidos,
                    email,
                    ficha,
                    cargo
                FROM aitsa_rrhh.nompersonal 
                WHERE personal_id = :personal_id
            """), {"personal_id": personal_id})
            
            row = result.fetchone()
            if row:
                return dict(row._mapping)
            return {}
        except Exception as e:
            print(f"Error obteniendo datos del empleado: {e}")
            return {}

    def _get_available_actions(self, mission: Mision, user: Usuario) -> List[str]:
        """Obtener acciones disponibles para el usuario en la misión actual"""
        actions = []
        
        # Buscar transiciones válidas
        transitions = self.db.query(TransicionFlujo).filter(
            and_(
                TransicionFlujo.id_estado_origen == mission.id_estado_flujo,
                TransicionFlujo.id_rol_autorizado == user.id_rol,
                TransicionFlujo.es_activa == True
            )
        ).all()
        
        for trans in transitions:
            actions.append(trans.tipo_accion.value)
            
        return actions

    def _get_responsible_for_subsanation(self, mission: Mision, previous_state_id: int) -> int:
        """Determinar el usuario responsable de atender la subsanación"""
        # Buscar quién aprobó en el estado anterior
        last_approval = self.db.query(HistorialFlujo).filter(
            and_(
                HistorialFlujo.id_mision == mission.id_mision,
                HistorialFlujo.id_estado_nuevo == previous_state_id,
                HistorialFlujo.tipo_accion == TipoAccion.APROBAR
            )
        ).order_by(HistorialFlujo.fecha_accion.desc()).first()
        
        if last_approval:
            return last_approval.id_usuario_accion
            
        # Si no hay aprobación previa, asignar al creador
        first_record = self.db.query(HistorialFlujo).filter(
            and_(
                HistorialFlujo.id_mision == mission.id_mision,
                HistorialFlujo.tipo_accion == TipoAccion.CREAR
            )
        ).first()
        
        if first_record:
            return first_record.id_usuario_accion
            
        return 1  # Usuario por defecto

    def process_approved_mission_webhook(self, webhook_data: WebhookMisionAprobada) -> Mision:
        """Process webhook for approved mission from RRHH"""
        try:
            # Get request data from RRHH
            rrhh_request = self.get_rrhh_request_data(webhook_data.solicitud_caso_id)
            if not rrhh_request:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"RRHH request {webhook_data.solicitud_caso_id} not found"
                )

            # Validate request type (must be mission type 10)
            if rrhh_request["id_tipo_solicitud"] != 10:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Request is not of mission type"
                )

            # Validate status (must be approved by supervisor - status 2)
            if rrhh_request["id_solicitudes_casos_status"] != 2:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Request is not in approved status"
                )

            # Check if mission already exists
            existing = self.db.query(Mision).filter(
                Mision.solicitud_caso_id_rrhh == webhook_data.solicitud_caso_id
            ).first()
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Mission already exists for request {webhook_data.solicitud_caso_id}"
                )

            # Get beneficiary data
            personal_data = self.get_personal_data_by_cedula(rrhh_request["cedula"])
            if not personal_data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Personal with cedula {rrhh_request['cedula']} not found"
                )

            # Determine mission type
            mission_type = self.determine_mission_type(rrhh_request)

            # Get initial state
            initial_state = self.db.query(EstadoFlujo).filter(
                EstadoFlujo.nombre_estado == "PENDIENTE_REVISION_TESORERIA"
            ).first()

            if not initial_state:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Initial state not configured"
                )

            # Create mission
            mission = Mision(
                solicitud_caso_id_rrhh=webhook_data.solicitud_caso_id,
                tipo_mision=mission_type,
                beneficiario_personal_id=personal_data["personal_id"],
                objetivo_mision=rrhh_request.get("observacion", "Official mission"),
                destino_mision=self.extract_destination(rrhh_request.get("observacion", "")),
                fecha_salida=rrhh_request["fecha_inicio"],
                fecha_retorno=rrhh_request.get("fecha_fin") or rrhh_request["fecha_inicio"],
                monto_total_calculado=Decimal('0.00'),
                id_estado_flujo=initial_state.id_estado_flujo,
                fecha_limite_presentacion=(
                    self.calculate_limit_date(rrhh_request.get("fecha_fin") or rrhh_request["fecha_inicio"])
                    if mission_type == TipoMision.VIATICOS else None
                )
            )

            self.db.add(mission)
            self.db.flush()  # Get the ID

            # Create initial history record
            history = HistorialFlujo(
                id_mision=mission.id_mision,
                id_usuario_accion=1,  # System user
                id_estado_anterior=None,
                id_estado_nuevo=initial_state.id_estado_flujo,
                tipo_accion=TipoAccion.CREAR,
                comentarios=f"Mission created automatically from RRHH request #{webhook_data.solicitud_caso_id}",
                datos_adicionales={
                    "solicitud_rrhh_id": webhook_data.solicitud_caso_id,
                    "beneficiario_cedula": rrhh_request["cedula"],
                    "webhook_timestamp": datetime.utcnow().isoformat()
                }
            )
            self.db.add(history)

            self.db.commit()
            self.db.refresh(mission)
            return mission

        except Exception as e:
            self.db.rollback()
            raise e