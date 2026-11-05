"""
Pruebas de coherencia teórica: verifican propiedades que TODO cálculo de riesgo
correcto debe cumplir (no sólo que el código corra).
"""
import numpy as np
import pandas as pd
import pytest
from scipy import stats

from app.services.fixed_income import FixedIncomeService
from app.services.options import OptionsService
from app.services.portfolio import PortfolioService
from app.services.risk import RiskService
from app.services.stress import StressService


def _precios_normales(n=1000, mu=0.0003, sigma=0.01, semilla=0):
    rng = np.random.default_rng(semilla)
    r = rng.normal(mu, sigma, n)
    fechas = pd.bdate_range("2020-01-01", periods=n + 1)
    return pd.DataFrame({"close": 100 * np.exp(np.concatenate([[0], np.cumsum(r)]))}, index=fechas)


def _precios_colas_pesadas(n=1500, semilla=1):
    rng = np.random.default_rng(semilla)
    r = stats.t.rvs(3, scale=0.008, size=n, random_state=rng)
    fechas = pd.bdate_range("2020-01-01", periods=n + 1)
    return pd.DataFrame({"close": 100 * np.exp(np.concatenate([[0], np.cumsum(r)]))}, index=fechas)


# ─────────────────────────── VaR / CVaR ───────────────────────────

def test_var_mas_conservador_a_mayor_confianza():
    s = RiskService(_precios_normales())
    assert s.var_historico(0.99) < s.var_historico(0.95) < s.var_historico(0.90)
    assert s.var_parametrico(0.99) < s.var_parametrico(0.95)


def test_cvar_siempre_peor_que_var():
    s = RiskService(_precios_colas_pesadas())
    for nivel in (0.90, 0.95, 0.99):
        assert s.cvar(nivel) <= s.var_historico(nivel)
        assert s.cvar_parametrico(nivel) <= s.var_parametrico(nivel)


def test_var_parametrico_coincide_con_formula_teorica():
    s = RiskService(_precios_normales(n=20000, mu=0.0, sigma=0.01))
    assert s.var_parametrico(0.95) == pytest.approx(-1.645 * 0.01, rel=0.03)


def test_montecarlo_reproducible_y_captura_colas():
    df = _precios_colas_pesadas()
    v1 = RiskService(df).var_montecarlo(0.99)
    v2 = RiskService(df).var_montecarlo(0.99)
    assert v1 == v2  # semilla fija
    # Con colas pesadas, el VaR 99 % t-Student debe ser más extremo que el Normal
    assert v1 < RiskService(df).var_parametrico(0.99)


def test_cornish_fisher_penaliza_colas_pesadas():
    s = RiskService(_precios_colas_pesadas())
    assert s.var_cornish_fisher(0.99) < s.var_parametrico(0.99)


def test_var_escala_con_raiz_del_tiempo():
    s = RiskService(_precios_normales(mu=0.0))
    mu = s.rendimientos.mean()
    # quitando la deriva (mu*h), la parte de riesgo escala con sqrt(h)
    ratio = (s.var_parametrico(0.95, horizonte=10) - 10 * mu) / (s.var_parametrico(0.95, horizonte=1) - mu)
    assert ratio == pytest.approx(np.sqrt(10), rel=0.05)


def test_kupiec_fuera_de_muestra_aprueba_modelo_correcto():
    k = RiskService(_precios_normales(n=2000)).backtesting_kupiec(0.95)
    assert k["disponible"]
    assert k["aprobado"]
    assert abs(k["p_observado"] - 0.05) < 0.02


def test_kupiec_cero_excepciones_no_falla():
    lr, p = RiskService._kupiec(0, 250, 0.05)
    assert lr > 0 and 0 <= p < 0.05  # 0 excepciones en 250 días es sospechoso a 95 %


# ─────────────────────────── Volatilidad ───────────────────────────

def test_ewma_cercana_a_volatilidad_real():
    s = RiskService(_precios_normales(n=3000, sigma=0.01))
    assert s.volatilidad_ewma() == pytest.approx(0.01 * np.sqrt(252), rel=0.35)


def test_garch_estacionario_y_con_diagnosticos():
    g = RiskService(_precios_colas_pesadas()).garch()
    assert "error" not in g
    assert 0 <= g["persistencia"] < 1.05
    assert 0 <= g["arch_lm"]["p_value"] <= 1
    assert g["volatilidad_actual_anual"] > 0


# ─────────────────────────── Portafolio ───────────────────────────

def _rend_activos(semilla=3):
    rng = np.random.default_rng(semilla)
    medias = np.array([0.0008, 0.0004, 0.0002])
    vols = np.array([0.02, 0.012, 0.006])
    corr = np.array([[1, 0.3, 0.1], [0.3, 1, 0.2], [0.1, 0.2, 1]])
    cov = np.outer(vols, vols) * corr
    datos = rng.multivariate_normal(medias, cov, size=1500)
    return pd.DataFrame(datos, columns=["A", "B", "C"], index=pd.bdate_range("2019-01-01", periods=1500))


def test_max_sharpe_supera_a_min_varianza_y_a_pesos_iguales():
    s = PortfolioService(_rend_activos(), rf=0.03)
    ms, mv = s.maximo_sharpe(), s.minima_varianza()
    iguales = s.metricas(np.ones(3) / 3)
    assert ms["sharpe_ratio"] >= mv["sharpe_ratio"] - 1e-6
    assert ms["sharpe_ratio"] >= iguales["sharpe_ratio"] - 1e-6
    assert mv["riesgo_anual"] <= ms["riesgo_anual"] + 1e-6
    assert sum(ms["pesos"].values()) == pytest.approx(1, abs=1e-3)
    assert min(ms["pesos"].values()) >= -1e-4  # sin cortos


def test_frontera_solo_parte_eficiente():
    s = PortfolioService(_rend_activos())
    f = s.frontera_eficiente(15)
    riesgos = [p["riesgo"] for p in f]
    retornos = [p["retorno"] for p in f]
    # a más retorno, más riesgo (rama superior, monótona)
    assert all(np.diff(retornos) >= -1e-4)
    assert all(np.diff(riesgos) >= -1e-4)


def test_var_portafolio_diversificacion_y_euler():
    s = PortfolioService(_rend_activos())
    v = s.var_portafolio(np.ones(3) / 3, 0.95)
    # El VaR del portafolio es menos severo que la suma de VaR individuales (subaditividad)
    assert v["var_parametrico_portafolio"] >= v["suma_var_individuales"]
    assert v["beneficio_diversificacion"] >= 0
    # Las contribuciones de Euler suman el VaR total
    total = sum(c["var_componente"] for c in v["contribucion_por_activo"])
    assert total == pytest.approx(v["var_parametrico_portafolio"], rel=1e-3)
    assert v["cvar_historico_portafolio"] <= v["var_historico_portafolio"]


# ─────────────────────────── Stress ───────────────────────────

def test_stress_beta_y_correlacion():
    rend = _rend_activos()
    mercado = rend.mean(axis=1)
    esc = {e["escenario"]: e for e in StressService(rend, mercado).stress_test()}
    caida = esc["Mercado bajista (−20 %)"]
    # Portafolio con beta ~1 al mercado (que es su propio promedio) cae ~20 %
    assert caida["impacto_portafolio"] == pytest.approx(-0.20, abs=0.02)
    corr = esc["Correlaciones se van a 1"]
    assert corr["impacto_portafolio"] < corr["impacto_con_correlacion_actual"]
    assert {"Peor día observado", "Peor semana observada", "Peor mes observado"} <= set(esc)


# ─────────────────────────── Renta fija ───────────────────────────

def test_bono_a_la_par_y_duracion():
    fi = FixedIncomeService([1, 30], [5, 5])
    r = fi.duracion_y_convexidad(tasa_cupon=0.05, vencimiento=10, tasa_descuento=0.05)
    assert r["precio_bono"] == pytest.approx(100, abs=1e-6)        # cupón = tasa -> a la par
    assert r["duracion_macaulay"] == pytest.approx(8.1078, abs=1e-3)
    assert r["duracion_modificada"] == pytest.approx(8.1078 / 1.05, abs=1e-3)


def test_bono_usa_tasa_del_plazo_correcto():
    fi = FixedIncomeService([0.25, 2, 10, 30], [5.0, 4.0, 4.5, 4.8])
    assert fi.duracion_y_convexidad(vencimiento=2)["tasa_descuento"] == pytest.approx(0.04)


def test_convexidad_mejora_la_aproximacion():
    fi = FixedIncomeService([1, 30], [5, 5])
    for s in fi.sensibilidad_shocks(0.05, 100, 10, 0.05):
        if s["shock_bp"] != 0:
            assert abs(s["error_duracion_convexidad"]) <= abs(s["error_lineal"])


def test_nelson_siegel_ajusta_bien():
    plazos = [0.25, 1, 2, 5, 10, 30]
    tasas = list(FixedIncomeService._nelson_siegel(np.array(plazos), 4.5, -1.0, 0.5, 2.0))
    ns = FixedIncomeService(plazos, tasas).ajustar_nelson_siegel()
    assert ns["rmse_pb"] < 2


# ─────────────────────────── Opciones ───────────────────────────

def test_black_scholes_valor_conocido_y_paridad():
    o = OptionsService(100, 100, 1, 0.05, 0.2)
    bs = o.black_scholes()
    assert bs["call"] == pytest.approx(10.4506, abs=1e-3)
    assert bs["put"] == pytest.approx(5.5735, abs=1e-3)
    assert abs(bs["error_paridad_put_call"]) < 1e-6


def test_volatilidad_implicita_recupera_sigma():
    o = OptionsService(100, 110, 0.5, 0.03, 0.35)
    precio = o.black_scholes()["put"]
    assert o.volatilidad_implicita(precio, "put") == pytest.approx(0.35, abs=1e-4)
    assert o.volatilidad_implicita(1000, "call") is None  # viola no arbitraje
