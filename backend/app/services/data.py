import logging
from datetime import date, timedelta

import numpy as np
import yfinance as yf
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.db_models import Asset, Price

logger = logging.getLogger(__name__)
settings= get_settings()

class DataService:
    
    def __init__(self, db: Session):
        self.db = db

    def registrar_activo(self, ticker: str) -> Asset:
        existente = self.db.scalars(
            select(Asset).where(Asset.ticker == ticker)
        ).first()
        if existente:
            return existente
        
        try:
            info = yf.Ticker(ticker).info
            activo = Asset(
                ticker=ticker,
                nombre=info.get("longName", ticker),
                sector=info.get("sector", "Desconocido"),
                moneda=info.get("currency", "USD")
            )
            self.db.add(activo)
            self.db.commit()
            self.db.refresh(activo)
            logger.info(f"Activo {ticker} registrado desde yfinance")
            return activo
        except Exception:
            self.db.rollback()
            # Si falló por duplicado, buscarlo de nuevo
            existente = self.db.scalars(
                select(Asset).where(Asset.ticker == ticker)
            ).first()
            if existente:
                return existente
            raise
    
    def descargar_precios(self, ticker: str, years: int = None) -> list[Price]:
        if years is None:
            years = settings.default_years

        activo= self.registrar_activo(ticker)

        ultimo_precio= self.db.scalars(
            select(Price)
            .where(Price.asset_id == activo.id)
            .order_by(Price.fecha.desc())
        ).first()

        if ultimo_precio:
            inicio= ultimo_precio.fecha
        else:
            inicio= date.today() - timedelta(days=years * 365)

        df= yf.Ticker(ticker).history(start=str(inicio))

        if df.empty:
            logger.warning(f"No se encontraron datos para {ticker}")
            return []
        
        nuevos=0

        for fecha, fila in df.iterrows():
            fecha_date= fecha.date()
            existe= self.db.scalars(
                select(Price)
                .where(Price.asset_id == activo.id)
                .where(Price.fecha == fecha_date)
            ).first()
            if not existe:
                precio= Price(
                    asset_id= activo.id,
                    fecha= fecha_date,
                    open=float(fila["Open"]),
                    high=float(fila["High"]),
                    low=float(fila["Low"]),
                    close=float(fila["Close"]),
                    volume=float(fila["Volume"])
                )
                self.db.add(precio)
                nuevos += 1
        
        self.db.commit()
        logger.info(f"{ticker}: {nuevos} precios nuevos guardados")

        return self.db.scalars(
            select(Price)
            .where(Price.asset_id == activo.id)
            .order_by(Price.fecha)
        ).all()
    

class TechnicalIndicators:

    def __init__(self, df: pd.DataFrame):
        self.df = df
        self.close = df["close"]
        self.high = df["high"]
        self.low = df["low"]

    def sma(self, period: int = None) -> pd.Series:
        if period is None:
            period = settings.sma_short_period
        return self.close.rolling(window=period).mean()

    def ema(self, period: int = None) -> pd.Series:
        if period is None:
            period = settings.sma_short_period
        return self.close.ewm(span=period).mean()

    def rsi(self, period: int = None) -> pd.Series:
        if period is None:
            period = settings.rsi_period
        delta = self.close.diff()
        gain = delta.where(delta > 0, 0).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    def macd(self) -> dict:
        ema_fast = self.close.ewm(span=settings.macd_fast).mean()
        ema_slow = self.close.ewm(span=settings.macd_slow).mean()
        macd_line = ema_fast - ema_slow
        signal = macd_line.ewm(span=settings.macd_signal).mean()
        histograma = macd_line - signal
        return {
            "macd": macd_line,
            "signal": signal,
            "histograma": histograma,
        }

    def bollinger(self) -> dict:
        sma = self.close.rolling(window=settings.bollinger_period).mean()
        std = self.close.rolling(window=settings.bollinger_period).std()
        return {
            "media": sma,
            "upper": sma + settings.bollinger_std * std,
            "lower": sma - settings.bollinger_std * std,
        }

    def stochastic(self) -> dict:
        low_min = self.low.rolling(window=settings.stochastic_k_period).min()
        high_max = self.high.rolling(window=settings.stochastic_k_period).max()
        k = 100 * (self.close - low_min) / (high_max - low_min)
        d = k.rolling(window=settings.stochastic_d_period).mean()
        return {"k": k, "d": d}

    def calcular_todos(self) -> dict:
        macd_data = self.macd()
        boll = self.bollinger()
        stoch = self.stochastic()

        resultado = pd.DataFrame({
            "close": self.close,
            "sma_short": self.sma(settings.sma_short_period),
            "sma_long": self.sma(settings.sma_long_period),
            "ema": self.ema(),
            "rsi": self.rsi(),
            "macd": macd_data["macd"],
            "macd_signal": macd_data["signal"],
            "macd_histograma": macd_data["histograma"],
            "bollinger_upper": boll["upper"],
            "bollinger_media": boll["media"],
            "bollinger_lower": boll["lower"],
            "stochastic_k": stoch["k"],
            "stochastic_d": stoch["d"],
        }).dropna()

        return resultado.to_dict(orient="index")