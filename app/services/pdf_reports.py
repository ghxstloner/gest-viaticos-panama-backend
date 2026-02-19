from typing import List, Dict, Any, Optional, Tuple, Union
from sqlalchemy.orm import Session
from datetime import datetime, date
from decimal import Decimal
import io
import textwrap
import locale

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import mm, inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.graphics.shapes import Drawing, Line

from ..models.mission import Mision, EstadoFlujo, HistorialFlujo, MisionCajaMenuda
from ..models.user import Usuario
from ..models.enums import TipoMision

locale.setlocale(locale.LC_ALL, 'es_ES.UTF-8')

class PDFReportService:
    def __init__(self, db: Session):
        self.db = db
        self.styles = getSampleStyleSheet()
        
        # Estilos personalizados para replicar el formato oficial
        self.header_style = ParagraphStyle(
            'HeaderStyle',
            parent=self.styles['Normal'],
            fontSize=12,
            fontName='Times-Roman',
            alignment=TA_CENTER,
            spaceAfter=6
        )
        self.header_style_bold = ParagraphStyle(
            'HeaderStyleBold',
            parent=self.styles['Normal'],
            fontSize=12,
            fontName='Times-Bold',
            alignment=TA_CENTER,
            spaceAfter=6,
        )
        
        self.title_style = ParagraphStyle(
            'TitleStyle',
            parent=self.styles['Normal'],
            fontSize=12,
            fontName='Times-Bold',
            alignment=TA_CENTER,
            spaceAfter=12
        )
        
        self.field_label_style = ParagraphStyle(
            'FieldLabel',
            parent=self.styles['Normal'],
            fontSize=10,
            fontName='Times-Bold'
        )
        
        self.field_data_style = ParagraphStyle(
            'FieldData',
            parent=self.styles['Normal'],
            fontSize=10,
            fontName='Times-Roman'
        )
        
        self.table_header_style = ParagraphStyle(
            'TableHeader',
            parent=self.styles['Normal'],
            fontSize=8,
            fontName='Times-Bold',
            alignment=TA_CENTER
        )
        
        self.table_data_style = ParagraphStyle(
            'TableData',
            parent=self.styles['Normal'],
            fontSize=9,
            fontName='Times-Roman',
            alignment=TA_CENTER
        )

    def generate_caja_menuda_pdf(
        self,
        caja_menuda_items: List[MisionCajaMenuda],
        mission: Mision,
        user: Usuario
    ) -> io.BytesIO:
        """Generar PDF de caja menuda con formato oficial de Tocumen"""
        
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
        
        # ENCABEZADO SUPERIOR - Alineado correctamente
        header_data = [
            [
                Image("app/static/logo.jpg", width=25*mm, height=20*mm),
                Paragraph("Gaceta Oficial Digital, " + datetime.now().strftime('%d de %B de %Y'), 
                         ParagraphStyle('Center', parent=self.styles['Normal'], alignment=TA_CENTER, fontSize=8)),
                Paragraph("Formulario " + str(mission.id_mision), 
                         ParagraphStyle('Right', parent=self.styles['Normal'], alignment=TA_RIGHT, fontSize=10, fontName='Helvetica-Bold'))
            ]
        ]
        
        header_table = Table(header_data, colWidths=[50*mm, 90*mm, 50*mm])
        header_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (0, 0), 'MIDDLE'),  # Logo al centro
            ('VALIGN', (1, 0), (1, 0), 'TOP'),     # Gaceta Oficial arriba
            ('VALIGN', (2, 0), (2, 0), 'MIDDLE'),  # Formulario al centro
        ]))
        story.append(header_table)
        story.append(Spacer(1, 3*mm))
        
        # TÍTULOS PRINCIPALES
        story.append(Paragraph("REPÚBLICA DE PANAMÁ", self.header_style_bold))
        story.append(Paragraph("AEROPUERTO INTERNACIONAL DE TOCUMEN, S.A.", self.header_style_bold))
        story.append(Paragraph("GERENCIA DE ADMINISTRACIÓN Y FINANZAS", self.header_style))
        story.append(Spacer(1, 3*mm))
        
        story.append(Paragraph("COMPROBANTE DE CAJA MENUDA ESPECIAL PARA EL PAGO DE VIÁTICOS", self.title_style))
        story.append(Spacer(1, 2*mm))
        
        # NÚMERO Y FECHA - Alineados con Formulario Núm.5
        numero_fecha_data = [
            [
                "",
                "",
                Paragraph(f"No. ___________", 
                         ParagraphStyle('Right', parent=self.styles['Normal'], alignment=TA_RIGHT, fontSize=10))
            ],
            [
                "",
                "",
                Paragraph(f"Fecha: {caja_menuda_items[0].fecha.strftime('%d/%m/%Y')}", 
                         ParagraphStyle('Right', parent=self.styles['Normal'], alignment=TA_RIGHT, fontSize=10))
            ]
        ]
        
        numero_fecha_table = Table(numero_fecha_data, colWidths=[100*mm, 40*mm, 50*mm])
        story.append(numero_fecha_table)
        story.append(Spacer(1, 2*mm))
        
        # INFORMACIÓN BÁSICA CON SUBRAYADO
        # PARA
        para_text = f"""<b>PARA:</b> <u>GERENCIA DE ADMINISTRACIÓN Y FINANZA</u>"""
        story.append(Paragraph(para_text, self.field_data_style))
        story.append(Spacer(1, 1*mm))
        
        # DE  
        beneficiary_name = self._get_beneficiary_name(mission.beneficiario_personal_id)
        de_text = f"""<b>DE:</b> <u>{beneficiary_name}</u>"""
        story.append(Paragraph(de_text, self.field_data_style))
        story.append(Spacer(1, 1*mm))
        
        # DEPTO. DE
        department = self._get_beneficiary_department(mission.beneficiario_personal_id)
        depto_text = f"""<b>DEPTO. DE:</b> EQUIPO <u>{department}</u>"""
        story.append(Paragraph(depto_text, self.field_data_style))
        story.append(Spacer(1, 1*mm))
        
        # TRABAJO A REALIZAR - CON SUBRAYADO CORREGIDO
        trabajo_text =  f"""<b>TRABAJO A REALIZAR:</b> <u>{mission.objetivo_mision}</u>"""
        story.append(Paragraph(trabajo_text, self.field_data_style))
        story.append(Spacer(1, 2*mm))


        # TABLA PRINCIPAL DE GASTOS - ESTRUCTURA CORRECTA CON ENCABEZADOS DE DOS NIVELES
        # Primera fila de encabezados - nivel superior
        header_row_1 = [
            Paragraph("FECHA", self.table_header_style),
            Paragraph("HORA", self.table_header_style),
            "",  # Vacía porque HORA abarca 2 columnas
            Paragraph("ALIMENTACIÓN", self.table_header_style),
            "",  # Vacía porque ALIMENTACIÓN abarca 3 columnas
            "",  # Vacía porque ALIMENTACIÓN abarca 3 columnas
            Paragraph("TRANSPORTE", self.table_header_style),
            Paragraph("TOTAL", self.table_header_style)
        ]

        # Segunda fila de encabezados - nivel inferior
        header_row_2 = [
            "",  # Vacía porque FECHA abarca 2 filas
            Paragraph("De", self.table_header_style),
            Paragraph("Hasta", self.table_header_style),
            Paragraph("Desayuno", self.table_header_style),
            Paragraph("Almuerzo", self.table_header_style),
            Paragraph("Cena", self.table_header_style),
            "",  # Vacía porque TRANSPORTE abarca 2 filas
            ""   # Vacía porque TOTAL abarca 2 filas
        ]

        # Datos de la tabla
        table_data = [header_row_1, header_row_2]
        total_general = 0

        for item in caja_menuda_items:
            total_dia = (item.desayuno or 0) + (item.almuerzo or 0) + \
                       (item.cena or 0) + (item.transporte or 0)
            total_general += total_dia
            
            # Formatear fecha como en el original (28-abr-25)
            fecha_formatted = item.fecha.strftime('%d-%b-%y').replace('Jan', 'ene').replace('Feb', 'feb').replace('Mar', 'mar').replace('Apr', 'abr').replace('May', 'may').replace('Jun', 'jun').replace('Jul', 'jul').replace('Aug', 'ago').replace('Sep', 'sep').replace('Oct', 'oct').replace('Nov', 'nov').replace('Dec', 'dic')
            
            row = [
                Paragraph(fecha_formatted, self.table_data_style),
                Paragraph(str(item.hora_de) if item.hora_de else '', self.table_data_style),
                Paragraph(str(item.hora_hasta) if item.hora_hasta else '', self.table_data_style),
                Paragraph(f"B/. {item.desayuno:,.2f}" if item.desayuno else '', self.table_data_style),
                Paragraph(f"B/. {item.almuerzo:,.2f}" if item.almuerzo else '', self.table_data_style),
                Paragraph(f"B/. {item.cena:,.2f}" if item.cena else '', self.table_data_style),
                Paragraph(f"B/. {item.transporte:,.2f}" if item.transporte else '', self.table_data_style),
                Paragraph(f"B/. {total_dia:,.2f}", self.table_data_style)
            ]
            table_data.append(row)

        # Agregar 6 filas vacías para mantener el formato - CON ESPACIOS EN BLANCO PARA MANTENER TAMAÑO
        for _ in range(6):
            empty_row = [
                Paragraph("&nbsp;", self.table_data_style),  # Espacio no-break para mantener altura
                Paragraph("&nbsp;", self.table_data_style),
                Paragraph("&nbsp;", self.table_data_style),
                Paragraph("&nbsp;", self.table_data_style),
                Paragraph("&nbsp;", self.table_data_style),
                Paragraph("&nbsp;", self.table_data_style),
                Paragraph("&nbsp;", self.table_data_style),
                Paragraph("&nbsp;", self.table_data_style)
            ]
            table_data.append(empty_row)

        # Fila de total en letras - CORREGIDA PARA COMBINAR CELDAS CORRECTAMENTE
        total_en_letras = self._number_to_words(total_general)
        total_row = [
            Paragraph(f"TOTAL (En Letras): {total_en_letras}", self.table_header_style),
            Paragraph("", self.table_data_style),  # Vacía - combinada
            Paragraph("", self.table_data_style),  # Vacía - combinada
            Paragraph("", self.table_data_style),  # Vacía - combinada
            Paragraph("", self.table_data_style),  # Vacía - combinada
            Paragraph("", self.table_data_style),  # Vacía - combinada
            Paragraph("", self.table_data_style),  # Vacía - combinada
            Paragraph(f"B/. {total_general:,.2f}", self.table_data_style)
        ]
        table_data.append(total_row)

        # Crear tabla con anchos fijos
        main_table = Table(table_data, colWidths=[22*mm, 18*mm, 18*mm, 22*mm, 22*mm, 22*mm, 26*mm, 24*mm])
        main_table.setStyle(TableStyle([
            # Spans para encabezados de dos niveles
            ('SPAN', (0, 0), (0, 1)),  # FECHA abarca 2 filas
            ('SPAN', (1, 0), (2, 0)),  # HORA abarca 2 columnas
            ('SPAN', (3, 0), (5, 0)),  # ALIMENTACIÓN abarca 3 columnas
            ('SPAN', (6, 0), (6, 1)),  # TRANSPORTE abarca 2 filas
            ('SPAN', (7, 0), (7, 1)),  # TOTAL abarca 2 filas
            
            # Span para fila total - CORREGIDO PARA ABARCAR DESDE COLUMNA 0 HASTA 6
            ('SPAN', (0, -1), (6, -1)),  # TOTAL (En Letras) abarca desde columna 0 hasta 6
            
            # Estilos de encabezados
            ('FONTNAME', (0, 0), (-1, 1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 1), 8),
            ('ALIGN', (0, 0), (-1, 1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, 1), 'MIDDLE'),
            
            # Estilos de datos
            ('FONTNAME', (0, 2), (-1, -2), 'Helvetica'),
            ('FONTSIZE', (0, 2), (-1, -2), 9),
            ('ALIGN', (0, 2), (-1, -2), 'CENTER'),
            ('VALIGN', (0, 2), (-1, -2), 'MIDDLE'),
            
            # Estilo de fila total
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, -1), (-1, -1), 9),
            ('ALIGN', (0, -1), (0, -1), 'LEFT'),  # Texto del total alineado a la izquierda
            ('ALIGN', (7, -1), (7, -1), 'CENTER'),  # Monto total centrado
            ('VALIGN', (0, -1), (-1, -1), 'MIDDLE'),
            
            # Grid - bordes negros
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            
            # Altura mínima para todas las filas
            ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white]),
        ]))

        story.append(main_table)
        story.append(Spacer(1, 15*mm))
        
        # FIRMAS
        firmas_data = [
            [
                Paragraph("_______________________<br/>Jefe de Área", 
                         ParagraphStyle('Center', parent=self.styles['Normal'], alignment=TA_CENTER, fontSize=10)),
                "",
                Paragraph("_______________________<br/>Gerente de área", 
                         ParagraphStyle('Center', parent=self.styles['Normal'], alignment=TA_CENTER, fontSize=10))
            ]
        ]
        
        firmas_table = Table(firmas_data, colWidths=[60*mm, 70*mm, 60*mm])
        firmas_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        story.append(firmas_table)
        story.append(Spacer(1, 10*mm))
        
        # TABLA DE CÓDIGOS PRESUPUESTARIOS
        codigos_headers = [
            [
                Paragraph("Código Presupuestario", self.table_header_style),
                Paragraph("Valor", self.table_header_style)
            ]
        ]
        
        codigos_data = codigos_headers + [
            [Paragraph("1", ParagraphStyle('Left', parent=self.styles['Normal'], alignment=TA_LEFT, fontSize=10)), Paragraph("", self.table_data_style)],
            [Paragraph("2", ParagraphStyle('Left', parent=self.styles['Normal'], alignment=TA_LEFT, fontSize=10)), Paragraph("", self.table_data_style)]
        ]
        
        codigos_table = Table(codigos_data, colWidths=[120*mm, 50*mm])
        codigos_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Times-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('ALIGN', (0, 0), (-1, 0), 'LEFT'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('ALIGN', (0, 1), (-1, -1), 'LEFT'),
        ]))
        story.append(codigos_table)
        story.append(Spacer(1, 10*mm))
        
        # CAMPOS FINALES
        campos_finales = [
            [
                Paragraph("_______________________<br/>Entregado por:", 
                         ParagraphStyle('Center', parent=self.styles['Normal'], alignment=TA_CENTER, fontSize=10)),
                "",
                Paragraph("_______________________<br/>Recibido por:<br/><br/>No. Cédula: ___________", 
                         ParagraphStyle('Center', parent=self.styles['Normal'], alignment=TA_CENTER, fontSize=10))
            ]
        ]
        
        campos_finales_table = Table(campos_finales, colWidths=[60*mm, 70*mm, 60*mm])
        story.append(campos_finales_table)
        story.append(Spacer(1, 1*mm))
        
        
        # Generar PDF
        doc.build(story)
        buffer.seek(0)
        return buffer


    def _get_beneficiary_name(self, personal_id: int) -> str:
        """Obtener nombre del beneficiario"""
        try:
            from sqlalchemy import text
            result = self.db.execute(text("""
                SELECT apenom FROM nompersonal 
                WHERE personal_id = :personal_id
            """), {"personal_id": personal_id})
            row = result.fetchone()
            return row.apenom if row else f"ID: {personal_id}"
        except:
            return f"ID: {personal_id}"

    def _get_beneficiary_department(self, personal_id: int) -> str:
        """Obtener departamento del beneficiario"""
        try:
            from sqlalchemy import text
            query = """
                SELECT d.Descripcion 
                FROM nompersonal np
                LEFT JOIN departamento d ON np.IdDepartamento = d.IdDepartamento
                WHERE np.personal_id = :personal_id
            """
            result = self.db.execute(text(query), {"personal_id": personal_id})
            row = result.fetchone()
            return row.Descripcion if row and row.Descripcion else "GERENCIA AYSEC"
        except Exception as e:
            return "GERENCIA AYSEC"

    def _get_user_department(self, user: Usuario) -> str:
        """Obtener departamento del usuario - ahora obtiene la vicepresidencia del beneficiario"""
        # Este método ahora se usa para obtener la vicepresidencia del beneficiario
        # pero mantenemos el nombre por compatibilidad
        return "GERENCIA AYSEC"

    def _number_to_words(self, number: float) -> str:
        """Convertir número a palabras en español"""
        if number == 0:
            return "Cero balboas con 00/100"
        
        # Números básicos
        unidades = {
            1: 'uno', 2: 'dos', 3: 'tres', 4: 'cuatro', 5: 'cinco',
            6: 'seis', 7: 'siete', 8: 'ocho', 9: 'nueve', 10: 'diez',
            11: 'once', 12: 'doce', 13: 'trece', 14: 'catorce', 15: 'quince',
            16: 'dieciséis', 17: 'diecisiete', 18: 'dieciocho', 19: 'diecinueve',
            20: 'veinte', 30: 'treinta', 40: 'cuarenta', 50: 'cincuenta',
            60: 'sesenta', 70: 'setenta', 80: 'ochenta', 90: 'noventa',
            100: 'cien', 200: 'doscientos', 300: 'trescientos', 400: 'cuatrocientos',
            500: 'quinientos', 600: 'seiscientos', 700: 'setecientos', 800: 'ochocientos',
            900: 'novecientos'
        }
        
        # Convertir a entero y decimal
        entero = int(number)
        decimal = int((number - entero) * 100)
        
        if entero == 0:
            return f"Cero balboas con {decimal:02d}/100"
        
        # Convertir entero a palabras (implementación básica)
        if entero in unidades:
            palabra_entero = unidades[entero]
        elif entero < 100:
            decena = (entero // 10) * 10
            unidad = entero % 10
            if unidad == 0:
                palabra_entero = unidades[decena]
            else:
                palabra_entero = f"{unidades[decena]} y {unidades[unidad]}"
        else:
            # Para números mayores implementar lógica completa
            palabra_entero = f"número {entero}"
        
        # Formatear resultado
        if decimal == 0:
            return f"{palabra_entero.capitalize()} balboas con 00/100"
        else:
            return f"{palabra_entero.capitalize()} balboas con {decimal:02d}/100"