from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.dependencies import DBSession
from app.models.db_models import Asset, Price, PredictionLog
from app.ml.predictor import predecir
from app.ml.train import entrenar_modelo
from app.services.data import DataService

import numpy as np
import pandas as pd


router = APIRouter(prefix="/ml", tags=["Machine Learning"])


@router.post("/entrenar/{ticker}")
def entrenar(ticker: str, db: DBSession):
    servicio = DataService(db)
    precios = servicio.descargar_precios(ticker)
    if not precios:
        raise HTTPException(status_code=404, detail=f"No hay datos para {ticker}")

    closes = pd.Series([p.close for p in precios])
    rendimientos = np.log(closes / closes.shift(1)).dropna()

    resultado = entrenar_modelo(rendimientos)
    return {"ticker": ticker, **resultado}


@router.post("/predecir/{ticker}")
def hacer_prediccion(ticker: str, db: DBSession):
    servicio = DataService(db)
    precios = servicio.descargar_precios(ticker)
    if len(precios) < 6:
        raise HTTPException(status_code=400, detail="Se necesitan al menos 6 precios")

    closes = [p.close for p in precios[-6:]]
    rendimientos = [np.log(closes[i] / closes[i - 1]) for i in range(1, len(closes))]

    features = {f"retorno_lag{i}": rendimientos[-(i)] for i in range(1, 6)}
    resultado = predecir(features)

    log = PredictionLog(
        ticker=ticker,
        features=features,
        prediccion=float(resultado["prediccion"]),
        modelo_version="v1",
    )
    db.add(log)
    db.commit()

    return {"ticker": ticker, **resultado}