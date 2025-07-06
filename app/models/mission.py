from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, JSON, Numeric, BigInteger, Date, Enum
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func
from typing import List, Optional, TYPE_CHECKING
from decimal import Decimal
from .base import Base, TimestampMixin
from ..models.enums import TipoMision, TipoFlujo, TipoAccion, EstadoGestion, TipoDocumento, EstadoSubsanacion, TipoTransporte, CategoriaBeneficiario, TipoViaje, TipoFirma

# ✅ Solo importar para type checking, evita referencias circulares
if TYPE_CHECKING:
    from .user import Rol, Usuario


class EstadoFlujo(Base):
    __tablename__ = "estados_flujo"

    id_estado_flujo: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    nombre_estado: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    descripcion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    es_estado_final: Mapped[bool] = mapped_column(Boolean, default=False)
    requiere_comentario: Mapped[bool] = mapped_column(Boolean, default=False)
    orden_flujo: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    tipo_flujo: Mapped[TipoFlujo] = mapped_column(String(20), default=TipoFlujo.AMBOS)

    # Relationships
    misiones: Mapped[List["Mision"]] = relationship("Mision", back_populates="estado_flujo")
    transiciones_origen: Mapped[List["TransicionFlujo"]] = relationship("TransicionFlujo", foreign_keys="[TransicionFlujo.id_estado_origen]", back_populates="estado_origen")
    transiciones_destino: Mapped[List["TransicionFlujo"]] = relationship("TransicionFlujo", foreign_keys="[TransicionFlujo.id_estado_destino]", back_populates="estado_destino")
    historial_flujo_anterior: Mapped[List["HistorialFlujo"]] = relationship("HistorialFlujo", foreign_keys="[HistorialFlujo.id_estado_anterior]", back_populates="estado_anterior")
    historial_flujo_nuevo: Mapped[List["HistorialFlujo"]] = relationship("HistorialFlujo", foreign_keys="[HistorialFlujo.id_estado_nuevo]", back_populates="estado_nuevo")


class TransicionFlujo(Base):
    __tablename__ = "transiciones_flujo"

    id_transicion: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    id_estado_origen: Mapped[int] = mapped_column(Integer, ForeignKey("estados_flujo.id_estado_flujo"), nullable=False)
    id_estado_destino: Mapped[int] = mapped_column(Integer, ForeignKey("estados_flujo.id_estado_flujo"), nullable=False)
    id_rol_autorizado: Mapped[int] = mapped_column(Integer, ForeignKey("roles.id_rol"), nullable=False)
    tipo_accion: Mapped[TipoAccion] = mapped_column(String(20), nullable=False)
    es_activa: Mapped[bool] = mapped_column(Boolean, default=True)

    estado_origen: Mapped["EstadoFlujo"] = relationship("EstadoFlujo", foreign_keys=[id_estado_origen], back_populates="transiciones_origen")
    estado_destino: Mapped["EstadoFlujo"] = relationship("EstadoFlujo", foreign_keys=[id_estado_destino], back_populates="transiciones_destino")
    rol_autorizado: Mapped["Rol"] = relationship("Rol", back_populates="transiciones_flujo")


class Mision(Base, TimestampMixin):
    __tablename__ = "misiones"

    id_mision: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    
    # --- Campos Nuevos y Modificados ---
    numero_solicitud: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, comment='Corresponde al "N. de Solicitud" del formulario de viáticos')
    destino_codnivel2: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, comment='Para Caja Menuda: "Para:". Se almacena el código del nivel 2 de la unidad administrativa destino. Es NULO para Viáticos.')
    
    tipo_mision: Mapped[TipoMision] = mapped_column(String(20), nullable=False)
    beneficiario_personal_id: Mapped[int] = mapped_column(Integer, nullable=False)
    
    id_usuario_prepara: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("usuarios.id_usuario"), nullable=True, comment='FK al usuario que prepara el formulario')
    
    categoria_beneficiario: Mapped[Optional[CategoriaBeneficiario]] = mapped_column(String(50), nullable=True, comment='Categoría del beneficiario para cálculo de tarifas de viáticos')
    
    objetivo_mision: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment='Para Viáticos es "Misión Oficial", para Caja Menuda es "Trabajo a Realizar"')
    destino_mision: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment='Aplica principalmente a Viáticos')
    tipo_viaje: Mapped[Optional[TipoViaje]] = mapped_column(String(20), nullable=True, comment='Distingue si la misión de viáticos es dentro o fuera del país')
    region_exterior: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, comment='Región para misiones de viáticos en el exterior')
    
    fecha_salida: Mapped[Optional[DateTime]] = mapped_column(DateTime, nullable=True, comment='En Caja Menuda puede ser una sola fecha/hora de inicio')
    fecha_retorno: Mapped[Optional[DateTime]] = mapped_column(DateTime, nullable=True, comment='Puede no aplicar para Caja Menuda')
    transporte_oficial: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True, comment='Campo "Transporte Oficial Si/No" del formulario de viáticos')

    monto_total_calculado: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0.00)
    monto_aprobado: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    id_estado_flujo: Mapped[int] = mapped_column(Integer, ForeignKey("estados_flujo.id_estado_flujo"), nullable=False)
    requiere_refrendo_cgr: Mapped[bool] = mapped_column(Boolean, default=False)
    numero_gestion_cobro: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    numero_orden_pago: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    hash_documento_firmado: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    fecha_firma_beneficiario: Mapped[Optional[DateTime]] = mapped_column(DateTime, nullable=True)
    observaciones_especiales: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    fecha_limite_presentacion: Mapped[Optional[Date]] = mapped_column(Date, nullable=True)

    # --- Relationships ---
    estado_flujo: Mapped["EstadoFlujo"] = relationship("EstadoFlujo", back_populates="misiones")
    usuario_prepara: Mapped[Optional["Usuario"]] = relationship("Usuario", foreign_keys=[id_usuario_prepara]) # back_populates en Usuario
    
    items_viaticos: Mapped[List["ItemViatico"]] = relationship("ItemViatico", back_populates="mision", cascade="all, delete-orphan")
    items_viaticos_completos: Mapped[List["ItemViaticoCompleto"]] = relationship("ItemViaticoCompleto", back_populates="mision", cascade="all, delete-orphan")
    items_transporte: Mapped[List["ItemTransporte"]] = relationship("ItemTransporte", back_populates="mision", cascade="all, delete-orphan")
    items_misiones_exterior: Mapped[List["ItemMisionExterior"]] = relationship("ItemMisionExterior", back_populates="mision", cascade="all, delete-orphan")
    misiones_caja_menuda: Mapped[List["MisionCajaMenuda"]] = relationship("MisionCajaMenuda", back_populates="mision", cascade="all, delete-orphan")
    adjuntos: Mapped[List["Adjunto"]] = relationship("Adjunto", back_populates="mision", cascade="all, delete-orphan")
    historial_flujo: Mapped[List["HistorialFlujo"]] = relationship("HistorialFlujo", back_populates="mision", cascade="all, delete-orphan")
    gestiones_cobro: Mapped[List["GestionCobro"]] = relationship("GestionCobro", back_populates="mision", cascade="all, delete-orphan")
    subsanaciones: Mapped[List["Subsanacion"]] = relationship("Subsanacion", back_populates="mision", cascade="all, delete-orphan")
    partidas_presupuestarias: Mapped[List["MisionPartidaPresupuestaria"]] = relationship("MisionPartidaPresupuestaria", back_populates="mision", cascade="all, delete-orphan")
    firmas_electronicas: Mapped[List["FirmaElectronica"]] = relationship("FirmaElectronica", back_populates="mision", cascade="all, delete-orphan")


class MisionPartidaPresupuestaria(Base):
    __tablename__ = "mision_partidas_presupuestarias"
    
    id_partida_mision: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_mision: Mapped[int] = mapped_column(Integer, ForeignKey("misiones.id_mision"), nullable=False)
    codigo_partida: Mapped[str] = mapped_column(String(100), nullable=False)
    monto: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    mision: Mapped["Mision"] = relationship("Mision", back_populates="partidas_presupuestarias")


class GestionCobro(Base):
    __tablename__ = "gestiones_cobro"

    id_gestion_cobro: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    id_mision: Mapped[int] = mapped_column(Integer, ForeignKey("misiones.id_mision"), unique=True, nullable=False)
    numero_gestion: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    fecha_generacion: Mapped[DateTime] = mapped_column(DateTime, default=func.now())
    id_usuario_genero: Mapped[int] = mapped_column(Integer, ForeignKey("usuarios.id_usuario"), nullable=False)
    monto_autorizado: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    codigo_presupuestario: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    observaciones: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    estado: Mapped[EstadoGestion] = mapped_column(String(20), default=EstadoGestion.PENDIENTE)

    mision: Mapped["Mision"] = relationship("Mision", back_populates="gestiones_cobro")
    usuario_genero: Mapped["Usuario"] = relationship("Usuario", back_populates="gestiones_cobro")


class ItemViatico(Base):
    __tablename__ = "items_viaticos"

    id_item_viatico: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    id_mision: Mapped[int] = mapped_column(Integer, ForeignKey("misiones.id_mision"), nullable=False)
    fecha: Mapped[Date] = mapped_column(Date, nullable=False)
    monto_desayuno: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), default=0.00)
    monto_almuerzo: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), default=0.00)
    monto_cena: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), default=0.00)
    monto_hospedaje: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), default=0.00)
    observaciones: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    mision: Mapped["Mision"] = relationship("Mision", back_populates="items_viaticos")


class ItemTransporte(Base):
    __tablename__ = "items_transporte"

    id_item_transporte: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    id_mision: Mapped[int] = mapped_column(Integer, ForeignKey("misiones.id_mision"), nullable=False)
    fecha: Mapped[Date] = mapped_column(Date, nullable=False)
    tipo: Mapped[TipoTransporte] = mapped_column(String(50), nullable=False)
    origen: Mapped[str] = mapped_column(String(255), nullable=False)
    destino: Mapped[str] = mapped_column(String(255), nullable=False)
    monto: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    observaciones: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    mision: Mapped["Mision"] = relationship("Mision", back_populates="items_transporte")


class Adjunto(Base):
    __tablename__ = "adjuntos"

    id_adjunto: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    id_mision: Mapped[int] = mapped_column(Integer, ForeignKey("misiones.id_mision"), nullable=False)
    nombre_archivo: Mapped[str] = mapped_column(String(255), nullable=False)
    nombre_original: Mapped[str] = mapped_column(String(255), nullable=False)
    url_almacenamiento: Mapped[str] = mapped_column(String(512), nullable=False)
    tipo_mime: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    tamano_bytes: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    tipo_documento: Mapped[TipoDocumento] = mapped_column(String(20), default=TipoDocumento.OTRO)
    id_usuario_subio: Mapped[int] = mapped_column(Integer, ForeignKey("usuarios.id_usuario"), nullable=False)
    fecha_carga: Mapped[DateTime] = mapped_column(DateTime, default=func.now())

    mision: Mapped["Mision"] = relationship("Mision", back_populates="adjuntos")
    usuario_subio: Mapped["Usuario"] = relationship("Usuario", back_populates="adjuntos_subidos")


class HistorialFlujo(Base):
    __tablename__ = "historial_flujo"

    id_historial: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    id_mision: Mapped[int] = mapped_column(Integer, ForeignKey("misiones.id_mision"), nullable=False)
    id_usuario_accion: Mapped[int] = mapped_column(Integer, ForeignKey("usuarios.id_usuario"), nullable=False)
    id_estado_anterior: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("estados_flujo.id_estado_flujo"), nullable=True)
    id_estado_nuevo: Mapped[int] = mapped_column(Integer, ForeignKey("estados_flujo.id_estado_flujo"), nullable=False)
    tipo_accion: Mapped[TipoAccion] = mapped_column(String(20), nullable=False)
    fecha_accion: Mapped[DateTime] = mapped_column(DateTime, default=func.now())
    comentarios: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    datos_adicionales: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    ip_usuario: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)

    mision: Mapped["Mision"] = relationship("Mision", back_populates="historial_flujo")
    usuario_accion: Mapped["Usuario"] = relationship("Usuario", back_populates="historial_flujo")
    estado_anterior: Mapped[Optional["EstadoFlujo"]] = relationship("EstadoFlujo", foreign_keys=[id_estado_anterior], back_populates="historial_flujo_anterior")
    estado_nuevo: Mapped["EstadoFlujo"] = relationship("EstadoFlujo", foreign_keys=[id_estado_nuevo], back_populates="historial_flujo_nuevo")


class Subsanacion(Base):
    __tablename__ = "subsanaciones"

    id_subsanacion: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    id_mision: Mapped[int] = mapped_column(Integer, ForeignKey("misiones.id_mision"), nullable=False)
    id_usuario_solicita: Mapped[int] = mapped_column(Integer, ForeignKey("usuarios.id_usuario"), nullable=False)
    id_usuario_responsable: Mapped[int] = mapped_column(Integer, ForeignKey("usuarios.id_usuario"), nullable=False)
    motivo: Mapped[str] = mapped_column(Text, nullable=False)
    fecha_solicitud: Mapped[DateTime] = mapped_column(DateTime, default=func.now())
    fecha_limite: Mapped[Date] = mapped_column(Date, nullable=False)
    fecha_respuesta: Mapped[Optional[DateTime]] = mapped_column(DateTime, nullable=True)
    respuesta: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    estado: Mapped[EstadoSubsanacion] = mapped_column(String(20), default=EstadoSubsanacion.PENDIENTE)

    mision: Mapped["Mision"] = relationship("Mision", back_populates="subsanaciones")
    usuario_solicita: Mapped["Usuario"] = relationship("Usuario", foreign_keys=[id_usuario_solicita], back_populates="subsanaciones_solicitadas")
    usuario_responsable: Mapped["Usuario"] = relationship("Usuario", foreign_keys=[id_usuario_responsable], back_populates="subsanaciones_responsables")


class ItemViaticoCompleto(Base):
    __tablename__ = "items_viaticos_completos"

    id_item_viatico_completo: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    id_mision: Mapped[int] = mapped_column(Integer, ForeignKey("misiones.id_mision"), nullable=False)
    fecha: Mapped[Date] = mapped_column(Date, nullable=False)
    cantidad_dias: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    monto_por_dia: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0.00, nullable=False)

    mision: Mapped["Mision"] = relationship("Mision", back_populates="items_viaticos_completos")


class ItemMisionExterior(Base):
    __tablename__ = "items_misiones_exterior"

    id_item_mision_exterior: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    id_mision: Mapped[int] = mapped_column(Integer, ForeignKey("misiones.id_mision"), nullable=False)
    region: Mapped[str] = mapped_column(String(100), nullable=False)
    destino: Mapped[str] = mapped_column(String(255), nullable=False)
    fecha_salida: Mapped[Date] = mapped_column(Date, nullable=False)
    fecha_retorno: Mapped[Date] = mapped_column(Date, nullable=False)
    porcentaje: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)

    mision: Mapped["Mision"] = relationship("Mision", back_populates="items_misiones_exterior")


class MisionCajaMenuda(Base):
    __tablename__ = "misiones_caja_menuda"

    id_caja_menuda: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    id_mision: Mapped[int] = mapped_column(Integer, ForeignKey("misiones.id_mision"), nullable=False)
    fecha: Mapped[Date] = mapped_column(Date, nullable=False)
    hora_de: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)  # TIME format as string
    hora_hasta: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)  # TIME format as string
    desayuno: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0.00)
    almuerzo: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0.00)
    cena: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0.00)
    transporte: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0.00)

    mision: Mapped["Mision"] = relationship("Mision", back_populates="misiones_caja_menuda")


class FirmaElectronica(Base):
    __tablename__ = "firmas_electronicas"

    id_firma: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    id_mision: Mapped[int] = mapped_column(Integer, ForeignKey("misiones.id_mision"), nullable=False)
    id_usuario: Mapped[int] = mapped_column(Integer, ForeignKey("usuarios.id_usuario"), nullable=False)
    tipo_firma: Mapped[TipoFirma] = mapped_column(String(20), nullable=False)
    fecha_firma: Mapped[DateTime] = mapped_column(DateTime, default=func.now())
    hash_documento: Mapped[str] = mapped_column(String(255), nullable=False)
    ip_firma: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    datos_firmante: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    es_valida: Mapped[bool] = mapped_column(Boolean, default=True)

    mision: Mapped["Mision"] = relationship("Mision", back_populates="firmas_electronicas")
    usuario: Mapped["Usuario"] = relationship("Usuario", back_populates="firmas_electronicas")
