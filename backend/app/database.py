import sqlite3
from typing import Generator

from sqlalchemy import create_engine, event, Engine
from sqlalchemy.orm import sessionmaker, Session, DeclarativeBase

from app.config import get_settings

class Base(DeclarativeBase):
    """Clase base para todos los modelos ORM."""
    pass 

settings = get_settings()

engine = create_engine(settings.database_url, connect_args={"check_same_thread": False}, echo=settings.debug)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db() -> None:
    from app.models import db_models # Importar modelos para registrar con SQLAlchemy noqa: F401
    Base.metadata.create_all(bind=engine)