"""Pruebas de integración de los endpoints de análisis con precios sintéticos en BD."""
import numpy as np
import pandas as pd
import pytest

from app.models.db_models import Asset, Price
from tests.conftest import SessionTest

TICKERS = ["AAA", "BBB", "CCC"]
BENCH = "^MKT"


@pytest.fixture
def client_con_datos(client):
    rng = np.random.default_rng(7)
    fechas = pd.bdate_range("2022-01-03", periods=700)
    mercado = rng.normal(0.0004, 0.01, len(fechas))
    series = {BENCH: mercado}
    for i, t in enumerate(TICKERS):
        beta = [1.4, 0.9, 0.5][i]
        series[t] = 0.0001 + beta * mercado + rng.normal(0, 0.008, len(fechas))

    db = SessionTest()
    for t, r in series.items():
        a = Asset(ticker=t, nombre=t, sector="Test", moneda="USD")
        db.add(a)
        db.flush()
        precios = 100 * np.cumprod(1 + r)
        for f, p in zip(fechas, precios):
            db.add(Price(asset_id=a.id, fecha=f.date(), open=p, high=p * 1.01,
                         low=p * 0.99, close=p, volume=1e6))
    db.commit()
    db.close()
    return client


def test_var_respeta_nivel(client_con_datos):
    r95 = client_con_datos.get("/analisis/var/AAA", params={"nivel": 0.95}).json()
    r99 = client_con_datos.get("/analisis/var/AAA", params={"nivel": 0.99}).json()
    assert r99["var_historico"] < r95["var_historico"]
    assert r95["kupiec"]["disponible"]


def test_markowitz_y_pesos(client_con_datos):
    d = client_con_datos.get("/analisis/markowitz",
                             params={"tickers": TICKERS, "rf": 0.03}).json()
    assert d["maximo_sharpe"]["sharpe_ratio"] >= d["minima_varianza"]["sharpe_ratio"] - 1e-6
    assert d["minima_varianza"]["riesgo_anual"] <= d["maximo_sharpe"]["riesgo_anual"] + 1e-6
    assert len(d["frontera"]) > 5


def test_var_portafolio_usa_pesos(client_con_datos):
    concentrado = client_con_datos.get("/analisis/var-portafolio", params={
        "tickers": TICKERS, "pesos": [1.0, 0.0, 0.0]}).json()
    defensivo = client_con_datos.get("/analisis/var-portafolio", params={
        "tickers": TICKERS, "pesos": [0.0, 0.0, 1.0]}).json()
    # AAA (beta 1.4) es más riesgoso que CCC (beta 0.5)
    assert concentrado["var_parametrico_portafolio"] < defensivo["var_parametrico_portafolio"]


def test_capm_recupera_betas(client_con_datos):
    d = client_con_datos.get("/analisis/capm", params={
        "tickers": TICKERS, "benchmark": BENCH, "tasa_libre_riesgo": 0.03}).json()
    betas = {a["ticker"]: a["beta"] for a in d["activos"]}
    assert betas["AAA"] == pytest.approx(1.4, abs=0.15)
    assert betas["CCC"] == pytest.approx(0.5, abs=0.15)


def test_stress_y_resumen(client_con_datos):
    s = client_con_datos.get("/analisis/stress-test",
                             params={"tickers": TICKERS, "benchmark": BENCH}).json()
    assert s["fuente_beta"] == "benchmark"
    assert len(s["escenarios"]) >= 7
    r = client_con_datos.get("/analisis/resumen-portafolio",
                             params={"tickers": TICKERS, "benchmark": BENCH}).json()
    assert r["max_drawdown"] <= 0
    assert r["cvar_historico"] <= r["var_historico"]
    assert "beta" in r


def test_garch_y_ewma(client_con_datos):
    g = client_con_datos.get("/analisis/garch/AAA").json()
    assert "mejor_modelo" in g and g["volatilidad_actual_anual"] > 0
    e = client_con_datos.get("/analisis/ewma/AAA").json()
    assert 0 < e["volatilidad_ewma"] < 2
