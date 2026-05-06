import logging
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score

logger = logging.getLogger(__name__)


def entrenar_modelo(rendimientos: pd.Series, ruta_salida: str = "app/ml/model.joblib"):
    df = pd.DataFrame({"retorno": rendimientos})

    # Features: retornos de los últimos 5 días
    for i in range(1, 6):
        df[f"retorno_lag{i}"] = df["retorno"].shift(i)

    # Target: si el retorno del día siguiente es positivo (1) o negativo (0)
    df["target"] = (df["retorno"].shift(-1) > 0).astype(int)

    df = df.dropna()

    X = df[[f"retorno_lag{i}" for i in range(1, 6)]]
    y = df["target"]

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    modelo = RandomForestClassifier(n_estimators=100, random_state=42)
    modelo.fit(X_train, y_train)

    accuracy = accuracy_score(y_test, modelo.predict(X_test))
    logger.info(f"Modelo entrenado. Accuracy: {accuracy:.4f}")

    joblib.dump(modelo, ruta_salida)
    logger.info(f"Modelo guardado en {ruta_salida}")

    return {"accuracy": round(accuracy, 4), "ruta": ruta_salida}