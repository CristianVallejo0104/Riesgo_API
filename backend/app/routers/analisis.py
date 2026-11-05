import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException, Query, status
from scipy import stats as scipy_stats
from sqlalchemy import select

from app.config import get_settings
from app.dependencies import DBSession
from app.models.db_models import Asset, Price, SignalLog
from app.models.schemas import MarkowitzResponse, VaRResponse
from app.services.data import TechnicalIndicators
from app.services.portfolio import PortfolioService
from app.services.risk import RiskService
from app.services.stress import StressService

settings = get_settings()
router = APIRouter(prefix="/analisis", tags=["Análisis de Riesgo"])

DIAS_ANIO = 252


# ═════════════════════════════ helpers ═════════════════════════════

def _obtener_precios_df(ticker: str, db, fecha_inicio: str = None, fecha_fin: str = None) -> pd.DataFrame:
    asset = db.scalars(select(Asset).where(Asset.ticker == ticker)).first()
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Activo {ticker} no registrado")
    precios = db.scalars(
        select(Price).where(Price.asset_id == asset.id).order_by(Price.fecha)
    ).all()
    if not precios:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"No hay precios para {ticker}. Descárgalos primero.")
    df = pd.DataFrame([{
        "fecha": p.fecha, "close": p.close, "open": p.open,
        "high": p.high, "low": p.low, "volume": p.volume,
    } for p in precios])
    df.set_index("fecha", inplace=True)
    df.index = pd.to_datetime(df.index)
    df = df[~df.index.duplicated(keep="last")].sort_index()

    if fecha_inicio:
        df = df[df.index >= pd.to_datetime(fecha_inicio)]
    if fecha_fin:
        df = df[df.index <= pd.to_datetime(fecha_fin)]

    if len(df) < 30:
        raise HTTPException(status_code=400,
                            detail=f"Insuficientes datos para {ticker} en el período seleccionado (mínimo 30 días).")
    return df


def _rendimientos_df(tickers: list[str], db, fecha_inicio=None, fecha_fin=None,
                     tipo: str = "simple") -> pd.DataFrame:
    """Rendimientos diarios alineados por fecha (sólo días comunes a todos los activos)."""
    series = {}
    for t in tickers:
        try:
            close = _obtener_precios_df(t, db, fecha_inicio, fecha_fin)["close"]
        except HTTPException:
            continue
        series[t] = np.log(close / close.shift(1)) if tipo == "log" else close.pct_change()
    if len(series) < 2:
        raise HTTPException(status_code=400,
                            detail="Se necesitan al menos 2 activos con datos. Inicializa el portafolio primero.")
    df = pd.DataFrame(series).dropna()
    if len(df) < 30:
        raise HTTPException(status_code=400, detail="Muy pocas fechas en común entre los activos.")
    return df


def _vector_pesos(columnas: list[str], tickers_pedidos: list[str], pesos: list[float] | None) -> np.ndarray:
    """Alinea los pesos enviados (en el orden de `tickers_pedidos`) con las columnas que
    sí tienen datos y los re-normaliza para que sumen 1."""
    if not pesos or len(pesos) != len(tickers_pedidos):
        return np.full(len(columnas), 1 / len(columnas))
    mapa = dict(zip(tickers_pedidos, pesos))
    w = np.array([float(mapa.get(c, 0.0)) for c in columnas])
    total = w.sum()
    if total <= 0:
        return np.full(len(columnas), 1 / len(columnas))
    return w / total


def _rend_benchmark(benchmark: str, db, fecha_inicio=None, fecha_fin=None) -> pd.Series | None:
    try:
        return _obtener_precios_df(benchmark, db, fecha_inicio, fecha_fin)["close"].pct_change().dropna()
    except HTTPException:
        return None


def _max_drawdown(rend_simples: pd.Series) -> tuple[float, str | None, str | None]:
    riqueza = (1 + rend_simples).cumprod()
    dd = riqueza / riqueza.cummax() - 1
    if dd.empty:
        return 0.0, None, None
    fondo = dd.idxmin()
    pico = riqueza.loc[:fondo].idxmax()
    return float(dd.min()), str(pico.date()), str(fondo.date())


# ═════════════════════════════ activo individual ═════════════════════════════

@router.get("/var/{ticker}", response_model=VaRResponse)
def calcular_var(ticker: str, db: DBSession,
                 nivel: float = Query(default=None, ge=0.80, le=0.999, description="Nivel de confianza"),
                 horizonte: int = Query(default=1, ge=1, le=30, description="Horizonte en días"),
                 fecha_inicio: str = Query(default=None),
                 fecha_fin: str = Query(default=None)):
    df = _obtener_precios_df(ticker, db, fecha_inicio, fecha_fin)
    servicio = RiskService(df)
    return {"ticker": ticker, **servicio.resumen_var(nivel, horizonte)}


@router.get("/garch/{ticker}")
def calcular_garch(ticker: str, db: DBSession,
                   fecha_inicio: str = Query(default=None),
                   fecha_fin: str = Query(default=None)):
    df = _obtener_precios_df(ticker, db, fecha_inicio, fecha_fin)
    return {"ticker": ticker, **RiskService(df).garch()}


@router.get("/ewma/{ticker}")
def calcular_ewma(ticker: str, db: DBSession,
                  lambd: float = Query(default=None, gt=0.5, lt=1.0),
                  fecha_inicio: str = Query(default=None),
                  fecha_fin: str = Query(default=None)):
    df = _obtener_precios_df(ticker, db, fecha_inicio, fecha_fin)
    servicio = RiskService(df)
    lam = settings.ewma_lambda if lambd is None else lambd
    serie = servicio.serie_ewma(lam) * np.sqrt(DIAS_ANIO)
    return {
        "ticker": ticker,
        "lambda": lam,
        "volatilidad_ewma": servicio.volatilidad_ewma(lam),
        "volatilidad_historica": servicio.volatilidad_historica(),
        "serie": [{"fecha": str(f.date()), "vol_anual": round(float(v), 6)} for f, v in serie.items()],
    }


@router.get("/indicadores/{ticker}")
def calcular_indicadores(ticker: str, db: DBSession,
                         fecha_inicio: str = Query(default=None),
                         fecha_fin: str = Query(default=None)):
    df = _obtener_precios_df(ticker, db, fecha_inicio, fecha_fin)
    return {"ticker": ticker, "indicadores": TechnicalIndicators(df).calcular_todos()}


@router.get("/rendimientos/{ticker}")
def calcular_rendimientos(ticker: str, db: DBSession,
                          fecha_inicio: str = Query(default=None),
                          fecha_fin: str = Query(default=None)):
    df = _obtener_precios_df(ticker, db, fecha_inicio, fecha_fin)
    r = np.log(df["close"] / df["close"].shift(1)).dropna()
    media, std = float(r.mean()), float(r.std())
    asim = float(r.skew())
    curt_exceso = float(r.kurtosis())  # pandas devuelve curtosis EN EXCESO (normal = 0)
    jb_stat, jb_p = scipy_stats.jarque_bera(r)
    sw_stat, sw_p = scipy_stats.shapiro(r[:5000])
    mdd, _, _ = _max_drawdown(df["close"].pct_change().dropna())
    # ¿Cuántas veces más frecuentes son los días extremos (|z|>3) que bajo la Normal?
    z = (r - media) / std
    freq_obs = float((z.abs() > 3).mean())
    freq_normal = float(2 * scipy_stats.norm.sf(3))
    return {
        "ticker": ticker,
        "n_observaciones": len(r),
        "media_diaria": round(media, 6),
        "media_anual": round(media * DIAS_ANIO, 4),
        "std_diaria": round(std, 6),
        "std_anual": round(std * np.sqrt(DIAS_ANIO), 4),
        "asimetria": round(asim, 4),
        "curtosis": round(curt_exceso, 4),           # compatibilidad: es la curtosis en exceso
        "curtosis_exceso": round(curt_exceso, 4),
        "curtosis_total": round(curt_exceso + 3, 4),
        "peor_dia": round(float(r.min()), 6),
        "mejor_dia": round(float(r.max()), 6),
        "max_drawdown": round(mdd, 4),
        "dias_extremos_obs_pct": round(freq_obs * 100, 3),
        "dias_extremos_normal_pct": round(freq_normal * 100, 3),
        "jarque_bera": {"estadistico": round(float(jb_stat), 4), "p_value": round(float(jb_p), 6),
                        "es_normal": float(jb_p) > 0.05},
        "shapiro_wilk": {"estadistico": round(float(sw_stat), 4), "p_value": round(float(sw_p), 6),
                         "es_normal": float(sw_p) > 0.05},
    }


@router.get("/rendimientos-serie/{ticker}")
def calcular_rendimientos_serie(ticker: str, db: DBSession,
                                fecha_inicio: str = Query(default=None),
                                fecha_fin: str = Query(default=None)):
    df = _obtener_precios_df(ticker, db, fecha_inicio, fecha_fin)
    r = np.log(df["close"] / df["close"].shift(1)).dropna()
    return {"ticker": ticker,
            "serie": [{"fecha": str(f), "rendimiento": float(v)} for f, v in r.items()]}


# ═════════════════════════════ portafolio ═════════════════════════════

@router.get("/stress-test")
def stress_test(db: DBSession,
                tickers: list[str] = Query(default=None),
                pesos: list[float] = Query(default=None),
                benchmark: str = Query(default=None),
                fecha_inicio: str = Query(default=None),
                fecha_fin: str = Query(default=None)):
    tickers = tickers or settings.default_tickers
    benchmark = benchmark or settings.benchmark_ticker
    df_rend = _rendimientos_df(tickers, db, fecha_inicio, fecha_fin, tipo="simple")
    w = _vector_pesos(list(df_rend.columns), tickers, pesos)
    servicio = StressService(df_rend, _rend_benchmark(benchmark, db, fecha_inicio, fecha_fin), w)
    return {
        "tickers": list(df_rend.columns),
        "pesos": {t: round(float(x), 4) for t, x in zip(df_rend.columns, w)},
        "betas": {t: round(b, 4) for t, b in servicio.betas.items()},
        "fuente_beta": servicio.fuente_beta,
        "benchmark": benchmark,
        "escenarios": servicio.stress_test(),
    }


@router.get("/capm")
def calcular_capm(db: DBSession,
                  tickers: list[str] = Query(...),
                  benchmark: str = Query("^GSPC"),
                  tasa_libre_riesgo: float = Query(0.04),
                  fecha_inicio: str = Query(default=None),
                  fecha_fin: str = Query(default=None)):
    """CAPM estimado con la regresión de EXCESOS de rendimiento (modelo de mercado):
        (R_i - rf) = alpha + beta (R_m - rf) + e
    alpha (anualizado) es el alfa de Jensen. Se usan rendimientos simples."""
    rf_anual = tasa_libre_riesgo
    rf_d = (1 + rf_anual) ** (1 / DIAS_ANIO) - 1
    rb = _rend_benchmark(benchmark, db, fecha_inicio, fecha_fin)
    if rb is None:
        raise HTTPException(status_code=400, detail=f"Benchmark {benchmark} no está en BD.")
    ret_anual_bench = float(rb.mean() * DIAS_ANIO)

    resultados = []
    for t in tickers:
        try:
            ra = _obtener_precios_df(t, db, fecha_inicio, fecha_fin)["close"].pct_change().dropna()
        except HTTPException:
            continue
        datos = pd.concat([ra.rename("a"), rb.rename("m")], axis=1).dropna()
        if len(datos) < 30:
            continue
        y, x = datos["a"] - rf_d, datos["m"] - rf_d
        reg = scipy_stats.linregress(x, y)
        n = len(datos)
        # error estándar del intercepto para su t-test
        resid = y - (reg.intercept + reg.slope * x)
        s2 = float(np.sum(resid ** 2) / (n - 2))
        se_alpha = float(np.sqrt(s2 * (1 / n + x.mean() ** 2 / np.sum((x - x.mean()) ** 2))))
        t_alpha = reg.intercept / se_alpha if se_alpha > 0 else 0.0
        p_alpha = float(2 * scipy_stats.t.sf(abs(t_alpha), n - 2))
        p_beta = float(reg.pvalue)

        beta = float(reg.slope)
        r2 = float(reg.rvalue ** 2)
        ret_anual_activo = float(datos["a"].mean() * DIAS_ANIO)
        er_capm = rf_anual + beta * (ret_anual_bench - rf_anual)
        vol_total = float(datos["a"].std() * np.sqrt(DIAS_ANIO))
        vol_sist = abs(beta) * float(datos["m"].std() * np.sqrt(DIAS_ANIO))
        vol_idio = float(np.sqrt(max(vol_total ** 2 - vol_sist ** 2, 0)))
        clasificacion = "Agresivo" if beta > 1.2 else ("Defensivo" if beta < 0.8 else "Neutro")
        resultados.append({
            "ticker": t, "beta": beta, "clasificacion": clasificacion,
            "beta_p_value": round(p_beta, 6),
            "rendimiento_esperado_capm": er_capm,
            "rendimiento_observado_anual": ret_anual_activo,
            "prima_riesgo": er_capm - rf_anual,
            "alpha_jensen": float(reg.intercept * DIAS_ANIO),
            "alpha_p_value": round(p_alpha, 6),
            "alpha_significativo": p_alpha < 0.05,
            "r_cuadrado": r2,
            "volatilidad_total": vol_total,
            "volatilidad_sistematica": vol_sist,
            "volatilidad_idiosincratica": vol_idio,
            "treynor": (ret_anual_activo - rf_anual) / beta if beta != 0 else None,
            "tasa_libre_riesgo_anual": rf_anual,
            "rendimiento_mercado_anual": ret_anual_bench,
            "n_observaciones": n,
        })
    if not resultados:
        raise HTTPException(status_code=400, detail="No se pudo calcular el CAPM.")
    return {"benchmark": benchmark, "activos": resultados}


@router.get("/var-portafolio")
def var_portafolio(db: DBSession, nivel: float = Query(0.95, ge=0.80, le=0.999),
                   tickers: list[str] = Query(default=None),
                   pesos: list[float] = Query(default=None),
                   fecha_inicio: str = Query(default=None),
                   fecha_fin: str = Query(default=None)):
    tickers = tickers or settings.default_tickers
    df_rend = _rendimientos_df(tickers, db, fecha_inicio, fecha_fin, tipo="simple")
    w = _vector_pesos(list(df_rend.columns), tickers, pesos)
    return PortfolioService(df_rend).var_portafolio(w, nivel, settings.montecarlo_simulations)


@router.get("/markowitz", response_model=MarkowitzResponse)
def optimizar_portafolio(db: DBSession,
                         permitir_cortos: bool = False,
                         tickers: list[str] = Query(default=None),
                         pesos: list[float] = Query(default=None),
                         rf: float = Query(default=0.04, ge=-0.05, le=0.30),
                         fecha_inicio: str = Query(default=None),
                         fecha_fin: str = Query(default=None)):
    tickers = tickers or settings.default_tickers
    df_rend = _rendimientos_df(tickers, db, fecha_inicio, fecha_fin, tipo="simple")
    servicio = PortfolioService(df_rend, rf=rf)
    w_actual = _vector_pesos(list(df_rend.columns), tickers, pesos)
    max_sharpe = servicio.maximo_sharpe(permitir_cortos)
    return {
        "tickers": list(df_rend.columns),
        "tasa_libre_riesgo": rf,
        "optimizacion": max_sharpe,
        "maximo_sharpe": max_sharpe,
        "minima_varianza": servicio.minima_varianza(permitir_cortos),
        "portafolio_actual": servicio.metricas(w_actual),
        "pesos_iguales": servicio.metricas(np.full(servicio.n_activos, 1 / servicio.n_activos)),
        "activos": servicio.activos_individuales(),
        "correlacion": df_rend.corr().round(4).to_dict(),
        "frontera": servicio.frontera_eficiente(n_puntos=30, permitir_cortos=permitir_cortos),
        "n_observaciones": int(len(df_rend)),
    }


@router.get("/resumen-portafolio")
def resumen_portafolio(db: DBSession,
                       tickers: list[str] = Query(default=None),
                       pesos: list[float] = Query(default=None),
                       benchmark: str = Query(default=None),
                       nivel: float = Query(0.95, ge=0.80, le=0.999),
                       rf: float = Query(0.04),
                       fecha_inicio: str = Query(default=None),
                       fecha_fin: str = Query(default=None)):
    """Panel ejecutivo: las métricas clave del portafolio en un solo llamado."""
    tickers = tickers or settings.default_tickers
    benchmark = benchmark or settings.benchmark_ticker
    df_rend = _rendimientos_df(tickers, db, fecha_inicio, fecha_fin, tipo="simple")
    w = _vector_pesos(list(df_rend.columns), tickers, pesos)
    rp = pd.Series(df_rend.values @ w, index=df_rend.index)

    ret_anual = float(rp.mean() * DIAS_ANIO)
    vol_anual = float(rp.std() * np.sqrt(DIAS_ANIO))
    rf_d = (1 + rf) ** (1 / DIAS_ANIO) - 1
    downside = rp[rp < rf_d] - rf_d
    sortino_den = float(np.sqrt((downside ** 2).sum() / len(rp)) * np.sqrt(DIAS_ANIO))
    mdd, pico, fondo = _max_drawdown(rp)
    var_info = PortfolioService(df_rend).var_portafolio(w, nivel, 5000)

    salida = {
        "tickers": list(df_rend.columns),
        "pesos": {t: round(float(x), 4) for t, x in zip(df_rend.columns, w)},
        "fecha_inicio": str(df_rend.index[0].date()),
        "fecha_fin": str(df_rend.index[-1].date()),
        "n_observaciones": int(len(rp)),
        "retorno_acumulado": round(float((1 + rp).prod() - 1), 4),
        "retorno_anual": round(ret_anual, 4),
        "volatilidad_anual": round(vol_anual, 4),
        "sharpe": round((ret_anual - rf) / vol_anual, 4) if vol_anual > 0 else 0.0,
        "sortino": round((ret_anual - rf) / sortino_den, 4) if sortino_den > 0 else None,
        "max_drawdown": round(mdd, 4),
        "max_drawdown_pico": pico,
        "max_drawdown_fondo": fondo,
        "peor_dia": round(float(rp.min()), 4),
        "mejor_dia": round(float(rp.max()), 4),
        "pct_dias_positivos": round(float((rp > 0).mean()), 4),
        "var_historico": var_info["var_historico_portafolio"],
        "cvar_historico": var_info["cvar_historico_portafolio"],
        "nivel_confianza": nivel,
        "beneficio_diversificacion": var_info["beneficio_diversificacion"],
        "tasa_libre_riesgo": rf,
        "benchmark": benchmark,
        "serie_valor": [{"fecha": str(f.date()), "valor": round(float(v), 6)}
                        for f, v in (1 + rp).cumprod().items()],
    }

    rb = _rend_benchmark(benchmark, db, fecha_inicio, fecha_fin)
    if rb is not None:
        datos = pd.concat([rp.rename("p"), rb.rename("m")], axis=1).dropna()
        if len(datos) > 30:
            beta = float(datos["p"].cov(datos["m"]) / datos["m"].var())
            activo = datos["p"] - datos["m"]
            te = float(activo.std() * np.sqrt(DIAS_ANIO))
            salida.update({
                "beta": round(beta, 4),
                "retorno_anual_benchmark": round(float(datos["m"].mean() * DIAS_ANIO), 4),
                "retorno_acumulado_benchmark": round(float((1 + datos["m"]).prod() - 1), 4),
                "volatilidad_anual_benchmark": round(float(datos["m"].std() * np.sqrt(DIAS_ANIO)), 4),
                "tracking_error": round(te, 4),
                "information_ratio": round(float(activo.mean() * DIAS_ANIO / te), 4) if te > 0 else None,
                "correlacion_benchmark": round(float(datos["p"].corr(datos["m"])), 4),
                "serie_benchmark": [{"fecha": str(f.date()), "valor": round(float(v), 6)}
                                    for f, v in (1 + datos["m"]).cumprod().items()],
            })
    return salida


@router.get("/alertas")
def obtener_alertas(db: DBSession,
                    rsi_sobrecompra: int = 70,
                    rsi_sobreventa: int = 30,
                    tickers: list[str] = Query(default=None),
                    fecha_inicio: str = Query(default=None),
                    fecha_fin: str = Query(default=None)):
    tickers = tickers or settings.default_tickers
    alertas = []
    for ticker in tickers:
        try:
            df = pd.DataFrame(TechnicalIndicators(
                _obtener_precios_df(ticker, db, fecha_inicio, fecha_fin)).calcular_todos()).T
            if len(df) == 0:
                continue
            ultimo = df.iloc[-1]
            senales = []
            if ultimo["rsi"] > rsi_sobrecompra:
                senales.append(("RSI", "VENTA", float(ultimo["rsi"])))
            elif ultimo["rsi"] < rsi_sobreventa:
                senales.append(("RSI", "COMPRA", float(ultimo["rsi"])))
            if ultimo["close"] > ultimo["bollinger_upper"]:
                senales.append(("Bollinger", "VENTA", float(ultimo["close"])))
            elif ultimo["close"] < ultimo["bollinger_lower"]:
                senales.append(("Bollinger", "COMPRA", float(ultimo["close"])))
            if ultimo["macd"] > ultimo["macd_signal"]:
                senales.append(("MACD", "COMPRA", float(ultimo["macd"])))
            else:
                senales.append(("MACD", "VENTA", float(ultimo["macd"])))
            for regla, senal, valor in senales:
                db.add(SignalLog(ticker=ticker, regla=regla, señal=senal, valor=valor))
                alertas.append({"ticker": ticker, "regla": regla, "señal": senal, "valor": round(valor, 4)})
        except Exception:
            continue
    db.commit()
    return {"alertas": alertas, "total": len(alertas)}
