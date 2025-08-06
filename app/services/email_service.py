# app/services/email_service.py

import logging
from typing import List, Optional, Dict, Any
from pathlib import Path
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.services.configuration import ConfigurationService
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
            use_ssl = config.smtp_seguridad.lower() == 'ssl'
            use_tls = config.smtp_seguridad.lower() == 'tls'
            
            connection_config = ConnectionConfig(
                MAIL_USERNAME=config.smtp_usuario,
                MAIL_PASSWORD=config.smtp_password,
                MAIL_FROM=config.email_remitente,
                MAIL_PORT=config.smtp_puerto,
                MAIL_SERVER=config.smtp_servidor,
                MAIL_SSL=use_ssl,
                MAIL_TLS=use_tls,
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
            
            # Si es un empleado (usuario_creacion es personal_id de RRHH)
            if mission.usuario_creacion:
                # Buscar en la tabla nompersonal de RRHH
                from sqlalchemy import text
                query = text("""
                    SELECT email 
                    FROM nompersonal 
                    WHERE personal_id = :personal_id
                """)
                
                result = db_rrhh.execute(query, {"personal_id": mission.usuario_creacion})
                row = result.fetchone()
                
                if row and row[0]:
                    logger.info(f"Email encontrado para empleado {mission.usuario_creacion}: {row[0]}")
                    return row[0]
            
            # Si no se encontró, intentar buscar como usuario financiero
            if mission.usuario_creacion:
                # Buscar en la tabla usuarios de financiero
                from app.models.user import Usuario
                usuario = self.db.query(Usuario).filter(Usuario.id_usuario == mission.usuario_creacion).first()
                
                if usuario and usuario.personal_id:
                    # Buscar el email en RRHH usando personal_id
                    query = text("""
                        SELECT email 
                        FROM nompersonal 
                        WHERE personal_id = :personal_id
                    """)
                    
                    result = db_rrhh.execute(query, {"personal_id": usuario.personal_id})
                    row = result.fetchone()
                    
                    if row and row[0]:
                        logger.info(f"Email encontrado para usuario financiero {usuario.id_usuario}: {row[0]}")
                        return row[0]
            
            logger.warning(f"No se pudo obtener email para misión {mission_id}")
            return None
            
        except Exception as e:
            logger.error(f"Error obteniendo email del solicitante: {str(e)}")
            return None

    async def send_email(
        self,
        to_emails: List[str],
        subject: str,
        body: str,
        html_body: Optional[str] = None,
        attachments: Optional[List[Dict[str, Any]]] = None
    ) -> bool:
        """
        Envía un email
        
        Args:
            to_emails: Lista de emails destinatarios
            subject: Asunto del email
            body: Cuerpo del email (texto plano)
            html_body: Cuerpo del email en HTML (opcional)
            attachments: Lista de adjuntos [{"file": Path, "filename": str}]
        
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
            
            # Agregar adjuntos si existen
            if attachments:
                message.attachments = []
                for attachment in attachments:
                    if isinstance(attachment["file"], (str, Path)):
                        file_path = Path(attachment["file"])
                        if file_path.exists():
                            message.attachments.append({
                                "file": file_path,
                                "filename": attachment.get("filename", file_path.name)
                            })
                        else:
                            logger.warning(f"Archivo no encontrado: {file_path}")
            
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
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .header {{ background-color: #28a745; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 20px; }}
                .details {{ background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0; }}
                .footer {{ background-color: #6c757d; color: white; padding: 15px; text-align: center; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>✅ Solicitud Aprobada</h1>
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
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .header {{ background-color: #dc3545; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 20px; }}
                .details {{ background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0; }}
                .reason {{ background-color: #fff3cd; border: 1px solid #ffeaa7; padding: 15px; border-radius: 5px; margin: 20px 0; }}
                .footer {{ background-color: #6c757d; color: white; padding: 15px; text-align: center; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>❌ Solicitud Rechazada</h1>
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
            </div>
        </body>
        </html>
        """

    def create_return_email_html(self, data: Dict[str, Any]) -> str:
        """Crea el HTML para emails de solicitudes devueltas"""
        return f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .header {{ background-color: #ffc107; color: #212529; padding: 20px; text-align: center; }}
                .content {{ padding: 20px; }}
                .details {{ background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0; }}
                .observations {{ background-color: #fff3cd; border: 1px solid #ffeaa7; padding: 15px; border-radius: 5px; margin: 20px 0; }}
                .footer {{ background-color: #6c757d; color: white; padding: 15px; text-align: center; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>⚠️ Solicitud Devuelta</h1>
            </div>
            <div class="content">
                <p>Su solicitud ha sido <strong>DEVUELTA</strong> para correcciones.</p>
                
                <div class="observations">
                    <h3>Observaciones:</h3>
                    <p>{data.get('observaciones', 'No especificadas')}</p>
                </div>
                
                <div class="details">
                    <h3>Detalles de la Solicitud:</h3>
                    <ul>
                        <li><strong>Número de Solicitud:</strong> {data.get('numero_solicitud', 'N/A')}</li>
                        <li><strong>Tipo:</strong> {data.get('tipo', 'N/A')}</li>
                        <li><strong>Fecha:</strong> {data.get('fecha', 'N/A')}</li>
                        <li><strong>Monto:</strong> {data.get('monto', 'N/A')}</li>
                        <li><strong>Devuelto por:</strong> {data.get('devuelto_por', 'N/A')}</li>
                    </ul>
                </div>
                
                <p>Por favor, revise y corrija los puntos mencionados.</p>
            </div>
            <div class="footer">
                <p>Sistema de Gestión de Viáticos - AITSA</p>
            </div>
        </body>
        </html>
        """ 