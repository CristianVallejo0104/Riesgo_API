import numpy as np
import pandas as pd
from app.services.risk import RiskService


def test_var_parametrico_es_negativo():
    np.random.seed(42)
    closes = pd.Series(np.cumsum(np.random.normal(0, 1, 500)) + 100)
    df = pd.DataFrame({"close": closes})
    servicio = RiskService(df)
    var = servicio.var_parametrico()
    assert var < 0


def test_cvar_menor_que_var():
    np.random.seed(42)
    closes = pd.Series(np.cumsum(np.random.normal(0, 1, 500)) + 100)
    df = pd.DataFrame({"close": closes})
    servicio = RiskService(df)
    var = servicio.var_historico()
    cvar = servicio.cvar()
    assert cvar <= var