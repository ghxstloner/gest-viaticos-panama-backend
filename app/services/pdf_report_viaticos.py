import io
from typing import Optional, Union, List, Dict
from datetime import datetime
from decimal import Decimal
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib import colors
from reportlab.platypus import Image

from ..models.mission import Mision
from ..models.user import Usuario

class PDFReportViaticosService:
    def __init__(self, db):
        self.db = db
        # Estilos para el PDF
        self.styles = {
            'Normal': ParagraphStyle('Normal', fontSize=10, fontName='Helvetica'),
        }
        
        # Estilos específicos
        self.field_label_style = ParagraphStyle('FieldLabel', parent=self.styles['Normal'], 
                                              fontSize=6, fontName='Helvetica-Bold')
        self.field_data_style = ParagraphStyle('FieldData', parent=self.styles['Normal'], 
                                             fontSize=6, fontName='Helvetica-Bold')
        self.table_header_style = ParagraphStyle('TableHeader', parent=self.styles['Normal'], 
                                               fontSize=5, fontName='Helvetica-Bold', alignment=TA_CENTER)
        self.table_data_style = ParagraphStyle('TableData', parent=self.styles['Normal'], 
                                             fontSize=7, fontName='Helvetica-Bold', alignment=TA_CENTER, wordWrap='CJK')
        
        # IDs de usuarios para firmas
        self.signature_user_ids = {
            'tesoreria': 2,
            'presupuesto': 4,
            'contabilidad': 5,
            'finanzas': 6
        }
        
        # Definir el orden de los estados en el flujo
        self.estados_orden = [
            'BORRADOR',
            'PENDIENTE_JEFE',
            'PENDIENTE_REVISION_TESORERIA',
            'PENDIENTE_ASIGNACION_PRESUPUESTO',
            'PENDIENTE_CONTABILIDAD',
            'PENDIENTE_APROBACION_FINANZAS',
            'PENDIENTE_REFRENDO_CGR',
            'APROBADO_PARA_PAGO',
            'PAGADO'
        ]
    
    def _get_required_signatures_for_state(self, mission, estado_actual: str) -> Dict[str, Dict]:
        """
        Determina qué firmas deben mostrarse según el estado actual de la misión y los IDs de aprobadores.
        Retorna un diccionario con información de los usuarios que aprobaron.
        """
        required_signatures = {}
        
        try:
            print(f"🔍 _get_required_signatures_for_state - Mission ID: {mission.id_mision}")
            print(f"🔍 _get_required_signatures_for_state - Estado actual: {estado_actual}")
            print(f"🔍 _get_required_signatures_for_state - IDs: jefe={mission.id_jefe}, tesoreria={mission.id_tesoreria}, presupuesto={mission.id_presupuesto}, contabilidad={mission.id_contabilidad}, finanzas={mission.id_finanzas}")
            
            # Estados que indican que la misión ha pasado por cada departamento
            # Estados que indican que la misión ha pasado por cada departamento
            # Incluir más estados para asegurar que las firmas aparezcan
            estados_tesoreria = ['PENDIENTE_ASIGNACION_PRESUPUESTO', 'PENDIENTE_CONTABILIDAD', 
                               'PENDIENTE_APROBACION_FINANZAS', 'PENDIENTE_REFRENDO_CGR', 
                               'APROBADO_PARA_PAGO', 'PAGADO', 'DEVUELTO_CORRECCION']
            
            estados_presupuesto = ['PENDIENTE_CONTABILIDAD', 'PENDIENTE_APROBACION_FINANZAS', 
                                 'PENDIENTE_REFRENDO_CGR', 'APROBADO_PARA_PAGO', 'PAGADO', 
                                 'DEVUELTO_CORRECCION']
            
            estados_contabilidad = ['PENDIENTE_APROBACION_FINANZAS', 'PENDIENTE_REFRENDO_CGR', 
                                  'APROBADO_PARA_PAGO', 'PAGADO', 'DEVUELTO_CORRECCION']
            
            estados_finanzas = ['PENDIENTE_REFRENDO_CGR', 'APROBADO_PARA_PAGO', 'PAGADO']
            
            # También mostrar firmas si el estado está en una etapa anterior pero hay ID asignado
            # (significa que ya pasó por esa etapa en algún momento)
            
            # Obtener información del jefe (si existe)
            if mission.id_jefe:
                print(f"🔍 _get_required_signatures_for_state - Procesando jefe ID: {mission.id_jefe}")
                jefe_signature = self._get_jefe_signature(mission.id_jefe)
                jefe_name = self._get_employee_name_from_rrhh(mission.id_jefe)
                print(f"🔍 _get_required_signatures_for_state - Jefe signature: {jefe_signature}, name: {jefe_name}")
                
                if jefe_signature and jefe_name:
                    required_signatures['jefe'] = {
                        'user_id': mission.id_jefe,
                        'signature_path': jefe_signature,
                        'name': jefe_name,
                        'is_jefe': True
                    }
                    print(f"🔍 _get_required_signatures_for_state - Jefe agregado a required_signatures")
        except Exception as e:
            print(f"❌ Error en _get_required_signatures_for_state (jefe): {e}")
            import traceback
            traceback.print_exc()
        
        # Determinar qué firmas de usuarios financieros mostrar
        # Mostrar firma si: (estado actual indica que pasó por esa etapa) O (hay ID asignado)
        try:
            # TESORERÍA
            if (estado_actual in estados_tesoreria or mission.id_tesoreria) and mission.id_tesoreria:
                print(f"🔍 _get_required_signatures_for_state - Procesando tesoreria ID: {mission.id_tesoreria}")
                user_signature = self._get_user_signature(mission.id_tesoreria)
                user_name = self._get_user_name(mission.id_tesoreria)
                print(f"🔍 _get_required_signatures_for_state - Tesoreria signature: {user_signature}, name: {user_name}")
                # Incluir siempre si hay ID asignado
                required_signatures['tesoreria'] = {
                    'user_id': mission.id_tesoreria,
                    'signature_path': user_signature,
                    'name': user_name or 'Tesorería',
                    'is_jefe': False
                }
                print(f"🔍 _get_required_signatures_for_state - Tesoreria agregada a required_signatures")
                
            # PRESUPUESTO
            if (estado_actual in estados_presupuesto or mission.id_presupuesto) and mission.id_presupuesto:
                print(f"🔍 _get_required_signatures_for_state - Procesando presupuesto ID: {mission.id_presupuesto}")
                user_signature = self._get_user_signature(mission.id_presupuesto)
                user_name = self._get_user_name(mission.id_presupuesto)
                print(f"🔍 _get_required_signatures_for_state - Presupuesto signature: {user_signature}, name: {user_name}")
                # Incluir siempre si hay ID asignado
                required_signatures['presupuesto'] = {
                    'user_id': mission.id_presupuesto,
                    'signature_path': user_signature,
                    'name': user_name or 'Presupuesto',
                    'is_jefe': False
                }
                print(f"🔍 _get_required_signatures_for_state - Presupuesto agregado a required_signatures")
                
            # CONTABILIDAD
            if (estado_actual in estados_contabilidad or mission.id_contabilidad) and mission.id_contabilidad:
                print(f"🔍 _get_required_signatures_for_state - Procesando contabilidad ID: {mission.id_contabilidad}")
                user_signature = self._get_user_signature(mission.id_contabilidad)
                user_name = self._get_user_name(mission.id_contabilidad)
                print(f"🔍 _get_required_signatures_for_state - Contabilidad signature: {user_signature}, name: {user_name}")
                # Incluir siempre si hay ID asignado
                required_signatures['contabilidad'] = {
                    'user_id': mission.id_contabilidad,
                    'signature_path': user_signature,
                    'name': user_name or 'Contabilidad',
                    'is_jefe': False
                }
                print(f"🔍 _get_required_signatures_for_state - Contabilidad agregada a required_signatures")
                
            # FINANZAS
            if (estado_actual in estados_finanzas or mission.id_finanzas) and mission.id_finanzas:
                print(f"🔍 _get_required_signatures_for_state - Procesando finanzas ID: {mission.id_finanzas}")
                user_signature = self._get_user_signature(mission.id_finanzas)
                user_name = self._get_user_name(mission.id_finanzas)
                print(f"🔍 _get_required_signatures_for_state - Finanzas signature: {user_signature}, name: {user_name}")
                # Incluir siempre si hay ID asignado
                required_signatures['finanzas'] = {
                    'user_id': mission.id_finanzas,
                    'signature_path': user_signature,
                    'name': user_name or 'Finanzas',
                    'is_jefe': False
                }
                print(f"🔍 _get_required_signatures_for_state - Finanzas agregado a required_signatures")
        except Exception as e:
            print(f"❌ Error en _get_required_signatures_for_state (usuarios financieros): {e}")
            import traceback
            traceback.print_exc()
            
        print(f"🔍 _get_required_signatures_for_state - Required signatures final: {list(required_signatures.keys())}")
        return required_signatures

    def _get_user_signature(self, user_id: int) -> Optional[str]:
        """Obtener firma de un usuario específico"""
        try:
            from sqlalchemy import text
            result = self.db.execute(text("""
                SELECT firma FROM usuarios 
                WHERE id_usuario = :user_id AND firma IS NOT NULL
            """), {"user_id": user_id})
            row = result.fetchone()
            return row.firma if row else None
        except Exception as e:
            print(f"Error obteniendo firma del usuario {user_id}: {e}")
            return None

    def _get_jefe_signature(self, jefe_id: int) -> Optional[str]:
        """Obtener firma del jefe desde la tabla firmas_jefes"""
        try:
            from sqlalchemy import text
            result = self.db.execute(text("""
                SELECT firma FROM firmas_jefes 
                WHERE personal_id = :jefe_id AND firma IS NOT NULL
            """), {"jefe_id": jefe_id})
            row = result.fetchone()
            return row.firma if row else None
        except Exception as e:
            print(f"Error obteniendo firma del jefe {jefe_id}: {e}")
            return None

    def _get_employee_name_from_rrhh(self, personal_id: int) -> Optional[str]:
        """Obtener nombre del empleado desde la tabla nompersonal de RRHH"""
        try:
            from sqlalchemy import text
            result = self.db.execute(text("""
                SELECT apenom FROM aitsa_rrhh.nompersonal 
                WHERE personal_id = :personal_id
            """), {"personal_id": personal_id})
            row = result.fetchone()
            return row.apenom if row else None
        except Exception as e:
            print(f"Error obteniendo nombre del empleado {personal_id}: {e}")
            return None

    def _get_user_name(self, user_id: int) -> Optional[str]:
        """Obtener nombre del usuario financiero desde la tabla usuarios y nompersonal"""
        try:
            from sqlalchemy import text
            result = self.db.execute(text("""
                SELECT np.apenom 
                FROM usuarios u
                JOIN aitsa_rrhh.nompersonal np ON u.personal_id_rrhh = np.personal_id
                WHERE u.id_usuario = :user_id
            """), {"user_id": user_id})
            row = result.fetchone()
            return row.apenom if row else None
        except Exception as e:
            print(f"Error obteniendo nombre del usuario {user_id}: {e}")
            return None

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
    
    def _get_beneficiary_details(self, personal_id: int) -> dict:
        """Obtener detalles completos del beneficiario"""
        print(f"🔍 _get_beneficiary_details - Personal ID: {personal_id}")
        
        try:
            from sqlalchemy import text
            query = """
                SELECT 
                    np.cedula,
                    np.apenom,
                    np.nomposicion_id,
                    npos.descripcion_posicion
                FROM aitsa_rrhh.nompersonal np
                LEFT JOIN aitsa_rrhh.nomposicion npos ON np.nomposicion_id = npos.nomposicion_id
                WHERE np.personal_id = :personal_id
            """
            print(f"🔍 _get_beneficiary_details - Query: {query}")
            print(f"🔍 _get_beneficiary_details - Parámetros: {{'personal_id': {personal_id}}}")
            
            result = self.db.execute(text(query), {"personal_id": personal_id})
            row = result.fetchone()
            
            print(f"🔍 _get_beneficiary_details - Resultado: {row}")
            
            if row:
                detalles = {
                    'cedula': row.cedula or '8-655-1886',  # valor por defecto si es NULL
                    'planilla': '',  # Este campo no está en la tabla, se deja vacío
                    'posicion': str(row.nomposicion_id) if row.nomposicion_id else '4673',
                    'cargo': row.descripcion_posicion or 'Ingeniero Civil'
                }
                print(f"🔍 _get_beneficiary_details - Detalles obtenidos: {detalles}")
                return detalles
            else:
                print(f"🔍 _get_beneficiary_details - No se encontraron datos para personal_id: {personal_id}")
                # Valores por defecto basados en la imagen
                return {
                    'cedula': '8-655-1886',
                    'planilla': '',
                    'posicion': '4673',
                    'cargo': 'Ingeniero Civil'
                }
        except Exception as e:
            print(f"❌ Error obteniendo detalles del beneficiario: {e}")
            return {
                'cedula': '8-655-1886',
                'planilla': '',
                'posicion': '4673',
                'cargo': 'Ingeniero Civil'
            }
    
    def _get_beneficiary_vicepresidency(self, personal_id: int) -> str:
        """Obtener vicepresidencia del beneficiario"""
        print(f"🔍 _get_beneficiary_vicepresidency - Personal ID: {personal_id}")

        try:
            from sqlalchemy import text
            query = """
                SELECT n1.descrip 
                FROM aitsa_rrhh.nompersonal np
                JOIN aitsa_rrhh.nomnivel1 n1 ON np.codnivel1 = n1.codorg
                WHERE np.personal_id = :personal_id
            """
            print(f"🔍 _get_beneficiary_vicepresidency - Query: {query}")
            print(f"🔍 _get_beneficiary_vicepresidency - Parámetros: {{'personal_id': {personal_id}}}")

            result = self.db.execute(text(query), {"personal_id": personal_id})
            row = result.fetchone()

            print(f"🔍 _get_beneficiary_vicepresidency - Resultado: {row}")
            vicepresidencia = row.descrip if row and row.descrip else "Vicepresidencia no especificada"
            print(f"🔍 _get_beneficiary_vicepresidency - Vicepresidencia obtenida: {vicepresidencia}")

            return vicepresidencia
        except Exception as e:
            print(f"❌ Error obteniendo vicepresidencia del beneficiario: {e}")
            return "Vicepresidencia no especificada"

    def _get_vicepresidency_chief_name(self, beneficiario_personal_id: int) -> str:
        """Obtener nombre del jefe de la vicepresidencia del beneficiario"""
        print(f"🔍 _get_vicepresidency_chief_name - Beneficiario personal_id: {beneficiario_personal_id}")
        
        try:
            from sqlalchemy import text
            query = """
                SELECT 
                    vp_chief.apenom
                FROM aitsa_rrhh.nompersonal beneficiario
                JOIN aitsa_rrhh.nomnivel1 vicepresidencia ON beneficiario.codnivel1 = vicepresidencia.codorg
                JOIN aitsa_rrhh.nompersonal vp_chief ON vicepresidencia.personal_id = vp_chief.personal_id
                WHERE beneficiario.personal_id = :beneficiario_personal_id
            """
            print(f"🔍 _get_vicepresidency_chief_name - Query: {query}")
            print(f"🔍 _get_vicepresidency_chief_name - Parámetros: {{'beneficiario_personal_id': {beneficiario_personal_id}}}")
            
            result = self.db.execute(text(query), {"beneficiario_personal_id": beneficiario_personal_id})
            row = result.fetchone()
            
            print(f"🔍 _get_vicepresidency_chief_name - Resultado: {row}")
            jefe_nombre = row.apenom if row else f"Jefe no encontrado para ID: {beneficiario_personal_id}"
            print(f"🔍 _get_vicepresidency_chief_name - Jefe obtenido: {jefe_nombre}")
            
            return jefe_nombre
        except Exception as e:
            print(f"❌ Error obteniendo jefe de vicepresidencia: {e}")
            return f"Error - ID: {beneficiario_personal_id}"

    def generate_viaticos_transporte_pdf(
        self,
        mission: Mision,
        user: Union[Usuario, dict],
        numero_solicitud: Optional[str] = None
    ) -> io.BytesIO:
        """Generar PDF de solicitud de viáticos y transporte con formato oficial de Tocumen"""
        
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer, 
            pagesize=letter, 
            rightMargin=15*mm, 
            leftMargin=15*mm,
            topMargin=15*mm, 
            bottomMargin=15*mm
        )
        
        story = []
        
        # ENCABEZADO SUPERIOR - Logo y títulos en la misma fila
        header_data = [
            [   
                Image("app/static/logo.jpg", width=25*mm, height=20*mm),
                Paragraph("REPÚBLICA DE PANAMÁ<br/>AEROPUERTO INTERNACIONAL DE TOCUMEN, S.A.<br/>SOLICITUD Y PAGO DE VIÁTICOS Y TRANSPORTE", 
                         ParagraphStyle('Center', parent=self.styles['Normal'], alignment=TA_CENTER, fontSize=12, fontName='Helvetica-Bold'))
            ]
        ]
        
        header_table = Table(header_data, colWidths=[40*mm, 150*mm, 40*mm])
        header_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        story.append(header_table)
        story.append(Spacer(1, 3*mm))
        
        # Número de solicitud y fecha en la misma línea
        header_info_data = [
            # Primera fila: N. de Solicitud y Fecha
            [
                Paragraph("N. de Solicitud:", self.field_label_style),
                Paragraph(f"<u>{numero_solicitud or mission.numero_solicitud or '_________________'}</u>", self.field_data_style),
                Paragraph("Fecha (dd/mm/aaaa):", self.field_label_style),
                Paragraph(f"<u>{datetime.now().strftime('%d/%m/%Y')}</u>", self.field_data_style)
            ],
            # Segunda fila: Unidad Administrativa (span across all columns)
            [
                Paragraph("Unidad Administrativa Solicitante:", self.field_label_style),
                Paragraph(f"<u>{self._get_beneficiary_vicepresidency(mission.beneficiario_personal_id)}</u>", self.field_data_style),
                Paragraph("", self.field_data_style),  # Celda vacía
                Paragraph("", self.field_data_style)   # Celda vacía
            ]
        ]
        
        header_info_table = Table(header_info_data, colWidths=[40*mm, 50*mm, 40*mm, 50*mm])
        header_info_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),  # Labels alineados a la izquierda
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),  # Datos alineados a la izquierda
            ('ALIGN', (2, 0), (2, -1), 'LEFT'),  # Labels alineados a la izquierda
            ('ALIGN', (3, 0), (3, -1), 'LEFT'),  # Datos alineados a la izquierda
            # Opcional: span para la unidad administrativa si quieres que ocupe más espacio
            ('SPAN', (1, 1), (3, 1)),  # Hacer que el departamento ocupe 3 columnas
        ]))
        story.append(header_info_table)
        story.append(Spacer(1, 5*mm))
        
        # INFORMACIÓN DEL SOLICITANTE/BENEFICIARIO
        print(f"🔍 generate_viaticos_transporte_pdf - Mission ID: {mission.id_mision}")
        print(f"🔍 generate_viaticos_transporte_pdf - Beneficiario personal_id: {mission.beneficiario_personal_id}")
        print(f"🔍 generate_viaticos_transporte_pdf - User: {user}")
        
        beneficiary_name = self._get_beneficiary_name(mission.beneficiario_personal_id)
        print(f"🔍 generate_viaticos_transporte_pdf - Beneficiary name: {beneficiary_name}")
        
        beneficiary_vicepresidency_chief_name = self._get_vicepresidency_chief_name(mission.beneficiario_personal_id)
        print(f"🔍 generate_viaticos_transporte_pdf - Vicepresidency chief name: {beneficiary_vicepresidency_chief_name}")
        
        beneficiary_details = self._get_beneficiary_details(mission.beneficiario_personal_id)
        print(f"🔍 generate_viaticos_transporte_pdf - Beneficiary details: {beneficiary_details}")
        
        beneficiary_vicepresidency = self._get_beneficiary_vicepresidency(mission.beneficiario_personal_id)
        print(f"🔍 generate_viaticos_transporte_pdf - Beneficiary vicepresidency: {beneficiary_vicepresidency}")
        
        # OBJETIVO DE LA MISIÓN
        objetivo_text = f" El suscrito:   <b><u>{beneficiary_vicepresidency_chief_name}</u></b>    solicita tramitar la solicitud de pago de viático y hospedaje para la ejecución de la Misión Oficial: <br/>{mission.objetivo_mision or 'No especificado'}"
        objetivo_data = [
            [Paragraph(objetivo_text, self.field_data_style)]
        ]
        objetivo_table = Table(objetivo_data, colWidths=[190*mm])
        objetivo_table.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        story.append(objetivo_table)
        story.append(Spacer(1, 3*mm))
        
        # DESTINO Y TRANSPORTE - Diseño corregido
        fecha_salida = mission.fecha_salida.strftime('%d/%m/%Y') if mission.fecha_salida else "No especificada"
        fecha_retorno = mission.fecha_retorno.strftime('%d/%m/%Y') if mission.fecha_retorno else "No especificada"
        hora_salida = mission.fecha_salida.strftime('%H:%M') if mission.fecha_salida else "No especificada"
        hora_retorno = mission.fecha_retorno.strftime('%H:%M') if mission.fecha_retorno else "No especificada"

        destino_transporte_data = [
            # Primera fila: Destino ocupa toda la fila
            [
                Paragraph("Destino de la Misión Oficial", self.field_label_style),
                Paragraph(mission.destino_mision or "No especificado", self.field_data_style),
                "",
                "",
                "",
                ""
            ],
            # Segunda fila: Transporte Oficial con fechas y horas
            [
                Paragraph("Transporte Oficial", self.field_label_style),
                Paragraph("Sí/No", self.field_data_style),
                Paragraph("Fecha de Salida (dd/mm/aaaa)", self.field_label_style),
                Paragraph(fecha_salida, self.field_data_style),
                Paragraph("Hora de Salida (hh:mm)", self.field_label_style),
                Paragraph(hora_salida, self.field_data_style),
            ],
            # Tercera fila: Respuesta del transporte con fecha y hora de retorno
            [
                "",  # Celda vacía porque "Transporte Oficial" hace span vertical
                Paragraph("☑ Sí" if mission.transporte_oficial else "☐ Sí", self.field_data_style),
                Paragraph("Fecha de Retorno (dd/mm/aaaa)", self.field_label_style),
                Paragraph(fecha_retorno, self.field_data_style),
                Paragraph("Hora de Retorno (hh:mm)", self.field_label_style),
                Paragraph(hora_retorno, self.field_data_style),
            ]
        ]

        destino_transporte_table = Table(destino_transporte_data, colWidths=[30*mm, 25*mm, 40*mm, 30*mm, 35*mm, 30*mm])
        destino_transporte_table.setStyle(TableStyle([
            # Span para el destino (primera fila)
            ('SPAN', (1, 0), (5, 0)),  # Destino ocupa desde columna 1 hasta 5

            # SPAN VERTICAL para Transporte Oficial (columna 0, filas 1 y 2)
            ('SPAN', (0, 1), (0, 2)),  # "Transporte Oficial" ocupa filas 1 y 2

            # Bordes
            ('GRID', (0, 0), (-1, -1), 1, colors.black),

            # Estilos de fuente
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),

            # Alineación
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),  # Primera columna a la izquierda
            ('ALIGN', (1, 0), (-1, -1), 'LEFT'),  # Resto a la izquierda
        ]))
        story.append(destino_transporte_table)
        story.append(Spacer(1, 3*mm))
        
        # TABLA DE INFORMACIÓN DEL BENEFICIARIO
        categoria_mapping = {
            'TITULAR': 'TITULAR',
            'OTROS_SERVIDORES_PUBLICOS': 'OTROS SERVIDORES PÚBLICOS',
            'OTRAS_PERSONAS': 'OTRAS PERSONAS'
        }
        categoria_display = categoria_mapping.get(mission.categoria_beneficiario.value if mission.categoria_beneficiario else '', 'OTROS SERVIDORES PÚBLICOS')
        
        # Crear tabla de información del beneficiario
        beneficiario_data = [
            # Fila de encabezados con fondo azul
            [
                Paragraph("A favor de (Beneficiario)", 
                         ParagraphStyle('Header', parent=self.styles['Normal'], fontSize=8, fontName='Helvetica-Bold', alignment=TA_CENTER)),
                Paragraph("Cédula", 
                         ParagraphStyle('Header', parent=self.styles['Normal'], fontSize=8, fontName='Helvetica-Bold', alignment=TA_CENTER)),
                Paragraph("Planilla", 
                         ParagraphStyle('Header', parent=self.styles['Normal'], fontSize=8, fontName='Helvetica-Bold', alignment=TA_CENTER)),
                Paragraph("Posición", 
                         ParagraphStyle('Header', parent=self.styles['Normal'], fontSize=8, fontName='Helvetica-Bold', alignment=TA_CENTER)),
                Paragraph("Cargo Según Función", 
                         ParagraphStyle('Header', parent=self.styles['Normal'], fontSize=8, fontName='Helvetica-Bold', alignment=TA_CENTER)),
                Paragraph("Categoría", 
                         ParagraphStyle('Header', parent=self.styles['Normal'], fontSize=8, fontName='Helvetica-Bold', alignment=TA_CENTER))
            ],
            # Fila de datos
            [
                Paragraph(beneficiary_name, 
                         ParagraphStyle('DataCenter', parent=self.styles['Normal'], fontSize=8, fontName='Helvetica', alignment=TA_CENTER)),
                Paragraph(beneficiary_details['cedula'], 
                         ParagraphStyle('DataCenter', parent=self.styles['Normal'], fontSize=8, fontName='Helvetica', alignment=TA_CENTER)),
                Paragraph(beneficiary_details['planilla'], 
                         ParagraphStyle('DataCenter', parent=self.styles['Normal'], fontSize=8, fontName='Helvetica', alignment=TA_CENTER)),
                Paragraph(beneficiary_details['posicion'], 
                         ParagraphStyle('DataCenter', parent=self.styles['Normal'], fontSize=8, fontName='Helvetica', alignment=TA_CENTER)),
                Paragraph(beneficiary_details['cargo'], 
                         ParagraphStyle('DataCenter', parent=self.styles['Normal'], fontSize=8, fontName='Helvetica', alignment=TA_CENTER)),
                Paragraph(categoria_display, 
                         ParagraphStyle('DataCenter', parent=self.styles['Normal'], fontSize=8, fontName='Helvetica', alignment=TA_CENTER))
            ]
        ]
        
        beneficiario_table = Table(beneficiario_data, colWidths=[45*mm, 25*mm, 20*mm, 20*mm, 40*mm, 40*mm])
        beneficiario_table.setStyle(TableStyle([
            # Bordes
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            
            # Fondo gris para los encabezados (primera fila)
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),  # Gris claro
            
            # Fondo azul para la celda de categoría (última columna, segunda fila)
            ('BACKGROUND', (5, 1), (5, 1), colors.Color(0.7, 0.85, 1.0)),  # Celda categoría
            
            # Alineación y formato de texto
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            
            # Fuente para encabezados
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 8),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),  # Texto negro para encabezados
            
            # Fuente para datos
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),  # Texto negro para datos
        ]))
        
        story.append(beneficiario_table)
        story.append(Spacer(1, 3*mm))
        
        # SECCIÓN VIÁTICOS - ESTRUCTURA CORRECTA
        viaticos_headers = [
            # Fila 1: "MISIÓN OFICIAL DENTRO DEL PAÍS" con fondo azul
            [
                Paragraph("MISIÓN OFICIAL DENTRO DEL PAÍS", 
                         ParagraphStyle('Center', parent=self.styles['Normal'], alignment=TA_CENTER, 
                                       fontSize=10, fontName='Helvetica-Bold')),
                Paragraph("", self.table_data_style),
                Paragraph("", self.table_data_style),
                Paragraph("", self.table_data_style),
                Paragraph("", self.table_data_style),
                Paragraph("", self.table_data_style),
                Paragraph("", self.table_data_style),
                Paragraph("", self.table_data_style),
                Paragraph("", self.table_data_style)
            ],
            # Fila 2: "Viáticos Completos" | "Viáticos Parciales" con fondo gris
            [
                Paragraph("Viáticos Completos", self.table_header_style),
                Paragraph("", self.table_data_style),
                Paragraph("", self.table_data_style),
                Paragraph("Viáticos Parciales", self.table_header_style),
                Paragraph("", self.table_data_style),
                Paragraph("", self.table_data_style),
                Paragraph("", self.table_data_style),
                Paragraph("", self.table_data_style),
                Paragraph("", self.table_data_style)
            ],
            # Fila 3: Títulos de columnas sin fondo
            [
                Paragraph("Cant. de días", self.table_header_style),
                Paragraph("Pago por día", self.table_header_style),
                Paragraph("Monto", self.table_header_style),
                Paragraph("Fecha (dd/mm/aaaa)", self.table_header_style),
                Paragraph("Desayuno", self.table_header_style),
                Paragraph("Almuerzo", self.table_header_style),
                Paragraph("Cena", self.table_header_style),
                Paragraph("Hospedaje", self.table_header_style),
                Paragraph("Monto", self.table_header_style)
            ]
        ]

        # Datos de viáticos
        viaticos_data = viaticos_headers.copy()

        # Calcular cuántas filas necesitamos
        max_viaticos_completos = len(mission.items_viaticos_completos) if hasattr(mission, 'items_viaticos_completos') and mission.items_viaticos_completos else 0
        max_viaticos_parciales = len(mission.items_viaticos) if mission.items_viaticos else 0
        max_filas = max(max_viaticos_completos, max_viaticos_parciales, 6)  # Mínimo 6 filas

        # Crear listas de datos para cada sección
        viaticos_completos_data = []
        if hasattr(mission, 'items_viaticos_completos') and mission.items_viaticos_completos:
            for item in mission.items_viaticos_completos:
                monto = item.cantidad_dias * item.monto_por_dia
                viaticos_completos_data.append([
                    str(item.cantidad_dias),
                    f"B/. {item.monto_por_dia:,.2f}",
                    f"B/. {monto:,.2f}"
                ])

        viaticos_parciales_data = []
        if mission.items_viaticos:
            for item in mission.items_viaticos:
                total_item = (item.monto_desayuno or 0) + (item.monto_almuerzo or 0) + (item.monto_cena or 0) + (item.monto_hospedaje or 0)
                viaticos_parciales_data.append([
                    item.fecha.strftime('%d/%m/%Y'),
                    f"B/. {item.monto_desayuno or 0:,.2f}",
                    f"B/. {item.monto_almuerzo or 0:,.2f}",
                    f"B/. {item.monto_cena or 0:,.2f}",
                    f"B/. {item.monto_hospedaje or 0:,.2f}",
                    f"B/. {total_item:,.2f}"
                ])

        # Llenar las filas con datos independientes
        for i in range(max_filas):
            row = []

            # Datos de viáticos completos (primeras 3 columnas)
            if i < len(viaticos_completos_data):
                row.extend([
                    Paragraph(viaticos_completos_data[i][0], self.table_data_style),
                    Paragraph(viaticos_completos_data[i][1], self.table_data_style),
                    Paragraph(viaticos_completos_data[i][2], self.table_data_style)
                ])
            else:
                row.extend([
                    Paragraph("", self.table_data_style),
                    Paragraph("", self.table_data_style),
                    Paragraph("", self.table_data_style)
                ])

            # Datos de viáticos parciales (últimas 6 columnas)
            if i < len(viaticos_parciales_data):
                row.extend([
                    Paragraph(viaticos_parciales_data[i][0], self.table_data_style),
                    Paragraph(viaticos_parciales_data[i][1], self.table_data_style),
                    Paragraph(viaticos_parciales_data[i][2], self.table_data_style),
                    Paragraph(viaticos_parciales_data[i][3], self.table_data_style),
                    Paragraph(viaticos_parciales_data[i][4], self.table_data_style),
                    Paragraph(viaticos_parciales_data[i][5], self.table_data_style)
                ])
            else:
                row.extend([
                    Paragraph("", self.table_data_style),
                    Paragraph("", self.table_data_style),
                    Paragraph("", self.table_data_style),
                    Paragraph("", self.table_data_style),
                    Paragraph("", self.table_data_style),
                    Paragraph("", self.table_data_style)
                ])

            viaticos_data.append(row)

        # Calcular subtotales
        subtotal_viaticos_completos = 0
        if hasattr(mission, 'items_viaticos_completos') and mission.items_viaticos_completos:
            subtotal_viaticos_completos = sum([
                item.cantidad_dias * item.monto_por_dia
                for item in mission.items_viaticos_completos
            ])

        subtotal_viaticos_parciales = 0
        if mission.items_viaticos:
            subtotal_viaticos_parciales = sum([
                (item.monto_desayuno or 0) + (item.monto_almuerzo or 0) + (item.monto_cena or 0) + (item.monto_hospedaje or 0)
                for item in mission.items_viaticos
            ])

                # Fila de subtotal CORREGIDA
        subtotal_row = [
            Paragraph("Subtotal", self.table_header_style),  # Esta celda se expandirá
            Paragraph("", self.table_data_style),  # Esta será "consumida" por el span
            Paragraph(f"B/. {subtotal_viaticos_completos:,.2f}", self.table_data_style),  # Suma total en columna Monto
            Paragraph("", self.table_data_style),
            Paragraph("", self.table_data_style),
            Paragraph("", self.table_data_style),
            Paragraph("", self.table_data_style),
            Paragraph("Subtotal:", self.table_header_style),
            Paragraph(f"B/. {subtotal_viaticos_parciales:,.2f}", self.table_data_style)
        ]
        viaticos_data.append(subtotal_row)

        # Total de viáticos
        total_viaticos = subtotal_viaticos_completos + subtotal_viaticos_parciales
        total_viaticos_row = [
            Paragraph("TOTAL DE VIÁTICOS COMPLETOS Y PARCIALES DENTRO DEL PAÍS:", self.table_header_style),
            Paragraph("", self.table_data_style),
            Paragraph("", self.table_data_style),
            Paragraph("", self.table_data_style),
            Paragraph("", self.table_data_style),
            Paragraph("", self.table_data_style),
            Paragraph("", self.table_data_style),
            Paragraph("", self.table_data_style),
            Paragraph(f"B/. {total_viaticos:,.2f}", self.table_data_style)
        ]
        viaticos_data.append(total_viaticos_row)

        # Crear la tabla con los colores correctos
        viaticos_table = Table(viaticos_data, colWidths=[20*mm, 20*mm, 20*mm, 25*mm, 20*mm, 20*mm, 20*mm, 25*mm, 20*mm])
        viaticos_table.setStyle(TableStyle([
            # Bordes
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            # Spans
            ('SPAN', (0, 0), (8, 0)),  # "MISIÓN OFICIAL DENTRO DEL PAÍS"
            ('SPAN', (0, 1), (2, 1)),  # "Viáticos Completos"
            ('SPAN', (3, 1), (8, 1)),  # "Viáticos Parciales"
            ('SPAN', (0, -2), (1, -2)),  # NUEVO: Span para "Subtotal" en viáticos completos
            ('SPAN', (0, -1), (7, -1)),  # Span del total (primeras 8 columnas)
            # Colores de fondo
            ('BACKGROUND', (0, 0), (8, 0), colors.Color(0.7, 0.85, 1.0)),  # Azul
            ('BACKGROUND', (0, 1), (8, 1), colors.lightgrey),  # Gris

            ('BACKGROUND', (0, -2), (8, -2), colors.lightgrey),  # Subtotal gris completo
            ('BACKGROUND', (2, -2), (2, -2), colors.white),      # Solo celda con B/. en subtotal
            ('BACKGROUND', (8, -2), (8, -2), colors.white),      # Solo celda con B/. en subtotal (segundo)
            ('BACKGROUND', (0, -1), (7, -1), colors.lightgrey),  # Total gris (primeras 8 columnas)
            ('BACKGROUND', (8, -1), (8, -1), colors.white),      # Solo celda con B/. en total

            # Estilos de texto
            ('FONTNAME', (0, 0), (-1, 2), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 2), 8),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTSIZE', (0, 3), (-1, -3), 9),
            ('FONTNAME', (0, 3), (-1, -3), 'Helvetica'),
            ('FONTNAME', (0, -2), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, -2), (-1, -1), 8),
        ]))
        story.append(viaticos_table)
        story.append(Spacer(1, 5*mm))
        
        # DETALLE DE TRANSPORTE - TÍTULO DENTRO DE LA TABLA
        # Primera fila: Título "DETALLE DE TRANSPORTE" con span completo
        titulo_transporte = [
            [
                Paragraph("DETALLE DE TRANSPORTE", 
                         ParagraphStyle('Left', parent=self.styles['Normal'], alignment=TA_LEFT, 
                                       fontSize=10, fontName='Helvetica-Bold')),
                Paragraph("", self.table_data_style),
                Paragraph("", self.table_data_style),
                Paragraph("", self.table_data_style),
                Paragraph("", self.table_data_style)
            ]
        ]

        # Segunda fila: Encabezados
        transporte_headers = [
            [
                Paragraph("Fecha (dd/mm/aaaa)", self.table_header_style),
                Paragraph("Tipo", self.table_header_style),
                Paragraph("Origen (desde)", self.table_header_style),
                Paragraph("Destino (hasta)", self.table_header_style),
                Paragraph("Monto", self.table_header_style)
            ]
        ]

        # Combinar título + headers + datos
        transporte_data = titulo_transporte + transporte_headers

        # Agregar datos de transporte
        total_transporte = 0
        if mission.items_transporte:
            for item in mission.items_transporte:
                total_transporte += item.monto
                # Crear estilos específicos para texto largo
                estilo_texto_largo = ParagraphStyle('TextoLargo', parent=self.styles['Normal'], 
                                                  fontSize=8, fontName='Helvetica', alignment=TA_CENTER, 
                                                  wordWrap='CJK', leading=10)
                row = [
                    Paragraph(item.fecha.strftime('%d/%m/%Y'), self.table_data_style),
                    Paragraph(item.tipo, self.table_data_style),
                    Paragraph(item.origen, estilo_texto_largo),
                    Paragraph(item.destino, estilo_texto_largo),
                    Paragraph(f"B/. {item.monto:,.2f}", self.table_data_style)
                ]
                transporte_data.append(row)

        # Agregar filas vacías hasta completar al menos 6 filas de datos
        estilo_texto_largo = ParagraphStyle('TextoLargo', parent=self.styles['Normal'], 
                                          fontSize=8, fontName='Helvetica', alignment=TA_CENTER, 
                                          wordWrap='CJK', leading=10)
        while len(transporte_data) < 11:  # 1 título + 1 header + 7 filas mínimo
            empty_row = [
                Paragraph("", self.table_data_style),
                Paragraph("", self.table_data_style),
                Paragraph("", estilo_texto_largo),
                Paragraph("", estilo_texto_largo),
                Paragraph("", self.table_data_style)
            ]
            transporte_data.append(empty_row)

        # Agregar fila de total de transporte
        total_transporte_row = [
            Paragraph("TOTAL DE VIÁTICOS Y TRANSPORTE DENTRO DEL PAÍS:", self.table_header_style),
            Paragraph("", self.table_data_style),
            Paragraph("", self.table_data_style),
            Paragraph("", self.table_data_style),
            Paragraph(f"B/. {total_viaticos + total_transporte:,.2f}", self.table_data_style)
        ]
        transporte_data.append(total_transporte_row)

        # Crear tabla sin rowHeights fijos para permitir ajuste automático
        transporte_table = Table(transporte_data, 
                                colWidths=[35*mm, 25*mm, 60*mm, 52*mm, 18*mm])

        transporte_table.setStyle(TableStyle([
            # Span para el título (primera fila, todas las columnas)
            ('SPAN', (0, 0), (4, 0)),  # Título ocupa todas las columnas
            
            # Span para el total (última fila, primeras 4 columnas)
            ('SPAN', (0, -1), (3, -1)),  # Total span de columnas 0-3
            
            # Bordes
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            
            # Fondo gris para la fila del título (primera fila)
            ('BACKGROUND', (0, 0), (4, 0), colors.lightgrey),
            
            # Fondo gris para el encabezado (segunda fila)
            ('BACKGROUND', (0, 1), (4, 1), colors.lightgrey),
            
            # Estilos de texto para el título (primera fila)
            ('FONTNAME', (0, 0), (4, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (4, 0), 10),
            ('ALIGN', (0, 0), (4, 0), 'LEFT'),  # Título alineado a la izquierda
            ('VALIGN', (0, 0), (4, 0), 'MIDDLE'),
            
            # Estilos de texto para encabezados (segunda fila)
            ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 1), (-1, 1), 8),
            ('ALIGN', (0, 1), (-1, 1), 'CENTER'),
            ('VALIGN', (0, 1), (-1, 1), 'MIDDLE'),
            
            # Estilos de texto para datos (filas intermedias)
            ('FONTSIZE', (0, 2), (-1, -2), 9),
            ('FONTNAME', (0, 2), (-1, -2), 'Helvetica'),
            ('ALIGN', (0, 2), (-1, -2), 'CENTER'),
            ('VALIGN', (0, 2), (-1, -2), 'MIDDLE'),
            # Configuración para texto largo
            ('LEFTPADDING', (0, 2), (-1, -2), 2),
            ('RIGHTPADDING', (0, 2), (-1, -2), 2),
            ('TOPPADDING', (0, 2), (-1, -2), 1),
            ('BOTTOMPADDING', (0, 2), (-1, -2), 1),
            
            # Estilos para la fila de total (última fila)
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, -1), (-1, -1), 8),
            ('ALIGN', (0, -1), (-1, -1), 'CENTER'),
            ('VALIGN', (0, -1), (-1, -1), 'MIDDLE'),
            ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),  # Fondo gris para total
            ('BACKGROUND', (-1, -1), (-1, -1), colors.white),     # Fondo blanco para la celda con B/.
        ]))
        story.append(transporte_table)
        story.append(Spacer(1, 3*mm))

        # MISIÓN OFICIAL EN EL EXTERIOR DEL PAÍS - ESTRUCTURA CORREGIDA CON MISMO ANCHO
        # Primera fila: Título con fondo azul
        exterior_titulo = [
            [
                Paragraph("MISIÓN OFICIAL EN EL EXTERIOR DEL PAÍS", 
                         ParagraphStyle('Center', parent=self.styles['Normal'], alignment=TA_CENTER, 
                                       fontSize=10, fontName='Helvetica-Bold')),
                Paragraph("", self.table_data_style),
                Paragraph("", self.table_data_style),
                Paragraph("", self.table_data_style),
                Paragraph("", self.table_data_style),
                Paragraph("", self.table_data_style),
                Paragraph("", self.table_data_style),
                Paragraph("", self.table_data_style)
            ]
        ]

        # Segunda fila: Encabezados (SIN la columna Total)
        exterior_headers = [
            [
                Paragraph("Destino", self.table_header_style),
                Paragraph("**Región", self.table_header_style),
                Paragraph("**Fecha de Salida (dd/mm/aaaa)", self.table_header_style),
                Paragraph("**Fecha de Retorno (dd/mm/aaaa)", self.table_header_style),
                Paragraph("Días", self.table_header_style),
                Paragraph("Pago por día", self.table_header_style),
                Paragraph("%", self.table_header_style),
                Paragraph("Subtotal", self.table_header_style)
            ]
        ]

        # Combinar título + headers
        exterior_data = exterior_titulo + exterior_headers

        # Agregar datos de misiones al exterior si existen
        total_exterior = 0
        if hasattr(mission, 'items_misiones_exterior') and mission.items_misiones_exterior:
            for item in mission.items_misiones_exterior:
                dias = (item.fecha_retorno - item.fecha_salida).days + 1
                # Calcular pago por día según región
                pago_por_dia = Decimal("100")  # Valor ejemplo
                porcentaje = item.porcentaje or Decimal("100")
                subtotal = dias * pago_por_dia * (porcentaje / 100)
                total_exterior += subtotal
                
                row = [
                    Paragraph(item.destino, self.table_data_style),
                    Paragraph(item.region, self.table_data_style),
                    Paragraph(item.fecha_salida.strftime('%d/%m/%Y'), self.table_data_style),
                    Paragraph(item.fecha_retorno.strftime('%d/%m/%Y'), self.table_data_style),
                    Paragraph(str(dias), self.table_data_style),
                    Paragraph(f"B/. {pago_por_dia:,.2f}", self.table_data_style),
                    Paragraph(f"{porcentaje}%", self.table_data_style),
                    Paragraph(f"B/. {subtotal:,.2f}", self.table_data_style)
                ]
                exterior_data.append(row)

        # Agregar filas vacías hasta completar al menos 3 filas de datos
        while len(exterior_data) < 6:  # 1 título + 1 header + 4 filas mínimo
            empty_row = [Paragraph("", self.table_data_style) for _ in range(8)]
            exterior_data.append(empty_row)

        # Agregar fila de total de misiones al exterior
        total_exterior_row = [
            Paragraph("TOTAL DE VIÁTICOS Y TRANSPORTE EN EL EXTERIOR:", self.table_header_style),
            Paragraph("", self.table_data_style),
            Paragraph("", self.table_data_style),
            Paragraph("", self.table_data_style),
            Paragraph("", self.table_data_style),
            Paragraph("", self.table_data_style),
            Paragraph("", self.table_data_style),
            Paragraph(f"B/. {total_exterior:,.2f}", self.table_data_style)
        ]
        exterior_data.append(total_exterior_row)

        # Crear tabla con el MISMO ANCHO que las otras tablas (190mm total)
        exterior_table = Table(exterior_data, colWidths=[28*mm, 22*mm, 28*mm, 28*mm, 18*mm, 24*mm, 18*mm, 24*mm])
        exterior_table.setStyle(TableStyle([
            # Spans
            ('SPAN', (0, 0), (7, 0)),   # Título ocupa todas las columnas (0-7)
            ('SPAN', (0, -1), (6, -1)), # Total span de columnas 0-6
            
            # Bordes
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            
            # Colores de fondo
            ('BACKGROUND', (0, 0), (7, 0), colors.Color(0.7, 0.85, 1.0)),  # Azul para título
            ('BACKGROUND', (0, 1), (7, 1), colors.lightgrey),              # Gris para headers
            
            # Estilos de texto para el título (primera fila)
            ('FONTNAME', (0, 0), (7, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (7, 0), 10),
            ('ALIGN', (0, 0), (7, 0), 'CENTER'),
            ('VALIGN', (0, 0), (7, 0), 'MIDDLE'),
            
            # Estilos de texto para encabezados (segunda fila)
            ('FONTNAME', (0, 1), (7, 1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 1), (7, 1), 8),
            ('ALIGN', (0, 1), (7, 1), 'CENTER'),
            ('VALIGN', (0, 1), (7, 1), 'MIDDLE'),
            
            # Estilos de texto para datos
            ('FONTSIZE', (0, 2), (-1, -2), 9),
            ('FONTNAME', (0, 2), (-1, -2), 'Helvetica'),
            ('ALIGN', (0, 2), (-1, -2), 'CENTER'),
            ('VALIGN', (0, 2), (-1, -2), 'MIDDLE'),
            
            # Estilos para la fila de total (última fila)
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, -1), (-1, -1), 8),
            ('ALIGN', (0, -1), (-1, -1), 'CENTER'),
            ('VALIGN', (0, -1), (-1, -1), 'MIDDLE'),
            ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),  # Fondo gris para total
            ('BACKGROUND', (-1, -1), (-1, -1), colors.white),     # Fondo blanco para la celda con B/.
        ]))
        story.append(exterior_table)
        story.append(Spacer(1, 5*mm))
        
        # PARTIDAS PRESUPUESTARIAS - SOLO TABLA IZQUIERDA
        partidas_header = [
            [
                Paragraph("Partidas Presupuestarias", 
                         ParagraphStyle('Center', parent=self.styles['Normal'], alignment=TA_CENTER, 
                                       fontSize=10, fontName='Helvetica-Bold'))
            ]
        ]
        
        partidas_data = partidas_header.copy()
        
        # Agregar partidas presupuestarias
        if mission.partidas_presupuestarias:
            for partida in mission.partidas_presupuestarias:
                row = [
                    Paragraph(f"{partida.codigo_partida}:", self.table_data_style),
                    Paragraph(f"B/. {partida.monto:,.2f}", self.table_data_style)
                ]
                partidas_data.append(row)
        else:
            # Filas vacías por defecto
            for _ in range(3):
                row = [
                    Paragraph("", self.table_data_style),
                    Paragraph("", self.table_data_style)
                ]
                partidas_data.append(row)
        
        # Total
        total_partidas = sum([p.monto for p in mission.partidas_presupuestarias]) if mission.partidas_presupuestarias else mission.monto_total_calculado
        total_partidas_row = [
            Paragraph("Total:", self.table_header_style),
            Paragraph(f"B/. {total_partidas:,.2f}", self.table_header_style)
        ]
        partidas_data.append(total_partidas_row)
        
        partidas_table = Table(partidas_data, colWidths=[75*mm, 20*mm])
        partidas_table.setStyle(TableStyle([
            # Bordes
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            
            # Spans
            ('SPAN', (0, 0), (1, 0)),  # Header ocupa ambas columnas
            
            # Colores de fondo
            ('BACKGROUND', (0, 0), (1, 0), colors.lightgrey),  # Header gris
            ('BACKGROUND', (0, -1), (0, -1), colors.lightgrey),  # Total gris
            ('BACKGROUND', (1, -1), (1, -1), colors.white),      # Total monto blanco
            
            # Estilos de texto
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
            
            # Estilos para datos
            ('FONTSIZE', (0, 1), (-1, -2), 9),
            ('FONTNAME', (0, 1), (-1, -2), 'Helvetica'),
            ('ALIGN', (0, 1), (0, -2), 'LEFT'),    # Código alineado a la izquierda
            ('ALIGN', (1, 1), (1, -2), 'RIGHT'),    # Monto alineado a la derecha
            ('VALIGN', (0, 1), (-1, -2), 'MIDDLE'),
            
            # Estilos para total
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, -1), (-1, -1), 8),
            ('ALIGN', (0, -1), (0, -1), 'CENTER'),  # Total texto centrado
            ('ALIGN', (1, -1), (1, -1), 'RIGHT'),    # Total monto a la derecha
            ('VALIGN', (0, -1), (-1, -1), 'MIDDLE'),
            
            # Forzar alineación izquierda de toda la tabla
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ]))
        # TABLA DE FIRMA SEPARADA
        firma_data = [
            [
                Paragraph("Nombre y Firma del Responsable de la Unidad Administrativa Solicitante:", 
                         ParagraphStyle('Center', parent=self.styles['Normal'], alignment=TA_CENTER, 
                                       fontSize=10, fontName='Helvetica-Bold'))
            ]
        ]
        
        # Agregar filas vacías para la firma
        for _ in range(5):  # Mismo número de filas que partidas
            firma_data.append([Paragraph("", self.table_data_style)])
        
        firma_table = Table(firma_data, colWidths=[95*mm])
        firma_table.setStyle(TableStyle([
            # Bordes
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            
            # Colores de fondo
            ('BACKGROUND', (0, 0), (0, 0), colors.lightgrey),  # Header gris
            
            # Estilos de texto
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
            
            # Estilos para datos
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('ALIGN', (0, 1), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 1), (-1, -1), 'MIDDLE'),
        ]))

                
        # Obtener información de la vicepresidencia y vicepresidente (para el solicitante)
        beneficiary_vicepresidency = self._get_beneficiary_vicepresidency(mission.beneficiario_personal_id)
        vicepresidency_chief_name = self._get_vicepresidency_chief_name(mission.beneficiario_personal_id)
        
        # Obtener firmas requeridas según el estado actual y los IDs de aprobadores reales
        try:
            required_signatures = self._get_required_signatures_for_state(mission, mission.estado_flujo.nombre_estado)
            print(f"🔍 generate_viaticos_transporte_pdf - Required signatures obtenidas: {list(required_signatures.keys())}")
        except Exception as e:
            print(f"❌ Error obteniendo required_signatures: {e}")
            required_signatures = {}
        

        

      
        
        # Crear elementos de firma para cada departamento usando los usuarios que realmente aprobaron
        tesoreria_element = Paragraph("", self.table_data_style)
        presupuesto_element = Paragraph("", self.table_data_style)
        contabilidad_element = Paragraph("", self.table_data_style)
        finanzas_element = Paragraph("", self.table_data_style)
        
        try:
            if 'tesoreria' in required_signatures:
                signature_path = required_signatures['tesoreria'].get('signature_path')
                if signature_path:
                    tesoreria_element = Image(signature_path, width=40*mm, height=15*mm)
                    print(f"🔍 generate_viaticos_transporte_pdf - Tesoreria element creado con firma: {signature_path}")
                
            if 'presupuesto' in required_signatures:
                signature_path = required_signatures['presupuesto'].get('signature_path')
                if signature_path:
                    presupuesto_element = Image(signature_path, width=40*mm, height=15*mm)
                    print(f"🔍 generate_viaticos_transporte_pdf - Presupuesto element creado con firma: {signature_path}")
                
            if 'contabilidad' in required_signatures:
                signature_path = required_signatures['contabilidad'].get('signature_path')
                if signature_path:
                    contabilidad_element = Image(signature_path, width=40*mm, height=15*mm)
                    print(f"🔍 generate_viaticos_transporte_pdf - Contabilidad element creado con firma: {signature_path}")
                
            if 'finanzas' in required_signatures:
                signature_path = required_signatures['finanzas'].get('signature_path')
                if signature_path:
                    finanzas_element = Image(signature_path, width=40*mm, height=15*mm)
                    print(f"🔍 generate_viaticos_transporte_pdf - Finanzas element creado con firma: {signature_path}")
        except Exception as e:
            print(f"❌ Error creando elementos de firma: {e}")
            import traceback
            traceback.print_exc()
        
        # Obtener información del jefe que realmente autorizó (si existe)
        jefe_name = None
        jefe_signature_element = Paragraph("", self.table_data_style)
        
        try:
            if 'jefe' in required_signatures:
                jefe_info = required_signatures['jefe']
                jefe_name = jefe_info.get('name')
                signature_path = jefe_info.get('signature_path')
                if signature_path:
                    jefe_signature_element = Image(signature_path, width=40*mm, height=15*mm)
                    print(f"🔍 generate_viaticos_transporte_pdf - Jefe signature element creado: {signature_path}")
            
            # Si no hay jefe específico, usar la información de vicepresidencia como fallback
            if not jefe_name:
                jefe_name = f"{beneficiary_vicepresidency} - {vicepresidency_chief_name}"
                print(f"🔍 generate_viaticos_transporte_pdf - Usando jefe fallback: {jefe_name}")
        except Exception as e:
            print(f"❌ Error procesando información del jefe: {e}")
            jefe_name = f"{beneficiary_vicepresidency} - {vicepresidency_chief_name}"
            jefe_signature_element = Paragraph("", self.table_data_style)
        
        # TABLA DE FIRMA (al lado de partidas presupuestarias)
        # Esta tabla contiene tanto el responsable de la unidad como el que autoriza
        firma_data = [
            [Paragraph("Nombre y Firma del Responsable de la Unidad Administrativa Solicitante:", 
                      ParagraphStyle('Left', parent=self.styles['Normal'], alignment=TA_LEFT, fontSize=9))],
            [Paragraph(f"{beneficiary_vicepresidency} - {vicepresidency_chief_name}", 
                      ParagraphStyle('Left', parent=self.styles['Normal'], alignment=TA_LEFT, fontSize=9))],
            [Paragraph("", self.table_data_style)],   # Espacio vacío
            [Paragraph("Nombre y Firma del Responsable que Autoriza el Trámite de la Solicitud y Pago de Viático y Transporte:", 
                      ParagraphStyle('Left', parent=self.styles['Normal'], alignment=TA_LEFT, fontSize=9))],
            [Paragraph(jefe_name, 
                      ParagraphStyle('Left', parent=self.styles['Normal'], alignment=TA_LEFT, fontSize=9))],
            [jefe_signature_element]   # Firma real del jefe o espacio vacío
        ]
        print(f"🔍 generate_viaticos_transporte_pdf - firma_data creada con jefe: {jefe_name}")

        firma_row_heights = [10*mm, 6*mm, 15*mm, 10*mm, 6*mm, 15*mm]  # 6 filas

        # Crear tabla de firma con estructura correcta (sin colores)
        firma_table = Table(firma_data, colWidths=[95*mm], rowHeights=firma_row_heights)
        firma_table.setStyle(TableStyle([
            # Bordes
            ('GRID', (0, 0), (-1, -1), 1, colors.black),

            # Estilos de texto (sin colores de fondo)
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),  # Todo alineado a la izquierda
            ('ALIGN', (0, 5), (0, 5), 'CENTER'),  # Firma del jefe centrada horizontalmente
            ('VALIGN', (0, 0), (0, 1), 'TOP'),    # Header y texto arriba
            ('VALIGN', (0, 2), (0, 2), 'MIDDLE'), # Espacio de firma centrado verticalmente
            ('VALIGN', (0, 3), (0, 4), 'TOP'),    # Header y texto del jefe arriba
            ('VALIGN', (0, 5), (0, 5), 'MIDDLE'), # Espacio de firma del jefe centrado
        ]))
        
        print(f"🔍 generate_viaticos_transporte_pdf - firma_table creada correctamente")
        
        # Crear el contenedor side-by-side con partidas y firmas
        side_by_side_data = [
            [partidas_table, firma_table]
        ]
        
        # Tabla contenedora que respeta los márgenes y bordes
        side_by_side_container = Table(side_by_side_data, colWidths=[95*mm, 95*mm])
        side_by_side_container.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))
        
        story.append(side_by_side_container)
        story.append(Spacer(1, 10*mm))
        
        # TABLA DE FIRMAS DE PREPARADOR Y BENEFICIARIO
        firmas_data = [
            [
                Paragraph("Nombre y Firma de quien Prepara el Formulario", 
                        ParagraphStyle('Left', parent=self.styles['Normal'], alignment=TA_LEFT, fontSize=9)),
                Paragraph("Nombre y Firma del Beneficiario", 
                        ParagraphStyle('Left', parent=self.styles['Normal'], alignment=TA_LEFT, fontSize=9))
            ],
            [
                Paragraph("", self.table_data_style),  # Espacio para firma del preparador
                Paragraph("", self.table_data_style)   # Firma del beneficiario
            ]
        ]

        # Definir alturas para mantener consistencia visual
        firmas_row_heights = [12*mm, 20*mm]  # Total: 32mm

        firmas_table = Table(firmas_data, colWidths=[95*mm, 95*mm], rowHeights=firmas_row_heights)
        firmas_table.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, 0), 'TOP'),    # Texto arriba
            ('VALIGN', (0, 1), (-1, 1), 'MIDDLE'), # Espacio firma centrado
            ('FONTSIZE', (0, 0), (-1, -1), 9),
        ]))
        story.append(firmas_table)
        story.append(Spacer(1, 5*mm))
        
        # DEPARTAMENTOS DE AUTORIZACIÓN
        dept_data = [
            [
                Paragraph("Nombre y Firma del Director de Administración y/o Finanzas:", 
                         ParagraphStyle('Left', parent=self.styles['Normal'], alignment=TA_LEFT, fontSize=9)),
                Paragraph("Nombre y Firma de la Máxima Autoridad:", 
                         ParagraphStyle('Left', parent=self.styles['Normal'], alignment=TA_LEFT, fontSize=9))
            ],
            [
                Paragraph("", self.table_data_style),
                Paragraph("", self.table_data_style)
            ],
            [
                finanzas_element,
                Paragraph("", self.table_data_style)   # Espacio para firma de máxima autoridad
            ]
        ]

        # Alturas: header + nombre + espacio firma
        dept_row_heights = [8*mm, 6*mm, 18*mm]  # Total: 32mm

        dept_table = Table(dept_data, colWidths=[95*mm, 95*mm], rowHeights=dept_row_heights)
        dept_table.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('VALIGN', (0, 0), (-1, 1), 'TOP'),    # Headers y nombres arriba
            ('VALIGN', (0, 2), (-1, 2), 'MIDDLE'), # Espacio firma centrado
            ('ALIGN', (0, 2), (-1, 2), 'CENTER'),  # Firmas centradas horizontalmente
        ]))
        story.append(dept_table)
        story.append(Spacer(1, 5*mm))
        
        # DEPARTAMENTOS FINALES (Tesorería, Contabilidad, Presupuesto)
        final_depts_data = [
            [
                Paragraph("DEPARTAMENTO DE TESORERÍA<br/>SELLO, FECHA Y FIRMA", 
                         ParagraphStyle('Left', parent=self.styles['Normal'], alignment=TA_LEFT, fontSize=9)),
                Paragraph("DEPARTAMENTO DE CONTABILIDAD<br/>SELLO, FECHA Y FIRMA", 
                         ParagraphStyle('Left', parent=self.styles['Normal'], alignment=TA_LEFT, fontSize=9)),
                Paragraph("DEPARTAMENTO DE PRESUPUESTO<br/>SELLO, FECHA Y FIRMA", 
                         ParagraphStyle('Left', parent=self.styles['Normal'], alignment=TA_LEFT, fontSize=9))
            ],
            [
                tesoreria_element,
                contabilidad_element,
                presupuesto_element
            ]
        ]

        # Alturas: header + espacio para sello/firma
        final_depts_row_heights = [10*mm, 22*mm]  # Total: 32mm

        final_depts_table = Table(final_depts_data, colWidths=[63*mm, 63*mm, 64*mm], rowHeights=final_depts_row_heights)
        final_depts_table.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('VALIGN', (0, 0), (-1, 0), 'TOP'),    # Headers arriba
            ('VALIGN', (0, 1), (-1, 1), 'MIDDLE'), # Espacio sello/firma centrado
            ('ALIGN', (0, 1), (-1, 1), 'CENTER'),  # Firmas centradas horizontalmente
        ]))
        story.append(final_depts_table)
        story.append(Spacer(1, 5*mm))
        
        # OFICINA DE FISCALIZACIÓN (CGR) - Siempre mostrar la tabla, pero solo la firma cuando corresponda
        estados_cgr = ['PENDIENTE_REFRENDO_CGR', 'APROBADO_PARA_PAGO', 'PAGADO', 'DEVUELTO_CORRECCION']
        
        # Obtener firma de CGR si corresponde
        cgr_signature = None
        if mission.estado_flujo.nombre_estado in estados_cgr:
            # Aquí podrías obtener la firma de CGR si tienes un usuario específico
            # cgr_signature = self._get_user_signature(self.signature_user_ids.get('cgr'))
            pass
        
        # Crear elemento de firma para CGR
        cgr_element = Image(cgr_signature, width=40*mm, height=15*mm) if cgr_signature else Paragraph("", self.table_data_style)
        
        fiscalizacion_data = [
            [
                Paragraph("OFICINA DE FISCALIZACIÓN GENERAL DE LA CGR<br/>SELLO, FECHA Y REFRENDO", 
                         ParagraphStyle('Center', parent=self.styles['Normal'], alignment=TA_CENTER, fontSize=8, fontName='Helvetica-Bold'))
            ],
            [
                cgr_element  # Firma de CGR (vacía si no corresponde)
            ]
        ]

        # Alturas: header + espacio para sello/refrendo
        fiscalizacion_row_heights = [10*mm, 22*mm]  # Total: 32mm

        fiscalizacion_table = Table(fiscalizacion_data, colWidths=[190*mm], rowHeights=fiscalizacion_row_heights)
        fiscalizacion_table.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (0, 0), 'TOP'),    # Header arriba
            ('VALIGN', (0, 1), (0, 1), 'MIDDLE'), # Espacio sello/refrendo centrado
            ('ALIGN', (0, 1), (0, 1), 'CENTER'),  # Firma centrada horizontalmente
            ('FONTSIZE', (0, 1), (-1, -1), 9),
        ]))
        story.append(fiscalizacion_table)
        
        # Generar PDF
        doc.build(story)
        buffer.seek(0)
        return buffer