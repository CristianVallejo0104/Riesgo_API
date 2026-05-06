import logging

import numpy as np
from scipy.stats import norm

logger = logging.getLogger(__name__)


class OptionsService:

    def __init__(self, S: float, K: float, T: float, r: float, sigma: float):
        self.S = S          # Precio actual del activo
        self.K = K          # Precio de ejercicio (strike)
        self.T = T          # Tiempo al vencimiento (años)
        self.r = r          # Tasa libre de riesgo
        self.sigma = sigma  # Volatilidad

    def black_scholes(self) -> dict:
        d1 = (np.log(self.S / self.K) + (self.r + self.sigma ** 2 / 2) * self.T) / (self.sigma * np.sqrt(self.T))
        d2 = d1 - self.sigma * np.sqrt(self.T)

        call = self.S * norm.cdf(d1) - self.K * np.exp(-self.r * self.T) * norm.cdf(d2)
        put = self.K * np.exp(-self.r * self.T) * norm.cdf(-d2) - self.S * norm.cdf(-d1)

        return {
            "call": round(float(call), 4),
            "put": round(float(put), 4),
            "d1": round(float(d1), 6),
            "d2": round(float(d2), 6),
        }
    
    def greeks(self) -> dict:
        d1 = (np.log(self.S / self.K) + (self.r + self.sigma ** 2 / 2) * self.T) / (self.sigma * np.sqrt(self.T))
        d2 = d1 - self.sigma * np.sqrt(self.T)

        delta_call = float(norm.cdf(d1))
        delta_put = float(norm.cdf(d1) - 1)
        gamma = float(norm.pdf(d1) / (self.S * self.sigma * np.sqrt(self.T)))
        theta_call = float(-(self.S * norm.pdf(d1) * self.sigma) / (2 * np.sqrt(self.T)) - self.r * self.K * np.exp(-self.r * self.T) * norm.cdf(d2))
        vega = float(self.S * norm.pdf(d1) * np.sqrt(self.T))
        rho_call = float(self.K * self.T * np.exp(-self.r * self.T) * norm.cdf(d2))

        return {
            "delta_call": round(delta_call, 6),
            "delta_put": round(delta_put, 6),
            "gamma": round(gamma, 6),
            "theta_call": round(theta_call, 6),
            "vega": round(vega, 6),
            "rho_call": round(rho_call, 6),
        }
    
    def volatilidad_implicita(self, precio_mercado: float, tipo: str = "call") -> float:
        sigma = 0.2
        for _ in range(100):
            servicio = OptionsService(self.S, self.K, self.T, self.r, sigma)
            bs = servicio.black_scholes()
            precio_bs = bs[tipo]
            d1 = bs["d1"]
            vega = self.S * norm.pdf(d1) * np.sqrt(self.T)

            if vega < 1e-10:
                break

            sigma = sigma - (precio_bs - precio_mercado) / vega

            if abs(precio_bs - precio_mercado) < 1e-6:
                break

        return round(float(sigma), 6)
    