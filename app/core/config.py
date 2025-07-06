# app/core/config.py

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import Optional, List
import secrets

class Settings(BaseSettings):
    """
    Settings for the application, loaded from a .env file.
    """
    # --- Project Info ---
    PROJECT_NAME: str = "SIRCEL API"
    API_V1_STR: str = "/api/v1"
    VERSION: str = "1.0.0"

    # --- Security ---
    SECRET_KEY: str = secrets.token_urlsafe(32)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 horas
    ALGORITHM: str = "HS256"
    WEBHOOK_SECRET_TOKEN: Optional[str] = Field(None, description="Secret token to validate webhooks")

    # ✅ NUEVAS CONFIGURACIONES FRONTEND
    FRONTEND_URL: str = Field(default="http://localhost:8080", description="Frontend application URL")
    ALLOWED_ORIGINS: List[str] = Field(default_factory=lambda: ["http://localhost:8080"])

    # --- Database ---
    DATABASE_URL: str = Field(..., description="Database URL for 'aitsa_financiero'")
    RRHH_DATABASE_URL: str = Field(..., description="Database URL for 'aitsa_rrhh'")

    # Configuración de Base de Datos
    DB_FINANCIERO_HOST: str = "localhost"
    DB_FINANCIERO_USER: str = "postgres"
    DB_FINANCIERO_PASSWORD: str = "postgres"
    DB_FINANCIERO_NAME: str = "sircel_financiero"
    DB_FINANCIERO_PORT: str = "5432"

    DB_RRHH_HOST: str = "localhost"
    DB_RRHH_USER: str = "postgres"
    DB_RRHH_PASSWORD: str = "postgres"
    DB_RRHH_NAME: str = "sircel_rrhh"
    DB_RRHH_PORT: str = "5432"

    # Configuración de CORS
    CORS_ORIGINS: list = ["*"]
    CORS_CREDENTIALS: bool = True
    CORS_METHODS: list = ["*"]
    CORS_HEADERS: list = ["*"]

    # Configuración de archivos
    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10MB

    # Pydantic V2 necesita esta configuración para leer desde .env
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding='utf-8', extra='ignore')

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Configurar ALLOWED_ORIGINS basado en FRONTEND_URL si no se especifica explícitamente
        if not kwargs.get('ALLOWED_ORIGINS'):
            self.ALLOWED_ORIGINS = [self.FRONTEND_URL]

# Se crea una única instancia que será usada en toda la aplicación
settings = Settings()