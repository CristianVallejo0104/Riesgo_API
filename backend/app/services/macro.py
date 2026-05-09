import requests
import pandas as pd
import logging
import time
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

FALLBACKS = {
    "tasa_libre_riesgo": 0.045,
    "inflacion": 3.5,
}

_cache_curva = {"data": None, "timestamp": 0}
_cache_tasa  = {"data": None, "timestamp": 0}
CACHE_TTL = 3600

FRED_BASE = "https://api.stlouisfed.org/fred/series/observations"

class MacroService:
    def __init__(self):
        if not settings.fred_api_key:
            raise ValueError("FRED_API_KEY no configurada en .env")
        self.api_key = settings.fred_api_key

    def _get_serie(self, serie: str, timeout: int = 5) -> float | None:
        try:
            r = requests.get(FRED_BASE, params={
                "series_id": serie,
                "api_key": self.api_key,
                "file_type": "json",
                "sort_order": "desc",
                "limit": 5,
            }, timeout=timeout)
            if r.status_code == 200:
                obs = [o for o in r.json()["observations"] if o["value"] != "."]
                if obs:
                    return float(obs[0]["value"])
        except Exception as e:
            logger.warning(f"No se pudo obtener {serie}: {e}")
        return None

    def tasa_libre_riesgo(self) -> float:
        ahora = time.time()
        if _cache_tasa["data"] and (ahora - _cache_tasa["timestamp"]) < CACHE_TTL:
            return _cache_tasa["data"]
        resultado = self._get_serie(settings.fred_risk_free_series)
        tasa = resultado / 100 if resultado else FALLBACKS["tasa_libre_riesgo"]
        _cache_tasa["data"] = tasa
        _cache_tasa["timestamp"] = ahora
        return tasa

    def curva_rendimiento(self) -> dict:
        ahora = time.time()
        if _cache_curva["data"] and (ahora - _cache_curva["timestamp"]) < CACHE_TTL:
            return _cache_curva["data"]

        plazos_nombres = {
            "DGS3MO": 0.25, "DGS1": 1, "DGS2": 2,
            "DGS5": 5, "DGS10": 10, "DGS30": 30,
        }
        plazos, tasas = [], []
        for serie, plazo in plazos_nombres.items():
            resultado = self._get_serie(serie)
            if resultado is not None:
                plazos.append(plazo)
                tasas.append(resultado)

        if not plazos:
            plazos = [0.25, 1, 2, 5, 10, 30]
            tasas  = [4.5, 4.8, 4.6, 4.4, 4.3, 4.5]

        data = {"plazos": plazos, "tasas": tasas}
        _cache_curva["data"] = data
        _cache_curva["timestamp"] = ahora
        return data

    def inflacion(self) -> float:
        try:
            r = requests.get(FRED_BASE, params={
                "series_id": "CPIAUCSL",
                "api_key": self.api_key,
                "file_type": "json",
                "sort_order": "desc",
                "limit": 14,
            }, timeout=5)
            if r.status_code == 200:
                obs = [float(o["value"]) for o in r.json()["observations"] if o["value"] != "."]
                if len(obs) >= 13:
                    return round((obs[0] / obs[12] - 1) * 100, 4)
        except Exception as e:
            logger.warning(f"FRED inflacion falló: {e}")
        return FALLBACKS["inflacion"]