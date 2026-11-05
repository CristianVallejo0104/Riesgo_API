"""
Teoría Moderna de Portafolios (Markowitz) y riesgo de portafolio.

Por qué rendimientos SIMPLES aquí (y no logarítmicos)
----------------------------------------------------
El rendimiento de un portafolio es el promedio ponderado de los rendimientos
SIMPLES de sus activos:  R_p = sum(w_i * R_i).  Esa igualdad NO se cumple con
rendimientos logarítmicos, así que para combinar activos se usan simples.
"""
import logging

import cvxpy as cp
import numpy as np
import pandas as pd
from scipy import stats

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

DIAS_ANIO = 252
LIMITE_CORTO = -0.20   # con cortos: hasta 20 % del capital en corto por activo
LIMITE_LARGO = 1.20    # ... y hasta 120 % en largo


class PortfolioService:
    def __init__(self, rendimientos: pd.DataFrame, rf: float = 0.04):
        """`rendimientos`: DataFrame de rendimientos SIMPLES diarios (columnas = activos)."""
        self.rendimientos = rendimientos
        self.tickers = list(rendimientos.columns)
        self.n_activos = rendimientos.shape[1]
        self.rf = rf
        self.media = rendimientos.mean().values * DIAS_ANIO
        cov = rendimientos.cov().values * DIAS_ANIO
        # Pequeña regularización para garantizar que la matriz sea definida positiva
        self.cov = cov + np.eye(self.n_activos) * 1e-10

    # ───────────────────────── métricas de un vector de pesos ─────────────────
    def metricas(self, w: np.ndarray) -> dict:
        w = np.asarray(w, dtype=float)
        ret = float(w @ self.media)
        vol = float(np.sqrt(w @ self.cov @ w))
        return {
            "pesos": {t: round(float(x), 4) for t, x in zip(self.tickers, w)},
            "retorno_anual": round(ret, 4),
            "riesgo_anual": round(vol, 4),
            "sharpe_ratio": round((ret - self.rf) / vol, 4) if vol > 0 else 0.0,
        }

    def _restricciones(self, w, permitir_cortos: bool, escala=1):
        r = [cp.sum(w) == escala]
        if permitir_cortos:
            r += [w >= LIMITE_CORTO * escala, w <= LIMITE_LARGO * escala]
        else:
            r += [w >= 0]
        return r

    @staticmethod
    def _resolver(problema: cp.Problem):
        try:
            problema.solve()
        except cp.SolverError:
            problema.solve(solver=cp.SCS)

    # ───────────────────────── portafolios óptimos ────────────────────────────
    def minima_varianza(self, permitir_cortos: bool = False) -> dict:
        w = cp.Variable(self.n_activos)
        prob = cp.Problem(cp.Minimize(cp.quad_form(w, cp.psd_wrap(self.cov))),
                          self._restricciones(w, permitir_cortos))
        self._resolver(prob)
        return self.metricas(w.value)

    def maximo_sharpe(self, permitir_cortos: bool = False) -> dict:
        """Portafolio tangente: maximiza (E[R]-rf)/sigma.

        Se resuelve como problema convexo con el cambio de variable y = k*w:
            min y'Σy   s.a.  (mu - rf)'y = 1,  sum(y) = k,  k >= 0
        y luego w = y / k.  Requiere que al menos un activo rinda más que rf.
        """
        exceso = self.media - self.rf
        if np.all(exceso <= 0):
            # Ningún activo supera la tasa libre de riesgo: el "mejor" Sharpe es el
            # menos negativo; se aproxima buscando sobre la frontera.
            frontera = self.frontera_eficiente(60, permitir_cortos, incluir_pesos=True)
            mejor = max(frontera, key=lambda p: (p["retorno"] - self.rf) / p["riesgo"])
            return self.metricas(np.array([mejor["pesos"][t] for t in self.tickers]))

        y = cp.Variable(self.n_activos)
        k = cp.Variable(nonneg=True)
        restr = [exceso @ y == 1] + self._restricciones(y, permitir_cortos, escala=k)
        prob = cp.Problem(cp.Minimize(cp.quad_form(y, cp.psd_wrap(self.cov))), restr)
        self._resolver(prob)
        if y.value is None or k.value is None or k.value <= 1e-12:
            return self.minima_varianza(permitir_cortos)
        return self.metricas(y.value / k.value)

    def optimizar_markowitz(self, permitir_cortos: bool = False) -> dict:
        """Compatibilidad: devuelve el portafolio de máximo Sharpe."""
        return self.maximo_sharpe(permitir_cortos)

    def frontera_eficiente(self, n_puntos: int = 40, permitir_cortos: bool = False,
                           incluir_pesos: bool = False) -> list[dict]:
        """Sólo la parte EFICIENTE: desde el portafolio de mínima varianza hasta el
        de máximo retorno. La rama inferior (mismo riesgo, menos retorno) no es
        eficiente y por eso no se dibuja."""
        w_mv = cp.Variable(self.n_activos)
        self._resolver(cp.Problem(cp.Minimize(cp.quad_form(w_mv, cp.psd_wrap(self.cov))),
                                  self._restricciones(w_mv, permitir_cortos)))
        ret_min = float(self.media @ w_mv.value)

        w_max = cp.Variable(self.n_activos)
        self._resolver(cp.Problem(cp.Maximize(self.media @ w_max),
                                  self._restricciones(w_max, permitir_cortos)))
        ret_max = float(self.media @ w_max.value)

        frontera = []
        for objetivo in np.linspace(ret_min, ret_max, n_puntos):
            w = cp.Variable(self.n_activos)
            restr = self._restricciones(w, permitir_cortos) + [self.media @ w >= objetivo]
            prob = cp.Problem(cp.Minimize(cp.quad_form(w, cp.psd_wrap(self.cov))), restr)
            self._resolver(prob)
            if w.value is None:
                continue
            punto = {"retorno": round(float(w.value @ self.media), 4),
                     "riesgo": round(float(np.sqrt(w.value @ self.cov @ w.value)), 4)}
            if incluir_pesos:
                punto["pesos"] = {t: float(x) for t, x in zip(self.tickers, w.value)}
            frontera.append(punto)
        return frontera

    def activos_individuales(self) -> list[dict]:
        vols = np.sqrt(np.diag(self.cov))
        return [{"ticker": t, "retorno": round(float(m), 4), "riesgo": round(float(s), 4),
                 "sharpe": round(float((m - self.rf) / s), 4) if s > 0 else 0.0}
                for t, m, s in zip(self.tickers, self.media, vols)]

    # ───────────────────────── VaR de portafolio ──────────────────────────────
    def var_portafolio(self, pesos: np.ndarray, nivel: float = 0.95, n_sim: int = 10_000,
                       semilla: int = 42) -> dict:
        """VaR diario del portafolio por 3 métodos + descomposición por activo."""
        w = np.asarray(pesos, dtype=float)
        R = self.rendimientos.values
        rp = R @ w                                   # serie histórica del portafolio
        alpha = 1 - nivel
        z = stats.norm.ppf(alpha)

        mu_d = self.rendimientos.mean().values
        cov_d = self.rendimientos.cov().values
        mu_p = float(w @ mu_d)
        sigma_p = float(np.sqrt(w @ cov_d @ w))

        var_param = mu_p + z * sigma_p
        var_hist = float(np.percentile(rp, alpha * 100))
        cvar_hist = float(rp[rp <= var_hist].mean())
        cvar_param = mu_p - sigma_p * stats.norm.pdf(z) / alpha

        # Monte Carlo con normal multivariada: respeta las correlaciones entre activos
        rng = np.random.default_rng(semilla)
        sims = rng.multivariate_normal(mu_d, cov_d, size=n_sim) @ w
        var_mc = float(np.percentile(sims, alpha * 100))

        # VaR individual (paramétrico) de cada posición y suma "sin diversificar"
        sig_i = np.sqrt(np.diag(cov_d))
        var_indiv = w * (mu_d + z * sig_i)           # en fracción del capital total
        suma_indiv = float(var_indiv.sum())

        # VaR por componentes (Euler): CVaR_i = w_i * (dVaR/dw_i); suman el VaR total
        marginal = mu_d + z * (cov_d @ w) / sigma_p if sigma_p > 0 else mu_d
        componente = w * marginal
        contrib = componente / var_param if var_param != 0 else np.zeros_like(w)

        return {
            "tickers": self.tickers,
            "pesos": {t: round(float(x), 4) for t, x in zip(self.tickers, w)},
            "nivel_confianza": nivel,
            "var_parametrico_portafolio": round(var_param, 6),
            "var_historico_portafolio": round(var_hist, 6),
            "var_montecarlo_portafolio": round(var_mc, 6),
            "cvar_historico_portafolio": round(cvar_hist, 6),
            "cvar_parametrico_portafolio": round(float(cvar_param), 6),
            "suma_var_individuales": round(suma_indiv, 6),
            # VaR expresados como rendimientos negativos: el del portafolio es menos negativo
            "beneficio_diversificacion": round(var_param - suma_indiv, 6),
            "volatilidad_anual_portafolio": round(sigma_p * np.sqrt(DIAS_ANIO), 4),
            "retorno_anual_esperado": round(mu_p * DIAS_ANIO, 4),
            "contribucion_por_activo": [
                {"ticker": t, "peso": round(float(wi), 4), "var_individual": round(float(vi), 6),
                 "var_componente": round(float(ci), 6), "contribucion_pct": round(float(pi), 4)}
                for t, wi, vi, ci, pi in zip(self.tickers, w, var_indiv, componente, contrib)
            ],
            "n_observaciones": int(len(rp)),
        }
