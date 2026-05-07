import logging
from fredapi import Fred

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class MacroService:

    def __init__(self):
        if not settings.fred_api_key:
            raise ValueError("FRED_API_KEY no configurada en .env")
        self.fred = Fred(api_key=settings.fred_api_key)

    def tasa_libre_riesgo(self) -> float:
        datos = self.fred.get_series(settings.fred_risk_free_series)
        tasa = float(datos.dropna().iloc[-1]) / 100
        return tasa

    def curva_rendimiento(self) -> dict:
        plazos_nombres = {
            "DGS3MO": 0.25, "DGS1": 1, "DGS2": 2,
            "DGS5": 5, "DGS10": 10, "DGS30": 30,
        }
        plazos = []
        tasas = []
        for serie, plazo in plazos_nombres.items():
            try:
                datos = self.fred.get_series(serie)
                tasa = float(datos.dropna().iloc[-1])
                plazos.append(plazo)
                tasas.append(tasa)
            except Exception as e:
                logger.warning(f"No se pudo obtener {serie}: {e}")

        return {"plazos": plazos, "tasas": tasas}
    
    def inflacion(self) -> float:
        datos = self.fred.get_series("CPIAUCSL")
        datos = datos.dropna()
        # Inflación anualizada: variación % 12 meses
        inflacion = float((datos.iloc[-1] / datos.iloc[-13] - 1) * 100)
        return round(inflacion, 4)