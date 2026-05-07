import logging

import numpy as np
import pandas as pd
from scipy import stats

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

class RiskService:

    def __init__(self, precios: pd.DataFrame):
        self.precios = precios
        self.rendimientos = np.log(precios["close"] / precios["close"].shift(1)).dropna()

    def volatilidad_ewma(self, lambd: float = None) -> float:
        if lambd is None:
            lambd = settings.ewma_lambda
        pesos = np.array([(1 - lambd) * lambd ** i for i in range(len(self.rendimientos))])
        pesos = pesos[::-1]
        pesos = pesos / pesos.sum()
        varianza = np.sum(pesos * self.rendimientos ** 2)
        return float(np.sqrt(varianza * 252))
    
    def var_parametrico(self, nivel: float = None) -> float:
        if nivel is None:
            nivel = settings.var_confidence_level
        media = self.rendimientos.mean()
        std = self.rendimientos.std()
        z = stats.norm.ppf(1 - nivel)
        return float(media + z * std)

    def var_historico(self, nivel: float = None) -> float:
        if nivel is None:
            nivel = settings.var_confidence_level
        return float(np.percentile(self.rendimientos, (1 - nivel) * 100))

    def var_montecarlo(self, nivel: float = None, n_sim: int = None) -> float:
        if nivel is None:
            nivel = settings.var_confidence_level
        if n_sim is None:
            n_sim = settings.montecarlo_simulations
        media = self.rendimientos.mean()
        std = self.rendimientos.std()
        simulados = np.random.normal(media, std, n_sim)
        return float(np.percentile(simulados, (1 - nivel) * 100))
    
    def cvar(self, nivel: float = None) -> float:
        if nivel is None:
            nivel = settings.var_confidence_level
        var = self.var_historico(nivel)
        return float(self.rendimientos[self.rendimientos <= var].mean())

    def backtesting_kupiec(self, nivel: float = None) -> dict:
        if nivel is None:
            nivel = settings.var_confidence_level
        var = self.var_historico(nivel)
        excepciones = int((self.rendimientos < var).sum())
        n = len(self.rendimientos)
        p_esperado = 1 - nivel
        p_observado = excepciones / n

        if p_observado == 0 or p_observado == 1:
            return {"excepciones": excepciones, "n": n, "p_value": 0.0, "aprobado": False}

        lr = -2 * (
            excepciones * np.log(p_esperado / p_observado)
            + (n - excepciones) * np.log((1 - p_esperado) / (1 - p_observado))
        )
        p_value = float(1 - stats.chi2.cdf(lr, df=1))

        return {
            "excepciones": excepciones,
            "n": n,
            "p_esperado": round(p_esperado, 4),
            "p_observado": round(p_observado, 4),
            "estadistico_lr": round(float(lr), 4),
            "p_value": round(p_value, 4),
            "aprobado": p_value > 0.05,
        }
    
    def garch(self) -> dict:
        from arch import arch_model

        rendimientos_pct = self.rendimientos * 100
        mejor_aic = np.inf
        mejor_modelo = None
        mejor_orden = (1, 1)

        for p in [1, 2]:
            for q in [1, 2]:
                try:
                    modelo = arch_model(rendimientos_pct, vol="Garch", p=p, q=q)
                    resultado = modelo.fit(disp="off")
                    if resultado.aic < mejor_aic:
                        mejor_aic = resultado.aic
                        mejor_modelo = resultado
                        mejor_orden = (p, q)
                except Exception:
                    continue

        if mejor_modelo is None:
            return {"error": "No se pudo ajustar GARCH"}

        return {
            "orden": f"GARCH{mejor_orden}",
            "aic": round(float(mejor_modelo.aic), 4),
            "bic": round(float(mejor_modelo.bic), 4),
            "volatilidad_actual": round(float(mejor_modelo.conditional_volatility.iloc[-1] / 100), 6),
            "persistencia": round(float(mejor_modelo.params.filter(like="alpha").sum() + mejor_modelo.params.filter(like="beta").sum()), 4),
        }
    
    
    def capm(self, rendimientos_benchmark: pd.Series) -> dict:
        rendimientos_activo = self.rendimientos.copy()
        
        # Alinear las fechas de ambos
        comunes = rendimientos_activo.index.intersection(rendimientos_benchmark.index)
        ra = rendimientos_activo.loc[comunes]
        rb = rendimientos_benchmark.loc[comunes]

        beta, alpha, r_value, p_value, std_err = stats.linregress(rb, ra)

        rf_diario = 0.04 / 252  # Tasa libre de riesgo aproximada
        retorno_mercado = float(rb.mean() * 252)
        retorno_esperado = rf_diario * 252 + beta * (retorno_mercado - rf_diario * 252)

        return {
            "beta": round(float(beta), 4),
            "alpha_jensen": round(float(alpha * 252), 6),
            "r_cuadrado": round(float(r_value ** 2), 4),
            "retorno_esperado_anual": round(float(retorno_esperado), 4),
        }
    
    def garch(self) -> dict:
        from arch import arch_model

        rendimientos_pct = self.rendimientos * 100
        modelos = {}

        # GARCH(1,1), GARCH(1,2), GARCH(2,1), GARCH(2,2)
        for p in [1, 2]:
            for q in [1, 2]:
                try:
                    m = arch_model(rendimientos_pct, vol="Garch", p=p, q=q)
                    r = m.fit(disp="off")
                    modelos[f"GARCH({p},{q})"] = r
                except: continue

        # EGARCH(1,1)
        try:
            m = arch_model(rendimientos_pct, vol="EGARCH", p=1, q=1)
            r = m.fit(disp="off")
            modelos["EGARCH(1,1)"] = r
        except: pass

        # GJR-GARCH(1,1)
        try:
            m = arch_model(rendimientos_pct, vol="GARCH", p=1, o=1, q=1)
            r = m.fit(disp="off")
            modelos["GJR-GARCH(1,1)"] = r
        except: pass

        if not modelos:
            return {"error": "No se pudo ajustar ningún modelo"}

        # Selección por AIC
        mejor_nombre = min(modelos, key=lambda k: modelos[k].aic)
        mejor = modelos[mejor_nombre]

        # Tabla comparativa
        tabla = [{"modelo": k, "aic": round(v.aic, 4), "bic": round(v.bic, 4),
                "loglik": round(v.loglikelihood, 4)} for k, v in modelos.items()]

        # Test ARCH-LM sobre residuos del mejor modelo
        from arch.unitroot import PhillipsPerron
        from scipy import stats
        residuos = mejor.resid / mejor.conditional_volatility
        _, arch_lm_pvalue = stats.normaltest(residuos.dropna())

        persistencia = float(mejor.params.filter(like="alpha").sum() +
                            mejor.params.filter(like="beta").sum())

        return {
            "mejor_modelo": mejor_nombre,
            "aic": round(float(mejor.aic), 4),
            "bic": round(float(mejor.bic), 4),
            "volatilidad_actual": round(float(mejor.conditional_volatility.iloc[-1] / 100), 6),
            "persistencia": round(persistencia, 4),
            "tabla_comparativa": tabla,
            "orden": mejor_nombre,
        }
