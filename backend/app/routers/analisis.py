import pandas as pd
import numpy as np
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.dependencies import DBSession
from app.models.db_models import Asset, Price
from app.services.risk import RiskService
from app.services.portfolio import PortfolioService
from app.services.data import DataService
from app.config import get_settings

settings = get_settings()
router = APIRouter(prefix="/analisis", tags=["Análisis de Riesgo"])


def _obtener_precios_df(ticker: str, db) -> pd.DataFrame:
    asset = db.scalars(select(Asset).where(Asset.ticker == ticker)).first()
    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Activo {ticker} no registrado",
        )
    precios = db.scalars(
        select(Price).where(Price.asset_id == asset.id).order_by(Price.fecha)
    ).all()
    if not precios:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No hay precios para {ticker}. Descárgalos primero.",
        )
    df = pd.DataFrame([{
        "fecha": p.fecha,
        "close": p.close,
        "open": p.open,
        "high": p.high,
        "low": p.low,
        "volume": p.volume,
    } for p in precios])
    df.set_index("fecha", inplace=True)
    return df


@router.get("/var/{ticker}")
def calcular_var(ticker: str, db: DBSession):
    df = _obtener_precios_df(ticker, db)
    servicio = RiskService(df)
    return {
        "ticker": ticker,
        "var_parametrico": servicio.var_parametrico(),
        "var_historico": servicio.var_historico(),
        "var_montecarlo": servicio.var_montecarlo(),
        "cvar": servicio.cvar(),
    }


@router.get("/garch/{ticker}")
def calcular_garch(ticker: str, db: DBSession):
    df = _obtener_precios_df(ticker, db)
    servicio = RiskService(df)
    return {"ticker": ticker, **servicio.garch()}


@router.get("/ewma/{ticker}")
def calcular_ewma(ticker: str, db: DBSession):
    df = _obtener_precios_df(ticker, db)
    servicio = RiskService(df)
    return {
        "ticker": ticker,
        "volatilidad_ewma": servicio.volatilidad_ewma(),
    }

@router.get("/markowitz")
def optimizar_portafolio(db: DBSession, permitir_cortos: bool = False):
    servicio_data = DataService(db)
    tickers = settings.default_tickers

    rendimientos = {}
    for ticker in tickers:
        precios = servicio_data.descargar_precios(ticker)
        if precios:
            df = pd.DataFrame([{"fecha": p.fecha, "close": p.close} for p in precios])
            df.set_index("fecha", inplace=True)
            rendimientos[ticker] = np.log(df["close"] / df["close"].shift(1)).dropna()

    df_rend = pd.DataFrame(rendimientos).dropna()
    servicio = PortfolioService(df_rend)

    return {
        "tickers": tickers,
        "optimizacion": servicio.optimizar_markowitz(permitir_cortos),
        "frontera": servicio.frontera_eficiente(n_puntos=20),
    }