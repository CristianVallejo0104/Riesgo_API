"""
frontend/app.py — RiskLab USTA · Tablero de riesgo financiero
Consume los endpoints del backend FastAPI.
Correr: streamlit run frontend/app.py

Organización del archivo
  1. Configuración, conexión al backend y utilidades
  2. Barra lateral: navegación + configuración del portafolio
  3. Una función por página (sólo se ejecuta la página abierta)
"""
import json
import os
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st
from scipy import stats as sp_stats

import ui
from ui import num, pct, usd

st.set_page_config(page_title="RiskLab USTA · Riesgo Financiero", page_icon="📊",
                   layout="wide", initial_sidebar_state="expanded")
ui.aplicar_estilos()


# ═══════════════════════════ 1. CONEXIÓN AL BACKEND ═══════════════════════════

def _risklab_health(api_base: str):
    try:
        response = requests.get(f"{api_base}/health", timeout=1.5)
        response.raise_for_status()
        data = response.json()
        if data.get("app") == "RiskLab USTA API":
            return data
    except (requests.RequestException, ValueError):
        return None
    return None


@st.cache_data(ttl=30, show_spinner=False)
def resolve_api_url():
    explicit_api = os.getenv("BACKEND_URL")
    if explicit_api:
        return explicit_api.rstrip("/")
    candidatos = ["http://127.0.0.1:8000"] + [f"http://127.0.0.1:{p}" for p in range(8010, 8021)]
    detectados = [c for c in candidatos if _risklab_health(c)]
    return detectados[0] if detectados else "http://127.0.0.1:8000"


API = resolve_api_url()


def api_error_detail(response):
    try:
        return response.json().get("detail", response.reason)
    except ValueError:
        return response.text.strip() or response.reason


def api_get(ep, params=None, timeout=120):
    """GET sin caché, mostrando el error en pantalla si falla."""
    try:
        r = requests.get(f"{API}{ep}", params=params, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        st.error(f"❌ Backend no disponible en {API}. Verifica que FastAPI esté corriendo.")
    except requests.exceptions.HTTPError as e:
        st.error(f"❌ Error {e.response.status_code}: {api_error_detail(e.response)}")
    except requests.exceptions.JSONDecodeError:
        st.error("❌ El backend devolvió una respuesta inválida.")
    except Exception as e:  # noqa: BLE001
        st.error(f"❌ {e}")
    return None


def api_post(ep, body=None, timeout=120):
    try:
        r = requests.post(f"{API}{ep}", json=body or {}, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        st.error(f"❌ Backend no disponible en {API}. Verifica que FastAPI esté corriendo.")
    except requests.exceptions.HTTPError as e:
        st.error(f"❌ Error {e.response.status_code}: {api_error_detail(e.response)}")
    except Exception as e:  # noqa: BLE001
        st.error(f"❌ {e}")
    return None


@st.cache_data(ttl=3600, show_spinner=False, max_entries=2000)
def _get_cacheado(ep: str, params_json: str, timeout: int):
    # Si hay error se lanza la excepción: st.cache_data NO guarda excepciones,
    # así un fallo temporal no queda "pegado" en la caché.
    r = requests.get(f"{API}{ep}", params=json.loads(params_json) if params_json else None, timeout=timeout)
    r.raise_for_status()
    return r.json()


def fetch(ep, params=None, timeout=180, silencioso=False):
    """GET con caché compartida de 1 hora (entre pestañas y usuarios).
    La clave incluye endpoint + parámetros: si agregas un ticker, los resultados de
    los demás activos se reutilizan y sólo se calcula lo nuevo."""
    try:
        return _get_cacheado(ep, json.dumps(params or {}, sort_keys=True, default=str), timeout)
    except requests.exceptions.ConnectionError:
        if not silencioso:
            st.error(f"❌ Backend no disponible en {API}. Verifica que FastAPI esté corriendo.")
    except requests.exceptions.HTTPError as e:
        if not silencioso:
            st.error(f"❌ {api_error_detail(e.response)}")
    except Exception as e:  # noqa: BLE001
        if not silencioso:
            st.error(f"❌ {e}")
    return None


def cached_get(endpoint: str, params_str: str = ""):
    """Compatibilidad con los módulos de ML / Arquitectura."""
    return fetch(endpoint, json.loads(params_str) if params_str else None)


def descargar_o_actualizar(ticker):
    """Asegura que el ticker tenga precios en la BD.
    * Si no existe: descarga 3 años completos.
    * Si existe pero su último precio tiene más de 1 día hábil: descarga SÓLO los días
      que faltan (el backend continúa desde la última fecha guardada).
    * Si está al día: no hace nada."""
    try:
        r = requests.get(f"{API}/precios/{urllib.parse.quote(ticker, safe='')}", timeout=30)
        datos = r.json() if r.status_code == 200 else []
        if datos:
            ultimo = pd.to_datetime(max(d["fecha"] for d in datos)).normalize()
            if ultimo >= pd.Timestamp.today().normalize() - pd.tseries.offsets.BDay(1):
                return
        requests.post(f"{API}/precios/descargar/{urllib.parse.quote(ticker, safe='')}", timeout=120)
    except Exception:  # noqa: BLE001
        pass


@st.cache_resource(show_spinner=False)
def registro_descargas() -> dict:
    """Memoria compartida por todo el servidor: {ticker: fecha en que se revisó}.
    Evita volver a consultar Yahoo Finance por un ticker ya revisado hoy."""
    return {}


def actualizar_precios(ticker):
    try:
        requests.post(f"{API}/precios/descargar/{urllib.parse.quote(ticker, safe='')}", timeout=120)
    except Exception:  # noqa: BLE001
        pass


def q(t: str) -> str:
    return urllib.parse.quote(t, safe="")


# ═══════════════════════════ CATÁLOGO DE TICKERS ═══════════════════════════

TICKERS_DB = {
    "AAPL": "Apple (Tech)", "MSFT": "Microsoft (Tech)", "GOOGL": "Alphabet (Tech)",
    "AMZN": "Amazon (Tech)", "TSLA": "Tesla (Tech)", "NVDA": "NVIDIA (Tech)",
    "META": "Meta (Tech)", "NFLX": "Netflix (Tech)", "AMD": "AMD (Tech)",
    "JPM": "JPMorgan (Financiero)", "BAC": "Bank of America (Financiero)",
    "GS": "Goldman Sachs (Financiero)", "V": "Visa (Financiero)", "MA": "Mastercard (Financiero)",
    "JNJ": "Johnson & Johnson (Salud)", "PFE": "Pfizer (Salud)", "UNH": "UnitedHealth (Salud)",
    "MRK": "Merck (Salud)", "ABBV": "AbbVie (Salud)",
    "XOM": "ExxonMobil (Energía)", "CVX": "Chevron (Energía)", "COP": "ConocoPhillips (Energía)",
    "KO": "Coca-Cola (Consumo)", "PEP": "PepsiCo (Consumo)", "WMT": "Walmart (Consumo)",
    "MCD": "McDonald's (Consumo)", "NKE": "Nike (Consumo)", "SBUX": "Starbucks (Consumo)",
    "PG": "P&G (Consumo)", "F": "Ford (Automotriz)", "GM": "General Motors (Automotriz)",
    "TM": "Toyota (Automotriz)", "TSM": "TSMC (Tech)", "ASML": "ASML (Tech)", "SAP": "SAP (Tech)",
    "BABA": "Alibaba (Tech)", "TCEHY": "Tencent (Tech)", "BRK-B": "Berkshire (Financiero)",
    "HD": "Home Depot (Consumo)", "CRM": "Salesforce (Tech)", "ADBE": "Adobe (Tech)",
    "INTC": "Intel (Tech)", "QCOM": "Qualcomm (Tech)", "TXN": "Texas Instruments (Tech)",
    "PYPL": "PayPal (Financiero)", "SHOP": "Shopify (Tech)", "SPOT": "Spotify (Tech)",
    "ABNB": "Airbnb (Consumo)", "UBER": "Uber (Tech)", "005930.KS": "Samsung (Tech)",
    "ORCL": "Oracle (Tech)", "IBM": "IBM (Tech)", "NOW": "ServiceNow (Tech)",
    "SNOW": "Snowflake (Tech)", "NET": "Cloudflare (Tech)", "DDOG": "Datadog (Tech)",
    "AVGO": "Broadcom (Tech)", "MU": "Micron (Tech)", "LRCX": "Lam Research (Tech)",
    "AMAT": "Applied Materials (Tech)", "CSCO": "Cisco (Tech)", "PANW": "Palo Alto Networks (Ciberseguridad)",
    "CRWD": "CrowdStrike (Ciberseguridad)", "AXP": "American Express (Financiero)",
    "MS": "Morgan Stanley (Financiero)", "C": "Citigroup (Financiero)", "BLK": "BlackRock (Financiero)",
    "SCHW": "Charles Schwab (Financiero)", "TMO": "Thermo Fisher (Salud)", "LLY": "Eli Lilly (Salud)",
    "NVO": "Novo Nordisk (Salud)", "ISRG": "Intuitive Surgical (Salud)", "GILD": "Gilead (Salud)",
    "BMY": "Bristol Myers Squibb (Salud)", "SLB": "Schlumberger (Energía)", "EOG": "EOG Resources (Energía)",
    "PSX": "Phillips 66 (Energía)", "VLO": "Valero (Energía)", "COST": "Costco (Consumo)",
    "TGT": "Target (Consumo)", "LOW": "Lowe's (Consumo)", "DIS": "Disney (Consumo)",
    "CMG": "Chipotle (Consumo)", "BKNG": "Booking Holdings (Consumo)", "LULU": "Lululemon (Consumo)",
    "CAT": "Caterpillar (Industrial)", "DE": "Deere (Industrial)", "GE": "GE Aerospace (Industrial)",
    "HON": "Honeywell (Industrial)", "UPS": "UPS (Industrial)", "FDX": "FedEx (Industrial)",
    "BA": "Boeing (Industrial)", "RTX": "RTX (Industrial)", "LMT": "Lockheed Martin (Industrial)",
    "NEE": "NextEra Energy (Servicios públicos)", "DUK": "Duke Energy (Servicios públicos)",
    "SO": "Southern Company (Servicios públicos)", "PLD": "Prologis (Inmobiliario)",
    "AMT": "American Tower (Inmobiliario)", "EQIX": "Equinix (Inmobiliario)",
    "GLD": "Oro — SPDR Gold Trust (ETF)", "IWM": "Russell 2000 (ETF)", "VTI": "Mercado total EE. UU. (ETF)",
    "EFA": "Mercados desarrollados (ETF)", "EEM": "Mercados emergentes (ETF)",
    "TLT": "Bonos del Tesoro 20+ años (ETF)", "HYG": "Bonos high yield (ETF)",
    "LQD": "Bonos grado de inversión (ETF)", "XLF": "Sector financiero (ETF)",
    "XLK": "Sector tecnología (ETF)", "XLV": "Sector salud (ETF)", "XLE": "Sector energía (ETF)",
}

TICKER_PRESETS = {
    "Base USTA": ["AAPL", "JPM", "JNJ", "XOM", "KO"],
    "Tecnología": ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META"],
    "Defensivo": ["JNJ", "KO", "PG", "WMT", "COST", "NEE"],
    "Financiero": ["JPM", "BAC", "GS", "V", "MA", "BLK"],
    "Balanceado (acciones + bonos + oro)": ["VTI", "EFA", "TLT", "LQD", "GLD"],
    "Databricks demo 15": ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "JPM", "V", "LLY",
                           "NVO", "XOM", "COST", "CAT", "NEE", "GLD"],
}

BENCHMARKS = {"^GSPC": "S&P 500", "^DJI": "Dow Jones", "^IXIC": "NASDAQ Composite",
              "^RUT": "Russell 2000", "SPY": "S&P 500 (ETF SPY)", "QQQ": "NASDAQ-100 (ETF QQQ)"}


# ═══════════════════════════ 2. BARRA LATERAL ═══════════════════════════

PAGINAS = {
    "Empezar": ["🏠 Inicio y guía de uso", "📋 Resumen ejecutivo"],
    "Comportamiento del mercado": ["📈 Precios y señales técnicas", "📉 Rendimientos y distribución",
                                   "🌊 Volatilidad (EWMA / GARCH)"],
    "Medición del riesgo": ["🛡️ VaR y CVaR", "💥 Pruebas de estrés", "🎯 CAPM y riesgo de mercado"],
    "Construcción del portafolio": ["⚡ Optimización (Markowitz)", "🌐 Benchmark y macroeconomía"],
    "Otros instrumentos": ["📐 Renta fija (bonos)", "🧮 Opciones (Black-Scholes)"],
    "Herramientas": ["🤖 Machine Learning", "🧠 Agente IA", "🧩 Arquitectura técnica", "📖 Glosario"],
}
LISTA_PAGINAS = [p for grupo in PAGINAS.values() for p in grupo]
GRUPO_DE = {p: g for g, ps in PAGINAS.items() for p in ps}

with st.sidebar:
    st.markdown('<div class="rl-side-brand"><div class="logo">RL</div><div>'
                '<div class="t1">RiskLab USTA</div><div class="t2">Tablero de riesgo financiero</div>'
                '</div></div>', unsafe_allow_html=True)

    st.markdown('<div class="rl-side-label">Navegación</div>', unsafe_allow_html=True)
    # Enlace directo: ?pagina=var abre "VaR y CVaR" (sólo en la primera carga)
    _slug = st.query_params.get("pagina")
    if _slug and not st.session_state.get("_slug_aplicado"):
        for _p in LISTA_PAGINAS:
            if _slug.lower() in _p.lower():
                st.session_state["nav_grupo"] = GRUPO_DE[_p]
                st.session_state[f"nav_{GRUPO_DE[_p]}"] = _p
                break
        st.session_state["_slug_aplicado"] = True
    grupo = st.selectbox("Sección", list(PAGINAS.keys()), key="nav_grupo", label_visibility="collapsed")
    pagina = st.radio("Módulo", PAGINAS[grupo], key=f"nav_{grupo}", label_visibility="collapsed")

    st.markdown('<div class="rl-side-label">Tu portafolio</div>', unsafe_allow_html=True)
    if "tickers_seleccionados" not in st.session_state:
        st.session_state["tickers_seleccionados"] = ["AAPL", "JPM", "JNJ", "XOM", "KO"]
    for t in st.session_state["tickers_seleccionados"]:
        TICKERS_DB.setdefault(t, f"{t} (personalizado)")

    with st.expander("📦 Activos", expanded=True):
        preset = st.selectbox("Cargar un portafolio de ejemplo", ["—"] + list(TICKER_PRESETS),
                              key="preset_sel", help="Atajos para probar el tablero rápidamente.")
        if preset != "—" and st.session_state.get("_preset_aplicado") != preset:
            st.session_state["tickers_seleccionados"] = TICKER_PRESETS[preset]
            st.session_state["_preset_aplicado"] = preset
            st.session_state.pop("ms_tickers", None)
            st.rerun()

        tickers = st.multiselect(
            "Activos del portafolio", options=sorted(TICKERS_DB.keys()),
            default=[t for t in st.session_state["tickers_seleccionados"] if t in TICKERS_DB],
            format_func=lambda t: f"{t} — {TICKERS_DB[t]}", key="ms_tickers",
            help="Escribe el nombre o el ticker para buscar. Se necesitan al menos 2 activos.")
        st.session_state["tickers_seleccionados"] = tickers

        nuevo = st.text_input("¿No está en la lista? Escribe el ticker de Yahoo Finance",
                              placeholder="Ej: ECOPETROL.CL, BTC-USD", key="ticker_manual")
        if st.button("➕ Agregar ticker", use_container_width=True) and nuevo.strip():
            for t in [x.strip().upper() for x in nuevo.split(",") if x.strip()]:
                TICKERS_DB.setdefault(t, f"{t} (personalizado)")
                if t not in st.session_state["tickers_seleccionados"]:
                    st.session_state["tickers_seleccionados"].append(t)
            st.session_state.pop("ms_tickers", None)
            st.rerun()

        benchmark = st.selectbox("Índice de referencia (benchmark)", list(BENCHMARKS),
                                 format_func=lambda x: BENCHMARKS[x],
                                 help="El 'mercado' contra el que se compara tu portafolio.")

    with st.expander("💰 Monto y nivel de confianza", expanded=False):
        valor_portafolio = st.number_input("Valor del portafolio (USD)", min_value=100.0,
                                           max_value=100_000_000.0, value=100_000.0, step=1_000.0)
        confianza_var = st.slider(
            "Nivel de confianza del VaR (%)", min_value=80.0, max_value=99.5, value=95.0, step=0.5,
            format="%.1f%%",
            help="95 % significa: 'en 95 de cada 100 días la pérdida no debería superar el VaR'. "
                 "Más confianza = VaR más alto (más conservador).") / 100
        st.caption(f"Valores habituales: 95 % (gestión interna), 99 % (Basilea, VaR), 97,5 % (Basilea III, CVaR). "
                   f"Con {confianza_var:.1%}".replace(".0%", "%") +
                   f" se espera superar el VaR ~{(1 - confianza_var) * 100:.1f} de cada 100 días.")

    with st.expander("⚖️ Pesos de cada activo", expanded=False):
        peso_igual = st.checkbox("Repartir en partes iguales", value=True)
        pesos = {}
        if tickers:
            if peso_igual:
                pesos = {t: 1 / len(tickers) for t in tickers}
                st.caption(f"Cada activo recibe {100 / len(tickers):.1f} % del capital.")
            else:
                st.caption("Escribe el porcentaje de cada activo. Si no suman 100 % se re-escalan.")
                for t in tickers:
                    pesos[t] = st.number_input(f"{t} (%)", 0.0, 100.0, round(100 / len(tickers), 1),
                                               1.0, key=f"w_{t}") / 100
                total = sum(pesos.values())
                if total <= 0:
                    pesos = {t: 1 / len(tickers) for t in tickers}
                elif abs(total - 1) > 0.001:
                    st.caption(f"Suman {total:.0%} → se re-escalan a 100 %.")
                    pesos = {t: w / total for t, w in pesos.items()}

    with st.expander("📅 Período de análisis", expanded=False):
        hoy = pd.Timestamp.today().normalize()
        fecha_inicio = st.date_input("Desde", value=(hoy - pd.DateOffset(years=3)).date(),
                                     max_value=hoy.date(), key="fecha_inicio_global")
        fecha_fin = st.date_input("Hasta", value=hoy.date(), min_value=fecha_inicio,
                                  max_value=hoy.date(), key="fecha_fin_global")
        st.caption(f"{(fecha_fin - fecha_inicio).days} días calendario. "
                   "Se descargan hasta 3 años de historia.")

    if st.button("🔄 Actualizar precios", use_container_width=True,
                 help="Descarga los últimos precios de Yahoo Finance y borra la caché."):
        with st.spinner("Actualizando precios..."):
            with ThreadPoolExecutor(max_workers=4) as ex:
                list(ex.map(actualizar_precios, tickers + [benchmark]))
            for t in tickers + [benchmark]:
                registro_descargas()[t] = str(pd.Timestamp.today().date())
        registro_descargas().clear()
        st.cache_data.clear()
        st.rerun()

    st.markdown("---")
    st.caption(f"Backend: `{API}`")
    st.caption("RiskLab USTA · Teoría del Riesgo · CIII")

fi, ff = str(fecha_inicio), str(fecha_fin)
lista_pesos = [float(pesos.get(t, 0)) for t in tickers]
P_BASE = {"tickers": tickers, "pesos": lista_pesos, "fecha_inicio": fi, "fecha_fin": ff}

# ── Descarga incremental de datos ──
# Sólo se consultan los tickers que nadie ha revisado hoy. Al agregar un ticker se
# descarga únicamente ese; los demás conservan sus datos y sus cálculos en caché.
_reg = registro_descargas()
_hoy = str(pd.Timestamp.today().date())
faltantes = [t for t in dict.fromkeys(tickers + [benchmark]) if _reg.get(t) != _hoy]
if faltantes:
    with st.spinner(f"Preparando datos de {', '.join(faltantes)}..."):
        with ThreadPoolExecutor(max_workers=4) as ex:
            list(ex.map(descargar_o_actualizar, faltantes))
    for t in faltantes:
        _reg[t] = _hoy
    # Sólo se invalida la caché de precios de los tickers nuevos/actualizados

# Colores estables: cada activo conserva su color aunque agregues o quites otros
ui.registrar_colores(tickers)

# ── Tasa libre de riesgo y datos macro (FRED) ──
macro = fetch("/macro/", silencioso=True)
tasa_fred = float(macro["tasa_libre_riesgo"]) if macro else 0.045
fuente_rf = "FRED · Tesoro EE. UU. 3 meses" if macro else "valor de respaldo"


# ═══════════════════════════ UTILIDADES DE PÁGINA ═══════════════════════════

def cabecera(titulo: str, descripcion: str):
    chips = [f"{len(tickers)} activos", f"Benchmark: {BENCHMARKS.get(benchmark, benchmark)}",
             f"Capital: {usd(valor_portafolio)}", f"VaR al {confianza_var:.1%}".replace(".0%", "%"),
             f"{fi} → {ff}", f"Tasa libre de riesgo: {pct(tasa_fred)}"]
    ui.hero(titulo, descripcion, eyebrow=GRUPO_DE.get(pagina, "RiskLab USTA"), chips=chips)


def requiere_portafolio(minimo: int = 2) -> bool:
    if len(tickers) < minimo:
        ui.nota(f"Selecciona al menos {minimo} activos en la barra lateral para usar este módulo.",
                "warn", "Faltan activos")
        return False
    return True


def selector_activo(key: str, etiqueta: str = "Activo a analizar"):
    return st.selectbox(etiqueta, tickers, key=key,
                        format_func=lambda t: f"{t} — {TICKERS_DB.get(t, t)}")


def precios_df(ticker: str) -> pd.DataFrame | None:
    data = fetch(f"/precios/{q(ticker)}", silencioso=True)
    if not data:
        return None
    df = pd.DataFrame(data)
    df["fecha"] = pd.to_datetime(df["fecha"])
    df = df.drop_duplicates("fecha", keep="last").sort_values("fecha")
    return df[(df["fecha"] >= pd.to_datetime(fi)) & (df["fecha"] <= pd.to_datetime(ff))]


def nivel_txt() -> str:
    return f"{confianza_var:.1%}".replace(".0%", "%")


# Semáforos (umbrales orientativos, explicados en cada guía de lectura)
def est_vol(v):
    return "bueno" if v < 0.15 else "alerta" if v < 0.25 else "serio" if v < 0.40 else "critico"


def est_sharpe(s):
    return "bueno" if s >= 1 else "alerta" if s >= 0.5 else "serio" if s >= 0 else "critico"


def est_dd(d):
    return "bueno" if d > -0.10 else "alerta" if d > -0.20 else "serio" if d > -0.35 else "critico"


def est_var(v):
    """v = pérdida diaria (fracción positiva). Los umbrales están definidos para el 95 %;
    con otro nivel de confianza se re-escala por z(95 %)/z(nivel) para que el color
    refleje el riesgo del portafolio y no sólo el nivel de confianza elegido."""
    v = v * sp_stats.norm.ppf(0.95) / sp_stats.norm.ppf(confianza_var)
    return "bueno" if v < 0.015 else "alerta" if v < 0.025 else "serio" if v < 0.04 else "critico"


def est_ret(r, rf):
    return "bueno" if r > rf else "alerta" if r > 0 else "critico"


def tipo_beta(b):
    return "Defensivo" if b < 0.8 else "Agresivo" if b > 1.2 else "Similar al mercado"


# ═══════════════════════════ 3. PÁGINAS ═══════════════════════════

# ─────────────────────────── INICIO ───────────────────────────
def pagina_inicio():
    ui.hero("Entiende el riesgo de tu inversión, paso a paso",
            "RiskLab convierte precios de mercado en respuestas claras: ¿cuánto podría perder?, "
            "¿qué tan volátil es?, ¿estoy bien diversificado?, ¿qué pasa si hay una crisis? "
            "No necesitas saber estadística: cada módulo trae una guía para leer sus resultados.",
            eyebrow="Bienvenido a RiskLab USTA",
            chips=["Datos reales de Yahoo Finance", "Tasas de la Reserva Federal (FRED)",
                   "Modelos usados por bancos y reguladores"])

    ui.encabezado("Cómo usar el tablero en 3 pasos")
    ui.pasos([
        ("Arma tu portafolio", "En la barra lateral elige los activos (acciones, ETF, bonos, oro...) "
         "o carga un portafolio de ejemplo. Define cuánto dinero inviertes y qué peso tiene cada activo."),
        ("Mira el Resumen ejecutivo", "Es la foto general: rentabilidad, riesgo, peor caída y pérdida "
         "probable en un mal día, con un semáforo que te dice si cada número es tranquilo o preocupante."),
        ("Profundiza por módulo", "Cada módulo responde una pregunta concreta. Abajo de cada resultado "
         "encontrarás una tabla 📘 'Cómo leer' con el significado y los rangos de referencia."),
    ])

    ui.encabezado("Cómo leer los colores", "El mismo código de semáforo se usa en todo el tablero.")
    ui.guia_lectura("Código de colores", [
        {"Color": ("bueno", "Favorable"), "Significado": "El indicador está en una zona cómoda.",
         "Qué hacer": "Nada urgente; sigue monitoreando."},
        {"Color": ("alerta", "Atención"), "Significado": "Riesgo moderado o desempeño regular.",
         "Qué hacer": "Revisa el detalle del módulo para entender por qué."},
        {"Color": ("serio", "Elevado"), "Significado": "Riesgo alto frente a lo habitual.",
         "Qué hacer": "Considera diversificar o reducir la exposición."},
        {"Color": ("critico", "Crítico"), "Significado": "Riesgo muy alto o pérdidas.",
         "Qué hacer": "Analiza con cuidado antes de mantener la posición."},
    ], columnas=("Color", "Significado", "Qué hacer"))

    ui.encabezado("Conceptos clave en un minuto")
    ui.guia_lectura("Las 6 ideas que necesitas", [
        {"Concepto": "Rendimiento", "Idea simple": "Cuánto ganó o perdió la inversión en porcentaje.",
         "Ejemplo": "Invertiste 100 y ahora tienes 108 → rendimiento de 8 %."},
        {"Concepto": "Volatilidad", "Idea simple": "Qué tanto sube y baja el precio. Más volatilidad = más incertidumbre.",
         "Ejemplo": "Volatilidad anual de 20 %: en un año 'normal' el resultado suele estar entre −20 % y +20 % alrededor del promedio."},
        {"Concepto": "VaR (Valor en Riesgo)", "Idea simple": "La pérdida que, en un mal día, solo se supera con poca probabilidad.",
         "Ejemplo": "VaR 95 % de USD 2.000: en 95 de cada 100 días pierdes menos de USD 2.000."},
        {"Concepto": "CVaR / Expected Shortfall", "Idea simple": "Cuánto pierdes en promedio en esos días malos que superan el VaR.",
         "Ejemplo": "CVaR de USD 3.000: cuando el día es peor que el VaR, la pérdida media es USD 3.000."},
        {"Concepto": "Beta (β)", "Idea simple": "Cuánto se mueve el activo cuando se mueve el mercado.",
         "Ejemplo": "β = 1.5: si el mercado cae 10 %, el activo tiende a caer 15 %."},
        {"Concepto": "Ratio de Sharpe", "Idea simple": "Ganancia extra (sobre un bono sin riesgo) por cada unidad de riesgo asumida.",
         "Ejemplo": "Sharpe de 1 o más se considera bueno; negativo significa que no compensó el riesgo."},
    ], columnas=("Concepto", "Idea simple", "Ejemplo"))

    ui.encabezado("Qué pregunta responde cada módulo")
    ui.tarjetas_modulos([
        {"titulo": "📋 Resumen ejecutivo", "pregunta": "¿Cómo va mi portafolio en general?",
         "desc": "Rentabilidad, riesgo, peor caída y pérdida probable con semáforo."},
        {"titulo": "📈 Precios y señales", "pregunta": "¿Cómo se ha movido el precio y qué dicen los indicadores?",
         "desc": "Velas, medias móviles, RSI, MACD y un semáforo técnico por activo."},
        {"titulo": "📉 Rendimientos", "pregunta": "¿Los movimientos son 'normales' o hay sorpresas extremas?",
         "desc": "Distribución, colas pesadas y pruebas de normalidad."},
        {"titulo": "🌊 Volatilidad", "pregunta": "¿Está el mercado más nervioso que de costumbre?",
         "desc": "EWMA y modelos GARCH que siguen la volatilidad día a día."},
        {"titulo": "🛡️ VaR y CVaR", "pregunta": "¿Cuánto podría perder en un mal día?",
         "desc": "Cuatro métodos, contribución de cada activo y validación (backtesting)."},
        {"titulo": "💥 Pruebas de estrés", "pregunta": "¿Qué pasa si hay una crisis?",
         "desc": "Caídas del mercado, volatilidad extrema y las peores semanas reales."},
        {"titulo": "🎯 CAPM", "pregunta": "¿Cuánto riesgo de mercado tiene cada activo y si rinde lo que debería?",
         "desc": "Beta, alfa de Jensen y línea del mercado de valores."},
        {"titulo": "⚡ Markowitz", "pregunta": "¿Cuál es la mejor combinación de activos?",
         "desc": "Frontera eficiente, máximo Sharpe y mínima varianza vs tu portafolio."},
        {"titulo": "🌐 Benchmark y macro", "pregunta": "¿Le gano al mercado? ¿Cómo está la economía?",
         "desc": "Comparación con el índice, tasas de interés e inflación."},
        {"titulo": "📐 Renta fija", "pregunta": "¿Cuánto cambia el precio de un bono si suben las tasas?",
         "desc": "Duración, convexidad y sensibilidad a choques de tasas."},
        {"titulo": "🧮 Opciones", "pregunta": "¿Cuánto vale una opción y de qué depende?",
         "desc": "Black-Scholes, griegas y perfil de ganancias."},
        {"titulo": "📖 Glosario", "pregunta": "¿Qué significa este término?",
         "desc": "Todos los conceptos del tablero explicados en lenguaje simple."},
    ])
    st.write("")
    ui.nota("Este tablero es una herramienta educativa. Los resultados se basan en datos históricos, "
            "que no garantizan resultados futuros, y no constituyen asesoría de inversión.", "info",
            "Aviso importante")


# ─────────────────────────── RESUMEN EJECUTIVO ───────────────────────────
def pagina_resumen():
    cabecera("Resumen ejecutivo del portafolio",
             "La foto general de tu inversión en una sola pantalla: cuánto ha rendido, cuánto riesgo "
             "tiene y cuánto podrías perder en un mal día.")
    if not requiere_portafolio():
        return
    d = fetch("/analisis/resumen-portafolio",
              {**P_BASE, "benchmark": benchmark, "nivel": confianza_var, "rf": tasa_fred})
    if not d:
        return

    var_usd = abs(d["var_historico"]) * valor_portafolio
    cvar_usd = abs(d["cvar_historico"]) * valor_portafolio
    ui.kpi_grid([
        {"label": "Rentabilidad anual promedio", "value": pct(d["retorno_anual"]),
         "sub": f"Acumulado del período: {pct(d['retorno_acumulado'], signo=True)}",
         "estado": est_ret(d["retorno_anual"], tasa_fred),
         "tag": "Supera la tasa sin riesgo" if d["retorno_anual"] > tasa_fred else
                ("Positiva, pero bajo la tasa sin riesgo" if d["retorno_anual"] > 0 else "Pérdidas")},
        {"label": "Volatilidad anual", "value": pct(d["volatilidad_anual"]),
         "sub": "Qué tanto oscila el valor", "estado": est_vol(d["volatilidad_anual"])},
        {"label": "Ratio de Sharpe", "value": num(d["sharpe"]),
         "sub": "Ganancia extra por unidad de riesgo", "estado": est_sharpe(d["sharpe"])},
        {"label": "Peor caída (máx. drawdown)", "value": pct(d["max_drawdown"]),
         "sub": f"De {d['max_drawdown_pico']} a {d['max_drawdown_fondo']}", "estado": est_dd(d["max_drawdown"])},
        {"label": f"VaR diario al {nivel_txt()}", "value": usd(var_usd),
         "sub": f"{pct(abs(d['var_historico']))} del capital", "estado": est_var(abs(d["var_historico"]))},
        {"label": "CVaR (pérdida media en días malos)", "value": usd(cvar_usd),
         "sub": f"{pct(abs(d['cvar_historico']))} del capital", "estado": est_var(abs(d["cvar_historico"]) * 0.8)},
        {"label": "Beta frente al benchmark", "value": num(d.get("beta")),
         "sub": BENCHMARKS.get(benchmark, benchmark), "estado": "neutral",
         "tag": tipo_beta(d["beta"]) if d.get("beta") is not None else "Sin benchmark"},
        {"label": "Ahorro por diversificar", "value": usd(d["beneficio_diversificacion"] * valor_portafolio),
         "sub": "Reducción del VaR frente a sumar los riesgos por separado", "estado": "neutral",
         "tag": "Beneficio de diversificación"},
    ])

    # Narrativa automática
    frases = [f"Con **{usd(valor_portafolio)}** invertidos, en un día malo (1 de cada "
              f"{round(1 / (1 - confianza_var))} días) podrías perder más de **{usd(var_usd)}**; "
              f"cuando eso ocurre, la pérdida promedio ronda **{usd(cvar_usd)}**."]
    frases.append(f"La peor racha del período llevó la inversión a caer **{pct(abs(d['max_drawdown']))}** "
                  f"desde su máximo, es decir, unos **{usd(abs(d['max_drawdown']) * valor_portafolio)}**.")
    if d.get("retorno_acumulado_benchmark") is not None:
        dif = d["retorno_acumulado"] - d["retorno_acumulado_benchmark"]
        frases.append(f"En el mismo período el portafolio {'superó' if dif >= 0 else 'quedó por debajo de'} "
                      f"al {BENCHMARKS.get(benchmark, benchmark)} por **{pct(abs(dif))}**.")
    frases.append(f"Ganaste dinero en el **{pct(d['pct_dias_positivos'], 0)}** de los días negociados.")
    ui.en_simple(" ".join(frases), "Lectura rápida de tu portafolio")

    c1, c2 = st.columns([1.6, 1])
    with c1:
        serie = pd.DataFrame(d["serie_valor"])
        serie["fecha"] = pd.to_datetime(serie["fecha"])
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=serie["fecha"], y=serie["valor"] * valor_portafolio, name="Tu portafolio",
                                 line=dict(color=ui.AZUL, width=2),
                                 hovertemplate="%{x|%d %b %Y}<br>USD %{y:,.0f}<extra>Portafolio</extra>"))
        if d.get("serie_benchmark"):
            sb = pd.DataFrame(d["serie_benchmark"])
            sb["fecha"] = pd.to_datetime(sb["fecha"])
            fig.add_trace(go.Scatter(x=sb["fecha"], y=sb["valor"] * valor_portafolio,
                                     name=BENCHMARKS.get(benchmark, benchmark),
                                     line=dict(color=ui.TINTA_3, width=2, dash="dot"),
                                     hovertemplate="%{x|%d %b %Y}<br>USD %{y:,.0f}<extra>Benchmark</extra>"))
        fig.add_hline(y=valor_portafolio, line_color=ui.EJE, line_width=1)
        fig.update_layout(**ui.layout("Evolución del dinero invertido", 360, yaxis_title="USD",
                                      hovermode="x unified"))
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        dfw = pd.DataFrame({"Activo": list(d["pesos"].keys()), "Peso": list(d["pesos"].values())})
        dfw = dfw.sort_values("Peso")
        fig_w = go.Figure(go.Bar(
            x=dfw["Peso"] * 100, y=dfw["Activo"], orientation="h",
            marker_color=[ui.color_activo(t, tickers) for t in dfw["Activo"]],
            text=[f"{w:.1%}" for w in dfw["Peso"]], textposition="inside", insidetextanchor="end",
            hovertemplate="%{y}: %{x:.1f}%<extra></extra>"))
        fig_w.update_layout(**ui.layout("Composición del portafolio", 360, xaxis_title="% del capital",
                                        legend=False, barcornerradius=4))
        st.plotly_chart(fig_w, use_container_width=True)

    riqueza = serie.set_index("fecha")["valor"]
    dd = riqueza / riqueza.cummax() - 1
    fig_dd = go.Figure(go.Scatter(x=dd.index, y=dd * 100, fill="tozeroy", line=dict(color=ui.ESTADO["critico"], width=1.5),
                                  fillcolor="rgba(208,59,59,0.12)", name="Caída desde el máximo",
                                  hovertemplate="%{x|%d %b %Y}<br>%{y:.1f}%<extra></extra>"))
    fig_dd.update_layout(**ui.layout("Caídas desde el máximo anterior (drawdown)", 240,
                                     yaxis_title="%", legend=False))
    st.plotly_chart(fig_dd, use_container_width=True)
    st.caption("El drawdown muestra, en cada fecha, cuánto estaba el portafolio por debajo de su "
               "mejor valor previo. 0 % significa que estaba en un máximo.")

    ui.guia_lectura("Cómo leer el resumen", [
        {"Indicador": "Rentabilidad anual", "Qué mide": "Ganancia promedio por año en el período.",
         "Rangos de referencia": "Verde si supera la tasa libre de riesgo (lo que pagaría un bono del Tesoro); "
                                 "amarillo si es positiva pero menor; rojo si es negativa."},
        {"Indicador": "Volatilidad anual", "Qué mide": "Tamaño típico de las subidas y bajadas en un año.",
         "Rangos de referencia": "< 15 % baja (bonos, defensivas) · 15–25 % media (índice S&P 500 ≈ 18 %) · "
                                 "25–40 % alta · > 40 % muy alta (cripto, acciones especulativas)."},
        {"Indicador": "Sharpe", "Qué mide": "(Rentabilidad − tasa sin riesgo) ÷ volatilidad.",
         "Rangos de referencia": "≥ 1 bueno · 0.5–1 aceptable · 0–0.5 pobre · < 0 no compensó el riesgo."},
        {"Indicador": "Máximo drawdown", "Qué mide": "La peor caída desde un máximo hasta un mínimo.",
         "Rangos de referencia": "> −10 % leve · −10 a −20 % moderada · −20 a −35 % fuerte · < −35 % severa."},
        {"Indicador": "VaR diario", "Qué mide": f"Pérdida que sólo se supera en {round((1 - confianza_var) * 100, 1)} % de los días.",
         "Rangos de referencia": "Al 95 %: < 1.5 % del capital bajo · 1.5–2.5 % medio · 2.5–4 % alto · > 4 % muy alto. "
                                 "Con otro nivel de confianza los umbrales se ajustan proporcionalmente."},
        {"Indicador": "Beta", "Qué mide": "Sensibilidad a los movimientos del benchmark.",
         "Rangos de referencia": "< 0.8 defensivo · 0.8–1.2 se mueve como el mercado · > 1.2 agresivo. "
                                 "No es bueno ni malo: depende de tu tolerancia al riesgo."},
    ], columnas=("Indicador", "Qué mide", "Rangos de referencia"))


# ─────────────────────────── PRECIOS Y SEÑALES ───────────────────────────
def _senales(ultimo) -> list[tuple]:
    out = []
    rsi = ultimo["rsi"]
    out.append(("RSI (14)", "VENTA" if rsi > 70 else "COMPRA" if rsi < 30 else "NEUTRAL",
                f"{rsi:.1f}", "Sobrecompra (>70)" if rsi > 70 else "Sobreventa (<30)" if rsi < 30 else "Zona normal (30–70)"))
    c = ultimo["close"]
    out.append(("Bandas de Bollinger", "VENTA" if c > ultimo["bollinger_upper"] else
                "COMPRA" if c < ultimo["bollinger_lower"] else "NEUTRAL", f"{c:,.2f}",
                "Precio sobre la banda superior" if c > ultimo["bollinger_upper"] else
                "Precio bajo la banda inferior" if c < ultimo["bollinger_lower"] else "Dentro de las bandas"))
    out.append(("MACD", "COMPRA" if ultimo["macd"] > ultimo["macd_signal"] else "VENTA",
                f"{ultimo['macd']:.3f}", "MACD sobre su señal (impulso alcista)" if ultimo["macd"] > ultimo["macd_signal"]
                else "MACD bajo su señal (impulso bajista)"))
    k = ultimo["stochastic_k"]
    out.append(("Estocástico %K", "VENTA" if k > 80 else "COMPRA" if k < 20 else "NEUTRAL", f"{k:.1f}",
                "Zona alta (>80)" if k > 80 else "Zona baja (<20)" if k < 20 else "Zona media"))
    out.append(("Tendencia (SMA 20 vs 50)", "COMPRA" if ultimo["sma_short"] > ultimo["sma_long"] else "VENTA",
                f"{ultimo['sma_short']:,.2f} / {ultimo['sma_long']:,.2f}",
                "Media corta sobre la larga (tendencia alcista)" if ultimo["sma_short"] > ultimo["sma_long"]
                else "Media corta bajo la larga (tendencia bajista)"))
    return out


def pagina_tecnico():
    cabecera("Precios y señales técnicas",
             "Cómo se ha movido el precio de cada activo y qué sugieren los indicadores técnicos más usados "
             "por los operadores. Son señales de corto plazo, no predicciones seguras.")
    if not requiere_portafolio(1):
        return
    tab_comp, tab_activo, tab_sem = st.tabs(["Comparación de activos", "Gráfico de un activo", "Semáforo técnico"])

    with tab_comp:
        fig = go.Figure()
        filas = []
        for t in tickers:
            df = precios_df(t)
            if df is None or df.empty:
                continue
            base = df["close"] / df["close"].iloc[0] * 100
            fig.add_trace(go.Scatter(x=df["fecha"], y=base, name=t, line=dict(color=ui.color_activo(t, tickers), width=2),
                                     hovertemplate=f"{t}<br>%{{x|%d %b %Y}}<br>%{{y:.1f}}<extra></extra>"))
            filas.append({"Activo": t, "Nombre": TICKERS_DB.get(t, t), "Precio inicial": df["close"].iloc[0],
                          "Precio actual": df["close"].iloc[-1], "Variación": base.iloc[-1] / 100 - 1})
        fig.add_hline(y=100, line_color=ui.EJE, line_width=1)
        fig.update_layout(**ui.layout("Si hubieras invertido 100 al inicio del período...", 420,
                                      yaxis_title="Valor (inicio = 100)", hovermode="x unified"))
        st.plotly_chart(fig, use_container_width=True)
        if filas:
            st.dataframe(pd.DataFrame(filas).style.format({"Precio inicial": "{:,.2f}", "Precio actual": "{:,.2f}",
                                                           "Variación": "{:+.1%}"}),
                         use_container_width=True, hide_index=True)
        ui.en_simple("Todas las líneas arrancan en 100 para poder comparar activos con precios muy distintos. "
                     "Si una línea termina en 130, ese activo ganó 30 % en el período; si termina en 80, perdió 20 %.")

    with tab_activo:
        t = selector_activo("tec_activo")
        df = precios_df(t)
        ind = fetch(f"/analisis/indicadores/{q(t)}", {"fecha_inicio": fi, "fecha_fin": ff})
        if df is None or not ind:
            st.info("No hay datos suficientes para este activo.")
        else:
            di = pd.DataFrame(ind["indicadores"]).T
            di.index = pd.to_datetime(di.index)
            fig = go.Figure()
            fig.add_trace(go.Candlestick(x=df["fecha"], open=df["open"], high=df["high"], low=df["low"],
                                         close=df["close"], name="Precio",
                                         increasing_line_color=ui.ESTADO["bueno"], decreasing_line_color=ui.ESTADO["critico"]))
            fig.add_trace(go.Scatter(x=di.index, y=di["bollinger_upper"], name="Banda superior",
                                     line=dict(color=ui.SERIES[6], width=1, dash="dot")))
            fig.add_trace(go.Scatter(x=di.index, y=di["bollinger_lower"], name="Banda inferior",
                                     line=dict(color=ui.SERIES[6], width=1, dash="dot"),
                                     fill="tonexty", fillcolor="rgba(98,80,214,0.05)"))
            fig.add_trace(go.Scatter(x=di.index, y=di["sma_short"], name="Media 20 días", line=dict(color=ui.AZUL, width=1.5)))
            fig.add_trace(go.Scatter(x=di.index, y=di["sma_long"], name="Media 50 días", line=dict(color=ui.NARANJA, width=1.5)))
            fig.update_layout(**ui.layout(f"{t} — velas japonesas, medias móviles y bandas de Bollinger", 460,
                                          yaxis_title="Precio"), xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)

            c1, c2 = st.columns(2)
            with c1:
                f = go.Figure(go.Scatter(x=di.index, y=di["rsi"], name="RSI", line=dict(color=ui.AZUL, width=1.6)))
                f.add_hrect(y0=70, y1=100, fillcolor="rgba(208,59,59,0.07)", line_width=0)
                f.add_hrect(y0=0, y1=30, fillcolor="rgba(12,163,12,0.07)", line_width=0)
                f.update_layout(**ui.layout("RSI — fuerza relativa (0 a 100)", 260, legend=False))
                f.update_yaxes(range=[0, 100])
                st.plotly_chart(f, use_container_width=True)
            with c2:
                f = go.Figure()
                f.add_trace(go.Bar(x=di.index, y=di["macd_histograma"], name="Histograma",
                                   marker_color=[ui.ESTADO["bueno"] if v >= 0 else ui.ESTADO["critico"] for v in di["macd_histograma"]]))
                f.add_trace(go.Scatter(x=di.index, y=di["macd"], name="MACD", line=dict(color=ui.AZUL, width=1.5)))
                f.add_trace(go.Scatter(x=di.index, y=di["macd_signal"], name="Señal", line=dict(color=ui.NARANJA, width=1.5)))
                f.update_layout(**ui.layout("MACD — impulso de la tendencia", 260))
                st.plotly_chart(f, use_container_width=True)

            sen = _senales(di.iloc[-1])
            st.dataframe(pd.DataFrame(sen, columns=["Indicador", "Señal", "Valor actual", "Lectura"]),
                         use_container_width=True, hide_index=True)

    with tab_sem:
        filas = []
        for t in tickers:
            ind = fetch(f"/analisis/indicadores/{q(t)}", {"fecha_inicio": fi, "fecha_fin": ff}, silencioso=True)
            if not ind or not ind["indicadores"]:
                continue
            ultimo = pd.DataFrame(ind["indicadores"]).T.iloc[-1]
            sen = _senales(ultimo)
            compras = sum(s[1] == "COMPRA" for s in sen)
            ventas = sum(s[1] == "VENTA" for s in sen)
            balance = compras - ventas
            veredicto = ("🟢 Sesgo alcista" if balance >= 2 else "🔴 Sesgo bajista" if balance <= -2 else "🟡 Mixto / neutral")
            filas.append({"Activo": t, "Precio": ultimo["close"], "Veredicto": veredicto,
                          "Señales de compra": compras, "Señales de venta": ventas,
                          "RSI": ultimo["rsi"], **{s[0]: s[1] for s in sen if s[0] != "RSI (14)"}})
        if filas:
            st.dataframe(pd.DataFrame(filas).style.format({"Precio": "{:,.2f}", "RSI": "{:.1f}"}),
                         use_container_width=True, hide_index=True)
        ui.nota("Los indicadores técnicos miran sólo el precio pasado y fallan con frecuencia. "
                "Úsalos como una pista más, nunca como única razón para comprar o vender.", "warn")

    ui.guia_lectura("Cómo leer los indicadores técnicos", [
        {"Indicador": "Velas japonesas", "Qué muestra": "Apertura, máximo, mínimo y cierre de cada día.",
         "Cómo leerlo": "Vela verde: cerró más alto de lo que abrió. Vela roja: cerró más bajo."},
        {"Indicador": "Medias móviles (20 y 50 días)", "Qué muestra": "El precio promedio reciente; suaviza el ruido.",
         "Cómo leerlo": "Media de 20 sobre la de 50 → tendencia alcista. Debajo → bajista."},
        {"Indicador": "Bandas de Bollinger", "Qué muestra": "Media de 20 días ± 2 desviaciones estándar.",
         "Cómo leerlo": "Precio fuera de las bandas = movimiento inusual. Bandas anchas = alta volatilidad."},
        {"Indicador": "RSI", "Qué muestra": "Velocidad de subidas vs bajadas recientes (0–100), método de Wilder.",
         "Cómo leerlo": "> 70 sobrecompra (pudo subir 'demasiado rápido'); < 30 sobreventa; 30–70 normal."},
        {"Indicador": "MACD", "Qué muestra": "Diferencia entre una media rápida (12) y una lenta (26).",
         "Cómo leerlo": "Cruza por encima de su señal → impulso alcista; por debajo → bajista."},
        {"Indicador": "Estocástico", "Qué muestra": "Dónde está el cierre dentro del rango de los últimos 14 días.",
         "Cómo leerlo": "> 80 cerca de máximos recientes; < 20 cerca de mínimos."},
    ], columnas=("Indicador", "Qué muestra", "Cómo leerlo"))


# ─────────────────────────── RENDIMIENTOS ───────────────────────────
def pagina_rendimientos():
    cabecera("Rendimientos y distribución",
             "¿Los movimientos diarios se comportan como una campana de Gauss (distribución normal) o hay "
             "más días extremos de lo esperado? Esto define qué métodos de riesgo son confiables.")
    if not requiere_portafolio(1):
        return

    filas = []
    for t in tickers:
        s = fetch(f"/analisis/rendimientos/{q(t)}", {"fecha_inicio": fi, "fecha_fin": ff}, silencioso=True)
        if s:
            filas.append({"Activo": t, "Rend. anual": s["media_anual"], "Volatilidad anual": s["std_anual"],
                          "Peor día": s["peor_dia"], "Mejor día": s["mejor_dia"], "Asimetría": s["asimetria"],
                          "Curtosis (exceso)": s["curtosis_exceso"], "Máx. drawdown": s["max_drawdown"],
                          "¿Normal?": "Sí" if s["jarque_bera"]["es_normal"] else "No (colas pesadas)"})
    if filas:
        ui.encabezado("Comparación entre activos")
        st.dataframe(pd.DataFrame(filas).style.format({
            "Rend. anual": "{:+.1%}", "Volatilidad anual": "{:.1%}", "Peor día": "{:+.2%}", "Mejor día": "{:+.2%}",
            "Asimetría": "{:.2f}", "Curtosis (exceso)": "{:.2f}", "Máx. drawdown": "{:.1%}"}),
            use_container_width=True, hide_index=True)

    ui.encabezado("Análisis detallado de un activo")
    t = selector_activo("rend_activo")
    s = fetch(f"/analisis/rendimientos/{q(t)}", {"fecha_inicio": fi, "fecha_fin": ff})
    serie = fetch(f"/analisis/rendimientos-serie/{q(t)}", {"fecha_inicio": fi, "fecha_fin": ff})
    if not s or not serie:
        return
    r = pd.DataFrame(serie["serie"])
    r["fecha"] = pd.to_datetime(r["fecha"])
    rv = r["rendimiento"].values

    colas = s["curtosis_exceso"] > 1
    ui.kpi_grid([
        {"label": "Rendimiento diario promedio", "value": pct(s["media_diaria"], 3),
         "sub": f"≈ {pct(s['media_anual'])} al año"},
        {"label": "Volatilidad diaria", "value": pct(s["std_diaria"]),
         "sub": f"≈ {pct(s['std_anual'])} al año", "estado": est_vol(s["std_anual"])},
        {"label": "Asimetría", "value": num(s["asimetria"]),
         "sub": "Negativa: caídas fuertes más frecuentes que subidas fuertes",
         "estado": "alerta" if s["asimetria"] < -0.5 else "neutral"},
        {"label": "Curtosis en exceso", "value": num(s["curtosis_exceso"]),
         "sub": "0 = normal · > 0 = colas pesadas", "estado": "serio" if s["curtosis_exceso"] > 3 else
         "alerta" if colas else "bueno", "tag": "Colas pesadas" if colas else "Cercana a normal"},
        {"label": "Días extremos (> 3σ)", "value": f"{s['dias_extremos_obs_pct']:.2f}%",
         "sub": f"La normal predice {s['dias_extremos_normal_pct']:.2f}%",
         "estado": "serio" if s["dias_extremos_obs_pct"] > 2 * s["dias_extremos_normal_pct"] else "neutral"},
    ])

    c1, c2 = st.columns(2)
    with c1:
        mu, sd = rv.mean(), rv.std(ddof=1)
        x = np.linspace(rv.min(), rv.max(), 300)
        fig = go.Figure()
        fig.add_trace(go.Histogram(x=rv * 100, nbinsx=70, histnorm="probability density", name="Datos reales",
                                   marker_color=ui.AZUL, opacity=0.75))
        fig.add_trace(go.Scatter(x=x * 100, y=sp_stats.norm.pdf(x, mu, sd) / 100, name="Curva normal teórica",
                                 line=dict(color=ui.NARANJA, width=2)))
        fig.update_layout(**ui.layout("Histograma vs distribución normal", 340, xaxis_title="Rendimiento diario (%)",
                                      yaxis_title="Densidad", bargap=0.02))
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        z = np.sort((rv - mu) / sd)
        teo = sp_stats.norm.ppf((np.arange(1, len(z) + 1) - 0.5) / len(z))
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=teo, y=z, mode="markers", name="Datos", marker=dict(color=ui.AZUL, size=4, opacity=0.6)))
        lim = [teo.min(), teo.max()]
        fig.add_trace(go.Scatter(x=lim, y=lim, name="Si fuera normal", line=dict(color=ui.NARANJA, dash="dash", width=2)))
        fig.update_layout(**ui.layout("Gráfico Q-Q (cuantiles)", 340, xaxis_title="Cuantil teórico normal (σ)",
                                      yaxis_title="Cuantil observado (σ)"))
        st.plotly_chart(fig, use_container_width=True)

    fig = go.Figure(go.Bar(x=r["fecha"], y=r["rendimiento"] * 100, marker_color=ui.AZUL, name="Rendimiento",
                           hovertemplate="%{x|%d %b %Y}<br>%{y:.2f}%<extra></extra>"))
    fig.update_layout(**ui.layout(f"Rendimientos diarios de {t}", 260, yaxis_title="%", legend=False, bargap=0))
    st.plotly_chart(fig, use_container_width=True)

    jb, sw = s["jarque_bera"], s["shapiro_wilk"]
    if jb["es_normal"] and sw["es_normal"]:
        ui.nota(f"Las pruebas no rechazan la normalidad para {t} (p-values {jb['p_value']:.3f} y {sw['p_value']:.3f}). "
                "El VaR paramétrico (normal) es razonable.", "ok", "Distribución compatible con la normal")
    else:
        ui.nota(f"Las pruebas de Jarque-Bera (p = {jb['p_value']:.4f}) y Shapiro-Wilk (p = {sw['p_value']:.4f}) "
                f"rechazan la normalidad. {t} tiene más días extremos de lo que predice la campana de Gauss, "
                "así que el VaR normal tiende a **subestimar** el riesgo. Prefiere el VaR histórico, Cornish-Fisher "
                "o Monte Carlo con t de Student (módulo VaR).", "warn", "Los rendimientos NO son normales")

    ui.guia_lectura("Cómo leer las propiedades de los rendimientos", [
        {"Concepto": "Rendimiento logarítmico", "Qué es": "ln(Pₜ / Pₜ₋₁). Muy parecido al % de cambio diario.",
         "Cómo leerlo": "Se usan porque se pueden sumar en el tiempo: el rendimiento de una semana es la suma de sus días."},
        {"Concepto": "Histograma", "Qué es": "Cuántos días tuvieron cada tamaño de rendimiento.",
         "Cómo leerlo": "Si las barras sobresalen de la curva en el centro y en los extremos → colas pesadas."},
        {"Concepto": "Gráfico Q-Q", "Qué es": "Compara los datos ordenados con lo que daría una normal.",
         "Cómo leerlo": "Puntos sobre la línea = normal. Si los extremos se 'despegan' en forma de S, hay colas pesadas."},
        {"Concepto": "Asimetría", "Qué es": "Si la distribución está inclinada hacia un lado.",
         "Cómo leerlo": "≈ 0 simétrica · < 0 caídas grandes más frecuentes (típico en acciones) · > 0 subidas grandes."},
        {"Concepto": "Curtosis en exceso", "Qué es": "Qué tan gruesas son las colas comparadas con la normal.",
         "Cómo leerlo": "0 = normal · 0–1 leve · 1–3 colas pesadas · > 3 colas muy pesadas (crisis más probables)."},
        {"Concepto": "Pruebas de normalidad (p-value)", "Qué es": "Jarque-Bera y Shapiro-Wilk. H₀: los datos son normales.",
         "Cómo leerlo": "p > 0.05 → no hay evidencia contra la normalidad. p < 0.05 → se rechaza: NO son normales."},
    ], columnas=("Concepto", "Qué es", "Cómo leerlo"))


# ─────────────────────────── VOLATILIDAD ───────────────────────────
def pagina_volatilidad():
    cabecera("Volatilidad condicional — EWMA y GARCH",
             "La volatilidad no es constante: hay épocas tranquilas y épocas nerviosas que se agrupan "
             "('volatility clustering'). Estos modelos la siguen día a día y la pronostican.")
    if not requiere_portafolio(1):
        return

    filas = []
    for t in tickers:
        e = fetch(f"/analisis/ewma/{q(t)}", {"fecha_inicio": fi, "fecha_fin": ff}, silencioso=True)
        if e:
            filas.append({"Activo": t, "Histórica": e["volatilidad_historica"], "EWMA (hoy)": e["volatilidad_ewma"]})
    if filas:
        dv = pd.DataFrame(filas)
        fig = go.Figure()
        fig.add_trace(go.Bar(x=dv["Activo"], y=dv["Histórica"] * 100, name="Promedio del período", marker_color=ui.ROL["referencia"]))
        fig.add_trace(go.Bar(x=dv["Activo"], y=dv["EWMA (hoy)"] * 100, name="Actual (EWMA)", marker_color=ui.AZUL))
        fig.update_layout(**ui.layout("¿Está cada activo más nervioso que su promedio?", 320,
                                      yaxis_title="Volatilidad anual (%)", barmode="group", barcornerradius=4))
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Si la barra azul (hoy) es más alta que la gris (promedio), el activo atraviesa un período "
                   "más agitado de lo normal.")

    ui.encabezado("Modelos para un activo")
    t = selector_activo("vol_activo")
    with st.spinner("Ajustando 6 modelos GARCH..."):
        e = fetch(f"/analisis/ewma/{q(t)}", {"fecha_inicio": fi, "fecha_fin": ff})
        g = fetch(f"/analisis/garch/{q(t)}", {"fecha_inicio": fi, "fecha_fin": ff})
    if not e or not g or "error" in g:
        st.info("No fue posible ajustar los modelos para este activo.")
        return

    ui.kpi_grid([
        {"label": "Volatilidad histórica", "value": pct(e["volatilidad_historica"]),
         "sub": "Promedio de todo el período", "estado": est_vol(e["volatilidad_historica"])},
        {"label": "EWMA (pronóstico mañana)", "value": pct(e["volatilidad_ewma"]),
         "sub": f"λ = {e['lambda']}", "estado": est_vol(e["volatilidad_ewma"])},
        {"label": f"{g['mejor_modelo']} (hoy)", "value": pct(g["volatilidad_actual_anual"]),
         "sub": f"Pronóstico próximo mes: {pct(g['pronostico_21d_anual'])}", "estado": est_vol(g["volatilidad_actual_anual"])},
        {"label": "Volatilidad de largo plazo", "value": pct(g.get("volatilidad_largo_plazo_anual")),
         "sub": "Nivel al que tiende a regresar"},
        {"label": "Persistencia", "value": num(g["persistencia"], 3),
         "sub": f"Vida media de un choque: {num(g.get('vida_media_dias'), 0)} días",
         "estado": "critico" if g["persistencia"] >= 0.99 else "alerta" if g["persistencia"] > 0.95 else "bueno"},
    ])

    df = precios_df(t)
    fig = go.Figure()
    if df is not None and not df.empty:
        rl = np.log(df["close"] / df["close"].shift(1))
        movil = rl.rolling(21).std() * np.sqrt(252) * 100
        fig.add_trace(go.Scatter(x=df["fecha"], y=movil, name="Móvil 21 días", line=dict(color=ui.TINTA_3, width=1.2)))
    se = pd.DataFrame(e["serie"])
    fig.add_trace(go.Scatter(x=pd.to_datetime(se["fecha"]), y=se["vol_anual"] * 100, name="EWMA",
                             line=dict(color=ui.SERIES[0], width=2)))
    sg = pd.DataFrame(g["serie_volatilidad"])
    fig.add_trace(go.Scatter(x=pd.to_datetime(sg["fecha"]), y=sg["vol_anual"] * 100, name=g["mejor_modelo"],
                             line=dict(color=ui.SERIES[1], width=2)))
    if g.get("volatilidad_largo_plazo_anual"):
        fig.add_hline(y=g["volatilidad_largo_plazo_anual"] * 100, line_dash="dash", line_color=ui.EJE,
                      annotation_text="Largo plazo", annotation_font_color=ui.TINTA_2)
    fig.update_layout(**ui.layout(f"Volatilidad anualizada de {t} a lo largo del tiempo", 380,
                                  yaxis_title="Volatilidad anual (%)", hovermode="x unified"))
    st.plotly_chart(fig, use_container_width=True)

    c1, c2 = st.columns([1.2, 1])
    with c1:
        tabla = pd.DataFrame(g["tabla_comparativa"]).sort_values("aic")
        tabla["Elegido"] = np.where(tabla["modelo"] == g["mejor_modelo"], "⭐", "")
        tabla = tabla[["Elegido", "modelo", "aic", "bic", "loglik", "persistencia"]]
        tabla.columns = ["", "Modelo", "AIC", "BIC", "Log-verosimilitud", "Persistencia"]
        st.markdown("**Comparación de modelos (menor AIC = mejor)**")
        st.dataframe(tabla.style.format({"AIC": "{:.1f}", "BIC": "{:.1f}", "Log-verosimilitud": "{:.1f}",
                                         "Persistencia": "{:.3f}"}), use_container_width=True, hide_index=True)
    with c2:
        lm = g["arch_lm"]
        if lm["sin_efectos_arch"]:
            ui.nota(f"Test ARCH-LM sobre los residuos: p = {lm['p_value']:.3f} > 0.05. El modelo capturó "
                    "bien la dinámica de la volatilidad.", "ok", "Diagnóstico del modelo: adecuado")
        else:
            ui.nota(f"Test ARCH-LM: p = {lm['p_value']:.3f} < 0.05. Queda algo de agrupamiento de volatilidad "
                    "sin explicar; el pronóstico debe tomarse con cautela.", "warn", "Diagnóstico del modelo")
        params = ", ".join(f"{k} = {v:.4f}" for k, v in g["parametros"].items())
        st.caption(f"Parámetros estimados de {g['mejor_modelo']}: {params}")

    ui.en_simple(
        f"Hoy {t} tiene una volatilidad anual estimada de {pct(g['volatilidad_actual_anual'])}, frente a "
        f"{pct(e['volatilidad_historica'])} de promedio en el período. Un choque de volatilidad tarda unos "
        f"{num(g.get('vida_media_dias'), 0)} días en reducirse a la mitad.")

    ui.guia_lectura("Cómo leer los modelos de volatilidad", [
        {"Concepto": "Volatilidad anualizada", "Qué es": "Desviación estándar diaria × √252 (días hábiles del año).",
         "Cómo leerlo": "20 % significa que, en un año típico, el rendimiento suele moverse ±20 % alrededor de su promedio."},
        {"Concepto": "EWMA (RiskMetrics)", "Qué es": "Promedio que da más peso a los días recientes (λ = 0.94).",
         "Cómo leerlo": "Reacciona rápido a sustos del mercado. Útil para el VaR diario de bancos."},
        {"Concepto": "GARCH / GJR / EGARCH", "Qué es": "Modelos estadísticos donde la volatilidad de hoy depende de los choques y la volatilidad de ayer.",
         "Cómo leerlo": "GJR y EGARCH permiten que las caídas aumenten más la volatilidad que las subidas (efecto apalancamiento)."},
        {"Concepto": "AIC / BIC", "Qué es": "Criterios que premian el buen ajuste y castigan la complejidad.",
         "Cómo leerlo": "Se elige el modelo con el valor más bajo."},
        {"Concepto": "Persistencia", "Qué es": "Qué tanto 'recuerda' el modelo los choques pasados.",
         "Cómo leerlo": ("bueno", "< 0.95 los choques se disipan rápido · 0.95–0.99 se disipan lento · ≥ 0.99 casi permanentes")},
        {"Concepto": "Vida media", "Qué es": "Días para que un choque de volatilidad se reduzca a la mitad.",
         "Cómo leerlo": "Ej.: 30 días → un susto de mercado tarda ~1 mes y medio en calmarse a la mitad."},
        {"Concepto": "Test ARCH-LM", "Qué es": "Revisa si queda volatilidad agrupada sin explicar en los residuos.",
         "Cómo leerlo": "p > 0.05 el modelo es adecuado · p < 0.05 el modelo deja patrones sin capturar."},
    ], columnas=("Concepto", "Qué es", "Cómo leerlo"))


# ─────────────────────────── VaR y CVaR ───────────────────────────
def pagina_var():
    cabecera("Valor en Riesgo (VaR) y Expected Shortfall (CVaR)",
             f"¿Cuánto podrías perder en un mal día? El VaR al {nivel_txt()} es la pérdida que sólo se "
             f"supera en {round((1 - confianza_var) * 100, 1)} de cada 100 días. El CVaR dice cuánto pierdes "
             "en promedio cuando ese límite se rompe.")
    if not requiere_portafolio():
        return
    vp = fetch("/analisis/var-portafolio", {**P_BASE, "nivel": confianza_var})
    if not vp:
        return

    V = valor_portafolio
    ui.encabezado("Portafolio completo (horizonte: 1 día)")
    ui.kpi_grid([
        {"label": "VaR histórico", "value": usd(abs(vp["var_historico_portafolio"]) * V),
         "sub": f"{pct(abs(vp['var_historico_portafolio']))} · basado en días reales",
         "estado": est_var(abs(vp["var_historico_portafolio"]))},
        {"label": "VaR paramétrico (normal)", "value": usd(abs(vp["var_parametrico_portafolio"]) * V),
         "sub": pct(abs(vp["var_parametrico_portafolio"]))},
        {"label": "VaR Monte Carlo", "value": usd(abs(vp["var_montecarlo_portafolio"]) * V),
         "sub": "10.000 escenarios con correlaciones"},
        {"label": "CVaR histórico", "value": usd(abs(vp["cvar_historico_portafolio"]) * V),
         "sub": "Pérdida promedio en los días peores al VaR", "estado": est_var(abs(vp["cvar_historico_portafolio"]) * 0.8)},
        {"label": "VaR a 10 días (regla √t)", "value": usd(abs(vp["var_historico_portafolio"]) * np.sqrt(10) * V),
         "sub": "Horizonte regulatorio de Basilea"},
    ])

    c1, c2 = st.columns(2)
    with c1:
        suma = abs(vp["suma_var_individuales"]) * V
        port = abs(vp["var_parametrico_portafolio"]) * V
        fig = go.Figure(go.Bar(
            x=["Suma de los VaR por separado", "VaR del portafolio"], y=[suma, port],
            marker_color=[ui.TINTA_3, ui.AZUL], text=[usd(suma), usd(port)], textposition="outside", width=0.5))
        fig.update_layout(**ui.layout("Efecto de la diversificación (VaR paramétrico)", 330, yaxis_title="USD",
                                      legend=False, barcornerradius=4))
        st.plotly_chart(fig, use_container_width=True)
        ui.en_simple(f"Si cada activo se evaluara solo, el riesgo sumaría {usd(suma)}. Como no todos caen el mismo "
                     f"día, el riesgo conjunto es {usd(port)}: diversificar te ahorra {usd(suma - port)} de VaR.")
    with c2:
        dc = pd.DataFrame(vp["contribucion_por_activo"]).sort_values("contribucion_pct")
        fig = go.Figure(go.Bar(
            x=dc["contribucion_pct"] * 100, y=dc["ticker"], orientation="h",
            marker_color=[ui.color_activo(t, tickers) for t in dc["ticker"]],
            text=[f"{c:.0%} del riesgo · {w:.0%} del capital" for c, w in zip(dc["contribucion_pct"], dc["peso"])],
            textposition="auto", hovertemplate="%{y}: %{x:.1f}% del VaR<extra></extra>"))
        fig.update_layout(**ui.layout("¿Quién aporta el riesgo? (VaR por componentes)", 330,
                                      xaxis_title="% del VaR total", legend=False, barcornerradius=4))
        st.plotly_chart(fig, use_container_width=True)
        top = dc.iloc[-1]
        ui.en_simple(f"**{top['ticker']}** pesa {pct(top['peso'], 0)} del capital pero aporta "
                     f"{pct(top['contribucion_pct'], 0)} del riesgo. Un activo que aporta más riesgo que peso "
                     "es el primer candidato a reducir si quieres bajar el VaR.")

    ui.encabezado("Análisis por activo")
    cc1, cc2 = st.columns([2, 1])
    with cc1:
        t = selector_activo("var_activo")
    with cc2:
        h = st.radio("Horizonte", [1, 5, 10], horizontal=True, format_func=lambda x: f"{x} día{'s' if x > 1 else ''}",
                     key="var_h")
    dv = fetch(f"/analisis/var/{q(t)}", {"nivel": confianza_var, "horizonte": h, "fecha_inicio": fi, "fecha_fin": ff})
    serie = fetch(f"/analisis/rendimientos-serie/{q(t)}", {"fecha_inicio": fi, "fecha_fin": ff})
    if not dv:
        return
    capital = V * pesos.get(t, 0)
    metodos = [
        ("Paramétrico (normal)", dv["var_parametrico"], "Supone campana de Gauss. Rápido, pero subestima si hay colas pesadas."),
        ("Cornish-Fisher", dv["var_cornish_fisher"], "Normal corregida por asimetría y curtosis."),
        ("Histórico", dv["var_historico"], "Percentil de los días reales. No supone ninguna distribución."),
        ("Monte Carlo (t de Student)", dv["var_montecarlo"], "10.000 simulaciones con colas pesadas."),
        ("CVaR histórico", dv["cvar"], "Promedio de las pérdidas peores que el VaR histórico."),
        ("CVaR paramétrico", dv["cvar_parametrico"], "Expected Shortfall bajo normalidad."),
    ]
    tabla = pd.DataFrame([{"Método": m, "Pérdida (%)": abs(v), f"Sobre USD 100.000": abs(v) * 100_000,
                           f"Sobre tu posición en {t}": abs(v) * capital, "Idea": idea} for m, v, idea in metodos])
    c1, c2 = st.columns([1.15, 1])
    with c1:
        st.dataframe(tabla.style.format({"Pérdida (%)": "{:.2%}", "Sobre USD 100.000": "USD {:,.0f}",
                                         f"Sobre tu posición en {t}": "USD {:,.0f}"}),
                     use_container_width=True, hide_index=True, height=260)
        st.caption(f"Tu posición en {t}: {usd(capital)} ({pct(pesos.get(t, 0), 1)} del portafolio). "
                   f"Horizonte: {h} día(s); para más de 1 día se usa la regla de la raíz del tiempo.")
    with c2:
        if serie:
            rv = np.array([x["rendimiento"] for x in serie["serie"]]) * 100
            fig = go.Figure(go.Histogram(x=rv, nbinsx=70, marker_color=ui.AZUL, opacity=0.7, name="Días"))
            for nombre, val, col in [("VaR histórico 1d", dv["var_historico"] / np.sqrt(h), ui.ESTADO["serio"]),
                                     ("CVaR 1d", dv["cvar"] / np.sqrt(h), ui.ESTADO["critico"])]:
                fig.add_vline(x=val * 100, line_color=col, line_width=2, line_dash="dash",
                              annotation_text=nombre, annotation_font_color=col, annotation_position="top left")
            fig.update_layout(**ui.layout(f"Rendimientos diarios de {t} y la cola de pérdidas", 300,
                                          xaxis_title="Rendimiento diario (%)", yaxis_title="Número de días",
                                          legend=False, bargap=0.02))
            st.plotly_chart(fig, use_container_width=True)

    k = dv.get("kupiec") or {}
    if k.get("disponible"):
        zona_est = {"verde": "bueno", "amarilla": "alerta", "roja": "critico"}[k["zona"]]
        ui.encabezado("¿El VaR histórico funciona? Backtesting de Kupiec (fuera de muestra)",
                      f"Cada día se calcula el VaR sólo con los {k['ventana']} días anteriores y se comprueba si "
                      "la pérdida real lo superó.")
        ui.kpi_grid([
            {"label": "Días evaluados", "value": f"{k['n']:,}"},
            {"label": "Excepciones esperadas", "value": num(k["excepciones_esperadas"], 1),
             "sub": f"{pct(k['p_esperado'], 1)} de los días"},
            {"label": "Excepciones observadas", "value": f"{k['excepciones']}",
             "sub": f"{pct(k['p_observado'], 1)} de los días"},
            {"label": "p-value de Kupiec", "value": num(k["p_value"], 3),
             "estado": "bueno" if k["aprobado"] else "critico",
             "tag": "Modelo aceptado" if k["aprobado"] else "Modelo rechazado"},
            {"label": "Zona tipo Basilea", "value": k["zona"].capitalize(), "estado": zona_est},
        ])
        if k["aprobado"]:
            ui.nota("La frecuencia de pérdidas mayores al VaR es estadísticamente coherente con el nivel de "
                    "confianza elegido: el VaR está bien calibrado.", "ok")
        else:
            mas = k["p_observado"] > k["p_esperado"]
            ui.nota("El VaR " + ("se rompe con más frecuencia de la esperada: está **subestimando** el riesgo."
                                 if mas else "casi nunca se rompe: es **demasiado conservador**.")
                    + " Considera otro método o un período distinto.", "bad", "El VaR no está bien calibrado")

    ui.guia_lectura("Cómo leer el VaR y el CVaR", [
        {"Concepto": "VaR al 95 %, 1 día", "Qué significa": "Pérdida que no se supera en 95 de cada 100 días.",
         "Ejemplo / referencia": "VaR = USD 2.000 → aprox. 1 día al mes (de ~20 hábiles) perderías más de USD 2.000."},
        {"Concepto": "CVaR (Expected Shortfall)", "Qué significa": "Pérdida promedio en el 5 % de peores días.",
         "Ejemplo / referencia": "Siempre es mayor que el VaR. Basilea III lo usa (al 97.5 %) porque mira 'qué tan mala' es la cola."},
        {"Concepto": "Diferencia entre métodos", "Qué significa": "Si histórico/Monte Carlo/Cornish-Fisher dan pérdidas mayores que el normal…",
         "Ejemplo / referencia": "…los datos tienen colas pesadas y el VaR normal subestima el riesgo."},
        {"Concepto": "VaR por componentes", "Qué significa": "Qué parte del VaR total viene de cada activo (suman 100 %).",
         "Ejemplo / referencia": "Puede ser negativo: un activo que tiende a subir cuando los demás caen REDUCE el riesgo."},
        {"Concepto": "Regla de la raíz del tiempo", "Qué significa": "VaR de h días ≈ VaR de 1 día × √h.",
         "Ejemplo / referencia": "VaR 10 días ≈ 3.16 × VaR diario. Supone días independientes."},
        {"Concepto": "Backtesting de Kupiec", "Qué significa": "Prueba si las excepciones observadas son coherentes con las esperadas.",
         "Ejemplo / referencia": ("bueno", "p > 0.05 VaR bien calibrado · p < 0.05 VaR mal calibrado")},
        {"Concepto": "Zonas de Basilea", "Qué significa": "Semáforo regulatorio según el número de excepciones.",
         "Ejemplo / referencia": "Verde: normal · Amarilla: vigilar · Roja: el modelo falla (el regulador penaliza)."},
    ], columnas=("Concepto", "Qué significa", "Ejemplo / referencia"))


# ─────────────────────────── STRESS TEST ───────────────────────────
def pagina_stress():
    cabecera("Pruebas de estrés",
             "El VaR describe días 'malos pero normales'. Las pruebas de estrés preguntan qué pasaría en una "
             "crisis: caídas del mercado, volatilidad disparada o la desaparición de la diversificación.")
    if not requiere_portafolio():
        return
    d = fetch("/analisis/stress-test", {**P_BASE, "benchmark": benchmark})
    if not d:
        return
    esc = pd.DataFrame(d["escenarios"])
    esc["usd"] = esc["impacto_portafolio"] * valor_portafolio
    peor = esc.loc[esc["impacto_portafolio"].idxmin()]

    def est_imp(x):
        return "bueno" if x > -0.05 else "alerta" if x > -0.10 else "serio" if x > -0.20 else "critico"

    hist = esc[esc["tipo"] == "historico"]
    ui.kpi_grid([
        {"label": "Peor escenario evaluado", "value": usd(peor["usd"]), "sub": peor["escenario"],
         "estado": est_imp(peor["impacto_portafolio"]), "tag": pct(peor["impacto_portafolio"], 1)},
        {"label": "Si el mercado cae 20 %", "value": pct(esc.iloc[1]["impacto_portafolio"], 1),
         "sub": usd(esc.iloc[1]["usd"]), "estado": est_imp(esc.iloc[1]["impacto_portafolio"])},
        {"label": "Peor mes real del período", "value": pct(hist.iloc[-1]["impacto_portafolio"], 1) if len(hist) else "—",
         "sub": f"{hist.iloc[-1]['fecha_inicio']} → {hist.iloc[-1]['fecha_fin']}" if len(hist) else "",
         "estado": est_imp(hist.iloc[-1]["impacto_portafolio"]) if len(hist) else None},
        {"label": "Beta del portafolio", "value": num(sum(d["pesos"][t] * d["betas"][t] for t in d["pesos"])),
         "sub": f"Calculada contra {BENCHMARKS.get(d['benchmark'], d['benchmark'])}" if d["fuente_beta"] == "benchmark"
         else "Aproximada con el promedio del portafolio"},
    ])

    orden = esc.sort_values("impacto_portafolio", ascending=False)
    fig = go.Figure(go.Bar(
        x=orden["usd"], y=orden["escenario"], orientation="h",
        marker_color=[ui.ESTADO[est_imp(v)] for v in orden["impacto_portafolio"]],
        text=[f"{pct(v, 1)} · {usd(u)}" for v, u in zip(orden["impacto_portafolio"], orden["usd"])],
        textposition="auto", hovertemplate="%{y}<br>USD %{x:,.0f}<extra></extra>"))
    fig.update_layout(**ui.layout("Pérdida del portafolio en cada escenario", 420, xaxis_title="USD",
                                  legend=False, barcornerradius=4))
    st.plotly_chart(fig, use_container_width=True)

    c1, c2 = st.columns([1.3, 1])
    with c1:
        activos = list(d["pesos"].keys())
        z = [[e["impactos_por_activo"][a] * 100 for e in d["escenarios"]] for a in activos]
        lim = max(abs(np.min(z)), abs(np.max(z)), 1)
        fig = go.Figure(go.Heatmap(z=z, x=[e["escenario"] for e in d["escenarios"]], y=activos,
                                   colorscale=ui.DIVERGENTE, zmid=0, zmin=-lim, zmax=lim,
                                   text=[[f"{v:.1f}%" for v in fila] for fila in z], texttemplate="%{text}",
                                   colorbar=dict(title="%"), xgap=2, ygap=2,
                                   hovertemplate="%{y} · %{x}<br>%{z:.1f}%<extra></extra>"))
        fig.update_layout(**ui.layout("Impacto por activo y escenario", 380, legend=False))
        fig.update_xaxes(tickangle=-30)
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        st.markdown("**Descripción de cada escenario**")
        st.dataframe(esc[["escenario", "descripcion"]].rename(columns={"escenario": "Escenario",
                                                                      "descripcion": "Qué supone"}),
                     use_container_width=True, hide_index=True, height=380)

    corr = esc[esc["tipo"] == "correlacion"]
    if len(corr):
        r = corr.iloc[0]
        ui.en_simple(f"Hoy, con las correlaciones actuales, una pérdida extrema a 10 días (99 %) sería de "
                     f"{pct(abs(r['impacto_con_correlacion_actual']), 1)}. Si en una crisis todos los activos se "
                     f"movieran juntos, sería de {pct(abs(r['impacto_portafolio']), 1)}. Esa diferencia es lo que "
                     "la diversificación te protege… y lo que puedes perder justo cuando más la necesitas.")

    ui.guia_lectura("Cómo leer las pruebas de estrés", [
        {"Escenario": "Choques de mercado (−10 %, −20 %, −34 %)", "Cómo se calcula": "Impacto = beta del activo × caída del mercado.",
         "Cómo leerlo": "Activos con beta alta sufren más. Un portafolio con beta 0.7 caería ~14 % si el mercado cae 20 %."},
        {"Escenario": "Volatilidad se duplica", "Cómo se calcula": "Pérdida al 99 % en 10 días con el doble de volatilidad.",
         "Cómo leerlo": "Simula episodios como marzo de 2020, cuando la volatilidad se multiplicó."},
        {"Escenario": "Correlaciones → 1", "Cómo se calcula": "Pérdida al 99 % en 10 días si todos los activos se mueven igual.",
         "Cómo leerlo": "Mide cuánto depende tu protección de la diversificación."},
        {"Escenario": "Peor día / semana / mes observado", "Cómo se calcula": "La peor ventana real del portafolio en el período elegido.",
         "Cómo leerlo": "No es hipotético: ya ocurrió. Amplía el período (hasta 3 años) para incluir más crisis."},
        {"Escenario": "Colores", "Cómo se calcula": "Según la pérdida del portafolio.",
         "Cómo leerlo": ("critico", "> −5 % leve · −5 a −10 % moderada · −10 a −20 % severa · < −20 % crítica")},
    ], columnas=("Escenario", "Cómo se calcula", "Cómo leerlo"))


# ─────────────────────────── CAPM ───────────────────────────
def pagina_capm():
    cabecera("CAPM y riesgo de mercado",
             "El CAPM separa el riesgo de cada activo en dos partes: el que viene del mercado (no se puede "
             "diversificar, se mide con beta) y el propio de la empresa (se reduce diversificando).")
    if not requiere_portafolio(1):
        return
    d = fetch("/analisis/capm", {"tickers": tickers, "benchmark": benchmark, "tasa_libre_riesgo": tasa_fred,
                                 "fecha_inicio": fi, "fecha_fin": ff})
    if not d:
        return
    df = pd.DataFrame(d["activos"])
    rf, rm = df.iloc[0]["tasa_libre_riesgo_anual"], df.iloc[0]["rendimiento_mercado_anual"]

    ui.kpi_grid([
        {"label": "Tasa libre de riesgo (rf)", "value": pct(rf), "sub": fuente_rf},
        {"label": f"Rendimiento del mercado", "value": pct(rm), "sub": BENCHMARKS.get(benchmark, benchmark)},
        {"label": "Prima de riesgo de mercado", "value": pct(rm - rf), "sub": "Lo que paga el mercado sobre rf",
         "estado": "bueno" if rm > rf else "alerta"},
        {"label": "Beta promedio ponderada", "value": num(sum(pesos.get(t, 0) * b for t, b in zip(df["ticker"], df["beta"]))),
         "sub": "Sensibilidad de tu portafolio"},
    ])

    tabla = df[["ticker", "beta", "clasificacion", "r_cuadrado", "rendimiento_observado_anual",
                "rendimiento_esperado_capm", "alpha_jensen", "alpha_p_value"]].copy()
    tabla["¿Alfa significativo?"] = np.where(df["alpha_significativo"], "Sí (p < 0.05)", "No")
    tabla.columns = ["Activo", "Beta", "Tipo", "R²", "Rend. observado", "Rend. exigido (CAPM)",
                     "Alfa de Jensen", "p-value alfa", "¿Alfa significativo?"]
    st.dataframe(tabla.style.format({"Beta": "{:.2f}", "R²": "{:.0%}", "Rend. observado": "{:+.1%}",
                                     "Rend. exigido (CAPM)": "{:.1%}", "Alfa de Jensen": "{:+.1%}",
                                     "p-value alfa": "{:.3f}"}), use_container_width=True, hide_index=True)

    c1, c2 = st.columns(2)
    with c1:
        bmax = max(2.0, df["beta"].max() * 1.15)
        b = np.linspace(min(0, df["beta"].min() * 1.1), bmax, 50)
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=b, y=(rf + b * (rm - rf)) * 100, name="SML: rendimiento exigido",
                                 line=dict(color=ui.TINTA_3, width=2, dash="dash")))
        for _, r in df.iterrows():
            col = ui.color_activo(r["ticker"], tickers)
            fig.add_trace(go.Scatter(x=[r["beta"], r["beta"]], y=[r["rendimiento_esperado_capm"] * 100,
                                                                   r["rendimiento_observado_anual"] * 100],
                                     mode="lines", line=dict(color=col, width=1), showlegend=False, hoverinfo="skip"))
            fig.add_trace(go.Scatter(x=[r["beta"]], y=[r["rendimiento_observado_anual"] * 100], mode="markers+text",
                                     text=[r["ticker"]], textposition="top center", name=r["ticker"],
                                     marker=dict(color=col, size=11, line=dict(color="white", width=2)),
                                     hovertemplate=f"{r['ticker']}<br>β = %{{x:.2f}}<br>Observado: %{{y:.1f}}%<extra></extra>"))
        fig.update_layout(**ui.layout("Línea del Mercado de Valores (SML)", 400, xaxis_title="Beta (β)",
                                      yaxis_title="Rendimiento anual (%)", legend=False))
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Puntos SOBRE la línea rindieron más de lo que exige su riesgo (alfa positivo); "
                   "puntos DEBAJO rindieron menos. La línea vertical es el alfa.")
    with c2:
        var_sist = df["r_cuadrado"] * 100
        fig = go.Figure()
        fig.add_trace(go.Bar(y=df["ticker"], x=var_sist, orientation="h", name="Sistemático (mercado)",
                             marker_color=ui.SERIES[0], hovertemplate="%{y}: %{x:.0f}%<extra>Sistemático</extra>"))
        fig.add_trace(go.Bar(y=df["ticker"], x=100 - var_sist, orientation="h", name="Propio de la empresa",
                             marker_color=ui.SERIES[2], hovertemplate="%{y}: %{x:.0f}%<extra>Idiosincrático</extra>"))
        fig.update_layout(**ui.layout("¿De dónde viene el riesgo de cada activo?", 400,
                                      xaxis_title="% de la varianza", barmode="stack"))
        st.plotly_chart(fig, use_container_width=True)
        st.caption("La parte azul (R²) se explica por el mercado. La verde es riesgo propio y se puede "
                   "reducir combinando activos distintos.")

    mejor = df.loc[df["alpha_jensen"].idxmax()]
    ui.en_simple(f"{mejor['ticker']} tuvo el mayor alfa ({pct(mejor['alpha_jensen'], 1, True)} anual): rindió por encima de "
                 f"lo que su beta de {mejor['beta']:.2f} exigía. "
                 + ("Además el alfa es estadísticamente significativo." if mejor["alpha_significativo"] else
                    "Sin embargo, el alfa NO es estadísticamente significativo: podría deberse al azar."))

    ui.guia_lectura("Cómo leer el CAPM", [
        {"Indicador": "Beta (β)", "Qué mide": "Cuánto se mueve el activo por cada 1 % que se mueve el mercado.",
         "Cómo leerlo": "< 0.8 defensivo · 0.8–1.2 como el mercado · > 1.2 agresivo · < 0 se mueve al revés (cobertura)."},
        {"Indicador": "Rendimiento exigido (CAPM)", "Qué mide": "E(R) = rf + β × (Rm − rf).",
         "Cómo leerlo": "Lo que el activo DEBERÍA rendir para compensar su riesgo de mercado."},
        {"Indicador": "Alfa de Jensen", "Qué mide": "Rendimiento observado menos el exigido (intercepto de la regresión de excesos).",
         "Cómo leerlo": "> 0 superó lo esperado · < 0 rindió menos · mira el p-value: si p > 0.05 puede ser suerte."},
        {"Indicador": "R²", "Qué mide": "Porcentaje del riesgo explicado por el mercado.",
         "Cómo leerlo": "Alto (> 50 %) el activo sigue al índice · bajo (< 20 %) se mueve por razones propias."},
        {"Indicador": "SML", "Qué mide": "Relación teórica entre beta y rendimiento exigido.",
         "Cómo leerlo": "Sobre la línea: activo 'barato' (paga más por su riesgo) · debajo: 'caro'."},
    ], columnas=("Indicador", "Qué mide", "Cómo leerlo"))


# ─────────────────────────── MARKOWITZ ───────────────────────────
def pagina_markowitz():
    cabecera("Optimización de portafolio — Markowitz",
             "Combinar activos que no se mueven igual reduce el riesgo. La frontera eficiente muestra las "
             "mejores combinaciones posibles: el mayor rendimiento esperado para cada nivel de riesgo.")
    if not requiere_portafolio():
        return
    with st.container(border=True):
        c1, c2 = st.columns([1, 2.2])
        with c1:
            cortos = st.toggle("Permitir ventas en corto", value=False, key="mk_cortos",
                               help="Vender en corto = apostar a que un activo baja. Se limita a −20 % por activo.")
            st.caption("Sin cortos: cada peso entre 0 % y 100 %.  \nCon cortos: entre −20 % y 120 %.")
        with c2:
            st.markdown(
                "**¿Qué es vender en corto?** Es pedir prestadas acciones que no tienes, venderlas hoy y "
                "recomprarlas después para devolverlas. **Ganas si el precio baja** y pierdes si sube. "
                "*Ejemplo:* pides prestada 1 acción a USD 100 y la vendes; si baja a USD 80, la recompras, "
                "la devuelves y te quedas con USD 20. En un portafolio, el dinero de esa venta se usa para "
                "comprar más de otros activos, por eso un peso puede ser negativo (−20 %) y otro mayor a 100 %.")

    # Se piden ambas versiones (quedan en caché) para poder compararlas
    d_sin = fetch("/analisis/markowitz", {**P_BASE, "permitir_cortos": False, "rf": tasa_fred})
    d_con = fetch("/analisis/markowitz", {**P_BASE, "permitir_cortos": True, "rf": tasa_fred}, silencioso=True) if cortos else None
    d = d_con if (cortos and d_con) else d_sin
    if not d:
        return

    ms, mv, act, ig = d["maximo_sharpe"], d["minima_varianza"], d["portafolio_actual"], d["pesos_iguales"]

    if cortos and d_con:
        ms0, mv0 = d_sin["maximo_sharpe"], d_sin["minima_varianza"]
        cortas = {t: w for t, w in ms["pesos"].items() if w < -0.001}
        largas = {t: w for t, w in ms["pesos"].items() if w > 0.001}
        bruta = sum(abs(w) for w in ms["pesos"].values())
        ui.encabezado("¿Qué cambió al permitir ventas en corto?",
                      "Comparación del portafolio de máximo Sharpe y de mínima varianza, con y sin cortos.")
        ui.kpi_grid([
            {"label": "Sharpe máximo", "value": f"{ms0['sharpe_ratio']:.2f} → {ms['sharpe_ratio']:.2f}",
             "sub": f"Cambio: {ms['sharpe_ratio'] - ms0['sharpe_ratio']:+.2f}",
             "estado": "bueno" if ms["sharpe_ratio"] > ms0["sharpe_ratio"] + 0.01 else "neutral",
             "tag": "Mejora" if ms["sharpe_ratio"] > ms0["sharpe_ratio"] + 0.01 else "Sin mejora relevante"},
            {"label": "Rendimiento (máx. Sharpe)", "value": f"{pct(ms0['retorno_anual'], 1)} → {pct(ms['retorno_anual'], 1)}",
             "sub": f"Riesgo {pct(ms0['riesgo_anual'], 1)} → {pct(ms['riesgo_anual'], 1)}"},
            {"label": "Riesgo mínimo posible", "value": f"{pct(mv0['riesgo_anual'], 1)} → {pct(mv['riesgo_anual'], 1)}",
             "sub": "Mínima varianza sin → con cortos",
             "estado": "bueno" if mv["riesgo_anual"] < mv0["riesgo_anual"] - 0.0005 else "neutral"},
            {"label": "Exposición bruta", "value": pct(bruta, 0),
             "sub": "Suma de posiciones largas + cortas (100 % = sin apalancamiento)",
             "estado": "alerta" if bruta > 1.2 else "neutral"},
        ])
        if cortas:
            txt_c = ", ".join(f"**{t}** ({usd(abs(w) * valor_portafolio)})" for t, w in cortas.items())
            txt_l = ", ".join(f"**{t}** ({pct(w, 0)})" for t, w in sorted(largas.items(), key=lambda x: -x[1]))
            ui.en_simple(
                f"El portafolio de máximo Sharpe ahora **vende en corto** {txt_c}: el modelo apuesta a que esos "
                f"activos rendirán relativamente menos. Con ese dinero compra más de {txt_l}. "
                f"Así, por cada USD 100 de tu capital tienes posiciones por USD {bruta * 100:,.0f} en total, "
                "lo que amplifica tanto las ganancias como las pérdidas.", "Interpretación")
        else:
            ui.en_simple("Aun pudiendo vender en corto, el portafolio óptimo **no lo hace**: ningún activo "
                         "es tan poco atractivo como para que convenga apostar en su contra. Por eso los resultados "
                         "son casi iguales a los de sin cortos.", "Interpretación")
        ui.nota("Vender en corto tiene riesgos que el modelo no ve: la pérdida es teóricamente **ilimitada** "
                "(el precio puede subir sin techo), hay que pagar intereses por las acciones prestadas, el bróker "
                "puede exigir más garantía (margin call) y en muchos países o fondos está restringido.", "warn",
                "Riesgos de las ventas en corto")
        ui.encabezado("Resultados con ventas en corto")

    ui.kpi_grid([
        {"label": "⭐ Máximo Sharpe — rendimiento", "value": pct(ms["retorno_anual"]),
         "sub": f"Riesgo {pct(ms['riesgo_anual'])} · Sharpe {ms['sharpe_ratio']:.2f}", "estado": est_sharpe(ms["sharpe_ratio"])},
        {"label": "💎 Mínima varianza — riesgo", "value": pct(mv["riesgo_anual"]),
         "sub": f"Rendimiento {pct(mv['retorno_anual'])} · Sharpe {mv['sharpe_ratio']:.2f}", "estado": est_vol(mv["riesgo_anual"])},
        {"label": "📍 Tu portafolio — Sharpe", "value": num(act["sharpe_ratio"]),
         "sub": f"Rend. {pct(act['retorno_anual'])} · Riesgo {pct(act['riesgo_anual'])}", "estado": est_sharpe(act["sharpe_ratio"])},
        {"label": "Mejora posible de Sharpe", "value": f"{ms['sharpe_ratio'] - act['sharpe_ratio']:+.2f}",
         "sub": "Máximo Sharpe vs tu portafolio"},
    ])

    # Nube de portafolios aleatorios a partir de medias, volatilidades y correlaciones
    activos = pd.DataFrame(d["activos"]).set_index("ticker")
    cols = d["tickers"]
    corr = pd.DataFrame(d["correlacion"]).loc[cols, cols].values
    vol = activos.loc[cols, "riesgo"].values
    mu = activos.loc[cols, "retorno"].values
    cov = corr * np.outer(vol, vol)
    rng = np.random.default_rng(0)
    W = rng.dirichlet(np.ones(len(cols)) * 0.6, 4000)
    nube_r, nube_s = W @ mu, np.sqrt(np.einsum("ij,jk,ik->i", W, cov, W))

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=nube_s * 100, y=nube_r * 100, mode="markers", name="Portafolios posibles (sin cortos)",
                             marker=dict(color=ui.SECUENCIAL[0][1], size=4, opacity=0.6), hoverinfo="skip"))
    fr = pd.DataFrame(d["frontera"]).sort_values("riesgo")
    if cortos and d_con:
        fr0 = pd.DataFrame(d_sin["frontera"]).sort_values("riesgo")
        fig.add_trace(go.Scatter(x=fr0["riesgo"] * 100, y=fr0["retorno"] * 100, mode="lines",
                                 name="Frontera SIN cortos", line=dict(color=ui.ROL["referencia"], width=2, dash="dash"),
                                 hovertemplate="Riesgo %{x:.1f}%<br>Rend. %{y:.1f}%<extra>Sin cortos</extra>"))
    fig.add_trace(go.Scatter(x=fr["riesgo"] * 100, y=fr["retorno"] * 100, mode="lines",
                             name="Frontera CON cortos" if cortos and d_con else "Frontera eficiente",
                             line=dict(color=ui.AZUL, width=3),
                             hovertemplate="Riesgo %{x:.1f}%<br>Rend. %{y:.1f}%<extra>Frontera</extra>"))
    xs = np.linspace(0, max(fr["riesgo"].max(), activos["riesgo"].max()) * 1.02, 20)
    fig.add_trace(go.Scatter(x=xs * 100, y=(tasa_fred + ms["sharpe_ratio"] * xs) * 100, mode="lines",
                             name="Línea del mercado de capitales", line=dict(color=ui.TINTA_3, dash="dot", width=1.5)))
    for tk in cols:
        fig.add_trace(go.Scatter(x=[activos.loc[tk, "riesgo"] * 100], y=[activos.loc[tk, "retorno"] * 100],
                                 mode="markers+text", text=[tk], textposition="middle right", showlegend=False,
                                 marker=dict(color=ui.TINTA_3, size=8, line=dict(color="white", width=1.5)),
                                 hovertemplate=f"{tk}<br>Riesgo %{{x:.1f}}%<br>Rend. %{{y:.1f}}%<extra></extra>"))
    for nombre, p, simb, col in [("Pesos iguales", ig, "square", ui.ROL["iguales"]),
                                 ("Máximo Sharpe", ms, "star", ui.ROL["max_sharpe"]),
                                 ("Mínima varianza", mv, "diamond", ui.ROL["min_var"]),
                                 ("Tu portafolio", act, "circle", ui.ROL["actual"])]:
        fig.add_trace(go.Scatter(x=[p["riesgo_anual"] * 100], y=[p["retorno_anual"] * 100], mode="markers", name=nombre,
                                 marker=dict(symbol=simb, size=16 if simb == "star" else 12, color=col,
                                             line=dict(color="white", width=2)),
                                 hovertemplate=f"{nombre}<br>Riesgo %{{x:.1f}}%<br>Rend. %{{y:.1f}}%<extra></extra>"))
    fig.update_layout(**ui.layout("Mapa riesgo – rendimiento", 520, xaxis_title="Riesgo: volatilidad anual (%)",
                                  yaxis_title="Rendimiento esperado anual (%)"))
    st.plotly_chart(fig, use_container_width=True)
    if cortos and d_con:
        st.caption("La frontera azul (con cortos) queda por encima o igual que la gris (sin cortos): tener más "
                   "libertad nunca empeora el óptimo. La distancia entre ambas es el beneficio teórico de poder "
                   "vender en corto. La nube de puntos corresponde a combinaciones sin cortos.")
    else:
        st.caption("Activa **Permitir ventas en corto** arriba para ver cómo se expande la frontera.")

    c1, c2 = st.columns([1.3, 1])
    with c1:
        comp = pd.DataFrame({"Activo": cols,
                             "Tu portafolio": [act["pesos"][t] for t in cols],
                             "Máximo Sharpe": [ms["pesos"][t] for t in cols],
                             "Mínima varianza": [mv["pesos"][t] for t in cols]})
        fig = go.Figure()
        for i, c in enumerate(["Tu portafolio", "Máximo Sharpe", "Mínima varianza"]):
            fig.add_trace(go.Bar(x=comp["Activo"], y=comp[c] * 100, name=c,
                                 marker_color=[ui.ROL["actual"], ui.ROL["max_sharpe"], ui.ROL["min_var"]][i]))
        fig.add_hline(y=0, line_color=ui.EJE, line_width=1)
        if (comp[["Máximo Sharpe", "Mínima varianza"]] < -0.001).any().any():
            fig.add_annotation(text="Barras bajo 0 = venta en corto", xref="paper", yref="paper", x=0, y=0,
                               showarrow=False, font=dict(size=11, color=ui.TINTA_2), xanchor="left", yanchor="bottom")
        fig.update_layout(**ui.layout("Pesos sugeridos vs tus pesos actuales", 360, yaxis_title="% del capital",
                                      barmode="group", barcornerradius=3))
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        corr_df = pd.DataFrame(d["correlacion"]).loc[cols, cols]
        fig = go.Figure(go.Heatmap(z=corr_df.values, x=cols, y=cols, colorscale=ui.DIVERGENTE, zmin=-1, zmax=1,
                                   text=corr_df.round(2).values, texttemplate="%{text}", xgap=2, ygap=2,
                                   colorbar=dict(title="ρ")))
        fig.update_layout(**ui.layout("Correlaciones entre activos", 360, legend=False))
        st.plotly_chart(fig, use_container_width=True)

    elegido = st.radio("Ver la distribución en dinero de:", ["Máximo Sharpe", "Mínima varianza"], horizontal=True)
    pe = ms if elegido == "Máximo Sharpe" else mv
    dist = pd.DataFrame([{"Activo": t,
                          "Posición": "▼ Venta en corto" if w < -0.001 else "▲ Compra (larga)" if w > 0.001 else "— Sin posición",
                          "Peso sugerido": w, "Monto (USD)": w * valor_portafolio,
                          "Peso actual": act["pesos"][t], "Cambio (USD)": (w - act["pesos"][t]) * valor_portafolio}
                         for t, w in pe["pesos"].items()])
    st.dataframe(dist.style.format({"Peso sugerido": "{:.1%}", "Monto (USD)": "USD {:,.0f}", "Peso actual": "{:.1%}",
                                    "Cambio (USD)": "{:+,.0f}"}), use_container_width=True, hide_index=True)
    ui.nota("La optimización usa rendimientos y correlaciones PASADOS. Pequeños cambios en los datos pueden "
            "cambiar mucho los pesos óptimos; el portafolio de mínima varianza suele ser más estable porque no "
            "depende de pronosticar rendimientos.", "warn")

    ui.guia_lectura("Cómo leer el modelo de Markowitz", [
        {"Elemento": "Nube de puntos", "Qué representa": "Miles de combinaciones aleatorias de tus activos.",
         "Cómo leerlo": "Muestra todo lo que es posible lograr con estos activos."},
        {"Elemento": "Frontera eficiente (línea azul)", "Qué representa": "Las combinaciones con el mayor rendimiento para cada nivel de riesgo.",
         "Cómo leerlo": "Cualquier portafolio por debajo de la línea es mejorable: se puede ganar más con el mismo riesgo."},
        {"Elemento": "💎 Mínima varianza", "Qué representa": "La combinación con el menor riesgo posible.",
         "Cómo leerlo": "Ideal para un perfil conservador."},
        {"Elemento": "⭐ Máximo Sharpe (portafolio tangente)", "Qué representa": "La mejor relación rendimiento extra / riesgo.",
         "Cómo leerlo": "Es donde la línea punteada (que parte de la tasa libre de riesgo) toca la frontera."},
        {"Elemento": "📍 Tu portafolio", "Qué representa": "Tus pesos actuales de la barra lateral.",
         "Cómo leerlo": "Cuanto más lejos esté por debajo de la frontera, más margen de mejora tienes."},
        {"Elemento": "Venta en corto", "Qué representa": "Vender un activo prestado para recomprarlo más barato.",
         "Cómo leerlo": "Peso negativo (ej. −20 %) = vendes en corto el 20 % de tu capital en ese activo; ganas si baja."},
        {"Elemento": "Frontera con vs sin cortos", "Qué representa": "Lo mejor que se puede lograr con y sin esa libertad.",
         "Cómo leerlo": "Si casi coinciden, los cortos no aportan. Si la azul queda muy arriba, el modelo encuentra activos para apostar en contra."},
        {"Elemento": "Exposición bruta", "Qué representa": "Suma de todas las posiciones en valor absoluto.",
         "Cómo leerlo": "100 % = sin apalancamiento. 140 % = por cada USD 100 tienes USD 140 invertidos: más riesgo real que el que muestra el modelo."},
        {"Elemento": "Correlación (ρ)", "Qué representa": "Qué tanto se mueven juntos dos activos (−1 a 1).",
         "Cómo leerlo": "Cerca de 1 (azul intenso): no diversifican · cerca de 0: diversifican · negativa (rojo): se compensan."},
    ], columnas=("Elemento", "Qué representa", "Cómo leerlo"))


# ─────────────────────────── BENCHMARK Y MACRO ───────────────────────────
def pagina_macro():
    cabecera("Benchmark y contexto macroeconómico",
             "¿Tu portafolio le gana al mercado? ¿Y cómo están las tasas de interés y la inflación, que "
             "afectan a todos los activos?")
    curva = fetch("/renta-fija/curva", silencioso=True)
    if macro:
        tasa_real = (1 + macro["tasa_libre_riesgo"]) / (1 + macro["inflacion_anual_pct"] / 100) - 1
        pend = curva["nelson_siegel"]["pendiente_10a_3m"] if curva else None
        ui.kpi_grid([
            {"label": "Tasa libre de riesgo (3 meses)", "value": pct(macro["tasa_libre_riesgo"]), "sub": "Bonos del Tesoro EE. UU."},
            {"label": "Inflación anual (IPC)", "value": f"{macro['inflacion_anual_pct']:.2f}%",
             "estado": "bueno" if macro["inflacion_anual_pct"] < 2.5 else "alerta" if macro["inflacion_anual_pct"] < 4 else "serio",
             "sub": "Meta de la Fed: 2 %"},
            {"label": "Tasa real", "value": pct(tasa_real), "sub": "Rendimiento del Tesoro descontando inflación"},
            {"label": "Pendiente 10 años − 3 meses", "value": f"{pend:+.2f} p.p." if pend is not None else "—",
             "estado": ("critico" if pend < 0 else "alerta" if pend < 0.5 else "bueno") if pend is not None else None,
             "tag": ("Curva invertida" if pend < 0 else "Curva plana" if pend < 0.5 else "Curva normal") if pend is not None else None},
        ])
    if curva:
        dm = curva["datos_mercado"]
        ns = pd.DataFrame(curva["nelson_siegel"]["curva_suave"])
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=ns["plazo"], y=ns["tasa"], name="Ajuste Nelson-Siegel", line=dict(color=ui.AZUL, width=2)))
        fig.add_trace(go.Scatter(x=dm["plazos"], y=dm["tasas"], name="Tasas observadas (FRED)", mode="markers",
                                 marker=dict(color=ui.NARANJA, size=10, line=dict(color="white", width=2))))
        fig.update_layout(**ui.layout("Curva de rendimientos del Tesoro de EE. UU.", 360, xaxis_title="Plazo (años)",
                                      yaxis_title="Tasa anual (%)"))
        st.plotly_chart(fig, use_container_width=True)
        if curva["nelson_siegel"]["pendiente_10a_3m"] < 0:
            ui.nota("La curva está invertida: los bonos cortos pagan más que los largos. Históricamente esto ha "
                    "antecedido a recesiones en EE. UU. (aunque no siempre).", "warn", "Señal macro a vigilar")

    if not requiere_portafolio():
        return
    ui.encabezado(f"Tu portafolio vs {BENCHMARKS.get(benchmark, benchmark)}")
    b = fetch("/macro/benchmark", {**P_BASE, "benchmark": benchmark})
    if not b:
        return
    dif = b["retorno_acumulado_portafolio"] - b["retorno_acumulado_benchmark"]
    ui.kpi_grid([
        {"label": "Rendimiento acumulado — portafolio", "value": pct(b["retorno_acumulado_portafolio"], 1, True),
         "estado": "bueno" if dif >= 0 else "alerta", "tag": f"{pct(dif, 1, True)} vs benchmark"},
        {"label": "Rendimiento acumulado — benchmark", "value": pct(b["retorno_acumulado_benchmark"], 1, True)},
        {"label": "Sharpe portafolio / benchmark", "value": f"{b['sharpe_portafolio']:.2f} / {b['sharpe_benchmark']:.2f}",
         "estado": "bueno" if b["sharpe_portafolio"] >= b["sharpe_benchmark"] else "alerta"},
        {"label": "Máx. drawdown portafolio / benchmark", "value": f"{pct(b['max_drawdown'], 1)} / {pct(b['max_drawdown_benchmark'], 1)}",
         "estado": "bueno" if b["max_drawdown"] >= b["max_drawdown_benchmark"] else "alerta"},
        {"label": "Tracking error", "value": pct(b["tracking_error"]), "sub": "Qué tanto te alejas del índice"},
        {"label": "Information ratio", "value": num(b["information_ratio"]),
         "estado": "bueno" if b["information_ratio"] > 0.5 else "alerta" if b["information_ratio"] > 0 else "serio"},
        {"label": "Beta / correlación", "value": f"{num(b['beta_portafolio'])} / {num(b['correlacion'])}"},
    ])
    ui.guia_lectura("Cómo leer la comparación con el benchmark", [
        {"Indicador": "Tracking error", "Qué mide": "Volatilidad de la diferencia de rendimientos con el índice.",
         "Cómo leerlo": "< 2 % casi idéntico al índice · 2–6 % gestión activa moderada · > 6 % muy distinto del índice."},
        {"Indicador": "Information ratio", "Qué mide": "Exceso de rendimiento sobre el índice ÷ tracking error.",
         "Cómo leerlo": "> 0.5 bueno · 0–0.5 modesto · < 0 el portafolio rindió menos que el índice."},
        {"Indicador": "Máximo drawdown", "Qué mide": "Peor caída desde un máximo.",
         "Cómo leerlo": "Si es menor que la del índice, tu portafolio aguantó mejor las caídas."},
        {"Indicador": "Curva de rendimientos", "Qué mide": "Tasa de interés de los bonos del Tesoro según su plazo.",
         "Cómo leerlo": "Normal: sube con el plazo · plana: incertidumbre · invertida: posible señal de recesión."},
        {"Indicador": "Tasa real", "Qué mide": "Tasa nominal descontando la inflación.",
         "Cómo leerlo": "Positiva: el ahorro sin riesgo gana poder de compra · negativa: lo pierde."},
    ], columnas=("Indicador", "Qué mide", "Cómo leerlo"))


# ─────────────────────────── RENTA FIJA ───────────────────────────
def pagina_renta_fija():
    cabecera("Renta fija — valoración de un bono, duración y convexidad",
             "Un bono es un préstamo: entregas dinero hoy y recibes intereses (cupones) y tu capital al final. "
             "Cuando las tasas de interés del mercado suben, el precio de los bonos baja. Aquí puedes armar "
             "cualquier bono y ver cuánto vale y qué tan sensible es a las tasas.")
    FREC = {1: "Anual (1 pago al año)", 2: "Semestral (2 pagos)", 4: "Trimestral (4 pagos)", 12: "Mensual (12 pagos)"}
    with st.container(border=True):
        st.markdown("**1. Características del bono**")
        c1, c2, c3, c4 = st.columns(4)
        tipo = c1.radio("Tipo de bono", ["Con cupones", "Cupón cero"], horizontal=True,
                        help="Un bono cupón cero no paga intereses periódicos: se compra con descuento y "
                             "al vencimiento devuelve el nominal completo.")
        if tipo == "Cupón cero":
            cupon = 0.0
            c2.number_input("Tasa cupón anual (%)", value=0.0, disabled=True)
            frec = 1
            c3.selectbox("Frecuencia de pago", ["No aplica (un solo pago al final)"], disabled=True)
        else:
            cupon = c2.number_input("Tasa cupón anual (%)", value=5.0, step=0.25, min_value=0.01, max_value=50.0,
                                    help="Interés anual que paga el bono sobre su nominal.") / 100
            frec = c3.selectbox("Frecuencia de pago", list(FREC), index=1, format_func=FREC.get,
                                help="Los bonos del Tesoro de EE. UU. y muchos corporativos pagan semestralmente.")
        nominal = c4.number_input("Valor nominal (USD)", value=1000.0, min_value=1.0, max_value=1e9, step=100.0,
                                  help="Lo que te devuelven al vencimiento. Suele ser 100 o 1.000.")

        st.markdown("**2. Plazo y tasa de mercado**")
        c5, c6, c7 = st.columns([1, 1, 1])
        venc = int(c5.number_input("Años al vencimiento", value=10, min_value=1, max_value=50))
        usar_curva = c6.toggle("Usar la tasa del mercado (curva del Tesoro, FRED)", value=True,
                               help="Toma la tasa de la curva al mismo plazo del bono.")
        ytm = None
        if not usar_curva:
            ytm = c7.number_input("Rendimiento exigido / YTM anual (%)", value=4.5, step=0.25,
                                  min_value=-2.0, max_value=40.0,
                                  help="La tasa que exige el mercado hoy para este tipo de bono.") / 100
        else:
            c7.caption("Desactiva el interruptor para escribir tu propio rendimiento (YTM).")

    params = {"tasa_cupon": cupon, "vencimiento": venc, "frecuencia": frec, "valor_nominal": nominal}
    if ytm is not None:
        params["tasa_descuento"] = ytm
    d = fetch("/renta-fija/duracion", params)
    s = fetch("/renta-fija/sensibilidad", params)
    if not d or not s:
        return
    y0 = d["tasa_descuento"]
    p0, dm, cx = d["precio_bono"], d["duracion_modificada"], d["convexidad"]

    ui.kpi_grid([
        {"label": "Precio justo del bono", "value": usd(p0, 2),
         "sub": f"{d['precio_pct_nominal']:.2f} % del nominal", "estado": "neutral", "tag": f"Cotiza {d['cotiza']}"},
        {"label": "Rendimiento usado (YTM)", "value": pct(y0), "sub": d["fuente_tasa"].replace("curva FRED", "Curva FRED").replace("ingresada", "Ingresada")},
        {"label": "Pagos que recibirás", "value": f"{d['numero_pagos']}",
         "sub": "Sólo el nominal al final" if d["es_cupon_cero"] else
                f"{usd(d['cupon_por_pago'], 2)} cada pago ({d['frecuencia_nombre']})"},
        {"label": "Duración de Macaulay", "value": f"{d['duracion_macaulay']:.2f} años",
         "sub": "Igual al plazo (cupón cero)" if d["es_cupon_cero"] else "Plazo promedio en que recuperas tu dinero"},
        {"label": "Duración modificada", "value": f"{dm:.2f}",
         "sub": f"Si la tasa sube 1 p.p., el precio cae ≈ {dm:.1f} %",
         "estado": "bueno" if dm < 3 else "alerta" if dm < 7 else "serio",
         "tag": "Sensibilidad baja" if dm < 3 else "Sensibilidad media" if dm < 7 else "Sensibilidad alta"},
        {"label": "Convexidad", "value": f"{cx:.1f}", "sub": "Corrige la curvatura precio–tasa (mayor = mejor)"},
        {"label": "DV01", "value": usd(d["dv01"], 4), "sub": "Cambio de precio por cada 0,01 % de tasa"},
    ])

    sube = next(x for x in s["shocks"] if x["shock_bp"] == 100)
    baja = next(x for x in s["shocks"] if x["shock_bp"] == -100)
    ui.en_simple(
        f"Hoy este bono vale {usd(p0, 2)}"
        + (f", menos que su nominal de {usd(nominal, 0)}, porque no paga intereses: tu ganancia es la diferencia."
           if d["es_cupon_cero"] else
           f" ({d['cotiza']}: su cupón de {pct(cupon)} es {'mayor' if cupon > y0 else 'menor' if cupon < y0 else 'igual'} "
           f"que la tasa de mercado de {pct(y0)}).")
        + f" Si las tasas suben 1 punto porcentual, bajaría a {usd(sube['precio_exacto'], 2)} "
        f"({sube['cambio_pct_exacto']:+.2f} %); si bajan 1 punto, subiría a {usd(baja['precio_exacto'], 2)} "
        f"({baja['cambio_pct_exacto']:+.2f} %). Fíjate que gana más de lo que pierde: eso es la convexidad.")

    def precio(y):
        n = venc * frec
        k = np.arange(1, n + 1)
        f = np.full(n, cupon * nominal / frec)
        f[-1] += nominal
        return float(np.sum(f / (1 + y / frec) ** k))

    c1, c2 = st.columns([1.3, 1])
    with c1:
        ys = np.linspace(max(-0.005, y0 - 0.04), y0 + 0.04, 80)
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=ys * 100, y=[precio(y) for y in ys], name="Precio exacto",
                                 line=dict(color=ui.AZUL, width=3)))
        fig.add_trace(go.Scatter(x=ys * 100, y=p0 * (1 - dm * (ys - y0)), name="Aproximación sólo con duración",
                                 line=dict(color=ui.NARANJA, width=2, dash="dash")))
        fig.add_trace(go.Scatter(x=ys * 100, y=p0 * (1 - dm * (ys - y0) + 0.5 * cx * (ys - y0) ** 2),
                                 name="Duración + convexidad", line=dict(color=ui.SERIES[2], width=2, dash="dot")))
        fig.add_trace(go.Scatter(x=[y0 * 100], y=[p0], mode="markers", name="Hoy",
                                 marker=dict(color=ui.ROL["actual"], size=10, line=dict(color="white", width=2))))
        fig.update_layout(**ui.layout("Si cambia la tasa de mercado, ¿cuánto vale el bono?", 400,
                                      xaxis_title="Tasa de mercado / YTM (%)", yaxis_title="Precio (USD)",
                                      hovermode="x unified"))
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        fl = pd.DataFrame(d["flujos"])
        fig = go.Figure()
        fig.add_trace(go.Bar(x=fl["anio"], y=fl["flujo"], name="Pago recibido", marker_color=ui.ROL["referencia"]))
        fig.add_trace(go.Bar(x=fl["anio"], y=fl["valor_presente"], name="Lo que vale hoy (valor presente)",
                             marker_color=ui.AZUL))
        fig.add_vline(x=d["duracion_macaulay"], line_dash="dash", line_color=ui.ROL["actual"],
                      annotation_text="Duración", annotation_position="top left")
        fig.update_layout(**ui.layout("Calendario de pagos del bono", 400, xaxis_title="Año",
                                      yaxis_title="USD", barmode="overlay"))
        fig.update_traces(opacity=0.85, selector=dict(type="bar"))
        st.plotly_chart(fig, use_container_width=True)
        st.caption("La línea punteada (duración) es el 'centro de gravedad' de los pagos: el momento promedio en "
                   "que recuperas tu dinero, ponderado por lo que vale cada pago hoy.")

    sh = pd.DataFrame(s["shocks"])
    tabla = sh[["shock_bp", "precio_exacto", "cambio_pct_exacto", "precio_lineal", "precio_duracion_convexidad",
                "error_lineal", "error_duracion_convexidad"]]
    tabla.columns = ["Cambio de tasa (pb)", "Precio exacto", "Cambio %", "Estimado con duración",
                     "Estimado con dur. + convexidad", "Error duración", "Error dur. + convexidad"]
    st.markdown("**¿Qué pasa con el precio si las tasas cambian?** (100 pb = 1 punto porcentual)")
    st.dataframe(tabla.style.format({"Precio exacto": "{:,.2f}", "Cambio %": "{:+.2f}%",
                                     "Estimado con duración": "{:,.2f}", "Estimado con dur. + convexidad": "{:,.2f}",
                                     "Error duración": "{:+.3f}", "Error dur. + convexidad": "{:+.3f}"}),
                 use_container_width=True, hide_index=True)
    st.caption("La columna de error muestra cuánto se equivoca cada aproximación frente al precio exacto: la de "
               "duración + convexidad casi siempre acierta mucho mejor, sobre todo en cambios grandes.")

    ui.guia_lectura("Cómo leer las métricas de un bono", [
        {"Concepto": "Nominal", "Qué es": "El monto que te devuelven al vencimiento (también llamado valor facial o par).",
         "Cómo leerlo": "Los cupones se calculan sobre él: cupón 5 % con nominal 1.000 = 50 USD al año."},
        {"Concepto": "Frecuencia del cupón", "Qué es": "Cuántas veces al año se pagan intereses.",
         "Cómo leerlo": "Semestral con cupón 5 % y nominal 1.000 = dos pagos de 25 USD al año. Más pagos = recuperas antes = menor duración."},
        {"Concepto": "Bono cupón cero", "Qué es": "No paga intereses: se compra barato y paga el nominal al final.",
         "Cómo leerlo": "Su duración es igual al plazo; es el bono más sensible a las tasas para un plazo dado."},
        {"Concepto": "A la par / con prima / con descuento", "Qué es": "Precio igual, mayor o menor que el nominal.",
         "Cómo leerlo": "Cupón > tasa de mercado → con prima. Cupón < tasa → con descuento. Iguales → a la par."},
        {"Concepto": "YTM (rendimiento al vencimiento)", "Qué es": "La tasa anual que hace que el valor presente de los pagos sea igual al precio.",
         "Cómo leerlo": "Es lo que ganas por año si compras hoy y mantienes hasta el final, reinvirtiendo los cupones a esa tasa."},
        {"Concepto": "Duración de Macaulay", "Qué es": "Tiempo promedio, en años, en que recibes tu dinero.",
         "Cómo leerlo": "Siempre ≤ plazo. Un bono a 10 años con cupones puede tener duración de ~8 años."},
        {"Concepto": "Duración modificada", "Qué es": "% que cambia el precio si la tasa cambia 1 punto porcentual.",
         "Cómo leerlo": ("alerta", "< 3 baja · 3–7 media · > 7 alta sensibilidad a las tasas")},
        {"Concepto": "Convexidad", "Qué es": "Curvatura de la relación precio–tasa.",
         "Cómo leerlo": "Más convexidad es mejor para quien tiene el bono: gana más cuando bajan las tasas de lo que pierde cuando suben."},
        {"Concepto": "DV01", "Qué es": "Cambio en USD del precio por un movimiento de 0,01 % (1 pb) en la tasa.",
         "Cómo leerlo": "Lo usan los operadores para medir y cubrir el riesgo de tasa de interés."},
    ], columnas=("Concepto", "Qué es", "Cómo leerlo"))


# ─────────────────────────── OPCIONES ───────────────────────────
def pagina_opciones():
    cabecera("Opciones — modelo de Black-Scholes",
             "Una opción da el DERECHO (no la obligación) de comprar (call) o vender (put) un activo a un precio "
             "fijo (strike) en una fecha futura. Black-Scholes calcula su precio justo.")
    if not requiere_portafolio(1):
        return
    t = selector_activo("opt_activo", "Activo subyacente")
    df = precios_df(t)
    spot = float(df["close"].iloc[-1]) if df is not None and not df.empty else 100.0
    vol_hist = float(np.log(df["close"] / df["close"].shift(1)).std() * np.sqrt(252)) if df is not None and len(df) > 30 else 0.2

    with st.container(border=True):
        c1, c2, c3, c4, c5 = st.columns(5)
        S = c1.number_input("Precio actual (S)", value=round(spot, 2), min_value=0.01, step=1.0)
        K = c2.number_input("Strike (K)", value=round(spot, 2), min_value=0.01, step=1.0)
        meses = c3.number_input("Meses al vencimiento", value=6, min_value=1, max_value=120)
        r = c4.number_input("Tasa libre de riesgo (%)", value=round(tasa_fred * 100, 2), step=0.25) / 100
        sigma = c5.number_input("Volatilidad anual (%)", value=round(vol_hist * 100, 1), min_value=1.0, max_value=300.0,
                                step=1.0, help="Por defecto, la volatilidad histórica del activo.") / 100
    T = meses / 12
    d = fetch("/opciones/black-scholes", {"S": S, "K": K, "T": T, "r": r, "sigma": sigma})
    if not d:
        return
    p, g = d["precios"], d["greeks"]
    estado_call = "dentro del dinero" if S > K else "fuera del dinero" if S < K else "en el dinero"
    ui.kpi_grid([
        {"label": "Prima de la CALL", "value": f"USD {p['call']:.2f}",
         "sub": f"Intrínseco {p['valor_intrinseco_call']:.2f} + tiempo {p['valor_tiempo_call']:.2f}", "tag": estado_call, "estado": "neutral"},
        {"label": "Prima de la PUT", "value": f"USD {p['put']:.2f}",
         "sub": f"Intrínseco {p['valor_intrinseco_put']:.2f} + tiempo {p['valor_tiempo_put']:.2f}"},
        {"label": "Prob. de ejercer la call", "value": pct(p["prob_ejercicio_call"], 1), "sub": "N(d₂), en el mundo neutral al riesgo"},
        {"label": "Prob. de ejercer la put", "value": pct(p["prob_ejercicio_put"], 1), "sub": "N(−d₂)"},
        {"label": "Paridad put-call", "value": "✓ se cumple" if abs(p["error_paridad_put_call"]) < 1e-4 else "✗",
         "sub": "C − P = S − K·e^(−rT)", "estado": "bueno" if abs(p["error_paridad_put_call"]) < 1e-4 else "critico"},
    ])

    griegas = pd.DataFrame([
        {"Griega": "Delta (Δ)", "Call": g["delta_call"], "Put": g["delta_put"],
         "Interpretación con tus datos": f"Si {t} sube USD 1, la call gana USD {g['delta_call']:.2f} y la put pierde USD {abs(g['delta_put']):.2f}."},
        {"Griega": "Gamma (Γ)", "Call": g["gamma"], "Put": g["gamma"],
         "Interpretación con tus datos": f"Por cada USD 1 que sube {t}, el delta cambia {g['gamma']:.4f}. Máxima cerca del strike."},
        {"Griega": "Vega (ν)", "Call": g["vega"], "Put": g["vega"],
         "Interpretación con tus datos": f"Si la volatilidad sube 1 p.p. (de {sigma:.0%} a {sigma + 0.01:.0%}), ambas primas suben USD {g['vega']:.2f}."},
        {"Griega": "Theta (Θ)", "Call": g["theta_call"], "Put": g["theta_put"],
         "Interpretación con tus datos": f"Cada día que pasa, la call pierde USD {abs(g['theta_call']):.3f} de valor por el paso del tiempo."},
        {"Griega": "Rho (ρ)", "Call": g["rho_call"], "Put": g["rho_put"],
         "Interpretación con tus datos": f"Si la tasa sube 1 p.p., la call sube USD {g['rho_call']:.2f} y la put cambia USD {g['rho_put']:.2f}."},
    ])
    st.dataframe(griegas.style.format({"Call": "{:.4f}", "Put": "{:.4f}"}), use_container_width=True, hide_index=True)

    spots = np.linspace(S * 0.6, S * 1.4, 120)
    c1, c2 = st.columns(2)
    with c1:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=spots, y=np.maximum(spots - K, 0) - p["call"], name="Comprar CALL", line=dict(color=ui.SERIES[0], width=2.5)))
        fig.add_trace(go.Scatter(x=spots, y=np.maximum(K - spots, 0) - p["put"], name="Comprar PUT", line=dict(color=ui.SERIES[1], width=2.5)))
        fig.add_hline(y=0, line_color=ui.EJE)
        fig.add_vline(x=K, line_dash="dot", line_color=ui.TINTA_3, annotation_text="Strike")
        fig.update_layout(**ui.layout("Ganancia o pérdida al vencimiento", 360, xaxis_title=f"Precio de {t} al vencimiento",
                                      yaxis_title="USD por opción", hovermode="x unified"))
        st.plotly_chart(fig, use_container_width=True)
        st.caption(f"Punto de equilibrio de la call: {K + p['call']:.2f} · de la put: {K - p['put']:.2f}. "
                   "La pérdida máxima al comprar una opción es la prima pagada.")
    with c2:
        def bs_call(s, tt):
            d1 = (np.log(s / K) + (r + sigma ** 2 / 2) * tt) / (sigma * np.sqrt(tt))
            return s * sp_stats.norm.cdf(d1) - K * np.exp(-r * tt) * sp_stats.norm.cdf(d1 - sigma * np.sqrt(tt))
        fig = go.Figure()
        for i, tt in enumerate([T, T / 2, max(T / 6, 1 / 52)]):
            fig.add_trace(go.Scatter(x=spots, y=bs_call(spots, tt), name=f"Faltando {tt * 12:.1f} meses",
                                     line=dict(color=ui.SERIES[i], width=2)))
        fig.add_trace(go.Scatter(x=spots, y=np.maximum(spots - K, 0), name="Valor intrínseco",
                                 line=dict(color=ui.TINTA_3, width=1.5, dash="dash")))
        fig.update_layout(**ui.layout("Precio de la call según el precio del activo", 360, xaxis_title=f"Precio de {t}",
                                      yaxis_title="Prima (USD)", hovermode="x unified"))
        st.plotly_chart(fig, use_container_width=True)
        st.caption("La distancia entre cada curva y la línea punteada es el 'valor tiempo': se va perdiendo a medida "
                   "que se acerca el vencimiento (theta).")

    with st.expander("🔎 Calcular la volatilidad implícita a partir de un precio de mercado"):
        cc1, cc2 = st.columns(2)
        tipo = cc1.radio("Tipo", ["call", "put"], horizontal=True)
        pm = cc2.number_input("Precio de mercado de la opción", value=float(round(p[tipo], 2)), min_value=0.01)
        vi = fetch("/opciones/volatilidad-implicita", {"S": S, "K": K, "T": T, "r": r, "precio_mercado": pm, "tipo": tipo})
        if vi:
            st.metric("Volatilidad implícita", pct(vi["volatilidad_implicita"], 1),
                      delta=f"{(vi['volatilidad_implicita'] - vol_hist) * 100:+.1f} p.p. vs histórica", delta_color="off")
            st.caption("Es la volatilidad que el mercado 'espera'. Si es mayor que la histórica, el mercado anticipa más turbulencia.")

    ui.guia_lectura("Cómo leer una opción", [
        {"Concepto": "Call / Put", "Qué es": "Derecho a comprar / vender al strike.",
         "Cómo leerlo": "La call gana si el precio sube por encima del strike; la put si baja por debajo."},
        {"Concepto": "Dentro / fuera del dinero", "Qué es": "Si ejercerla hoy daría ganancia o no.",
         "Cómo leerlo": "Call dentro del dinero: S > K. Put dentro del dinero: S < K."},
        {"Concepto": "Valor intrínseco y valor tiempo", "Qué es": "Prima = lo que vale ejercer hoy + valor de la posibilidad futura.",
         "Cómo leerlo": "El valor tiempo es mayor cuanto más plazo y más volatilidad, y llega a 0 al vencimiento."},
        {"Concepto": "Delta", "Qué es": "Sensibilidad al precio del activo.",
         "Cómo leerlo": "Call: 0 a 1 · Put: −1 a 0. Delta 0.5 ≈ opción en el dinero."},
        {"Concepto": "Gamma", "Qué es": "Qué tan rápido cambia el delta.", "Cómo leerlo": "Alta cerca del strike y del vencimiento."},
        {"Concepto": "Vega", "Qué es": "Sensibilidad a la volatilidad (por 1 p.p.).", "Cómo leerlo": "Más volatilidad = opciones más caras."},
        {"Concepto": "Theta", "Qué es": "Pérdida de valor por cada día que pasa.", "Cómo leerlo": "Casi siempre negativa para el comprador."},
        {"Concepto": "Supuestos de Black-Scholes", "Qué es": "Opción europea, sin dividendos, volatilidad y tasa constantes.",
         "Cómo leerlo": "En la realidad la volatilidad cambia (ver módulo de volatilidad), así que es una aproximación."},
    ], columnas=("Concepto", "Qué es", "Cómo leerlo"))


# ─────────────────────────── GLOSARIO ───────────────────────────
GLOSARIO = [
    ("Activo", "Cualquier cosa en la que se invierte: acciones, bonos, ETF, oro, etc."),
    ("Acción", "Una pequeña parte de la propiedad de una empresa."),
    ("Alfa de Jensen", "Rendimiento obtenido por encima (o por debajo) de lo que el CAPM exige según su beta."),
    ("Asimetría", "Mide si la distribución de rendimientos está inclinada hacia pérdidas (negativa) o ganancias (positiva)."),
    ("Backtesting", "Comprobar un modelo con datos pasados: ¿predijo bien lo que realmente ocurrió?"),
    ("Benchmark", "Índice de referencia (como el S&P 500) contra el que se compara una inversión."),
    ("Beta (β)", "Sensibilidad de un activo a los movimientos del mercado. β = 1 se mueve igual que el mercado."),
    ("Bono", "Préstamo que haces a un gobierno o empresa a cambio de pagos de interés (cupones) y la devolución del capital."),
    ("CAPM", "Modelo que dice cuánto debería rendir un activo según su riesgo de mercado: E(R) = rf + β(Rm − rf)."),
    ("Colas pesadas", "Cuando los eventos extremos ocurren más seguido de lo que predice la distribución normal."),
    ("Convexidad", "Curvatura de la relación precio-tasa de un bono. Mejora la aproximación de la duración."),
    ("Correlación", "Qué tanto se mueven juntos dos activos, de −1 (opuestos) a +1 (idénticos)."),
    ("Cupón", "Pago periódico de intereses de un bono."),
    ("Curtosis", "Mide qué tan gruesas son las colas. En exceso: 0 para la normal; positiva implica más extremos."),
    ("CVaR / Expected Shortfall", "Pérdida promedio en los días en que se supera el VaR."),
    ("Distribución normal", "La 'campana de Gauss'. Muchos modelos la suponen, pero los mercados suelen tener colas más pesadas."),
    ("Diversificación", "Combinar activos que no se mueven igual para reducir el riesgo total."),
    ("Drawdown", "Caída desde el máximo anterior. El máximo drawdown es la peor caída del período."),
    ("Duración", "Medida de sensibilidad del precio de un bono a cambios en las tasas de interés."),
    ("ETF", "Fondo que cotiza en bolsa y replica un índice o una canasta de activos."),
    ("EWMA", "Promedio móvil exponencial: estima la volatilidad dando más peso a los días recientes."),
    ("Frontera eficiente", "Conjunto de portafolios con el mayor rendimiento posible para cada nivel de riesgo."),
    ("GARCH", "Modelo estadístico donde la volatilidad de hoy depende de los choques y la volatilidad recientes."),
    ("Information ratio", "Exceso de rendimiento sobre el benchmark dividido por el tracking error."),
    ("Monte Carlo", "Método que simula miles de escenarios aleatorios para estimar un resultado."),
    ("Opción", "Contrato que da el derecho a comprar (call) o vender (put) un activo a un precio fijo."),
    ("p-value", "Probabilidad de observar los datos si la hipótesis inicial fuera cierta. Si es < 0.05 se suele rechazar esa hipótesis."),
    ("Portafolio", "Conjunto de inversiones de una persona o institución."),
    ("Punto básico (pb)", "0.01 %. Se usa para hablar de cambios en tasas de interés."),
    ("Rendimiento logarítmico", "ln(Pₜ/Pₜ₋₁). Casi igual al % de cambio diario y se puede sumar en el tiempo."),
    ("Riesgo sistemático", "Riesgo del mercado en su conjunto; no se elimina diversificando."),
    ("Riesgo idiosincrático", "Riesgo propio de una empresa; se reduce diversificando."),
    ("Sharpe", "(Rendimiento − tasa libre de riesgo) ÷ volatilidad. Rendimiento extra por unidad de riesgo."),
    ("Sortino", "Como el Sharpe, pero sólo penaliza la volatilidad de las caídas."),
    ("Stress test", "Simulación del impacto de escenarios extremos (crisis) sobre el portafolio."),
    ("Tasa libre de riesgo", "Rendimiento de una inversión considerada sin riesgo, como un bono del Tesoro de EE. UU. a corto plazo."),
    ("Tracking error", "Volatilidad de la diferencia de rendimientos entre el portafolio y su benchmark."),
    ("VaR (Valor en Riesgo)", "Pérdida máxima esperada en un horizonte y con un nivel de confianza dados."),
    ("Venta en corto", "Vender un activo prestado esperando recomprarlo más barato; se gana si el precio baja."),
    ("Volatilidad", "Desviación estándar de los rendimientos: mide qué tanto oscila el precio."),
    ("YTM", "Rendimiento al vencimiento: la tasa anual que obtienes si compras el bono hoy y lo mantienes hasta el final."),
]


def pagina_glosario():
    ui.hero("Glosario", "Todos los términos del tablero explicados en lenguaje simple.", eyebrow="Herramientas")
    buscar = st.text_input("Buscar un término", placeholder="Ej: beta, VaR, drawdown...")
    filas = [{"Término": t, "Significado": s} for t, s in GLOSARIO
             if not buscar or buscar.lower() in t.lower() or buscar.lower() in s.lower()]
    if filas:
        ui.guia_lectura(f"{len(filas)} términos", filas, columnas=("Término", "Significado"))
    else:
        st.info("No se encontró ese término.")


# ─────────────────────────── MACHINE LEARNING ───────────────────────────
def pagina_ml():
    if not requiere_portafolio(1):
        return
    ui.hero('Machine Learning — dirección del precio', 'Compara Random Forest, XGBoost y Regresión Logística para estimar si el precio subirá o bajará mañana. Una exactitud cercana a 50 % equivale a lanzar una moneda.', eyebrow='Herramientas')
    ui.en_simple("El sistema mira cómo se movió el precio en los últimos 5 días y aprende de miles de casos "
                 "pasados para estimar si mañana subirá o bajará. Prueba 3 modelos (Random Forest, XGBoost y "
                 "Regresión Logística), elige el que más acierta y se reentrena solo cada 8 días. "
                 "Los mercados son muy difíciles de predecir: acertar 55 % de las veces ya se considera bueno.",
                 "Cómo funciona")

    # ── SECCIÓN 1: CONTROLES ──
    with st.container(border=True):
        col1, col2 = st.columns([1, 1])

        with col1:
            st.markdown("### 🏋️ Entrenamiento")
            ticker_ml = st.selectbox("Activo a entrenar", tickers, key="ml_t")
            col_opt1, col_opt2 = st.columns(2)
            with col_opt1:
                optimizar_hp = st.checkbox("⚙️ Optimizar hiperparámetros", value=True,
                    help="GridSearchCV busca los mejores parámetros automáticamente")
            with col_opt2:
                forzar_ent = st.checkbox("🔄 Forzar reentrenamiento", value=False,
                    help="Reentrenar aunque no hayan pasado 8 días")

            if st.button("Entrenar Modelos", key="btn_ml_t", use_container_width=True):
                with st.spinner(f"Entrenando y comparando modelos para {ticker_ml}..."):
                    params = f"?optimizar={str(optimizar_hp).lower()}&forzar={str(forzar_ent).lower()}"
                    d = api_post(f"/ml/entrenar/{ticker_ml}{params}")
                if d:
                    if d.get("mensaje") == "Modelo vigente":
                        st.session_state["ml_aviso"] = f"ℹ️ Modelo vigente — entrenado hace {d.get('dias_desde_entrenamiento', 0)} días. Activa 'Forzar reentrenamiento' para actualizar."
                    else:
                        st.session_state[f"ml_trained_{ticker_ml}"] = d
                        st.session_state["ml_ultimo_resultado"] = d
                        st.session_state["ml_aviso"] = None
                    st.rerun()

            st.divider()

            if st.button("🚀 Entrenar TODOS los activos", key="btn_ml_all",
                        use_container_width=True, type="primary"):
                progreso = st.progress(0, text="Iniciando entrenamiento...")
                params = f"?optimizar={str(optimizar_hp).lower()}&forzar={str(forzar_ent).lower()}"
                ultimo_resultado = None
                for i, t in enumerate(tickers):
                    progreso.progress((i + 0.5) / len(tickers), text=f"Entrenando {t}...")
                    d = api_post(f"/ml/entrenar/{t}{params}")
                    if d and d.get("mensaje") != "Modelo vigente":
                        st.session_state[f"ml_trained_{t}"] = d
                        ultimo_resultado = d
                    progreso.progress((i + 1) / len(tickers), text=f"Prediciendo {t}...")
                    d_pred = api_post(f"/ml/predecir/{t}")
                    if d_pred:
                        st.session_state[f"ml_pred_{t}"] = d_pred
                progreso.empty()
                if ultimo_resultado:
                    st.session_state["ml_ultimo_resultado"] = ultimo_resultado
                    st.session_state["ml_aviso"] = None
                else:
                    st.session_state["ml_aviso"] = "ℹ️ Modelos vigentes. Activa 'Forzar reentrenamiento' para actualizar."
                st.rerun()

        with col2:
            st.markdown("### 🔮 Predicción")
            ticker_p = st.selectbox("Activo a predecir", tickers, key="ml_p")

            estado_ml = api_get("/ml/estado")
            if not (estado_ml and estado_ml.get("modelo_entrenado")):
                st.warning("⚠️ Entrena el modelo primero.")

            if st.button("Ejecutar Predicción", key="btn_ml_p", use_container_width=True):
                with st.spinner(f"Prediciendo {ticker_p}..."):
                    d = api_post(f"/ml/predecir/{ticker_p}")
                if d:
                    st.session_state[f"ml_pred_{ticker_p}"] = d

            pred = st.session_state.get(f"ml_pred_{ticker_p}")
            if pred:
                prob = pred['probabilidad']
                label = pred['direccion'].upper()
                color = "#10b981" if label == "SUBE" else "#ef4444"
                emoji = "📈" if label == "SUBE" else "📉"

                fig_gauge = go.Figure(go.Indicator(
                    mode="gauge+number+delta",
                    value=prob * 100,
                    domain={'x': [0, 1], 'y': [0, 1]},
                    title={'text': f"{emoji} Señal: {label}", 'font': {'size': 18}},
                    delta={'reference': 50, 'increasing': {'color': "#10b981"},
                           'decreasing': {'color': "#ef4444"}},
                    gauge={
                        'axis': {'range': [0, 100]},
                        'bar': {'color': color},
                        'steps': [
                            {'range': [0, 40], 'color': "rgba(239,68,68,0.2)"},
                            {'range': [40, 60], 'color': "rgba(245,158,11,0.2)"},
                            {'range': [60, 100], 'color': "rgba(16,185,129,0.2)"},
                        ],
                        'threshold': {'line': {'color': "white", 'width': 3},
                                      'thickness': 0.75, 'value': 50}
                    }
                ))
                fig_gauge.update_layout(height=280, margin=dict(l=20, r=20, t=60, b=20))
                st.plotly_chart(fig_gauge, use_container_width=True)

                precio_act = 100.0
                try:
                    p = cached_get(f"/precios/{ticker_p}")
                    if p: precio_act = float(p[-1]["close"])
                except: pass

                confianza = "ALTA" if prob > 0.7 else "MEDIA" if prob > 0.55 else "BAJA"
                mejor_mod = estado_ml.get('mejor_modelo', 'XGBoost') if estado_ml else 'XGBoost'
                st.markdown(f"""
                **Precio actual {ticker_p}:** USD {precio_act:,.2f}  
                **Señal:** {emoji} {label} con confianza **{confianza}** ({prob:.1%})  
                **Modelo usado:** {mejor_mod}
                """)

    # ── SECCIÓN 2: RESULTADOS DEL ENTRENAMIENTO ──
    st.divider()

    # Aviso de modelo vigente
    if st.session_state.get("ml_aviso"):
        st.info(st.session_state["ml_aviso"])

    # Estado del modelo
    if estado_ml and estado_ml.get("modelo_entrenado"):
        st.markdown("### 📊 Estado del Modelo")
        col_e1, col_e2, col_e3, col_e4 = st.columns(4)
        col_e1.metric("🏆 Mejor Modelo", estado_ml.get("mejor_modelo", "—"))
        col_e2.metric("🎯 Accuracy", f"{estado_ml.get('accuracy', 0):.2%}")
        fecha_ent = estado_ml.get("fecha_entrenamiento", "—")
        if fecha_ent != "—":
            from datetime import datetime
            fecha_fmt = datetime.fromisoformat(fecha_ent).strftime("%d/%m/%Y %H:%M")
        else:
            fecha_fmt = "—"
        col_e3.metric("📅 Último Entrenamiento", fecha_fmt)
        necesita = estado_ml.get("necesita_reentrenamiento", False)
        col_e4.metric("🔄 Reentrenamiento", "⚠️ Necesario" if necesita else "✅ Vigente")
    else:
        st.info("⏳ No hay modelo entrenado. Entrena uno primero.", icon="🧠")

    # Tabla comparativa
    ultimo = st.session_state.get("ml_ultimo_resultado")
    comp_data = None
    if ultimo and ultimo.get("comparacion"):
        comp_data = ultimo["comparacion"]
        mejor_nombre = ultimo.get("mejor_modelo")
        st.success(f"✅ Último entrenamiento — Mejor modelo: **{mejor_nombre}** — Accuracy: {ultimo.get('accuracy', 0):.2%}")
    elif estado_ml and estado_ml.get("comparacion_modelos"):
        comp_data = estado_ml["comparacion_modelos"]
        mejor_nombre = estado_ml.get("mejor_modelo")

    if comp_data:
        st.markdown("### 🥇 Comparación de Modelos")
        rows = []
        for nombre, metricas in comp_data.items():
            es_mejor = nombre == mejor_nombre
            rows.append({
                "Modelo": f"⭐ {nombre}" if es_mejor else nombre,
                "Accuracy": f"{metricas['accuracy']:.2%}",
                "Precisión": f"{metricas['precision']:.2%}",
                "Recall": f"{metricas['recall']:.2%}",
                "Estado": "✅ SELECCIONADO" if es_mejor else "—",
            })
        st.dataframe(pd.DataFrame(rows).set_index("Modelo"), use_container_width=True)

    # ── SECCIÓN 3: RESUMEN DE SEÑALES ──
    preds_guardadas = {t: st.session_state[f"ml_pred_{t}"]
                       for t in tickers if f"ml_pred_{t}" in st.session_state}
    if preds_guardadas:
        st.divider()
        st.markdown("### 📊 Resumen de Señales del Portafolio")
        cols = st.columns(len(preds_guardadas))
        for i, (t, p) in enumerate(preds_guardadas.items()):
            label = p['direccion'].upper()
            prob = p['probabilidad']
            emoji = "📈" if label == "SUBE" else "📉"
            confianza = "ALTA" if prob > 0.7 else "MEDIA" if prob > 0.55 else "BAJA"
            color_delta = "normal" if label == "SUBE" else "inverse"
            with cols[i]:
                st.metric(f"{emoji} {t}", label,
                    delta=f"{prob:.1%} — {confianza}", delta_color=color_delta)

        st.divider()
        compras = sum(1 for p in preds_guardadas.values() if p['direccion'].upper() == "SUBE")
        ventas = sum(1 for p in preds_guardadas.values() if p['direccion'].upper() == "BAJA")
        total = len(preds_guardadas)

        if compras > ventas:
            st.success(f"📈 **Sesgo alcista** — {compras}/{total} activos con señal de SUBE.")
        elif ventas > compras:
            st.error(f"📉 **Sesgo bajista** — {ventas}/{total} activos con señal de BAJA.")
        else:
            st.warning(f"⚖️ **Portafolio neutral** — señales mixtas.")

        st.info("⚠️ **Importante:** predicciones basadas en ML con datos históricos. No constituyen asesoramiento financiero.")

    ui.guia_lectura("Cómo leer los resultados del modelo", [
        {"Indicador": "Accuracy (exactitud)", "Qué mide": "% de días en que el modelo acertó si subía o bajaba.",
         "Cómo leerlo": ("alerta", "≈ 50 % igual que lanzar una moneda · 52–55 % modesto · > 55 % bueno · > 65 % sospechoso (posible sobreajuste)")},
        {"Indicador": "Precisión", "Qué mide": "De las veces que dijo 'sube', cuántas realmente subió.",
         "Cómo leerlo": "Alta precisión = pocas falsas alarmas de subida."},
        {"Indicador": "Recall (sensibilidad)", "Qué mide": "De los días que realmente subió, cuántos detectó.",
         "Cómo leerlo": "Alto recall = se le escapan pocas subidas."},
        {"Indicador": "Probabilidad de la predicción", "Qué mide": "Qué tan seguro está el modelo de su señal.",
         "Cómo leerlo": "50–55 % confianza baja · 55–70 % media · > 70 % alta. Cerca de 50 % = el modelo no sabe."},
        {"Indicador": "Reentrenamiento", "Qué mide": "Si el modelo se actualizó con los datos recientes.",
         "Cómo leerlo": "Los patrones del mercado cambian; un modelo viejo pierde validez."},
    ], columnas=("Indicador", "Qué mide", "Cómo leerlo"))




# ─────────────────────────── ARQUITECTURA ───────────────────────────
def pagina_arquitectura():
    ui.hero('Arquitectura técnica — del dato a la visualización', 'Cómo viaja un dato desde Yahoo Finance hasta este tablero: Streamlit → FastAPI → SQLAlchemy → SQLite / Databricks.', eyebrow='Herramientas')
    st.markdown(
        "Explora un llamado real del sistema y observa cómo cambia el recorrido entre "
        "**Streamlit**, **FastAPI**, **SQLAlchemy** y **SQLite**."
    )

    recorridos = {
        "Lectura de precios": {
            "color": "#1a56db",
            "metodo": "GET",
            "endpoint": "/precios/AAPL",
            "accion": "SELECT",
            "recurso": "prices",
            "salida": "Serie OHLCV",
            "objetivo": "Recuperar precios previamente almacenados para graficarlos.",
            "nodos": ["Streamlit", "FastAPI", "Router precios", "SQLAlchemy SELECT", "SQLite", "Plotly"],
            "etapas": [
                ("Solicitud", "El usuario elige AAPL y Streamlit solicita precios históricos."),
                ("Validación", "FastAPI resuelve el endpoint y obtiene una sesión de base de datos."),
                ("Lectura ORM", "SQLAlchemy busca el activo y sus registros de precios."),
                ("Respuesta", "SQLite entrega filas y la API las serializa como JSON."),
                ("Visualización", "Plotly dibuja la serie de precios en el dashboard."),
            ],
            "request": 'requests.get(f"{API}/precios/AAPL")',
            "orm": (
                'asset = db.scalars(select(Asset).where(Asset.ticker == "AAPL")).first()\n'
                "precios = db.scalars(\n"
                "    select(Price).where(Price.asset_id == asset.id)\n"
                ").all()"
            ),
            "json": '[{"fecha": "2026-05-26", "close": 201.42, "volume": 45210300}]',
            "presentacion": "Gráfico de velas y rendimiento base 100",
        },
        "Persistencia desde Yahoo": {
            "color": "#059669",
            "metodo": "POST",
            "endpoint": "/precios/descargar/AAPL",
            "accion": "INSERT / COMMIT",
            "recurso": "assets + prices",
            "salida": "Cache actualizada",
            "objetivo": "Descargar precios externos y persistir solo las fechas nuevas.",
            "nodos": ["Streamlit", "FastAPI", "DataService", "yfinance", "SQLAlchemy COMMIT", "SQLite"],
            "etapas": [
                ("Acción", "El usuario inicializa el portafolio desde Streamlit."),
                ("Descarga", "FastAPI delega a DataService y consulta Yahoo Finance."),
                ("Control", "Se verifica si el activo y cada fecha ya existen."),
                ("Escritura ORM", "Los nuevos objetos Price se agregan y confirman."),
                ("Cache", "SQLite conserva los datos para consultas posteriores."),
            ],
            "request": 'requests.post(f"{API}/precios/descargar/AAPL")',
            "orm": (
                "precio = Price(asset_id=activo.id, fecha=fecha_date, close=close, ...)\n"
                "self.db.add(precio)\n"
                "self.db.commit()"
            ),
            "json": '{"ticker": "AAPL", "registros_disponibles": 756, "cache": "actualizada"}',
            "presentacion": "Confirmación de descarga y datos habilitados",
        },
        "Análisis de riesgo": {
            "color": "#7c3aed",
            "metodo": "GET",
            "endpoint": "/analisis/var/AAPL",
            "accion": "SELECT + CÁLCULO",
            "recurso": "prices",
            "almacen": "SQLite · `risklab.db`",
            "salida": "VaR / CVaR",
            "objetivo": "Leer datos persistidos, calcular riesgo y presentar métricas.",
            "nodos": ["Streamlit", "FastAPI", "RiskService", "SQLAlchemy SELECT", "SQLite", "Métricas"],
            "etapas": [
                ("Parámetros", "Streamlit envía ticker, periodo y nivel de confianza."),
                ("Datos", "El endpoint carga precios históricos desde SQLite."),
                ("Cálculo", "RiskService transforma precios en rendimientos logarítmicos."),
                ("Métrica", "Se estiman VaR paramétrico, histórico, Monte Carlo y CVaR."),
                ("Resultado", "Streamlit presenta indicadores y gráficos comparativos."),
            ],
            "request": 'requests.get(f"{API}/analisis/var/AAPL", params={"nivel": 0.95})',
            "orm": (
                "precios = db.scalars(\n"
                "    select(Price).where(Price.asset_id == asset.id).order_by(Price.fecha)\n"
                ").all()\n"
                "resultado = RiskService(df).var_historico()"
            ),
            "json": '{"var_historico": -0.0214, "cvar": -0.0318, "nivel": 0.95}',
            "presentacion": "Tarjetas VaR/CVaR y análisis de exposición",
        },
        "Consulta cloud Databricks": {
            "color": "#ff5f46",
            "metodo": "GET",
            "endpoint": "/databricks/risklab-prices/resumen",
            "accion": "SQL WAREHOUSE",
            "recurso": "risklab_prices",
            "almacen": "Databricks SQL Warehouse",
            "salida": "Resumen cloud",
            "objetivo": "Consultar en Databricks la tabla sincronizada desde SQLite.",
            "nodos": ["Streamlit", "FastAPI", "DatabricksService", "SQL Warehouse", "risklab_prices", "Resumen"],
            "etapas": [
                ("Petición", "Streamlit solicita el resumen cloud expuesto por FastAPI."),
                ("Credenciales", "El backend lee hostname, HTTP path y token desde `backend/.env`."),
                ("Warehouse", "Databricks SQL ejecuta la consulta sobre `risklab_prices`."),
                ("Agregación", "La tabla devuelve registros, fechas y precios promedio por ticker."),
                ("Presentación", "El dashboard puede mostrar la evidencia de integración cloud."),
            ],
            "request": 'requests.get(f"{API}/databricks/risklab-prices/resumen")',
            "orm": (
                "with sql.connect(server_hostname=host, http_path=http_path, access_token=token) as conn:\n"
                "    cursor.execute('''\n"
                "        SELECT ticker, COUNT(*) AS registros, AVG(close) AS precio_promedio\n"
                "        FROM risklab_prices GROUP BY ticker\n"
                "    ''')"
            ),
            "json": '{"tabla": "risklab_prices", "datos": [{"ticker": "AAPL", "registros": 751}]}',
            "presentacion": "Tabla resumen consultada desde Databricks",
        },
    }

    if "arquitectura_recorrido" not in st.session_state:
        st.session_state["arquitectura_recorrido"] = "Lectura de precios"
    recorrido = st.session_state["arquitectura_recorrido"]
    escenario = recorridos[recorrido]

    flujo_tab, sql_tab, infraestructura_tab = st.tabs(
        ["🔄 Flujo de llamados", "🗃️ SQL y consultas", "🐳 Infraestructura"]
    )

    with flujo_tab:
        st.markdown("#### Elige el caso que quieres explicar")
        botones = st.columns(len(recorridos))
        for idx, (nombre_recorrido, datos_recorrido) in enumerate(recorridos.items()):
            activo = nombre_recorrido == recorrido
            with botones[idx]:
                st.markdown(
                    f"""
                    <div style="height:74px; border:2px solid {'{0}'.format(datos_recorrido['color']) if activo else '#dbe3ef'};
                                background:{'rgba(26,86,219,0.08)' if activo else '#ffffff'};
                                border-radius:14px; padding:10px; margin-bottom:6px;">
                        <div style="font-size:12px; font-weight:700; color:{datos_recorrido['color']};">
                            {datos_recorrido['metodo']}
                        </div>
                        <div style="font-size:13px; font-weight:700; color:#1e293b; line-height:1.15;">
                            {'✓ ' if activo else ''}{nombre_recorrido}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                if st.button(
                    "Seleccionado" if activo else "Seleccionar",
                    key=f"btn_recorrido_{nombre_recorrido}",
                    type="primary" if activo else "secondary",
                    use_container_width=True,
                ):
                    st.session_state["arquitectura_recorrido"] = nombre_recorrido
                    st.rerun()

        st.markdown(
            f"""
            <div style="border-left:6px solid {escenario['color']}; background:#ffffff;
                        padding:14px 18px; border-radius:10px; margin:18px 0;">
              <div style="font-size:12px; font-weight:700; color:{escenario['color']};">
                RECORRIDO ACTIVO · {escenario['metodo']} {escenario['endpoint']}
              </div>
              <div style="font-size:16px; font-weight:600; margin-top:5px;">{recorrido}</div>
              <div style="font-size:13px; color:#475569; margin-top:5px;">{escenario['objetivo']}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Petición HTTP", escenario["metodo"])
        c1.caption(escenario["endpoint"])
        c2.metric("Operación ORM", escenario["accion"])
        c2.caption("SQLAlchemy 2.0")
        c3.metric("Tabla / recurso", escenario["recurso"])
        c3.caption(escenario.get("almacen", "SQLite · `risklab.db`"))
        c4.metric("Resultado final", escenario["salida"])
        c4.caption(escenario["presentacion"])

        st.markdown(f"### Ruta activa: {recorrido}")
        nodos = escenario["nodos"]
        x_pos = list(range(len(nodos)))
        fig_flujo = go.Figure()
        fig_flujo.add_trace(go.Scatter(
            x=x_pos,
            y=[0] * len(nodos),
            mode="lines",
            line=dict(color=escenario["color"], width=5),
            hoverinfo="skip",
        ))
        fig_flujo.add_trace(go.Scatter(
            x=x_pos,
            y=[0] * len(nodos),
            mode="markers+text",
            marker=dict(
                size=42,
                color=escenario["color"],
                line=dict(width=4, color="white"),
                symbol="circle",
            ),
            text=[str(i + 1) for i in x_pos],
            textfont=dict(color="white", size=15, family="Arial Black"),
            textposition="middle center",
            hovertext=nodos,
            hovertemplate="%{hovertext}<extra></extra>",
        ))
        for x, nodo in zip(x_pos, nodos):
            fig_flujo.add_annotation(
                x=x,
                y=-0.18,
                text=f"<b>{nodo}</b>",
                showarrow=False,
                font=dict(size=11, color="#475569"),
                align="center",
            )
        fig_flujo.update_layout(
            height=210,
            margin=dict(l=20, r=20, t=20, b=65),
            paper_bgcolor="rgba(255,255,255,0)",
            plot_bgcolor="rgba(255,255,255,0)",
            showlegend=False,
            xaxis=dict(visible=False, range=[-0.35, len(nodos) - 0.65]),
            yaxis=dict(visible=False, range=[-0.28, 0.16]),
        )
        st.plotly_chart(
            fig_flujo,
            use_container_width=True,
            config={"displayModeBar": False, "staticPlot": False},
        )

        for numero, (titulo, detalle) in enumerate(escenario["etapas"], start=1):
            with st.expander(f"{numero}. {titulo}", expanded=numero == 1):
                st.markdown(detalle)

        peticion, respuesta = st.columns(2)
        with peticion:
            st.markdown("**Llamado desde Streamlit**")
            st.code(escenario["request"], language="python")
        with respuesta:
            st.markdown("**Respuesta consumida por la visualización**")
            st.code(escenario["json"], language="json")

    with sql_tab:
        st.markdown(f"### SQLAlchemy en el recorrido: {recorrido}")
        st.info(
            "El proyecto usa SQL a través del ORM de **SQLAlchemy**: el código "
            "trabaja con modelos Python y `select(...)`; SQLAlchemy genera las "
            "sentencias que SQLite ejecuta."
        )

        izquierda, derecha = st.columns([1.05, 0.95])
        with izquierda:
            with st.container(border=True):
                st.markdown(f"**Operación elegida: `{escenario['accion']}`**")
                st.caption(f"Endpoint involucrado: `{escenario['metodo']} {escenario['endpoint']}`")
                st.code(escenario["orm"], language="python")

            with st.expander("Conexión e inicialización"):
                st.markdown(
                    "`backend/app/database.py` crea el engine, abre sesiones por "
                    "request y crea las tablas al iniciar FastAPI."
                )
                st.code(
                    'engine = create_engine(\n'
                    '    settings.database_url,\n'
                    '    connect_args={"check_same_thread": False},\n'
                    ')\n'
                    'SessionLocal = sessionmaker(bind=engine)\n'
                    'Base.metadata.create_all(bind=engine)',
                    language="python",
                )

        with derecha:
            st.markdown("#### Evidencia en la base de datos")
            tablas = pd.DataFrame(
                [
                    {"Tabla": "assets", "Rol": "Catálogo de tickers", "Participa en esta ruta": recorrido != "Análisis de riesgo"},
                    {"Tabla": "prices", "Rol": "Históricos OHLCV", "Participa en esta ruta": True},
                    {"Tabla": "portfolios", "Rol": "Asignación y pesos", "Participa en esta ruta": False},
                    {"Tabla": "prediction_logs", "Rol": "Salida de ML", "Participa en esta ruta": False},
                    {"Tabla": "signals_log", "Rol": "Alertas técnicas", "Participa en esta ruta": False},
                    {
                        "Tabla": "risklab_prices",
                        "Rol": "Tabla cloud usada solo en el recorrido Databricks",
                        "Participa en esta ruta": recorrido == "Consulta cloud Databricks",
                    },
                ]
            )
            tablas["Participa en esta ruta"] = tablas["Participa en esta ruta"].map({True: "Sí", False: "No"})
            st.dataframe(tablas, use_container_width=True, hide_index=True)

            with st.expander("Modelos ORM verificados"):
                st.markdown(
                    "Las tablas ORM verificadas son **assets**, **prices**, "
                    "**portfolios**, **prediction_logs** y **signals_log**."
                )
                st.code(
                    'class Price(Base):\n'
                    '    __tablename__ = "prices"\n'
                    '    asset_id = mapped_column(ForeignKey("assets.id"))\n'
                    '    fecha = mapped_column(Date)\n'
                    '    close = mapped_column(Float)',
                    language="python",
                )

    with infraestructura_tab:
        col_docker, col_bricks = st.columns(2)
        with col_docker:
            with st.container(border=True):
                st.markdown("### 🐳 Docker")
                st.markdown(
                    "El repositorio incluye contenedores separados para la API y "
                    "el dashboard. `docker-compose.yml` publica ambos puertos y "
                    "monta `risklab.db` para conservar los datos del backend."
                )
                st.code(
                    "frontend:8501  -->  http://backend:8000\n"
                    "backend:8000   -->  /app/risklab.db (volumen)",
                    language="text",
                )
                st.caption(
                    f"El recorrido **{recorrido}** viaja por esta red como "
                    f"`{escenario['metodo']} {escenario['endpoint']}`."
                )

        with col_bricks:
            with st.container(border=True):
                st.markdown("### 🧱 Bricks / Databricks")
                st.success("Integración cloud opcional configurada.")
                st.markdown(
                    "El backend puede conectarse a **Databricks SQL Warehouse** "
                    "usando `DATABRICKS_SERVER_HOSTNAME`, `DATABRICKS_HTTP_PATH` "
                    "y `DATABRICKS_TOKEN`. La tabla demo es **risklab_prices**, "
                    "cargada desde los precios de SQLite."
                )
                st.code(
                    "Flujo actual:\n"
                    "yfinance → FastAPI → SQLite → SQLAlchemy → modelos\n\n"
                    "Flujo complementario:\n"
                    "Databricks → FastAPI → consultas SQL → dashboard\n\n"
                    "FastAPI intenta yfinance\n"
                    "  ↓ si falla\n"
                    "FastAPI consulta Databricks risklab_prices\n"
                    "  ↓\n"
                    "continúa el análisis",
                    language="text",
                )

        st.divider()
        st.markdown("### 🔎 Laboratorio SQL en Databricks")
        st.caption(
            "Selecciona una consulta predefinida. FastAPI la ejecuta en Databricks SQL Warehouse "
            "sobre la tabla `risklab_prices` y devuelve el resultado al dashboard."
        )

        consultas_data = api_get("/databricks/consultas", timeout=60)
        consultas = consultas_data.get("consultas", []) if consultas_data else []
        if not consultas:
            st.info(
                "Modo demostración: el backend desplegado todavía no expone las consultas de Databricks "
                "o no tiene credenciales cloud configuradas. La integración queda documentada y lista para "
                "activarse cuando el deploy incluya las variables `DATABRICKS_*`."
            )
            consultas = [
                {
                    "id": "promedio_cierre",
                    "titulo": "Promedio de cierre por activo",
                    "descripcion": "Promedio, mínimo y máximo del precio de cierre por ticker.",
                    "sql": "SELECT ticker, COUNT(*) AS registros, ROUND(AVG(close), 2) AS cierre_promedio, ROUND(MIN(close), 2) AS cierre_minimo, ROUND(MAX(close), 2) AS cierre_maximo FROM risklab_prices GROUP BY ticker ORDER BY cierre_promedio DESC",
                    "demo": True,
                },
                {
                    "id": "top_5_ultimo_cierre",
                    "titulo": "Top 5 por último cierre",
                    "descripcion": "Activos con mayor precio en la fecha más reciente disponible.",
                    "sql": "WITH ultimos AS (SELECT ticker, MAX(fecha) AS fecha FROM risklab_prices GROUP BY ticker) SELECT p.ticker, p.fecha, ROUND(p.close, 2) AS ultimo_cierre FROM risklab_prices p INNER JOIN ultimos u ON p.ticker = u.ticker AND p.fecha = u.fecha ORDER BY ultimo_cierre DESC LIMIT 5",
                    "demo": True,
                },
                {
                    "id": "menor_fluctuacion_mes",
                    "titulo": "Menor fluctuación en el último mes",
                    "descripcion": "Activos con menor rango porcentual aproximado en los últimos 30 días.",
                    "sql": "SELECT ticker, ROUND((MAX(close) - MIN(close)) / AVG(close) * 100, 2) AS fluctuacion_pct FROM risklab_prices WHERE fecha >= DATE_SUB((SELECT MAX(fecha) FROM risklab_prices), 30) GROUP BY ticker ORDER BY fluctuacion_pct ASC LIMIT 5",
                    "demo": True,
                },
            ]
            st.caption("Estas consultas se muestran como ejemplo de presentación; no ejecutan el warehouse en modo demo.")

        consulta_map = {c["titulo"]: c for c in consultas}
        consulta_titulo = st.selectbox(
            "Consulta SQL preseleccionada",
            options=list(consulta_map.keys()),
            key="consulta_databricks_sql",
        )
        consulta_sel = consulta_map[consulta_titulo]
        consultas_con_filtro = {
            "promedio_cierre",
            "desviacion_cierre",
            "minimos_maximos",
            "menor_fluctuacion_mes",
            "mayor_volumen_promedio",
            "rendimiento_periodo",
            "ultimo_mes_retorno",
            "dias_disponibles",
        }
        permite_filtro_ticker = consulta_sel["id"] in consultas_con_filtro
        tickers_consulta = []

        if permite_filtro_ticker:
            opciones_ticker_sql = sorted(set(TICKERS_DB.keys()) | set(tickers))
            default_ticker_sql = [t for t in tickers if t in opciones_ticker_sql][:5]
            if not default_ticker_sql and "AAPL" in opciones_ticker_sql:
                default_ticker_sql = ["AAPL"]

            tickers_consulta = st.multiselect(
                "Activos para esta consulta",
                options=opciones_ticker_sql,
                default=default_ticker_sql,
                format_func=lambda t: f"{t} — {TICKERS_DB.get(t, t)}",
                help="Puedes escoger uno o varios activos. FastAPI enviará esos tickers a Databricks como filtro SQL.",
                key=f"tickers_databricks_{consulta_sel['id']}",
            )
            st.caption(
                "La consulta se ejecutará solo sobre los activos seleccionados; "
                "si eliges varios, compara sus resultados en la misma tabla."
            )

        def preview_sql_filtrado(sql_base, consulta_id, tickers_elegidos):
            if not tickers_elegidos or consulta_id not in consultas_con_filtro:
                return sql_base

            valores = ", ".join(f"'{ticker}'" for ticker in tickers_elegidos)
            filtro = f"ticker IN ({valores})"

            if consulta_id in {"menor_fluctuacion_mes", "ultimo_mes_retorno"}:
                return sql_base.replace(
                    "WHERE fecha >= DATE_SUB((SELECT MAX(fecha) FROM risklab_prices), 30)",
                    "WHERE fecha >= DATE_SUB((SELECT MAX(fecha) FROM risklab_prices), 30)"
                    f"\n            AND {filtro}",
                    1,
                )

            if consulta_id == "rendimiento_periodo":
                return sql_base.replace(
                    "FROM risklab_prices",
                    f"FROM risklab_prices\n                WHERE {filtro}",
                    1,
                )

            return sql_base.replace(
                "FROM risklab_prices",
                f"FROM risklab_prices\n            WHERE {filtro}",
                1,
            )

        resultado_previo_sql = st.session_state.get("resultado_databricks_sql")
        sql_mostrado = preview_sql_filtrado(
            consulta_sel["sql"],
            consulta_sel["id"],
            tickers_consulta,
        )
        if (
            resultado_previo_sql
            and resultado_previo_sql.get("id") == consulta_sel["id"]
            and (
                not permite_filtro_ticker
                or resultado_previo_sql.get("tickers", []) == tickers_consulta
            )
        ):
            sql_mostrado = resultado_previo_sql.get("sql", sql_mostrado)

        sql_col, resultado_col = st.columns([1, 1.25])
        with sql_col:
            st.markdown(f"**{consulta_sel['titulo']}**")
            st.caption(consulta_sel["descripcion"])
            st.code(sql_mostrado, language="sql")

        with resultado_col:
            if consulta_sel.get("demo"):
                st.warning("Consulta no ejecutada: backend desplegado sin endpoint/credenciales Databricks.")
                st.markdown(
                    """
                    **Qué demuestra esta consulta**
                    - La tabla cloud esperada es `risklab_prices`.
                    - El cálculo se haría directamente en Databricks SQL Warehouse.
                    - Al configurar las variables `DATABRICKS_*` en el backend desplegado, aquí aparecerá la tabla real.
                    """
                )
            else:
                params_sql = {"tickers": tickers_consulta} if tickers_consulta else None
                filtro_activo = tickers_consulta if permite_filtro_ticker else []

                if permite_filtro_ticker and not tickers_consulta:
                    st.warning("Selecciona al menos un activo para ejecutar esta consulta filtrada.")

                if st.button(
                    "▶ Ejecutar consulta en Databricks",
                    key="btn_run_databricks_sql",
                    type="primary",
                    disabled=permite_filtro_ticker and not tickers_consulta,
                ):
                    respuesta_databricks = api_get(
                        f"/databricks/consultas/{consulta_sel['id']}",
                        params=params_sql,
                        timeout=120,
                    )
                    st.session_state["resultado_databricks_sql"] = respuesta_databricks

                resultado_sql = st.session_state.get("resultado_databricks_sql")
                resultado_tickers = resultado_sql.get("tickers", []) if resultado_sql else []
                misma_consulta = resultado_sql and resultado_sql.get("id") == consulta_sel["id"]
                filtro_coincide = (
                    not permite_filtro_ticker
                    or not resultado_tickers
                    or resultado_tickers == filtro_activo
                )
                if misma_consulta and filtro_coincide:
                    df_sql = pd.DataFrame(resultado_sql.get("resultados", []))
                    if permite_filtro_ticker and tickers_consulta and "ticker" in df_sql.columns:
                        df_sql = df_sql[df_sql["ticker"].isin(tickers_consulta)]
                    if df_sql.empty:
                        st.info("La consulta no devolvió filas.")
                    else:
                        if resultado_tickers:
                            st.caption(f"Filtro aplicado: {', '.join(resultado_tickers)}")
                        elif permite_filtro_ticker and tickers_consulta:
                            st.caption(
                                "Filtro aplicado en la visualización: "
                                f"{', '.join(tickers_consulta)}. Reinicia FastAPI para que Databricks ejecute el filtro directamente."
                            )
                        numeric_cols = [
                            col for col in df_sql.columns
                            if pd.api.types.is_numeric_dtype(pd.to_numeric(df_sql[col], errors="coerce"))
                        ]
                        metric_cols = st.columns(min(3, max(1, len(numeric_cols))))
                        if numeric_cols:
                            for i, col in enumerate(numeric_cols[:3]):
                                valor = pd.to_numeric(df_sql[col], errors="coerce").dropna()
                                if not valor.empty:
                                    metric_cols[i].metric(col.replace("_", " ").title(), f"{valor.iloc[0]:,.2f}")
                        st.dataframe(df_sql, use_container_width=True, hide_index=True)
                else:
                    st.info("Ejecuta la consulta para ver evidencia numérica desde Databricks.")



# ─────────────────────────── AGENTE IA ───────────────────────────
def pagina_agente():
    if not requiere_portafolio(1):
        return
    ui.hero('Agente IA — análisis en lenguaje natural', 'Un modelo de lenguaje local (Ollama) redacta un informe ejecutivo con las métricas reales de tu portafolio y responde preguntas.', eyebrow='Herramientas')
    st.info("Análisis de riesgo en lenguaje natural potenciado por **llama3** corriendo localmente con Ollama.", icon="🤖")

    # ── Estado de Ollama ──────────────────────────────────────────────────────
    estado = api_get("/agente/estado")
    if not estado or not estado.get("disponible"):
        st.error("❌ Ollama no está corriendo. Abre una terminal y ejecuta: `ollama serve`")
        return

    st.success(f"✅ Ollama activo | Modelo: **{estado['modelo_activo']}** | "
               f"Modelos instalados: {', '.join(estado['modelos'])}")

    subtab_auto, subtab_chat = st.tabs(["📊 Análisis Automático", "💬 Chat Financiero"])

    # ── Sub-tab 1: Análisis automático ────────────────────────────────────────
    with subtab_auto:
        st.markdown("El agente recopila todas las métricas del portafolio y genera un **informe ejecutivo** completo.")

        if st.button("🔍 Generar Informe con IA", key="btn_agente", type="primary"):

            with st.spinner("⏳ Recopilando métricas del portafolio..."):
                data_res  = fetch("/analisis/resumen-portafolio", {**P_BASE, "benchmark": benchmark,
                                                                    "nivel": confianza_var, "rf": tasa_fred})
                # Adaptación al formato que espera el agente (métricas reales del portafolio)
                data_var  = {"var_historico": data_res["var_historico"], "cvar": data_res["cvar_historico"]} if data_res else None
                data_port = {"volatilidad_anual_portafolio": data_res["volatilidad_anual"],
                             "retorno_anual_esperado": data_res["retorno_anual"]} if data_res else None
                data_mk   = {"optimizacion": {"sharpe_ratio": data_res["sharpe"]}} if data_res else None
                data_capm = {"activos": [{"beta": data_res.get("beta", 1.0)}]} if data_res else None

            if not data_var or not data_port:
                st.error("⚠️ Ve primero al Tab 1 para cargar los datos del portafolio.")
            else:
                var_h     = abs(data_var.get("var_historico", 0.02))
                cvar_v    = abs(data_var.get("cvar", 0.025))
                vol_anual = data_port.get("volatilidad_anual_portafolio", 0.15)
                ret_anual = data_port.get("retorno_anual_esperado", 0.08)
                sharpe_v  = data_mk["optimizacion"]["sharpe_ratio"] if data_mk and "optimizacion" in data_mk else 0.5
                beta_prom = (sum(a["beta"] for a in data_capm["activos"]) / len(data_capm["activos"])
                             if data_capm and "activos" in data_capm else 1.0)

                with st.spinner("🧠 llama3 analizando el portafolio... (puede tardar 30-60 segundos)"):
                    resultado = api_get("/agente/analisis", params={
                        "tickers": tickers, "benchmark": benchmark,
                        "var_historico": var_h, "cvar": cvar_v,
                        "sharpe": sharpe_v, "retorno_anual": ret_anual,
                        "volatilidad_anual": vol_anual, "beta_promedio": beta_prom,
                        "inversion": valor_portafolio,
                    }, timeout=360)

                if resultado:
                    nivel_riesgo = resultado.get("riesgo", "N/A")
                    color_riesgo = {"ALTO": "🔴", "MEDIO": "🟡", "BAJO": "🟢"}.get(nivel_riesgo, "⚪")
                    st.markdown(f"### {color_riesgo} Nivel de Riesgo Global: **{nivel_riesgo}**")
                    st.divider()
                    texto= resultado["analisis"].replace("$", "\\$")
                    st.markdown(texto)
                    st.divider()
                    st.caption(f"Generado por **{resultado['modelo']}** via Ollama · "
                               f"Portafolio: {', '.join(resultado['portafolio'])}")

    # ── Sub-tab 2: Chat ───────────────────────────────────────────────────────
    with subtab_chat:
        st.markdown("Haz preguntas sobre tu portafolio, conceptos de riesgo o métricas específicas.")

        contexto_port = (
            f"Portafolio: {', '.join(tickers)} | Benchmark: {benchmark} | "
            f"Inversión: ${valor_portafolio:,.0f} | Confianza VaR: {confianza_var:.0%} | "
            f"Tasa libre de riesgo: {tasa_fred*100:.2f}%"
        )

        if "chat_history" not in st.session_state:
            st.session_state.chat_history = []

        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        if pregunta := st.chat_input("Pregunta algo... ej: ¿Qué activo tiene mayor riesgo sistemático?"):
            st.session_state.chat_history.append({"role": "user", "content": pregunta})
            with st.chat_message("user"):
                st.markdown(pregunta)

            with st.chat_message("assistant"):
                with st.spinner("🤖 Pensando..."):
                    try:
                        r = requests.post(f"{API}/agente/chat", 
                            json={"pregunta": pregunta, "contexto": contexto_port}, 
                            timeout=600)
                        resp = r.json() if r.status_code == 200 else None
                    except Exception as e:
                        st.error(f"❌ {e}")
                        resp = None
                if resp:
                    st.markdown(resp["respuesta"])
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": resp["respuesta"],
                    })


# ═══════════════════════════ ENRUTADOR ═══════════════════════════
RUTAS = {
    "🏠 Inicio y guía de uso": pagina_inicio,
    "📋 Resumen ejecutivo": pagina_resumen,
    "📈 Precios y señales técnicas": pagina_tecnico,
    "📉 Rendimientos y distribución": pagina_rendimientos,
    "🌊 Volatilidad (EWMA / GARCH)": pagina_volatilidad,
    "🛡️ VaR y CVaR": pagina_var,
    "💥 Pruebas de estrés": pagina_stress,
    "🎯 CAPM y riesgo de mercado": pagina_capm,
    "⚡ Optimización (Markowitz)": pagina_markowitz,
    "🌐 Benchmark y macroeconomía": pagina_macro,
    "📐 Renta fija (bonos)": pagina_renta_fija,
    "🧮 Opciones (Black-Scholes)": pagina_opciones,
    "🤖 Machine Learning": pagina_ml,
    "🧠 Agente IA": pagina_agente,
    "🧩 Arquitectura técnica": pagina_arquitectura,
    "📖 Glosario": pagina_glosario,
}
assert set(RUTAS) == set(LISTA_PAGINAS)
RUTAS[pagina]()
