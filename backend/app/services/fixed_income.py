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
    
    def sensibilidad_shocks(self, tasa_cupon: float = 0.05, valor_nominal: float = 100, vencimiento: int = 10) -> list:
        resultado_base = self.duracion_y_convexidad(tasa_cupon, valor_nominal, vencimiento)
        precio_base = resultado_base["precio_bono"]
        duracion_mod = resultado_base["duracion"] / (1 + resultado_base["tasa_descuento"])
        convexidad = resultado_base["convexidad"]
        tasa_base = resultado_base["tasa_descuento"]

        shocks_bp = [-200, -100, -50, 50, 100, 200]
        resultados = []

        for shock_bp in shocks_bp:
            delta_y = shock_bp / 10000
            nueva_tasa = tasa_base + delta_y

            # Aprox. lineal (solo duración)
            cambio_lineal = -duracion_mod * delta_y * precio_base
            precio_lineal = precio_base + cambio_lineal

            # Aprox. segundo orden (duración + convexidad)
            cambio_dc = (-duracion_mod * delta_y + 0.5 * convexidad * delta_y**2) * precio_base
            precio_dc = precio_base + cambio_dc

            # Reprice exacto
            flujos = [tasa_cupon * valor_nominal] * (vencimiento - 1) + [tasa_cupon * valor_nominal + valor_nominal]
            precio_exacto = sum(f / (1 + nueva_tasa)**t for t, f in enumerate(flujos, 1))

            resultados.append({
                "shock_bp": shock_bp,
                "precio_lineal": round(precio_lineal, 4),
                "precio_duracion_convexidad": round(precio_dc, 4),
                "precio_exacto": round(precio_exacto, 4),
                "cambio_pct_exacto": round((precio_exacto - precio_base) / precio_base * 100, 4),
            })

        return resultados