import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.dependencies import DBSession
from app.models.db_models import Asset, Price
from app.services.macro import MacroService
from app.config import get_settings
from app.services.data import DataService

router = APIRouter(prefix="/macro", tags=["Macro"])
settings = get_settings()


@router.get("/")
def obtener_macro(db: DBSession):
    macro = MacroService()
    return {
        "tasa_libre_riesgo": macro.tasa_libre_riesgo(),
        "inflacion_anual_pct": macro.inflacion(),
        "curva": macro.curva_rendimiento(),
    }


@router.get("/benchmark")
def metricas_benchmark(db: DBSession, benchmark: str = "^GSPC"):
    servicio = DataService(db)
    tickers = settings.default_tickers

    precios_bench = servicio.descargar_precios(benchmark)
    if not precios_bench:
        raise HTTPException(status_code=404, detail=f"No hay datos para {benchmark}")

    df_bench = pd.DataFrame([{"fecha": p.fecha, "close": p.close} for p in precios_bench])
    df_bench.set_index("fecha", inplace=True)
    ret_bench = np.log(df_bench["close"] / df_bench["close"].shift(1)).dropna()

    pesos = {t: 1/len(tickers) for t in tickers}
    ret_port = pd.Series(dtype=float)

    for ticker in tickers:
        precios = servicio.descargar_precios(ticker)
        if precios:
            df_t = pd.DataFrame([{"fecha": p.fecha, "close": p.close} for p in precios])
            df_t.set_index("fecha", inplace=True)
            ret_t = np.log(df_t["close"] / df_t["close"].shift(1)).dropna()
            if ret_port.empty:
                ret_port = ret_t * pesos[ticker]
            else:
                comunes = ret_port.index.intersection(ret_t.index)
                ret_port = ret_port.loc[comunes] + ret_t.loc[comunes] * pesos[ticker]

    comunes = ret_port.index.intersection(ret_bench.index)
    rp = ret_port.loc[comunes]
    rb = ret_bench.loc[comunes]

    exceso = rp - rb
    tracking_error = float(exceso.std() * np.sqrt(252))
    information_ratio = float(exceso.mean() * 252 / tracking_error) if tracking_error > 0 else 0

    # Max Drawdown del portafolio
    cum = (1 + rp).cumprod()
    rolling_max = cum.cummax()
    drawdown = (cum - rolling_max) / rolling_max
    max_drawdown = float(drawdown.min())

    # Rendimiento acumulado base 100
    ret_acum_port = float((1 + rp).prod() - 1)
    ret_acum_bench = float((1 + rb).prod() - 1)

    return {
        "benchmark": benchmark,
        "tracking_error": round(tracking_error, 4),
        "information_ratio": round(information_ratio, 4),
        "max_drawdown": round(max_drawdown, 4),
        "retorno_acumulado_portafolio": round(ret_acum_port, 4),
        "retorno_acumulado_benchmark": round(ret_acum_bench, 4),
        "sharpe_portafolio": round(float(rp.mean() * 252 / (rp.std() * np.sqrt(252))), 4),
    }