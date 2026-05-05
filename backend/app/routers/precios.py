from datetime import date

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.dependencies import DBSession
from app.models.db_models import Asset, Price
from app.models.schemas import PriceResponse


router = APIRouter(prefix="/precios", tags=["Precios"])

@router.get("/{ticker}", response_model=list[PriceResponse])
def obtener_precios(ticker: str, db: DBSession):
    asset = db.scalars(select(Asset).where(Asset.ticker == ticker)).first()
    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Activo {ticker} no registrado",
        )
    precios = db.scalars(select(Price).where(Price.asset_id == asset.id)).all()
    return precios

