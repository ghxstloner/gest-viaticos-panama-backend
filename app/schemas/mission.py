# app/schemas/mission.py

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


# --- Esquema para Caja Menuda ---
class MisionCajaMenudaBase(BaseModel):
    fecha: date
    hora_de: Optional[str] = None
    hora_hasta: Optional[str] = None
    desayuno: Decimal = Field(default=Decimal("0.0"), ge=0)
    almuerzo: Decimal = Field(default=Decimal("0.0"), ge=0)
    cena: Decimal = Field(default=Decimal("0.0"), ge=0)
    transporte: Decimal = Field(default=Decimal("0.0"), ge=0)

class MisionCajaMenudaCreate(MisionCajaMenudaBase):
    pass

class MisionCajaMenuda(MisionCajaMenudaBase):
    id_caja_menuda: int
    id_mision: int
    model_config = ConfigDict(from_attributes=True)


# --- Esquemas específicos para empleados (reutilizables) ---
class ViaticoCompletoEmployee(BaseModel):
    cantidadDias: int = Field(..., gt=0)
    pagoPorDia: Decimal = Field(..., gt=0)

class ViaticoParcialEmployee(BaseModel):
    fecha: date
    desayuno: str  # 'SI' o 'NO'
    almuerzo: str  # 'SI' o 'NO'
    cena: str      # 'SI' o 'NO'
    hospedaje: str # 'SI' o 'NO'
    observaciones: Optional[str] = None

class TransporteDetalleEmployee(BaseModel):
    fecha: date
    tipo: str  # 'AÉREO', 'ACUÁTICO', 'MARÍTIMO', 'TERRESTRE'
    origen: str = Field(..., min_length=1)
    destino: str = Field(..., min_length=1)
    monto: Decimal = Field(..., gt=0)

class MisionExteriorEmployee(BaseModel):
    destino: str = Field(..., min_length=1)
    region: str = Field(..., min_length=1)
    fechaSalida: date
    fechaRetorno: date
    porcentaje: Decimal = Field(default=Decimal("100"), ge=0, le=100)

class CajaMenudaViaticoEmployee(BaseModel):
    fecha: date
    horaDe: str = Field(..., pattern=r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$')
    horaHasta: str = Field(..., pattern=r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$')
    desayuno: Decimal = Field(default=Decimal("0"), ge=0)
    almuerzo: Decimal = Field(default=Decimal("0"), ge=0)
    cena: Decimal = Field(default=Decimal("0"), ge=0)
    transporte: Decimal = Field(default=Decimal("0"), ge=0)

    @validator('horaHasta')
    def validate_time_range(cls, v, values):
        if 'horaDe' in values:
            from datetime import datetime
            try:
                hora_de = datetime.strptime(values['horaDe'], '%H:%M')
                hora_hasta = datetime.strptime(v, '%H:%M')
                if hora_hasta <= hora_de:
                    raise ValueError('La hora hasta debe ser posterior a la hora de')
            except ValueError:
                pass  # Si no se puede parsear, no validamos
        return v


# --- Esquemas Principales de Misión ---
class MisionCreate(BaseModel):
    tipo_mision: TipoMision
    beneficiario_personal_id: Optional[int] = None
    objetivo_mision: str = Field(..., min_length=10, max_length=1000)
    observaciones_especiales: Optional[str] = None

    # --- Campos para VIATICOS ---
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
    codnivel2_destino_cm: Optional[int] = None
    monto_solicitado: Optional[Decimal] = Field(None, gt=0)
    
    @root_validator(pre=True)
    def check_mission_type_fields(cls, values):
        tipo_mision = values.get('tipo_mision')
        if tipo_mision == TipoMision.VIATICOS:
            required_fields = ['destino_mision', 'fecha_salida', 'fecha_retorno', 'categoria_beneficiario', 'tipo_viaje']
            for field in required_fields:
                if values.get(field) is None:
                    raise ValueError(f"Para viáticos, el campo '{field}' es obligatorio.")
            if values.get('tipo_viaje') == TipoViaje.INTERNACIONAL and not values.get('region_exterior'):
                raise ValueError("Para viajes internacionales, el campo 'region_exterior' es obligatorio.")
        
        elif tipo_mision == TipoMision.CAJA_MENUDA:
            required_fields = ['codnivel2_destino_cm', 'monto_solicitado']
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


# --- Esquemas de actualización específicos para empleados ---
class TravelExpensesUpdateRequest(BaseModel):
    objetivo: Optional[str] = Field(None, min_length=10, max_length=1000)
    destino: Optional[str] = Field(None, min_length=1, max_length=255)
    transporteOficial: Optional[str] = None  # 'SI' o 'NO'
    fechaSalida: Optional[date] = None
    horaSalida: Optional[str] = Field(None, pattern=r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$')
    fechaRetorno: Optional[date] = None
    horaRetorno: Optional[str] = Field(None, pattern=r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$')
    categoria: Optional[str] = Field(None, pattern=r'^(TITULAR|OTROS_SERVIDORES_PUBLICOS|OTRAS_PERSONAS)$')
    viaticosCompletos: Optional[List[ViaticoCompletoEmployee]] = None
    viaticosParciales: Optional[List[ViaticoParcialEmployee]] = None
    transporteDetalle: Optional[List[TransporteDetalleEmployee]] = None
    misionesExterior: Optional[List[MisionExteriorEmployee]] = None

    @validator('fechaRetorno')
    def validate_return_date(cls, v, values):
        if 'fechaSalida' in values and v and values['fechaSalida'] and v < values['fechaSalida']:
            raise ValueError('La fecha de retorno debe ser igual o posterior a la fecha de salida')
        return v

class PettyCashUpdateRequest(BaseModel):
    trabajo_a_realizar: Optional[str] = Field(None, min_length=10, max_length=500)
    para: Optional[str] = None  # departamento
    vicepresidencia: Optional[str] = None
    viaticosCompletos: Optional[List[CajaMenudaViaticoEmployee]] = None


# --- Esquemas de creación para empleados ---
class TravelExpensesCreateRequest(BaseModel):
    objetivo: str = Field(..., min_length=10, max_length=1000)
    destino: str = Field(..., min_length=1, max_length=255)
    transporteOficial: str  # 'SI' o 'NO'
    fechaSalida: date
    horaSalida: str = Field(..., pattern=r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$')
    fechaRetorno: date
    horaRetorno: str = Field(..., pattern=r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$')
    categoria: str = Field(..., pattern=r'^(TITULAR|OTROS_SERVIDORES_PUBLICOS|OTRAS_PERSONAS)$')
    viaticosCompletos: List[ViaticoCompletoEmployee] = []
    viaticosParciales: List[ViaticoParcialEmployee] = []
    transporteDetalle: List[TransporteDetalleEmployee] = []
    misionesExterior: List[MisionExteriorEmployee] = []

    @validator('fechaRetorno')
    def validate_return_date(cls, v, values):
        if 'fechaSalida' in values and v < values['fechaSalida']:
            raise ValueError('La fecha de retorno debe ser igual o posterior a la fecha de salida')
        return v

class PettyCashCreateRequest(BaseModel):
    trabajo_a_realizar: str = Field(..., min_length=10, max_length=500)
    para: str = Field(..., min_length=1)  # departamento
    vicepresidencia: str = Field(..., min_length=1)
    viaticosCompletos: List[CajaMenudaViaticoEmployee] = Field(..., min_items=1)


class ItemMisionExterior(BaseModel):
    id_item_mision_exterior: int
    id_mision: int
    region: str
    destino: str
    fecha_salida: date
    fecha_retorno: date
    porcentaje: Optional[Decimal] = None
    model_config = ConfigDict(from_attributes=True)


# --- Esquema para Items Viaticos Completos ---
class ItemViaticoCompletoSchema(BaseModel):
    id_item_viatico_completo: int
    id_mision: int
    cantidad_dias: int
    monto_por_dia: Decimal
    model_config = ConfigDict(from_attributes=True)

class Mision(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id_mision: int
    numero_solicitud: Optional[str] = None
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
    observacion: Optional[str] = None
    beneficiario_nombre: Optional[str] = None
    
    # Campos para tracking de usuarios que aprueban en cada etapa del workflow
    id_tesoreria: Optional[int] = None
    id_presupuesto: Optional[int] = None
    id_contabilidad: Optional[int] = None
    id_finanzas: Optional[int] = None
    id_jefe: Optional[int] = None
    
    # Campos para tracking de estado del cheque (solo para Viáticos)
    cheque_confeccionado: Optional[bool] = False
    cheque_firmado: Optional[bool] = False
    
    estado_flujo: "EstadoFlujo"
    items_viaticos: List[ItemViatico] = []
    items_transporte: List[ItemTransporte] = []
    partidas_presupuestarias: List[MisionPartidaPresupuestaria] = []
    items_misiones_exterior: List[ItemMisionExterior] = []
    items_viaticos_completos: Optional[List[ItemViaticoCompletoSchema]] = []
    misiones_caja_menuda: List[MisionCajaMenuda] = []

    @validator('categoria_beneficiario', pre=True, always=True)
    def normalize_categoria_beneficiario(cls, v):
        if isinstance(v, str):
            v = v.replace('Á', 'A').replace('É', 'E').replace('Í', 'I').replace('Ó', 'O').replace('Ú', 'U').replace('Ü', 'U').replace('Ñ', 'N')
            v = v.replace(' ', '_').replace("'", '').upper()
        return v


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
    beneficiario_nombre: Optional[str]
    fecha_salida: Optional[datetime]
    monto_total_calculado: Decimal
    estado_flujo: EstadoFlujo
    created_at: datetime
    observacion: Optional[str]

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

class ViaticoValidationRequest(BaseModel):
    """Schema para validar viáticos en un rango de fechas"""
    fecha_inicio: date
    fecha_fin: date
    hora_inicio: Optional[str] = Field(None, pattern=r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$')
    hora_fin: Optional[str] = Field(None, pattern=r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$')

class ViaticoValidationResponse(BaseModel):
    """Response para validación de viáticos"""
    tiene_viaticos_en_rango: bool
    mensaje: str
    detalles: Optional[Dict[str, Any]] = None

class ViaticoDiaValidationRequest(BaseModel):
    """Schema para validar viáticos en un día específico"""
    fecha: date

class ViaticoDiaValidationResponse(BaseModel):
    """Response para validación de viáticos por día"""
    tiene_desayuno: bool
    tiene_almuerzo: bool
    tiene_cena: bool
    tiene_hospedaje: bool
    mensaje: str
    detalles: Optional[Dict[str, Any]] = None

class UserParticipationResponse(BaseModel):
    """Schema para respuesta de participación de usuario en solicitudes"""
    id_mision: int
    numero_solicitud: Optional[str]
    codnivel2_destino_cm: Optional[int]
    tipo_mision: TipoMision
    beneficiario_personal_id: int
    id_usuario_prepara: Optional[int]
    categoria_beneficiario: Optional[CategoriaBeneficiario]
    objetivo_mision: Optional[str]
    destino_mision: Optional[str]
    tipo_viaje: Optional[TipoViaje]
    region_exterior: Optional[str]
    fecha_salida: Optional[datetime]
    fecha_retorno: Optional[datetime]
    transporte_oficial: Optional[bool]
    monto_total_calculado: Decimal
    monto_aprobado: Optional[Decimal]
    requiere_refrendo_cgr: bool
    numero_gestion_cobro: Optional[str]
    observaciones_especiales: Optional[str]
    fecha_limite_presentacion: Optional[date]
    created_at: datetime
    updated_at: datetime
    observacion: Optional[str]
    beneficiario_nombre: Optional[str]
    
    # Campos para tracking de usuarios que aprueban en cada etapa del workflow
    id_tesoreria: Optional[int]
    id_presupuesto: Optional[int]
    id_contabilidad: Optional[int]
    id_finanzas: Optional[int]
    id_jefe: Optional[int]
    
    # Relaciones
    estado_flujo: EstadoFlujo
    items_viaticos: List[ItemViatico] = []
    items_transporte: List[ItemTransporte] = []
    partidas_presupuestarias: List[MisionPartidaPresupuestaria] = []
    items_misiones_exterior: List[ItemMisionExterior] = []
    items_viaticos_completos: Optional[List[ItemViaticoCompletoSchema]] = []
    misiones_caja_menuda: List[MisionCajaMenuda] = []
    
    model_config = ConfigDict(from_attributes=True)

class UserParticipationsResponse(BaseModel):
    """Schema para lista de participaciones de usuario"""
    items: List[UserParticipationResponse]
    total: int
    page: int
    size: int
    pages: int
    stats: Dict[str, Any]


# --- Esquemas para Check de Cheque (solo Viáticos) ---
class ChequeStatusUpdate(BaseModel):
    """Schema para actualizar el estado de los checks del cheque"""
    cheque_confeccionado: Optional[bool] = Field(
        None, 
        description="Indica si el cheque ya fue confeccionado"
    )
    cheque_firmado: Optional[bool] = Field(
        None,
        description="Indica si el cheque ya fue firmado"
    )
    
    @validator('cheque_confeccionado', 'cheque_firmado')
    def validate_not_none(cls, v):
        """Valida que al menos un campo sea proporcionado"""
        return v

class ChequeStatusResponse(BaseModel):
    """Schema para respuesta del estado de los checks del cheque"""
    mission_id: int
    numero_solicitud: Optional[str] = None
    tipo_mision: TipoMision
    cheque_confeccionado: bool
    cheque_firmado: bool
    message: str