# app/core/config.py

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import Optional, List

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

    # ✅ NUEVAS CONFIGURACIONES FRONTEND
    FRONTEND_URL: str = Field(default="http://localhost:8080", description="Frontend application URL")
    ALLOWED_ORIGINS: List[str] = Field(default_factory=lambda: ["http://localhost:8080"])

    # --- Database ---
    DATABASE_URL: str = Field(..., description="Database URL for 'aitsa_financiero'")
    RRHH_DATABASE_URL: str = Field(..., description="Database URL for 'aitsa_rrhh'")

    # Pydantic V2 necesita esta configuración para leer desde .env
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding='utf-8', extra='ignore')

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Configurar ALLOWED_ORIGINS basado en FRONTEND_URL si no se especifica explícitamente
        if not kwargs.get('ALLOWED_ORIGINS'):
            self.ALLOWED_ORIGINS = [self.FRONTEND_URL]

# Se crea una única instancia que será usada en toda la aplicación
settings = Settings()