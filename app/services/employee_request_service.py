# app/services/employee_request_service.py

from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Dict, Any

class EmployeeRequestService:
    def __init__(self, db: Session):
        self.db = db

    def get_requests_by_cedula(self, cedula: str) -> List[Dict[str, Any]]:
        """
        Obtiene las solicitudes de un empleado por su cédula, uniendo las tablas
        para obtener descripciones legibles.
        """
        query = text("""
            SELECT 
                sc.id_solicitudes_casos,
                st.descrip_solicitudes_tipos AS tipo_solicitud,
                se.descrip_solicitudes_estatus AS estado,
                sc.fecha_registro,
                sc.fecha_inicio,
                sc.fecha_fin,
                sc.observacion
            FROM solicitudes_casos sc
            LEFT JOIN solicitudes_tipos st ON sc.id_tipo_solicitud = st.id_solicitudes_tipos
            LEFT JOIN solicitudes_estatus se ON sc.id_solicitudes_casos_status = se.id_solicitudes_estatus
            WHERE sc.cedula = :cedula
            ORDER BY sc.fecha_registro DESC;
        """)
        
        try:
            result = self.db.execute(query, {"cedula": cedula})
            requests = [dict(row._mapping) for row in result.fetchall()]
            return requests
        except Exception as e:
            print(f"Error al obtener solicitudes para la cédula {cedula}: {e}")
            return []
