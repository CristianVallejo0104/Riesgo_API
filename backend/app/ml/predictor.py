import logging

import joblib
import numpy as np

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_modelo = None


def cargar_modelo():
    global _modelo
    if _modelo is None:
        try:
            _modelo = joblib.load(settings.ml_model_path)
            logger.info("Modelo ML cargado en memoria")
        except FileNotFoundError:
            logger.warning("Modelo no encontrado. Entrénalo primero.")
            _modelo = None
    return _modelo


def predecir(features: dict) -> float:
    modelo = cargar_modelo()
    if modelo is None:
        raise ValueError("Modelo no disponible")

    X = np.array([[features[f"retorno_lag{i}"] for i in range(1, 6)]])
    prediccion = modelo.predict(X)[0]
    probabilidad = modelo.predict_proba(X)[0]

    return {
        "prediccion": int(prediccion),
        "direccion": "sube" if prediccion == 1 else "baja",
        "probabilidad": round(float(max(probabilidad)), 4),
    }