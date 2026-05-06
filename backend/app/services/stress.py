import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class StressService:

    def __init__(self, rendimientos: pd.DataFrame):
        self.rendimientos = rendimientos

    def stress_test(self) -> list[dict]:
        escenarios = [
            {"nombre": "Shock de tasas +200bp", "tipo": "tasas", "magnitud": 0.02},
            {"nombre": "Caída de mercado -30%", "tipo": "mercado", "magnitud": -0.30},
            {"nombre": "Shock de volatilidad x2", "tipo": "volatilidad", "magnitud": 2.0},
        ]
        resultados = []

        for esc in escenarios:
            if esc["tipo"] == "tasas":
                impacto = -esc["magnitud"] * 5
            elif esc["tipo"] == "mercado":
                impacto = float(self.rendimientos.mean().mean() * 252 + esc["magnitud"])
            else:
                vol_actual = float(self.rendimientos.std().mean() * np.sqrt(252))
                impacto = vol_actual * esc["magnitud"]

            resultados.append({
                "escenario": esc["nombre"],
                "tipo": esc["tipo"],
                "magnitud": esc["magnitud"],
                "impacto_portafolio": round(float(impacto), 4),
            })

        return resultados