from pydantic import BaseModel, ConfigDict, Field, validator, root_validator
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from decimal import Decimal
from ..models.enums import (
    TipoMision, TipoAccion, EstadoGestion, TipoDocumento, EstadoSubsanacion,
    TipoTransporte, CategoriaBeneficiario, TipoViaje
)

# --- Esquemas para Partidas Presupuestarias ---
class MisionPartidaPresupuestariaBase(BaseModel):
    codigo_partida: str = Field(..., min_length=1)
    monto: Decimal = Field(..., gt=0)

class MisionPartidaPresupuestariaCreate(MisionPartidaPresupuestariaBase):
    pass

class MisionPartidaPresupuestaria(MisionPartidaPresupuestariaBase):
    id_partida_mision: int
    id_mision: int
    model_config = ConfigDict(from_attributes=True)


# --- Esquemas para Items de Misión ---
class ItemViaticoBase(BaseModel):
    fecha: date
    monto_desayuno: Decimal = Field(ge=0, default=Decimal("0.0"))
    monto_almuerzo: Decimal = Field(ge=0, default=Decimal("0.0"))
    monto_cena: Decimal = Field(ge=0, default=Decimal("0.0"))
    monto_hospedaje: Decimal = Field(ge=0, default=Decimal("0.0"))
    observaciones: Optional[str] = None

class ItemViaticoCreate(ItemViaticoBase):
    pass

class ItemViatico(ItemViaticoBase):
    id_item_viatico: int
    id_mision: int
    model_config = ConfigDict(from_attributes=True)


class ItemTransporteBase(BaseModel):
    fecha: date
    tipo: TipoTransporte
    origen: str = Field(..., min_length=1)
    destino: str = Field(..., min_length=1)
    monto: Decimal = Field(..., gt=0)
    observaciones: Optional[str] = None

class ItemTransporteCreate(ItemTransporteBase):
    pass

class ItemTransporte(ItemTransporteBase):
    id_item_transporte: int
    id_mision: int
    model_config = ConfigDict(from_attributes=True)


# --- Esquemas Principales de Misión ---
class MisionCreate(BaseModel):
    tipo_mision: TipoMision
    beneficiario_personal_id: Optional[int] = None
    objetivo_mision: str = Field(..., min_length=10, max_length=1000)
    observaciones_especiales: Optional[str] = None

    # --- Campos para VIATICOS ---
    codnivel1_solicitante: Optional[int] = None
    destino_mision: Optional[str] = Field(None, min_length=1, max_length=255)
    fecha_salida: Optional[datetime] = None
    fecha_retorno: Optional[datetime] = None
    categoria_beneficiario: Optional[CategoriaBeneficiario] = None
    tipo_viaje: Optional[TipoViaje] = None
    region_exterior: Optional[str] = None
    transporte_oficial: Optional[bool] = False
    items_viaticos: Optional[List[ItemViaticoCreate]] = []
    items_transporte: Optional[List[ItemTransporteCreate]] = []
    partidas_presupuestarias: Optional[List[MisionPartidaPresupuestariaCreate]] = []

    # --- Campos para CAJA MENUDA ---
    codnivel1_destino_cm: Optional[int] = None
    codnivel2_destino_cm: Optional[int] = None
    monto_solicitado: Optional[Decimal] = Field(None, gt=0)
    
    @root_validator(pre=True)
    def check_mission_type_fields(cls, values):
        tipo_mision = values.get('tipo_mision')
        if tipo_mision == TipoMision.VIATICOS:
            required_fields = ['codnivel1_solicitante', 'destino_mision', 'fecha_salida', 'fecha_retorno', 'categoria_beneficiario', 'tipo_viaje']
            for field in required_fields:
                if values.get(field) is None:
                    raise ValueError(f"Para viáticos, el campo '{field}' es obligatorio.")
            if values.get('tipo_viaje') == TipoViaje.INTERNACIONAL and not values.get('region_exterior'):
                raise ValueError("Para viajes internacionales, el campo 'region_exterior' es obligatorio.")
        
        elif tipo_mision == TipoMision.CAJA_MENUDA:
            required_fields = ['codnivel1_destino_cm', 'codnivel2_destino_cm', 'monto_solicitado']
            for field in required_fields:
                if values.get(field) is None:
                    raise ValueError(f"Para caja menuda, el campo '{field}' es obligatorio.")
            # Caja menuda usualmente tiene una sola fecha, la usamos en fecha_salida
            if not values.get('fecha_salida'):
                 raise ValueError("Para caja menuda, el campo 'fecha_salida' (fecha del gasto) es obligatorio.")

        return values

    @validator('fecha_retorno')
    def validate_dates(cls, v, values):
        if 'fecha_salida' in values and v and values['fecha_salida'] and v < values['fecha_salida']:
            raise ValueError('La fecha de retorno debe ser igual o posterior a la fecha de salida')
        return v

class MisionUpdate(BaseModel):
    objetivo_mision: Optional[str] = Field(None, min_length=10, max_length=1000)
    observaciones_especiales: Optional[str] = None
    # Añadir más campos actualizables según las reglas de negocio
    items_viaticos: Optional[List[ItemViaticoCreate]] = None
    items_transporte: Optional[List[ItemTransporteCreate]] = None
    partidas_presupuestarias: Optional[List[MisionPartidaPresupuestariaCreate]] = None


class Mision(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id_mision: int
    numero_solicitud: Optional[str] = None
    codnivel1_solicitante: Optional[int] = None
    codnivel1_destino_cm: Optional[int] = None
    codnivel2_destino_cm: Optional[int] = None
    tipo_mision: TipoMision
    beneficiario_personal_id: int
    id_usuario_prepara: Optional[int] = None
    categoria_beneficiario: Optional[CategoriaBeneficiario] = None
    objetivo_mision: Optional[str] = None
    destino_mision: Optional[str] = None
    tipo_viaje: Optional[TipoViaje] = None
    region_exterior: Optional[str] = None
    fecha_salida: Optional[datetime] = None
    fecha_retorno: Optional[datetime] = None
    transporte_oficial: Optional[bool] = None
    monto_total_calculado: Decimal
    monto_aprobado: Optional[Decimal] = None
    requiere_refrendo_cgr: bool
    numero_gestion_cobro: Optional[str] = None
    observaciones_especiales: Optional[str] = None
    fecha_limite_presentacion: Optional[date] = None
    created_at: datetime
    updated_at: datetime
    
    estado_flujo: "EstadoFlujo"
    items_viaticos: List[ItemViatico] = []
    items_transporte: List[ItemTransporte] = []
    partidas_presupuestarias: List[MisionPartidaPresupuestaria] = []


# --- Esquemas para API Responses y Acciones ---
class EstadoFlujo(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id_estado_flujo: int
    nombre_estado: str
    descripcion: Optional[str] = None

class MisionListResponseItem(BaseModel):
    id_mision: int
    numero_solicitud: Optional[str]
    tipo_mision: TipoMision
    objetivo_mision: Optional[str]
    destino_mision: Optional[str]
    fecha_salida: Optional[datetime]
    monto_total_calculado: Decimal
    estado_flujo: EstadoFlujo
    created_at: datetime

class MisionListResponse(BaseModel):
    items: List[MisionListResponseItem]
    total: int
    page: int
    size: int
    pages: int

class MisionDetail(BaseModel):
    mission: Mision
    beneficiary: Dict[str, Any]
    preparer: Optional[Dict[str, Any]] = None
    available_actions: List[str]
    can_edit: bool
    can_delete: bool

class MisionApprovalRequest(BaseModel):
    comentarios: Optional[str] = Field(None, max_length=500)
    datos_adicionales: Optional[dict] = None

class MisionRejectionRequest(BaseModel):
    motivo: str = Field(..., min_length=10, max_length=500)
    comentarios: Optional[str] = Field(None, max_length=500)

class PresupuestoAssignRequest(BaseModel):
    partidas: List[MisionPartidaPresupuestariaCreate]
    comentarios: Optional[str] = None

class SubsanacionRequest(BaseModel):
    respuesta: str = Field(..., min_length=10, max_length=2000)

class SubsanacionResponse(BaseModel):
    subsanacion: Any
    mission_status: str

class GestionCobroCreate(BaseModel):
    monto_autorizado: Optional[Decimal] = None
    observaciones: Optional[str] = None

class AttachmentUpload(BaseModel):
    id_adjunto: int
    nombre_archivo: str
    url: str

class WorkflowState(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id_estado_flujo: int
    nombre_estado: str
    descripcion: Optional[str]
    es_estado_final: bool
    orden_flujo: Optional[int]

# --- Esquemas para Webhooks ---
class WebhookMisionAprobada(BaseModel):
    """Schema for mission approved webhook payload"""
    id_mision: int
    numero_solicitud: str
    estado_nuevo: str
    fecha_aprobacion: datetime
    datos_adicionales: Optional[dict] = None
    comentarios: Optional[str] = None

# --- Esquemas para Dashboard ---
class DashboardStats(BaseModel):
    """Schema for dashboard statistics"""
    total_missions: int
    missions_pending: int
    missions_approved: int
    missions_rejected: int
    missions_in_progress: int
    total_amount: Decimal
    approved_amount: Decimal
    pending_amount: Decimal
    missions_by_type: Dict[str, int]
    missions_by_state: Dict[str, int]
    recent_missions: List[Dict[str, Any]]
