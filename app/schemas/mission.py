from pydantic import BaseModel, ConfigDict, Field, validator
from typing import Optional, List, Dict, Any, Union
from datetime import datetime, date
from decimal import Decimal
from ..models.enums import TipoMision, TipoAccion, EstadoGestion, TipoDocumento, EstadoSubsanacion


class EstadoFlujoBase(BaseModel):
    id_estado_flujo: int
    nombre_estado: str
    descripcion: Optional[str] = None


class EstadoFlujo(EstadoFlujoBase):
    model_config = ConfigDict(from_attributes=True)
    
    es_estado_final: bool = False
    requiere_comentario: bool = False


class ItemViaticoBase(BaseModel):
    fecha: date
    monto_desayuno: float = Field(ge=0, default=0.0)
    monto_almuerzo: float = Field(ge=0, default=0.0)
    monto_cena: float = Field(ge=0, default=0.0)
    monto_hospedaje: float = Field(ge=0, default=0.0)
    observaciones: Optional[str] = None


class ItemViaticoCreate(ItemViaticoBase):
    pass


class ItemViatico(ItemViaticoBase):
    model_config = ConfigDict(from_attributes=True)
    
    id_item_viatico: int
    id_mision: int


class ItemTransporteBase(BaseModel):
    fecha: date
    tipo: str = Field(..., description="Terrestre, Aéreo, Marítimo")
    origen: str = Field(..., min_length=1)
    destino: str = Field(..., min_length=1)
    monto: float = Field(gt=0)
    observaciones: Optional[str] = None


class ItemTransporteCreate(ItemTransporteBase):
    pass


class ItemTransporte(ItemTransporteBase):
    model_config = ConfigDict(from_attributes=True)
    
    id_item_transporte: int
    id_mision: int


class MisionBase(BaseModel):
    tipo_mision: TipoMision
    beneficiario_personal_id: int
    objetivo_mision: str
    destino_mision: str
    fecha_salida: datetime
    fecha_retorno: datetime


class MisionCreate(BaseModel):
    tipo_mision: TipoMision
    beneficiario_personal_id: Optional[int] = None
    objetivo_mision: str = Field(..., min_length=10, max_length=1000)
    destino_mision: str = Field(..., min_length=1, max_length=255)
    fecha_salida: datetime
    fecha_retorno: datetime
    observaciones_especiales: Optional[str] = None
    
    # Para viáticos
    items_viaticos: Optional[List[ItemViaticoBase]] = []
    items_transporte: Optional[List[ItemTransporteBase]] = []
    
    # Para caja menuda
    monto_solicitado: Optional[float] = Field(None, gt=0)
    concepto: Optional[str] = Field(None, min_length=5, max_length=255)
    
    @validator('fecha_retorno')
    def validate_dates(cls, v, values):
        if 'fecha_salida' in values and v < values['fecha_salida']:
            raise ValueError('La fecha de retorno debe ser igual o posterior a la fecha de salida')
        return v
    
    @validator('items_viaticos')
    def validate_viaticos_items(cls, v, values):
        if values.get('tipo_mision') == TipoMision.VIATICOS and not v:
            raise ValueError('Los viáticos requieren al menos un día de gastos')
        return v
    
    @validator('monto_solicitado')
    def validate_monto_caja_menuda(cls, v, values):
        if values.get('tipo_mision') == TipoMision.CAJA_MENUDA and not v:
            raise ValueError('La caja menuda requiere especificar el monto solicitado')
        return v


class MisionUpdate(BaseModel):
    objetivo_mision: Optional[str] = Field(None, min_length=10, max_length=1000)
    destino_mision: Optional[str] = Field(None, min_length=1, max_length=255)
    fecha_salida: Optional[datetime] = None
    fecha_retorno: Optional[datetime] = None
    observaciones_especiales: Optional[str] = None
    items_viaticos: Optional[List[ItemViaticoBase]] = None
    items_transporte: Optional[List[ItemTransporteBase]] = None


class Mision(MisionBase):
    model_config = ConfigDict(from_attributes=True)
    
    id_mision: int
    solicitud_caso_id_rrhh: int
    monto_total_calculado: Decimal
    monto_aprobado: Optional[Decimal] = None
    requiere_refrendo_cgr: bool
    numero_gestion_cobro: Optional[str] = None
    observaciones_especiales: Optional[str] = None
    fecha_limite_presentacion: Optional[date] = None
    fecha_creacion: datetime
    ultima_actualizacion: datetime
    estado_flujo: EstadoFlujo
    items_viaticos: List[ItemViatico] = []
    items_transporte: List[ItemTransporte] = []


class MisionApprovalRequest(BaseModel):
    comentarios: Optional[str] = Field(None, max_length=500)
    datos_adicionales: Optional[dict] = None


class MisionRejectionRequest(BaseModel):
    motivo: str = Field(..., min_length=10, max_length=500)
    comentarios: Optional[str] = Field(None, max_length=500)


class WebhookMisionAprobada(BaseModel):
    id_mision: int
    estado_nuevo: str
    aprobado_por: str
    fecha_aprobacion: datetime
    comentarios: Optional[str] = None


class HistorialFlujoBase(BaseModel):
    tipo_accion: TipoAccion
    comentarios: Optional[str] = None
    datos_adicionales: Optional[dict] = None


class HistorialFlujo(HistorialFlujoBase):
    model_config = ConfigDict(from_attributes=True)
    
    id_historial: int
    id_mision: int
    id_usuario_accion: int
    id_estado_anterior: Optional[int] = None
    id_estado_nuevo: int
    fecha_accion: datetime
    ip_usuario: Optional[str] = None

class MisionListItem(BaseModel):
    """Item de misión para listados"""
    model_config = ConfigDict(from_attributes=True)
    
    id_mision: int
    solicitud_caso_id_rrhh: int
    tipo_mision: TipoMision
    beneficiario_personal_id: int
    beneficiario_nombre: Optional[str] = None
    objetivo_mision: str
    destino_mision: str
    fecha_salida: datetime
    fecha_retorno: datetime
    monto_total_calculado: Decimal
    monto_aprobado: Optional[Decimal] = None
    estado_actual: str
    dias_en_estado: int
    requiere_accion: bool = False
    
class MisionListResponse(BaseModel):
    """Respuesta paginada de misiones"""
    total: int
    missions: List[MisionListItem]
    skip: int
    limit: int
    
class MisionDetail(BaseModel):
    """Detalle completo de una misión"""
    mission: Mision
    beneficiary: Dict[str, Any]
    available_actions: List[str]
    can_edit: bool
    can_delete: bool
    
class SubsanacionRequest(BaseModel):
    """Solicitud de subsanación"""
    respuesta: str = Field(..., min_length=10, max_length=2000)
    
class SubsanacionResponse(BaseModel):
    """Respuesta de subsanación"""
    model_config = ConfigDict(from_attributes=True)
    
    subsanacion: Any  # Subsanacion model
    mission_status: str
    
class GestionCobroCreate(BaseModel):
    """Crear gestión de cobro"""
    monto_autorizado: Optional[Decimal] = None
    codigo_presupuestario: Optional[str] = None
    observaciones: Optional[str] = None
    
class AttachmentUpload(BaseModel):
    """Respuesta de carga de archivo"""
    id_adjunto: int
    nombre_archivo: str
    url: str
    
class DashboardStats(BaseModel):
    """Estadísticas del dashboard"""
    resumen: Dict[str, Any]
    por_estado: List[Dict[str, Any]]
    por_tipo: List[Dict[str, Any]]
    tendencia_mensual: List[Dict[str, Any]]
    proximas_acciones: List[Dict[str, Any]]
    alertas: List[Dict[str, Any]]
    resumen_financiero: Optional[Dict[str, Any]] = None
    pagos_pendientes: Optional[Dict[str, Any]] = None

class WorkflowState(BaseModel):
    """Estado del flujo de trabajo"""
    model_config = ConfigDict(from_attributes=True)
    
    id_estado_flujo: int
    nombre_estado: str
    descripcion: Optional[str]
    es_estado_final: bool
    orden_flujo: Optional[int]
    
class WorkflowTransition(BaseModel):
    """Transición del flujo"""
    model_config = ConfigDict(from_attributes=True)
    
    id_transicion: int
    estado_origen: WorkflowState
    estado_destino: WorkflowState
    tipo_accion: TipoAccion
    rol_requerido: str


class SubsanacionBase(BaseModel):
    """Base para subsanación"""
    motivo: str
    fecha_limite: date
    respuesta: Optional[str] = None


class Subsanacion(SubsanacionBase):
    """Esquema de subsanación"""
    model_config = ConfigDict(from_attributes=True)
    
    id_subsanacion: int
    id_mision: int
    id_usuario_solicita: int
    id_usuario_responsable: int
    fecha_solicitud: datetime
    fecha_respuesta: Optional[datetime] = None
    estado: EstadoSubsanacion


class SubsanacionCreate(SubsanacionBase):
    """Crear subsanación"""
    id_usuario_responsable: int