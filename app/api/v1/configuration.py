# app/api/v1/configuration.py

import os
import shutil
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.database import get_db_financiero
from app.api.deps import get_current_user
from app.models.user import Usuario
from app.services.configuration import ConfigurationService
from app.schemas.configuration import (
    ConfiguracionGeneral,
    ConfiguracionGeneralCreate,
    ConfiguracionGeneralUpdate,
    ConfiguracionSistema,
    ConfiguracionSistemaCreate,
    ConfiguracionSistemaUpdate,
    ConfiguracionNotificacion,
    ConfiguracionNotificacionCreate,
    ConfiguracionNotificacionUpdate,
    PersonalRRHH,
    PersonalRRHHSearch
)

router = APIRouter()

# Configuración para subida de archivos
UPLOAD_DIR = "uploads/logos"
ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

# Crear directorio si no existe
os.makedirs(UPLOAD_DIR, exist_ok=True)

# === CONFIGURACIÓN GENERAL ===

@router.get("/general", response_model=ConfiguracionGeneral)
async def get_configuracion_general(
    db: Session = Depends(get_db_financiero),
    current_user: Usuario = Depends(get_current_user)
):
    """Obtiene la configuración general del sistema"""
    service = ConfigurationService(db)
    config = service.get_configuracion_general()
    
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No existe configuración general"
        )
    
    return config

@router.post("/general", response_model=ConfiguracionGeneral)
async def create_configuracion_general(
    config_data: ConfiguracionGeneralCreate,
    db: Session = Depends(get_db_financiero),
    current_user: Usuario = Depends(get_current_user)
):
    """Crea la configuración general (solo si no existe)"""
    # Verificar permisos de administrador
    if current_user.rol.nombre_rol != "Administrador Sistema":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo los administradores pueden crear la configuración general"
        )
    
    service = ConfigurationService(db)
    return service.create_configuracion_general(config_data)

@router.put("/general", response_model=ConfiguracionGeneral)
async def update_configuracion_general(
    config_data: ConfiguracionGeneralUpdate,
    db: Session = Depends(get_db_financiero),
    current_user: Usuario = Depends(get_current_user)
):
    """Actualiza la configuración general"""
    # Verificar permisos de administrador
    if current_user.rol.nombre_rol != "Administrador Sistema":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo los administradores pueden modificar la configuración general"
        )
    
    service = ConfigurationService(db)
    return service.update_configuracion_general(config_data)

@router.post("/general/logo")
async def upload_logo(
    file: UploadFile = File(...),
    db: Session = Depends(get_db_financiero),
    current_user: Usuario = Depends(get_current_user)
):
    """Sube el logo de la empresa"""
    # Validar extensión
    file_extension = os.path.splitext(file.filename)[1].lower()
    if file_extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tipo de archivo no permitido. Extensiones permitidas: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    
    # Validar tamaño
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Archivo muy grande. Tamaño máximo: {MAX_FILE_SIZE // (1024 * 1024)}MB"
        )
    
    # Generar nombre único
    import uuid
    unique_filename = f"logo_{uuid.uuid4()}{file_extension}"
    file_path = os.path.join(UPLOAD_DIR, unique_filename)
    
    # Guardar archivo
    with open(file_path, "wb") as buffer:
        buffer.write(contents)
    
    # Actualizar configuración general
    config_service = ConfigurationService(db)
    relative_path = f"/uploads/logos/{unique_filename}"
    
    # Eliminar logo anterior si existe
    config = config_service.get_configuracion_general()
    if config and config.logo_empresa:
        old_file_path = f".{config.logo_empresa}"
        if os.path.exists(old_file_path):
            os.remove(old_file_path)
    
    # Actualizar con nueva ruta
    config_service.update_configuracion_general(
        ConfiguracionGeneralUpdate(logo_empresa=relative_path)
    )
    
    return {"message": "Logo subido exitosamente", "path": relative_path}

@router.get("/general/logo")
async def get_logo(
    db: Session = Depends(get_db_financiero)
):
    """Obtiene el logo de la empresa"""
    config_service = ConfigurationService(db)
    config = config_service.get_configuracion_general()
    
    if not config or not config.logo_empresa:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No hay logo configurado"
        )
    
    file_path = f".{config.logo_empresa}"
    if not os.path.exists(file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Archivo de logo no encontrado"
        )
    
    return FileResponse(file_path)

# === CONFIGURACIÓN SISTEMA ===

@router.get("/sistema", response_model=List[ConfiguracionSistema])
async def get_configuraciones_sistema(
    db: Session = Depends(get_db_financiero),
    current_user: Usuario = Depends(get_current_user)
):
    """Obtiene todas las configuraciones del sistema"""
    service = ConfigurationService(db)
    return service.get_configuraciones_sistema()

@router.get("/sistema/dict", response_model=Dict[str, Any])
async def get_configuraciones_sistema_dict(
    db: Session = Depends(get_db_financiero),
    current_user: Usuario = Depends(get_current_user)
):
    """Obtiene todas las configuraciones como diccionario clave-valor"""
    service = ConfigurationService(db)
    return service.get_configuraciones_as_dict()

@router.get("/sistema/{clave}", response_model=ConfiguracionSistema)
async def get_configuracion_sistema_by_clave(
    clave: str,
    db: Session = Depends(get_db_financiero),
    current_user: Usuario = Depends(get_current_user)
):
    """Obtiene una configuración específica por clave"""
    service = ConfigurationService(db)
    config = service.get_configuracion_sistema_by_clave(clave)
    
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe configuración con la clave '{clave}'"
        )
    
    return config

@router.post("/sistema", response_model=ConfiguracionSistema)
async def create_configuracion_sistema(
    config_data: ConfiguracionSistemaCreate,
    db: Session = Depends(get_db_financiero),
    current_user: Usuario = Depends(get_current_user)
):
    """Crea una nueva configuración del sistema"""
    # Verificar permisos de administrador
    if current_user.rol.nombre_rol != "Administrador Sistema":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo los administradores pueden crear configuraciones"
        )
    
    service = ConfigurationService(db)
    return service.create_configuracion_sistema(config_data)

@router.put("/sistema/{clave}", response_model=ConfiguracionSistema)
async def update_configuracion_sistema(
    clave: str,
    config_data: ConfiguracionSistemaUpdate,
    db: Session = Depends(get_db_financiero),
    current_user: Usuario = Depends(get_current_user)
):
    """Actualiza una configuración del sistema"""
    # Verificar permisos de administrador
    if current_user.rol.nombre_rol != "Administrador Sistema":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo los administradores pueden modificar configuraciones"
        )
    
    service = ConfigurationService(db)
    return service.update_configuracion_sistema(clave, config_data)

@router.delete("/sistema/{clave}")
async def delete_configuracion_sistema(
    clave: str,
    db: Session = Depends(get_db_financiero),
    current_user: Usuario = Depends(get_current_user)
):
    """Elimina una configuración del sistema"""
    # Verificar permisos de administrador
    if current_user.rol.nombre_rol != "Administrador Sistema":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo los administradores pueden eliminar configuraciones"
        )
    
    service = ConfigurationService(db)
    service.delete_configuracion_sistema(clave)
    return {"message": f"Configuración '{clave}' eliminada correctamente"}

# === CONFIGURACIÓN NOTIFICACIONES ===

@router.get("/notificaciones", response_model=List[ConfiguracionNotificacion])
async def get_configuraciones_notificaciones(
    db: Session = Depends(get_db_financiero),
    current_user: Usuario = Depends(get_current_user)
):
    """Obtiene todas las configuraciones de notificaciones"""
    service = ConfigurationService(db)
    return service.get_configuraciones_notificaciones()

@router.post("/notificaciones", response_model=ConfiguracionNotificacion)
async def create_configuracion_notificacion(
    config_data: ConfiguracionNotificacionCreate,
    db: Session = Depends(get_db_financiero),
    current_user: Usuario = Depends(get_current_user)
):
    """Crea una nueva configuración de notificación"""
    service = ConfigurationService(db)
    return service.create_configuracion_notificacion(config_data)

@router.put("/notificaciones/{notif_id}", response_model=ConfiguracionNotificacion)
async def update_configuracion_notificacion(
    notif_id: int,
    config_data: ConfiguracionNotificacionUpdate,
    db: Session = Depends(get_db_financiero),
    current_user: Usuario = Depends(get_current_user)
):
    """Actualiza una configuración de notificación"""
    service = ConfigurationService(db)
    return service.update_configuracion_notificacion(notif_id, config_data)

@router.delete("/notificaciones/{notif_id}")
async def delete_configuracion_notificacion(
    notif_id: int,
    db: Session = Depends(get_db_financiero),
    current_user: Usuario = Depends(get_current_user)
):
    """Elimina una configuración de notificación"""
    service = ConfigurationService(db)
    success = service.delete_configuracion_notificacion(notif_id)
    return {"message": "Configuración de notificación eliminada exitosamente"}

# === PERSONAL RRHH ===

@router.get("/personal/search", response_model=List[PersonalRRHH])
async def search_personal_rrhh(
    q: str = Query(min_length=2, description="Término de búsqueda (mínimo 2 caracteres)"),
    limit: int = Query(default=20, le=50),
    db: Session = Depends(get_db_financiero),
    current_user: Usuario = Depends(get_current_user)
):
    """Busca personal en RRHH por nombre o ficha"""
    service = ConfigurationService(db)
    return service.search_personal_rrhh(q, limit)

@router.get("/personal/{personal_id}", response_model=PersonalRRHH)
async def get_personal_rrhh(
    personal_id: int,
    db: Session = Depends(get_db_financiero),
    current_user: Usuario = Depends(get_current_user)
):
    """Obtiene un personal específico por ID"""
    service = ConfigurationService(db)
    personal = service.get_personal_rrhh_by_id(personal_id)
    if not personal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Personal no encontrado"
        )
    return personal