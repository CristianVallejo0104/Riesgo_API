from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

class AssetCreate(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=10, description="Símbolo del activo", example="AAPL")
    nombre: str = Field(..., min_length=1, max_length=100, description="Nombre del activo", example="Apple Inc.")
    sector: str = Field(..., min_length=1, max_length=50, description="Sector del activo", example="Tecnología")
    moneda: str = Field(default="USD", max_length=10)

class AssetResponse(BaseModel):
    id: int
    ticker: str
    nombre: str
    sector: str
    moneda: str
    creado_en: datetime

    model_config = {"from_attributes": True}

class PriceResponse(BaseModel):
    id: int
    asset_id: int
    fecha: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

    model_config = {"from_attributes": True}

class PortfolioCreate(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=100)
    descripcion: Optional[str] = None
    tickers: list[str] = Field(..., min_legth=1, description="Lista de tickers en el portafolio")
    pesos: dict[str, float] = Field(...)

    @field_validator("pesos")
    @classmethod
    def pesos_debe_sumar_1(cls, v):
        total = sum(v.values())
        if abs(total - 1.0) > 0.01:
            raise ValueError(f"Los pesos deben sumar 1.0, suman {total}")
        return v

class PortfolioResponse(BaseModel):
    id: int
    nombre: str
    descripcion: Optional[str]
    tickers: list[str]
    pesos: dict[str, float]
    creado_en: datetime
    model_config = {"from_attributes": True}

class PredictionCreate(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=10)
    features: dict = Field(...)

class PredictionResponse(BaseModel):
    id: int
    ticker: str
    features: dict
    prediccion: float
    modelo_version: str
    creado_en: datetime

    model_config = {"from_attributes": True}


# ── Opciones ──────────────────────────────────────────────────────────────────
class OptionRequest(BaseModel):
    S: float = Field(..., gt=0, description="Precio spot del activo")
    K: float = Field(..., gt=0, description="Precio de ejercicio")
    T: float = Field(..., gt=0, description="Tiempo al vencimiento en años")
    r: float = Field(..., description="Tasa libre de riesgo")
    sigma: float = Field(..., gt=0, description="Volatilidad")

    @field_validator("T")
    @classmethod
    def t_positivo(cls, v):
        if v <= 0:
            raise ValueError("T debe ser mayor que 0")
        return v

    @field_validator("sigma")
    @classmethod
    def sigma_positivo(cls, v):
        if v <= 0:
            raise ValueError("sigma debe ser mayor que 0")
        return v


class GreeksResponse(BaseModel):
    delta_call: float
    delta_put: float
    gamma: float
    theta_call: float
    vega: float
    rho_call: float


class OptionResponse(BaseModel):
    parametros: dict
    precios: dict
    greeks: GreeksResponse
    


# ── VaR ───────────────────────────────────────────────────────────────────────
class KupiecResult(BaseModel):
    excepciones: int
    n: int
    p_value: float
    aprobado: bool


class VaRResponse(BaseModel):
    ticker: str
    var_parametrico: float
    var_historico: float
    var_montecarlo: float
    cvar: float
    kupiec: Optional[KupiecResult] = None


# ── Portafolio ────────────────────────────────────────────────────────────────
class PortfolioOptResult(BaseModel):
    pesos: dict[str, float]
    retorno_anual: float
    riesgo_anual: float
    sharpe_ratio: float


class FronteraPoint(BaseModel):
    retorno: float
    riesgo: float


class MarkowitzResponse(BaseModel):
    tickers: list[str]
    optimizacion: PortfolioOptResult
    frontera: list[FronteraPoint]