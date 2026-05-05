from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import init_db   
from app.routers import activos, portafolios, precios 

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()  # Inicializar la base de datos al iniciar la aplicación
    yield  # Aquí se ejecutan las operaciones normales de la aplicación
    # No se necesitan operaciones especiales al finalizar la aplicación


settings = get_settings()

app = FastAPI(
    title=settings.app_name, 
    version=settings.app_version, 
    description="API para análisis de riesgo financiero y gestión de portafolios  con FastAPI y SQLite",
    lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def healt_check():
    return {"status": "ok", "app": settings.app_name, "version": settings.app_version, "entorno": settings.entorno}


app.include_router(activos.router)

app.include_router(portafolios.router)

app.include_router(precios.router)