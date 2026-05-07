import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class StressService:

    def __init__(self, rendimientos: pd.DataFrame):
        self.rendimientos = rendimientos

    def stress_test(self) -> list[dict]:
        escenarios = [
            {"nombre": "Shock tasas +200pb", "tipo": "tasas", "magnitud": 0.02},
            {"nombre": "Caída mercado -30%", "tipo": "mercado", "magnitud": -0.30},
            {"nombre": "Shock volatilidad x2", "tipo": "volatilidad", "magnitud": 2.0},
            {"nombre": "Combinado", "tipo": "combinado", "magnitud": -0.20},
        ]
        resultados = []

        for esc in escenarios:
            impactos_activos = {}
            for col in self.rendimientos.columns:
                ret = self.rendimientos[col]
                if esc["tipo"] == "tasas":
                    impacto = -esc["magnitud"] * 5
                elif esc["tipo"] == "mercado":
                    beta = float(ret.cov(self.rendimientos.mean(axis=1)) / self.rendimientos.mean(axis=1).var()) if self.rendimientos.mean(axis=1).var() > 0 else 1.0
                    impacto = beta * esc["magnitud"]
                elif esc["tipo"] == "volatilidad":
                    impacto = -(ret.std() * np.sqrt(252)) * (esc["magnitud"] - 1) * 0.5
                else:
                    impacto = esc["magnitud"] * 0.8
                impactos_activos[col] = round(float(impacto), 4)

            impacto_port = float(np.mean(list(impactos_activos.values())))
            resultados.append({
                "escenario": esc["nombre"],
                "tipo": esc["tipo"],
                "magnitud": esc["magnitud"],
                "impacto_portafolio": round(impacto_port, 4),
                "impactos_por_activo": impactos_activos,
            })

        return resultados