from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func
from typing import List, Optional, TYPE_CHECKING
from .base import Base, TimestampMixin

# ✅ Solo importar para type checking, evita referencias circulares
if TYPE_CHECKING:
    from .mission import TransicionFlujo, HistorialFlujo, GestionCobro, Subsanacion, Adjunto


class Rol(Base, TimestampMixin):
    __tablename__ = "roles"

    id_rol: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    nombre_rol: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    descripcion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    permisos_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    fecha_creacion: Mapped[DateTime] = mapped_column(DateTime, default=func.now())

    # ✅ Usar strings para forward references
    usuarios: Mapped[List["Usuario"]] = relationship("Usuario", back_populates="rol")
    transiciones_flujo: Mapped[List["TransicionFlujo"]] = relationship("TransicionFlujo", back_populates="rol_autorizado")


class Usuario(Base, TimestampMixin):
    __tablename__ = "usuarios"

    id_usuario: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    personal_id_rrhh: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    login_username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    id_rol: Mapped[int] = mapped_column(Integer, ForeignKey("roles.id_rol"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    ultimo_acceso: Mapped[Optional[DateTime]] = mapped_column(DateTime, nullable=True)
    fecha_creacion: Mapped[DateTime] = mapped_column(DateTime, default=func.now())
    fecha_actualizacion: Mapped[DateTime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    # ✅ Usar strings para forward references
    rol: Mapped["Rol"] = relationship("Rol", back_populates="usuarios")
    historial_flujo: Mapped[List["HistorialFlujo"]] = relationship("HistorialFlujo", back_populates="usuario_accion")
    gestiones_cobro: Mapped[List["GestionCobro"]] = relationship("GestionCobro", back_populates="usuario_genero")
    subsanaciones_solicitadas: Mapped[List["Subsanacion"]] = relationship("Subsanacion", foreign_keys="[Subsanacion.id_usuario_solicita]", back_populates="usuario_solicita")
    subsanaciones_responsables: Mapped[List["Subsanacion"]] = relationship("Subsanacion", foreign_keys="[Subsanacion.id_usuario_responsable]", back_populates="usuario_responsable")
    adjuntos_subidos: Mapped[List["Adjunto"]] = relationship("Adjunto", back_populates="usuario_subio")