# app/core/config.py

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import Optional

class Settings(BaseSettings):
    """
    Settings for the application, loaded from a .env file.
    """
    # --- Project Info ---
    PROJECT_NAME: str = "Gestión de Viáticos - AITSA"
    API_V1_STR: str = "/api/v1"

    # --- Security ---
    SECRET_KEY: str = Field(..., description="Secret key for signing JWTs")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480  # 8 hours
    ALGORITHM: str = "HS256"
    WEBHOOK_SECRET_TOKEN: Optional[str] = Field(None, description="Secret token to validate webhooks")

    # --- Database ---
    # Conexión a la base de datos del sistema financiero
    DATABASE_URL: str = Field(..., description="Database URL for 'aitsa_financiero'")

    # ✅ CORRECCIÓN: Se añade la variable para la BD de RRHH
    # Conexión a la base de datos de Recursos Humanos
    RRHH_DATABASE_URL: str = Field(..., description="Database URL for 'aitsa_rrhh'")

    # Pydantic V2 necesita esta configuración para leer desde .env
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding='utf-8', extra='ignore')

# Se crea una única instancia que será usada en toda la aplicación
settings = Settings()
