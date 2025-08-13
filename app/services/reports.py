from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, func, extract
from datetime import datetime, date, timedelta
from decimal import Decimal
import io
import xlsxwriter

from ..models.mission import Mision, EstadoFlujo, HistorialFlujo
from ..models.user import Usuario
from ..models.enums import TipoMision
from .pdf_reports import PDFReportService


class ReportService:
    def __init__(self, db: Session, current_user: Optional[Usuario] = None):
        self.db = db
        self.current_user = current_user

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

    def get_dashboard_stats(self, user: Usuario) -> Dict[str, Any]:
        """Obtener estadísticas del dashboard"""
        # Obtener fechas para el mes actual
        today = date.today()
        start_of_month = today.replace(day=1)
        
        # Total de misiones según el rol del usuario
        base_query = self._get_base_query(user)
        
        # Estadísticas generales
        total_misiones = base_query.count()
        
        # Estadísticas por estado
        estado_counts = self.db.query(
            EstadoFlujo.nombre_estado,
            func.count(Mision.id_mision).label('count')
        ).join(
            Mision, EstadoFlujo.id_estado_flujo == Mision.id_estado_flujo
        ).filter(
            self._apply_user_filter(user, Mision)
        ).group_by(EstadoFlujo.nombre_estado).all()
        
        # Contar por categorías
        pendientes_revision = 0
        aprobadas_mes = 0
        rechazadas_mes = 0
        
        for estado, count in estado_counts:
            if estado in ['PENDIENTE_REVISION', 'PENDIENTE_JEFE', 'PENDIENTE_TESORERIA', 'PENDIENTE_PRESUPUESTO']:
                pendientes_revision += count
            elif estado in ['APROBADO', 'PAGADO']:
                aprobadas_mes += count
            elif estado in ['RECHAZADO', 'DEVUELTO']:
                rechazadas_mes += count
        
        # Monto total del mes
        monto_total_mes = self.db.query(
            func.sum(Mision.monto_total_calculado)
        ).filter(
            and_(
                Mision.created_at >= start_of_month,
                self._apply_user_filter(user, Mision)
            )
        ).scalar() or Decimal('0.00')
        
        return {
            "total_misiones": total_misiones,
            "pendientes_revision": pendientes_revision,
            "aprobadas_mes": aprobadas_mes,
            "rechazadas_mes": rechazadas_mes,
            "monto_total_mes": float(monto_total_mes)
        }

    def generate_complete_solicitudes_report(
        self,
        tipo_mision: Optional[str] = None,
        estado: Optional[str] = None,
        fecha_desde: Optional[str] = None,
        fecha_hasta: Optional[str] = None,
        fecha_salida: Optional[str] = None,
        fecha_retorno: Optional[str] = None,
        monto_min: Optional[float] = None,
        monto_max: Optional[float] = None
    ) -> io.BytesIO:
        """Generar reporte completo de todas las solicitudes con información detallada y filtros"""
        # Query base con las relaciones necesarias
        query = self.db.query(Mision).options(
            joinedload(Mision.estado_flujo),
            joinedload(Mision.usuario_prepara),
            joinedload(Mision.historial_flujo).joinedload(HistorialFlujo.usuario_accion),
            joinedload(Mision.historial_flujo).joinedload(HistorialFlujo.estado_nuevo)
        )
        
        # Aplicar filtros
        if estado:
            query = query.join(EstadoFlujo).filter(EstadoFlujo.nombre_estado == estado)
        
        if tipo_mision:
            # Convertir string a enum si es necesario
            tipo_enum = TipoMision(tipo_mision) if isinstance(tipo_mision, str) else tipo_mision
            query = query.filter(Mision.tipo_mision == tipo_enum)
        
        if fecha_desde:
            query = query.filter(Mision.created_at >= fecha_desde)
        
        if fecha_hasta:
            query = query.filter(Mision.created_at <= fecha_hasta)
        
        if fecha_salida:
            query = query.filter(Mision.fecha_salida == fecha_salida)
        
        if fecha_retorno:
            query = query.filter(Mision.fecha_retorno == fecha_retorno)
        
        if monto_min:
            query = query.filter(Mision.monto_total_calculado >= monto_min)
        
        if monto_max:
            query = query.filter(Mision.monto_total_calculado <= monto_max)
        
        # Obtener misiones filtradas
        missions = query.order_by(Mision.created_at.desc()).all()
        
        return self._generate_complete_excel_report(missions)

    def _apply_user_filter(self, user: Usuario, model_class):
        """Aplicar filtros basados en el rol del usuario"""
        if user.rol.nombre_rol == "Administrador Sistema":
            return True  # Los admins ven todo
        elif user.rol.nombre_rol == "Solicitante":
            return model_class.beneficiario_personal_id == user.personal_id_rrhh
        elif user.rol.nombre_rol in ["Jefe Inmediato", "Analista Tesorería", "Director Finanzas"]:
            return True  # Los roles de aprobación ven todo
        else:
            return model_class.beneficiario_personal_id == user.personal_id_rrhh

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

    def _generate_complete_excel_report(self, missions: List[Mision]) -> io.BytesIO:
        """Generar reporte Excel completo con todos los campos solicitados"""
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output)
        worksheet = workbook.add_worksheet('Solicitudes Completas')
        
        # Formatos - mismos colores que PDF
        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#D3D3D3',  # Equivalente a colors.lightgrey
            'font_color': 'black',
            'border': 1,
            'text_wrap': True,
            'valign': 'top'
        })
        
        date_format = workbook.add_format({
            'num_format': 'dd/mm/yyyy',
            'border': 1
        })
        
        money_format = workbook.add_format({
            'num_format': '#,##0.00',
            'border': 1
        })
        
        text_format = workbook.add_format({
            'border': 1,
            'text_wrap': True,
            'valign': 'top'
        })
        
        # Headers con los campos solicitados
        headers = [
            'Número de Solicitud',
            'Tipo',
            'Nombre del Solicitante',
            'Categoría de Beneficiario',
            'Objetivo de la Misión',
            'Destino de la Misión',
            'Tipo de Viaje',
            'Región del Exterior',
            'Fecha de Salida',
            'Fecha de Retorno',
            'Estado',
            'Monto Total',
            'Monto Aprobado',
            'Aprobado por Jefe',
            'Aprobado por Tesorería',
            'Aprobado por Presupuesto',
            'Aprobado por Contabilidad',
            'Aprobado por Finanzas'
        ]
        
        # Escribir título principal (filas 0 y 1 combinadas) - color personalizado
        title_format = workbook.add_format({
            'bold': True,
            'bg_color': '#001689',  # Color hexadecimal personalizado
            'font_color': 'white',  # Texto blanco
            'font_size': 16,
            'border': 1,
            'text_wrap': True,
            'valign': 'vcenter',
            'align': 'center'
        })
        
        # Combinar celdas para el título principal
        worksheet.merge_range(0, 0, 1, len(headers)-1, 'REPORTE COMPLETO DE SOLICITUDES DE VIÁTICOS', title_format)
        
        # Escribir headers en la fila 2
        for col, header in enumerate(headers):
            worksheet.write(2, col, header, header_format)
        
        # Datos
        for row, mission in enumerate(missions, 3):
            # Número de solicitud
            worksheet.write(row, 0, mission.numero_solicitud or f"MISION-{mission.id_mision}", text_format)
            
            # Tipo (quitar guiones bajos)
            tipo_limpio = mission.tipo_mision.value.replace('_', ' ') if mission.tipo_mision.value else ''
            worksheet.write(row, 1, tipo_limpio, text_format)
            
            # Nombre del solicitante
            solicitante_nombre = self._get_beneficiary_name(mission.beneficiario_personal_id)
            worksheet.write(row, 2, solicitante_nombre, text_format)
            
            # Categoría de beneficiario (quitar guiones bajos)
            categoria_limpia = mission.categoria_beneficiario.replace('_', ' ') if mission.categoria_beneficiario else ''
            worksheet.write(row, 3, categoria_limpia, text_format)
            
            # Objetivo de la misión
            worksheet.write(row, 4, mission.objetivo_mision, text_format)
            
            # Destino de la misión
            worksheet.write(row, 5, mission.destino_mision, text_format)
            
            # Tipo de viaje
            worksheet.write(row, 6, mission.tipo_viaje.value, text_format)
            
            # Región del exterior (solo si es internacional)
            region_exterior = mission.region_exterior if mission.tipo_viaje.value == "INTERNACIONAL" else ""
            worksheet.write(row, 7, region_exterior, text_format)
            
            # Fecha de salida
            worksheet.write(row, 8, mission.fecha_salida, date_format)
            
            # Fecha de retorno
            worksheet.write(row, 9, mission.fecha_retorno, date_format)
            
            # Estado (quitar guiones bajos)
            estado_nombre = mission.estado_flujo.nombre_estado if mission.estado_flujo else ''
            estado_limpio = estado_nombre.replace('_', ' ') if estado_nombre else ''
            worksheet.write(row, 10, estado_limpio, text_format)
            
            # Monto total
            worksheet.write(row, 11, float(mission.monto_total_calculado), money_format)
            
            # Monto aprobado
            monto_aprobado = float(mission.monto_aprobado) if mission.monto_aprobado else 0.0
            worksheet.write(row, 12, monto_aprobado, money_format)
             
            # Usuarios que aprobaron (columnas separadas)
            aprobadores = self._get_approval_users_separated(mission)
            worksheet.write(row, 13, aprobadores.get('jefe', '') or 'Sin aprobar', text_format)
            worksheet.write(row, 14, aprobadores.get('tesoreria', '') or 'Sin aprobar', text_format)
            worksheet.write(row, 15, aprobadores.get('presupuesto', '') or 'Sin aprobar', text_format)
            worksheet.write(row, 16, aprobadores.get('contabilidad', '') or 'Sin aprobar', text_format)
            worksheet.write(row, 17, aprobadores.get('finanzas', '') or 'Sin aprobar', text_format)
        
        # Ajustar anchos de columna
        worksheet.set_column('A:A', 20)  # Número de solicitud
        worksheet.set_column('B:B', 15)  # Tipo
        worksheet.set_column('C:C', 35)  # Nombre del solicitante
        worksheet.set_column('D:D', 25)  # Categoría de beneficiario
        worksheet.set_column('E:E', 50)  # Objetivo de la misión
        worksheet.set_column('F:F', 30)  # Destino de la misión
        worksheet.set_column('G:G', 15)  # Tipo de viaje
        worksheet.set_column('H:H', 20)  # Región del exterior
        worksheet.set_column('I:J', 15)  # Fechas
        worksheet.set_column('K:K', 15)  # Estado
        worksheet.set_column('L:M', 15)  # Montos
        worksheet.set_column('N:R', 20)  # Aprobadores separados
        
        workbook.close()
        output.seek(0)
        return output

    def _generate_pdf_report(self, missions: List[Mision]) -> io.BytesIO:
        """Generar reporte PDF"""
        pdf_service = PDFReportService(self.db)
        return pdf_service.generate_missions_pdf_report(missions, self.current_user)

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

    def _get_approval_users(self, mission: Mision) -> str:
        """Obtener lista de usuarios que aprobaron la misión"""
        aprobadores = []
        
        # Obtener usuarios específicos que aprobaron según los campos de la misión
        if mission.id_tesoreria:
            usuario = self.db.query(Usuario).filter(Usuario.id_usuario == mission.id_tesoreria).first()
            if usuario:
                aprobadores.append(f"Tesorería: {usuario.login_username}")
        
        if mission.id_presupuesto:
            usuario = self.db.query(Usuario).filter(Usuario.id_usuario == mission.id_presupuesto).first()
            if usuario:
                aprobadores.append(f"Presupuesto: {usuario.login_username}")
        
        if mission.id_contabilidad:
            usuario = self.db.query(Usuario).filter(Usuario.id_usuario == mission.id_contabilidad).first()
            if usuario:
                aprobadores.append(f"Contabilidad: {usuario.login_username}")
        
        if mission.id_finanzas:
            usuario = self.db.query(Usuario).filter(Usuario.id_usuario == mission.id_finanzas).first()
            if usuario:
                aprobadores.append(f"Finanzas: {usuario.login_username}")
        
        if mission.id_jefe:
            usuario = self.db.query(Usuario).filter(Usuario.id_usuario == mission.id_jefe).first()
            if usuario:
                aprobadores.append(f"Jefe: {usuario.login_username}")
        
        # También obtener del historial de flujo
        for historial in mission.historial_flujo:
            if historial.tipo_accion == "APROBAR" and historial.usuario_accion:
                aprobadores.append(f"{historial.estado_nuevo.nombre_estado}: {historial.usuario_accion.login_username}")
        
        # Eliminar duplicados y unir
        aprobadores_unicos = list(dict.fromkeys(aprobadores))
        return "; ".join(aprobadores_unicos) if aprobadores_unicos else "Sin aprobaciones"

    def _get_approval_users_separated(self, mission: Mision) -> Dict[str, str]:
        """Obtener usuarios que aprobaron la misión separados por tipo"""
        aprobadores = {
            'jefe': '',
            'tesoreria': '',
            'presupuesto': '',
            'contabilidad': '',
            'finanzas': ''
        }
        
        # Obtener usuarios específicos que aprobaron según los campos de la misión
        if mission.id_jefe:
            # Para jefes inmediatos, obtener de nompersonal
            jefe_nombre = self._get_beneficiary_name(mission.id_jefe)
            if jefe_nombre and not jefe_nombre.startswith('ID:'):
                aprobadores['jefe'] = jefe_nombre
        
        if mission.id_tesoreria:
            usuario = self.db.query(Usuario).filter(Usuario.id_usuario == mission.id_tesoreria).first()
            if usuario:
                aprobadores['tesoreria'] = usuario.login_username
        
        if mission.id_presupuesto:
            usuario = self.db.query(Usuario).filter(Usuario.id_usuario == mission.id_presupuesto).first()
            if usuario:
                aprobadores['presupuesto'] = usuario.login_username
        
        if mission.id_contabilidad:
            usuario = self.db.query(Usuario).filter(Usuario.id_usuario == mission.id_contabilidad).first()
            if usuario:
                aprobadores['contabilidad'] = usuario.login_username
        
        if mission.id_finanzas:
            usuario = self.db.query(Usuario).filter(Usuario.id_usuario == mission.id_finanzas).first()
            if usuario:
                aprobadores['finanzas'] = usuario.login_username
        
        # También obtener del historial de flujo para complementar
        for historial in mission.historial_flujo:
            if historial.tipo_accion == "APROBAR" and historial.usuario_accion:
                estado = historial.estado_nuevo.nombre_estado.lower()
                if 'jefe' in estado and not aprobadores['jefe']:
                    # Para jefes del historial, también obtener de nompersonal si es un personal_id
                    if hasattr(historial.usuario_accion, 'personal_id_rrhh') and historial.usuario_accion.personal_id_rrhh:
                        jefe_nombre = self._get_beneficiary_name(historial.usuario_accion.personal_id_rrhh)
                        if jefe_nombre and not jefe_nombre.startswith('ID:'):
                            aprobadores['jefe'] = jefe_nombre
                    else:
                        aprobadores['jefe'] = historial.usuario_accion.login_username
                elif 'tesorería' in estado or 'tesoreria' in estado and not aprobadores['tesoreria']:
                    aprobadores['tesoreria'] = historial.usuario_accion.login_username
                elif 'presupuesto' in estado and not aprobadores['presupuesto']:
                    aprobadores['presupuesto'] = historial.usuario_accion.login_username
                elif 'contabilidad' in estado and not aprobadores['contabilidad']:
                    aprobadores['contabilidad'] = historial.usuario_accion.login_username
                elif 'finanzas' in estado and not aprobadores['finanzas']:
                    aprobadores['finanzas'] = historial.usuario_accion.login_username
        
        return aprobadores