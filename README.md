# 📊 RiskLab USTA — Sistema Integral de Análisis de Riesgo Financiero

**Autor:** Cristian Vallejo  
**Curso:** Python para APIs e IA + Teoría del Riesgo — CIII  
**Universidad:** Universidad Santo Tomás (USTA)

---

## 🔗 Links de Acceso

| Servicio | URL |
|---|---|
| 🖥️ **Dashboard (Streamlit Cloud)** | https://riesgoapi-7ft4qhompohizwzjfeyefr.streamlit.app/ |
| ⚙️ **API REST (Render)** | https://riesgo-api.onrender.com |
| 📖 **Swagger UI** | https://riesgo-api.onrender.com/docs |
| 📄 **ReDoc** | https://riesgo-api.onrender.com/redoc |
| 💻 **Repositorio GitHub** | https://github.com/CristianVallejo0104/Riesgo_API |

---

## 📋 Descripción

RiskLab USTA es un sistema integral de análisis de riesgo financiero construido con **FastAPI** en el backend, persistencia en **SQLite** vía **SQLAlchemy ORM**, y un dashboard interactivo en **Streamlit**. Integra datos en tiempo real de **Yahoo Finance** y **FRED API**.

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

## ▶️ Ejecutar localmente

### Backend (FastAPI)
```bash
cd backend
python -m uvicorn app.main:app --reload --port 8000
```

- Swagger UI: http://localhost:8000/docs  
- ReDoc: http://localhost:8000/redoc  
- Health check: http://localhost:8000/health

### Frontend (Streamlit)
En otra terminal (desde la raíz del proyecto):

```bash
streamlit run frontend/app.py
```

Dashboard disponible en: http://localhost:8501

---

## 🐳 Ejecutar con Docker

### Solo el backend
```bash
cd backend
docker build -t risklab-backend .
docker run -p 8000:8000 --env-file .env risklab-backend
```

### Backend + Frontend con Docker Compose
```bash
cd backend
docker-compose up --build
```

En segundo plano (sin bloquear la terminal):
```bash
docker-compose up --build -d
```

| Servicio | URL local |
|---|---|
| Frontend Streamlit | http://localhost:8501 |
| Backend FastAPI | http://localhost:8000 |
| Swagger UI | http://localhost:8000/docs |

### Comandos útiles de Docker
```bash
docker-compose logs -f       # ver logs en tiempo real
docker-compose down          # apagar todos los contenedores
docker-compose ps            # ver estado de los contenedores
```

> **Nota:** El archivo `.env` con las API keys no está en el repositorio por seguridad. Debes crearlo manualmente antes de correr Docker.

---

## 🌐 Deploy en producción

### Backend — Render
1. Crear cuenta en https://render.com
2. New → Web Service → conectar repositorio GitHub
3. Render detecta el `Dockerfile` automáticamente
4. Configurar variables de entorno en la UI de Render:
   - `FRED_API_KEY`
   - `DATABASE_URL=sqlite:///./risklab.db`
5. Cada push a `main` dispara redeploy automático vía GitHub Actions

> **Nota:** El free tier de Render se duerme tras 15 min sin tráfico. El cold start toma ~30s. Hacer una llamada a `/health` antes de una demo.

### Frontend — Streamlit Cloud
1. Crear cuenta en https://streamlit.io/cloud
2. New app → conectar repositorio GitHub
3. Main file path: `frontend/app.py`
4. Configurar secrets en la UI de Streamlit Cloud:
   ```toml
   BACKEND_URL = "https://riesgo-api.onrender.com"
   ```
5. Cada push a `main` redeploya automáticamente

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
**Período de análisis:** 3 años de historia (configurable desde el sidebar)

---

## 📡 Endpoints principales

| Endpoint | Método | Descripción |
|---|---|---|
| `/health` | GET | Estado de la API |
| `/activos/` | GET/POST | Lista y crea activos |
| `/precios/{ticker}` | GET | Precios históricos con cache en BD |
| `/precios/descargar/{ticker}` | POST | Descarga y persiste precios |
| `/portafolios/` | GET/POST | CRUD de portafolios |
| `/analisis/rendimientos/{ticker}` | GET | Rendimientos y estadísticas empíricas |
| `/analisis/rendimientos-serie/{ticker}` | GET | Serie temporal de rendimientos log |
| `/analisis/indicadores/{ticker}` | GET | SMA, EMA, RSI, MACD, Bollinger, Estocástico |
| `/analisis/ewma/{ticker}` | GET | Volatilidad EWMA (RiskMetrics λ=0.94) |
| `/analisis/garch/{ticker}` | GET | GARCH/EGARCH/GJR-GARCH con selección AIC/BIC |
| `/analisis/var/{ticker}` | GET | VaR paramétrico, histórico, Monte Carlo + CVaR |
| `/analisis/var-portafolio` | GET | VaR del portafolio completo con diversificación |
| `/analisis/capm` | GET | Beta, Alpha Jensen, R², clasificación |
| `/analisis/markowitz` | GET | Frontera eficiente con QP (cvxpy) + tickers dinámicos |
| `/analisis/alertas` | GET | Señales de trading con persistencia en BD |
| `/analisis/stress-test` | GET | Stress testing 4 escenarios históricos |
| `/macro/` | GET | Tasa libre de riesgo + inflación FRED |
| `/macro/benchmark` | GET | Tracking Error, Information Ratio, Max Drawdown |
| `/renta-fija/curva` | GET | Curva Nelson-Siegel desde FRED |
| `/renta-fija/duracion` | GET | Duración Macaulay, modificada y convexidad |
| `/renta-fija/sensibilidad` | GET | Sensibilidad ante shocks ±50/±100/±200 pb |
| `/opciones/black-scholes` | GET | Black-Scholes + 5 Greeks (validación Pydantic) |
| `/opciones/volatilidad-implicita` | GET | Volatilidad implícita Newton-Raphson |
| `/ml/entrenar/{ticker}` | POST | Entrenamiento offline del modelo RF |
| `/ml/predecir/{ticker}` | POST | Predicción con logging en BD |
| `/agente/estado` | GET | Estado de Ollama y modelos disponibles |
| `/agente/analisis` | POST | Análisis automático del portafolio con LLM |
| `/agente/chat` | POST | Chat financiero con contexto del portafolio |

### Parámetros globales de fecha
Todos los endpoints de análisis aceptan parámetros opcionales de filtro:
- `fecha_inicio` — fecha de inicio del período (YYYY-MM-DD)
- `fecha_fin` — fecha de fin del período (YYYY-MM-DD)

---

## 🧱 Estructura del proyecto

```
Riesgo_API/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app, routers, lifespan
│   │   ├── config.py            # BaseSettings, .env (pydantic-settings)
│   │   ├── dependencies.py      # Depends(): DBSession, SettingsDep
│   │   ├── database.py          # SQLAlchemy engine, session, get_db
│   │   ├── models/
│   │   │   ├── db_models.py     # ORM: Asset, Price, Portfolio, PredictionLog, SignalLog
│   │   │   └── schemas.py       # Pydantic v2 request/response models
│   │   ├── services/
│   │   │   ├── data.py          # DataService + TechnicalIndicators
│   │   │   ├── risk.py          # VaR, CVaR, EWMA, GARCH, CAPM
│   │   │   ├── portfolio.py     # Markowitz QP (cvxpy)
│   │   │   ├── macro.py         # FRED API + cache TTL 1h + fallback automático
│   │   │   ├── fixed_income.py  # Nelson-Siegel, duración, convexidad
│   │   │   ├── options.py       # Black-Scholes, Greeks, vol. implícita
│   │   │   └── stress.py        # Stress testing 4 escenarios
│   │   ├── ml/
│   │   │   ├── train.py         # Entrenamiento offline
│   │   │   ├── predictor.py     # Singleton + predict
│   │   │   └── model.joblib     # Modelo serializado
│   │   └── routers/
│   │       ├── activos.py
│   │       ├── precios.py
│   │       ├── portafolios.py
│   │       ├── analisis.py      # Filtro global por fechas
│   │       ├── macro.py
│   │       ├── fixed_income.py  # Validación Pydantic Query params
│   │       ├── options.py       # Validación Pydantic Query params
│   │       ├── ml.py
│   │       └── agente.py        # Agente IA con Ollama (llama3)
│   ├── tests/
│   │   ├── conftest.py          # BD en memoria + fixtures
│   │   ├── test_endpoints.py
│   │   ├── test_indicators.py
│   │   └── test_risk.py
│   ├── Dockerfile               # Multi-stage python:3.11.9-slim-bookworm
│   ├── docker-compose.yml       # Orquesta backend + frontend
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── app.py                   # Streamlit dashboard (13 módulos + Agente IA)
│   ├── Dockerfile               # Contenedor Streamlit
│   └── requirements.txt
├── .github/
│   └── workflows/
│       └── ci.yml               # GitHub Actions CI/CD
├── .streamlit/
│   └── config.toml              # Tema visual
├── .gitignore
└── README.md
```

---

## 📊 Módulos del Dashboard

| Tab | Módulo | Descripción |
|---|---|---|
| 0 | Contexto | Arquitectura + inicialización del portafolio |
| 1 | Técnico | Velas japonesas, SMA, EMA, Bollinger, RSI, MACD, Estocástico |
| 2 | Rendimientos | Propiedades empíricas, histograma, Q-Q Plot, pruebas de normalidad |
| 3 | Volatilidad | EWMA, GARCH/GJR-GARCH con selección AIC/BIC |
| 4 | CAPM | Beta, Alpha Jensen, R², SML |
| 5 | VaR/CVaR | VaR paramétrico, histórico, Monte Carlo + CVaR + portafolio |
| 6 | Markowitz | Frontera eficiente, Máx. Sharpe, Mín. Varianza, Monte Carlo |
| 7 | Señales | Semáforo de trading por indicadores técnicos |
| 8 | Macro | Curva de rendimientos FRED, inflación, benchmark |
| 9 | Renta Fija | Nelson-Siegel, duración, convexidad, sensibilidad a shocks |
| 10 | Opciones | Black-Scholes, Greeks, perfil de beneficios, análisis de sensibilidad |
| 11 | Stress | Escenarios extremos: caída mercado, shock tasas, volatilidad, combinado |
| 12 | ML | Random Forest: entrenar, predecir, resumen de señales del portafolio |
| 13 | Agente IA | Análisis automático + chat financiero con llama3 (Ollama local) |

---

## 🤖 Uso de herramientas de IA

Este proyecto fue desarrollado con asistencia de **Claude (Anthropic)** como tutor y guía de código. El uso de IA se limitó a:
- Explicación de conceptos de FastAPI, SQLAlchemy y Pydantic
- Revisión y corrección de errores de código
- Sugerencias de estructura y arquitectura

Todo el código fue escrito, entendido y validado por el autor. La lógica financiera fue implementada siguiendo los contenidos del curso de Teoría del Riesgo.