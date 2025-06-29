from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text, and_
from decimal import Decimal
from datetime import datetime, date, timedelta
from ..models.mission import Mision, EstadoFlujo, HistorialFlujo, TransicionFlujo, GestionCobro, Subsanacion
from ..models.user import Usuario
from ..models.enums import TipoMision, TipoAccion, EstadoGestion
from ..schemas.mission import MisionCreate, MisionUpdate, MisionApprovalRequest, MisionRejectionRequest, WebhookMisionAprobada
from fastapi import HTTPException, status


class MissionService:
    def __init__(self, db: Session):
        self.db = db

    def approve_mission(self, mission_id: int, user_id: int, approval_data: MisionApprovalRequest) -> Mision:
        """Approve a mission"""
        try:
            # Get mission
            mission = self.db.query(Mision).filter(Mision.id_mision == mission_id).first()
            if not mission:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Mission not found"
                )

            # Get user
            user = self.db.query(Usuario).filter(Usuario.id_usuario == user_id).first()
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )

            # Validate transition
            if not self.validate_transition(mission.id_estado_flujo, user.id_rol, TipoAccion.APROBAR):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not authorized to approve in this state"
                )

            # Determine next state
            next_state = self.determine_next_state(mission.estado_flujo.nombre_estado, mission.tipo_mision)

            # Update mission
            mission.id_estado_flujo = next_state.id_estado_flujo
            mission.ultima_actualizacion = datetime.utcnow()
            
            if approval_data.monto_aprobado:
                mission.monto_aprobado = approval_data.monto_aprobado

            # Create history record
            history = HistorialFlujo(
                id_mision=mission_id,
                id_usuario_accion=user_id,
                id_estado_anterior=mission.id_estado_flujo,
                id_estado_nuevo=next_state.id_estado_flujo,
                tipo_accion=TipoAccion.APROBAR,
                comentarios=approval_data.comentarios,
                datos_adicionales={
                    "usuario_rol": user.rol.nombre_rol,
                    "estado_anterior": mission.estado_flujo.nombre_estado,
                    "estado_nuevo": next_state.nombre_estado
                }
            )
            self.db.add(history)

            # Execute special logic based on state
            self.execute_special_state_logic(mission, user_id)

            self.db.commit()
            self.db.refresh(mission)
            return mission

        except Exception as e:
            self.db.rollback()
            raise e

    def reject_mission(self, mission_id: int, user_id: int, rejection_data: MisionRejectionRequest) -> Mision:
        """Reject a mission and create subsanation"""
        try:
            mission = self.db.query(Mision).filter(Mision.id_mision == mission_id).first()
            if not mission:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Mission not found"
                )

            # Get rejection state
            rejection_state = self.db.query(EstadoFlujo).filter(
                EstadoFlujo.nombre_estado == "DEVUELTO_CORRECCION"
            ).first()

            if not rejection_state:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Rejection state not found"
                )

            # Update mission
            mission.id_estado_flujo = rejection_state.id_estado_flujo
            mission.ultima_actualizacion = datetime.utcnow()

            # Create subsanation
            subsanation = Subsanacion(
                id_mision=mission_id,
                id_usuario_solicita=user_id,
                id_usuario_responsable=self.get_responsible_user_for_subsanation(),
                motivo=rejection_data.motivo,
                fecha_limite=date.today() + timedelta(days=5)  # 5 days limit
            )
            self.db.add(subsanation)

            # Create history record
            history = HistorialFlujo(
                id_mision=mission_id,
                id_usuario_accion=user_id,
                id_estado_anterior=mission.id_estado_flujo,
                id_estado_nuevo=rejection_state.id_estado_flujo,
                tipo_accion=TipoAccion.DEVOLVER,
                comentarios=rejection_data.motivo
            )
            self.db.add(history)

            self.db.commit()
            self.db.refresh(mission)
            return mission

        except Exception as e:
            self.db.rollback()
            raise e

    def validate_transition(self, current_state_id: int, user_role_id: int, action: TipoAccion) -> bool:
        """Validate if transition is allowed"""
        transition = self.db.query(TransicionFlujo).filter(
            and_(
                TransicionFlujo.id_estado_origen == current_state_id,
                TransicionFlujo.id_rol_autorizado == user_role_id,
                TransicionFlujo.tipo_accion == action,
                TransicionFlujo.es_activa == True
            )
        ).first()
        
        return transition is not None

    def determine_next_state(self, current_state: str, mission_type: TipoMision) -> EstadoFlujo:
        """Determine the next state based on current state and mission type"""
        state_mapping = {
            "PENDIENTE_REVISION_TESORERIA": (
                "PENDIENTE_ASIGNACION_PRESUPUESTO" if mission_type == TipoMision.VIATICOS 
                else "APROBADO_PARA_PAGO"
            ),
            "PENDIENTE_ASIGNACION_PRESUPUESTO": "PENDIENTE_CONTABILIDAD",
            "PENDIENTE_CONTABILIDAD": "PENDIENTE_APROBACION_FINANZAS",
            "PENDIENTE_APROBACION_FINANZAS": "PENDIENTE_REFRENDO_CGR",
            "PENDIENTE_REFRENDO_CGR": "APROBADO_PARA_PAGO"
        }

        next_state_name = state_mapping.get(current_state)
        if not next_state_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot determine next state"
            )

        next_state = self.db.query(EstadoFlujo).filter(
            EstadoFlujo.nombre_estado == next_state_name
        ).first()

        if not next_state:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Next state not found in system"
            )

        return next_state

    def execute_special_state_logic(self, mission: Mision, user_id: int) -> None:
        """Execute special logic based on mission state"""
        if mission.estado_flujo.nombre_estado == "PENDIENTE_ASIGNACION_PRESUPUESTO":
            # Generate collection management
            self.generate_collection_management(mission, user_id)
        elif mission.estado_flujo.nombre_estado == "APROBADO_PARA_PAGO":
            # Notify treasury for payment
            self.notify_for_payment(mission)

    def generate_collection_management(self, mission: Mision, user_id: int) -> None:
        """Generate collection management document"""
        management_number = f"GC-{mission.id_mision}-{int(datetime.now().timestamp())}"

        collection_management = GestionCobro(
            id_mision=mission.id_mision,
            numero_gestion=management_number,
            id_usuario_genero=user_id,
            monto_autorizado=mission.monto_total_calculado
        )
        self.db.add(collection_management)

        # Update mission with management number
        mission.numero_gestion_cobro = management_number

    def notify_for_payment(self, mission: Mision) -> None:
        """Notify treasury for payment (placeholder for email/webhook logic)"""
        print(f"Mission {mission.id_mision} ready for payment")
        # Here you would implement email notification or webhook

    def get_responsible_user_for_subsanation(self) -> int:
        """Get responsible user for subsanation (placeholder)"""
        # In a real implementation, this would determine the responsible user
        return 1  # Default user

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

    def get_rrhh_request_data(self, request_id: int) -> Optional[dict]:
        """Get request data from RRHH database"""
        try:
            result = self.db.execute(text("""
                SELECT 
                    id_solicitudes_casos,
                    cedula,
                    id_tipo_solicitud,
                    id_solicitudes_casos_status,
                    fecha_inicio,
                    fecha_fin,
                    observacion
                FROM aitsa_rrhh.solicitudes_casos 
                WHERE id_solicitudes_casos = :request_id
            """), {"request_id": request_id})
            
            row = result.fetchone()
            if row:
                return {
                    "id_solicitudes_casos": row.id_solicitudes_casos,
                    "cedula": row.cedula,
                    "id_tipo_solicitud": row.id_tipo_solicitud,
                    "id_solicitudes_casos_status": row.id_solicitudes_casos_status,
                    "fecha_inicio": row.fecha_inicio,
                    "fecha_fin": row.fecha_fin,
                    "observacion": row.observacion
                }
            return None
        except Exception as e:
            print(f"Error getting RRHH request data: {e}")
            return None

    def get_personal_data_by_cedula(self, cedula: str) -> Optional[dict]:
        """Get personal data by cedula"""
        try:
            result = self.db.execute(text("""
                SELECT 
                    personal_id,
                    cedula,
                    apenom,
                    nombres,
                    apellidos,
                    email
                FROM aitsa_rrhh.nompersonal 
                WHERE cedula = :cedula AND estado = 'ACTIVO'
            """), {"cedula": cedula})
            
            row = result.fetchone()
            if row:
                return {
                    "personal_id": row.personal_id,
                    "cedula": row.cedula,
                    "apenom": row.apenom,
                    "nombres": row.nombres,
                    "apellidos": row.apellidos,
                    "email": row.email
                }
            return None
        except Exception as e:
            print(f"Error getting personal data: {e}")
            return None

    def determine_mission_type(self, request_data: dict) -> TipoMision:
        """Determine mission type based on request data"""
        # Simple logic: if more than 2 days, it's travel allowance; otherwise, petty cash
        start_date = request_data["fecha_inicio"]
        end_date = request_data.get("fecha_fin") or start_date
        
        if isinstance(start_date, str):
            start_date = datetime.fromisoformat(start_date)
        if isinstance(end_date, str):
            end_date = datetime.fromisoformat(end_date)
            
        days_diff = (end_date - start_date).days
        
        return TipoMision.VIATICOS if days_diff > 2 else TipoMision.CAJA_MENUDA

    def extract_destination(self, observation: str) -> str:
        """Extract destination from observation text"""
        return observation[:255] if observation else "Destination not specified"

    def calculate_limit_date(self, return_date) -> date:
        """Calculate limit date for document submission"""
        if isinstance(return_date, str):
            return_date = datetime.fromisoformat(return_date).date()
        elif isinstance(return_date, datetime):
            return_date = return_date.date()
            
        return return_date + timedelta(days=10)  # 10 days after return