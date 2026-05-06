import logging
from datetime import date, timedelta

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
        existente= self.db.scalars(
            select(Asset).where(Asset.ticker == ticker)
        ).first()
        if existente:
            return existente
        
        info = yf.Ticker(ticker).info
        activo= Asset(
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