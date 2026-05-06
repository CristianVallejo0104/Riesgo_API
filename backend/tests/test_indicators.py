import numpy as np
import pandas as pd
from app.services.data import TechnicalIndicators


def test_rsi_entre_0_y_100():
    closes = pd.Series(np.random.uniform(100, 200, 100))
    df = pd.DataFrame({"close": closes, "high": closes + 1, "low": closes - 1})
    indicadores = TechnicalIndicators(df)
    rsi = indicadores.rsi().dropna()
    assert rsi.min() >= 0
    assert rsi.max() <= 100


def test_bollinger_upper_mayor_que_lower():
    closes = pd.Series(np.random.uniform(100, 200, 50))
    df = pd.DataFrame({"close": closes, "high": closes + 1, "low": closes - 1})
    indicadores = TechnicalIndicators(df)
    boll = indicadores.bollinger()
    datos = pd.DataFrame({"upper": boll["upper"], "lower": boll["lower"]}).dropna()
    assert (datos["upper"] >= datos["lower"]).all()