from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from sqlalchemy.orm import relationship, Mapped, mapped_column
from typing import Optional, TYPE_CHECKING
from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .user import Usuario
    from .mission import Mision

class Notificacion(Base, TimestampMixin):
    __tablename__ = "notificaciones"
    __table_args__ = {'extend_existing': True}
    
    notificacion_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    titulo: Mapped[str] = mapped_column(String(100), nullable=False)
    descripcion: Mapped[str] = mapped_column(String(200), nullable=False)
    personal_id: Mapped[int] = mapped_column(Integer, nullable=False)
    id_mision: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("misiones.id_mision"), nullable=True)
    visto: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Relaciones
    mision: Mapped[Optional["Mision"]] = relationship("Mision", back_populates="notificaciones")
    
    def to_dict(self):
        return {
            'notificacion_id': self.notificacion_id,
            'titulo': self.titulo,
            'descripcion': self.descripcion,
            'personal_id': self.personal_id,
            'id_mision': self.id_mision,
            'visto': self.visto,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
