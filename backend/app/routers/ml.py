from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from app.dependencies import DBSession
from app.models.db_models import Asset, Price, PredictionLog
from app.ml.predictor import predecir, resetear_modelo
from app.ml.train import entrenar_modelo, necesita_reentrenamiento, _cargar_meta
from app.services.data import DataService

import numpy as np
import pandas as pd

router = APIRouter(prefix="/ml", tags=["Machine Learning"])


@router.post("/entrenar/{ticker}")
def entrenar(
    ticker: str,
    db: DBSession,
    optimizar: bool = Query(default=True, description="Optimizar hiperparámetros con GridSearchCV"),
    forzar: bool = Query(default=False, description="Forzar reentrenamiento aunque no hayan pasado 8 días"),
):
    servicio = DataService(db)
    precios = servicio.descargar_precios(ticker)
    if not precios:
        raise HTTPException(status_code=404, detail=f"No hay datos para {ticker}")

    closes = pd.Series([p.close for p in precios])
    rendimientos = np.log(closes / closes.shift(1)).dropna()

    resultado = entrenar_modelo(rendimientos, optimizar_hiperparametros=optimizar, forzar=forzar)

    # Resetear singleton para cargar el nuevo modelo
    resetear_modelo()

    return {"ticker": ticker, **resultado}


@router.post("/entrenar-todos")
def entrenar_todos(
    db: DBSession,
    optimizar: bool = Query(default=True),
    forzar: bool = Query(default=False),
):
    """Entrena el modelo con todos los tickers disponibles en la BD."""
    activos = db.scalars(select(Asset)).all()
    if not activos:
        raise HTTPException(status_code=404, detail="No hay activos en la BD")

    todos_rendimientos = []
    for activo in activos:
        precios = db.scalars(
            select(Price).where(Price.asset_id == activo.id).order_by(Price.fecha)
        ).all()
        if len(precios) > 10:
            closes = pd.Series([p.close for p in precios])
            rend = np.log(closes / closes.shift(1)).dropna()
            todos_rendimientos.append(rend)

    if not todos_rendimientos:
        raise HTTPException(status_code=400, detail="No hay suficientes datos")

    rendimientos_combined = pd.concat(todos_rendimientos, ignore_index=True)
    resultado = entrenar_modelo(rendimientos_combined, optimizar_hiperparametros=optimizar, forzar=forzar)
    resetear_modelo()

    return {"tickers": [a.ticker for a in activos], **resultado}


@router.get("/estado")
def estado_modelo():
    """Muestra el estado del modelo — fecha, accuracy y si necesita reentrenamiento."""
    meta = _cargar_meta()
    if not meta:
        return {
            "modelo_entrenado": False,
            "mensaje": "No hay modelo entrenado. Usa POST /ml/entrenar/{ticker}",
        }
    return {
        "modelo_entrenado": True,
        "mejor_modelo": meta.get("mejor_modelo"),
        "accuracy": meta.get("accuracy"),
        "fecha_entrenamiento": meta.get("fecha_entrenamiento"),
        "necesita_reentrenamiento": necesita_reentrenamiento(),
        "comparacion_modelos": meta.get("comparacion", {}),
    }


@router.post("/predecir/{ticker}")
def hacer_prediccion(ticker: str, db: DBSession):
    servicio = DataService(db)
    precios = servicio.descargar_precios(ticker)
    if len(precios) < 6:
        raise HTTPException(status_code=400, detail="Se necesitan al menos 6 precios")

    closes = [p.close for p in precios[-6:]]
    rendimientos = [np.log(closes[i] / closes[i - 1]) for i in range(1, len(closes))]
    features = {f"retorno_lag{i}": rendimientos[-(i)] for i in range(1, 6)}

    # Verificar si necesita reentrenamiento automático
    if necesita_reentrenamiento():
        closes_all = pd.Series([p.close for p in precios])
        rend_all = np.log(closes_all / closes_all.shift(1)).dropna()
        entrenar_modelo(rend_all, forzar=False)
        resetear_modelo()

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