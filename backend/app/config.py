from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name : str = "RiskLab USTA API"
    app_version: str = "2.0.1"
    debug: bool =False
    entorno: str = "development"
    database_url: str = "sqlite:///./risklab.db"
    fred_api_key: str= ""
    alpha_vantage_api_key: str = ""
    default_tickers: list[str] = ["AAPL", "JPM",  "JNJ", "XOM", "KO"]
    default_years: int = 3
    benchmark_ticker: str = "^GSPC"
    var_confidence_level: float = 0.95
    montecarlo_simulations: int = 10_000
    markowitz_portfolio: int = 10_000
    ewma_lambda: float = 0.94
    sma_short_period: int = 20
    sma_long_period: int = 50
    rsi_period: int = 14
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    stochastic_k_period: int = 14
    stochastic_d_period: int = 3
    bollinger_period: int = 20
    bollinger_std: float = 2.0
    fred_risk_free_series: str = "DGS3MO"
    fred_inflation_series: str = "CPIAUCSL"
    fred_yield_curve_series: list[str] = ["DGS3MO", "DGS1", "DGS2", "DGS5", "DGS10", "DGS30"]
    ml_model_path: str = "app/ml/model.joblib"
    ml_model_version: str = "1.0.0"

    cors_origins: list[str] = ["http://localhost:8501", "http://127.0.0.1:8501"]
    model_config = SettingsConfigDict(env_file="backend/.env", env_file_encoding="utf-8", extra="ignore")



@lru_cache
def get_settings() -> Settings:
    return Settings()