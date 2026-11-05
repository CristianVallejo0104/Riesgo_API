"""
Renta fija: curva de rendimientos (Nelson-Siegel), duración y convexidad.

Convenciones: bono con cupón ANUAL, nominal 100, tasas en decimales
(0.045 = 4.5 %). Las tasas de la curva de FRED llegan en porcentaje.
"""
import logging

import numpy as np
from scipy.optimize import minimize

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class FixedIncomeService:

    def __init__(self, plazos: list[float], tasas: list[float]):
        """`tasas` en PORCENTAJE (como las entrega FRED)."""
        orden = np.argsort(plazos)
        self.plazos = np.array(plazos, dtype=float)[orden]
        self.tasas = np.array(tasas, dtype=float)[orden]

    # ───────────────────────── Nelson-Siegel ─────────────────────────────────
    @staticmethod
    def _nelson_siegel(t, beta0, beta1, beta2, tau):
        """y(t) = b0 + b1 * f1 + b2 * (f1 - e^{-t/tau}),  f1 = (1 - e^{-t/tau}) / (t/tau)
        b0 = nivel de largo plazo, b1 = pendiente (corto - largo), b2 = curvatura (joroba)."""
        t = np.asarray(t, dtype=float)
        x = t / tau
        factor = np.where(x > 1e-8, (1 - np.exp(-x)) / np.where(x > 1e-8, x, 1), 1.0)
        return beta0 + beta1 * factor + beta2 * (factor - np.exp(-x))

    def ajustar_nelson_siegel(self) -> dict:
        def objetivo(p):
            return np.sum((self.tasas - self._nelson_siegel(self.plazos, *p)) ** 2)

        x0 = [self.tasas[-1], self.tasas[0] - self.tasas[-1], 0.0, 2.0]
        res = minimize(objetivo, x0=x0, method="L-BFGS-B",
                       bounds=[(0, 20), (-20, 20), (-20, 20), (0.05, 30)])
        b0, b1, b2, tau = res.x
        ajustadas = self._nelson_siegel(self.plazos, b0, b1, b2, tau)
        malla = np.linspace(max(0.08, self.plazos.min()), self.plazos.max(), 80)
        return {
            "beta0": round(float(b0), 6),
            "beta1": round(float(b1), 6),
            "beta2": round(float(b2), 6),
            "tau": round(float(tau), 6),
            "tasas_ajustadas": [round(float(t), 6) for t in ajustadas],
            "error_cuadratico": round(float(res.fun), 8),
            "rmse_pb": round(float(np.sqrt(res.fun / len(self.plazos)) * 100), 2),
            "curva_suave": [{"plazo": round(float(p), 3), "tasa": round(float(y), 4)}
                            for p, y in zip(malla, self._nelson_siegel(malla, b0, b1, b2, tau))],
            "pendiente_10a_3m": round(float(np.interp(10, self.plazos, self.tasas)
                                            - np.interp(0.25, self.plazos, self.tasas)), 4),
        }

    def tasa_para_plazo(self, plazo: float) -> float:
        """Tasa de la curva (en decimal) interpolada linealmente al plazo del bono."""
        return float(np.interp(plazo, self.plazos, self.tasas)) / 100

    # ───────────────────────── Bonos ─────────────────────────────────────────
    # Notación: m = pagos por año (1 anual, 2 semestral, 4 trimestral, 12 mensual),
    # n = vencimiento * m períodos, y = tasa anual nominal (capitalizable m veces).
    # Cada período se descuenta a la tasa periódica y/m.
    FRECUENCIAS = {1: "anual", 2: "semestral", 4: "trimestral", 12: "mensual"}

    @staticmethod
    def _flujos(tasa_cupon: float, valor_nominal: float, vencimiento: float, frecuencia: int = 1):
        n = max(1, int(round(vencimiento * frecuencia)))
        k = np.arange(1, n + 1, dtype=float)                 # número de período
        flujos = np.full(n, tasa_cupon * valor_nominal / frecuencia)
        flujos[-1] += valor_nominal
        return k, flujos

    @classmethod
    def precio(cls, tasa: float, tasa_cupon: float, valor_nominal: float, vencimiento: float,
               frecuencia: int = 1) -> float:
        k, f = cls._flujos(tasa_cupon, valor_nominal, vencimiento, frecuencia)
        return float(np.sum(f / (1 + tasa / frecuencia) ** k))

    def duracion_y_convexidad(self, tasa_cupon: float = 0.05, valor_nominal: float = 100,
                              vencimiento: float = 10, tasa_descuento: float | None = None,
                              frecuencia: int = 1) -> dict:
        """Si no se da `tasa_descuento` se usa la tasa de la curva al plazo del bono
        (antes se usaba siempre la de 30 años, lo que no tiene sentido para un bono a 2 años)."""
        m = int(frecuencia)
        tasa = self.tasa_para_plazo(vencimiento) if tasa_descuento is None else float(tasa_descuento)
        k, f = self._flujos(tasa_cupon, valor_nominal, vencimiento, m)
        yp = tasa / m                                            # tasa por período
        vp = f / (1 + yp) ** k
        precio = vp.sum()

        d_mac = float(np.sum((k / m) * vp) / precio)             # en años
        d_mod = d_mac / (1 + yp)                                 # % de cambio por 1.00 de tasa anual
        convex = float(np.sum(k * (k + 1) * vp) / (precio * (1 + yp) ** 2 * m ** 2))  # en años²
        dv01 = d_mod * precio * 0.0001                           # $ por 1 pb

        return {
            "precio_bono": round(float(precio), 4),
            "precio_pct_nominal": round(float(precio / valor_nominal * 100), 4),
            "valor_nominal": valor_nominal,
            "frecuencia": m,
            "frecuencia_nombre": self.FRECUENCIAS.get(m, f"{m} veces al año"),
            "cupon_por_pago": round(float(tasa_cupon * valor_nominal / m), 4),
            "numero_pagos": int(len(k)),
            "es_cupon_cero": tasa_cupon == 0,
            "duracion": round(d_mac, 4),               # compatibilidad: Macaulay
            "duracion_macaulay": round(d_mac, 4),
            "duracion_modificada": round(d_mod, 4),
            "convexidad": round(convex, 4),
            "dv01": round(float(dv01), 4),
            "tasa_descuento": round(tasa, 6),
            "fuente_tasa": "curva FRED interpolada" if tasa_descuento is None else "ingresada por el usuario",
            "cotiza": "a la par" if abs(precio - valor_nominal) < 0.005 * valor_nominal / 100
                      else ("con prima" if precio > valor_nominal else "con descuento"),
            "flujos": [{"periodo": int(kk), "anio": round(float(kk / m), 4), "flujo": round(float(ff), 4),
                        "valor_presente": round(float(v), 4)} for kk, ff, v in zip(k, f, vp)],
        }

    def sensibilidad_shocks(self, tasa_cupon: float = 0.05, valor_nominal: float = 100,
                            vencimiento: float = 10, tasa_descuento: float | None = None,
                            frecuencia: int = 1) -> list:
        base = self.duracion_y_convexidad(tasa_cupon, valor_nominal, vencimiento, tasa_descuento, frecuencia)
        p0, dm, cx, y0 = (base["precio_bono"], base["duracion_modificada"],
                          base["convexidad"], base["tasa_descuento"])
        resultados = []
        for shock_bp in [-200, -100, -50, -25, 0, 25, 50, 100, 200]:
            dy = shock_bp / 10000
            p_lin = p0 * (1 - dm * dy)                          # 1er orden
            p_dc = p0 * (1 - dm * dy + 0.5 * cx * dy ** 2)      # 2do orden
            p_ex = self.precio(y0 + dy, tasa_cupon, valor_nominal, vencimiento, frecuencia)
            resultados.append({
                "shock_bp": shock_bp,
                "precio_lineal": round(p_lin, 4),
                "precio_duracion_convexidad": round(p_dc, 4),
                "precio_exacto": round(p_ex, 4),
                "cambio_pct_exacto": round((p_ex - p0) / p0 * 100, 4),
                "error_lineal": round(p_lin - p_ex, 4),
                "error_duracion_convexidad": round(p_dc - p_ex, 4),
            })
        return resultados
