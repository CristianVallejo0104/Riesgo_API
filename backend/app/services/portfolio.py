import logging

import numpy as np
import pandas as pd
import cvxpy as cp

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

class PortfolioService:

    def __init__(self, rendimientos: pd.DataFrame):
        self.rendimientos = rendimientos
        self.n_activos = rendimientos.shape[1]
        self.media = rendimientos.mean().values * 252
        self.cov = rendimientos.cov().values * 252

    def optimizar_markowitz(self, permitir_cortos: bool = False) -> dict:
        pesos = cp.Variable(self.n_activos)
        retorno = self.media @ pesos
        riesgo = cp.quad_form(pesos, self.cov)

        restricciones = [cp.sum(pesos) == 1]
        if not permitir_cortos:
            restricciones.append(pesos >= 0)

        problema = cp.Problem(cp.Minimize(riesgo), restricciones)
        problema.solve()

        pesos_opt = pesos.value

        retorno_opt = float(pesos_opt @ self.media)
        riesgo_opt = float(np.sqrt(pesos_opt @ self.cov @ pesos_opt))
        sharpe = retorno_opt / riesgo_opt if riesgo_opt > 0 else 0

        return {
            "pesos": {col: round(float(w), 4) for col, w in zip(self.rendimientos.columns, pesos_opt)},
            "retorno_anual": round(retorno_opt, 4),
            "riesgo_anual": round(riesgo_opt, 4),
            "sharpe_ratio": round(sharpe, 4),
        }
    
    def frontera_eficiente(self, n_puntos: int = 50) -> list[dict]:
        retornos_objetivo = np.linspace(self.media.min(), self.media.max(), n_puntos)
        frontera = []

        for ret_obj in retornos_objetivo:
            pesos = cp.Variable(self.n_activos)
            riesgo = cp.quad_form(pesos, self.cov)
            restricciones = [
                cp.sum(pesos) == 1,
                pesos >= 0,
                self.media @ pesos >= ret_obj,
            ]
            problema = cp.Problem(cp.Minimize(riesgo), restricciones)
            problema.solve()

            if pesos.value is not None:
                r = float(pesos.value @ self.media)
                s = float(np.sqrt(pesos.value @ self.cov @ pesos.value))
                frontera.append({"retorno": round(r, 4), "riesgo": round(s, 4)})

        return frontera