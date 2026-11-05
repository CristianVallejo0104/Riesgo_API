"""
Servicio de medición de riesgo de mercado para un activo individual.

Convenciones usadas en todo el módulo
-------------------------------------
* Rendimientos logarítmicos diarios  r_t = ln(P_t / P_{t-1}).
  Se usan para un activo individual porque son aditivos en el tiempo
  (el rendimiento de 10 días es la suma de los 10 rendimientos diarios).
* El VaR y el CVaR se reportan como **rendimientos negativos**
  (ej. -0.025 = "puedo perder 2.5 % en un día"). Para pasarlos a dinero
  basta multiplicar su valor absoluto por el capital invertido.
* `nivel` es el nivel de confianza (0.95 = 95 %). La cola analizada es
  alpha = 1 - nivel.
* Para escalar a un horizonte de h días se usa la regla de la raíz del
  tiempo (sigma_h = sigma_1 * sqrt(h)), que asume rendimientos i.i.d.
"""
import logging

import numpy as np
import pandas as pd
from scipy import stats

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

DIAS_ANIO = 252


class RiskService:

    def __init__(self, precios: pd.DataFrame, semilla: int = 42):
        self.precios = precios
        self.rendimientos = np.log(precios["close"] / precios["close"].shift(1)).dropna()
        # Semilla fija -> Monte Carlo reproducible (mismo resultado en cada consulta)
        self.rng = np.random.default_rng(semilla)

    # ────────────────────────────── utilidades ──────────────────────────────
    @staticmethod
    def _nivel(nivel: float | None) -> float:
        return settings.var_confidence_level if nivel is None else nivel

    # ────────────────────────────── volatilidad ─────────────────────────────
    def serie_ewma(self, lambd: float | None = None) -> pd.Series:
        """Varianza condicional EWMA (RiskMetrics):
        sigma²_t = lambda * sigma²_{t-1} + (1 - lambda) * r²_{t-1}
        Devuelve la volatilidad diaria (no anualizada) para cada fecha.
        """
        lambd = settings.ewma_lambda if lambd is None else lambd
        r = self.rendimientos.values
        var = np.empty(len(r))
        # Semilla: varianza muestral de los primeros 30 días (o de todos si hay menos)
        var[0] = np.var(r[: min(30, len(r))], ddof=1) if len(r) > 1 else r[0] ** 2
        for t in range(1, len(r)):
            var[t] = lambd * var[t - 1] + (1 - lambd) * r[t - 1] ** 2
        return pd.Series(np.sqrt(var), index=self.rendimientos.index)

    def volatilidad_ewma(self, lambd: float | None = None) -> float:
        """Volatilidad EWMA anualizada pronosticada para el próximo día."""
        lambd = settings.ewma_lambda if lambd is None else lambd
        sigma = self.serie_ewma(lambd)
        r_ult = float(self.rendimientos.iloc[-1])
        var_siguiente = lambd * sigma.iloc[-1] ** 2 + (1 - lambd) * r_ult ** 2
        return float(np.sqrt(var_siguiente * DIAS_ANIO))

    def volatilidad_historica(self) -> float:
        return float(self.rendimientos.std() * np.sqrt(DIAS_ANIO))

    # ────────────────────────────── VaR ─────────────────────────────────────
    def var_parametrico(self, nivel: float | None = None, horizonte: int = 1) -> float:
        """VaR Normal (varianza-covarianza): mu*h + z_alpha * sigma * sqrt(h)."""
        nivel = self._nivel(nivel)
        mu, sigma = self.rendimientos.mean(), self.rendimientos.std()
        z = stats.norm.ppf(1 - nivel)
        return float(mu * horizonte + z * sigma * np.sqrt(horizonte))

    def var_cornish_fisher(self, nivel: float | None = None, horizonte: int = 1) -> float:
        """VaR Normal corregido por asimetría (S) y curtosis en exceso (K).
        z_cf = z + (z²-1)S/6 + (z³-3z)K/24 - (2z³-5z)S²/36
        Si los datos tienen colas pesadas, este VaR será más negativo que el Normal.
        """
        nivel = self._nivel(nivel)
        mu, sigma = self.rendimientos.mean(), self.rendimientos.std()
        s = float(stats.skew(self.rendimientos))
        k = float(stats.kurtosis(self.rendimientos))  # curtosis en EXCESO (normal = 0)
        z = stats.norm.ppf(1 - nivel)
        z_cf = (z + (z**2 - 1) * s / 6 + (z**3 - 3 * z) * k / 24
                - (2 * z**3 - 5 * z) * s**2 / 36)
        return float(mu * horizonte + z_cf * sigma * np.sqrt(horizonte))

    def var_historico(self, nivel: float | None = None, horizonte: int = 1) -> float:
        """Percentil (1-nivel) de los rendimientos observados. No supone ninguna distribución."""
        nivel = self._nivel(nivel)
        return float(np.percentile(self.rendimientos, (1 - nivel) * 100) * np.sqrt(horizonte))

    def var_montecarlo(self, nivel: float | None = None, n_sim: int | None = None,
                       horizonte: int = 1) -> float:
        """Monte Carlo con distribución t de Student ajustada por máxima verosimilitud.

        Simular con una Normal daría exactamente el mismo resultado que el VaR
        paramétrico (sólo con ruido). La t de Student captura las colas pesadas
        típicas de los rendimientos financieros, por eso aporta información nueva.
        """
        nivel = self._nivel(nivel)
        n_sim = settings.montecarlo_simulations if n_sim is None else n_sim
        try:
            gl, loc, escala = stats.t.fit(self.rendimientos)
            gl = max(gl, 2.5)  # gl <= 2 implica varianza infinita
        except Exception:
            gl, loc, escala = 30.0, self.rendimientos.mean(), self.rendimientos.std()
        # Suma de h días simulados (rendimientos log son aditivos en el tiempo)
        sims = stats.t.rvs(gl, loc=loc, scale=escala, size=(n_sim, horizonte),
                           random_state=self.rng).sum(axis=1)
        return float(np.percentile(sims, (1 - nivel) * 100))

    # ────────────────────────────── CVaR / ES ───────────────────────────────
    def cvar(self, nivel: float | None = None, horizonte: int = 1) -> float:
        """Expected Shortfall histórico: promedio de los rendimientos <= VaR histórico."""
        nivel = self._nivel(nivel)
        var = np.percentile(self.rendimientos, (1 - nivel) * 100)
        cola = self.rendimientos[self.rendimientos <= var]
        return float(cola.mean() * np.sqrt(horizonte))

    def cvar_parametrico(self, nivel: float | None = None, horizonte: int = 1) -> float:
        """ES Normal: mu - sigma * phi(z) / alpha."""
        nivel = self._nivel(nivel)
        alpha = 1 - nivel
        mu, sigma = self.rendimientos.mean(), self.rendimientos.std()
        z = stats.norm.ppf(alpha)
        return float(mu * horizonte - sigma * np.sqrt(horizonte) * stats.norm.pdf(z) / alpha)

    # ────────────────────────────── Backtesting ─────────────────────────────
    @staticmethod
    def _kupiec(excepciones: int, n: int, p: float) -> tuple[float, float]:
        """Estadístico LR de Kupiec (POF) y su p-value con chi² de 1 g.l."""
        x = excepciones
        if n == 0:
            return 0.0, 1.0
        pi = x / n
        # log-verosimilitud bajo H0 (tasa = p) y bajo la tasa observada pi
        ll_h0 = (n - x) * np.log(1 - p) + (x * np.log(p) if x > 0 else 0.0)
        ll_h1 = ((n - x) * np.log(1 - pi) if x < n else 0.0) + (x * np.log(pi) if x > 0 else 0.0)
        lr = float(-2 * (ll_h0 - ll_h1))
        return lr, float(1 - stats.chi2.cdf(lr, df=1))

    def backtesting_kupiec(self, nivel: float | None = None, ventana: int = 250) -> dict:
        """Backtesting FUERA DE MUESTRA del VaR histórico.

        Para cada día t se calcula el VaR con los `ventana` días anteriores (sin
        mirar el día t) y se verifica si la pérdida real de t lo superó. Hacerlo
        dentro de muestra sería tramposo: el VaR histórico tiene, por
        construcción, casi exactamente el número esperado de excepciones.
        """
        nivel = self._nivel(nivel)
        p = 1 - nivel
        r = self.rendimientos
        ventana = min(ventana, max(60, len(r) // 2))
        if len(r) <= ventana + 20:
            return {"disponible": False, "motivo": "Se necesitan más datos para el backtesting."}

        var_movil = r.rolling(ventana).quantile(p).shift(1)  # sólo información pasada
        datos = pd.DataFrame({"r": r, "var": var_movil}).dropna()
        exc = datos["r"] < datos["var"]
        x, n = int(exc.sum()), int(len(datos))
        lr, p_value = self._kupiec(x, n, p)

        # Zonas tipo semáforo de Basilea, adaptadas al nivel elegido mediante la
        # distribución binomial de las excepciones (verde < 95 %, rojo >= 99.99 %)
        acumulada = stats.binom.cdf(x, n, p)
        zona = "verde" if acumulada < 0.95 else ("amarilla" if acumulada < 0.9999 else "roja")

        return {
            "disponible": True,
            "ventana": ventana,
            "excepciones": x,
            "excepciones_esperadas": round(n * p, 1),
            "n": n,
            "p_esperado": round(p, 4),
            "p_observado": round(x / n, 4),
            "estadistico_lr": round(lr, 4),
            "p_value": round(p_value, 4),
            "aprobado": p_value > 0.05,
            "zona": zona,
        }

    # ────────────────────────────── GARCH ───────────────────────────────────
    @staticmethod
    def _persistencia(nombre: str, params: pd.Series) -> float:
        alpha = params.filter(like="alpha").sum()
        beta = params.filter(like="beta").sum()
        gamma = params.filter(like="gamma").sum()
        if nombre.startswith("EGARCH"):
            return float(beta)                     # en EGARCH la persistencia es beta
        if nombre.startswith("GJR"):
            return float(alpha + gamma / 2 + beta)  # el choque negativo pesa alpha+gamma
        return float(alpha + beta)

    @staticmethod
    def _arch_lm(residuos_std: np.ndarray, rezagos: int = 5) -> dict:
        """Test ARCH-LM de Engle sobre los residuos estandarizados al cuadrado.
        H0: no queda heterocedasticidad condicional (el modelo capturó la volatilidad).
        """
        e2 = residuos_std ** 2
        y = e2[rezagos:]
        X = np.column_stack([np.ones(len(y))] + [e2[rezagos - i:-i] for i in range(1, rezagos + 1)])
        coef, *_ = np.linalg.lstsq(X, y, rcond=None)
        ajuste = X @ coef
        sst = np.sum((y - y.mean()) ** 2)
        r2 = 1 - np.sum((y - ajuste) ** 2) / sst if sst > 0 else 0.0
        lm = len(y) * r2
        p_value = float(1 - stats.chi2.cdf(lm, df=rezagos))
        return {"estadistico": round(float(lm), 4), "p_value": round(p_value, 4),
                "rezagos": rezagos, "sin_efectos_arch": p_value > 0.05}

    def garch(self) -> dict:
        """Ajusta varias especificaciones y elige la de menor AIC.

        * GARCH(p,q): la varianza depende de choques pasados (alpha) y de la
          varianza pasada (beta).
        * GJR-GARCH: agrega gamma, que permite que las caídas aumenten más la
          volatilidad que las subidas (efecto apalancamiento).
        * EGARCH: modela el logaritmo de la varianza (siempre positiva) y
          también captura asimetría.
        """
        from arch import arch_model

        # Escalar a % mejora la convergencia numérica del optimizador
        r_pct = self.rendimientos * 100
        especificaciones = {
            "GARCH(1,1)": dict(vol="GARCH", p=1, q=1),
            "GARCH(1,2)": dict(vol="GARCH", p=1, q=2),
            "GARCH(2,1)": dict(vol="GARCH", p=2, q=1),
            "GARCH(2,2)": dict(vol="GARCH", p=2, q=2),
            "GJR-GARCH(1,1)": dict(vol="GARCH", p=1, o=1, q=1),
            "EGARCH(1,1)": dict(vol="EGARCH", p=1, o=1, q=1),
        }
        modelos = {}
        for nombre, kw in especificaciones.items():
            try:
                res = arch_model(r_pct, mean="Constant", dist="normal", **kw).fit(disp="off")
                if np.isfinite(res.aic):
                    modelos[nombre] = res
            except Exception as e:  # noqa: BLE001
                logger.debug(f"{nombre} no convergió: {e}")

        if not modelos:
            return {"error": "No se pudo ajustar ningún modelo GARCH"}

        mejor_nombre = min(modelos, key=lambda k: modelos[k].aic)
        mejor = modelos[mejor_nombre]
        persistencia = self._persistencia(mejor_nombre, mejor.params)

        # Pronóstico de volatilidad 1, 5 y 21 días adelante (anualizada)
        try:
            pron = mejor.forecast(horizon=21, reindex=False).variance.values[-1]  # en %²
        except ValueError:
            # EGARCH no tiene pronóstico analítico a más de 1 día -> simulación
            pron = mejor.forecast(horizon=21, reindex=False, method="simulation",
                                  simulations=1000).variance.values[-1]
        vol_1d = float(np.sqrt(pron[0]) / 100)
        vol_21d_prom = float(np.sqrt(pron.mean()) / 100)

        # Volatilidad de largo plazo (a la que revierte) y vida media de un choque
        omega = float(mejor.params.get("omega", np.nan))
        if mejor_nombre.startswith("EGARCH"):
            vol_lp = float(np.sqrt(np.exp(omega / (1 - persistencia))) / 100) if persistencia < 1 else None
        else:
            vol_lp = float(np.sqrt(omega / (1 - persistencia)) / 100) if 0 < persistencia < 1 else None
        vida_media = float(np.log(0.5) / np.log(persistencia)) if 0 < persistencia < 1 else None

        z = (mejor.resid / mejor.conditional_volatility).dropna().values
        tabla = [{"modelo": k, "aic": round(float(v.aic), 4), "bic": round(float(v.bic), 4),
                  "loglik": round(float(v.loglikelihood), 4),
                  "persistencia": round(self._persistencia(k, v.params), 4)}
                 for k, v in modelos.items()]

        serie_vol = (mejor.conditional_volatility / 100 * np.sqrt(DIAS_ANIO))
        return {
            "mejor_modelo": mejor_nombre,
            "orden": mejor_nombre,
            "aic": round(float(mejor.aic), 4),
            "bic": round(float(mejor.bic), 4),
            # volatilidad_actual: diaria (compatibilidad); las *_anual son las que se interpretan
            "volatilidad_actual": round(float(mejor.conditional_volatility.iloc[-1] / 100), 6),
            "volatilidad_actual_anual": round(float(mejor.conditional_volatility.iloc[-1] / 100 * np.sqrt(DIAS_ANIO)), 4),
            "pronostico_1d_anual": round(vol_1d * np.sqrt(DIAS_ANIO), 4),
            "pronostico_21d_anual": round(vol_21d_prom * np.sqrt(DIAS_ANIO), 4),
            "volatilidad_largo_plazo_anual": round(vol_lp * np.sqrt(DIAS_ANIO), 4) if vol_lp else None,
            "persistencia": round(persistencia, 4),
            "vida_media_dias": round(vida_media, 1) if vida_media else None,
            "parametros": {k: round(float(v), 6) for k, v in mejor.params.items()},
            "arch_lm": self._arch_lm(z),
            "tabla_comparativa": tabla,
            "serie_volatilidad": [{"fecha": str(f.date()), "vol_anual": round(float(v), 6)}
                                  for f, v in serie_vol.items()],
        }

    # ────────────────────────────── resumen ─────────────────────────────────
    def resumen_var(self, nivel: float | None = None, horizonte: int = 1) -> dict:
        nivel = self._nivel(nivel)
        return {
            "nivel_confianza": nivel,
            "horizonte_dias": horizonte,
            "var_parametrico": self.var_parametrico(nivel, horizonte),
            "var_cornish_fisher": self.var_cornish_fisher(nivel, horizonte),
            "var_historico": self.var_historico(nivel, horizonte),
            "var_montecarlo": self.var_montecarlo(nivel, horizonte=horizonte),
            "cvar": self.cvar(nivel, horizonte),
            "cvar_parametrico": self.cvar_parametrico(nivel, horizonte),
            "volatilidad_anual": self.volatilidad_historica(),
            "kupiec": self.backtesting_kupiec(nivel),
        }
