from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime, date
from decimal import Decimal
from ..models.enums import TipoMision, TipoAccion, EstadoGestion, TipoDocumento, EstadoSubsanacion


class EstadoFlujoBase(BaseModel):
    nombre_estado: str
    descripcion: Optional[str] = None
    es_estado_final: bool = False
    requiere_comentario: bool = False


class EstadoFlujo(EstadoFlujoBase):
    model_config = ConfigDict(from_attributes=True)
    
    id_estado_flujo: int


class ItemViaticoBase(BaseModel):
    fecha: date
    monto_desayuno: Optional[Decimal] = Decimal('0.00')
    monto_almuerzo: Optional[Decimal] = Decimal('0.00')
    monto_cena: Optional[Decimal] = Decimal('0.00')
    monto_hospedaje: Optional[Decimal] = Decimal('0.00')
    observaciones: Optional[str] = None


class ItemViaticoCreate(ItemViaticoBase):
    pass


class ItemViatico(ItemViaticoBase):
    model_config = ConfigDict(from_attributes=True)
    
    id_item_viatico: int
    id_mision: int


class ItemTransporteBase(BaseModel):
    fecha: date
    tipo: str
    origen: str
    destino: str
    monto: Decimal
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


class MisionCreate(MisionBase):
    solicitud_caso_id_rrhh: int
    items_viaticos: Optional[List[ItemViaticoCreate]] = []
    items_transporte: Optional[List[ItemTransporteCreate]] = []


class MisionUpdate(BaseModel):
    objetivo_mision: Optional[str] = None
    destino_mision: Optional[str] = None
    fecha_salida: Optional[datetime] = None
    fecha_retorno: Optional[datetime] = None
    monto_aprobado: Optional[Decimal] = None
    observaciones_especiales: Optional[str] = None


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
    comentarios: Optional[str] = None
    monto_aprobado: Optional[Decimal] = None


class MisionRejectionRequest(BaseModel):
    motivo: str


class WebhookMisionAprobada(BaseModel):
    solicitud_caso_id: int
    usuario_aprobador: Optional[str] = None
    fecha_aprobacion: Optional[datetime] = None


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