from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from ..models.base import Base


class Department(Base):
    __tablename__ = "departamentos"
    
    id_departamento = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(250), nullable=False)
    ruta_sello = Column(String(250), nullable=True)
    
    # Relación con usuarios
    usuarios = relationship("Usuario", back_populates="departamento")
