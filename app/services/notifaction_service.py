from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, text, or_
from ..models.notificacion import Notificacion
from ..schemas.notification import NotificacionCreate, NotificacionUpdate, NotificacionVistoUpdate
from fastapi import HTTPException, status


class NotificationService:
    def __init__(self, db: Session):
        self.db = db

    def get_notifications(self, skip: int = 0, limit: int = 100) -> List[Notificacion]:
        """Get all notifications"""
        return self.db.query(Notificacion).offset(skip).limit(limit).all()

    def get_notification(self, notificacion_id: int) -> Optional[Notificacion]:
        """Get notification by ID"""
        return self.db.query(Notificacion).filter(
            Notificacion.notificacion_id == notificacion_id
        ).first()

    def get_notifications_by_personal_id(self, personal_id: int, skip: int = 0, limit: int = 100) -> List[Notificacion]:
        """Get notifications by personal_id"""
        return self.db.query(Notificacion).filter(
            Notificacion.personal_id == personal_id
        ).offset(skip).limit(limit).all()

    def get_unread_notifications_by_personal_id(self, personal_id: int, skip: int = 0, limit: int = 100) -> List[Notificacion]:
        """Get unread notifications by personal_id"""
        return self.db.query(Notificacion).filter(
            and_(
                Notificacion.personal_id == personal_id,
                Notificacion.visto == False
            )
        ).offset(skip).limit(limit).all()

    def get_notifications_by_mission(self, id_mision: int, skip: int = 0, limit: int = 100) -> List[Notificacion]:
        """Get notifications by mission ID"""
        return self.db.query(Notificacion).filter(
            Notificacion.id_mision == id_mision
        ).offset(skip).limit(limit).all()

    def update_notification_visto(self, notificacion_id: int, visto_data: NotificacionVistoUpdate) -> Notificacion:
        """Update notification visto status"""
        notification = self.get_notification(notificacion_id)
        if not notification:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notification not found"
            )

        notification.visto = visto_data.visto
        self.db.commit()
        self.db.refresh(notification)
        return notification

    def mark_notification_as_read(self, notificacion_id: int) -> Notificacion:
        """Mark notification as read (visto = True)"""
        return self.update_notification_visto(notificacion_id, NotificacionVistoUpdate(visto=True))

    def mark_notification_as_unread(self, notificacion_id: int) -> Notificacion:
        """Mark notification as unread (visto = False)"""
        return self.update_notification_visto(notificacion_id, NotificacionVistoUpdate(visto=False))

    def get_notification_count_by_personal_id(self, personal_id: int, unread_only: bool = False) -> int:
        """Get notification count by personal_id"""
        query = self.db.query(Notificacion).filter(Notificacion.personal_id == personal_id)
        if unread_only:
            query = query.filter(Notificacion.visto == False)
        return query.count()

    def get_notifications_for_logged_user(self, personal_id: int, skip: int = 0, limit: int = 100) -> List[Notificacion]:
        """
        Obtiene todas las notificaciones donde el usuario loggeado es el destinatario (personal_id)
        
        Args:
            personal_id: personal_id del usuario loggeado
            skip: Número de registros a saltar para paginación
            limit: Número máximo de registros a retornar
            
        Returns:
            List[Notificacion]: Lista de notificaciones del usuario
        """
        return self.db.query(Notificacion).filter(
            and_(
                Notificacion.personal_id == personal_id,
                Notificacion.visto == False
            )
        ).order_by(Notificacion.created_at.desc()).offset(skip).limit(limit).all()

    def get_notifications_for_logged_user_with_count(self, personal_id: int, skip: int = 0, limit: int = 100) -> Dict[str, Any]:
        """
        Obtiene las notificaciones no vistas del usuario loggeado junto con el contador total
        
        Args:
            personal_id: personal_id del usuario loggeado
            skip: Número de registros a saltar para paginación
            limit: Número máximo de registros a retornar
            
        Returns:
            Dict con las notificaciones y el contador total
        """
        # Obtener el contador total de notificaciones no vistas
        total_count = self.db.query(Notificacion).filter(
            and_(
                Notificacion.personal_id == personal_id,
                Notificacion.visto == False
            )
        ).count()
        
        # Obtener las notificaciones paginadas
        notifications = self.db.query(Notificacion).filter(
            and_(
                Notificacion.personal_id == personal_id,
                Notificacion.visto == False
            )
        ).order_by(Notificacion.created_at.desc()).offset(skip).limit(limit).all()
        
        return {
            "notifications": notifications,
            "total_count": total_count,
            "skip": skip,
            "limit": limit
        }

    def get_notifications_for_logged_user_with_created_missions(self, personal_id: int, skip: int = 0, limit: int = 100) -> List[Notificacion]:
        """
        Obtiene todas las notificaciones no vistas donde el usuario loggeado es el destinatario (personal_id)
        más todas las notificaciones no vistas de las misiones que él creó (como beneficiario/solicitante)
        
        Args:
            personal_id: personal_id del usuario loggeado
            skip: Número de registros a saltar para paginación
            limit: Número máximo de registros a retornar
            
        Returns:
            List[Notificacion]: Lista de notificaciones del usuario y de sus misiones creadas
        """
        # Query para obtener las misiones donde el usuario es el beneficiario/solicitante
        misiones_creadas_query = text("""
            SELECT id_mision 
            FROM misiones 
            WHERE beneficiario_personal_id = :personal_id
        """)
        
        misiones_result = self.db.execute(misiones_creadas_query, {"personal_id": personal_id})
        misiones_ids = [row.id_mision for row in misiones_result.fetchall()]
        
        # Query para obtener notificaciones no vistas: del usuario + de sus misiones creadas
        if misiones_ids:
            # Si tiene misiones creadas, incluir notificaciones de esas misiones también
            query = self.db.query(Notificacion).filter(
                and_(
                    or_(
                        Notificacion.personal_id == personal_id,
                        Notificacion.id_mision.in_(misiones_ids)
                    ),
                    Notificacion.visto == False
                )
            )
        else:
            # Si no tiene misiones creadas, solo sus notificaciones personales no vistas
            query = self.db.query(Notificacion).filter(
                and_(
                    Notificacion.personal_id == personal_id,
                    Notificacion.visto == False
                )
            )
        
        return query.order_by(Notificacion.created_at.desc()).offset(skip).limit(limit).all()

    def get_notifications_for_logged_user_with_created_missions_with_count(self, personal_id: int, skip: int = 0, limit: int = 100) -> Dict[str, Any]:
        """
        Obtiene las notificaciones no vistas del usuario loggeado + de sus misiones creadas junto con el contador total
        
        Args:
            personal_id: personal_id del usuario loggeado
            skip: Número de registros a saltar para paginación
            limit: Número máximo de registros a retornar
            
        Returns:
            Dict con las notificaciones y el contador total
        """
        # Query para obtener las misiones donde el usuario es el beneficiario/solicitante
        misiones_creadas_query = text("""
            SELECT id_mision 
            FROM misiones 
            WHERE beneficiario_personal_id = :personal_id
        """)
        
        misiones_result = self.db.execute(misiones_creadas_query, {"personal_id": personal_id})
        misiones_ids = [row.id_mision for row in misiones_result.fetchall()]
        
        # Query para obtener notificaciones no vistas: del usuario + de sus misiones creadas
        if misiones_ids:
            # Si tiene misiones creadas, incluir notificaciones de esas misiones también
            base_query = self.db.query(Notificacion).filter(
                and_(
                    or_(
                        Notificacion.personal_id == personal_id,
                        Notificacion.id_mision.in_(misiones_ids)
                    ),
                    Notificacion.visto == False
                )
            )
        else:
            # Si no tiene misiones creadas, solo sus notificaciones personales no vistas
            base_query = self.db.query(Notificacion).filter(
                and_(
                    Notificacion.personal_id == personal_id,
                    Notificacion.visto == False
                )
            )
        
        # Obtener el contador total
        total_count = base_query.count()
        
        # Obtener las notificaciones paginadas
        notifications = base_query.order_by(Notificacion.created_at.desc()).offset(skip).limit(limit).all()
        
        return {
            "notifications": notifications,
            "total_count": total_count,
            "skip": skip,
            "limit": limit
        }

    def get_notification_count_for_logged_user(self, personal_id: int, unread_only: bool = False) -> int:
        """
        Obtiene el conteo de notificaciones donde el usuario loggeado es el destinatario
        
        Args:
            personal_id: personal_id del usuario loggeado
            unread_only: Si True, solo cuenta notificaciones no leídas
            
        Returns:
            int: Número de notificaciones
        """
        query = self.db.query(Notificacion).filter(Notificacion.personal_id == personal_id)
        if unread_only:
            query = query.filter(Notificacion.visto == False)
        return query.count()

    def get_notification_count_for_logged_user_with_created_missions(self, personal_id: int, unread_only: bool = False) -> int:
        """
        Obtiene el conteo de notificaciones donde el usuario loggeado es el destinatario
        más las notificaciones de las misiones que él creó
        
        Args:
            personal_id: personal_id del usuario loggeado
            unread_only: Si True, solo cuenta notificaciones no leídas
            
        Returns:
            int: Número de notificaciones
        """
        # Query para obtener las misiones donde el usuario es el beneficiario/solicitante
        misiones_creadas_query = text("""
            SELECT id_mision 
            FROM misiones 
            WHERE beneficiario_personal_id = :personal_id
        """)
        
        misiones_result = self.db.execute(misiones_creadas_query, {"personal_id": personal_id})
        misiones_ids = [row.id_mision for row in misiones_result.fetchall()]
        
        # Query para contar notificaciones: del usuario + de sus misiones creadas
        if misiones_ids:
            # Si tiene misiones creadas, incluir notificaciones de esas misiones también
            query = self.db.query(Notificacion).filter(
                or_(
                    Notificacion.personal_id == personal_id,
                    Notificacion.id_mision.in_(misiones_ids)
                )
            )
        else:
            # Si no tiene misiones creadas, solo sus notificaciones personales
            query = self.db.query(Notificacion).filter(
                Notificacion.personal_id == personal_id
            )
        
        if unread_only:
            query = query.filter(Notificacion.visto == False)
        
        return query.count()

    def create_notification(self, notification_data: NotificacionCreate) -> Notificacion:
        """Create a new notification"""
        print(f"🔔 Creando notificación con datos: {notification_data}")
        
        try:
            notification = Notificacion(
                titulo=notification_data.titulo,
                descripcion=notification_data.descripcion,
                personal_id=notification_data.personal_id,
                id_mision=notification_data.id_mision,
                visto=notification_data.visto
            )
            
            print(f"🔔 Objeto notificación creado: {notification}")
            
            self.db.add(notification)
            print(f"🔔 Notificación agregada a la sesión")
            
            self.db.commit()
            print(f"🔔 Commit realizado")
            
            self.db.refresh(notification)
            print(f"✅ Notificación creada exitosamente: {notification.notificacion_id}")
            
            return notification
            
        except Exception as e:
            print(f"❌ ERROR creando notificación: {str(e)}")
            self.db.rollback()
            raise e

    def get_next_department_id(self, current_state: str) -> Optional[int]:
        """
        Determina el ID del departamento siguiente en el flujo basado en el estado actual
        
        Args:
            current_state: Estado actual de la misión
            
        Returns:
            int: ID del departamento siguiente o None si no hay departamento siguiente
        """
        print(f"DEBUG NOTIFICATION SERVICE: get_next_department_id para current_state={current_state}")
        
        # Mapeo de estados a departamentos (mismo que en EmailService)
        state_to_department = {
            'PENDIENTE_JEFE': None,  # Jefe inmediato (no es departamento financiero)
            'PENDIENTE_REVISION_TESORERIA': 1,  # Tesorería
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
        print(f"DEBUG NOTIFICATION SERVICE: get_next_department_id resultado={result}")
        return result

    def get_department_users_personal_ids(self, department_id: int) -> List[int]:
        """
        Obtiene los personal_ids de todos los usuarios activos de un departamento específico
        
        Args:
            department_id: ID del departamento en aitsa_financiero
            
        Returns:
            List[int]: Lista de personal_ids de usuarios del departamento
        """
        print(f"DEBUG NOTIFICATION SERVICE: get_department_users_personal_ids para department_id={department_id}")
        try:
            # Query para obtener personal_ids de usuarios del departamento
            usuarios_query = text("""
                SELECT personal_id_rrhh
                FROM usuarios
                WHERE id_departamento = :department_id
                  AND is_active = 1
                  AND personal_id_rrhh IS NOT NULL
            """)
            
            usuarios_result = self.db.execute(usuarios_query, {"department_id": department_id})
            usuarios_rows = usuarios_result.fetchall()
            print(f"DEBUG NOTIFICATION SERVICE: Usuarios encontrados en departamento {department_id}: {len(usuarios_rows)}")
            
            personal_ids = [row.personal_id_rrhh for row in usuarios_rows]
            print(f"DEBUG NOTIFICATION SERVICE: personal_ids extraídos: {personal_ids}")
            
            # logger.info(f"Encontrados {len(personal_ids)} usuarios para departamento {department_id}") # Original code had this line commented out
            return personal_ids
            
        except Exception as e:
            # logger.error(f"Error obteniendo usuarios del departamento {department_id}: {str(e)}") # Original code had this line commented out
            return []

    def create_workflow_notifications_for_department(
        self, 
        mission_id: int, 
        next_state: str, 
        titulo: str, 
        descripcion: str
    ) -> List[Notificacion]:
        """
        Crea notificaciones para todos los usuarios del departamento siguiente en el workflow
        
        Args:
            mission_id: ID de la misión (se usa para el campo id_mision en la base de datos)
            next_state: Estado siguiente al que se movió la misión
            titulo: Título de la notificación (debe incluir numero_solicitud)
            descripcion: Descripción de la notificación (debe incluir numero_solicitud)
            
        Returns:
            List[Notificacion]: Lista de notificaciones creadas
        """
        print(f"DEBUG NOTIFICATION SERVICE: create_workflow_notifications_for_department para misión {mission_id}")
        print(f"DEBUG NOTIFICATION SERVICE: next_state={next_state}")
        print(f"DEBUG NOTIFICATION SERVICE: titulo={titulo}")
        print(f"DEBUG NOTIFICATION SERVICE: descripcion={descripcion}")
        
        try:
            # Determinar el departamento siguiente
            next_department_id = self.get_next_department_id(next_state)
            print(f"DEBUG NOTIFICATION SERVICE: next_department_id={next_department_id}")
            
            if not next_department_id:
                # logger.info(f"No hay departamento siguiente para el estado {next_state}") # Original code had this line commented out
                print(f"DEBUG NOTIFICATION SERVICE: No hay departamento siguiente para el estado {next_state}")
                return []  # No es un error, simplemente no hay departamento siguiente
            
            # Obtener personal_ids de usuarios del departamento siguiente
            department_personal_ids = self.get_department_users_personal_ids(next_department_id)
            print(f"DEBUG NOTIFICATION SERVICE: department_personal_ids={department_personal_ids}")
            
            if not department_personal_ids:
                # logger.warning(f"No se encontraron usuarios para el departamento {next_department_id}") # Original code had this line commented out
                return []
            
            # Crear notificaciones para cada usuario del departamento
            notifications_created = []
            print(f"🔔 Iniciando creación de {len(department_personal_ids)} notificaciones")
            
            for i, personal_id in enumerate(department_personal_ids):
                print(f"🔔 Creando notificación {i+1}/{len(department_personal_ids)} para personal_id: {personal_id}")
                
                try:
                    notification_data = NotificacionCreate(
                        titulo=titulo,
                        descripcion=descripcion,
                        personal_id=personal_id,
                        id_mision=mission_id,  # Este campo debe ser el ID numérico para la relación en BD
                        visto=False
                    )
                    
                    print(f"🔔 Datos de notificación preparados para personal_id {personal_id}")
                    
                    notification = self.create_notification(notification_data)
                    notifications_created.append(notification)
                    print(f"✅ Notificación {i+1} creada exitosamente")
                    
                except Exception as e:
                    print(f"❌ ERROR creando notificación {i+1} para personal_id {personal_id}: {str(e)}")
                    # Continuar con las siguientes notificaciones
                    continue
            
            print(f"🔔 Total de notificaciones creadas exitosamente: {len(notifications_created)}")
            return notifications_created
            
        except Exception as e:
            # logger.error(f"Error creando notificaciones de workflow: {str(e)}") # Original code had this line commented out
            return []

    def create_mission_created_notification(self, mission_id: int, jefe_personal_id: int, numero_solicitud: str = None) -> Notificacion:
        """Create notification when mission is created - for immediate supervisor"""
        # Usar numero_solicitud si está disponible, sino usar mission_id como fallback
        identificador = numero_solicitud if numero_solicitud else f"#{mission_id}"
        
        notification_data = NotificacionCreate(
            titulo="Nueva Solicitud",
            descripcion=f"Nueva solicitud {identificador} requiere su aprobación",
            personal_id=jefe_personal_id,
            id_mision=mission_id,
            visto=False
        )
        
        return self.create_notification(notification_data)

    def create_mission_returned_notification(self, mission_id: int, jefe_personal_id: int, motivo: str = None, numero_solicitud: str = None) -> Notificacion:
        """Create notification when mission is returned for correction - for immediate supervisor"""
        # Usar numero_solicitud si está disponible, sino usar mission_id como fallback
        identificador = numero_solicitud if numero_solicitud else f"#{mission_id}"
        
        descripcion = f"Solicitud {identificador} devuelta para corrección"
        if motivo:
            descripcion += f". Motivo: {motivo}"
        
        notification_data = NotificacionCreate(
            titulo="Solicitud Devuelta",
            descripcion=descripcion,
            personal_id=jefe_personal_id,
            id_mision=mission_id,
            visto=False
        )
        
        return self.create_notification(notification_data)

    def create_mission_rejected_notification(self, mission_id: int, beneficiary_personal_id: int, motivo: str = None) -> Notificacion:
        """Create notification when mission is rejected - for beneficiary/solicitante"""
        descripcion = f"Solicitud #{mission_id} rechazada"
        if motivo:
            descripcion += f". Motivo: {motivo}"
        
        notification_data = NotificacionCreate(
            titulo="Solicitud Rechazada",
            descripcion=descripcion,
            personal_id=beneficiary_personal_id,
            id_mision=mission_id,
            visto=False
        )
        
        return self.create_notification(notification_data)

    def create_mission_approved_notification(self, mission_id: int, personal_id: int, estado_nuevo: str) -> Notificacion:
        """Create notification when mission is approved - for other workflow users"""
        notification_data = NotificacionCreate(
            titulo=f"Misión #{mission_id} Aprobada",
            descripcion=f"Misión #{mission_id} aprobada. Estado: {estado_nuevo}",
            personal_id=personal_id,
            id_mision=mission_id,
            visto=False
        )
        
        return self.create_notification(notification_data)

    def get_all_notifications_for_logged_user_with_filters(
        self, 
        personal_id: int, 
        skip: int = 0, 
        limit: int = 100,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        visto: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        Obtiene todas las notificaciones del usuario loggeado con filtros opcionales
        
        Args:
            personal_id: personal_id del usuario loggeado
            skip: Número de registros a saltar para paginación
            limit: Número máximo de registros a retornar
            start_date: Fecha de inicio en formato YYYY-MM-DD (opcional)
            end_date: Fecha de fin en formato YYYY-MM-DD (opcional)
            visto: Filtrar por estado visto (True/False) o None para todos
            
        Returns:
            Dict con las notificaciones y el contador total
        """
        from datetime import datetime
        
        # Query base para obtener todas las notificaciones del usuario
        query = self.db.query(Notificacion).filter(
            Notificacion.personal_id == personal_id
        )
        
        # Aplicar filtro de fecha de inicio
        if start_date:
            try:
                start_datetime = datetime.strptime(start_date, "%Y-%m-%d")
                query = query.filter(Notificacion.created_at >= start_datetime)
            except ValueError:
                # Si la fecha no es válida, ignorar el filtro
                pass
        
        # Aplicar filtro de fecha de fin
        if end_date:
            try:
                end_datetime = datetime.strptime(end_date, "%Y-%m-%d")
                # Añadir 23:59:59 para incluir todo el día
                end_datetime = end_datetime.replace(hour=23, minute=59, second=59)
                query = query.filter(Notificacion.created_at <= end_datetime)
            except ValueError:
                # Si la fecha no es válida, ignorar el filtro
                pass
        
        # Aplicar filtro de visto
        if visto is not None:
            query = query.filter(Notificacion.visto == visto)
        
        # Obtener el contador total antes de aplicar paginación
        total_count = query.count()
        
        # Aplicar ordenamiento y paginación
        notifications = query.order_by(Notificacion.created_at.desc()).offset(skip).limit(limit).all()
        
        return {
            "notifications": notifications,
            "total_count": total_count,
            "skip": skip,
            "limit": limit,
            "filters": {
                "start_date": start_date,
                "end_date": end_date,
                "visto": visto
            }
        }
