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
    tickers: list[str] = Field(..., min_length=1, description="Lista de tickers en el portafolio")
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
    theta_put: Optional[float] = None
    vega: float
    rho_call: float
    rho_put: Optional[float] = None


class OptionResponse(BaseModel):
    parametros: dict
    precios: dict
    greeks: GreeksResponse


# ── VaR ───────────────────────────────────────────────────────────────────────
class KupiecResult(BaseModel):
    disponible: bool = True
    motivo: Optional[str] = None
    ventana: Optional[int] = None
    excepciones: Optional[int] = None
    excepciones_esperadas: Optional[float] = None
    n: Optional[int] = None
    p_esperado: Optional[float] = None
    p_observado: Optional[float] = None
    estadistico_lr: Optional[float] = None
    p_value: Optional[float] = None
    aprobado: Optional[bool] = None
    zona: Optional[str] = None


class VaRResponse(BaseModel):
    ticker: str
    nivel_confianza: Optional[float] = None
    horizonte_dias: Optional[int] = None
    var_parametrico: float
    var_cornish_fisher: Optional[float] = None
    var_historico: float
    var_montecarlo: float
    cvar: float
    cvar_parametrico: Optional[float] = None
    volatilidad_anual: Optional[float] = None
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


class ActivoFrontera(BaseModel):
    ticker: str
    retorno: float
    riesgo: float
    sharpe: float


class MarkowitzResponse(BaseModel):
    tickers: list[str]
    tasa_libre_riesgo: Optional[float] = None
    optimizacion: PortfolioOptResult
    maximo_sharpe: Optional[PortfolioOptResult] = None
    minima_varianza: Optional[PortfolioOptResult] = None
    portafolio_actual: Optional[PortfolioOptResult] = None
    pesos_iguales: Optional[PortfolioOptResult] = None
    activos: list[ActivoFrontera] = []
    correlacion: Optional[dict] = None
    frontera: list[FronteraPoint]
    n_observaciones: Optional[int] = None
