# app/services/configuration.py

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import text
from fastapi import HTTPException, status

from app.models.configuration import ConfiguracionGeneral, ConfiguracionSistema, ConfiguracionNotificacion
from app.schemas.configuration import (
    ConfiguracionGeneralCreate, 
    ConfiguracionGeneralUpdate,
    ConfiguracionSistemaCreate, 
    ConfiguracionSistemaUpdate,
    ConfiguracionNotificacionCreate,
    ConfiguracionNotificacionUpdate,
    PersonalRRHH
)

class ConfigurationService:
    def __init__(self, db: Session):
        self.db = db

    # === CONFIGURACIÓN GENERAL ===
    def get_configuracion_general(self) -> Optional[ConfiguracionGeneral]:
        """Obtiene la configuración general (debería ser única)"""
        return self.db.query(ConfiguracionGeneral).first()

    def create_configuracion_general(self, config_data: ConfiguracionGeneralCreate) -> ConfiguracionGeneral:
        """Crea la configuración general"""
        # Verificar que no exista ya una configuración
        existing = self.db.query(ConfiguracionGeneral).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ya existe una configuración general. Use UPDATE en su lugar."
            )

        db_config = ConfiguracionGeneral(**config_data.model_dump())
        self.db.add(db_config)
        self.db.commit()
        self.db.refresh(db_config)
        return db_config

    def update_configuracion_general(self, config_data: ConfiguracionGeneralUpdate) -> ConfiguracionGeneral:
        """Actualiza la configuración general"""
        db_config = self.db.query(ConfiguracionGeneral).first()
        
        if not db_config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No existe configuración general. Créela primero."
            )

        # Actualizar solo los campos proporcionados
        update_data = config_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_config, field, value)

        self.db.commit()
        self.db.refresh(db_config)
        return db_config

    # === CONFIGURACIÓN SISTEMA ===
    def get_configuraciones_sistema(self) -> List[ConfiguracionSistema]:
        """Obtiene todas las configuraciones del sistema"""
        return self.db.query(ConfiguracionSistema).order_by(ConfiguracionSistema.clave).all()

    def get_configuracion_sistema_by_clave(self, clave: str) -> Optional[ConfiguracionSistema]:
        """Obtiene una configuración específica por clave"""
        return self.db.query(ConfiguracionSistema).filter(ConfiguracionSistema.clave == clave).first()

    def create_configuracion_sistema(self, config_data: ConfiguracionSistemaCreate) -> ConfiguracionSistema:
        """Crea una nueva configuración del sistema"""
        # Verificar que no exista ya esa clave
        existing = self.get_configuracion_sistema_by_clave(config_data.clave)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Ya existe una configuración con la clave '{config_data.clave}'"
            )

        db_config = ConfiguracionSistema(**config_data.model_dump())
        self.db.add(db_config)
        self.db.commit()
        self.db.refresh(db_config)
        return db_config

    def update_configuracion_sistema(self, clave: str, config_data: ConfiguracionSistemaUpdate) -> ConfiguracionSistema:
        """Actualiza una configuración del sistema"""
        db_config = self.get_configuracion_sistema_by_clave(clave)
        
        if not db_config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No existe configuración con la clave '{clave}'"
            )

        if not db_config.es_modificable:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"La configuración '{clave}' no es modificable"
            )

        # Actualizar solo los campos proporcionados
        update_data = config_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_config, field, value)

        self.db.commit()
        self.db.refresh(db_config)
        return db_config

    def delete_configuracion_sistema(self, clave: str) -> bool:
        """Elimina una configuración del sistema"""
        db_config = self.get_configuracion_sistema_by_clave(clave)
        
        if not db_config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No existe configuración con la clave '{clave}'"
            )

        if not db_config.es_modificable:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"La configuración '{clave}' no es modificable"
            )

        self.db.delete(db_config)
        self.db.commit()
        return True

    # === CONFIGURACIÓN NOTIFICACIONES ===
    def get_configuraciones_notificaciones(self) -> List[ConfiguracionNotificacion]:
        """Obtiene todas las configuraciones de notificaciones"""
        return self.db.query(ConfiguracionNotificacion).order_by(ConfiguracionNotificacion.tipo_notificacion).all()

    def get_configuracion_notificacion_by_id(self, notif_id: int) -> Optional[ConfiguracionNotificacion]:
        """Obtiene una configuración de notificación por ID"""
        return self.db.query(ConfiguracionNotificacion).filter(ConfiguracionNotificacion.id_configuracion_notificacion == notif_id).first()

    def get_configuracion_notificacion_by_tipo(self, tipo: str) -> Optional[ConfiguracionNotificacion]:
        """Obtiene una configuración de notificación por tipo"""
        return self.db.query(ConfiguracionNotificacion).filter(ConfiguracionNotificacion.tipo_notificacion == tipo).first()

    def create_configuracion_notificacion(self, config_data: ConfiguracionNotificacionCreate) -> ConfiguracionNotificacion:
        """Crea una nueva configuración de notificación"""
        # Verificar que no exista ya ese tipo
        existing = self.get_configuracion_notificacion_by_tipo(config_data.tipo_notificacion)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Ya existe una configuración para el tipo '{config_data.tipo_notificacion}'"
            )

        db_config = ConfiguracionNotificacion(**config_data.model_dump())
        self.db.add(db_config)
        self.db.commit()
        self.db.refresh(db_config)
        return db_config

    def update_configuracion_notificacion(self, notif_id: int, config_data: ConfiguracionNotificacionUpdate) -> ConfiguracionNotificacion:
        """Actualiza una configuración de notificación"""
        db_config = self.get_configuracion_notificacion_by_id(notif_id)
        
        if not db_config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No existe configuración de notificación con ID '{notif_id}'"
            )

        if not db_config.es_modificable:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"La configuración de notificación '{db_config.tipo_notificacion}' no es modificable"
            )

        # Actualizar solo los campos proporcionados
        update_data = config_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_config, field, value)

        self.db.commit()
        self.db.refresh(db_config)
        return db_config

    def delete_configuracion_notificacion(self, notif_id: int) -> bool:
        """Elimina una configuración de notificación"""
        db_config = self.get_configuracion_notificacion_by_id(notif_id)
        
        if not db_config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No existe configuración de notificación con ID '{notif_id}'"
            )

        if not db_config.es_modificable:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"La configuración de notificación '{db_config.tipo_notificacion}' no es modificable"
            )

        self.db.delete(db_config)
        self.db.commit()
        return True

    # === PERSONAL RRHH ===
    def search_personal_rrhh(self, query: str, limit: int = 20) -> List[PersonalRRHH]:
        """Busca personal en RRHH por nombre o ficha"""
        if len(query) < 2:
            return []
        
        try:
            # Buscar por nombre o ficha
            result = self.db.execute(text("""
                SELECT personal_id, apenom, ficha 
                FROM aitsa_rrhh.nompersonal 
                WHERE (apenom LIKE :query OR ficha LIKE :query_ficha) 
                  AND estado != 'De Baja'
                ORDER BY apenom
                LIMIT :limit
            """), {
                "query": f"%{query}%",
                "query_ficha": f"{query}%",
                "limit": limit
            })
            
            personal_list = []
            for row in result.fetchall():
                personal_list.append(PersonalRRHH(
                    personal_id=row.personal_id,
                    apenom=row.apenom,
                    ficha=str(row.ficha)  # Convertir a string
                ))
            
            return personal_list
        except Exception as e:
            print(f"Error buscando personal en RRHH: {e}")
            return []

    def get_personal_rrhh_by_id(self, personal_id: int) -> Optional[PersonalRRHH]:
        """Obtiene un personal específico por ID"""
        try:
            result = self.db.execute(text("""
                SELECT personal_id, apenom, ficha 
                FROM aitsa_rrhh.nompersonal 
                WHERE personal_id = :personal_id AND estado != 'De Baja'
            """), {"personal_id": personal_id})
            
            row = result.fetchone()
            if row:
                return PersonalRRHH(
                    personal_id=row.personal_id,
                    apenom=row.apenom,
                    ficha=str(row.ficha)  # Convertir a string
                )
            return None
        except Exception as e:
            print(f"Error obteniendo personal en RRHH: {e}")
            return None

    def get_configuraciones_as_dict(self) -> Dict[str, Any]:
        """Retorna todas las configuraciones como un diccionario clave-valor"""
        configs = self.get_configuraciones_sistema()
        result = {}
        
        for config in configs:
            value = config.valor
            
            # Convertir según el tipo de dato
            if config.tipo_dato == "NUMBER":
                try:
                    value = float(value) if '.' in value else int(value)
                except ValueError:
                    value = config.valor
            elif config.tipo_dato == "BOOLEAN":
                value = value.lower() in ['true', '1', 'yes', 'on']
            elif config.tipo_dato == "JSON":
                try:
                    import json
                    value = json.loads(value)
                except:
                    value = config.valor
            
            result[config.clave] = value
        
        return result

    def ensure_default_configurations(self):
        """Asegurar que las configuraciones por defecto existan"""
        default_configs = [
            {
                "clave": "LIMITE_EFECTIVO_VIATICOS",
                "valor": "200.00",
                "tipo_dato": "NUMBER",
                "descripcion": "Límite máximo para pago de viáticos en efectivo (B/.)",
                "es_modificable": True
            },
            {
                "clave": "DIAS_LIMITE_PRESENTACION",
                "valor": "10",
                "tipo_dato": "NUMBER", 
                "descripcion": "Días mínimos de anticipación para solicitar viáticos",
                "es_modificable": True
            },
            {
                "clave": "MONTO_REFRENDO_CGR",
                "valor": "1000.00",
                "tipo_dato": "NUMBER",
                "descripcion": "Monto mínimo que requiere refrendo de CGR (B/.)",
                "es_modificable": True
            }
        ]
        
        for config_data in default_configs:
            existing = self.get_configuracion_sistema_by_clave(config_data["clave"])
            if not existing:
                db_config = ConfiguracionSistema(**config_data)
                self.db.add(db_config)
        
        self.db.commit()