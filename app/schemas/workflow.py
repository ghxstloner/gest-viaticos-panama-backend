# app/schemas/workflow.py

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any, Union
from decimal import Decimal
from datetime import datetime

# ===============================================
# ESQUEMAS BASE PARA WORKFLOW
# ===============================================

class WorkflowActionBase(BaseModel):
    """Esquema base para todas las acciones de workflow"""
    comentarios: Optional[str] = Field(None, max_length=1000, description="Comentarios opcionales sobre la acción")
    datos_adicionales: Optional[Dict[str, Any]] = Field(None, description="Datos adicionales específicos de la acción")

class PartidaPresupuestariaBase(BaseModel):
    """Esquema para partidas presupuestarias"""
    codigo_partida: str = Field(..., min_length=1, max_length=100, description="Código de la partida presupuestaria")
    monto: Decimal = Field(..., gt=0, description="Monto asignado a esta partida")
    descripcion: Optional[str] = Field(None, max_length=255, description="Descripción opcional de la partida")

    @validator('monto')
    def validate_monto_positive(cls, v):
        if v <= 0:
            raise ValueError('El monto debe ser mayor que cero')
        return v

# ===============================================
# ESQUEMAS ESPECÍFICOS POR ROL/ACCIÓN
# ===============================================

class JefeApprovalRequest(WorkflowActionBase):
    """Esquema específico para aprobación del jefe inmediato"""
    pass  # Solo requiere comentarios opcionales

class JefeRejectionRequest(WorkflowActionBase):
    """Esquema específico para rechazo del jefe inmediato"""
    motivo: str = Field(..., min_length=10, max_length=500, description="Motivo específico del rechazo")

class TesoreriaApprovalRequest(WorkflowActionBase):
    """Esquema específico para aprobación de tesorería"""
    observaciones_tesoreria: Optional[str] = Field(None, max_length=500, description="Observaciones específicas de tesorería")

class PresupuestoActionRequest(WorkflowActionBase):
    """Esquema específico para asignación de presupuesto"""
    partidas: List[PartidaPresupuestariaBase] = Field(..., min_items=1, description="Lista de partidas presupuestarias a asignar")
    monto_total_asignado: Optional[Decimal] = Field(None, description="Monto total calculado automáticamente")

    @validator('partidas')
    def validate_partidas_not_empty(cls, v):
        if not v:
            raise ValueError('Debe especificar al menos una partida presupuestaria')
        return v

    @validator('monto_total_asignado', always=True)
    def calculate_monto_total(cls, v, values):
        if 'partidas' in values:
            total = sum(partida.monto for partida in values['partidas'])
            return total
        return v

class ContabilidadApprovalRequest(WorkflowActionBase):
    """Esquema específico para aprobación de contabilidad"""
    numero_comprobante: Optional[str] = Field(None, max_length=50, description="Número de comprobante contable")
    observaciones_contables: Optional[str] = Field(None, max_length=500, description="Observaciones contables específicas")

class FinanzasApprovalRequest(WorkflowActionBase):
    """Esquema específico para aprobación de finanzas"""
    monto_aprobado: Optional[Decimal] = Field(None, gt=0, description="Monto específico aprobado por finanzas")
    requiere_documentos_adicionales: bool = Field(False, description="Indica si requiere documentos adicionales")
    observaciones_finanzas: Optional[str] = Field(None, max_length=500, description="Observaciones específicas de finanzas")

    @validator('monto_aprobado')
    def validate_monto_aprobado(cls, v):
        if v is not None and v <= 0:
            raise ValueError('El monto aprobado debe ser mayor que cero')
        return v

class CGRApprovalRequest(WorkflowActionBase):
    """Esquema específico para refrendo de CGR"""
    numero_refrendo: Optional[str] = Field(None, max_length=50, description="Número de refrendo asignado por CGR")
    observaciones_cgr: Optional[str] = Field(None, max_length=500, description="Observaciones específicas de CGR")

class PaymentProcessRequest(WorkflowActionBase):
    """Esquema específico para procesamiento de pago"""
    metodo_pago: str = Field(..., pattern="^(EFECTIVO|TRANSFERENCIA|ACH)$", description="Método de pago utilizado")
    numero_transaccion: Optional[str] = Field(None, max_length=100, description="Número de transacción bancaria")
    fecha_pago: Optional[datetime] = Field(None, description="Fecha específica del pago")
    banco_origen: Optional[str] = Field(None, max_length=100, description="Banco desde donde se realiza el pago")

# ===============================================
# ESQUEMAS DE RESPUESTA
# ===============================================

class WorkflowTransitionResponse(BaseModel):
    """Respuesta estándar para transiciones de workflow"""
    success: bool
    message: str
    mission_id: int
    estado_anterior: str
    estado_nuevo: str
    accion_ejecutada: str
    requiere_accion_adicional: bool = False
    datos_transicion: Optional[Dict[str, Any]] = None

class AvailableActionsResponse(BaseModel):
    """Respuesta con las acciones disponibles para un usuario"""
    mission_id: int
    estado_actual: str
    acciones_disponibles: List[Dict[str, Any]]
    puede_editar: bool
    puede_eliminar: bool

class PartidaPresupuestariaResponse(BaseModel):
    """Respuesta con información de partida presupuestaria"""
    codigo_partida: str
    descripcion: str
    monto_disponible: Optional[Decimal] = None
    es_activa: bool

class WorkflowStateInfo(BaseModel):
    """Información detallada del estado actual del workflow"""
    id_estado: int
    nombre_estado: str
    descripcion: str
    es_estado_final: bool
    tipo_flujo: str
    orden_flujo: Optional[int]
    acciones_posibles: List[str]

# ===============================================
# ESQUEMAS DINÁMICOS PARA DIFERENTES CONTEXTOS
# ===============================================

# Union type para manejar diferentes tipos de request según el rol
WorkflowActionRequest = Union[
    JefeApprovalRequest,
    JefeRejectionRequest,
    TesoreriaApprovalRequest,
    PresupuestoActionRequest,
    ContabilidadApprovalRequest,
    FinanzasApprovalRequest,
    CGRApprovalRequest,
    PaymentProcessRequest
]

# ===============================================
# VALIDADORES ADICIONALES
# ===============================================

class WorkflowValidationMixin:
    """Mixin con validaciones comunes para workflow"""
    
    @staticmethod
    def validate_monto_range(monto: Decimal, min_val: Decimal = Decimal('0.01'), max_val: Decimal = Decimal('999999.99')) -> Decimal:
        if monto < min_val or monto > max_val:
            raise ValueError(f'El monto debe estar entre {min_val} y {max_val}')
        return monto
    
    @staticmethod
    def validate_codigo_partida_format(codigo: str) -> str:
        # Validar formato específico de códigos presupuestarios
        if not codigo or len(codigo) < 5:
            raise ValueError('El código de partida presupuestaria debe tener al menos 5 caracteres')
        return codigo.strip().upper()

class WorkflowActionBase(BaseModel):
    comentarios: Optional[str] = Field(None, max_length=500)
    datos_adicionales: Optional[dict] = None

class JefeApprovalRequest(WorkflowActionBase):
    pass

class JefeRejectionRequest(WorkflowActionBase):
    motivo: str = Field(..., min_length=10, max_length=500)

class TesoreriaApprovalRequest(WorkflowActionBase):
    pass

class PartidaPresupuestariaBase(BaseModel):
    codigo_partida: str = Field(..., min_length=1)
    monto: Decimal = Field(..., gt=0)
    descripcion: Optional[str] = None

class PresupuestoActionRequest(WorkflowActionBase):
    partidas: List[PartidaPresupuestariaBase]

class ContabilidadApprovalRequest(WorkflowActionBase):
    numero_comprobante: Optional[str] = None

class FinanzasApprovalRequest(WorkflowActionBase):
    monto_aprobado: Optional[Decimal] = None

class CGRApprovalRequest(WorkflowActionBase):
    numero_refrendo: Optional[str] = None

class PaymentProcessRequest(WorkflowActionBase):
    metodo_pago: str = Field(..., description="EFECTIVO, TRANSFERENCIA, ACH")
    fecha_pago: Optional[datetime] = None
    numero_transaccion: Optional[str] = None
    banco_origen: Optional[str] = None

class AvailableActionsResponse(BaseModel):
    mission_id: int
    estado_actual: str
    acciones_disponibles: List[dict]
    puede_editar: bool
    puede_eliminar: bool

class WorkflowTransitionResponse(BaseModel):
    success: bool
    message: str
    mission_id: int
    estado_anterior: str
    estado_nuevo: str
    accion_ejecutada: str
    requiere_accion_adicional: bool = False
    datos_transicion: Optional[dict] = None

class WorkflowStateInfo(BaseModel):
    id_estado: int
    nombre_estado: str
    descripcion: str
    es_estado_final: bool
    tipo_flujo: str
    orden_flujo: Optional[int]
    acciones_posibles: List[str]

class PartidaPresupuestariaResponse(BaseModel):
    codigo_partida: str
    descripcion: str
    es_activa: bool

class JefeReturnRequest(WorkflowActionBase):
    observacion: str = Field(..., max_length=1000, description="Observación de la devolución/corrección")

class JefeDirectApprovalRequest(WorkflowActionBase):
    justificacion: str = Field(..., min_length=10, max_length=500, description="Justificación para aprobación directa")
    es_emergencia: bool = Field(default=False, description="Indica si es una situación de emergencia")
    monto_aprobado: Optional[Decimal] = Field(None, description="Monto específico aprobado por el jefe")

class DevolverRequest(BaseModel):
    observacion: str = Field(..., max_length=1000, description="Observación de la devolución/corrección")