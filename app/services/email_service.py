# app/services/email_service.py

import logging
from typing import List, Optional, Dict, Any
from pathlib import Path
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.services.configuration import ConfigurationService
from app.services.department_service import DepartmentService
from app.models.configuration import ConfiguracionGeneral

logger = logging.getLogger(__name__)

class EmailService:
    def __init__(self, db: Session):
        self.db = db
        self.config_service = ConfigurationService(db)
        self._fastmail = None

    def _get_email_config(self) -> ConfiguracionGeneral:
        """Obtiene la configuración de email desde la base de datos"""
        config = self.config_service.get_configuracion_general()
        if not config:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="No se encontró configuración de email en la base de datos"
            )
        
        # Validar que los campos necesarios estén presentes
        required_fields = ['smtp_servidor', 'smtp_puerto', 'smtp_usuario', 'smtp_password', 'email_remitente']
        missing_fields = [field for field in required_fields if not getattr(config, field)]
        
        if missing_fields:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Configuración de email incompleta. Faltan: {', '.join(missing_fields)}"
            )
        
        return config

    def _get_fastmail_instance(self) -> FastMail:
        """Obtiene o crea la instancia de FastMail con la configuración actual"""
        if self._fastmail is None:
            config = self._get_email_config()
            
            # Determinar si usar SSL o TLS basado en la configuración
            smtp_seguridad = config.smtp_seguridad.lower()
            
            # Configuración para la nueva versión de fastapi-mail
            connection_config = ConnectionConfig(
                MAIL_USERNAME=config.smtp_usuario,
                MAIL_PASSWORD=config.smtp_password,
                MAIL_FROM=config.email_remitente,
                MAIL_PORT=config.smtp_puerto,
                MAIL_SERVER=config.smtp_servidor,
                MAIL_STARTTLS=smtp_seguridad == 'tls',
                MAIL_SSL_TLS=smtp_seguridad == 'ssl',
                USE_CREDENTIALS=True,
                VALIDATE_CERTS=True
            )
            
            self._fastmail = FastMail(connection_config)
        
        return self._fastmail

    def get_solicitante_email(self, mission_id: int, db_rrhh: Session) -> Optional[str]:
        """
        Obtiene el email del solicitante de una misión
        
        Args:
            mission_id: ID de la misión
            db_rrhh: Sesión de la base de datos RRHH
            
        Returns:
            str: Email del solicitante o None si no se encuentra
        """
        try:
            # Obtener la misión
            from app.models.mission import Mision
            mission = self.db.query(Mision).filter(Mision.id_mision == mission_id).first()
            
            if not mission:
                logger.warning(f"No se encontró la misión {mission_id}")
                return None
            
            # Obtener el personal_id del beneficiario (solicitante)
            personal_id = mission.beneficiario_personal_id
            
            if not personal_id:
                logger.warning(f"No se pudo obtener personal_id para misión {mission_id}")
                return None
            
            # Buscar el email en la tabla nompersonal de RRHH
            from sqlalchemy import text
            query = text("""
                SELECT email 
                FROM nompersonal 
                WHERE personal_id = :personal_id
            """)
            
            result = db_rrhh.execute(query, {"personal_id": personal_id})
            row = result.fetchone()
            
            if row and row[0]:
                logger.info(f"Email encontrado para empleado {personal_id}: {row[0]}")
                return row[0]
            
            logger.warning(f"No se pudo obtener email para misión {mission_id}")
            return None
            
        except Exception as e:
            logger.error(f"Error obteniendo email del solicitante: {str(e)}")
            return None

    def get_departamento_info(self, mission_id: int, db_rrhh: Session) -> Optional[Dict[str, Any]]:
        """
        Obtiene la información del departamento de una misión
        
        Args:
            mission_id: ID de la misión
            db_rrhh: Sesión de la base de datos RRHH
            
        Returns:
            Dict con información del departamento o None si no se encuentra
        """
        try:
            # Obtener la misión
            from app.models.mission import Mision
            mission = self.db.query(Mision).filter(Mision.id_mision == mission_id).first()
            
            if not mission:
                logger.warning(f"No se encontró la misión {mission_id}")
                return None
            
            # Obtener el personal_id del beneficiario (solicitante)
            personal_id = mission.beneficiario_personal_id
            
            if not personal_id:
                logger.warning(f"No se pudo obtener personal_id para misión {mission_id}")
                return None
            
            # Obtener el departamento del empleado
            from sqlalchemy import text
            dept_query = text("""
                SELECT np.IdDepartamento, d.Descripcion
                FROM nompersonal np
                JOIN departamento d ON d.IdDepartamento = np.IdDepartamento
                WHERE np.personal_id = :personal_id
            """)
            
            dept_result = db_rrhh.execute(dept_query, {"personal_id": personal_id})
            dept_row = dept_result.fetchone()
            
            if dept_row and dept_row[0]:
                logger.info(f"Departamento encontrado: {dept_row[1]} (ID: {dept_row[0]})")
                return {
                    "id": dept_row[0],
                    "nombre": dept_row[1]
                }
            
            logger.warning(f"No se encontró departamento para personal_id {personal_id}")
            return None
            
        except Exception as e:
            logger.error(f"Error obteniendo información del departamento: {str(e)}")
            return None

    def get_jefe_inmediato_email(self, mission_id: int, db_rrhh: Session) -> Optional[str]:
        """
        Obtiene el email del jefe inmediato de la misión
        
        Args:
            mission_id: ID de la misión
            db_rrhh: Sesión de la base de datos RRHH
            
        Returns:
            str: Email del jefe inmediato o None si no se encuentra
        """
        try:
            # Obtener la misión
            from app.models.mission import Mision
            mission = self.db.query(Mision).filter(Mision.id_mision == mission_id).first()
            
            if not mission:
                logger.warning(f"No se encontró la misión {mission_id}")
                return None
            
            # Obtener el personal_id del beneficiario (solicitante)
            personal_id = mission.beneficiario_personal_id
            
            if not personal_id:
                logger.warning(f"No se pudo obtener personal_id para misión {mission_id}")
                return None
            
            # Obtener el departamento del empleado
            from sqlalchemy import text
            dept_query = text("""
                SELECT IdDepartamento 
                FROM nompersonal 
                WHERE personal_id = :personal_id
            """)
            
            dept_result = db_rrhh.execute(dept_query, {"personal_id": personal_id})
            dept_row = dept_result.fetchone()
            
            if not dept_row or not dept_row[0]:
                logger.warning(f"No se encontró departamento para personal_id {personal_id}")
                return None
            
            departamento_id = dept_row[0]
            
            # Obtener el jefe inmediato del departamento (orden_aprobador = 1)
            jefe_query = text("""
                SELECT np.email, np.apenom
                FROM nompersonal np
                JOIN departamento_aprobadores_maestros dam ON dam.cedula_aprobador = np.cedula
                WHERE dam.id_departamento = :departamento_id
                  AND dam.orden_aprobador = 1
                  AND np.estado != 'De Baja'
            """)
            
            jefe_result = db_rrhh.execute(jefe_query, {"departamento_id": departamento_id})
            jefe_row = jefe_result.fetchone()
            
            if jefe_row and jefe_row[0]:
                logger.info(f"Email del jefe inmediato encontrado: {jefe_row[0]} ({jefe_row[1]})")
                return jefe_row[0]
            
            logger.warning(f"No se encontró jefe inmediato para departamento {departamento_id}")
            return None
            
        except Exception as e:
            logger.error(f"Error obteniendo email del jefe inmediato: {str(e)}")
            return None

    def get_department_users_emails(self, department_id: int, db_rrhh: Session) -> List[str]:
        """
        Obtiene los emails de todos los usuarios activos de un departamento específico
        
        Args:
            department_id: ID del departamento en aitsa_financiero
            
        Returns:
            List[str]: Lista de emails de usuarios del departamento
        """
        print(f"DEBUG EMAIL SERVICE: get_department_users_emails para department_id={department_id}")
        try:
            from sqlalchemy import text
            
            # Query para obtener emails de usuarios del departamento
            # Primero obtener los personal_ids de usuarios del departamento
            usuarios_query = text("""
                SELECT personal_id_rrhh
                FROM usuarios
                WHERE id_departamento = :department_id
                  AND is_active = 1
                  AND personal_id_rrhh IS NOT NULL
            """)
            
            usuarios_result = self.db.execute(usuarios_query, {"department_id": department_id})
            usuarios_rows = usuarios_result.fetchall()
            print(f"DEBUG EMAIL SERVICE: Usuarios encontrados en departamento {department_id}: {len(usuarios_rows)}")
            
            personal_ids = [row.personal_id_rrhh for row in usuarios_rows]
            print(f"DEBUG EMAIL SERVICE: personal_ids extraídos: {personal_ids}")
            
            if not personal_ids:
                print(f"DEBUG EMAIL SERVICE: No se encontraron usuarios en departamento {department_id}")
                return []
            
            print(f"DEBUG EMAIL SERVICE: personal_ids encontrados: {personal_ids}")
            
            # Luego obtener los emails de esos personal_ids en RRHH
            # Manejar el caso cuando solo hay un personal_id (evitar error de tupla con un elemento)
            if len(personal_ids) == 1:
                emails_query = text("""
                    SELECT email
                    FROM nompersonal
                    WHERE personal_id = :personal_id
                      AND estado != 'De Baja'
                      AND email IS NOT NULL
                      AND email != ''
                """)
                result = db_rrhh.execute(emails_query, {"personal_id": personal_ids[0]})
                emails_rows = result.fetchall()
                print(f"DEBUG EMAIL SERVICE: Filas de emails encontradas (1 usuario): {len(emails_rows)}")
                
                emails = [row.email for row in emails_rows]
                print(f"DEBUG EMAIL SERVICE: Emails extraídos (1 usuario): {emails}")
            else:
                # Verificar que no esté vacío antes de crear la tupla
                if not personal_ids:
                    print(f"DEBUG EMAIL SERVICE: personal_ids está vacío")
                    return []
                
                # Construir la consulta dinámicamente para evitar problemas con tuplas
                placeholders = ','.join([':id' + str(i) for i in range(len(personal_ids))])
                emails_query = text(f"""
                    SELECT email
                    FROM nompersonal
                    WHERE personal_id IN ({placeholders})
                      AND estado != 'De Baja'
                      AND email IS NOT NULL
                      AND email != ''
                """)
                
                # Crear parámetros dinámicamente
                params = {f'id{i}': personal_ids[i] for i in range(len(personal_ids))}
                result = db_rrhh.execute(emails_query, params)
                emails_rows = result.fetchall()
                print(f"DEBUG EMAIL SERVICE: Filas de emails encontradas (múltiples): {len(emails_rows)}")
                
                emails = [row.email for row in emails_rows]
                print(f"DEBUG EMAIL SERVICE: Emails extraídos (múltiples): {emails}")
            
            print(f"DEBUG EMAIL SERVICE: Encontrados {len(emails)} emails en departamento {department_id}")
            print(f"DEBUG EMAIL SERVICE: department_emails={emails}")
            
            logger.info(f"Encontrados {len(emails)} emails para departamento {department_id}")
            return emails
            
        except Exception as e:
            logger.error(f"Error obteniendo emails de usuarios del departamento {department_id}: {str(e)}")
            return []

    def get_next_department_id(self, current_state: str) -> Optional[int]:
        """
        Determina el ID del departamento siguiente en el flujo basado en el estado actual
        
        Args:
            current_state: Estado actual de la misión
            
        Returns:
            int: ID del departamento siguiente o None si no hay departamento siguiente
        """
        print(f"DEBUG EMAIL SERVICE: get_next_department_id para current_state={current_state}")
        
        # Mapeo de estados a departamentos (esto debe configurarse según la estructura real)
        state_to_department = {
            'PENDIENTE_JEFE': None,  # Jefe inmediato (no es departamento financiero)
            'PENDIENTE_REVISION_TESORERIA': 1,  #
            'PENDIENTE_ASIGNACION_PRESUPUESTO': 3,  # Presupuesto
            'PENDIENTE_CONTABILIDAD': 2,  # Contabilidad
            'PENDIENTE_APROBACION_FINANZAS': 7,  # Finanzas
            'PENDIENTE_REFRENDO_CGR': 4,  # CGR
            'APROBADO_PARA_PAGO': 5,  # Tesorería para pago
            'PAGADO': None,  # Estado final
            'DEVUELTO_CORRECCION': None,  # No tiene departamento siguiente
            'RECHAZADO': None,  # Estado final
        }
        
        result = state_to_department.get(current_state)
        print(f"DEBUG EMAIL SERVICE: get_next_department_id resultado={result}")
        return result

    def get_return_notification_recipients(self, mission_id: int, return_state: str, db_rrhh: Session) -> List[str]:
        """
        Determina a quién enviar la notificación cuando se devuelve una solicitud
        
        Args:
            mission_id: ID de la misión
            return_state: Estado de devolución (ej: DEVUELTO_CORRECCION_JEFE, DEVUELTO_CORRECCION_TESORERIA, etc.)
            db_rrhh: Sesión de RRHH
            
        Returns:
            List[str]: Lista de emails de destinatarios
        """
        print(f"DEBUG EMAIL SERVICE: get_return_notification_recipients para misión {mission_id}, estado {return_state}")
        
        try:
            # Mapeo de estados de devolución a departamentos
            return_state_to_department = {
                'DEVUELTO_CORRECCION_JEFE': None,  # Se envía al jefe inmediato del departamento del solicitante
                'DEVUELTO_CORRECCION_TESORERIA': 1,  # Tesorería
                'DEVUELTO_CORRECCION_PRESUPUESTO': 3,  # Presupuesto
                'DEVUELTO_CORRECCION_CONTABILIDAD': 2,  # Contabilidad
                'DEVUELTO_CORRECCION_FINANZAS': 7,  # Finanzas
                'DEVUELTO_CORRECCION_CGR': 4,  # CGR
                'DEVUELTO_CORRECCION': None,  # Estado general, se envía al solicitante
            }
            
            department_id = return_state_to_department.get(return_state)
            print(f"DEBUG EMAIL SERVICE: department_id={department_id}")
            
            if department_id is None:
                if return_state == 'DEVUELTO_CORRECCION_JEFE':
                    # Enviar al jefe inmediato del departamento del solicitante
                    print(f"DEBUG EMAIL SERVICE: Enviando al jefe inmediato del departamento del solicitante")
                    jefe_email = self.get_jefe_inmediato_email(mission_id, db_rrhh)
                    return [jefe_email] if jefe_email else []
                else:
                    # Para otros estados sin departamento específico, enviar al solicitante
                    print(f"DEBUG EMAIL SERVICE: Enviando al solicitante")
                    solicitante_email = self.get_solicitante_email(mission_id, db_rrhh)
                    return [solicitante_email] if solicitante_email else []
            else:
                # Enviar a todos los usuarios del departamento
                print(f"DEBUG EMAIL SERVICE: Enviando a departamento {department_id}")
                return self.get_department_users_emails(department_id, db_rrhh)
                
        except Exception as e:
            logger.error(f"Error determinando destinatarios de devolución: {str(e)}")
            return []

    def get_return_department_name(self, return_state: str) -> str:
        """
        Obtiene el nombre del departamento responsable según el estado de devolución
        
        Args:
            return_state: Estado de devolución
            
        Returns:
            str: Nombre del departamento
        """
        try:
            # Mapeo de estados de devolución a IDs de departamento
            return_state_to_department_id = {
                'DEVUELTO_CORRECCION_JEFE': None,  # Jefe Inmediato (no es departamento financiero)
                'DEVUELTO_CORRECCION_TESORERIA': 1,  # Tesorería
                'DEVUELTO_CORRECCION_PRESUPUESTO': 3,  # Presupuesto
                'DEVUELTO_CORRECCION_CONTABILIDAD': 2,  # Contabilidad
                'DEVUELTO_CORRECCION_FINANZAS': 7,  # Finanzas
                'DEVUELTO_CORRECCION_CGR': 4,  # CGR
                'DEVUELTO_CORRECCION': None,  # Estado general, se envía al solicitante
            }
            
            department_id = return_state_to_department_id.get(return_state)
            
            if department_id is None:
                # Si no hay departamento específico, es jefe inmediato o solicitante
                if return_state == 'DEVUELTO_CORRECCION_JEFE':
                    return 'Jefe Inmediato'
                else:
                    return 'Solicitante'
            
            # Obtener el nombre del departamento desde la base de datos
            from app.services.department_service import DepartmentService
            department_service = DepartmentService(self.db)
            department = department_service.get_department(department_id)
            
            if department:
                return department.nombre
            else:
                return f'Departamento {department_id}'
                
        except Exception as e:
            logger.error(f"Error obteniendo nombre del departamento: {str(e)}")
            return 'Departamento'

    async def send_email(
        self,
        to_emails: List[str],
        subject: str,
        body: str,
        html_body: Optional[str] = None
    ) -> bool:
        """
        Envía un email
        
        Args:
            to_emails: Lista de emails destinatarios
            subject: Asunto del email
            body: Cuerpo del email (texto plano)
            html_body: Cuerpo del email en HTML (opcional)
        
        Returns:
            bool: True si se envió correctamente
        """
        try:
            fastmail = self._get_fastmail_instance()
            
            # Preparar el mensaje
            message = MessageSchema(
                subject=subject,
                recipients=to_emails,
                body=html_body if html_body else body,
                subtype="html" if html_body else "plain"
            )
            
            # Enviar el email
            await fastmail.send_message(message)
            logger.info(f"Email enviado exitosamente a: {', '.join(to_emails)}")
            return True
            
        except Exception as e:
            logger.error(f"Error enviando email: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error enviando email: {str(e)}"
            )

    def create_approval_email_html(self, data: Dict[str, Any]) -> str:
        """Crea el HTML para emails de solicitudes aprobadas"""
        return f"""
        <html>
        <head>
            <style>
                body {{ 
                    font-family: Arial, sans-serif; 
                    line-height: 1.6; 
                    color: #333; 
                    margin: 0; 
                    padding: 0; 
                    background-color: #f5f5f5;
                }}
                .container {{
                    max-width: 600px;
                    margin: 0 auto;
                    background-color: #ffffff;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                }}
                .header {{ 
                    background-color: #b3d9ff; 
                    color: #000000; 
                    padding: 30px 20px; 
                    text-align: center; 
                }}
                .content {{ 
                    padding: 30px 20px; 
                }}
                .details {{ 
                    background-color: #f5f5f5; 
                    padding: 20px; 
                    border-left: 4px solid #b3d9ff; 
                    margin: 25px 0; 
                }}
                .footer {{ 
                    background-color: #d3d3d3; 
                    color: #000000; 
                    padding: 20px; 
                    text-align: center; 
                    font-size: 12px; 
                }}
                h1, h2, h3 {{
                    color: #2c3e50;
                }}
                ul {{
                    margin: 10px 0;
                    padding-left: 20px;
                }}
                li {{
                    margin: 5px 0;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Solicitud Aprobada</h1>
                </div>
                <div class="content">
                    <p>Su solicitud ha sido <strong>APROBADA</strong> exitosamente.</p>
                    
                    <div class="details">
                        <h3>Detalles de la Solicitud:</h3>
                        <ul>
                            <li><strong>Número de Solicitud:</strong> {data.get('numero_solicitud', 'N/A')}</li>
                            <li><strong>Tipo:</strong> {data.get('tipo', 'N/A')}</li>
                            <li><strong>Fecha:</strong> {data.get('fecha', 'N/A')}</li>
                            <li><strong>Monto:</strong> {data.get('monto', 'N/A')}</li>
                            <li><strong>Aprobado por:</strong> {data.get('aprobador', 'N/A')}</li>
                        </ul>
                    </div>
                    
                    {f'<p><strong>Comentarios:</strong> {data.get("comentarios", "")}</p>' if data.get('comentarios') else ''}
                    
                    <p>Gracias por usar el Sistema de Viáticos de AITSA.</p>
                </div>
                <div class="footer">
                    <p>Sistema de Gestión de Viáticos - AITSA</p>
                    <p>Este es un mensaje automático del sistema. Por favor no responda a este correo.</p>
                </div>
            </div>
        </body>
        </html>
        """

    def create_rejection_email_html(self, data: Dict[str, Any]) -> str:
        """Crea el HTML para emails de solicitudes rechazadas"""
        return f"""
        <html>
        <head>
            <style>
                body {{ 
                    font-family: Arial, sans-serif; 
                    line-height: 1.6; 
                    color: #333; 
                    margin: 0; 
                    padding: 0; 
                    background-color: #f5f5f5;
                }}
                .container {{
                    max-width: 600px;
                    margin: 0 auto;
                    background-color: #ffffff;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                }}
                .header {{ 
                    background-color: #b3d9ff; 
                    color: #000000; 
                    padding: 30px 20px; 
                    text-align: center; 
                }}
                .content {{ 
                    padding: 30px 20px; 
                }}
                .details {{ 
                    background-color: #f5f5f5; 
                    padding: 20px; 
                    border-left: 4px solid #b3d9ff; 
                    margin: 25px 0; 
                }}
                .reason {{ 
                    background-color: #fff3cd; 
                    border: 1px solid #ffeaa7; 
                    padding: 20px; 
                    margin: 25px 0; 
                }}
                .footer {{ 
                    background-color: #d3d3d3; 
                    color: #000000; 
                    padding: 20px; 
                    text-align: center; 
                    font-size: 12px; 
                }}
                h1, h2, h3 {{
                    color: #2c3e50;
                }}
                ul {{
                    margin: 10px 0;
                    padding-left: 20px;
                }}
                li {{
                    margin: 5px 0;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Solicitud Rechazada</h1>
                </div>
                <div class="content">
                    <p>Su solicitud ha sido <strong>RECHAZADA</strong>.</p>
                    
                    <div class="reason">
                        <h3>Motivo del Rechazo:</h3>
                        <p>{data.get('motivo', 'No especificado')}</p>
                    </div>
                    
                    <div class="details">
                        <h3>Detalles de la Solicitud:</h3>
                        <ul>
                            <li><strong>Número de Solicitud:</strong> {data.get('numero_solicitud', 'N/A')}</li>
                            <li><strong>Tipo:</strong> {data.get('tipo', 'N/A')}</li>
                            <li><strong>Fecha:</strong> {data.get('fecha', 'N/A')}</li>
                            <li><strong>Monto:</strong> {data.get('monto', 'N/A')}</li>
                            <li><strong>Rechazado por:</strong> {data.get('rechazador', 'N/A')}</li>
                        </ul>
                    </div>
                    
                    {f'<p><strong>Comentarios:</strong> {data.get("comentarios", "")}</p>' if data.get('comentarios') else ''}
                    
                    <p>Para más información, contacte al administrador del sistema.</p>
                </div>
                <div class="footer">
                    <p>Sistema de Gestión de Viáticos - AITSA</p>
                    <p>Este es un mensaje automático del sistema. Por favor no responda a este correo.</p>
                </div>
            </div>
        </body>
        </html>
        """

    def create_return_email_html(self, data: Dict[str, Any]) -> str:
        """Crea el HTML para emails de solicitudes devueltas para corrección"""
        # Determinar el tipo de solicitud y personalizar el mensaje
        tipo_solicitud = data.get('tipo', 'N/A')
        if tipo_solicitud == 'VIATICOS':
            tipo_descripcion = "Viáticos"
            color_header = "#ff6b6b"  # Rojo para viáticos
        elif tipo_solicitud == 'CAJA_MENUDA':
            tipo_descripcion = "Caja Menuda"
            color_header = "#4ecdc4"  # Verde para caja menuda
        else:
            tipo_descripcion = tipo_solicitud
            color_header = "#b3d9ff"  # Azul por defecto
        
        return f"""
        <html>
        <head>
            <style>
                body {{ 
                    font-family: Arial, sans-serif; 
                    line-height: 1.6; 
                    color: #333; 
                    margin: 0; 
                    padding: 0; 
                    background-color: #f5f5f5;
                }}
                .container {{
                    max-width: 600px;
                    margin: 0 auto;
                    background-color: #ffffff;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                }}
                .header {{ 
                    background-color: {color_header}; 
                    color: #ffffff; 
                    padding: 30px 20px; 
                    text-align: center; 
                }}
                .content {{ 
                    padding: 30px 20px; 
                }}
                .details {{ 
                    background-color: #f5f5f5; 
                    padding: 20px; 
                    border-left: 4px solid {color_header}; 
                    margin: 25px 0; 
                }}
                .observations {{ 
                    background-color: #fff3cd; 
                    border: 1px solid #ffeaa7; 
                    padding: 20px; 
                    margin: 25px 0; 
                }}
                .tipo-badge {{
                    display: inline-block;
                    background-color: {color_header};
                    color: #ffffff;
                    padding: 5px 15px;
                    border-radius: 20px;
                    font-size: 12px;
                    font-weight: bold;
                    margin-bottom: 10px;
                }}
                .footer {{ 
                    background-color: #d3d3d3; 
                    color: #000000; 
                    padding: 20px; 
                    text-align: center; 
                    font-size: 12px; 
                }}
                h1, h2, h3 {{
                    color: #2c3e50;
                }}
                ul {{
                    margin: 10px 0;
                    padding-left: 20px;
                }}
                li {{
                    margin: 5px 0;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <div class="tipo-badge">{tipo_descripcion}</div>
                    <h1>Solicitud Devuelta</h1>
                </div>
                <div class="content">
                    <p>Su solicitud de <strong>{tipo_descripcion.lower()}</strong> ha sido <strong>DEVUELTA</strong> para correcciones.</p>
                    
                    <div class="observations">
                        <h3>Observaciones:</h3>
                        <p>{data.get('observaciones', 'No especificadas')}</p>
                    </div>
                    
                    <div class="details">
                        <h3>Detalles de la Solicitud:</h3>
                        <ul>
                            <li><strong>Número de Solicitud:</strong> {data.get('numero_solicitud', 'N/A')}</li>
                            <li><strong>Tipo de Solicitud:</strong> {tipo_descripcion}</li>
                            <li><strong>Fecha:</strong> {data.get('fecha', 'N/A')}</li>
                            <li><strong>Monto:</strong> {data.get('monto', 'N/A')}</li>
                            <li><strong>Devuelto por:</strong> {data.get('devuelto_por', 'N/A')}</li>
                            <li><strong>Departamento Responsable:</strong> {data.get('departamento_responsable', 'N/A')}</li>
                        </ul>
                    </div>
                    
                    <p>Por favor, revise y corrija los puntos mencionados para continuar con el proceso de {tipo_descripcion.lower()}.</p>
                </div>
                <div class="footer">
                    <p>Sistema de Gestión de Viáticos - AITSA</p>
                    <p>Este es un mensaje automático del sistema. Por favor no responda a este correo.</p>
                </div>
            </div>
        </body>
        </html>
        """

    def create_new_request_email_html(self, data: Dict[str, Any]) -> str:
        """Crea el HTML para emails de nuevas solicitudes (para jefes inmediatos)"""
        return f"""
        <html>
        <head>
            <style>
                body {{ 
                    font-family: Arial, sans-serif; 
                    line-height: 1.6; 
                    color: #333; 
                    margin: 0; 
                    padding: 0; 
                    background-color: #f5f5f5;
                }}
                .container {{
                    max-width: 600px;
                    margin: 0 auto;
                    background-color: #ffffff;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                }}
                .header {{ 
                    background-color: #b3d9ff; 
                    color: #000000; 
                    padding: 30px 20px; 
                    text-align: center; 
                }}
                .content {{ 
                    padding: 30px 20px; 
                }}
                .details {{ 
                    background-color: #f5f5f5; 
                    padding: 20px; 
                    border-left: 4px solid #b3d9ff; 
                    margin: 25px 0; 
                }}
                .action {{ 
                    background-color: #f5f5f5; 
                    border: 1px solid #d3d3d3; 
                    padding: 20px; 
                    margin: 25px 0; 
                }}
                .footer {{ 
                    background-color: #d3d3d3; 
                    color: #000000; 
                    padding: 20px; 
                    text-align: center; 
                    font-size: 12px; 
                }}
                .btn {{
                    display: inline-block;
                    background-color: #3498db;
                    color: white;
                    padding: 10px 20px;
                    text-decoration: none;
                    border-radius: 4px;
                    margin: 10px 5px;
                }}
                .btn:hover {{
                    background-color: #2980b9;
                }}
                h1, h2, h3 {{
                    color: #2c3e50;
                }}
                ul {{
                    margin: 10px 0;
                    padding-left: 20px;
                }}
                li {{
                    margin: 5px 0;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Nueva Solicitud Pendiente de Aprobación</h1>
                </div>
                <div class="content">
                    <p>Se ha creado una nueva solicitud que requiere su <strong>APROBACIÓN</strong> como jefe inmediato.</p>
                    
                    <div class="details">
                        <h3>Detalles de la Solicitud:</h3>
                        <ul>
                            <li><strong>Número de Solicitud:</strong> {data.get('numero_solicitud', 'N/A')}</li>
                            <li><strong>Tipo:</strong> {data.get('tipo', 'N/A')}</li>
                            <li><strong>Solicitante:</strong> {data.get('solicitante', 'N/A')}</li>
                            <li><strong>Departamento:</strong> {data.get('departamento', 'N/A')}</li>
                            <li><strong>Fecha de Solicitud:</strong> {data.get('fecha', 'N/A')}</li>
                            <li><strong>Monto Solicitado:</strong> {data.get('monto', 'N/A')}</li>
                            <li><strong>Objetivo:</strong> {data.get('objetivo', 'N/A')}</li>
                        </ul>
                    </div>
                    
                    <div class="action">
                        <h3>Acción Requerida:</h3>
                        <p>Por favor, revise la solicitud y tome una de las siguientes acciones:</p>
                        <ul>
                            <li><strong>Aprobar:</strong> Si la solicitud cumple con los requisitos</li>
                            <li><strong>Rechazar:</strong> Si la solicitud no cumple con los requisitos</li>
                            <li><strong>Devolver:</strong> Si requiere correcciones o información adicional</li>
                        </ul>
                    </div>
                    
                    <p>Acceda al sistema para revisar y procesar esta solicitud.</p>
                </div>
                <div class="footer">
                    <p>Sistema de Gestión de Viáticos - AITSA</p>
                    <p>Este es un mensaje automático del sistema. Por favor no responda a este correo.</p>
                </div>
            </div>
        </body>
        </html>
        """

    def create_workflow_notification_email_html(self, data: Dict[str, Any]) -> str:
        """Crea el HTML para emails de notificaciones del workflow"""
        # Determinar el tipo de solicitud y personalizar el mensaje
        tipo_solicitud = data.get('tipo', 'N/A')
        if tipo_solicitud == 'VIATICOS':
            tipo_descripcion = "Viáticos"
            color_header = "#ff6b6b"  # Rojo para viáticos
            flujo_descripcion = "flujo completo de viáticos"
        elif tipo_solicitud == 'CAJA_MENUDA':
            tipo_descripcion = "Caja Menuda"
            color_header = "#4ecdc4"  # Verde para caja menuda
            flujo_descripcion = "flujo simplificado de caja menuda"
        else:
            tipo_descripcion = tipo_solicitud
            color_header = "#b3d9ff"  # Azul por defecto
            flujo_descripcion = "flujo de solicitud"
        
        return f"""
        <html>
        <head>
            <style>
                body {{ 
                    font-family: Arial, sans-serif !important; 
                    line-height: 1.6 !important; 
                    color: #000000 !important; 
                    margin: 0 !important; 
                    padding: 0 !important; 
                    background-color: #f5f5f5 !important;
                }}
                .container {{
                    max-width: 600px !important;
                    margin: 0 auto !important;
                    background-color: #ffffff !important;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1) !important;
                }}
                .header {{ 
                    background-color: {color_header} !important; 
                    color: #ffffff !important; 
                    padding: 30px 20px !important; 
                    text-align: center !important; 
                }}
                .content {{ 
                    padding: 30px 20px !important; 
                    color: #000000 !important;
                }}
                .details {{ 
                    background-color: #f5f5f5 !important; 
                    padding: 20px !important; 
                    border-left: 4px solid {color_header} !important; 
                    margin: 25px 0 !important; 
                    color: #000000 !important;
                }}
                .action {{ 
                    background-color: #e8f4fd !important; 
                    border: 1px solid {color_header} !important; 
                    padding: 20px !important; 
                    margin: 25px 0 !important; 
                    color: #000000 !important;
                }}
                .tipo-badge {{
                    display: inline-block !important;
                    background-color: {color_header} !important;
                    color: #ffffff !important;
                    padding: 5px 15px !important;
                    border-radius: 20px !important;
                    font-size: 12px !important;
                    font-weight: bold !important;
                    margin-bottom: 10px !important;
                }}
                .footer {{ 
                    background-color: #d3d3d3 !important; 
                    color: #000000 !important; 
                    padding: 20px !important; 
                    text-align: center !important; 
                    font-size: 12px !important; 
                }}
                h1, h2, h3 {{
                    color: #000000 !important;
                }}
                p {{
                    color: #000000 !important;
                }}
                ul {{
                    margin: 10px 0 !important;
                    padding-left: 20px !important;
                    color: #000000 !important;
                }}
                li {{
                    margin: 5px 0 !important;
                    color: #000000 !important;
                }}
                strong {{
                    color: #000000 !important;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <div class="tipo-badge">{tipo_descripcion}</div>
                    <h1>Solicitud Pendiente de Revisión</h1>
                </div>
                <div class="content">
                    <p>Una solicitud de <strong>{tipo_descripcion.lower()}</strong> ha sido <strong>APROBADA</strong> y requiere su revisión en el siguiente paso del {flujo_descripcion}.</p>
                    
                    <div class="details">
                        <h3>Detalles de la Solicitud:</h3>
                        <ul>
                            <li><strong>Número de Solicitud:</strong> {data.get('numero_solicitud', 'N/A')}</li>
                            <li><strong>Tipo de Solicitud:</strong> {tipo_descripcion}</li>
                            <li><strong>Solicitante:</strong> {data.get('solicitante', 'N/A')}</li>
                            <li><strong>Departamento Solicitante:</strong> {data.get('departamento_solicitante', 'N/A')}</li>
                            <li><strong>Fecha de Solicitud:</strong> {data.get('fecha', 'N/A')}</li>
                            <li><strong>Monto Solicitado:</strong> {data.get('monto', 'N/A')}</li>
                            <li><strong>Objetivo:</strong> {data.get('objetivo', 'N/A')}</li>
                            <li><strong>Estado Actual:</strong> {data.get('estado_actual', 'N/A')}</li>
                            <li><strong>Aprobado por:</strong> {data.get('aprobado_por', 'N/A')}</li>
                        </ul>
                    </div>
                    
                    <div class="action">
                        <h3>Acción Requerida:</h3>
                        <p>Esta solicitud de {tipo_descripcion.lower()} está ahora en su área de responsabilidad. Por favor, revise y procese según corresponda.</p>
                        <p><strong>Departamento Responsable:</strong> {data.get('departamento_responsable', 'N/A')}</p>
                    </div>
                    
                    <p>Acceda al sistema para revisar y procesar esta solicitud de {tipo_descripcion.lower()}.</p>
                </div>
                <div class="footer">
                    <p>Sistema de Gestión de Viáticos - AITSA</p>
                    <p>Este es un mensaje automático del sistema. Por favor no responda a este correo.</p>
                </div>
            </div>
        </body>
        </html>
        """

    # === MÉTODOS DE ENVÍO ESPECÍFICOS ===

    async def send_approval_notification(
        self,
        to_email: str,
        data: Dict[str, Any],
        db_rrhh: Session = None
    ) -> bool:
        """
        Envía notificación de aprobación
        
        Args:
            to_email: Email del destinatario
            data: Datos de la solicitud
            db_rrhh: Sesión de RRHH (opcional, para obtener email si no se proporciona)
        
        Returns:
            bool: True si se envió correctamente
        """
        try:
            html_body = self.create_approval_email_html(data)
            
            await self.send_email(
                to_emails=[to_email],
                subject=f"Solicitud Aprobada - {data.get('numero_solicitud', 'N/A')}",
                body=f"Su solicitud {data.get('numero_solicitud', '')} ha sido aprobada exitosamente.",
                html_body=html_body
            )
            
            logger.info(f"Notificación de aprobación enviada a {to_email}")
            return True
            
        except Exception as e:
            logger.error(f"Error enviando notificación de aprobación: {str(e)}")
            return False

    async def send_rejection_notification(
        self,
        to_email: str,
        data: Dict[str, Any],
        db_rrhh: Session = None
    ) -> bool:
        """
        Envía notificación de rechazo
        
        Args:
            to_email: Email del destinatario
            data: Datos de la solicitud
            db_rrhh: Sesión de RRHH (opcional, para obtener email si no se proporciona)
        
        Returns:
            bool: True si se envió correctamente
        """
        try:
            html_body = self.create_rejection_email_html(data)
            
            await self.send_email(
                to_emails=[to_email],
                subject=f"Solicitud Rechazada - {data.get('numero_solicitud', 'N/A')}",
                body=f"Su solicitud {data.get('numero_solicitud', '')} ha sido rechazada.",
                html_body=html_body
            )
            
            logger.info(f"Notificación de rechazo enviada a {to_email}")
            return True
            
        except Exception as e:
            logger.error(f"Error enviando notificación de rechazo: {str(e)}")
            return False

    async def send_return_notification(
        self,
        mission_id: int,
        return_state: str,
        returned_by: str,
        observaciones: str,
        data: Dict[str, Any],
        db_rrhh: Session
    ) -> bool:
        """
        Envía notificación de devolución a los destinatarios correspondientes
        
        Args:
            mission_id: ID de la misión
            return_state: Estado de devolución
            returned_by: Nombre del usuario que devolvió la solicitud
            observaciones: Observaciones de la devolución
            data: Datos de la solicitud
            db_rrhh: Sesión de RRHH
            
        Returns:
            bool: True si se envió correctamente
        """
        print(f"DEBUG EMAIL SERVICE: Iniciando send_return_notification para misión {mission_id}")
        print(f"DEBUG EMAIL SERVICE: return_state={return_state}, returned_by={returned_by}")
        
        try:
            # Determinar destinatarios
            recipients = self.get_return_notification_recipients(mission_id, return_state, db_rrhh)
            print(f"DEBUG EMAIL SERVICE: recipients={recipients}")
            
            if not recipients:
                logger.warning(f"No se encontraron destinatarios para notificación de devolución de misión {mission_id}")
                return False
            
            # Preparar datos adicionales
            data['devuelto_por'] = returned_by
            data['observaciones'] = observaciones
            data['departamento_responsable'] = self.get_return_department_name(return_state)
            
            # Crear el HTML del email
            html_body = self.create_return_email_html(data)
            
            # Preparar el asunto del correo
            subject = f"Solicitud Devuelta - {data.get('numero_solicitud', 'N/A')}"
            print(f"DEBUG EMAIL SERVICE: Asunto del correo: {subject}")
            
            # Enviar el email
            await self.send_email(
                to_emails=recipients,
                subject=subject,
                body=f"Solicitud {data.get('numero_solicitud', '')} devuelta para correcciones",
                html_body=html_body
            )
            
            logger.info(f"Notificación de devolución enviada a {len(recipients)} destinatarios")
            return True
            
        except Exception as e:
            logger.error(f"Error enviando notificación de devolución: {str(e)}")
            return False

    async def send_mission_notification(
        self,
        mission_id: int,
        notification_type: str,
        data: Dict[str, Any],
        db_rrhh: Session
    ) -> bool:
        """
        Envía notificación para una misión específica
        
        Args:
            mission_id: ID de la misión
            notification_type: Tipo de notificación ('approval', 'rejection', 'return', 'payment')
            data: Datos adicionales para la notificación
            db_rrhh: Sesión de RRHH
        
        Returns:
            bool: True si se envió correctamente
        """
        try:
            # Obtener el email del solicitante
            solicitante_email = self.get_solicitante_email(mission_id, db_rrhh)
            
            if not solicitante_email:
                logger.warning(f"No se pudo obtener email del solicitante para misión {mission_id}")
                return False
            
            # Enviar la notificación según el tipo
            if notification_type == 'approval':
                return await self.send_approval_notification(solicitante_email, data, db_rrhh)
            elif notification_type == 'rejection':
                return await self.send_rejection_notification(solicitante_email, data, db_rrhh)
            elif notification_type == 'return':
                # Para devoluciones, usar el nuevo método que determina automáticamente los destinatarios
                return await self.send_return_notification(
                    mission_id=mission_id,
                    return_state=data.get('estado_nuevo', 'DEVUELTO_CORRECCION'),
                    returned_by=data.get('devuelto_por', 'Usuario'),
                    observaciones=data.get('observaciones', 'Sin observaciones'),
                    data=data,
                    db_rrhh=db_rrhh
                )
            elif notification_type == 'payment':
                return await self.send_payment_notification(solicitante_email, data, db_rrhh)
            else:
                logger.error(f"Tipo de notificación no válido: {notification_type}")
                return False
                
        except Exception as e:
            logger.error(f"Error enviando notificación de misión: {str(e)}")
            return False

    async def send_new_request_notification(
        self,
        mission_id: int,
        data: Dict[str, Any],
        db_rrhh: Session
    ) -> bool:
        """
        Envía notificación de nueva solicitud al jefe inmediato
        
        Args:
            mission_id: ID de la misión
            data: Datos de la solicitud
            db_rrhh: Sesión de RRHH
        
        Returns:
            bool: True si se envió correctamente
        """
        try:
            # Obtener el email del jefe inmediato
            jefe_email = self.get_jefe_inmediato_email(mission_id, db_rrhh)
            
            if not jefe_email:
                logger.warning(f"No se pudo obtener email del jefe inmediato para misión {mission_id}")
                return False
            
            # Obtener información del departamento
            departamento_info = self.get_departamento_info(mission_id, db_rrhh)
            if departamento_info:
                data['departamento'] = departamento_info['nombre']
            else:
                data['departamento'] = 'N/A'
            
            # Crear el HTML del email
            html_body = self.create_new_request_email_html(data)
            
            # Enviar el email
            await self.send_email(
                to_emails=[jefe_email],
                subject=f"Nueva Solicitud Pendiente - {data.get('numero_solicitud', 'N/A')}",
                body=f"Nueva solicitud pendiente de aprobación: {data.get('numero_solicitud', '')}",
                html_body=html_body
            )
            
            logger.info(f"Notificación de nueva solicitud enviada al jefe inmediato: {jefe_email}")
            return True
            
        except Exception as e:
            logger.error(f"Error enviando notificación de nueva solicitud: {str(e)}")
            return False

    async def send_workflow_notification(
        self,
        mission_id: int,
        current_state: str,
        next_state: str,
        approved_by: str,
        data: Dict[str, Any],
        db_rrhh: Session
    ) -> bool:
        """
        Envía notificación a todos los usuarios del departamento siguiente en el workflow
        
        Args:
            mission_id: ID de la misión
            current_state: Estado actual de la misión
            next_state: Estado siguiente al que se movió la misión
            approved_by: Nombre del usuario que aprobó
            data: Datos de la solicitud
            db_rrhh: Sesión de RRHH
        
        Returns:
            bool: True si se envió correctamente
        """
        print(f"DEBUG EMAIL SERVICE: Iniciando send_workflow_notification para misión {mission_id}")
        print(f"DEBUG EMAIL SERVICE: current_state={current_state}, next_state={next_state}")
        print(f"DEBUG EMAIL SERVICE: approved_by={approved_by}")
        
        try:
            # Determinar el departamento siguiente
            next_department_id = self.get_next_department_id(next_state)
            print(f"DEBUG EMAIL SERVICE: next_department_id={next_department_id}")
            
            if not next_department_id:
                logger.info(f"No hay departamento siguiente para el estado {next_state}")
                print(f"DEBUG EMAIL SERVICE: No hay departamento siguiente para el estado {next_state}")
                return True  # No es un error, simplemente no hay departamento siguiente
            
            # Obtener emails de usuarios del departamento siguiente
            department_emails = self.get_department_users_emails(next_department_id, db_rrhh)
            print(f"DEBUG EMAIL SERVICE: department_emails={department_emails}")
            
            if not department_emails:
                logger.warning(f"No se encontraron emails para el departamento {next_department_id}")
                return False
            
            # Obtener información del departamento solicitante
            departamento_info = self.get_departamento_info(mission_id, db_rrhh)
            if departamento_info:
                data['departamento_solicitante'] = departamento_info['nombre']
            else:
                data['departamento_solicitante'] = 'N/A'
            
            # Agregar información adicional
            data['estado_actual'] = next_state
            data['aprobado_por'] = approved_by
            
            print(f"DEBUG EMAIL SERVICE: Datos completos para notificación: {data}")
            
            # Determinar el departamento responsable usando DepartmentService
            department_service = DepartmentService(self.db)
            department = department_service.get_department(next_department_id)
            data['departamento_responsable'] = department.nombre if department else 'Departamento'
            
            # Crear el HTML del email
            html_body = self.create_workflow_notification_email_html(data)
            
            # Preparar el asunto del correo
            subject = f"Solicitud Pendiente de Revisión - {data.get('numero_solicitud', 'N/A')}"
            print(f"DEBUG EMAIL SERVICE: Asunto del correo: {subject}")
            
            # Enviar el email a todos los usuarios del departamento
            await self.send_email(
                to_emails=department_emails,
                subject=subject,
                body=f"Solicitud {data.get('numero_solicitud', '')} pendiente de revisión en {data['departamento_responsable']}",
                html_body=html_body
            )
            
            logger.info(f"Notificación de workflow enviada a {len(department_emails)} usuarios del departamento {next_department_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error enviando notificación de workflow: {str(e)}")
            return False 

    async def send_payment_notification(
        self,
        to_email: str,
        data: Dict[str, Any],
        db_rrhh: Session = None
    ) -> bool:
        """
        Envía notificación de pago completado al solicitante
        
        Args:
            to_email: Email del destinatario
            data: Datos de la solicitud
            db_rrhh: Sesión de RRHH (opcional, para obtener email si no se proporciona)
        
        Returns:
            bool: True si se envió correctamente
        """
        try:
            html_body = self.create_payment_email_html(data)
            
            await self.send_email(
                to_emails=[to_email],
                subject=f"Pago Completado - {data.get('numero_solicitud', 'N/A')}",
                body=f"Su solicitud {data.get('numero_solicitud', '')} ha sido pagada exitosamente.",
                html_body=html_body
            )
            
            logger.info(f"Notificación de pago enviada a {to_email}")
            return True
            
        except Exception as e:
            logger.error(f"Error enviando notificación de pago: {str(e)}")
            return False

    def create_payment_email_html(self, data: Dict[str, Any]) -> str:
        """
        Crea el HTML para el email de notificación de pago
        
        Args:
            data: Datos de la solicitud
            
        Returns:
            str: HTML del email
        """
        html = f"""
        <!DOCTYPE html>
        <html lang="es">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Pago Completado</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 20px;
                }}
                .header {{
                    background-color: #28a745;
                    color: white;
                    padding: 20px;
                    text-align: center;
                    border-radius: 5px 5px 0 0;
                }}
                .content {{
                    background-color: #f8f9fa;
                    padding: 20px;
                    border-radius: 0 0 5px 5px;
                }}
                .info-row {{
                    display: flex;
                    justify-content: space-between;
                    margin-bottom: 10px;
                    padding: 8px 0;
                    border-bottom: 1px solid #dee2e6;
                }}
                .info-label {{
                    font-weight: bold;
                    color: #495057;
                }}
                .info-value {{
                    color: #212529;
                }}
                .success-message {{
                    background-color: #d4edda;
                    color: #155724;
                    padding: 15px;
                    border-radius: 5px;
                    margin: 20px 0;
                    border-left: 4px solid #28a745;
                }}
                .footer {{
                    margin-top: 20px;
                    padding-top: 20px;
                    border-top: 1px solid #dee2e6;
                    font-size: 12px;
                    color: #6c757d;
                    text-align: center;
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>✅ Pago Completado</h1>
                <p>Solicitud {data.get('numero_solicitud', 'N/A')}</p>
            </div>
            
            <div class="content">
                <div class="success-message">
                    <strong>¡Su solicitud ha sido pagada exitosamente!</strong><br>
                    El proceso de pago ha sido completado y los fondos han sido transferidos.
                </div>
                
                <h3>Detalles de la Solicitud:</h3>
                
                <div class="info-row">
                    <span class="info-label">Número de Solicitud:</span>
                    <span class="info-value">{data.get('numero_solicitud', 'N/A')}</span>
                </div>
                
                <div class="info-row">
                    <span class="info-label">Tipo de Misión:</span>
                    <span class="info-value">{data.get('tipo', 'N/A')}</span>
                </div>
                
                <div class="info-row">
                    <span class="info-label">Solicitante:</span>
                    <span class="info-value">{data.get('solicitante', 'N/A')}</span>
                </div>
                
                <div class="info-row">
                    <span class="info-label">Fecha de Salida:</span>
                    <span class="info-value">{data.get('fecha', 'N/A')}</span>
                </div>
                
                <div class="info-row">
                    <span class="info-label">Monto Aprobado:</span>
                    <span class="info-value">{data.get('monto', 'N/A')}</span>
                </div>
                
                <div class="info-row">
                    <span class="info-label">Objetivo:</span>
                    <span class="info-value">{data.get('objetivo', 'N/A')}</span>
                </div>
                
                {f'''
                <div class="info-row">
                    <span class="info-label">Método de Pago:</span>
                    <span class="info-value">{data.get('metodo_pago', 'N/A')}</span>
                </div>
                ''' if data.get('metodo_pago') else ''}
                
                {f'''
                <div class="info-row">
                    <span class="info-label">Número de Transacción:</span>
                    <span class="info-value">{data.get('numero_transaccion', 'N/A')}</span>
                </div>
                ''' if data.get('numero_transaccion') else ''}
                
                {f'''
                <div class="info-row">
                    <span class="info-label">Banco Origen:</span>
                    <span class="info-value">{data.get('banco_origen', 'N/A')}</span>
                </div>
                ''' if data.get('banco_origen') else ''}
                
                {f'''
                <div class="info-row">
                    <span class="info-label">Fecha de Pago:</span>
                    <span class="info-value">{data.get('fecha_pago', 'N/A')}</span>
                </div>
                ''' if data.get('fecha_pago') else ''}
                
                {f'''
                <div class="info-row">
                    <span class="info-label">Procesado por:</span>
                    <span class="info-value">{data.get('procesado_por', 'N/A')}</span>
                </div>
                ''' if data.get('procesado_por') else ''}
            </div>
            
            <div class="footer">
                <p>Este es un mensaje automático del Sistema de Gestión de Viáticos.</p>
                <p>Por favor, no responda a este correo.</p>
            </div>
        </body>
        </html>
        """
        return html 