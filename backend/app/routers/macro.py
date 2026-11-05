import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from app.dependencies import DBSession
from app.models.db_models import Asset, Price
from app.services.macro import MacroService
from app.config import get_settings
from app.services.data import DataService

router = APIRouter(prefix="/macro", tags=["Macro"])
settings = get_settings()


@router.get("/")
def obtener_macro(db: DBSession, mercado: str = Query("US", pattern="^(US|CO|us|co)$")):
    macro = MacroService()
    rf = macro.tasa_libre_riesgo_info(mercado)
    return {
        "mercado": mercado.upper(),
        "tasa_libre_riesgo": rf["tasa"],
        "fuente_tasa": rf["fuente"],
        "tasa_es_respaldo": rf["es_respaldo"],
        "inflacion_anual_pct": macro.inflacion(),
        "curva": macro.curva_rendimiento(),
    }


@router.get("/benchmark")
def metricas_benchmark(db: DBSession, benchmark: str = "^GSPC",
                       rf: float | None = Query(default=None, description="Tasa libre de riesgo anual; si se omite se usa la de EE. UU."),
                       tickers: list[str] = Query(default=None),
                       pesos: list[float] = Query(default=None),
                       fecha_inicio: str = Query(default=None),
                       fecha_fin: str = Query(default=None)):
    """Desempeño relativo del portafolio frente al benchmark.
    Se usan rendimientos SIMPLES: el rendimiento del portafolio es el promedio
    ponderado de los rendimientos simples (con log-rendimientos eso no se cumple)."""
    # Import local para evitar import circular
    from app.routers.analisis import _rendimientos_df, _vector_pesos, _max_drawdown, _rend_benchmark

    tickers = tickers or settings.default_tickers
    servicio = DataService(db)
    try:
        servicio.descargar_precios(benchmark)
    except Exception:
        pass
    rb = _rend_benchmark(benchmark, db, fecha_inicio, fecha_fin)
    if rb is None:
        raise HTTPException(status_code=404, detail=f"No hay datos para {benchmark}")

    df_rend = _rendimientos_df(tickers, db, fecha_inicio, fecha_fin, tipo="simple")
    w = _vector_pesos(list(df_rend.columns), tickers, pesos)
    rp = pd.Series(df_rend.values @ w, index=df_rend.index)

    datos = pd.concat([rp.rename("p"), rb.rename("m")], axis=1).dropna()
    rp, rb = datos["p"], datos["m"]

    exceso = rp - rb
    tracking_error = float(exceso.std() * np.sqrt(252))
    information_ratio = float(exceso.mean() * 252 / tracking_error) if tracking_error > 0 else 0.0
    max_dd, _, _ = _max_drawdown(rp)
    max_dd_bench, _, _ = _max_drawdown(rb)
    rf = MacroService().tasa_libre_riesgo() if rf is None else rf
    vol_p = float(rp.std() * np.sqrt(252))

    return {
        "benchmark": benchmark,
        "tickers": list(df_rend.columns),
        "tracking_error": round(tracking_error, 4),
        "information_ratio": round(information_ratio, 4),
        "max_drawdown": round(max_dd, 4),
        "max_drawdown_benchmark": round(max_dd_bench, 4),
        "retorno_acumulado_portafolio": round(float((1 + rp).prod() - 1), 4),
        "retorno_acumulado_benchmark": round(float((1 + rb).prod() - 1), 4),
        "beta_portafolio": round(float(rp.cov(rb) / rb.var()), 4) if rb.var() > 0 else None,
        "correlacion": round(float(rp.corr(rb)), 4),
        "tasa_libre_riesgo": rf,
        "sharpe_portafolio": round((float(rp.mean() * 252) - rf) / vol_p, 4) if vol_p > 0 else 0.0,
        "sharpe_benchmark": round((float(rb.mean() * 252) - rf) / float(rb.std() * np.sqrt(252)), 4),
    }
