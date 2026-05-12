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
        else:
            # Box constraints: máximo 30% en corto, máximo 120% en largo
            restricciones.append(pesos >= -0.2)
            restricciones.append(pesos <= 1.2)
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

    def frontera_eficiente(self, n_puntos: int = 50, permitir_cortos: bool = False) -> list[dict]:
        if permitir_cortos:
            # Calcular retorno máximo posible con los bounds permitidos
            pesos_max = cp.Variable(self.n_activos)
            restricciones_max = [
                cp.sum(pesos_max) == 1,
                pesos_max >= -0.2,
                pesos_max <= 1.2,
            ]
            prob_max = cp.Problem(cp.Maximize(self.media @ pesos_max), restricciones_max)
            prob_max.solve()
            retorno_max = float(self.media @ pesos_max.value) if pesos_max.value is not None else self.media.max() * 1.5

            # Calcular retorno mínimo posible
            pesos_min = cp.Variable(self.n_activos)
            restricciones_min = [
                cp.sum(pesos_min) == 1,
                pesos_min >= -0.2,
                pesos_min <= 1.2,
            ]
            prob_min = cp.Problem(cp.Minimize(self.media @ pesos_min), restricciones_min)
            prob_min.solve()
            retorno_min = float(self.media @ pesos_min.value) if pesos_min.value is not None else self.media.min()
        else:
            retorno_min = self.media.min()
            retorno_max = self.media.max()

        retornos_objetivo = np.linspace(retorno_min, retorno_max, n_puntos)
        frontera = []

        for ret_obj in retornos_objetivo:
            pesos = cp.Variable(self.n_activos)
            riesgo = cp.quad_form(pesos, self.cov)
            restricciones = [
                cp.sum(pesos) == 1,
                self.media @ pesos >= ret_obj,
            ]
            if not permitir_cortos:
                restricciones.append(pesos >= 0)
            else:
                restricciones.append(pesos >= -0.2)
                restricciones.append(pesos <= 1.2)

            problema = cp.Problem(cp.Minimize(riesgo), restricciones)
            problema.solve()
            if pesos.value is not None:
                r = float(pesos.value @ self.media)
                s = float(np.sqrt(pesos.value @ self.cov @ pesos.value))
                frontera.append({"retorno": round(r, 4), "riesgo": round(s, 4)})
        return frontera