# 📊 RiskLab USTA — Sistema Integral de Análisis de Riesgo Financiero

**Autores:** Cristian Vallejo  
**Curso:** Python para APIs e IA + Teoría del Riesgo — CIII  
**Universidad:** USTA

---

## 📋 Descripción

RiskLab USTA es una API REST de análisis de riesgo financiero construida con **FastAPI**, con persistencia en **SQLite** vía **SQLAlchemy ORM**, y un dashboard interactivo en **Streamlit**. Integra datos en tiempo real de **Yahoo Finance** y **FRED API**.

### Arquitectura en 5 Capas

```
Capa 1 — Datos y persistencia:   yfinance + FRED → SQLite (cache transparente)
Capa 2 — Análisis clásico:       Indicadores, Rendimientos, EWMA/GARCH, CAPM, VaR, Markowitz
Capa 3 — Renta fija y derivados: Nelson-Siegel, Duración, Black-Scholes, Stress Testing
Capa 4 — Machine Learning:       Random Forest → joblib → Singleton → /predict
Capa 5 — Infraestructura:        pytest + Docker + Render + GitHub Actions CI
```

```
Streamlit (8501) ──HTTP/JSON──► FastAPI (8000) ──► yfinance / FRED API
                                      │
                               SQLAlchemy ORM
                               SQLite (risklab.db)
                               Pydantic v2 (validación)
                               9 servicios de cálculo
```

---

## 🚀 Instalación local

### 1. Clonar el repositorio
```bash
git clone https://github.com/CristianVallejo0104/Riesgo_API.git
cd Riesgo_API
```

### 2. Crear entorno virtual
```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux/Mac
source .venv/bin/activate
```

### 3. Instalar dependencias
```bash
pip install -r backend/requirements.txt
```

### 4. Configurar variables de entorno
```bash
cp backend/.env.example backend/.env
# Editar backend/.env con tus API keys
```

---

## ⚙️ Variables de entorno

Crea el archivo `backend/.env` basándote en `.env.example`:

| Variable | Descripción | Dónde obtenerla |
|---|---|---|
| `FRED_API_KEY` | API Key de FRED | https://fred.stlouisfed.org/docs/api/api_key.html |
| `DATABASE_URL` | URL de SQLite | `sqlite:///./risklab.db` (por defecto) |
| `DEBUG` | Modo debug | `false` para producción |

---

## ▶️ Ejecutar el backend

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

- Swagger UI: http://localhost:8000/docs  
- ReDoc: http://localhost:8000/redoc  
- Health check: http://localhost:8000/health

---

## 🖥️ Ejecutar el frontend

En otra terminal (desde la raíz del proyecto):

```bash
streamlit run frontend/app.py
```

Dashboard disponible en: http://localhost:8501

---

## 🐳 Ejecutar con Docker

```bash
cd backend
docker build -t risklab-backend .
docker run -p 8000:8000 --env-file .env risklab-backend
```

O con docker-compose:

```bash
docker compose up
```

---

## 🧪 Ejecutar tests

```bash
cd backend
python -m pytest tests/ -v
```

Los tests usan una BD SQLite en memoria — no afectan los datos reales.

---

## 🤖 Entrenar el modelo ML

```bash
cd backend
python -m app.ml.train
```

**Propósito analítico:** El modelo predice la dirección del precio (sube/baja) al día siguiente usando los retornos logarítmicos de los últimos 5 días como features (lags). Se usa un `RandomForestClassifier` con 100 árboles entrenado con datos históricos de Yahoo Finance.

- **Features:** retorno_lag1, retorno_lag2, retorno_lag3, retorno_lag4, retorno_lag5
- **Target:** 1 si el retorno del día siguiente > 0, 0 si no
- **Métrica:** Accuracy en conjunto de test (80/20 split, shuffle=False para respetar orden temporal)
- **Serialización:** `joblib.dump()` → `app/ml/model.joblib`
- **Serving:** Patrón Singleton en `predictor.py` — el modelo se carga una sola vez al iniciar la app

---

## 📦 Activos seleccionados

| Ticker | Empresa | Sector | Justificación |
|---|---|---|---|
| **AAPL** | Apple Inc. | Tecnología | Mayor capitalización mundial. Beta ~1. |
| **JPM** | JPMorgan Chase | Financiero | Banco más grande de USA. Exposición al ciclo económico. |
| **JNJ** | Johnson & Johnson | Salud | Activo defensivo. Baja correlación con tecnología. |
| **XOM** | ExxonMobil | Energía | Diversificación con commodities. Correlación negativa en crisis. |
| **KO** | Coca-Cola | Consumo básico | Máxima estabilidad. Beta < 1. Ideal para reducir riesgo del portafolio. |

**Benchmark:** S&P 500 (^GSPC)

---

## 🌐 Deploy en Render

**URL pública del backend:** https://riesgo-api.onrender.com  
**Swagger UI:** https://riesgo-api.onrender.com/docs 
**ReDoc:** *(URL)/redoc*

### Pasos para deployar:
1. Crear cuenta en https://render.com
2. New → Web Service → conectar repositorio GitHub
3. Render detecta el `Dockerfile` automáticamente
4. Configurar variables de entorno en la UI de Render:
   - `FRED_API_KEY`
   - `DATABASE_URL=sqlite:///./risklab.db`
5. Cada push a `main` dispara redeploy automático

> **Nota:** El free tier de Render se duerme tras 15 min sin tráfico. El cold start toma ~30s. Hacer una llamada de calentamiento a `/health` antes de una demo.

---

## 📡 Endpoints principales

| Endpoint | Método | Descripción |
|---|---|---|
| `/health` | GET | Estado de la API |
| `/activos/` | GET/POST | Lista y crea activos |
| `/precios/{ticker}` | GET | Precios históricos con cache en BD |
| `/precios/descargar/{ticker}` | POST | Descarga y persiste precios |
| `/portafolios/` | GET/POST | CRUD de portafolios |
| `/analisis/rendimientos/{ticker}` | GET | Rendimientos y estadísticas |
| `/analisis/indicadores/{ticker}` | GET | SMA, EMA, RSI, MACD, Bollinger, Estocástico |
| `/analisis/ewma/{ticker}` | GET | Volatilidad EWMA |
| `/analisis/garch/{ticker}` | GET | GARCH/EGARCH/GJR-GARCH con selección AIC |
| `/analisis/var/{ticker}` | GET | VaR paramétrico, histórico, Monte Carlo + CVaR + Kupiec |
| `/analisis/capm` | GET | Beta, Alpha Jensen, clasificación |
| `/analisis/markowitz` | GET | Frontera eficiente con QP (cvxpy) |
| `/analisis/alertas` | GET | Señales de trading con persistencia |
| `/analisis/stress-test` | GET | Stress testing 4 escenarios |
| `/macro/` | GET | Tasa libre de riesgo + inflación FRED |
| `/macro/benchmark` | GET | Tracking Error, Information Ratio, Max Drawdown |
| `/renta-fija/curva` | GET | Curva Nelson-Siegel desde FRED |
| `/renta-fija/duracion` | GET | Duración Macaulay, modificada y convexidad |
| `/renta-fija/sensibilidad` | GET | Sensibilidad ante shocks ±50/±100/±200 pb |
| `/opciones/black-scholes` | GET | Black-Scholes + 5 Greeks |
| `/opciones/volatilidad-implicita` | GET | Volatilidad implícita Newton-Raphson |
| `/ml/entrenar/{ticker}` | POST | Entrenamiento offline del modelo |
| `/ml/predecir/{ticker}` | POST | Predicción con logging en BD |

---

## 🧱 Estructura del proyecto

```
Riesgo_API/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app, routers, lifespan
│   │   ├── config.py            # BaseSettings, .env
│   │   ├── dependencies.py      # Depends(): DBSession, SettingsDep
│   │   ├── database.py          # SQLAlchemy engine, session, get_db
│   │   ├── models/
│   │   │   ├── db_models.py     # ORM: Asset, Price, Portfolio, PredictionLog, SignalLog
│   │   │   └── schemas.py       # Pydantic request/response models
│   │   ├── services/
│   │   │   ├── data.py          # DataService + TechnicalIndicators
│   │   │   ├── risk.py          # VaR, CVaR, EWMA, GARCH, CAPM, Kupiec
│   │   │   ├── portfolio.py     # Markowitz QP (cvxpy)
│   │   │   ├── macro.py         # FRED API service
│   │   │   ├── fixed_income.py  # Nelson-Siegel, duración, convexidad
│   │   │   ├── options.py       # Black-Scholes, Greeks, vol. implícita
│   │   │   └── stress.py        # Stress testing 4 escenarios
│   │   ├── ml/
│   │   │   ├── train.py         # Entrenamiento offline
│   │   │   ├── predictor.py     # Singleton + predict
│   │   │   └── model.joblib     # Modelo serializado
│   │   └── routers/             # Endpoints por dominio
│   ├── tests/
│   │   ├── conftest.py          # BD en memoria + fixtures
│   │   ├── test_endpoints.py
│   │   ├── test_indicators.py
│   │   └── test_risk.py
│   ├── Dockerfile               # Multi-stage python:3.11.9-slim-bookworm
│   ├── docker-compose.yml
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   └── app.py                   # Streamlit dashboard (12 módulos)
├── .github/workflows/ci.yml     # GitHub Actions CI
├── .streamlit/config.toml       # Tema visual
├── .gitignore
└── README.md
```

---

## 🤖 Uso de herramientas de IA

Este proyecto fue desarrollado con asistencia de **Claude (Anthropic)** como tutor y guía de código. El uso de IA se limitó a:
- Explicación de conceptos de FastAPI, SQLAlchemy y Pydantic
- Revisión y corrección de errores de código
- Sugerencias de estructura y arquitectura

Todo el código fue escrito, entendido y validado por el autor. La lógica financiera fue implementada siguiendo los contenidos del curso de Teoría del Riesgo.