# app/models/user.py

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, Table
from sqlalchemy.orm import relationship, Mapped, mapped_column
from typing import List, Optional, TYPE_CHECKING
from .base import Base, TimestampMixin
from datetime import datetime

# ✅ Solo importar para type checking, evita referencias circulares
if TYPE_CHECKING:
    from .mission import TransicionFlujo, HistorialFlujo, GestionCobro, Subsanacion, Adjunto, FirmaElectronica, Mision

# Definición de la tabla de asociación
RolPermiso = Table(
    'rol_permiso',
    Base.metadata,
    Column('id_rol', Integer, ForeignKey('roles.id_rol'), primary_key=True),
    Column('id_permiso', Integer, ForeignKey('permisos.id_permiso'), primary_key=True),
    extend_existing=True
)

class Permiso(Base):
    __tablename__ = 'permisos'
    __table_args__ = {'extend_existing': True}
    
    id_permiso = Column(Integer, primary_key=True, autoincrement=True)
    codigo = Column(String(50), unique=True, nullable=False)
    nombre = Column(String(100), nullable=False)
    descripcion = Column(String(255))
    modulo = Column(String(50), nullable=False)
    accion = Column(String(50), nullable=False)
    es_permiso_empleado = Column(Boolean, default=False)
    
    roles = relationship("Rol", secondary=RolPermiso, back_populates="permisos")

class Rol(Base, TimestampMixin):
    __tablename__ = "roles"
    __table_args__ = {'extend_existing': True}
    
    id_rol: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    nombre_rol: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    descripcion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    usuarios: Mapped[List["Usuario"]] = relationship("Usuario", back_populates="rol")
    permisos: Mapped[List["Permiso"]] = relationship("Permiso", secondary=RolPermiso, back_populates="roles")
    transiciones_flujo: Mapped[List["TransicionFlujo"]] = relationship("TransicionFlujo", back_populates="rol_autorizado")

    def has_permission(self, permission_code: str) -> bool:
        return any(p.codigo == permission_code for p in self.permisos)

    def to_dict(self):
        return {
            'id_rol': self.id_rol,
            'nombre_rol': self.nombre_rol,
            'descripcion': self.descripcion,
            'permisos': [
                {
                    'id_permiso': p.id_permiso,
                    'codigo': p.codigo,
                    'nombre': p.nombre
                } for p in self.permisos
            ]
        }

class FirmaJefe(Base):
    __tablename__ = "firmas_jefes"
    __table_args__ = {'extend_existing': True}
    
    firmas_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    personal_id: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    firma: Mapped[Optional[str]] = mapped_column(String(250), nullable=True)

class Usuario(Base, TimestampMixin):
    __tablename__ = "usuarios"
    __table_args__ = {'extend_existing': True}
    
    id_usuario: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    personal_id_rrhh: Mapped[Optional[int]] = mapped_column(Integer, unique=True, nullable=True)
    login_username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    id_rol: Mapped[int] = mapped_column(Integer, ForeignKey("roles.id_rol"), nullable=False)
    id_departamento: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("departamentos.id_departamento"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    ultimo_acceso: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    firma: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    rol: Mapped["Rol"] = relationship("Rol", back_populates="usuarios")
    departamento: Mapped[Optional["Department"]] = relationship("Department", back_populates="usuarios")
    
    # Relaciones para otras partes de la aplicación
    historial_flujo: Mapped[List["HistorialFlujo"]] = relationship("HistorialFlujo", back_populates="usuario_accion")
    gestiones_cobro: Mapped[List["GestionCobro"]] = relationship("GestionCobro", back_populates="usuario_genero")
    subsanaciones_solicitadas: Mapped[List["Subsanacion"]] = relationship("Subsanacion", foreign_keys="[Subsanacion.id_usuario_solicita]", back_populates="usuario_solicita")
    subsanaciones_responsables: Mapped[List["Subsanacion"]] = relationship("Subsanacion", foreign_keys="[Subsanacion.id_usuario_responsable]", back_populates="usuario_responsable")
    adjuntos_subidos: Mapped[List["Adjunto"]] = relationship("Adjunto", back_populates="usuario_subio")
    firmas_electronicas: Mapped[List["FirmaElectronica"]] = relationship("FirmaElectronica", back_populates="usuario")
    misiones_preparadas: Mapped[List["Mision"]] = relationship("Mision", back_populates="usuario_prepara")

    def get_permissions(self):
        """Obtener permisos del usuario según su rol - DINÁMICO para todos"""
        if not self.rol:
            return {}

        permisos_lista = [p.codigo for p in self.rol.permisos]
        
        # --- CORRECCIÓN APLICADA AQUÍ ---
        # Se eliminó la función lambda que causaba el error de serialización.
        # Este diccionario es seguro para convertir a JSON.
        return {
            "codes": permisos_lista,
            "usuarios": {
                "ver": "USER_VIEW" in permisos_lista,
                "crear": "USER_CREATE" in permisos_lista,
                "editar": "USER_EDIT" in permisos_lista,
                "eliminar": "USER_DELETE" in permisos_lista
            },
            "roles": {
                "ver": "ROLE_VIEW" in permisos_lista,
                "crear": "ROLE_CREATE" in permisos_lista,
                "editar": "ROLE_EDIT" in permisos_lista,
                "eliminar": "ROLE_DELETE" in permisos_lista
            },
            "misiones": {
                "ver": "MISSION_VIEW" in permisos_lista,
                "crear": "MISSION_CREATE" in permisos_lista,
                "editar": "MISSION_EDIT" in permisos_lista,
                "eliminar": "MISSION_DELETE" in permisos_lista,
                "aprobar": "MISSION_APPROVE" in permisos_lista,
                "rechazar": "MISSION_REJECT" in permisos_lista
            },
            "configuracion": {
                "ver": "CONFIG_VIEW" in permisos_lista,
                "editar": "CONFIG_EDIT" in permisos_lista
            },
            "reportes": {
                "ver": "REPORT_VIEW" in permisos_lista,
                "exportar": "REPORT_EXPORT" in permisos_lista
            },
            "auditoria": {
                "ver": "AUDIT_VIEW" in permisos_lista
            },
            "sistema": {
                "mantener": "SYSTEM_MAINTAIN" in permisos_lista,
                "configurar": "SYSTEM_CONFIG" in permisos_lista
            }
        }

    def to_dict(self):
        """Convertir usuario a diccionario"""
        return {
            'id_usuario': self.id_usuario,
            'login_username': self.login_username,
            'is_active': self.is_active,
            'id_rol': self.id_rol,
            'personal_id_rrhh': self.personal_id_rrhh,
            'firma': self.firma,
            'rol': self.rol.to_dict() if self.rol else None,
            'permisos': self.get_permissions()
        }

    def has_permission(self, permission_code: str) -> bool:
        return self.rol.has_permission(permission_code) if self.rol else False

    @classmethod
    def create_employee(cls, db_session, username: str, password_hash: str, personal_id: Optional[int] = None) -> "Usuario":
        """
        Crea un nuevo usuario con rol de empleado (id_rol = 1)
        """
        nuevo_usuario = cls(
            login_username=username,
            password_hash=password_hash,
            personal_id_rrhh=personal_id,
            id_rol=1  # Rol de empleado por defecto
        )
        db_session.add(nuevo_usuario)
        db_session.commit()
        db_session.refresh(nuevo_usuario)
        return nuevo_usuario
