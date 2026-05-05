from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.dependencies import DBSession
from app.models.db_models import Asset
from app.models.schemas import AssetCreate, AssetResponse

router = APIRouter(prefix="/activos", tags=["activos"])

@router.post("/", response_model=AssetResponse, status_code=status.HTTP_201_CREATED)
def crear_activo(datos: AssetCreate, db: DBSession):
    activo = Asset(**datos.model_dump())
    db.add(activo)
    db.commit()
    db.refresh(activo)
    return activo 

@router.get("/", response_model=list[AssetResponse])
def listar_activos(db: DBSession):
    activos= db.scalars(select(Asset)).all()
    return activos

@router.get("/{ticker}", response_model=AssetResponse)
def obtener_activo(ticker: str, db: DBSession):
    activo = db.scalars(select(Asset).where(Asset.ticker == ticker)).first()
    if not activo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Activo {ticker} no encontrado",
        )
    return activo