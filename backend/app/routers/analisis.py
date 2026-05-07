import pandas as pd
import numpy as np
from fastapi import APIRouter, HTTPException, status, Query
from sqlalchemy import select
from scipy import stats as scipy_stats

from app.dependencies import DBSession
from app.models.db_models import Asset, Price
from app.services.risk import RiskService
from app.services.portfolio import PortfolioService
from app.services.data import DataService,  TechnicalIndicators
from app.config import get_settings
from app.services.stress import StressService
from app.models.db_models import Asset, Price, SignalLog
from app.models.schemas import AssetResponse, PriceResponse, PortfolioCreate, PortfolioResponse, PredictionCreate, PredictionResponse, VaRResponse, MarkowitzResponse


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


@router.get("/var/{ticker}", response_model=VaRResponse)
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

@router.get("/markowitz", response_model=MarkowitzResponse)
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

@router.get("/stress-test")
def stress_test(db: DBSession):
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
    servicio = StressService(df_rend)
    return {"escenarios": servicio.stress_test()}

@router.get("/capm")
def calcular_capm(
    db: DBSession,
    tickers: list[str] = Query(..., description="Lista de tickers a analizar"),
    benchmark: str = Query("^GSPC", description="Ticker del benchmark"),
    tasa_libre_riesgo: float = Query(0.04, description="Tasa FRED actual en decimal")
):
    # ¡Ahora usamos la tasa real que nos envíe el frontend!
    rf_anual = tasa_libre_riesgo
    
    servicio_data = DataService(db)

    try:
        precios_bench = servicio_data.descargar_precios(benchmark)
        if not precios_bench:
            raise ValueError(f"No se pudieron descargar datos para el benchmark {benchmark}")
            
        df_bench = pd.DataFrame([{"fecha": p.fecha, "close": p.close} for p in precios_bench])
        df_bench.set_index("fecha", inplace=True)
        df_bench["ret_bench"] = np.log(df_bench["close"] / df_bench["close"].shift(1))
        df_bench = df_bench.dropna()
        ret_anual_bench = float(df_bench["ret_bench"].mean() * 252)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Error {benchmark}: {str(e)}")

    resultados = []

    for t in tickers:
        try:
            precios_t = servicio_data.descargar_precios(t)
            if not precios_t: continue
                
            df_t = pd.DataFrame([{"fecha": p.fecha, "close": p.close} for p in precios_t])
            df_t.set_index("fecha", inplace=True)
            df_t["ret_activo"] = np.log(df_t["close"] / df_t["close"].shift(1))
            df_t = df_t.dropna()

            df_merge = pd.merge(df_t["ret_activo"], df_bench["ret_bench"], left_index=True, right_index=True).dropna()

            if len(df_merge) > 1:
                cov = np.cov(df_merge["ret_activo"], df_merge["ret_bench"])[0, 1]
                var_m = np.var(df_merge["ret_bench"], ddof=1)
                beta = float(cov / var_m) if var_m != 0 else 0.0

                ret_anual_activo = float(df_merge["ret_activo"].mean() * 252)
                rend_esperado_capm = float(rf_anual + beta * (ret_anual_bench - rf_anual))
                alpha_jensen = float(ret_anual_activo - rend_esperado_capm)

                corr = np.corrcoef(df_merge["ret_activo"], df_merge["ret_bench"])[0, 1]
                r2 = float(corr ** 2)

                clasificacion = "Agresivo" if beta > 1.2 else ("Defensivo" if beta < 0.8 else "Neutro")

                resultados.append({
                    "ticker": t, "beta": beta, "clasificacion": clasificacion,
                    "rendimiento_esperado_capm": rend_esperado_capm,
                    "prima_riesgo": rend_esperado_capm - rf_anual,
                    "alpha_jensen": alpha_jensen, "r_cuadrado": r2,
                    "tasa_libre_riesgo_anual": rf_anual,
                    "rendimiento_mercado_anual": ret_anual_bench
                })
        except Exception:
            continue

    if not resultados:
        raise HTTPException(status_code=400, detail="No se pudo calcular el CAPM.")

    return {"benchmark": benchmark, "activos": resultados}

@router.get("/rendimientos-serie/{ticker}")
def calcular_rendimientos_serie(ticker: str, db: DBSession):
    df = _obtener_precios_df(ticker, db)
    rendimientos = np.log(df["close"] / df["close"].shift(1)).dropna()
    return {
        "ticker": ticker,
        "serie": [
            {"fecha": str(fecha), "rendimiento": float(val)}
            for fecha, val in rendimientos.items()
        ]
    }

@router.get("/var-portafolio")
def var_portafolio(db: DBSession, nivel: float = 0.95):
    from scipy.stats import norm
    tickers = settings.default_tickers
    rendimientos = {}
    
    for ticker in tickers:
        asset = db.scalars(select(Asset).where(Asset.ticker == ticker)).first()
        if not asset:
            continue
        precios = db.scalars(
            select(Price).where(Price.asset_id == asset.id).order_by(Price.fecha)
        ).all()
        if len(precios) < 2:
            continue
        closes = pd.Series([p.close for p in precios])
        rendimientos[ticker] = np.log(closes / closes.shift(1)).dropna()

    if len(rendimientos) < 2:
        raise HTTPException(status_code=404, detail="No hay suficientes datos en BD")

    df_rend = pd.DataFrame(rendimientos).dropna()
    n = len(df_rend.columns)
    pesos = np.array([1/n] * n)
    cov = df_rend.cov().values * 252
    vol_port = float(np.sqrt(pesos @ cov @ pesos))
    media_port = float((df_rend.mean() * 252).values @ pesos)
    z = norm.ppf(1 - nivel)
    var_param = float(media_port/252 + z * vol_port/np.sqrt(252))
    
    return {
        "tickers": list(df_rend.columns),
        "var_parametrico_portafolio": round(var_param, 6),
        "volatilidad_anual_portafolio": round(vol_port, 4),
        "retorno_anual_esperado": round(media_port, 4),
        "nivel_confianza": nivel,
    }

@router.get("/alertas")
def obtener_alertas(
    db: DBSession,
    rsi_sobrecompra: int = 70,
    rsi_sobreventa: int = 30,
):
    tickers = settings.default_tickers
    alertas = []

    for ticker in tickers:
        try:
            df_precios = _obtener_precios_df(ticker, db)
            indicadores = TechnicalIndicators(df_precios)
            data = indicadores.calcular_todos()
            df = pd.DataFrame(data).T
            if len(df) == 0:
                continue
            ultimo = df.iloc[-1]
            señales_ticker = []

            if ultimo["rsi"] > rsi_sobrecompra:
                señales_ticker.append(("RSI", "VENTA", float(ultimo["rsi"])))
            elif ultimo["rsi"] < rsi_sobreventa:
                señales_ticker.append(("RSI", "COMPRA", float(ultimo["rsi"])))

            if ultimo["close"] > ultimo["bollinger_upper"]:
                señales_ticker.append(("Bollinger", "VENTA", float(ultimo["close"])))
            elif ultimo["close"] < ultimo["bollinger_lower"]:
                señales_ticker.append(("Bollinger", "COMPRA", float(ultimo["close"])))

            if ultimo["macd"] > ultimo["macd_signal"]:
                señales_ticker.append(("MACD", "COMPRA", float(ultimo["macd"])))
            else:
                señales_ticker.append(("MACD", "VENTA", float(ultimo["macd"])))

            for regla, señal, valor in señales_ticker:
                log = SignalLog(ticker=ticker, regla=regla, señal=señal, valor=valor)
                db.add(log)
                alertas.append({"ticker": ticker, "regla": regla, "señal": señal, "valor": round(valor, 4)})
        except:
            continue

    db.commit()
    return {"alertas": alertas, "total": len(alertas)}