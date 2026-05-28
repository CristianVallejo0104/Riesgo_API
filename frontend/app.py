"""
frontend/app.py — RiskLab USTA Dashboard CIII
Consume los endpoints del backend FastAPI.
Correr: streamlit run frontend/app.py
"""
import urllib.parse 
import requests
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import os

def plotly_layout(title, height=350, xaxis_title="", yaxis_title=""):
    return {
        "title": {"text": f"<b>{title}</b>", "font": {"size": 15, "color": "#0f172a", "family": "Montserrat, sans-serif"}, "x": 0},
        "paper_bgcolor": "white",
        "plot_bgcolor": "#fafafa",
        "height": height,
        "margin": dict(l=50, r=20, t=60, b=50),
        "xaxis": {
            "title": xaxis_title,
            "gridcolor": "#f1f5f9",
            "showgrid": True,
            "linecolor": "#e2e8f0",
            "tickfont": {"size": 11, "color": "#64748b"},
            "titlefont": {"size": 12, "color": "#475569"},
        },
        "yaxis": {
            "title": yaxis_title,
            "gridcolor": "#f1f5f9",
            "showgrid": True,
            "linecolor": "#e2e8f0",
            "tickfont": {"size": 11, "color": "#64748b"},
            "titlefont": {"size": 12, "color": "#475569"},
        },
        "legend": {
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "right",
            "x": 1,
            "font": {"size": 11, "color": "#475569"},
            "bgcolor": "rgba(255,255,255,0.8)",
            "bordercolor": "#e2e8f0",
            "borderwidth": 1,
        },
        "font": {"family": "Montserrat, sans-serif", "color": "#0f172a"},
        "hoverlabel": {
            "bgcolor": "white",
            "bordercolor": "#e2e8f0",
            "font": {"size": 12, "color": "#0f172a"},
        },
    }

st.set_page_config(page_title="RiskLab USTA", page_icon="📊", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700&display=swap');
    
    html, body, [class*="css"] { font-family: 'Montserrat', sans-serif; }

    /* Ocultar marca Streamlit */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    /* Header principal — igual que antes */
    .main-header {
        background: linear-gradient(135deg, #1a56db 0%, #1e40af 100%);
        padding: 1.5rem 2rem; 
        border-radius: 12px; 
        margin-bottom: 1.5rem;
        box-shadow: 0 4px 20px rgba(26, 86, 219, 0.25);
    }
    .main-header h1 { margin: 0; font-size: 1.8rem; font-weight: 700; color: white; }
    .main-header p  { margin: 0.3rem 0 0; color: #e2e8f0; font-size: 0.9rem; }
    .main-header strong { color: white !important; }

    /* Tabs mejorados */
    .stTabs [data-baseweb="tab-list"] { 
        gap: 2px; 
        overflow-x: auto !important; 
        flex-wrap: nowrap !important;
        scrollbar-width: thin;
        background: #f1f5f9;
        padding: 3px;
        border-radius: 8px;
        border: 1px solid #e2e8f0;
    }
    .stTabs [data-baseweb="tab-list"]::-webkit-scrollbar { height: 4px; }
    .stTabs [data-baseweb="tab-list"]::-webkit-scrollbar-thumb {
        background: #cbd5e1;
        border-radius: 3px;
    }
    .stTabs [data-baseweb="tab"] { 
        border-radius: 6px; 
        padding: 6px 10px; 
        font-weight: 600; 
        font-size: 0.75rem;
        white-space: nowrap;
        color: #64748b;
    }
    .stTabs [aria-selected="true"] {
        background: white !important;
        color: #1d4ed8 !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.08) !important;
    }

    /* Métricas con card */
    [data-testid="stMetric"] {
        background: white !important;
        border: 1px solid #e2e8f0 !important;
        border-radius: 10px !important;
        padding: 1rem !important;
        box-shadow: 0 1px 4px rgba(0,0,0,0.05) !important;
    }
    [data-testid="stMetricLabel"] {
        font-size: 0.72rem !important;
        font-weight: 700 !important;
        color: #64748b !important;
        text-transform: uppercase !important;
        letter-spacing: 0.05em !important;
    }
    [data-testid="stMetricValue"] {
        font-size: 1.5rem !important;
        font-weight: 700 !important;
        color: #0f172a !important;
    }

    /* Botones azules */
    .stButton > button {
        background: linear-gradient(135deg, #1d4ed8, #2563eb) !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        font-size: 0.82rem !important;
        padding: 0.5rem 1.2rem !important;
        box-shadow: 0 2px 8px rgba(29, 78, 216, 0.3) !important;
        transition: all 0.2s !important;
    }
    .stButton > button:hover {
        transform: translateY(-1px) !important;
        box-shadow: 0 4px 12px rgba(29, 78, 216, 0.4) !important;
    }

    /* Expanders como cards */
    [data-testid="stExpander"] {
        background: white !important;
        border: 1px solid #e2e8f0 !important;
        border-radius: 10px !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05) !important;
    }

    /* Scrollbar */
    ::-webkit-scrollbar { width: 5px; height: 5px; }
    ::-webkit-scrollbar-track { background: #f8fafc; }
    ::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 3px; }

</style>
""", unsafe_allow_html=True)

API = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")

# ═══════════════════ HELPERS ═══════════════════

def api_error_detail(response):
    try:
        return response.json().get("detail", response.reason)
    except ValueError:
        return response.text.strip() or response.reason

def api_get(ep, params=None, timeout=120):
    try:
        r = requests.get(f"{API}{ep}", params=params, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        st.error("❌ Backend no disponible. Asegúrate de que corre en :8000")
        return None
    except requests.exceptions.HTTPError as e:
        st.error(f"❌ Error {e.response.status_code}: {api_error_detail(e.response)}")
        return None
    except requests.exceptions.JSONDecodeError:
        st.error("❌ El backend devolvió una respuesta inválida. Verifica que Render esté activo.")
        return None
    except Exception as e:
        st.error(f"❌ {e}")
        return None

def api_post(ep, body=None):
    try:
        r = requests.post(f"{API}{ep}", json=body or {}, timeout=120); r.raise_for_status(); return r.json()
    except requests.exceptions.ConnectionError:
        st.error("❌ Backend no disponible."); return None
    except requests.exceptions.HTTPError as e:
        st.error(f"❌ Error {e.response.status_code}: {api_error_detail(e.response)}"); return None
    except Exception as e:
        st.error(f"❌ {e}"); return None

@st.cache_data(ttl=300)
def cached_get(endpoint: str, params_str: str =""):
    """api_get cacheada - evita re--lamadas en cada re-render de Streamlit"""
    import json
    params=json.loads(params_str) if params_str else None
    return api_get(endpoint, params)

def descargar_si_no_existe(ticker):
    """Descarga precios si no existen en BD (maneja 404 silenciosamente)."""
    try:
        r = requests.get(f"{API}/precios/{ticker}", timeout=30)
        if r.status_code == 404 or (r.status_code == 200 and len(r.json()) == 0):
            api_post(f"/precios/descargar/{ticker}")
    except Exception:
        pass

# ═══════════════════ TICKERS DB ═══════════════════

TICKERS_DB = {
    "AAPL": "Apple (Tech)", "MSFT": "Microsoft (Tech)", "GOOGL": "Alphabet (Tech)",
    "AMZN": "Amazon (Tech)", "TSLA": "Tesla (Tech)", "NVDA": "NVIDIA (Tech)",
    "META": "Meta (Tech)", "NFLX": "Netflix (Tech)", "AMD": "AMD (Tech)",
    "JPM": "JPMorgan (Financiero)", "BAC": "Bank of America (Financiero)",
    "GS": "Goldman Sachs (Financiero)", "V": "Visa (Financiero)",
    "MA": "Mastercard (Financiero)",
    "JNJ": "Johnson & Johnson (Salud)", "PFE": "Pfizer (Salud)",
    "UNH": "UnitedHealth (Salud)", "MRK": "Merck (Salud)", "ABBV": "AbbVie (Salud)",
    "XOM": "ExxonMobil (Energía)", "CVX": "Chevron (Energía)", "COP": "ConocoPhillips (Energía)",
    "KO": "Coca-Cola (Consumo)", "PEP": "PepsiCo (Consumo)",
    "WMT": "Walmart (Consumo)", "MCD": "McDonald's (Consumo)",
    "NKE": "Nike (Consumo)", "SBUX": "Starbucks (Consumo)", "PG": "P&G (Consumo)",
    "F": "Ford (Automotriz)", "GM": "General Motors (Automotriz)",
    "TM": "Toyota (Automotriz)", "TSM": "TSMC (Tech)",
    "ASML": "ASML (Tech)", "SAP": "SAP (Tech)",
    "BABA": "Alibaba (Tech)", "TCEHY": "Tencent (Tech)",
    "BRK-B": "Berkshire (Financiero)", "HD": "Home Depot (Consumo)",
    "CRM": "Salesforce (Tech)", "ADBE": "Adobe (Tech)",
    "INTC": "Intel (Tech)", "QCOM": "Qualcomm (Tech)",
    "TXN": "Texas Instruments (Tech)", "PYPL": "PayPal (Financiero)",
    "SHOP": "Shopify (Tech)", "SPOT": "Spotify (Tech)",
    "ABNB": "Airbnb (Consumo)", "UBER": "Uber (Tech)",
    "005930.KS": "Samsung (Tech)",
}

TICKERS_DB.update({
    "ORCL": "Oracle (Tech)", "IBM": "IBM (Tech)", "NOW": "ServiceNow (Tech)",
    "SNOW": "Snowflake (Tech)", "NET": "Cloudflare (Tech)", "DDOG": "Datadog (Tech)",
    "AVGO": "Broadcom (Tech)", "MU": "Micron (Tech)", "LRCX": "Lam Research (Tech)",
    "AMAT": "Applied Materials (Tech)", "CSCO": "Cisco (Tech)", "PANW": "Palo Alto Networks (Cybersecurity)",
    "CRWD": "CrowdStrike (Cybersecurity)", "AXP": "American Express (Financiero)",
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
    "NEE": "NextEra Energy (Utilities)", "DUK": "Duke Energy (Utilities)", "SO": "Southern Company (Utilities)",
    "PLD": "Prologis (Real Estate)", "AMT": "American Tower (Real Estate)", "EQIX": "Equinix (Real Estate)",
    "GLD": "SPDR Gold Trust (ETF)", "IWM": "Russell 2000 ETF", "VTI": "Total Stock Market ETF",
    "EFA": "MSCI EAFE ETF", "EEM": "Emerging Markets ETF", "TLT": "20+ Year Treasury ETF",
    "HYG": "High Yield Bond ETF", "LQD": "Investment Grade Bond ETF", "XLF": "Financial Select ETF",
    "XLK": "Technology Select ETF", "XLV": "Health Care Select ETF", "XLE": "Energy Select ETF",
})

TICKER_PRESETS = {
    "Base USTA": ["AAPL", "JPM", "JNJ", "XOM", "KO"],
    "Databricks demo 15": ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "JPM", "V", "LLY", "NVO", "XOM", "COST", "CAT", "NEE", "GLD"],
    "Tecnología": ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "AMD", "AVGO", "ORCL", "CRM"],
    "Defensivo": ["JNJ", "KO", "PG", "WMT", "COST", "PEP", "MRK", "NEE", "DUK", "SO"],
    "Financiero": ["JPM", "BAC", "GS", "V", "MA", "AXP", "MS", "C", "BLK", "SCHW"],
    "Multi-sector 25": ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "JPM", "V", "MA", "JNJ", "LLY", "NVO", "XOM", "CVX", "KO", "PG", "COST", "WMT", "CAT", "DE", "NEE", "PLD", "GLD", "TLT", "XLK", "XLF"],
}

# ═══════════════════ SIDEBAR ═══════════════════

with st.sidebar:
    st.markdown("## ⚙️ Configuración")
    st.markdown("---")

        # Inicializar session_state para tickers
    if "tickers_seleccionados" not in st.session_state:
        st.session_state["tickers_seleccionados"] = ["AAPL", "JPM", "JNJ", "XOM", "KO"]

    # Añadir nuevos tickers del buscador al TICKERS_DB
    for t in st.session_state.get("tickers_extra", []):
        if t not in st.session_state["tickers_seleccionados"]:
            st.session_state["tickers_seleccionados"].append(t)
        if t not in TICKERS_DB:
            TICKERS_DB[t] = f"{t} (Personalizado)"

    with st.expander("⚡ Portafolios rápidos", expanded=False):
        st.caption("Útiles para cargar más activos y aprovechar mejor Databricks.")
        for nombre_preset, lista_preset in TICKER_PRESETS.items():
            if st.button(nombre_preset, key=f"preset_{nombre_preset}", use_container_width=True):
                st.session_state["tickers_seleccionados"] = lista_preset
                st.rerun()

    tickers = st.multiselect(
        "📦 Tickers del portafolio",
        options=sorted(TICKERS_DB.keys()),
        default=[t for t in st.session_state["tickers_seleccionados"] if t in TICKERS_DB],
        format_func=lambda t: f"{t} — {TICKERS_DB[t]}",
        help="Puedes buscar por ticker dentro del selector o usar el buscador por nombre.",
    )

    # Sincronizar
    st.session_state["tickers_seleccionados"] = tickers
    # ── Diccionario de búsqueda por nombre de empresa ──
    EMPRESAS_BUSQUEDA = {
        "Apple Inc.": "AAPL",
        "Microsoft Corporation": "MSFT",
        "NVIDIA Corporation": "NVDA",
        "Alphabet Inc. (Google)": "GOOGL",
        "Amazon.com Inc.": "AMZN",
        "Tesla Inc.": "TSLA",
        "Meta Platforms Inc.": "META",
        "Netflix Inc.": "NFLX",
        "AMD — Advanced Micro Devices": "AMD",
        "JPMorgan Chase & Co.": "JPM",
        "Bank of America": "BAC",
        "Goldman Sachs Group": "GS",
        "Visa Inc.": "V",
        "Mastercard Inc.": "MA",
        "Johnson & Johnson": "JNJ",
        "Pfizer Inc.": "PFE",
        "UnitedHealth Group": "UNH",
        "Merck & Co.": "MRK",
        "AbbVie Inc.": "ABBV",
        "ExxonMobil Corporation": "XOM",
        "Chevron Corporation": "CVX",
        "ConocoPhillips": "COP",
        "Coca-Cola Company": "KO",
        "PepsiCo Inc.": "PEP",
        "Walmart Inc.": "WMT",
        "McDonald's Corporation": "MCD",
        "Nike Inc.": "NKE",
        "Starbucks Corporation": "SBUX",
        "Ford Motor Company": "F",
        "General Motors": "GM",
        "Toyota Motor Corporation": "TM",
        "Samsung Electronics": "005930.KS",
        "Taiwan Semiconductor (TSMC)": "TSM",
        "ASML Holding": "ASML",
        "SAP SE": "SAP",
        "Alibaba Group": "BABA",
        "Tencent Holdings": "TCEHY",
        "Berkshire Hathaway": "BRK-B",
        "Procter & Gamble": "PG",
        "Home Depot": "HD",
        "Salesforce Inc.": "CRM",
        "Adobe Inc.": "ADBE",
        "Intel Corporation": "INTC",
        "Qualcomm Inc.": "QCOM",
        "Texas Instruments": "TXN",
        "PayPal Holdings": "PYPL",
        "Shopify Inc.": "SHOP",
        "Spotify Technology": "SPOT",
        "Airbnb Inc.": "ABNB",
        "Uber Technologies": "UBER",
    }

    st.markdown("**🔍 Buscar empresa**")
    BUSCADOR_EMPRESAS = {
        **{f"{ticker} — {nombre}": ticker for ticker, nombre in TICKERS_DB.items()},
        **{f"{ticker} — {nombre}": ticker for nombre, ticker in EMPRESAS_BUSQUEDA.items()},
    }
    texto_busqueda = st.text_input(
        "Escribe nombre o ticker",
        placeholder="Ej: Nvidia, NVDA, bancos, energía...",
        key="texto_busqueda_empresa",
        help="Filtra por ticker, nombre o sector."
    )
    opciones_filtradas = [
        etiqueta for etiqueta in sorted(BUSCADOR_EMPRESAS)
        if not texto_busqueda.strip()
        or texto_busqueda.lower() in etiqueta.lower()
        or texto_busqueda.lower() in TICKERS_DB.get(BUSCADOR_EMPRESAS[etiqueta], "").lower()
    ][:60]
    empresa_busqueda = st.selectbox(
        "Resultados",
        options=["— Buscar empresa —"] + opciones_filtradas,
        key="buscador_empresa",
    )

    if empresa_busqueda != "— Buscar empresa —":
        ticker_encontrado = BUSCADOR_EMPRESAS[empresa_busqueda]
        col1, col2 = st.columns([2, 1])
        with col1:
            st.success(f"**{ticker_encontrado}** — {TICKERS_DB.get(ticker_encontrado, empresa_busqueda)}")
        with col2:
            if st.button("➕ Añadir", key="btn_add_empresa"):
                if ticker_encontrado not in st.session_state["tickers_seleccionados"]:
                    if ticker_encontrado not in TICKERS_DB:
                        TICKERS_DB[ticker_encontrado] = f"{ticker_encontrado} (Personalizado)"
                    st.session_state["tickers_seleccionados"].append(ticker_encontrado)
                    if "tickers_extra" not in st.session_state:
                        st.session_state["tickers_extra"] = []
                    st.session_state["tickers_extra"].append(ticker_encontrado)
                    st.rerun()
                else:
                    st.warning("Ya está en el portafolio")

    # Campo manual para tickers no en el diccionario
    with st.expander("✏️ Ingresar ticker manualmente"):
        ticker_custom = st.text_input(
            "Ticker exacto",
            placeholder="Ej: TSM, BABA",
            help="Para empresas no encontradas en el buscador"
        )
        if ticker_custom.strip():
            extras = [t.strip().upper() for t in ticker_custom.split(",") if t.strip()]
            tickers = tickers + [t for t in extras if t not in tickers]

    if len(tickers) < 2:
        st.warning("⚠️ Selecciona al menos 2 activos.")


    benchmark = st.selectbox("📊 Benchmark",
        ["^GSPC", "^DJI", "^IXIC", "^RUT", "QQQ", "SPY"],
        format_func=lambda x: {"^GSPC": "S&P 500", "^DJI": "Dow Jones", "^IXIC": "NASDAQ",
                                "^RUT": "Russell 2000", "QQQ": "NASDAQ-100 ETF", "SPY": "S&P 500 ETF"}.get(x, x))

    st.markdown("---")
    st.markdown("**📐 Parámetros de Riesgo**")

    confianza_var = st.slider("Nivel de confianza VaR", 0.90, 0.99, 0.95, 0.01, format="%.2f")

    valor_portafolio = st.number_input("💰 Valor del portafolio (USD)",
        min_value=1.0, max_value=10_000_000.0, value=100_000.0, step=1_000.0)

    st.markdown("---")
    st.markdown("**⚖️ Pesos del portafolio**")
    peso_igual = st.checkbox("Pesos iguales", value=True)
    if tickers:
        if peso_igual:
            pesos = {t: round(1/len(tickers), 4) for t in tickers}
            st.caption(f"Cada activo: {list(pesos.values())[0]*100:.1f}%")
        else:
            pesos = {}
            for t in tickers:
                pesos[t] = st.number_input(f"Peso {t}", 0.0, 1.0, round(1/len(tickers), 2), 0.05, key=f"w_{t}")
            if abs(sum(pesos.values()) - 1.0) > 0.01:
                st.warning(f"⚠️ Pesos suman {sum(pesos.values()):.2f}")

    st.markdown("---")
    st.markdown("**📅 Período de Análisis**")
    fecha_inicio = st.date_input(
        "Fecha inicio",
        value=(pd.to_datetime("today")- pd.DateOffset(years=3)).date(),
        max_value=pd.to_datetime("today"),
        key="fecha_inicio_global"
    )
    fecha_fin = st.date_input(
        "Fecha fin",
        value=pd.to_datetime("today"),
        min_value=fecha_inicio,
        key="fecha_fin_global"
    )
    if fecha_inicio >= fecha_fin:
        st.warning("⚠️ Fecha inicio debe ser menor que fecha fin.")
    
    fecha_minima = (pd.to_datetime("today") - pd.DateOffset(years=3)).date()
    if fecha_inicio < fecha_minima:
        st.warning(f"⚠️ Datos disponibles desde **{fecha_minima.strftime('%Y/%m/%d')}**. Ajusta la fecha inicio.")
    else:
        st.caption(f"📊 {(fecha_fin - fecha_inicio).days} días seleccionados")

    fi = str(fecha_inicio)
    ff = str(fecha_fin)

    st.markdown("---")
    st.caption("**RiskLab USTA** · Teoría del Riesgo + Python APIs · CIII")


# Limpiar cache cuando cambian las fechas o tickers
_config_key = f"config_{'-'.join(tickers)}_{benchmark}_{fi}_{ff}"
if st.session_state.get("_last_config") != _config_key:
    # Limpiar todos los caches de análisis
    keys_to_clear = [k for k in st.session_state.keys() 
                     if any(k.startswith(p) for p in [
                         "rend_", "vol_", "capm_", "var_", "markowitz_",
                         "macro_", "stress_", "tab1_", "init_"
                     ])]
    for k in keys_to_clear:
        del st.session_state[k]
    st.session_state["_last_config"] = _config_key

# ═══════════════════ HEADER ═══════════════════

st.markdown(f"""
<div class="main-header">
    <h1>📊 RiskLab USTA — Análisis de Riesgo Financiero</h1>
    <p>Portafolio: <strong>{' · '.join(tickers)}</strong> &nbsp;|&nbsp;
       Benchmark: <strong>{benchmark}</strong> &nbsp;|&nbsp;
       VaR: <strong>{confianza_var:.0%}</strong> &nbsp;|&nbsp;
       Inversión: <strong>${valor_portafolio:,.0f}</strong></p>
</div>
""", unsafe_allow_html=True)


# --- CARGA GLOBAL DE TASA (TU FRED API) ---
tasa_fred = 0.045 # Respaldo
try:
    curva_data = api_get("/renta-fija/curva")
    if curva_data and "datos_mercado" in curva_data:
        # Convertimos a lista para evitar el error de dict_values
        tasa_fred = list(curva_data["datos_mercado"]["tasas"])[0] / 100
        # Mostramos en el sidebar que la conexión fue exitosa
        st.sidebar.success(f"🔌 FRED Online: {tasa_fred*100:.2f}%")
except Exception as e:
    st.sidebar.error("⚠️ FRED Offline (Usando base 4.5%)")


# ═══════════════════ TABS ═══════════════════


tabs = st.tabs([
"🎯 Contexto", "📈 1. Técnico", "📉 2. Rendimientos", "🌊 3. Volatilidad",
"🎯 4. CAPM", "🛡️ 5. VaR/CVaR", "⚡ 6. Markowitz",
"🚦 7. Señales", "🌐 8. Macro", "📐 9. Renta Fija",
"🧮 10. Opciones", "💥 11. Stress", "🤖 ML", "🧩 Arquitectura Técnica", "🧠 Agente IA",
])


# ═══════════════════ CONTEXTO ═══════════════════

with tabs[0]:
    st.subheader("🎯 Contexto y Objetivos del Análisis")
    col1, col2 = st.columns([3, 2])
    with col1:
        st.markdown("""
        ### Objetivo
        **RiskLab USTA** es un sistema integral de análisis de riesgo financiero
        que integra:
        - **Backend:** FastAPI + SQLAlchemy + SQLite (persistencia y cache)
        - **Cloud SQL:** Databricks SQL Warehouse con tabla `risklab_prices`
        - **Análisis:** Indicadores técnicos, VaR, CAPM, Markowitz, GARCH, EWMA
        - **Nuevos módulos:** Renta fija, Opciones, Stress Testing, ML y consultas cloud
        - **Infraestructura:** Docker, GitHub Actions CI, deploy en Render
        
        ### Arquitectura
        ```
        Streamlit (8501) ──HTTP/JSON──► FastAPI (8000) ──► yfinance / FRED
                                          │
                                   SQLAlchemy + SQLite (cache)
                                          │
                                   Databricks SQL Warehouse
                                   risklab_prices (capa cloud)
                                   Pydantic v2 (validación)
                                   9 servicios de cálculo
        ```

        ### Databricks en el proyecto
        Databricks no reemplaza SQLite: lo complementa como capa cloud para
        consultar datos financieros con SQL sobre `risklab_prices`.
        """)
    with col2:
        st.markdown("### Activos Seleccionados")
        for t in tickers:
            nombre = TICKERS_DB.get(t, t)
            st.write(f"**{t}** — {nombre}")
        st.info(f"Benchmark: **{benchmark}** | Inversión: **${valor_portafolio:,.0f}**")
    st.divider()
    st.markdown("### 🚀 Inicializar Portafolio")
    
    cache_key_init = f"init_{'_'.join(tickers)}_{benchmark}"
    if cache_key_init in st.session_state:
        st.success(f"✅ Portafolio inicializado — {len(tickers)} activos listos para análisis.")
    else:
        st.info("Descarga los datos del portafolio para habilitar todos los módulos.")
        if st.button("🚀 Inicializar Portafolio", key="btn_init", type="primary"):
            from concurrent.futures import ThreadPoolExecutor
            todos = tickers + [benchmark]
            progreso = st.progress(0, text="Iniciando descarga...")
            for i, t in enumerate(todos):
                progreso.progress((i+1)/len(todos), text=f"Descargando {t}...")
                descargar_si_no_existe(t)
            progreso.empty()
            st.session_state[cache_key_init] = True
            st.session_state[f"tab1_descargado_{'_'.join(tickers)}"] = True
            st.success(f"✅ Portafolio inicializado — {len(tickers)} activos listos.")
            st.rerun()


# ═══════════════════ MÓD 1 — TÉCNICO ═══════════════════

with tabs[1]:
    st.subheader("📈 Análisis Técnico e Indicadores")

    # Descarga inicial
    if f"tab1_descargado_{'_'.join(tickers)}" not in st.session_state:
        with st.spinner("Descargando precios de todos los activos en paralelo..."):
            from concurrent.futures import ThreadPoolExecutor
            todos = tickers + [benchmark]
            with ThreadPoolExecutor(max_workers=6) as executor:
                executor.map(descargar_si_no_existe, todos)
        st.session_state[f"tab1_descargado_{'_'.join(tickers)}"] = True

    # Gráfico comparativo base 100
    st.markdown("### 📊 Rendimiento Comparado — Base 100")
    fig_comp = go.Figure()
    for t in tickers:
        r_p = cached_get(f"/precios/{t}")
        if r_p and len(r_p) > 0:
            df_t = pd.DataFrame(r_p)
            df_t["fecha"] = pd.to_datetime(df_t["fecha"])
            df_t = df_t[(df_t["fecha"] >= pd.to_datetime(fi)) & (df_t["fecha"] <= pd.to_datetime(ff))]
            if len(df_t) == 0:
                continue
            df_t["norm"] = df_t["close"] / df_t["close"].iloc[0] * 100
            fig_comp.add_trace(go.Scatter(x=df_t["fecha"], y=df_t["norm"], name=t))
    fig_comp.update_layout(height=400,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        yaxis_title="Valor (base 100)")
    st.plotly_chart(fig_comp, use_container_width=True)

    st.divider()
    st.markdown("### 🕯️ Análisis Individual por Activo")

    for idx, t in enumerate(tickers):
        data_ind = api_get(f"/analisis/indicadores/{t}", params={"fecha_inicio": fi, "fecha_fin": ff})
        r_precios = cached_get(f"/precios/{t}")

        with st.expander(f"📈 {t} — Velas e Indicadores Técnicos", expanded=(idx == 0)):
            if r_precios and len(r_precios) > 0:
                df_p = pd.DataFrame(r_precios)
                df_p["fecha"] = pd.to_datetime(df_p["fecha"])
                fig_velas = go.Figure(data=go.Candlestick(
                    x=df_p["fecha"], open=df_p["open"], high=df_p["high"],
                    low=df_p["low"], close=df_p["close"]))
                fig_velas.update_layout(
                    title=f"Velas Japonesas — {t}",
                    xaxis_rangeslider_visible=False, height=350)
                st.plotly_chart(fig_velas, use_container_width=True)

            if data_ind:
                df = pd.DataFrame(data_ind["indicadores"]).T
                df.index = pd.to_datetime(df.index)

                fig = go.Figure()
                fig.add_trace(go.Scatter(x=df.index, y=df["close"], name="Precio", line=dict(width=2)))
                fig.add_trace(go.Scatter(x=df.index, y=df["sma_short"], name="SMA 20", line=dict(dash="dot")))
                fig.add_trace(go.Scatter(x=df.index, y=df["sma_long"], name="SMA 50", line=dict(dash="dash")))
                fig.add_trace(go.Scatter(x=df.index, y=df["bollinger_upper"], name="BB Sup",
                    line=dict(color="rgba(100,100,200,0.5)")))
                fig.add_trace(go.Scatter(x=df.index, y=df["bollinger_lower"], name="BB Inf",
                    line=dict(color="rgba(100,100,200,0.5)"),
                    fill="tonexty", fillcolor="rgba(100,100,200,0.07)"))
                fig.update_layout(title=f"Indicadores — {t}", height=380,
                    legend=dict(orientation="h", yanchor="bottom", y=1.02))
                st.plotly_chart(fig, use_container_width=True)

                col1, col2 = st.columns(2)
                with col1:
                    fig_rsi = go.Figure()
                    fig_rsi.add_trace(go.Scatter(x=df.index, y=df["rsi"],
                        name="RSI", line=dict(color="#6366F1", width=2)))
                    fig_rsi.add_hline(y=70, line_dash="dash", line_color="red", annotation_text="Sobrecompra")
                    fig_rsi.add_hline(y=30, line_dash="dash", line_color="green", annotation_text="Sobreventa")
                    fig_rsi.update_layout(title="RSI (14)", height=250, yaxis=dict(range=[0, 100]))
                    st.plotly_chart(fig_rsi, use_container_width=True)

                with col2:
                    fig_macd = go.Figure()
                    fig_macd.add_trace(go.Scatter(x=df.index, y=df["macd"], name="MACD"))
                    fig_macd.add_trace(go.Scatter(x=df.index, y=df["macd_signal"], name="Señal"))
                    colors = ["green" if v >= 0 else "red" for v in df["macd_histograma"].fillna(0)]
                    fig_macd.add_trace(go.Bar(x=df.index, y=df["macd_histograma"],
                        marker_color=colors, opacity=0.6, name="Hist"))
                    fig_macd.update_layout(title="MACD", height=250)
                    st.plotly_chart(fig_macd, use_container_width=True)

                fig_stoch = go.Figure()
                fig_stoch.add_trace(go.Scatter(x=df.index, y=df["stochastic_k"], name="%K"))
                fig_stoch.add_trace(go.Scatter(x=df.index, y=df["stochastic_d"], name="%D"))
                fig_stoch.add_hline(y=80, line_dash="dash", line_color="red")
                fig_stoch.add_hline(y=20, line_dash="dash", line_color="green")
                fig_stoch.update_layout(title=f"Estocástico — {t}", height=250,
                    yaxis=dict(range=[0, 100]))
                st.plotly_chart(fig_stoch, use_container_width=True)

    with st.expander("ℹ️ Interpretación de indicadores"):
            st.markdown("""
            | Indicador | Señal alcista | Señal bajista |
            |---|---|---|
            | **SMA/EMA** | Precio > media | Precio < media |
            | **Bollinger** | Toca banda inferior | Toca banda superior |
            | **RSI** | < 30 (sobreventa) | > 70 (sobrecompra) |
            | **MACD** | Cruza señal ↑ | Cruza señal ↓ |
            | **Estocástico** | %K cruza %D ↑ en <20 | %K cruza %D ↓ en >80 |
            """)


# ═══════════════════ MÓD 2 — RENDIMIENTOS ═══════════════════

with tabs[2]:
    st.subheader("📉 Rendimientos y Propiedades Empíricas")

    # Boxplot comparativo arriba — todos los activos de una vez
    st.markdown("### 📊 Comparativa de Volatilidad — Todos los Activos")
    fig_box = go.Figure()
    for t in tickers:
        serie_box = st.session_state.get(f"rend_{t}_{fi}_{ff}", {}).get("serie")
        if not serie_box:
            serie_box = api_get(f"/analisis/rendimientos-serie/{t}")
        if serie_box:
            r_log = pd.Series([x["rendimiento"] for x in serie_box["serie"]]) * 100
            fig_box.add_trace(go.Box(y=r_log, name=t, boxpoints="outliers", marker_size=2))
    try:
        fig_box.update_layout(**plotly_layout("Distribución de Rendimientos por Activo (%)", height=350))
    except:
        fig_box.update_layout(title="Boxplot", height=350)
    st.plotly_chart(fig_box, use_container_width=True)

    st.divider()

    # Precarga todos los tickers
    for _t in tickers:
        _key = f"rend_{_t}_{fi}_{ff}"
        if _key not in st.session_state:
            _data = {
                "stats": api_get(f"/analisis/rendimientos/{_t}", params={"fecha_inicio": fi, "fecha_fin": ff}),
                "serie": api_get(f"/analisis/rendimientos-serie/{_t}", params={"fecha_inicio": fi, "fecha_fin": ff}),
            }
            if _data["stats"] and _data["serie"]:
                st.session_state[_key] = _data
    
    # Acordeón por ticker
    st.markdown("### 📈 Análisis Individual por Activo")
    from scipy import stats as sp_stats

    for idx, t in enumerate(tickers):
        datos = st.session_state.get(f"rend_{t}_{fi}_{ff}")
        if not datos:
            continue

        data_stats = datos["stats"]
        data_serie = datos["serie"]

        with st.expander(f"📉 {t} — Propiedades Empíricas", expanded=(idx == 0)):
            df_r = pd.DataFrame(data_serie["serie"])
            df_r["fecha"] = pd.to_datetime(df_r["fecha"])
            df_r.set_index("fecha", inplace=True)
            rend_vals = df_r["rendimiento"] * 100

            # Métricas
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("Media Diaria", f"{data_stats['media_diaria']*100:.4f}%")
            c2.metric("Volatilidad Diaria", f"{data_stats['std_diaria']*100:.4f}%")
            c3.metric("Asimetría", f"{data_stats['asimetria']:.3f}")
            c4.metric("Curtosis", f"{data_stats['curtosis']:.3f}")
            p5_val = rend_vals.quantile(0.05)
            c5.metric("Peor día (5%)", f"{p5_val:.2f}%")

            st.markdown("---")

            col_a, col_b = st.columns(2)
            with col_a:
                fig_rend = go.Figure()
                fig_rend.add_trace(go.Scatter(
                    x=df_r.index, y=df_r["rendimiento"]*100,
                    name="Rend. log diario",
                    line=dict(color="#2563eb", width=0.8),
                    fill="tozeroy", fillcolor="rgba(37,99,235,0.08)",
                ))
                try:
                    fig_rend.update_layout(**plotly_layout(f"Serie log diaria — {t}", height=280))
                except:
                    fig_rend.update_layout(title=f"Rendimientos {t}", height=280)
                st.plotly_chart(fig_rend, use_container_width=True)

            with col_b:
                mu, sigma = rend_vals.mean(), rend_vals.std()
                x_norm = np.linspace(rend_vals.min(), rend_vals.max(), 200)
                y_norm = (1/(sigma*np.sqrt(2*np.pi))) * np.exp(-0.5*((x_norm-mu)/sigma)**2)
                fig_hist = go.Figure()
                fig_hist.add_trace(go.Histogram(
                    x=rend_vals, nbinsx=60, name="Distribución Real",
                    histnorm="probability density",
                    marker_color="#f43f5e", opacity=0.6,
                ))
                fig_hist.add_trace(go.Scatter(
                    x=x_norm, y=y_norm, name="Normal Teórica",
                    line=dict(color="#3b82f6", width=2),
                ))
                try:
                    fig_hist.update_layout(**plotly_layout("Histograma vs Normal", height=280))
                except:
                    fig_hist.update_layout(title="Histograma", height=280)
                st.plotly_chart(fig_hist, use_container_width=True)

            col_c, col_d = st.columns(2)
            with col_c:
                rend_sorted = np.sort(df_r["rendimiento"].dropna())
                cuantiles_teo = sp_stats.norm.ppf(
                    np.linspace(0.01, 0.99, len(rend_sorted)),
                    loc=df_r["rendimiento"].mean(), scale=df_r["rendimiento"].std()
                )
                fig_qq = go.Figure()
                fig_qq.add_trace(go.Scatter(
                    x=cuantiles_teo, y=rend_sorted, mode="markers",
                    name="Datos", marker=dict(color="#2563eb", size=3, opacity=0.7),
                ))
                fig_qq.add_trace(go.Scatter(
                    x=[min(cuantiles_teo), max(cuantiles_teo)],
                    y=[min(cuantiles_teo), max(cuantiles_teo)],
                    name="Línea 45°", line=dict(color="#ef4444", dash="dash"),
                ))
                try:
                    fig_qq.update_layout(**plotly_layout("Q-Q Plot", height=280,
                        xaxis_title="Cuantiles Teóricos", yaxis_title="Observados"))
                except:
                    fig_qq.update_layout(title="Q-Q Plot", height=280)
                st.plotly_chart(fig_qq, use_container_width=True)

            with col_d:
                jb = data_stats["jarque_bera"]
                sw = data_stats["shapiro_wilk"]
                st.markdown("#### ⚖️ Pruebas de Normalidad")
                n1, n2, n3 = st.columns(3)
                n1.metric("Jarque-Bera p", f"{jb['p_value']:.5f}",
                    delta="Normal ✅" if jb["es_normal"] else "No normal ⚠️",
                    delta_color="normal" if jb["es_normal"] else "inverse")
                n2.metric("Shapiro-Wilk p", f"{sw['p_value']:.5f}",
                    delta="Normal ✅" if sw["es_normal"] else "No normal ⚠️",
                    delta_color="normal" if sw["es_normal"] else "inverse")
                n3.metric("Conclusión",
                    "✅ Normal" if jb["es_normal"] and sw["es_normal"] else "⚠️ Colas Pesadas")

                st.markdown(f"""
                **Propiedades empíricas de {t}:**
                - Curtosis **{data_stats['curtosis']:.2f}** → {"leptocúrtica (colas pesadas)" if data_stats['curtosis'] > 3 else "mesocúrtica (normal)"}
                - Asimetría **{data_stats['asimetria']:.2f}** → {"sesgada negativamente (más caídas extremas)" if data_stats['asimetria'] < 0 else "sesgada positivamente"}
                - Esto justifica usar **VaR Histórico** y **GARCH** en vez de métodos paramétricos normales.
                """)

# ═══════════════════ MÓD 3 — VOLATILIDAD ═══════════════════

with tabs[3]:
    st.subheader("🌊 Volatilidad Condicional — EWMA & ARCH/GARCH")
    st.info(
        "Los modelos condicionales capturan el **agrupamiento de volatilidad (Volatility Clustering)**: "
        "períodos agitados tienden a seguir a períodos agitados, y períodos de calma siguen a períodos de calma. "
        "La volatilidad no es constante, depende de la memoria del mercado.",
        icon="💡",
    )

    # Carga automática para todos los tickers
    cache_key_m3_all = f"vol_all_{'_'.join(tickers)}_{fi}_{ff}"
    if cache_key_m3_all not in st.session_state:
        with st.spinner("Calculando modelos EWMA y GARCH para todos los activos..."):
            resultados_vol = {}
            for t in tickers:
                safe_t = urllib.parse.quote(t, safe='')
                resultados_vol[t] = {
                    "ewma":    api_get(f"/analisis/ewma/{safe_t}", params={"fecha_inicio": fi, "fecha_fin": ff}),
                    "garch":   api_get(f"/analisis/garch/{safe_t}", params={"fecha_inicio": fi, "fecha_fin": ff}),
                    "precios": cached_get(f"/precios/{safe_t}"),
                }
            st.session_state[cache_key_m3_all] = resultados_vol

    resultados_vol = st.session_state.get(cache_key_m3_all, {})

    if not resultados_vol:
        st.info("⏳ Ve primero al **Tab 1** para cargar los datos.")
    else:
        for t, datos in resultados_vol.items():
            ewma_data   = datos.get("ewma")
            garch_data  = datos.get("garch")
            precios_data = datos.get("precios")

            if not (ewma_data and garch_data and precios_data):
                continue

            with st.expander(f"📊 {t} — Volatilidad Condicional", expanded=(t == tickers[0])):
                df_p = pd.DataFrame(precios_data)
                df_p["fecha"] = pd.to_datetime(df_p["fecha"])
                df_p.set_index("fecha", inplace=True)
                df_p["rendimiento_log"] = np.log(df_p["close"] / df_p["close"].shift(1))
                df_p = df_p.dropna()
                df_p["vol_movil"] = df_p["rendimiento_log"].rolling(21).std() * np.sqrt(252) * 100

                fig_vol = go.Figure()
                fig_vol.add_trace(go.Scatter(
                    x=df_p.index, y=df_p["rendimiento_log"].abs() * 100,
                    name="|Rendimiento| diario",
                    line=dict(color="#1d4ed8", width=1.2),
                ))
                fig_vol.add_trace(go.Scatter(
                    x=df_p.index, y=df_p["vol_movil"],
                    name="Volatilidad móvil 21 días (Anual)",
                    line=dict(color="#ED1E79", width=2),
                ))
                try:
                    fig_vol.update_layout(**plotly_layout(f"Volatility Clustering — {t}", height=320, yaxis_title="Magnitud (%)"))
                except:
                    fig_vol.update_layout(title=f"Volatilidad {t}", height=320)
                st.plotly_chart(fig_vol, use_container_width=True)

                col_ewma, col_garch = st.columns(2)
                with col_ewma:
                    st.markdown("##### 📉 EWMA (RiskMetrics)")
                    vol_ewma = ewma_data.get('volatilidad_ewma', 0)
                    st.metric("Volatilidad EWMA Anualizada", f"{vol_ewma * 100:.2f}%" if vol_ewma < 1 else f"{vol_ewma:.2f}%")
                    st.info("λ = 0.94 — mayor peso a choques recientes.")

                with col_garch:
                    st.markdown("##### 🌊 Criterios de Información — Selección de Modelo")
                    modelo_optimo = garch_data.get("mejor_modelo", garch_data.get("orden", "N/A"))
                    persistencia = garch_data.get("persistencia", 0)

                    if "tabla_comparativa" in garch_data:
                        df_tabla = pd.DataFrame(garch_data["tabla_comparativa"])
                        df_tabla = df_tabla.sort_values("aic").reset_index(drop=True)
                        df_tabla.columns = ["Modelo", "AIC", "BIC", "Log-Lik"]

                        # Agregar estrella al mejor modelo
                        df_tabla["Modelo"] = df_tabla["Modelo"].apply(
                            lambda m: f"⭐ {m} ← ÓPTIMO" if m == modelo_optimo else m
                        )
                        st.dataframe(df_tabla.set_index("Modelo"), use_container_width=True)

                        st.markdown(f"""
                        **¿Por qué {modelo_optimo}?**
                        El modelo con **menor AIC** ({garch_data.get('aic', 0):.2f}) y **menor BIC** ({garch_data.get('bic', 0):.2f}) 
                        ofrece el mejor balance entre ajuste y parsimonia. 
                        Un AIC más bajo indica mejor capacidad predictiva penalizando la complejidad del modelo.
                        """)

                    c1, c2, c3 = st.columns(3)
                    c1.metric("AIC Óptimo", round(garch_data.get("aic", 0), 2))
                    c2.metric("BIC Óptimo", round(garch_data.get("bic", 0), 2))
                    c3.metric("Persistencia (α+β)", f"{persistencia:.4f}")

                    if persistencia > 0.98:
                        st.error("Persistencia extrema (>0.98): shocks casi permanentes.")
                    elif persistencia > 0.90:
                        st.warning("Persistencia alta (>0.90): mercado tardará en calmarse.")
                    else:
                        st.success("Persistencia moderada: volatilidad revierte a la media.")


# ═══════════════════ MÓD 4 — CAPM ═══════════════════

with tabs[4]:
        st.subheader("🎯 CAPM — Capital Asset Pricing Model")
        st.info("El CAPM determina el rendimiento esperado de un activo basado en su riesgo sistemático (Beta) frente al mercado.")

        cache_key_m4 = f"capm_{'-'.join(tickers)}_{benchmark}_{fi}_{ff}"
        if cache_key_m4 not in st.session_state:
            with st.spinner("Consultando FRED y calculando CAPM..."):
                descargar_si_no_existe(benchmark)
                rf_real = 0.04
                try:
                    curva = api_get("/renta-fija/curva")
                    if curva and "datos_mercado" in curva and "tasas" in curva["datos_mercado"]:
                        rf_real = curva["datos_mercado"]["tasas"][0] / 100
                except:
                    pass
                resultado = api_get("/analisis/capm", params={
                    "tickers": tickers,
                    "benchmark": benchmark,
                    "tasa_libre_riesgo": rf_real,
                    "fecha_inicio": fi,
                    "fecha_fin": ff,
                })
                if resultado:
                    st.session_state[cache_key_m4] = resultado
        data_capm = st.session_state.get(cache_key_m4)
        if not data_capm:
            st.info("⏳ Ve primero al **Tab 1 — Técnico** para cargar los datos del portafolio.")
        elif data_capm and "activos" in data_capm:

            rf_val = data_capm['activos'][0]['tasa_libre_riesgo_anual']
            st.success(f"✅ Tasa Libre de Riesgo (FRED): **{rf_val * 100:.2f}%** | Benchmark: **{data_capm['benchmark']}**")

            df_capm = pd.DataFrame(data_capm["activos"])

            # ── Métricas visuales por activo ──
            cols = st.columns(len(df_capm))
            for i, (_, row) in enumerate(df_capm.iterrows()):
                color = "🔴" if row["clasificacion"] == "Agresivo" else "🟢" if row["clasificacion"] == "Defensivo" else "🟡"
                cols[i].metric(
                    f"{color} {row['ticker']}", f"β = {row['beta']:.3f}",
                    delta=row["clasificacion"], delta_color="off"
                )

            st.divider()

            # ── Tabla resumen detallada ──
            df_display = df_capm[[
                "ticker", "beta", "clasificacion", "rendimiento_esperado_capm", 
                "prima_riesgo", "alpha_jensen", "r_cuadrado"
            ]].copy()
            
            df_display["rendimiento_esperado_capm"] *= 100
            df_display["prima_riesgo"] *= 100
            df_display["alpha_jensen"] *= 100
            
            df_display.columns = ["Ticker", "Beta (β)", "Clasificación", "E(R) CAPM %", "Prima Riesgo %", "α Jensen %", "R² (Sistemático)"]
            
            st.dataframe(
                df_display.set_index("Ticker").style.format({
                    "Beta (β)": "{:.4f}", "E(R) CAPM %": "{:.2f}%", 
                    "Prima Riesgo %": "{:.2f}%", "α Jensen %": "{:.2f}%", "R² (Sistemático)": "{:.4f}"
                }), 
                use_container_width=True
            )

            # ── Gráficos (Libres de la variable COLORS) ──
            col_g1, col_g2 = st.columns(2)

            with col_g1:
                fig_beta = go.Figure()
                # Usamos códigos Hexadecimales puros para evitar el NameError
                bar_colors = ["#ef4444" if b > 1.2 else "#10b981" if b < 0.8 else "#f59e0b" for b in df_capm["beta"]]
                
                fig_beta.add_trace(go.Bar(
                    x=df_capm["ticker"], y=df_capm["beta"],
                    marker_color=bar_colors, text=df_capm["beta"].round(3), textposition="auto"
                ))
                fig_beta.add_hline(y=1.0, line_dash="dash", line_color="#94a3b8", annotation_text="Mercado (β=1)")
                
                try: fig_beta.update_layout(**plotly_layout("Beta por activo", height=400))
                except: fig_beta.update_layout(title="Beta por activo", height=400, template="plotly_dark")
                st.plotly_chart(fig_beta, use_container_width=True)

            with col_g2:
                rf = df_capm.iloc[0]["tasa_libre_riesgo_anual"]
                rm = df_capm.iloc[0]["rendimiento_mercado_anual"]
                betas_sml = np.linspace(0, max(2.0, df_capm["beta"].max() * 1.2), 100)
                rend_sml = (rf + betas_sml * (rm - rf)) * 100

                fig_sml = go.Figure()
                fig_sml.add_trace(go.Scatter(
                    x=betas_sml, y=rend_sml, name="SML (Teórica)",
                    line=dict(color="#3b82f6", width=2, dash="dash"),
                ))
                
                for _, row in df_capm.iterrows():
                    fig_sml.add_trace(go.Scatter(
                        x=[row["beta"]], y=[row["rendimiento_esperado_capm"] * 100],
                        mode="markers+text", text=[row["ticker"]], textposition="top right",
                        marker=dict(size=12, color="#f43f5e"), showlegend=False
                    ))
                
                try: fig_sml.update_layout(**plotly_layout("Security Market Line (SML)", height=400, xaxis_title="Beta (β)", yaxis_title="E(R) %"))
                except: fig_sml.update_layout(title="Security Market Line", height=400, template="plotly_dark")
                st.plotly_chart(fig_sml, use_container_width=True)

            with st.expander("ℹ️ Guía de interpretación CAPM"):
                st.markdown("""
                - **Beta (β) > 1.2 (Agresivo):** El activo amplifica los movimientos del mercado. Mayor riesgo, pero mayor retorno esperado.
                - **Beta (β) < 0.8 (Defensivo):** El activo es menos volátil que el mercado. Ideal para proteger capital en tendencias bajistas.
                - **Alpha de Jensen (α):** Si es positivo, el activo superó el rendimiento teórico ajustado por riesgo. Indica "generación de valor".
                - **R² (R-Cuadrado):** Indica qué tanto del movimiento del activo se explica por el mercado. Un R² alto significa que el riesgo es mayoritariamente **sistemático**.
                """)
        else:
            st.error("⚠️ No se pudo obtener la información del CAPM. Verifica el backend.")


# ═══════════════════ TAB 5 — VALOR EN RIESGO (VaR) Y CVAR ═══════════════════

with tabs[5]:
    st.subheader("🛡️ Gestión de Riesgo — VaR y CVaR")
    st.info("""
        El **Value at Risk (VaR)** mide la pérdida máxima potencial en un horizonte de 1 día con un nivel de confianza determinado. 
        El **CVaR (Expected Shortfall)** mide la pérdida promedio en caso de que se supere el VaR.
    """)

    st.caption(f"**Confianza:** {confianza_var:.0%} | **Capital:** ${valor_portafolio:,.0f}")

    # ── VaR del Portafolio Completo (automático) ──
    cache_key_vp = f"var_portafolio_{confianza_var}_{fi}_{ff}"
    if cache_key_vp not in st.session_state:
        with st.spinner("Calculando VaR del portafolio..."):
            resultado_vp = api_get("/analisis/var-portafolio", params={"nivel": confianza_var, "tickers": tickers, "fecha_inicio": fi, "fecha_fin": ff})
            if resultado_vp:
                st.session_state[cache_key_vp] = resultado_vp

    data_vp = st.session_state.get(cache_key_vp)

    if data_vp:
        st.markdown("### 📊 VaR del Portafolio Completo")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("VaR Portafolio", f"{data_vp['var_parametrico_portafolio']:.6f}",
                delta=f"-USD {abs(data_vp['var_parametrico_portafolio'])*valor_portafolio:,.0f}")
        c2.metric("Volatilidad Anual", f"{data_vp['volatilidad_anual_portafolio']*100:.2f}%")
        c3.metric("Retorno Esperado", f"{data_vp['retorno_anual_esperado']*100:.2f}%")
        # CVaR aproximado = VaR * 1.3 (aproximación estándar)
        cvar_port = abs(data_vp['var_parametrico_portafolio']) * 1.3
        c4.metric("CVaR Estimado", f"{-cvar_port:.6f}",
                delta=f"-USD {cvar_port*valor_portafolio:,.0f}")
        st.info("El VaR del portafolio es **menor** que la suma de los VaR individuales gracias a la **diversificación**.")
        st.divider()

    # ── VaR Individual por Activo (automático) ──
    st.markdown("### 🎯 Análisis Individual por Activo")

    # Precarga todos
    for _t in tickers:
        _key = f"var_{_t}_{confianza_var}_{fi}_{ff}"
        if _key not in st.session_state:
            safe_t = urllib.parse.quote(_t, safe='')
            _data = {
                "var":  api_get(f"/analisis/var/{safe_t}", params={"fecha_inicio": fi, "fecha_fin": ff}),
                "rend": api_get(f"/analisis/rendimientos/{safe_t}", params={"fecha_inicio": fi, "fecha_fin": ff}),
            }
            if _data["var"] and _data["rend"]:
                st.session_state[_key] = _data

    def metric_var(label, val, cap):
        st.metric(label, f"{val*100:.4f}%",
                  delta=f"-${abs(val)*cap:,.0f}", delta_color="inverse")

    for idx, t in enumerate(tickers):
        cache_key_t = f"var_{t}_{confianza_var}_{fi}_{ff}"
        datos = st.session_state.get(cache_key_t)

        with st.expander(f"🛡️ {t} — VaR y CVaR", expanded=(idx == 0)):
            if not datos:
                st.info("⏳ Cargando...")
                continue

            data_v = datos["var"]
            data_r = datos["rend"]

            es_normal = data_r["jarque_bera"]["es_normal"]
            metodo_rec = "Paramétrico" if es_normal else "Histórico / Monte Carlo"

            if not es_normal:
                st.warning(f"⚠️ Rendimientos no normales — método recomendado: **{metodo_rec}**")
            else:
                st.success(f"✅ Rendimientos normales — método recomendado: **{metodo_rec}**")

            c1, c2, c3, c4 = st.columns(4)
            with c1: metric_var("VaR Paramétrico", data_v['var_parametrico'], valor_portafolio)
            with c2: metric_var("VaR Histórico", data_v['var_historico'], valor_portafolio)
            with c3: metric_var("VaR Monte Carlo", data_v['var_montecarlo'], valor_portafolio)
            with c4: metric_var("CVaR (Shortfall)", data_v['cvar'], valor_portafolio)

            col_tab, col_fig = st.columns([1, 1.2])
            with col_tab:
                res_data = [
                    {"Método": "Paramétrico", "VaR (%)": data_v['var_parametrico']*100, "VaR ($)": abs(data_v['var_parametrico'])*valor_portafolio},
                    {"Método": "Histórico",   "VaR (%)": data_v['var_historico']*100,   "VaR ($)": abs(data_v['var_historico'])*valor_portafolio},
                    {"Método": "Monte Carlo", "VaR (%)": data_v['var_montecarlo']*100,  "VaR ($)": abs(data_v['var_montecarlo'])*valor_portafolio},
                    {"Método": "CVaR",        "VaR (%)": data_v['cvar']*100,            "VaR ($)": abs(data_v['cvar'])*valor_portafolio},
                ]
                df_res = pd.DataFrame(res_data)
                st.table(df_res.set_index("Método").style.format(
                    {"VaR (%)": "{:.4f}%", "VaR ($)": "${:,.2f}"}))

            with col_fig:
                fig_v = go.Figure()
                fig_v.add_trace(go.Bar(
                    x=df_res["Método"], y=df_res["VaR (%)"],
                    marker_color=["#818CF8", "#636EFA", "#00CC96", "#ED1E79"],
                    text=df_res["VaR (%)"].round(4).astype(str) + "%",
                    textposition='auto'
                ))
                try:
                    fig_v.update_layout(**plotly_layout(
                        f"Comparativa VaR — {t} ({confianza_var:.0%})", height=320,
                        yaxis_title="% pérdida diaria"))
                except:
                    fig_v.update_layout(title=f"VaR {t}", height=320)
                st.plotly_chart(fig_v, use_container_width=True)

            var_h_str = f"USD {abs(data_v['var_historico'])*valor_portafolio:,.0f}"
            cvar_str = f"USD {abs(data_v['cvar'])*valor_portafolio:,.0f}"
            st.info(
                f"Al {confianza_var:.0%} de confianza, existe solo un "
                f"{100-confianza_var*100:.0f}% de probabilidad de que las pérdidas de "
                f"{t} superen {var_h_str} en un día. "
                f"En el escenario extremo (CVaR), la pérdida promedio sería {cvar_str}."
            )

    st.divider()
    with st.expander("ℹ️ ¿Qué método es más confiable?"):
        st.markdown("""
        | Método | Cuándo usarlo |
        |---|---|
        | **Paramétrico** | Si los datos son **Normales** (Jarque-Bera p > 0.05). |
        | **Histórico** | Si hay **Colas Pesadas**. No asume normalidad. |
        | **Monte Carlo** | El más flexible para portafolios complejos. |
        """)
        

# ═══════════════════ MÓD 6 — MARKOWITZ ═══════════════════

with tabs[6]:
    st.subheader("⚡ Optimización de Markowitz — Frontera Eficiente")
    st.info(
        "La **Teoría Moderna de Portafolios** de Markowitz busca el balance óptimo entre riesgo y retorno. "
        "La **frontera eficiente** muestra todas las combinaciones de activos que maximizan el retorno para un nivel dado de riesgo.",
        icon="💡",
    )

    # ── Controles ──
    col_c1, col_c2 = st.columns(2)
    with col_c1:
        n_port = st.slider("Portafolios a simular", 1000, 30000, 1000, step=1000, key="m6_slider_n")
    with col_c2:
        permitir_cortos = st.checkbox("Permitir ventas en corto", key="m6_cortos")
        if permitir_cortos:
            st.caption("⚠️ Modo experimental — la frontera puede ser aproximada con ventas en corto acotadas (máx. 20% por activo).")
    

    # ── Carga automática ──
    cache_key_m6 = f"markowitz_{'-'.join(tickers)}_{permitir_cortos}"
    if cache_key_m6 not in st.session_state:
        with st.spinner("Calculando frontera eficiente y descargando precios..."):
            data_m = api_get("/analisis/markowitz", params={"permitir_cortos": permitir_cortos, "tickers": tickers})
            precios_dict = {}
            for t in tickers:
                safe_t = urllib.parse.quote(t, safe='')
                p_data = cached_get(f"/precios/{safe_t}")
                if p_data and isinstance(p_data, list) and len(p_data) > 0:
                    df_p = pd.DataFrame(p_data)
                    df_p["fecha"] = pd.to_datetime(df_p["fecha"])
                    precios_dict[t] = df_p.set_index("fecha")["close"]

            if data_m:
                st.session_state[cache_key_m6] = {
                    "data_m": data_m,
                    "precios_dict": precios_dict,
                }

    cached = st.session_state.get(cache_key_m6, {})
    data_m = cached.get("data_m")
    precios_dict = cached.get("precios_dict", {})
    
    if not data_m or len(precios_dict) < 2:
        st.info("⏳ Ve primero al **Tab 1** para cargar los datos del portafolio.")
    elif "optimizacion" not in data_m:
        st.error("⚠️ El backend no logró calcular la frontera eficiente.")
    else:
        opt = data_m["optimizacion"]
        frontera = pd.DataFrame(data_m.get("frontera", []))

        # Tasa FRED
        rf_anual = 0.04
        try:
            curva = cached_get("/renta-fija/curva")
            if curva and "datos_mercado" in curva:
                rf_anual = curva["datos_mercado"]["tasas"][0] / 100
        except: pass

        # ── Métricas Header ──
        ms_retorno = opt["retorno_anual"]
        ms_riesgo = opt["riesgo_anual"]
        ms_sharpe = opt["sharpe_ratio"]


        st.divider()

        # ── 1. Gráfico Frontera Eficiente (LO PRIMERO) ──
        st.markdown("### 📈 Frontera Eficiente — Conjunto de Portafolios Posibles")

        with st.spinner(f"Simulando {n_port:,} portafolios..."):
            df_precios = pd.DataFrame(precios_dict)
            df_ret = np.log(df_precios / df_precios.shift(1)).dropna()
            mean_returns = df_ret.mean() * 252
            cov_matrix = df_ret.cov() * 252
            num_activos = len(tickers)
            resultados_sim = np.zeros((3, n_port))

            for i in range(n_port):
                if permitir_cortos:
                    while True:
                        pesos = np.random.uniform(-0.2, 1.2, num_activos)
                        pesos /= np.sum(pesos)
                        std_test = np.sqrt(np.dot(pesos.T, np.dot(cov_matrix, pesos)))
                        if std_test < 0.60:
                            break
                else:
                    pesos = np.random.random(num_activos)
                    pesos /= np.sum(pesos)
                retorno_port = np.sum(mean_returns * pesos)
                std_port = np.sqrt(np.dot(pesos.T, np.dot(cov_matrix, pesos)))
                sharpe_port = (retorno_port - rf_anual) / std_port if std_port > 0 else 0
                resultados_sim[0, i] = std_port
                resultados_sim[1, i] = retorno_port
                resultados_sim[2, i] = sharpe_port

        # ── Extender frontera con rango real del Monte Carlo ──
        if permitir_cortos:
            import scipy.optimize as sco
            retorno_max_mc = float(resultados_sim[1].max())
            retorno_min_mc = float(resultados_sim[1].min())
            
            cov_np = cov_matrix.values
            mean_np = mean_returns.values
            
            frontera_ext = []
            targets = np.linspace(retorno_min_mc, retorno_max_mc * 1.1, 50)

            for target in targets:
                def min_vol(p, cov=cov_np):
                    return np.sqrt(np.dot(p.T, np.dot(cov, p)))
                
                constraints = [
                    {'type': 'eq', 'fun': lambda p: np.sum(p) - 1},
                    {'type': 'ineq', 'fun': lambda p, t=target, m=mean_np: m @ p - t}
                ]
                bounds = [(-0.2, 1.2)] * num_activos
                
                result = sco.minimize(min_vol,
                    x0=np.ones(num_activos)/num_activos,
                    method='SLSQP',
                    bounds=bounds,
                    constraints=constraints,
                    options={'maxiter': 1000, 'ftol': 1e-9})
                
                if result.success and result.fun < 0.60:
                    frontera_ext.append({
                        "retorno": float(mean_np @ result.x),
                        "riesgo": float(result.fun)
                    })

            if len(frontera_ext) >= 3:
                frontera = pd.DataFrame(frontera_ext)

        fig_mk = go.Figure()
        # Filtrar portafolios por encima de la frontera
        retorno_max_frontera = frontera["retorno"].max() if not frontera.empty else float('inf')
        mask = resultados_sim[1] <= retorno_max_frontera
        resultados_sim = resultados_sim[:, mask]
        fig_mk.add_trace(go.Scatter(
            x=resultados_sim[0] * 100, y=resultados_sim[1] * 100,
            mode="markers", name=f"{n_port:,} simulaciones",
            marker=dict(
                color=resultados_sim[2], colorscale="Viridis",
                size=4, opacity=0.5, colorbar=dict(title="Sharpe"),
            ),
            hovertemplate="Riesgo: %{x:.2f}%<br>Retorno: %{y:.2f}%<br>Sharpe: %{marker.color:.4f}<extra></extra>"
        ))

        if not frontera.empty:
            frontera_sorted = frontera.sort_values("riesgo")
            fig_mk.add_trace(go.Scatter(
                x=frontera_sorted["riesgo"] * 100,
                y=frontera_sorted["retorno"] * 100,
                mode="lines", name="Frontera Eficiente",
                line=dict(color="#ED1E79", width=4),
            ))
            min_var_row = frontera_sorted.iloc[0]
            fig_mk.add_trace(go.Scatter(
                x=[min_var_row["riesgo"] * 100], y=[min_var_row["retorno"] * 100],
                mode="markers+text", name="Mínima Varianza",
                text=["💎 Mín. Varianza"], textposition="bottom right",
                marker=dict(color="#38BDF8", size=14, symbol="diamond",
                          line=dict(color="white", width=2)),
            ))

        fig_mk.add_trace(go.Scatter(
            x=[ms_riesgo * 100], y=[ms_retorno * 100],
            mode="markers+text", name="Máximo Sharpe",
            text=["⭐ Máx. Sharpe"], textposition="top left",
            marker=dict(color="gold", size=20, symbol="star",
                      line=dict(color="black", width=2)),
        ))

        try:
            fig_mk.update_layout(**plotly_layout(
                "Modelo de Markowitz", height=480,
                xaxis_title="Volatilidad anualizada (%)",
                yaxis_title="Rendimiento esperado (%)"
            ))
        except:
            fig_mk.update_layout(title="Frontera de Markowitz", height=400)
        st.plotly_chart(fig_mk, use_container_width=True)

        st.divider()

        # ── 2. Métricas del portafolio óptimo ──
        st.markdown("### ⭐ Portafolio Óptimo (Máximo Sharpe)")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Retorno Esperado", f"{ms_retorno*100:.2f}%")
        m2.metric("Riesgo (Volatilidad)", f"{ms_riesgo*100:.2f}%")
        m3.metric("Sharpe Ratio", f"{ms_sharpe:.4f}",
                  delta="Excelente ✅" if ms_sharpe > 2 else "Bueno ✅" if ms_sharpe > 1 else "Moderado ⚠️")
        m4.metric("Tasa Libre de Riesgo", f"{rf_anual*100:.2f}%", delta="FRED")

        st.divider()

        # ── 3. Correlación + Pie chart ──
        col_corr, col_pie = st.columns([1, 1])
        with col_corr:
            st.markdown("#### 🔗 Matriz de Correlación")
            corr_df = df_ret.corr()
            fig_corr = go.Figure(data=go.Heatmap(
                z=corr_df.values,
                x=corr_df.columns.tolist(),
                y=corr_df.index.tolist(),
                colorscale="RdBu", zmin=-1, zmax=1,
                text=corr_df.round(2).values,
                texttemplate="%{text}",
                textfont={"size": 11},
                colorbar=dict(title="ρ"),
            ))
            try:
                fig_corr.update_layout(**plotly_layout("Correlación entre activos", height=380))
            except:
                fig_corr.update_layout(title="Correlación", height=380)
            st.plotly_chart(fig_corr, use_container_width=True)

        with col_pie:
            st.markdown("#### 🥧 Distribución Óptima")
            df_ms = pd.DataFrame(list(opt["pesos"].items()), columns=["Ticker", "Peso"])
            df_ms["Peso_pct"] = df_ms["Peso"] * 100
            fig_pie = px.pie(df_ms, values="Peso_pct", names="Ticker", hole=0.4,
                color_discrete_sequence=px.colors.qualitative.Set2)
            fig_pie.update_traces(textposition='inside', textinfo='percent+label')
            try:
                fig_pie.update_layout(**plotly_layout("Pesos del Portafolio Óptimo", height=380))
            except:
                fig_pie.update_layout(title="Pesos", height=380)
            st.plotly_chart(fig_pie, use_container_width=True)

        st.divider()

        # ── 4. Distribución monetaria ──
        st.markdown("#### 💰 Distribución de la Inversión Óptima")
        cols_inv = st.columns(len(opt["pesos"]))
        for i, (t, w) in enumerate(opt["pesos"].items()):
            monto = w * valor_portafolio
            with cols_inv[i]:
                if w < 0:
                    st.metric(f"🔴 {t}", f"USD {monto:,.0f}",
                            delta=f"Corto {w*100:.1f}%", delta_color="inverse")
                else:
                    st.metric(f"🟢 {t}", f"USD {monto:,.0f}",
                            delta=f"{w*100:.1f}%")

        st.divider()

        # ── 5. Comparación fronteras ──
        st.markdown("#### 📊 Costo de la Restricción de No-Negatividad")
        cache_key_cortos = f"markowitz_cortos_{'-'.join(tickers)}"
        if cache_key_cortos not in st.session_state:
            with st.spinner("Calculando frontera con cortos..."):
                resultado_cortos = api_get("/analisis/markowitz", params={
                    "permitir_cortos": True,
                    "tickers": tickers,
                })
                if resultado_cortos:
                    st.session_state[cache_key_cortos] = resultado_cortos

        data_cortos = st.session_state.get(cache_key_cortos)
        if data_cortos:
            frontera_cortos = pd.DataFrame(data_cortos.get("frontera", []))
            fig_comp = go.Figure()
            if not frontera.empty:
                fig_comp.add_trace(go.Scatter(
                    x=frontera.sort_values("riesgo")["riesgo"] * 100,
                    y=frontera.sort_values("riesgo")["retorno"] * 100,
                    mode="lines", name="Sin cortos (wi ≥ 0)",
                    line=dict(color="#10b981", width=3),
                ))
            if not frontera_cortos.empty:
                fc = frontera_cortos.sort_values("riesgo")
                fig_comp.add_trace(go.Scatter(
                    x=fc["riesgo"] * 100, y=fc["retorno"] * 100,
                    mode="lines", name="Con cortos (wi ∈ ℝ)",
                    line=dict(color="#f59e0b", width=3, dash="dash"),
                ))
            try:
                fig_comp.update_layout(**plotly_layout(
                    "Comparación de Fronteras", height=400,
                    xaxis_title="Volatilidad (%)",
                    yaxis_title="Retorno (%)"))
            except:
                fig_comp.update_layout(title="Comparación", height=400)
            st.plotly_chart(fig_comp, use_container_width=True)

        with st.expander("ℹ️ Interpretación del Modelo de Markowitz"):
            st.markdown(f"""
            - **Frontera Eficiente (línea rosa):** todas las combinaciones óptimas. Cualquier portafolio por debajo es subóptimo.
            - **Mínima Varianza 💎:** menor riesgo posible, ideal para inversores conservadores.
            - **Máximo Sharpe ⭐ ({ms_sharpe:.2f}):** {"excelente" if ms_sharpe > 2 else "bueno" if ms_sharpe > 1 else "moderado"} — por cada unidad de riesgo el portafolio genera **{ms_sharpe:.2f}x** el retorno sobre la tasa libre de riesgo ({rf_anual*100:.2f}%).
            - **Sin cortos:** solo posiciones largas. Más conservador.
            - **Con cortos:** mayor flexibilidad pero más riesgo.
            """)

# ═══════════════════ TAB 7 — SEÑALES Y SEMÁFOROS ═══════════════════

with tabs[7]:
    st.subheader("🚦 Semáforo de Trading — Análisis Técnico")
    
    # 1. INYECCIÓN DE CSS PARA LAS TARJETAS DE SEÑAL
    st.markdown("""
        <style>
        .semaforo-verde {
        background-color: rgba(16,185,129,0.15);
        border: 1px solid #10b981;
        padding: 15px; border-radius: 10px; color: #065f46 !important;
        }
        .semaforo-rojo {
        background-color: rgba(239,68,68,0.15);
        border: 1px solid #ef4444;
        padding: 15px; border-radius: 10px; color: #7f1d1d !important;
        }
        .semaforo-amarillo {
            background-color: #fef08a;
            border: 1px solid #facc15;
            padding: 15px; border-radius: 10px; color: #1a1a1a !important;
        }
        .semaforo-title {
            font-weight: 800; font-size: 18px; margin-bottom: 8px; display: block;
        }
        .semaforo-desc {
            font-size: 13px; line-height: 1.4; display: block;
        }
        </style>
    """, unsafe_allow_html=True)

    # Función auxiliar para emojis en la tabla
    def get_emoji_senal(s):
        if "COMPRA" in s: return "🟢"
        if "VENTA" in s: return "🔴"
        return "🟡"

    for t in tickers:
        # Llamada al backend actual
        safe_t = urllib.parse.quote(t, safe='')
        data_s = cached_get(f"/analisis/indicadores/{safe_t}")
        
        if data_s and "indicadores" in data_s:
            # Convertimos a DataFrame y tomamos el último registro
            df_s = pd.DataFrame(data_s["indicadores"]).T
            if df_s.empty: continue
            
            ultimo = df_s.iloc[-1]
            precio_act = ultimo.get("close", 0)
            
            # 2. LÓGICA DE GENERACIÓN DE SEÑALES (Basada en tus indicadores actuales)
            señales_detalle = []
            
            # RSI
            rsi_val = ultimo["rsi"]
            if rsi_val > 70: s_rsi = ("RSI", "🔴 VENTA", f"Sobrecompra ({rsi_val:.1f})")
            elif rsi_val < 30: s_rsi = ("RSI", "🟢 COMPRA", f"Sobreventa ({rsi_val:.1f})")
            else: s_rsi = ("RSI", "🟡 NEUTRAL", f"RSI normal ({rsi_val:.1f})")
            señales_detalle.append(s_rsi)

            # BOLLINGER
            close = ultimo["close"]
            if close > ultimo["bollinger_upper"]: s_bb = ("Bollinger", "🔴 VENTA", "Precio sobre banda superior")
            elif close < ultimo["bollinger_lower"]: s_bb = ("Bollinger", "🟢 COMPRA", "Precio bajo banda inferior")
            else: s_bb = ("Bollinger", "🟡 NEUTRAL", "Dentro de bandas")
            señales_detalle.append(s_bb)

            # MACD
            if ultimo["macd"] > ultimo["macd_signal"]: s_macd = ("MACD", "🟢 COMPRA", "Cruce alcista (MACD > Señal)")
            else: s_macd = ("MACD", "🔴 VENTA", "Cruce bajista (MACD < Señal)")
            señales_detalle.append(s_macd)

            # ESTOCÁSTICO
            stoch = ultimo["stochastic_k"]
            if stoch > 80: s_st = ("Estocástico", "🔴 VENTA", f"Zona de techo ({stoch:.1f})")
            elif stoch < 20: s_st = ("Estocástico", "🟢 COMPRA", f"Zona de suelo ({stoch:.1f})")
            else: s_st = ("Estocástico", "🟡 NEUTRAL", f"Neutral ({stoch:.1f})")
            señales_detalle.append(s_st)

            # 3. CÁLCULO DEL SEMÁFORO GLOBAL
            compras = sum(1 for s in señales_detalle if "COMPRA" in s[1])
            ventas = sum(1 for s in señales_detalle if "VENTA" in s[1])
            
            if compras >= 3:
                status, css, emoji, desc = "VERDE - COMPRA FUERTE", "semaforo-verde", "🟢", "La mayoría de indicadores técnicos sugieren una entrada alcista con alta probabilidad."
            elif ventas >= 3:
                status, css, emoji, desc = "ROJO - VENTA FUERTE", "semaforo-rojo", "🔴", "Múltiples señales de agotamiento detectadas. Se recomienda precaución o toma de beneficios."
            elif compras == 2:
                status, css, emoji, desc = "AMARILLO - COMPRA DÉBIL", "semaforo-amarillo", "🟡", "Existen señales mixtas con sesgo alcista. Se recomienda esperar confirmación adicional."
            elif ventas == 2:
                status, css, emoji, desc = "AMARILLO - VENTA DÉBIL", "semaforo-amarillo", "🟡", "Presión bajista leve detectada. Posible consolidación de precios."
            else:
                status, css, emoji, desc = "AMARILLO - NEUTRAL", "semaforo-amarillo", "🟡", "El activo se encuentra en una fase lateral sin tendencia clara según los indicadores."

            # 4. DESPLIEGUE VISUAL (El diseño del proyecto anterior)
            st.markdown(f"### {emoji} {t} — ${precio_act:,.2f}")
            
            c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
            with c1:
                st.markdown(
                    f'<div class="{css}">'
                    f'<span class="semaforo-title">{status}</span>'
                    f'<span class="semaforo-desc">{desc}</span>'
                    f'</div>',
                    unsafe_allow_html=True
                )
            
            c2.metric("🟢 Compra", compras)
            c3.metric("🔴 Venta", ventas)
            c4.metric("🟡 Neutral", 4 - (compras + ventas))

            # Tabla detallada con los indicadores
            df_final = pd.DataFrame(señales_detalle, columns=["Indicador", "Señal", "Detalle"])
            st.dataframe(df_final.set_index("Indicador"), use_container_width=True)
            st.divider()


# ═══════════════════ TAB 8 — CONTEXTO MACRO Y BENCHMARK ═══════════════════

with tabs[8]:
    st.subheader("🌐 Contexto Macroeconómico y Benchmark")

    # Carga automática
    cache_key_m8 = f"macro_{benchmark}"
    if cache_key_m8 not in st.session_state:
        with st.spinner("Consultando FRED y calculando métricas..."):
            data_macro = api_get("/macro/")
            data_bench = api_get("/macro/benchmark", params={"benchmark": benchmark})
            if data_macro and data_bench:
                st.session_state[cache_key_m8] = {
                    "macro": data_macro,
                    "bench": data_bench,
                }

    cached_m8 = st.session_state.get(cache_key_m8, {})
    data_macro = cached_m8.get("macro")
    data_bench = cached_m8.get("bench")

    if not data_macro:
        st.info("⏳ Cargando datos macroeconómicos...")
    else:
        # ── Métricas macro ──
        st.markdown("### 📡 Indicadores Macroeconómicos USA (FRED)")
        c1, c2 = st.columns(2)
        c1.metric("Tasa Libre de Riesgo", f"{data_macro['tasa_libre_riesgo']*100:.2f}%",
                  delta="Bonos del Tesoro USA")
        c2.metric("Inflación Anual USA", f"{data_macro['inflacion_anual_pct']:.2f}%",
                  delta="CPI")

        # ── Curva de rendimientos ──
        curva = data_macro["curva"]
        df_curva = pd.DataFrame({
            "Plazo (años)": curva["plazos"],
            "Tasa (%)": curva["tasas"]
        })

        fig_c = go.Figure()
        fig_c.add_trace(go.Scatter(
            x=df_curva["Plazo (años)"], y=df_curva["Tasa (%)"],
            mode="lines+markers",
            line=dict(color="#3b82f6", width=3),
            marker=dict(size=8, color="#1e40af"),
            fill="tozeroy",
            fillcolor="rgba(59,130,246,0.1)",
            name="Tasa (%)"
        ))
        try:
            fig_c.update_layout(**plotly_layout(
                "Curva de Rendimiento USA (FRED)",
                height=380,
                xaxis_title="Plazo (años)",
                yaxis_title="Tasa (%)"
            ))
        except:
            fig_c.update_layout(title="Curva de Rendimiento", height=380)
        st.plotly_chart(fig_c, use_container_width=True)

        st.divider()

        if data_bench:
            st.markdown(f"### 📊 Desempeño del Portafolio vs {benchmark}")

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Tracking Error",
                      f"{data_bench['tracking_error']*100:.2f}%",
                      delta="Desviación vs benchmark")
            c2.metric("Information Ratio",
                      f"{data_bench['information_ratio']:.4f}",
                      delta="Retorno activo / TE")
            c3.metric("Max Drawdown",
                      f"{data_bench['max_drawdown']*100:.2f}%",
                      delta="Peor caída histórica",
                      delta_color="inverse")
            c4.metric("Sharpe Portafolio",
                      f"{data_bench['sharpe_portafolio']:.4f}")

            st.divider()

            col1, col2 = st.columns(2)
            with col1:
                ret_port = data_bench['retorno_acumulado_portafolio'] * 100
                ret_bench = data_bench['retorno_acumulado_benchmark'] * 100
                diferencia = ret_port - ret_bench
                st.metric("Retorno Acumulado Portafolio",
                          f"{ret_port:.2f}%",
                          delta=f"{diferencia:+.2f}% vs {benchmark}",
                          delta_color="normal" if diferencia >= 0 else "inverse")
            with col2:
                st.metric(f"Retorno Acumulado {benchmark}",
                          f"{ret_bench:.2f}%")

            with st.expander("ℹ️ Interpretación de métricas"):
                st.markdown(f"""
                - **Tracking Error:** desviación del portafolio respecto al benchmark. 
                  Valor actual **{data_bench['tracking_error']*100:.2f}%** — {"bajo, muy alineado al índice" if data_bench['tracking_error'] < 0.05 else "moderado, gestión activa"}.
                - **Information Ratio:** exceso de retorno por unidad de tracking error. 
                  {"Positivo ✅ — el portafolio supera al benchmark ajustado por riesgo." if data_bench['information_ratio'] > 0 else "Negativo ⚠️ — el portafolio rinde menos que el benchmark."}
                - **Max Drawdown:** mayor caída desde un pico histórico. 
                  Valor **{data_bench['max_drawdown']*100:.2f}%** — mide el peor escenario que vivió el portafolio.
                - **Sharpe:** rendimiento ajustado por riesgo total. Mayor = mejor relación riesgo-retorno.
                """)

# ═══════════════════ MÓD 9 — RENTA FIJA ═══════════════════

with tabs[9]:
    st.subheader("📐 Renta Fija — Duración y Convexidad")
    
    with st.container(border=True):
        c1, c2, c3 = st.columns(3)
        tasa_cupon = c1.number_input("Tasa Cupón (anual)", value=0.05, step=0.01, format="%.2f")
        vencimiento = c2.number_input("Vencimiento (años)", value=10, min_value=1, max_value=100)
        # Usamos la tasa de tu API Key de FRED
        tasa_desc = c3.number_input("Tasa Descuento (YTM)", value=tasa_fred, format="%.4f", 
                                   help="Tasa recuperada automáticamente de tu API de FRED")

    if st.button("🔄 Calcular Sensibilidad", key="btn_m9"):
        with st.spinner("Consultando métricas..."):
            data_rf = api_get("/renta-fija/duracion", params={"tasa_cupon": tasa_cupon, "vencimiento": vencimiento})
        
        if data_rf:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Precio del Bono", f"${data_rf['precio_bono']:.2f}")
            c2.metric("Duración Macaulay", f"{data_rf['duracion']:.2f} años")
            c3.metric("Convexidad", f"{data_rf['convexidad']:.4f}")
            
            impacto_1pct = -data_rf['duracion'] * 0.01 * data_rf['precio_bono']
            c4.metric("Efecto Δ 1% Tasa", f"{impacto_1pct:.2f}", delta="Pérdida estimada", delta_color="inverse")

            st.divider()

            # --- GRÁFICO CON NOMBRE Y COLORES NUEVOS ---
            st.markdown("#### 📈 Análisis de Sensibilidad")
            rango_yields = np.linspace(0.01, 0.20, 50)
            
            # Cálculo de la curva
            precios_curva = data_rf['precio_bono'] * (
                1 - data_rf['duracion'] * (rango_yields - tasa_desc) + 
                0.5 * data_rf['convexidad'] * (rango_yields - tasa_desc)**2
            )
            
            fig_rf = go.Figure()
            
            # Línea de la curva en AZUL CIELO (más visible que el blanco)
            fig_rf.add_trace(go.Scatter(
                x=rango_yields*100, y=precios_curva, 
                name="Precio Estimado", 
                line=dict(color="#38BDF8", width=4) 
            ))
            
            # Línea de Tasa FRED en NARANJA
            fig_rf.add_vline(
                x=tasa_desc*100, 
                line_dash="dash", 
                line_color="#F97316", 
                annotation_text=f" Tasa FRED: {tasa_desc*100:.2f}%",
                annotation_position="top right"
            )
            
            # CAMBIAMOS EL TÍTULO Y EL COLOR DEL TÍTULO
            fig_rf.update_layout(
                title={
                    'text': "<b>Curva de Sensibilidad del Bono</b>",
                    'y':0.9,
                    'x':0,
                    'xanchor': 'left',
                    'yanchor': 'top',
                    'font': {'size': 20, 'color': "#6DA9F3"} # Color gris azulado claro (muy visible)
                },
                xaxis_title="Tasa de Mercado (YTM %)",
                yaxis_title="Precio del Bono ($)",
                height=400,
                template="plotly_dark", # Forzamos tema oscuro para que todo contraste
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)'
            )
            
            st.plotly_chart(fig_rf, use_container_width=True)
            st.divider()
            st.markdown("#### 🔬 Comparación de 3 Aproximaciones ante Shocks")
            with st.spinner("Calculando shocks..."):
                data_sens = api_get("/renta-fija/sensibilidad",
                                   params={"tasa_cupon": tasa_cupon, "vencimiento": vencimiento})
            if data_sens:
                precio_base = data_sens["precio_base"]
                df_sens = pd.DataFrame(data_sens["shocks"])

                fig_sens = go.Figure()
                fig_sens.add_trace(go.Scatter(x=df_sens["shock_bp"], y=df_sens["precio_lineal"],
                    name="Lineal (solo D*)", line=dict(dash="dot", color="#f59e0b")))
                fig_sens.add_trace(go.Scatter(x=df_sens["shock_bp"], y=df_sens["precio_duracion_convexidad"],
                    name="D* + Convexidad", line=dict(dash="dash", color="#6366f1")))
                fig_sens.add_trace(go.Scatter(x=df_sens["shock_bp"], y=df_sens["precio_exacto"],
                    name="Reprice Exacto", line=dict(color="#10b981", width=3)))
                fig_sens.add_hline(y=precio_base, line_dash="dash", line_color="gray",
                                   annotation_text=f"Base: ${precio_base:.2f}")
                fig_sens.update_layout(title="Precio ante Shocks ±50/±100/±200 pb",
                                       xaxis_title="Shock (pb)", yaxis_title="Precio ($)", height=400)
                st.plotly_chart(fig_sens, use_container_width=True)
                st.dataframe(df_sens.rename(columns={
                    "shock_bp": "Shock (pb)", "precio_lineal": "Lineal",
                    "precio_duracion_convexidad": "D+Convexidad",
                    "precio_exacto": "Reprice Exacto", "cambio_pct_exacto": "Cambio %"
                }).set_index("Shock (pb)"), use_container_width=True)


# ═══════════════════ MÓD 10 — OPCIONES ═══════════════════

with tabs[10]:
    st.subheader("🧮 Valuación de Opciones — Black-Scholes")
    st.info("Black-Scholes calcula el precio teórico de opciones europeas basado en 5 parámetros de mercado.", icon="💡")

    # Tasa FRED
    tasa_fred_local = tasa_fred
    try:
        curva_opt = cached_get("/renta-fija/curva")
        if curva_opt and "datos_mercado" in curva_opt:
            tasa_fred_local = list(curva_opt["datos_mercado"]["tasas"])[0] / 100
    except:
        pass

    # Precio actual del ticker seleccionado
    precio_actual = 100.0
    try:
        ticker_opt = st.selectbox("Activo subyacente", tickers, key="opt_ticker")
        precios_opt = cached_get(f"/precios/{ticker_opt}")
        if precios_opt and len(precios_opt) > 0:
            precio_actual = float(precios_opt[-1]["close"])
    except:
        pass

    # ── Parámetros ──
    with st.container(border=True):
        st.caption(f"💡 Precio actual de **{ticker_opt}**: USD {precio_actual:,.2f}...")
        c1, c2, c3, c4, c5 = st.columns(5)
        S = c1.number_input("Precio Spot (S)", value=round(precio_actual, 2), min_value=0.01, step=5.0)
        K = c2.number_input("Strike (K)", value=round(precio_actual, 2), min_value=0.01, step=5.0)
        T = c3.number_input("Años (T)", value=1.0, min_value=0.01, max_value=50.0, step=0.1)
        r_opt = c4.number_input("Tasa (r)", value=tasa_fred_local, min_value=-0.20, max_value=1.0, format="%.4f")
        sigma = c5.number_input("Volatilidad (σ)", value=0.20, min_value=0.01, max_value=5.0, step=0.05)

    # ── Cálculo automático con session_state ──
    cache_key_bs = f"bs_{S}_{K}_{T}_{r_opt}_{sigma}"
    if cache_key_bs not in st.session_state:
        with st.spinner("Calculando Black-Scholes..."):
            resultado_bs = api_get("/opciones/black-scholes",
                params={"S": S, "K": K, "T": T, "r": r_opt, "sigma": sigma})
            if resultado_bs:
                st.session_state[cache_key_bs] = resultado_bs

    data_bs = st.session_state.get(cache_key_bs)

    if not data_bs:
        st.info("⏳ Calculando...")
    else:
        from scipy.stats import norm as sp_norm

        col1, col2 = st.columns([1, 1.5])
        with col1:
            st.markdown("### 💲 Primas")
            c_call, c_put = st.columns(2)
            c_call.metric("Call Price", f"USD {data_bs['precios']['call']:.4f}")
            c_put.metric("Put Price", f"USD {data_bs['precios']['put']:.4f}")

            st.markdown("### 📊 Griegas")
            g = data_bs["greeks"]
            g1, g2 = st.columns(2)
            g1.metric("Delta (Call)", f"{g['delta_call']:.4f}")
            g1.metric("Gamma", f"{g['gamma']:.6f}")
            g2.metric("Vega", f"{g['vega']:.4f}")
            g2.metric("Theta (Call)", f"{g['theta_call']:.4f}")

            with st.expander("ℹ️ Interpretación de Griegas"):
                st.markdown(f"""
                - **Delta {g['delta_call']:.3f}:** por cada USD 1 que sube el subyacente, la Call sube USD {g['delta_call']:.3f}.
                - **Gamma {g['gamma']:.5f}:** velocidad de cambio del Delta. Alto cerca del Strike.
                - **Vega {g['vega']:.3f}:** sensibilidad a la volatilidad. Por cada 1% más de σ, la prima cambia USD {g['vega']*0.01:.4f}.
                - **Theta {g['theta_call']:.3f}:** pérdida de valor por día que pasa (tiempo).
                """)

        with col2:
            st.markdown("### 📈 Perfil de Beneficios al Vencimiento")
            st_range = np.linspace(S*0.5, S*1.5, 100)
            payoff_call = np.maximum(st_range - K, 0) - data_bs['precios']['call']
            payoff_put = np.maximum(K - st_range, 0) - data_bs['precios']['put']

            fig_opt = go.Figure()
            fig_opt.add_trace(go.Scatter(
                x=st_range, y=payoff_call, name="Long Call",
                line=dict(color="#00f2ff", width=3),
                fill='tozeroy', fillcolor='rgba(0,242,255,0.1)'
            ))
            fig_opt.add_trace(go.Scatter(
                x=st_range, y=payoff_put, name="Long Put",
                line=dict(color="#ED1E79", width=3),
                fill='tozeroy', fillcolor='rgba(237,30,121,0.1)'
            ))
            fig_opt.add_hline(y=0, line_color="#94a3b8", line_width=1, line_dash="dash")
            fig_opt.add_vline(x=K, line_dash="dot", line_color="#f59e0b",
                            annotation_text=f"K={K:.0f}")
            fig_opt.add_vline(x=S, line_dash="dot", line_color="#10b981",
                            annotation_text=f"S={S:.0f}")
            try:
                fig_opt.update_layout(**plotly_layout(
                    "Perfil de Beneficios", height=380,
                    xaxis_title="Precio Subyacente", yaxis_title="P&G"))
            except:
                fig_opt.update_layout(title="Perfil", height=380)
            st.plotly_chart(fig_opt, use_container_width=True)

        st.divider()
        st.markdown("### 📊 Análisis de Sensibilidad")
        spots = np.linspace(S * 0.5, S * 1.5, 100)

        col_a, col_b = st.columns(2)
        with col_a:
            payoff_c = np.maximum(spots - K, 0)
            payoff_p = np.maximum(K - spots, 0)
            fig_payoff = go.Figure()
            fig_payoff.add_trace(go.Scatter(x=spots, y=payoff_c, name="Call",
                line=dict(color="#10b981", width=2)))
            fig_payoff.add_trace(go.Scatter(x=spots, y=payoff_p, name="Put",
                line=dict(color="#ef4444", width=2)))
            fig_payoff.add_vline(x=K, line_dash="dash", annotation_text=f"K={K:.0f}")
            try:
                fig_payoff.update_layout(**plotly_layout("Payoff a Vencimiento", height=300,
                    xaxis_title="Precio Spot", yaxis_title="Payoff"))
            except:
                fig_payoff.update_layout(title="Payoff", height=300)
            st.plotly_chart(fig_payoff, use_container_width=True)

        with col_b:
            precios_call = []
            for s in spots:
                if s <= 0: precios_call.append(0); continue
                d1 = (np.log(s/K) + (r_opt + sigma**2/2)*T) / (sigma*np.sqrt(T))
                d2 = d1 - sigma*np.sqrt(T)
                precios_call.append(s*sp_norm.cdf(d1) - K*np.exp(-r_opt*T)*sp_norm.cdf(d2))
            intrinseco = np.maximum(spots - K, 0)
            fig_precio = go.Figure()
            fig_precio.add_trace(go.Scatter(x=spots, y=precios_call, name="Precio Call BS",
                line=dict(color="#6366f1", width=2)))
            fig_precio.add_trace(go.Scatter(x=spots, y=intrinseco, name="Valor Intrínseco",
                line=dict(dash="dot", color="#f59e0b")))
            fig_precio.add_vline(x=S, line_dash="dash", annotation_text=f"S={S:.0f}")
            try:
                fig_precio.update_layout(**plotly_layout("Precio Call vs Spot", height=300,
                    xaxis_title="Precio Spot", yaxis_title="Precio"))
            except:
                fig_precio.update_layout(title="Precio Call", height=300)
            st.plotly_chart(fig_precio, use_container_width=True)

        # Delta vs Spot para distintos T
        fig_delta = go.Figure()
        for t_val, color in [(0.25, "#ef4444"), (0.5, "#f59e0b"), (1.0, "#10b981"), (2.0, "#6366f1")]:
            deltas = []
            for s in spots:
                if s <= 0: deltas.append(0); continue
                d1 = (np.log(s/K) + (r_opt + sigma**2/2)*t_val) / (sigma*np.sqrt(t_val))
                deltas.append(sp_norm.cdf(d1))
            fig_delta.add_trace(go.Scatter(x=spots, y=deltas, name=f"T={t_val}a",
                line=dict(color=color, width=2)))
        fig_delta.add_vline(x=K, line_dash="dash", annotation_text=f"K={K:.0f}")
        fig_delta.add_vline(x=S, line_dash="dot", line_color="#10b981",
                          annotation_text=f"S={S:.0f}")
        try:
            fig_delta.update_layout(**plotly_layout("Delta Call vs Spot (distintos horizontes)",
                height=350, xaxis_title="Precio Spot", yaxis_title="Delta"))
        except:
            fig_delta.update_layout(title="Delta", height=350)
        st.plotly_chart(fig_delta, use_container_width=True)


# ═══════════════════ MÓD 11 — STRESS ═══════════════════

with tabs[11]:
    st.subheader("💥 Análisis de Escenarios Extremos (Stress Test)")
    st.warning("Evaluación del impacto del portafolio ante eventos de 'Cisne Negro' históricos y catastróficos.")

    # Carga automática
    cache_key_st = f"stress_{'_'.join(tickers)}"
    if cache_key_st not in st.session_state:
        with st.spinner("Ejecutando simulación de crisis..."):
            resultado_st = api_get("/analisis/stress-test")
            if resultado_st:
                st.session_state[cache_key_st] = resultado_st

    data_st = st.session_state.get(cache_key_st)

    if not data_st:
        st.info("⏳ Ve primero al **Tab 1** para cargar los datos del portafolio.")
    else:
        escenarios = data_st["escenarios"]
        df_st = pd.DataFrame(escenarios)
        df_st["Impacto USD"] = df_st["impacto_portafolio"] * valor_portafolio
        df_st["Impacto %"] = df_st["impacto_portafolio"] * 100

        # ── Métricas resumen ──
        st.markdown("### 📊 Resumen de Impacto")
        peor = df_st.loc[df_st["impacto_portafolio"].idxmin()]
        mejor = df_st.loc[df_st["impacto_portafolio"].idxmax()]
        promedio = df_st["impacto_portafolio"].mean()

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Peor Escenario", peor["escenario"],
                  delta=f"{peor['Impacto %']:.2f}%", delta_color="inverse")
        m2.metric("Pérdida Máxima",
                  f"USD {abs(peor['Impacto USD']):,.0f}",
                  delta=f"{peor['Impacto %']:.2f}%", delta_color="inverse")
        m3.metric("Escenario Menos Severo", mejor["escenario"],
                  delta=f"{mejor['Impacto %']:.2f}%", delta_color="inverse")
        m4.metric("Impacto Promedio",
                  f"{promedio*100:.2f}%",
                  delta_color="inverse")

        st.divider()

        # ── Gráfico de barras ──
        fig_st = go.Figure()
        colors = ["#ef4444" if v < -0.05 else "#f59e0b" if v < 0 else "#10b981"
                  for v in df_st["impacto_portafolio"]]
        fig_st.add_trace(go.Bar(
            x=df_st["escenario"],
            y=df_st["Impacto USD"],
            marker_color=colors,
            text=df_st["Impacto %"].round(2).astype(str) + "%",
            textposition="outside",
        ))
        fig_st.add_hline(y=0, line_color="#94a3b8", line_width=1)
        try:
            fig_st.update_layout(**plotly_layout(
                "Impacto Monetario por Escenario de Crisis",
                height=420,
                xaxis_title="Escenario",
                yaxis_title="Impacto (USD)"
            ))
        except:
            fig_st.update_layout(title="Stress Test", height=420)
        st.plotly_chart(fig_st, use_container_width=True)

        st.divider()

        # ── Tarjetas detalladas ──
        st.markdown("### 🚨 Detalle por Escenario")
        grid = st.columns(3)
        for i, esc in enumerate(escenarios):
            impacto_pct = esc["impacto_portafolio"] * 100
            impacto_usd = esc["impacto_portafolio"] * valor_portafolio

            if impacto_pct < -10:
                bg_color = "rgba(239,68,68,0.15)"
                border_color = "#ef4444"
                nivel = "🔴 CRÍTICO"
            elif impacto_pct < -5:
                bg_color = "rgba(245,158,11,0.15)"
                border_color = "#f59e0b"
                nivel = "🟡 SEVERO"
            else:
                bg_color = "rgba(16,185,129,0.10)"
                border_color = "#10b981"
                nivel = "🟢 MODERADO"

            with grid[i % 3]:
                st.markdown(f"""
                    <div style="background:{bg_color}; border: 1px solid {border_color};
                                padding: 15px; border-radius: 10px; margin-bottom: 10px;">
                        <span style="font-size:11px; font-weight:600; color:{border_color};">{nivel}</span>
                        <h4 style="margin:4px 0; font-size:13px;">{esc['escenario']}</h4>
                        <p style="font-size:26px; font-weight:bold; margin:5px 0; color:{border_color};">
                            {impacto_pct:.2f}%</p>
                        <p style="margin:0; font-size:13px;">
                            Pérdida: USD {abs(impacto_usd):,.0f}</p>
                    </div>
                """, unsafe_allow_html=True)

        st.divider()

        # ── Heatmap ──
        st.markdown("### 🗺️ Heatmap: Activo × Escenario")
        nombres_esc = [e["escenario"] for e in escenarios]
        activos_hm = list(escenarios[0].get("impactos_por_activo", {}).keys()) if escenarios else []

        if activos_hm:
            matriz = [[e.get("impactos_por_activo", {}).get(a, 0) * 100
                       for e in escenarios] for a in activos_hm]
            fig_hm = go.Figure(data=go.Heatmap(
                z=matriz, x=nombres_esc, y=activos_hm,
                colorscale="RdYlGn", zmid=0,
                text=[[f"{v:.1f}%" for v in row] for row in matriz],
                texttemplate="%{text}",
                colorbar=dict(title="Impacto %"),
            ))
            try:
                fig_hm.update_layout(**plotly_layout(
                    "Sensibilidad por Activo y Escenario", height=380))
            except:
                fig_hm.update_layout(title="Heatmap", height=380)
            st.plotly_chart(fig_hm, use_container_width=True)

        with st.expander("ℹ️ Interpretación del Stress Test"):
            st.markdown(f"""
            - **🔴 CRÍTICO (< -10%):** escenarios catastróficos como crisis financieras globales o pandemias.
            - **🟡 SEVERO (-5% a -10%):** correcciones importantes del mercado o shocks sectoriales.
            - **🟢 MODERADO (> -5%):** impacto contenido gracias a la diversificación del portafolio.
            - **Peor escenario:** **{peor['escenario']}** con una pérdida de **USD {abs(peor['Impacto USD']):,.0f}** ({peor['Impacto %']:.2f}%).
            - El heatmap muestra qué activos son más vulnerables en cada crisis histórica.
            """)

# ═══════════════════ ML ═══════════════════

with tabs[12]:
    st.subheader("🤖 Inteligencia Artificial — Predicción de Tendencia")
    st.markdown("""
    El módulo de ML entrena y compara automáticamente **3 modelos de clasificación** 
    (Random Forest, XGBoost y Logistic Regression) para predecir si el precio de un 
    activo **subirá o bajará** al día siguiente.
    El sistema usa los **retornos logarítmicos de los últimos 5 días** como features 
    y selecciona automáticamente el modelo con mejor accuracy. Los hiperparámetros se 
    optimizan con **GridSearchCV** y el modelo se reentrenan automáticamente **cada 8 días**.
    """)
    st.divider()

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


# ═══════════════════ ARQUITECTURA TÉCNICA ═══════════════════

with tabs[13]:
    st.subheader("🧩 Arquitectura Técnica — Del dato a la visualización")
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
            line=dict(color=escenario["color"], width=4),
            hoverinfo="skip",
        ))
        fig_flujo.add_trace(go.Scatter(
            x=x_pos,
            y=[0] * len(nodos),
            mode="markers+text",
            marker=dict(size=38, color=escenario["color"], line=dict(width=3, color="white")),
            text=[str(i + 1) for i in x_pos],
            textfont=dict(color="white", size=14),
            textposition="middle center",
            hovertext=nodos,
            hovertemplate="%{hovertext}<extra></extra>",
        ))
        fig_flujo.update_layout(
            height=190,
            margin=dict(l=20, r=20, t=15, b=55),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            showlegend=False,
            xaxis=dict(
                tickmode="array", tickvals=x_pos, ticktext=nodos,
                showgrid=False, zeroline=False, tickfont=dict(size=11),
            ),
            yaxis=dict(visible=False, range=[-0.2, 0.2]),
        )
        st.plotly_chart(fig_flujo, use_container_width=True)

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
                    {"Tabla": "assets", "Rol": "Catálogo de tickers", "Interviene": recorrido != "Análisis de riesgo"},
                    {"Tabla": "prices", "Rol": "Históricos OHLCV", "Interviene": True},
                    {"Tabla": "portfolios", "Rol": "Asignación y pesos", "Interviene": False},
                    {"Tabla": "prediction_logs", "Rol": "Salida de ML", "Interviene": False},
                    {"Tabla": "signals_log", "Rol": "Alertas técnicas", "Interviene": False},
                    {"Tabla": "risklab_prices", "Rol": "Tabla cloud en Databricks", "Interviene": recorrido == "Consulta cloud Databricks"},
                ]
            )
            tablas["Interviene"] = tablas["Interviene"].map({True: "Sí", False: "No"})
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

        st.success(
            f"En este recorrido, {'Databricks SQL actúa como **capa cloud de consulta**' if recorrido == 'Consulta cloud Databricks' else 'SQLite actúa como **' + ('cache persistente' if recorrido == 'Persistencia desde Yahoo' else 'fuente local de datos') + '**'} "
            f"y la interfaz termina mostrando: **{escenario['presentacion']}**."
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
                    "FastAPI --> Databricks SQL Warehouse --> risklab_prices\n"
                    "Endpoint: GET /databricks/risklab-prices/resumen",
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

        sql_col, resultado_col = st.columns([1, 1.25])
        with sql_col:
            st.markdown(f"**{consulta_sel['titulo']}**")
            st.caption(consulta_sel["descripcion"])
            st.code(consulta_sel["sql"], language="sql")

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
                if st.button("▶ Ejecutar consulta en Databricks", key="btn_run_databricks_sql", type="primary"):
                    st.session_state["resultado_databricks_sql"] = api_get(
                        f"/databricks/consultas/{consulta_sel['id']}",
                        timeout=120,
                    )

                resultado_sql = st.session_state.get("resultado_databricks_sql")
                if resultado_sql and resultado_sql.get("id") == consulta_sel["id"]:
                    df_sql = pd.DataFrame(resultado_sql.get("resultados", []))
                    if df_sql.empty:
                        st.info("La consulta no devolvió filas.")
                    else:
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

        with st.expander("📌 Guion rápido para la presentación", expanded=True):
            st.markdown(
                f"**Caso seleccionado: {recorrido}.**\n\n"
                f"1. Streamlit dispara `{escenario['metodo']} {escenario['endpoint']}`.\n"
                f"2. FastAPI entrega una sesión SQLAlchemy y ejecuta **{escenario['accion']}**.\n"
                f"3. La capa de datos participa sobre **{escenario['recurso']}** en {escenario.get('almacen', 'SQLite')}.\n"
                f"4. La API devuelve **{escenario['salida']}** y el dashboard muestra **{escenario['presentacion']}**.\n"
                "5. Docker empaqueta frontend y backend; Databricks queda como capa cloud opcional para consultas SQL."
            )


# ═══════════════════ AGENTE IA ═══════════════════

with tabs[14]:
    st.subheader("🧠 RiskLab AI — Agente Financiero Inteligente")
    st.info("Análisis de riesgo en lenguaje natural potenciado por **llama3** corriendo localmente con Ollama.", icon="🤖")

    # ── Estado de Ollama ──────────────────────────────────────────────────────
    estado = api_get("/agente/estado")
    if not estado or not estado.get("disponible"):
        st.error("❌ Ollama no está corriendo. Abre una terminal y ejecuta: `ollama serve`")
        st.stop()

    st.success(f"✅ Ollama activo | Modelo: **{estado['modelo_activo']}** | "
               f"Modelos instalados: {', '.join(estado['modelos'])}")

    subtab_auto, subtab_chat = st.tabs(["📊 Análisis Automático", "💬 Chat Financiero"])

    # ── Sub-tab 1: Análisis automático ────────────────────────────────────────
    with subtab_auto:
        st.markdown("El agente recopila todas las métricas del portafolio y genera un **informe ejecutivo** completo.")

        if st.button("🔍 Generar Informe con IA", key="btn_agente", type="primary"):

            with st.spinner("⏳ Recopilando métricas del portafolio..."):
                data_var  = api_get(f"/analisis/var/{tickers[0]}")
                data_port = api_get("/analisis/var-portafolio", params={"nivel": confianza_var})
                data_mk   = api_get("/analisis/markowitz")
                params_capm = {"tickers": tickers, "benchmark": benchmark, "tasa_libre_riesgo": tasa_fred}
                data_capm = api_get("/analisis/capm", params=params_capm)

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
