"""
database.py
Configuración del motor SQLAlchemy y función generadora de sesiones.
 
Patrón usado (enseñado en la Semana 7 del curso):
    - Engine y SessionLocal creados UNA sola vez al arrancar la app.
    - get_db() es un generador que abre una sesión por request y la
      cierra en el bloque finally (garantía de limpieza).
    - Se activa el pragma PRAGMA foreign_keys=ON para SQLite, que por
      defecto no valida claves foráneas.
"""
 
import sqlite3
 
from sqlalchemy import create_engine, event, Engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase, Session
from typing import Generator
 
from app.config import get_settings
 
 
# ── Base declarativa ──────────────────────────────────────────────────────────
# Todas las clases ORM en db_models.py heredarán de esta Base.
class Base(DeclarativeBase):
    """Clase base para todos los modelos de SQLAlchemy."""
    pass
 
 
# ── Motor y fábrica de sesiones ───────────────────────────────────────────────
def _build_engine():
    settings = get_settings()
    connect_args = {}
 
    # check_same_thread=False es necesario para SQLite con FastAPI:
    # FastAPI despacha endpoints síncronos (def) a un threadpool, y SQLite
    # por defecto solo permite acceso desde el hilo que creó la conexión.
    # La seguridad se mantiene porque get_db() crea una sesión nueva por request.
    if settings.database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
 
    return create_engine(
        settings.database_url,
        connect_args=connect_args,
        echo=settings.debug,   # Muestra SQL generado en consola si debug=True
    )
 
 
engine = _build_engine()
 
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)
 
 
# ── Activar claves foráneas en SQLite ─────────────────────────────────────────
# Sin este evento, SQLite permite insertar filas huérfanas sin lanzar error.
@event.listens_for(Engine, "connect")
def _activar_fk_sqlite(dbapi_conn, connection_record):
    if isinstance(dbapi_conn, sqlite3.Connection):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
 
 
# ── Dependencia de sesión ─────────────────────────────────────────────────────
def get_db() -> Generator[Session, None, None]:
    """
    Generador que provee una sesión de BD por request.
 
    Flujo:
        1. Antes del yield  → se abre la sesión.
        2. yield            → el endpoint usa la sesión.
        3. finally          → la sesión se cierra SIEMPRE,
                              incluso si el endpoint lanza una excepción.
 
    Uso en routers:
        DBSession = Annotated[Session, Depends(get_db)]
 
        @router.get("/ejemplo")
        def ejemplo(db: DBSession):
            return db.query(...)
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
 
 
# ── Inicialización de tablas ──────────────────────────────────────────────────
def init_db() -> None:
    """
    Crea todas las tablas definidas en db_models.py si no existen.
    Se llama una vez desde el lifespan de FastAPI en main.py.
    """
    # El import aquí evita importaciones circulares:
    # database.py ← db_models.py, pero db_models.py importa Base desde database.py
    from app.models import db_models  # noqa: F401
    Base.metadata.create_all(bind=engine)