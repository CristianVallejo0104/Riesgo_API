from datetime import datetime
from typing import List, Optional

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

class Asset(Base):
    __tablename__ = "assets"

    id: Mapped [int] = mapped_column(Integer, primary_key=True, index=True)
    ticker: Mapped[str]= mapped_column(String(10), unique=True, index=True, nullable=False)
    nome: Mapped[str]= mapped_column(String(100), nullable=True)
    sector: Mapped[str]= mapped_column(String(50), nullable=True)
    moneda: Mapped[str] = mapped_column(String(10), default="USD")
    creado_en: Mapped[datetime]= mapped_column(DateTime, server_default=func.now())

    precios: Mapped[List["Price"]]=relationship(back_populates="asset")


class Price(Base):
    __tablename__ = "prices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    asset_id: Mapped[int]= mapped_column(Integer, ForeignKey("assets.id"), nullable=False)
    fecha: Mapped[datetime]= mapped_column(Date, nullable=False)
    open: Mapped[float]= mapped_column(Float, nullable=False)
    high: Mapped[float]= mapped_column(Float, nullable=False)
    low: Mapped[float]= mapped_column(Float, nullable=False)
    close: Mapped[float]= mapped_column(Float, nullable=False)
    volume: Mapped[int]= mapped_column(Float, nullable=False)

    asset: Mapped["Asset"]= relationship(back_populates="precios")

class Portfolio(Base):
    __tablename__ = "portfolios"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    descripcion: Mapped[Optional[str]] = mapped_column(String(500))
    tickers: Mapped[dict]=mapped_column(JSON, nullable=False)  # Guardar tickers y pesos como JSON
    pesos: Mapped[dict]=mapped_column(JSON, nullable=False)  # Guardar tickers y pesos como JSON
    creado_en: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class PredictionLog(Base):
    __tablename__ = "prediction_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    ticker: Mapped[str] = mapped_column(String(10), nullable=False)
    features: Mapped[dict] = mapped_column(JSON, nullable=False)  # Guardar características como JSON
    prediccion: Mapped[float] = mapped_column(Float, nullable=False)
    modelo_version: Mapped[str] = mapped_column(String(20), nullable=False)
    creado_en: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())