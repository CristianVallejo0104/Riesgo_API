import logging

import numpy as np
from scipy.optimize import minimize

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

class FixedIncomeService:

    def __init__(self, plazos: list[float], tasas: list[float]):
        self.plazos = np.array(plazos)
        self.tasas = np.array(tasas)

    @staticmethod
    def _nelson_siegel(t, beta0, beta1, beta2, tau):
        factor = (1 - np.exp(-t / tau)) / (t / tau)
        return beta0 + beta1 * factor + beta2 * (factor - np.exp(-t / tau))

    def ajustar_nelson_siegel(self) -> dict:
        def objetivo(params):
            beta0, beta1, beta2, tau = params
            predichas = self._nelson_siegel(self.plazos, beta0, beta1, beta2, tau)
            return np.sum((self.tasas - predichas) ** 2)

        resultado = minimize(
            objetivo,
            x0=[0.03, -0.01, 0.01, 1.0],
            method="Nelder-Mead",
        )
        beta0, beta1, beta2, tau = resultado.x

        tasas_ajustadas = self._nelson_siegel(self.plazos, beta0, beta1, beta2, tau)

        return {
            "beta0": round(float(beta0), 6),
            "beta1": round(float(beta1), 6),
            "beta2": round(float(beta2), 6),
            "tau": round(float(tau), 6),
            "tasas_ajustadas": [round(float(t), 6) for t in tasas_ajustadas],
            "error_cuadratico": round(float(resultado.fun), 8),
        }
    
    def duracion_y_convexidad(self, tasa_cupon: float = 0.05, valor_nominal: float = 100, vencimiento: int = 10) -> dict:
        flujos = []
        tiempos = []

        for t in range(1, vencimiento + 1):
            if t < vencimiento:
                flujos.append(tasa_cupon * valor_nominal)
            else:
                flujos.append(tasa_cupon * valor_nominal + valor_nominal)
            tiempos.append(t)

        tasa = float(self.tasas[-1]) / 100
        flujos = np.array(flujos)
        tiempos = np.array(tiempos)

        vp_flujos = flujos / (1 + tasa) ** tiempos
        precio = vp_flujos.sum()

        duracion = np.sum(tiempos * vp_flujos) / precio
        convexidad = np.sum(tiempos * (tiempos + 1) * vp_flujos) / (precio * (1 + tasa) ** 2)

        return {
            "precio_bono": round(float(precio), 4),
            "duracion": round(float(duracion), 4),
            "convexidad": round(float(convexidad), 4),
            "tasa_descuento": round(tasa, 6),
        }