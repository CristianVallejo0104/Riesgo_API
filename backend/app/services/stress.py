"""
Stress testing del portafolio.

Dos familias de escenarios:

1. HIPOTÉTICOS (¿qué pasaría si...?). Se traslada un choque del mercado a cada
   activo a través de su beta:  impacto_i = beta_i * choque_mercado.
   Además se estresan la volatilidad y las correlaciones.
2. HISTÓRICOS. Se buscan, dentro del período analizado, el peor día, la peor
   semana y el peor mes que realmente vivió el portafolio, y se reporta qué le
   pasó a cada activo en esas mismas fechas.

Todos los impactos son rendimientos simples (−0.10 = −10 % del valor).
"""
import logging

import numpy as np
import pandas as pd
from scipy import stats

logger = logging.getLogger(__name__)

DIAS_ANIO = 252


class StressService:

    def __init__(self, rendimientos: pd.DataFrame, rend_mercado: pd.Series | None = None,
                 pesos: np.ndarray | None = None):
        """`rendimientos`: rendimientos SIMPLES diarios de los activos.
        `rend_mercado`: rendimientos simples del benchmark (para las betas).
        `pesos`: vector de pesos (si no se da, pesos iguales)."""
        self.rendimientos = rendimientos
        n = rendimientos.shape[1]
        self.pesos = np.full(n, 1 / n) if pesos is None else np.asarray(pesos, dtype=float)
        self.tickers = list(rendimientos.columns)

        if rend_mercado is not None:
            datos = rendimientos.join(rend_mercado.rename("_mkt"), how="inner").dropna()
            mkt = datos["_mkt"]
            self.betas = {t: float(datos[t].cov(mkt) / mkt.var()) if mkt.var() > 0 else 1.0
                          for t in self.tickers}
            self.fuente_beta = "benchmark"
        else:
            # Sin benchmark se usa el promedio del propio portafolio como proxy del mercado
            proxy = rendimientos.mean(axis=1)
            self.betas = {t: float(rendimientos[t].cov(proxy) / proxy.var()) if proxy.var() > 0 else 1.0
                          for t in self.tickers}
            self.fuente_beta = "proxy_portafolio"

    def _resultado(self, nombre, tipo, descripcion, impactos: dict, extra: dict | None = None) -> dict:
        impacto_port = float(sum(self.pesos[i] * impactos[t] for i, t in enumerate(self.tickers)))
        out = {
            "escenario": nombre,
            "tipo": tipo,
            "descripcion": descripcion,
            "impacto_portafolio": round(impacto_port, 4),
            "impactos_por_activo": {t: round(float(v), 4) for t, v in impactos.items()},
        }
        if extra:
            out.update(extra)
        return out

    def stress_test(self) -> list[dict]:
        resultados = []
        R = self.rendimientos
        cov = R.cov().values
        sig = np.sqrt(np.diag(cov))
        w = self.pesos
        z99 = stats.norm.ppf(0.99)
        h = 10  # horizonte regulatorio de Basilea: 10 días

        # ── 1. Choques de mercado vía beta ──
        for nombre, choque, desc in [
            ("Corrección de mercado (−10 %)", -0.10,
             "El índice de referencia cae 10 %, algo que ocurre en promedio cada 1–2 años."),
            ("Mercado bajista (−20 %)", -0.20,
             "Caída de 20 %: definición clásica de 'bear market' (p. ej. 2022)."),
            ("Crash tipo COVID-19 (−34 %)", -0.34,
             "Caída similar a la del S&P 500 entre feb. y mar. de 2020."),
        ]:
            impactos = {t: max(self.betas[t] * choque, -1.0) for t in self.tickers}
            resultados.append(self._resultado(nombre, "mercado", desc, impactos,
                                              {"magnitud": choque}))

        # ── 2. Volatilidad x2: VaR 99 % a 10 días con la volatilidad duplicada ──
        impactos = {t: max(z99 * -2 * sig[i] * np.sqrt(h), -1.0) for i, t in enumerate(self.tickers)}
        vol_port_2x = 2 * float(np.sqrt(w @ cov @ w))
        resultados.append(self._resultado(
            "Volatilidad se duplica", "volatilidad",
            "Pérdida al 99 % en 10 días si la volatilidad diaria de todo el mercado se duplica.",
            impactos, {"magnitud": 2.0, "impacto_portafolio_diversificado":
                       round(max(-z99 * vol_port_2x * np.sqrt(h), -1.0), 4)}))

        # ── 3. Correlaciones -> 1 (se pierde la diversificación) ──
        vol_sin_div = float(np.abs(w) @ sig)
        vol_actual = float(np.sqrt(w @ cov @ w))
        perdida_corr = max(-z99 * vol_sin_div * np.sqrt(h), -1.0)
        impactos = {t: max(-z99 * sig[i] * np.sqrt(h), -1.0) for i, t in enumerate(self.tickers)}
        res = self._resultado(
            "Correlaciones se van a 1", "correlacion",
            "En crisis todos los activos tienden a caer juntos. Pérdida al 99 % en 10 días "
            "si la diversificación desaparece por completo.", impactos, {"magnitud": 1.0})
        res["impacto_portafolio"] = round(perdida_corr, 4)
        res["impacto_con_correlacion_actual"] = round(max(-z99 * vol_actual * np.sqrt(h), -1.0), 4)
        resultados.append(res)

        # ── 4. Históricos: peores ventanas reales del portafolio ──
        rp = pd.Series(R.values @ w, index=R.index)
        for dias, nombre in [(1, "Peor día observado"), (5, "Peor semana observada"),
                             (21, "Peor mes observado")]:
            if len(rp) <= dias:
                continue
            # rendimiento compuesto en ventanas móviles de `dias`
            acum_p = (1 + rp).rolling(dias).apply(np.prod, raw=True) - 1
            fin = acum_p.idxmin()
            pos_fin = R.index.get_loc(fin)
            ventana = R.iloc[pos_fin - dias + 1: pos_fin + 1]
            impactos = {t: float((1 + ventana[t]).prod() - 1) for t in self.tickers}
            inicio = ventana.index[0]
            res = self._resultado(
                nombre, "historico",
                f"Lo que realmente pasó entre {inicio.date()} y {fin.date()} dentro del período analizado.",
                impactos, {"fecha_inicio": str(inicio.date()), "fecha_fin": str(fin.date()),
                           "magnitud": dias})
            res["impacto_portafolio"] = round(float(acum_p.min()), 4)
            resultados.append(res)

        return resultados
