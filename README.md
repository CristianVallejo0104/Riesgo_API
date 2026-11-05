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

RiskLab USTA es un sistema integral de análisis de riesgo financiero construido con **FastAPI** en el backend, persistencia en **SQLite** vía **SQLAlchemy ORM**, y un tablero interactivo en **Streamlit**. Integra datos de **Yahoo Finance** y **FRED API**, y permite analizar portafolios de **Estados Unidos (USD)** o de **Colombia (COP)**.

El tablero está pensado para que **cualquier persona**, aunque no sepa de finanzas ni de estadística, entienda sus resultados. Cada módulo trae un semáforo, una explicación "en palabras simples" y una tabla de cómo leer cada indicador.

> 📘 **Teoría detrás de cada cálculo, pasos para probar y contexto completo:** [`docs/CONTEXTO_CLAUDE.md`](docs/CONTEXTO_CLAUDE.md)

### 🌿 Ramas del repositorio

| Rama | Contenido |
|---|---|
| `main` | **Versión actual (v2.1)**: teoría de riesgo corregida, tablero rediseñado, mercado colombiano. |
| `version-original` | Código inicial del proyecto (antes de la v2.1), conservado sin cambios. |

### Arquitectura en 5 Capas

```
Capa 1 — Datos y persistencia:   yfinance + FRED → SQLite (descarga incremental + caché)
Capa 2 — Análisis clásico:       Indicadores, rendimientos, EWMA/GARCH, CAPM, VaR/CVaR, Markowitz
Capa 3 — Renta fija y derivados: Nelson-Siegel, duración, convexidad, Black-Scholes, stress testing
Capa 4 — Machine Learning:       Random Forest / XGBoost / Regresión Logística → joblib → /predict
Capa 5 — Infraestructura:        pytest (46 pruebas) + Docker + Render + GitHub Actions CI
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

Los tests usan una BD SQLite en memoria y no afectan los datos reales. Son 46 pruebas:
- `test_teoria_riesgo.py`: propiedades teóricas (CVaR ≤ VaR, subaditividad, contribuciones de Euler, Kupiec,
  Black-Scholes contra valores de referencia, paridad put-call, bono a la par, duración del cupón cero = plazo, etc.).
- `test_endpoints_analisis.py`: endpoints de análisis con precios sintéticos (VaR por nivel, pesos, CAPM, stress).
- `test_endpoints.py`, `test_indicators.py`, `test_risk.py`: API básica e indicadores.

---

## 🤖 Entrenar el modelo ML

```bash
cd backend
python -m app.ml.train
```

**Propósito analítico:** El modelo predice la dirección del precio (sube/baja) al día siguiente usando los retornos logarítmicos de los últimos 5 días como features (lags). Compara Random Forest, XGBoost y Regresión Logística (con GridSearchCV opcional), elige el de mayor accuracy y se reentrena cada 8 días.

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

**Benchmark:** S&P 500 (^GSPC). Para Colombia, ICOLCAP.CL / ^COLCAP / GXG, o cualquier índice escrito por el usuario.  
**Período de análisis:** 3 años de historia (configurable desde el sidebar)  
**Portafolios de ejemplo:** Base USTA, Tecnología, Defensivo, Financiero, Balanceado, Colombia (líderes COLCAP, bancos, ADR).

---

## 📡 Endpoints principales

| Endpoint | Método | Descripción |
|---|---|---|
| `/health` | GET | Estado de la API |
| `/activos/` | GET/POST | Lista y crea activos |
| `/precios/{ticker}` | GET | Precios históricos guardados en BD (ordenados por fecha) |
| `/precios/descargar/{ticker}` | POST | Descarga incremental desde Yahoo Finance |
| `/portafolios/` | GET/POST | CRUD de portafolios |
| `/analisis/resumen-portafolio` | GET | Panel ejecutivo: rentabilidad, volatilidad, Sharpe, Sortino, drawdown, VaR/CVaR, beta |
| `/analisis/rendimientos/{ticker}` | GET | Estadísticas empíricas, curtosis en exceso, Jarque-Bera, Shapiro-Wilk |
| `/analisis/rendimientos-serie/{ticker}` | GET | Serie temporal de rendimientos log |
| `/analisis/indicadores/{ticker}` | GET | SMA, EMA, RSI (Wilder), MACD, Bollinger, Estocástico |
| `/analisis/ewma/{ticker}` | GET | Volatilidad EWMA (λ = 0.94) con serie histórica |
| `/analisis/garch/{ticker}` | GET | 6 modelos GARCH/GJR/EGARCH por AIC, pronóstico, persistencia, vida media, ARCH-LM |
| `/analisis/var/{ticker}` | GET | VaR paramétrico, Cornish-Fisher, histórico, Monte Carlo t, CVaR y Kupiec (`nivel`, `horizonte`) |
| `/analisis/var-portafolio` | GET | VaR del portafolio con `pesos`, 3 métodos, CVaR y VaR por componentes |
| `/analisis/capm` | GET | Beta, alfa de Jensen con p-value, R², riesgo sistemático/idiosincrático |
| `/analisis/markowitz` | GET | Máximo Sharpe, mínima varianza, tu portafolio, frontera eficiente, correlaciones (`rf`, `permitir_cortos`) |
| `/analisis/stress-test` | GET | Choques de mercado por beta, volatilidad ×2, correlaciones → 1, peores ventanas reales |
| `/analisis/alertas` | GET | Señales de trading con persistencia en BD |
| `/macro/` | GET | Tasa libre de riesgo (`mercado=US` o `CO`), inflación y curva FRED |
| `/macro/benchmark` | GET | Tracking error, information ratio, drawdown y Sharpe frente al benchmark |
| `/renta-fija/curva` | GET | Curva del Tesoro con ajuste Nelson-Siegel |
| `/renta-fija/duracion` | GET | Precio, duración Macaulay/modificada, convexidad, DV01 (`frecuencia`, `valor_nominal`, `tasa_descuento`) |
| `/renta-fija/sensibilidad` | GET | Precio ante choques de −200 a +200 pb: lineal, con convexidad y exacto |
| `/opciones/black-scholes` | GET | Black-Scholes, griegas call/put, probabilidad de ejercicio, paridad put-call |
| `/opciones/volatilidad-implicita` | GET | Volatilidad implícita (Brent, con límites de no arbitraje) |
| `/ml/entrenar/{ticker}` | POST | Entrena y compara modelos |
| `/ml/predecir/{ticker}` | POST | Predicción con logging en BD |
| `/agente/estado` | GET | Estado de Ollama y modelos disponibles |
| `/agente/analisis` | GET | Informe del portafolio con LLM local |
| `/agente/chat` | POST | Chat financiero con contexto del portafolio |

Los endpoints de portafolio reciben `tickers` y `pesos` (en el mismo orden) repetidos en la URL, por ejemplo
`/analisis/var-portafolio?tickers=AAPL&tickers=KO&pesos=0.6&pesos=0.4&nivel=0.99`.

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
│   │   │   ├── risk.py          # VaR (4 métodos), CVaR, Kupiec, EWMA, GARCH
│   │   │   ├── portfolio.py     # Markowitz (máx. Sharpe, mín. varianza) y VaR de portafolio
│   │   │   ├── macro.py         # FRED (EE. UU. y Colombia) + caché 1h + respaldo
│   │   │   ├── fixed_income.py  # Nelson-Siegel, bonos con frecuencia y nominal
│   │   │   ├── options.py       # Black-Scholes, griegas call/put, vol. implícita
│   │   │   └── stress.py        # Stress por beta, volatilidad, correlación e históricos
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
│   │   ├── test_endpoints_analisis.py
│   │   ├── test_indicators.py
│   │   ├── test_risk.py
│   │   └── test_teoria_riesgo.py # Propiedades teóricas de los cálculos
│   ├── Dockerfile               # Multi-stage python:3.11.9-slim-bookworm
│   ├── docker-compose.yml       # Orquesta backend + frontend
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── app.py                   # Tablero: barra lateral + 16 páginas
│   ├── ui.py                    # Sistema de diseño: colores, KPIs, guías de lectura
│   ├── .streamlit/config.toml   # Tema (para el contenedor del frontend)
│   ├── Dockerfile               # Contenedor Streamlit
│   └── requirements.txt
├── docs/
│   └── CONTEXTO_CLAUDE.md       # Teoría, cambios, pruebas y guía de trabajo
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

El tablero se navega desde la barra lateral (sección → módulo). Sólo se calcula la página abierta,
por eso carga rápido. Cada módulo trae KPIs con **semáforo**, un recuadro **"En palabras simples"** y una
tabla **📘 "Cómo leer"** con el significado y los rangos de referencia de cada resultado, pensada para
personas sin formación en finanzas o estadística. Se puede abrir un módulo directo con `?pagina=var`.

| Sección | Módulo | Pregunta que responde |
|---|---|---|
| Empezar | Inicio y guía de uso | ¿Cómo uso el tablero y qué significa cada color? |
| Empezar | Resumen ejecutivo | ¿Cómo va mi portafolio? (rentabilidad, volatilidad, Sharpe, drawdown, VaR/CVaR en USD, beta) |
| Mercado | Precios y señales técnicas | Velas, medias, Bollinger, RSI (Wilder), MACD, estocástico y semáforo técnico |
| Mercado | Rendimientos y distribución | ¿Hay colas pesadas? Histograma, Q-Q, Jarque-Bera, Shapiro-Wilk |
| Mercado | Volatilidad | EWMA y 6 modelos GARCH/GJR/EGARCH con pronóstico, persistencia, vida media y ARCH-LM |
| Riesgo | VaR y CVaR | 4 métodos de VaR, CVaR, VaR por componentes, diversificación y backtesting de Kupiec |
| Riesgo | Pruebas de estrés | Choques de mercado vía beta, volatilidad ×2, correlaciones → 1 y peores ventanas reales |
| Riesgo | CAPM | Beta, alfa de Jensen con p-value, SML, riesgo sistemático vs idiosincrático |
| Portafolio | Markowitz | Frontera eficiente, máximo Sharpe (tangente), mínima varianza vs tu portafolio |
| Portafolio | Benchmark y macro | Tracking error, information ratio, curva del Tesoro (Nelson-Siegel), inflación |
| Instrumentos | Renta fija | Precio, duración Macaulay/modificada, convexidad, DV01, choques de tasas |
| Instrumentos | Opciones | Black-Scholes, griegas call/put, paridad put-call, volatilidad implícita |
| Herramientas | ML · Agente IA · Arquitectura · Glosario | Predicción de dirección, informe con LLM local, flujo técnico, términos |

### Parámetros que puedes cambiar

| Dónde | Parámetro | Opciones |
|---|---|---|
| Barra lateral → 💰 | Valor del portafolio | USD 100 a USD 100 millones |
| Barra lateral → 💰 | Nivel de confianza del VaR | Libre entre 80 % y 99,5 % (pasos de 0,5 %) |
| Barra lateral → ⚖️ | Pesos | Iguales o personalizados (se re-escalan a 100 %) |
| Barra lateral → 📅 | Período | Hasta 3 años |
| Renta fija | Tipo de bono | Con cupones o **cupón cero** |
| Renta fija | Cupón, frecuencia y nominal | Anual, semestral, trimestral o mensual; nominal libre |
| Renta fija | Rendimiento (YTM) | Curva del Tesoro (FRED) al plazo del bono o tasa propia |

### Invertir en Colombia 🇨🇴

En la barra lateral, **¿Dónde quieres invertir?** permite elegir entre Estados Unidos (USD) y Colombia (COP).
Al elegir Colombia:
* Se carga un portafolio de ejemplo con acciones de la BVC (`ECOPETROL.CL`, `PFBCOLOM.CL`, `ISA.CL`, `GEB.CL`, …).
  Yahoo Finance usa el sufijo `.CL`. También hay ADR en USD (`EC`, `CIB`, `AVAL`) y el ETF `GXG`.
* El benchmark sugerido es `ICOLCAP.CL` (ETF que replica el COLCAP). También se puede elegir `^COLCAP` o
  escribir cualquier índice con la opción "Otro".
* La tasa libre de riesgo se toma de FRED (`COLIR3TIB01STM`, interbancaria a 3 meses) o se escribe a mano.
* Los montos se muestran en COP. Si mezclas activos en COP y USD, aparece un aviso: el modelo no incluye el riesgo cambiario.

> Resumen completo, teoría, pasos para probar y para fusionar a `main`: [`docs/CONTEXTO_CLAUDE.md`](docs/CONTEXTO_CLAUDE.md)

### Velocidad y caché

* Cada endpoint se guarda en caché **1 hora** según sus parámetros, y la caché se comparte entre pestañas y usuarios.
  Al agregar un ticker solo se calcula lo nuevo: los resultados de los demás activos se reutilizan.
* Los precios se revisan **una vez al día por ticker**. Si un ticker ya tiene datos, solo se descargan los días que faltan.
* El botón **🔄 Actualizar precios** fuerza la descarga y limpia la caché.

### Correcciones de teoría de riesgo (v2.1)

| Tema | Antes | Ahora (y por qué) |
|---|---|---|
| Máximo Sharpe | El portafolio mostrado como "Máx. Sharpe" era el de **mínima varianza** y el Sharpe ignoraba la tasa libre de riesgo | Se resuelve el portafolio tangente real con `(μ − rf)/σ`; la frontera sólo dibuja la rama eficiente |
| Nivel de confianza | El VaR individual ignoraba el slider (siempre 95 %) | Todos los endpoints de VaR reciben `nivel` y `horizonte` |
| VaR Monte Carlo | Simulaba una normal → repetía el VaR paramétrico con ruido | t de Student ajustada por MV (captura colas pesadas), con semilla fija |
| CVaR del portafolio | `VaR × 1.3` | CVaR histórico y paramétrico reales |
| Pesos | VaR, stress y benchmark usaban pesos iguales y tickers fijos | Usan los activos y pesos elegidos por el usuario |
| Agregación | Rendimientos log promediados entre activos | Rendimientos **simples** para portafolios (el log no es aditivo entre activos) |
| Kupiec | Backtesting dentro de muestra (tautológico); fallaba con 0 excepciones | Ventana móvil fuera de muestra + zonas tipo Basilea |
| Curtosis | Se comparaba la curtosis en exceso de pandas contra 3 | Se compara contra 0 (normal) |
| GARCH | Método duplicado, test ARCH-LM falso (`normaltest`), persistencia α+β para EGARCH/GJR | Persistencia correcta por modelo, ARCH-LM de Engle, pronóstico, vol. de largo plazo y vida media |
| CAPM | Alfa con medias de log-rendimientos sin regresión de excesos | Regresión `(Ri − rf) = α + β(Rm − rf)`, p-values y descomposición del riesgo |
| Stress test | Impactos fijos (−10 % por tasas a todos, −16 % "combinado") y beta contra el propio portafolio | Beta contra el benchmark, VaR estresado, correlaciones → 1 y peores ventanas observadas |
| Renta fija | Todo bono se descontaba con la tasa a 30 años; el gráfico usaba duración Macaulay como modificada | Tasa interpolada al plazo (o YTM del usuario), duración modificada, DV01 |
| Opciones | Theta anual sólo call, vega por 1.00 de σ, vol. implícita con Newton (puede divergir) | Griegas call/put en unidades interpretables (día, 1 p.p.), Brent con límites de no arbitraje |
| Benchmark | Drawdown con `(1 + r_log).cumprod()` y Sharpe sin rf | Rendimientos simples y Sharpe con la tasa de FRED |

Las pruebas `backend/tests/test_teoria_riesgo.py` y `test_endpoints_analisis.py` verifican estas
propiedades (CVaR ≤ VaR, subaditividad, contribuciones de Euler que suman el VaR, Black-Scholes contra
valores de referencia, paridad put-call, bono a la par, etc.).

---|---|---|
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


## 🧠 Configuración del Agente IA Local (Ollama)

El módulo de Agente IA usa [Ollama](https://ollama.ai) con el modelo **llama3** corriendo localmente en `http://localhost:11434`.

### 1. Instalar Ollama
Descarga desde: https://ollama.ai/download

### 2. Descargar el modelo
```bash
ollama pull llama3
```

### 3. Iniciar Ollama
```bash
ollama serve
```

> **Nota:** Con GPU dedicada (ej. RTX 3050) responde en ~5-10 segundos. Sin GPU puede tardar hasta 60 segundos usando CPU.