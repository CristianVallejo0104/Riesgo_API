import logging
import joblib
import json
import numpy as np
import pandas as pd
from datetime import datetime
from pathlib import Path
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.metrics import accuracy_score, precision_score, recall_score
from xgboost import XGBClassifier

logger = logging.getLogger(__name__)

MODELOS_DISPONIBLES = {
    "Random Forest": RandomForestClassifier(random_state=42),
    "XGBoost": XGBClassifier(random_state=42, eval_metric="logloss", verbosity=0),
    "Logistic Regression": LogisticRegression(random_state=42, max_iter=1000),
}

HIPERPARAMETROS = {
    "Random Forest": {
        "n_estimators": [50, 100, 200],
        "max_depth": [3, 5, 10, None],
    },
    "XGBoost": {
        "n_estimators": [50, 100, 200],
        "max_depth": [3, 5, 7],
        "learning_rate": [0.05, 0.1, 0.2],
    },
    "Logistic Regression": {
        "C": [0.1, 1.0, 10.0],
    },
}

META_PATH = "app/ml/model_meta.json"


def _cargar_meta() -> dict:
    """Carga metadatos del modelo — fecha de entrenamiento y accuracy."""
    try:
        if Path(META_PATH).exists():
            with open(META_PATH, "r") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _guardar_meta(meta: dict):
    """Guarda metadatos del modelo."""
    try:
        Path(META_PATH).parent.mkdir(parents=True, exist_ok=True)
        with open(META_PATH, "w") as f:
            json.dump(meta, f, indent=2)
    except Exception as e:
        logger.warning(f"No se pudo guardar meta: {e}")


def necesita_reentrenamiento(dias: int = 8) -> bool:
    """Verifica si han pasado más de N días desde el último entrenamiento."""
    meta = _cargar_meta()
    if not meta.get("fecha_entrenamiento"):
        return True
    ultima = datetime.fromisoformat(meta["fecha_entrenamiento"])
    diferencia = (datetime.now() - ultima).days
    logger.info(f"Días desde último entrenamiento: {diferencia}")
    return diferencia >= dias


def entrenar_modelo(
    rendimientos: pd.Series,
    ruta_salida: str = "app/ml/model.joblib",
    optimizar_hiperparametros: bool = True,
    forzar: bool = False,
):
    """
    Entrena y compara Random Forest, XGBoost y Logistic Regression.
    Selecciona automáticamente el mejor por accuracy.
    Reentrenar solo si han pasado 8 días — a menos que forzar=True.
    """
    # Verificar si necesita reentrenamiento
    if not forzar and not necesita_reentrenamiento():
        meta = _cargar_meta()
        logger.info("Modelo vigente — no necesita reentrenamiento.")
        return {
            "mensaje": "Modelo vigente",
            "dias_desde_entrenamiento": (
                datetime.now() - datetime.fromisoformat(meta["fecha_entrenamiento"])
            ).days,
            **meta,
        }

    # Preparar features
    df = pd.DataFrame({"retorno": rendimientos})
    for i in range(1, 6):
        df[f"retorno_lag{i}"] = df["retorno"].shift(i)
    df["target"] = (df["retorno"].shift(-1) > 0).astype(int)
    df = df.dropna()

    X = df[[f"retorno_lag{i}" for i in range(1, 6)]]
    y = df["target"]

    # shuffle=False para evitar leakage temporal
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, shuffle=False
    )

    # Entrenar y comparar modelos
    resultados = {}
    mejores_modelos = {}

    for nombre, modelo_base in MODELOS_DISPONIBLES.items():
        try:
            if optimizar_hiperparametros and nombre in HIPERPARAMETROS:
                grid = GridSearchCV(
                    modelo_base,
                    HIPERPARAMETROS[nombre],
                    cv=3,
                    scoring="accuracy",
                    n_jobs=-1,
                )
                grid.fit(X_train, y_train)
                modelo_final = grid.best_estimator_
                mejores_params = grid.best_params_
            else:
                modelo_base.fit(X_train, y_train)
                modelo_final = modelo_base
                mejores_params = {}

            y_pred = modelo_final.predict(X_test)
            acc = accuracy_score(y_test, y_pred)
            prec = precision_score(y_test, y_pred, zero_division=0)
            rec = recall_score(y_test, y_pred, zero_division=0)

            resultados[nombre] = {
                "accuracy": round(acc, 4),
                "precision": round(prec, 4),
                "recall": round(rec, 4),
                "mejores_params": mejores_params,
            }
            mejores_modelos[nombre] = modelo_final
            logger.info(f"{nombre} — Accuracy: {acc:.4f}")

        except Exception as e:
            logger.warning(f"Error entrenando {nombre}: {e}")

    if not resultados:
        raise ValueError("Ningún modelo pudo entrenarse correctamente.")

    # Seleccionar el mejor por accuracy
    mejor_nombre = max(resultados, key=lambda k: resultados[k]["accuracy"])
    mejor_modelo = mejores_modelos[mejor_nombre]
    mejor_accuracy = resultados[mejor_nombre]["accuracy"]

    # Guardar el mejor modelo
    Path(ruta_salida).parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(mejor_modelo, ruta_salida)
    logger.info(f"Mejor modelo: {mejor_nombre} (accuracy={mejor_accuracy})")
    logger.info(f"Modelo guardado en {ruta_salida}")

    # Guardar metadatos
    meta = {
        "mejor_modelo": mejor_nombre,
        "accuracy": mejor_accuracy,
        "fecha_entrenamiento": datetime.now().isoformat(),
        "comparacion": resultados,
        "ruta": ruta_salida,
    }
    _guardar_meta(meta)

    return meta