from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, func, extract
from datetime import datetime, date, timedelta
from decimal import Decimal
import io
import xlsxwriter

from ..models.mission import Mision, EstadoFlujo, HistorialFlujo
from ..models.user import Usuario
from ..models.enums import TipoMision


class ReportService:
    def __init__(self, db: Session):
        self.db = db

    def generate_missions_report(
        self,
        user: Usuario,
        fecha_desde: Optional[date] = None,
        fecha_hasta: Optional[date] = None,
        tipo_mision: Optional[TipoMision] = None,
        estado_id: Optional[int] = None,
        formato: str = "excel"
    ) -> io.BytesIO:
        """Generar reporte de misiones"""
        # Obtener datos
        query = self._get_base_query(user)
        
        if fecha_desde:
            query = query.filter(Mision.fecha_salida >= fecha_desde)
        if fecha_hasta:
            query = query.filter(Mision.fecha_salida <= fecha_hasta)
        if tipo_mision:
            query = query.filter(Mision.tipo_mision == tipo_mision)
        if estado_id:
            query = query.filter(Mision.id_estado_flujo == estado_id)
        
        missions = query.order_by(Mision.created_at.desc()).all()
        
        if formato == "excel":
            return self._generate_excel_report(missions)
        else:
            return self._generate_pdf_report(missions)

    def generate_financial_summary(
        self,
        fecha_desde: date,
        fecha_hasta: date
    ) -> Dict[str, Any]:
        """Generar resumen financiero"""
        # Total solicitado
        total_solicitado = self.db.query(
            func.sum(Mision.monto_total_calculado)
        ).filter(
            and_(
                Mision.created_at >= fecha_desde,
                Mision.created_at <= fecha_hasta
            )
        ).scalar() or Decimal('0.00')
        
        # Total aprobado
        total_aprobado = self.db.query(
            func.sum(Mision.monto_aprobado)
        ).filter(
            and_(
                Mision.created_at >= fecha_desde,
                Mision.created_at <= fecha_hasta,
                Mision.monto_aprobado.isnot(None)
            )
        ).scalar() or Decimal('0.00')
        
        # Total pagado
        estado_pagado = self.db.query(EstadoFlujo).filter(
            EstadoFlujo.nombre_estado == "PAGADO"
        ).first()
        
        total_pagado = self.db.query(
            func.sum(Mision.monto_aprobado)
        ).filter(
            and_(
                Mision.created_at >= fecha_desde,
                Mision.created_at <= fecha_hasta,
                Mision.id_estado_flujo == estado_pagado.id_estado_flujo if estado_pagado else -1
            )
        ).scalar() or Decimal('0.00')
        
        # Por tipo de misión
        por_tipo = self.db.query(
            Mision.tipo_mision,
            func.count(Mision.id_mision).label('cantidad'),
            func.sum(Mision.monto_total_calculado).label('monto')
        ).filter(
            and_(
                Mision.created_at >= fecha_desde,
                Mision.created_at <= fecha_hasta
            )
        ).group_by(Mision.tipo_mision).all()
        
        return {
            "periodo": {
                "desde": fecha_desde.isoformat(),
                "hasta": fecha_hasta.isoformat()
            },
            "totales": {
                "solicitado": float(total_solicitado),
                "aprobado": float(total_aprobado),
                "pagado": float(total_pagado),
                "pendiente": float(total_aprobado - total_pagado)
            },
            "por_tipo": [
                {
                    "tipo": t.tipo_mision.value,
                    "cantidad": t.cantidad,
                    "monto": float(t.monto or 0)
                }
                for t in por_tipo
            ]
        }

    def generate_audit_trail(
        self,
        mission_id: int
    ) -> List[Dict[str, Any]]:
        """Generar rastro de auditoría de una misión"""
        history = self.db.query(HistorialFlujo).filter(
            HistorialFlujo.id_mision == mission_id
        ).order_by(HistorialFlujo.fecha_accion).all()
        
        trail = []
        for h in history:
            trail.append({
                "fecha": h.fecha_accion.isoformat(),
                "usuario": h.usuario_accion.login_username,
                "accion": h.tipo_accion.value,
                "estado_anterior": h.estado_anterior.nombre_estado if h.estado_anterior else None,
                "estado_nuevo": h.estado_nuevo.nombre_estado,
                "comentarios": h.comentarios,
                "datos_adicionales": h.datos_adicionales
            })
        
        return trail

    def _generate_excel_report(self, missions: List[Mision]) -> io.BytesIO:
        """Generar reporte Excel"""
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output)
        worksheet = workbook.add_worksheet('Misiones')
        
        # Formatos
        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#4472C4',
            'font_color': 'white',
            'border': 1
        })
        
        date_format = workbook.add_format({
            'num_format': 'dd/mm/yyyy',
            'border': 1
        })
        
        money_format = workbook.add_format({
            'num_format': '#,##0.00',
            'border': 1
        })
        
        # Headers
        headers = [
            'ID', 'Tipo', 'Beneficiario', 'Objetivo', 'Destino',
            'Fecha Salida', 'Fecha Retorno', 'Monto Solicitado',
            'Monto Aprobado', 'Estado', 'Fecha Creación'
        ]
        
        for col, header in enumerate(headers):
            worksheet.write(0, col, header, header_format)
        
        # Datos
        for row, mission in enumerate(missions, 1):
            worksheet.write(row, 0, mission.id_mision)
            worksheet.write(row, 1, mission.tipo_mision.value)
            worksheet.write(row, 2, self._get_beneficiary_name(mission.beneficiario_personal_id))
            worksheet.write(row, 3, mission.objetivo_mision)
            worksheet.write(row, 4, mission.destino_mision)
            worksheet.write(row, 5, mission.fecha_salida, date_format)
            worksheet.write(row, 6, mission.fecha_retorno, date_format)
            worksheet.write(row, 7, float(mission.monto_total_calculado), money_format)
            worksheet.write(row, 8, float(mission.monto_aprobado or 0), money_format)
            worksheet.write(row, 9, mission.estado_flujo.nombre_estado)
            worksheet.write(row, 10, mission.created_at, date_format)
        
        # Ajustar anchos de columna
        worksheet.set_column('A:A', 10)
        worksheet.set_column('B:B', 15)
        worksheet.set_column('C:C', 30)
        worksheet.set_column('D:D', 50)
        worksheet.set_column('E:E', 30)
        worksheet.set_column('F:G', 15)
        worksheet.set_column('H:I', 15)
        worksheet.set_column('J:J', 25)
        worksheet.set_column('K:K', 15)
        
        workbook.close()
        output.seek(0)
        return output

    def _generate_pdf_report(self, missions: List[Mision]) -> io.BytesIO:
        """Generar reporte PDF"""
        # TODO: Implementar generación de PDF
        pass

    def _get_base_query(self, user: Usuario):
        """Query base según permisos del usuario"""
        query = self.db.query(Mision)
        
        if user.rol.nombre_rol == "Solicitante":
            query = query.filter(Mision.beneficiario_personal_id == user.personal_id_rrhh)
        
        return query

    def _get_beneficiary_name(self, personal_id: int) -> str:
        """Obtener nombre del beneficiario"""
        try:
            from sqlalchemy import text
            result = self.db.execute(text("""
                SELECT apenom FROM aitsa_rrhh.nompersonal 
                WHERE personal_id = :personal_id
            """), {"personal_id": personal_id})
            row = result.fetchone()
            return row.apenom if row else f"ID: {personal_id}"
        except:
            return f"ID: {personal_id}"