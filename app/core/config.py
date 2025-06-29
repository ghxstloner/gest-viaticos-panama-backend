from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional


class Settings(BaseSettings):
    # API
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "GestViáticos Panamá Backend"
    VERSION: str = "1.0.0"
    DESCRIPTION: str = "Sistema de Gestión de Viáticos y Caja Menuda - República de Panamá"

    # Database
    DATABASE_URL: str = Field(..., description="Database URL")
    
    # Security
    SECRET_KEY: str = Field(..., description="Secret key for JWT")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480  # 8 hours
    ALGORITHM: str = "HS256"
    
    # RRHH Integration
    WEBHOOK_SECRET_TOKEN: str = "CAMBIAR_EN_PRODUCCION"
    
    # Configuration
    LIMITE_EFECTIVO_VIATICOS: float = 200.00
    DIAS_LIMITE_PRESENTACION: int = 10
    MONTO_REFRENDO_CGR: float = 1000.00
    
    # Email (optional)
    MAIL_SERVER: Optional[str] = None
    MAIL_PORT: Optional[int] = 587
    MAIL_USERNAME: Optional[str] = None
    MAIL_PASSWORD: Optional[str] = None
    MAIL_FROM: Optional[str] = None
    
    # Environment
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    
    # CORS
    BACKEND_CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8080",
    ]

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()