"""
Valoración de opciones europeas con Black-Scholes (sin dividendos).

Unidades de las griegas devueltas
---------------------------------
* delta: cambio del precio de la opción por +1 USD en el subyacente.
* gamma: cambio de delta por +1 USD en el subyacente.
* vega:  cambio del precio por +1 punto porcentual de volatilidad (0.20 -> 0.21).
* theta: cambio del precio por cada DÍA calendario que pasa (normalmente negativo).
* rho:   cambio del precio por +1 punto porcentual en la tasa libre de riesgo.
"""
import logging

import numpy as np
from scipy.optimize import brentq
from scipy.stats import norm

logger = logging.getLogger(__name__)


class OptionsService:

    def __init__(self, S: float, K: float, T: float, r: float, sigma: float):
        self.S = S          # Precio actual del activo
        self.K = K          # Precio de ejercicio (strike)
        self.T = T          # Tiempo al vencimiento (años)
        self.r = r          # Tasa libre de riesgo (continua, anual)
        self.sigma = sigma  # Volatilidad anual

    def _d1_d2(self, sigma: float | None = None):
        s = self.sigma if sigma is None else sigma
        d1 = (np.log(self.S / self.K) + (self.r + s ** 2 / 2) * self.T) / (s * np.sqrt(self.T))
        return d1, d1 - s * np.sqrt(self.T)

    def _precio(self, sigma: float, tipo: str) -> float:
        d1, d2 = self._d1_d2(sigma)
        desc = self.K * np.exp(-self.r * self.T)
        if tipo == "call":
            return float(self.S * norm.cdf(d1) - desc * norm.cdf(d2))
        return float(desc * norm.cdf(-d2) - self.S * norm.cdf(-d1))

    def black_scholes(self) -> dict:
        d1, d2 = self._d1_d2()
        call, put = self._precio(self.sigma, "call"), self._precio(self.sigma, "put")
        intr_call = max(self.S - self.K, 0.0)
        intr_put = max(self.K - self.S, 0.0)
        return {
            "call": round(call, 4),
            "put": round(put, 4),
            "d1": round(float(d1), 6),
            "d2": round(float(d2), 6),
            "prob_ejercicio_call": round(float(norm.cdf(d2)), 4),  # N(d2), medida neutral al riesgo
            "prob_ejercicio_put": round(float(norm.cdf(-d2)), 4),
            "valor_intrinseco_call": round(intr_call, 4),
            "valor_tiempo_call": round(call - intr_call, 4),
            "valor_intrinseco_put": round(intr_put, 4),
            "valor_tiempo_put": round(put - intr_put, 4),
            # Paridad put-call: C - P = S - K e^{-rT}. Debe dar ~0.
            "error_paridad_put_call": round(call - put - (self.S - self.K * np.exp(-self.r * self.T)), 8),
        }

    def greeks(self) -> dict:
        d1, d2 = self._d1_d2()
        sqT = np.sqrt(self.T)
        desc = self.K * np.exp(-self.r * self.T)
        pdf = norm.pdf(d1)

        gamma = pdf / (self.S * self.sigma * sqT)
        vega = self.S * pdf * sqT / 100                       # por 1 p.p. de volatilidad
        theta_call = (-(self.S * pdf * self.sigma) / (2 * sqT) - self.r * desc * norm.cdf(d2)) / 365
        theta_put = (-(self.S * pdf * self.sigma) / (2 * sqT) + self.r * desc * norm.cdf(-d2)) / 365
        rho_call = self.K * self.T * np.exp(-self.r * self.T) * norm.cdf(d2) / 100
        rho_put = -self.K * self.T * np.exp(-self.r * self.T) * norm.cdf(-d2) / 100

        return {
            "delta_call": round(float(norm.cdf(d1)), 6),
            "delta_put": round(float(norm.cdf(d1) - 1), 6),
            "gamma": round(float(gamma), 6),
            "theta_call": round(float(theta_call), 6),
            "theta_put": round(float(theta_put), 6),
            "vega": round(float(vega), 6),
            "rho_call": round(float(rho_call), 6),
            "rho_put": round(float(rho_put), 6),
        }

    def volatilidad_implicita(self, precio_mercado: float, tipo: str = "call") -> float | None:
        """Volatilidad que hace que Black-Scholes iguale el precio de mercado.
        Se usa Brent (método de bisección robusto) en vez de Newton, que puede
        divergir cuando vega es muy pequeña (opciones muy dentro/fuera del dinero).
        Devuelve None si el precio viola los límites de no arbitraje."""
        desc = self.K * np.exp(-self.r * self.T)
        minimo = max(self.S - desc, 0) if tipo == "call" else max(desc - self.S, 0)
        maximo = self.S if tipo == "call" else desc
        if not (minimo < precio_mercado < maximo):
            return None
        try:
            vol = brentq(lambda s: self._precio(s, tipo) - precio_mercado, 1e-4, 10.0, xtol=1e-8)
            return round(float(vol), 6)
        except ValueError:
            return None
