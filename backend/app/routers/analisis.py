import pandas as pd
import numpy as np
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from scipy import stats as scipy_stats

from app.dependencies import DBSession
from app.models.db_models import Asset, Price
from app.services.risk import RiskService
from app.services.portfolio import PortfolioService
from app.services.data import DataService,  TechnicalIndicators
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


@router.get("/indicadores/{ticker}")
def calcular_indicadores(ticker: str, db: DBSession):
    df = _obtener_precios_df(ticker, db)
    indicadores = TechnicalIndicators(df)
    return {"ticker": ticker, "indicadores": indicadores.calcular_todos()}


@router.get("/rendimientos/{ticker}")
def calcular_rendimientos(ticker: str, db: DBSession):
    df = _obtener_precios_df(ticker, db)
    rendimientos = np.log(df["close"] / df["close"].shift(1)).dropna()

    media = float(rendimientos.mean())
    std = float(rendimientos.std())
    asimetria = float(rendimientos.skew())
    curtosis = float(rendimientos.kurtosis())

    jb_stat, jb_pvalue = scipy_stats.jarque_bera(rendimientos)
    shapiro_stat, shapiro_pvalue = scipy_stats.shapiro(rendimientos[:5000])

    return {
        "ticker": ticker,
        "n_observaciones": len(rendimientos),
        "media_diaria": round(media, 6),
        "media_anual": round(media * 252, 4),
        "std_diaria": round(std, 6),
        "std_anual": round(std * np.sqrt(252), 4),
        "asimetria": round(asimetria, 4),
        "curtosis": round(curtosis, 4),
        "jarque_bera": {
            "estadistico": round(float(jb_stat), 4),
            "p_value": round(float(jb_pvalue), 6),
            "es_normal": float(jb_pvalue) > 0.05,
        },
        "shapiro_wilk": {
            "estadistico": round(float(shapiro_stat), 4),
            "p_value": round(float(shapiro_pvalue), 6),
            "es_normal": float(shapiro_pvalue) > 0.05,
        },
    }