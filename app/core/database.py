# app/core/database.py

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator
from app.core.config import settings
from app.models.base import Base

# --- Motor para la BD Financiera ---
engine_financiero = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    echo=False
)
SessionLocal_financiero = sessionmaker(autocommit=False, autoflush=False, bind=engine_financiero)

# --- Motor para la BD de RRHH ---
engine_rrhh = create_engine(
    settings.RRHH_DATABASE_URL,
    pool_pre_ping=True,
    echo=False
)
SessionLocal_rrhh = sessionmaker(autocommit=False, autoflush=False, bind=engine_rrhh)

def get_db_financiero() -> Generator[Session, None, None]:
    """
    Dependency injector que provee una sesión para la base de datos 'aitsa_financiero'.
    """
    db = SessionLocal_financiero()
    try:
        yield db
    finally:
        db.close()

def get_db_rrhh() -> Generator[Session, None, None]:
    """
    Dependency injector que provee una sesión para la base de datos 'aitsa_rrhh'.
    """
    db = SessionLocal_rrhh()
    try:
        yield db
    finally:
        db.close()