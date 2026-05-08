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
        "title": {"text": f"<b>{title}</b>", "font": {"size": 16, "color": "#1e293b"}, "x": 0},
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor": "rgba(0,0,0,0)",
        "height": height,
        "margin": dict(l=40, r=20, t=60, b=40),
        "xaxis": {"title": xaxis_title, "gridcolor": "#e2e8f0", "showgrid": True},
        "yaxis": {"title": yaxis_title, "gridcolor": "#e2e8f0", "showgrid": True},
        "legend": {"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "right", "x": 1},
        "font": {"family": "Montserrat, sans-serif", "color": "#1e293b"}
    }

st.set_page_config(page_title="RiskLab USTA", page_icon="📊", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Montserrat', sans-serif; }
    .main-header {
        background: linear-gradient(135deg, #1a56db 0%, #1e40af 100%);
        padding: 1.5rem 2rem; border-radius: 12px; margin-bottom: 1.5rem;
    }
    .main-header h1 { margin: 0; font-size: 1.8rem; font-weight: 700; color: white; }
    .main-header p  { margin: 0.3rem 0 0; color: #e2e8f0; font-size: 0.9rem; }
    .stTabs [data-baseweb="tab-list"] { 
        gap: 2px; 
        overflow-x: auto !important; 
        flex-wrap: nowrap !important;
        scrollbar-width: thin;
    }
    .stTabs [data-baseweb="tab"] { 
        border-radius: 8px 8px 0 0; 
        padding: 6px 10px; 
        font-weight: 600; 
        font-size: 0.75rem;
        white-space: nowrap;
    }
</style>
""", unsafe_allow_html=True)

API = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")

# ═══════════════════ HELPERS ═══════════════════

def api_get(ep, params=None, timeout=120):
    try:
        r = requests.get(f"{API}{ep}", params=params, timeout=timeout); r.raise_for_status(); return r.json()
    except requests.exceptions.ConnectionError:
        st.error("❌ Backend no disponible. Asegúrate de que corre en :8000"); return None
    except requests.exceptions.HTTPError as e:
        st.error(f"❌ Error {e.response.status_code}: {e.response.json().get('detail', str(e))}"); return None
    except Exception as e:
        st.error(f"❌ {e}"); return None

def api_post(ep, body=None):
    try:
        r = requests.post(f"{API}{ep}", json=body or {}, timeout=120); r.raise_for_status(); return r.json()
    except requests.exceptions.ConnectionError:
        st.error("❌ Backend no disponible."); return None
    except requests.exceptions.HTTPError as e:
        st.error(f"❌ Error {e.response.status_code}: {e.response.json().get('detail', str(e))}"); return None
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
    "JNJ": "Johnson & Johnson (Salud)", "PFE": "Pfizer (Salud)",
    "UNH": "UnitedHealth (Salud)", "MRK": "Merck (Salud)",
    "XOM": "ExxonMobil (Energía)", "CVX": "Chevron (Energía)",
    "KO": "Coca-Cola (Consumo)", "PEP": "PepsiCo (Consumo)",
    "WMT": "Walmart (Consumo)", "MCD": "McDonald's (Consumo)",
    "NKE": "Nike (Consumo)", "SBUX": "Starbucks (Consumo)",
    "F": "Ford (Automotriz)", "GM": "General Motors (Automotriz)",
}

# ═══════════════════ SIDEBAR ═══════════════════

with st.sidebar:
    st.markdown("## ⚙️ Configuración")
    st.markdown("---")

    tickers = st.multiselect(
        "📦 Tickers del portafolio", options=list(TICKERS_DB.keys()),
        default=["AAPL", "JPM", "JNJ", "XOM", "KO"],
        format_func=lambda t: f"{t} — {TICKERS_DB[t]}",
    )

    ticker_custom = st.text_input("➕ Agregar ticker personalizado", placeholder="Ej: TSM, BABA",
                                   help="Escríbelo aquí separado por comas.")
    if ticker_custom.strip():
        extras = [t.strip().upper() for t in ticker_custom.split(",") if t.strip()]
        tickers = tickers + [t for t in extras if t not in tickers]

    if len(tickers) < 2:
        st.warning("⚠️ Selecciona al menos 2 activos.")

    ticker_sel = st.selectbox("🔍 Ticker a analizar", tickers if tickers else ["AAPL"])

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
    st.caption("**RiskLab USTA** · Teoría del Riesgo + Python APIs · CIII")

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
"🧮 10. Opciones", "💥 11. Stress", "🤖 ML", "🧠 Agente IA",
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
        - **Análisis:** Indicadores técnicos, VaR, CAPM, Markowitz, GARCH, EWMA
        - **Nuevos módulos:** Renta fija (Nelson-Siegel), Opciones (Black-Scholes), Stress Testing, ML
        - **Infraestructura:** Docker, GitHub Actions CI, deploy en Render
        
        ### Arquitectura
        ```
        Streamlit (8501) ──HTTP/JSON──► FastAPI (8000) ──► yfinance / FRED
                                          │
                                   SQLAlchemy + SQLite (cache)
                                   Pydantic v2 (validación)
                                   9 servicios de cálculo
        ```
        """)
    with col2:
        st.markdown("### Activos Seleccionados")
        for t in tickers:
            nombre = TICKERS_DB.get(t, t)
            st.write(f"**{t}** — {nombre}")
        st.info(f"Benchmark: **{benchmark}** | Inversión: **${valor_portafolio:,.0f}**")


# ═══════════════════ MÓD 1 — TÉCNICO ═══════════════════

with tabs[1]:
    st.subheader("📈 Análisis Técnico e Indicadores")

    # Descarga inicial
    if f"tab1_descargado_{'_'.join(tickers)}" not in st.session_state:
        with st.spinner("Descargando precios de todos los activos..."):
            for t in tickers:
                descargar_si_no_existe(t)
            descargar_si_no_existe(benchmark)
        st.session_state[f"tab1_descargado_{'_'.join(tickers)}"] = True

    # Gráfico comparativo base 100
    st.markdown("### 📊 Rendimiento Comparado — Base 100")
    fig_comp = go.Figure()
    for t in tickers:
        r_p = cached_get(f"/precios/{t}")
        if r_p and len(r_p) > 0:
            df_t = pd.DataFrame(r_p)
            df_t["fecha"] = pd.to_datetime(df_t["fecha"])
            df_t["norm"] = df_t["close"] / df_t["close"].iloc[0] * 100
            fig_comp.add_trace(go.Scatter(x=df_t["fecha"], y=df_t["norm"], name=t))
    fig_comp.update_layout(height=400,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        yaxis_title="Valor (base 100)")
    st.plotly_chart(fig_comp, use_container_width=True)

    st.divider()
    st.markdown("### 🕯️ Análisis Individual por Activo")

    for idx, t in enumerate(tickers):
        data_ind = cached_get(f"/analisis/indicadores/{t}")
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
        serie_box = st.session_state.get(f"rend_{t}", {}).get("serie")
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
        _key = f"rend_{_t}"
        if _key not in st.session_state:
            _data = {
                "stats": api_get(f"/analisis/rendimientos/{_t}"),
                "serie": api_get(f"/analisis/rendimientos-serie/{_t}"),
            }
            if _data["stats"] and _data["serie"]:
                st.session_state[_key] = _data

    # Acordeón por ticker
    st.markdown("### 📈 Análisis Individual por Activo")
    from scipy import stats as sp_stats

    for idx, t in enumerate(tickers):
        datos = st.session_state.get(f"rend_{t}")
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
                    line=dict(color="#A78BFA", width=0.8),
                    fill="tozeroy", fillcolor="rgba(167,139,250,0.1)",
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
                    name="Datos", marker=dict(color="#A5B4FC", size=3, opacity=0.7),
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
    cache_key_m3_all = f"vol_all_{'_'.join(tickers)}"
    if cache_key_m3_all not in st.session_state:
        with st.spinner("Calculando modelos EWMA y GARCH para todos los activos..."):
            resultados_vol = {}
            for t in tickers:
                safe_t = urllib.parse.quote(t, safe='')
                resultados_vol[t] = {
                    "ewma":    api_get(f"/analisis/ewma/{safe_t}"),
                    "garch":   api_get(f"/analisis/garch/{safe_t}"),
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
                    line=dict(color="rgba(167, 139, 250, 0.4)", width=0.8),
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

        cache_key_m4 = f"capm_{'-'.join(tickers)}_{benchmark}"
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
                    "tasa_libre_riesgo": rf_real
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
    cache_key_vp = f"var_portafolio_{confianza_var}"
    if cache_key_vp not in st.session_state:
        with st.spinner("Calculando VaR del portafolio..."):
            resultado_vp = api_get("/analisis/var-portafolio", params={"nivel": confianza_var})
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
        _key = f"var_{_t}_{confianza_var}"
        if _key not in st.session_state:
            safe_t = urllib.parse.quote(_t, safe='')
            _data = {
                "var":  api_get(f"/analisis/var/{safe_t}"),
                "rend": st.session_state.get(f"rend_{_t}", {}).get("stats") or api_get(f"/analisis/rendimientos/{safe_t}"),
            }
            if _data["var"] and _data["rend"]:
                st.session_state[_key] = _data

    def metric_var(label, val, cap):
        st.metric(label, f"{val*100:.4f}%",
                  delta=f"-${abs(val)*cap:,.0f}", delta_color="inverse")

    for idx, t in enumerate(tickers):
        cache_key_t = f"var_{t}_{confianza_var}"
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
    
    col_c1, col_c2 = st.columns(2)
    with col_c1:
        n_port = st.slider("Portafolios a simular (Fondo)", 1000, 30000, 5000, step=1000, key="m6_slider_n")
    with col_c2:
        # Aquí habilitamos el checkbox que envía la señal al backend y a la nube
        permitir_cortos = st.checkbox("Permitir ventas en corto", key="m6_cortos")
    
    cache_key_m6 = f"markowitz_{'-'.join(tickers)}_{permitir_cortos}"
    if st.button("🔄 Construir frontera eficiente", key="btn_markowitz"):
        if cache_key_m6 not in st.session_state:
            with st.spinner(f"Calculando línea matemática y simulando nube..."):
                data_m = api_get("/analisis/markowitz", params={"permitir_cortos": permitir_cortos})
                precios_dict = {}
                for t in tickers:
                    safe_t = urllib.parse.quote(t, safe='')
                    p_data = cached_get(f"/precios/{safe_t}")
                    if p_data and isinstance(p_data, list) and len(p_data) > 0:
                        df_p = pd.DataFrame(p_data)
                        df_p["fecha"] = pd.to_datetime(df_p["fecha"])
                        precios_dict[t] = df_p.set_index("fecha")["close"]
                st.session_state[cache_key_m6] = {
                    "data_m": data_m,
                    "precios_dict": precios_dict,
                }
            data_m = st.session_state.get(cache_key_m6, {}).get("data_m")
            precios_dict = st.session_state.get(cache_key_m6, {}).get("precios_dict", {})

            if len(precios_dict) < 2:
                st.error("⚠️ Se necesitan al menos 2 activos con historial de precios para simular.")
            elif data_m and "optimizacion" in data_m:
                opt = data_m["optimizacion"]
                frontera = pd.DataFrame(data_m.get("frontera", []))
                
                # Extraer tasa FRED localmente para el Sharpe de la nube
                rf_anual = 0.04
                try:
                    curva = api_get("/renta-fija/curva")
                    if curva and "datos_mercado" in curva:
                        rf_anual = curva["datos_mercado"]["tasas"][0] / 100
                except: pass

                st.success(f"✅ Optimización analítica completada. Rf usada: **{rf_anual * 100:.2f}%**")

                # 3. Preparar datos de rendimiento
                df_precios = pd.DataFrame(precios_dict)
                df_ret = np.log(df_precios / df_precios.shift(1)).dropna()
                
                # ── Matriz de Correlación ──
                st.markdown("#### 🔗 Matriz de correlación entre activos")
                corr_df = df_ret.corr()
                fig_corr = go.Figure(data=go.Heatmap(
                    z=corr_df.values, x=corr_df.columns.tolist(), y=corr_df.index.tolist(),
                    colorscale="RdBu", zmin=-1, zmax=1,
                    text=corr_df.round(2).values, texttemplate="%{text}", textfont={"size": 11},
                    colorbar=dict(title="Correlación"),
                ))
                try: fig_corr.update_layout(**plotly_layout("Correlación de rendimientos", height=350))
                except: fig_corr.update_layout(title="Correlación", height=350, template="plotly_dark")
                st.plotly_chart(fig_corr, use_container_width=True)
                st.divider()

                # 4. SIMULACIÓN DE MONTE CARLO (Solo para pintar la nube visual)
                mean_returns = df_ret.mean() * 252
                cov_matrix = df_ret.cov() * 252
                num_activos = len(tickers)
                
                resultados_sim = np.zeros((3, n_port))
                
                for i in range(n_port):
                    # Lógica para permitir o no ventas en corto en la nube
                    if permitir_cortos:
                        pesos = np.random.uniform(-1, 1.5, num_activos)
                        # Evitar divisiones por cero o apalancamientos locos
                        while abs(np.sum(pesos)) < 0.1:
                            pesos = np.random.uniform(-1, 1.5, num_activos)
                    else:
                        pesos = np.random.random(num_activos)
                        
                    pesos /= np.sum(pesos)
                    
                    retorno_port = np.sum(mean_returns * pesos)
                    std_port = np.sqrt(np.dot(pesos.T, np.dot(cov_matrix, pesos)))
                    sharpe_port = (retorno_port - rf_anual) / std_port
                    
                    resultados_sim[0, i] = std_port
                    resultados_sim[1, i] = retorno_port
                    resultados_sim[2, i] = sharpe_port

                # 5. GRÁFICO INTEGRADO (Nube + Línea + Puntos exactos)
                st.markdown("#### 📈 Frontera Eficiente y Conjunto Factible")
                fig_mk = go.Figure()

                # A. La nube generada aleatoriamente
                fig_mk.add_trace(go.Scatter(
                    x=resultados_sim[0] * 100, y=resultados_sim[1] * 100,
                    mode="markers", name="Simulación",
                    marker=dict(
                        color=resultados_sim[2], colorscale="Plasma", 
                        size=4, opacity=0.4, colorbar=dict(title="Sharpe"),
                    ),
                    hovertemplate="Riesgo: %{x:.2f}%<br>Retorno: %{y:.2f}%<br>Sharpe: %{marker.color:.4f}<extra></extra>"
                ))

                # B. La Línea Exacta (Calculada por tu backend)
                if not frontera.empty:
                    frontera_sorted = frontera.sort_values("riesgo")
                    fig_mk.add_trace(go.Scatter(
                        x=frontera_sorted["riesgo"] * 100,
                        y=frontera_sorted["retorno"] * 100,
                        mode="lines", name="Frontera Analítica",
                        line=dict(color="#ED1E79", width=4),
                    ))
                    
                    # Extraemos Mínima Varianza directo de la línea
                    min_var_row = frontera_sorted.iloc[0]
                    fig_mk.add_trace(go.Scatter(
                        x=[min_var_row["riesgo"] * 100], y=[min_var_row["retorno"] * 100],
                        mode="markers+text", name="Mín. Varianza 🔵",
                        text=["Mín. Varianza"], textposition="bottom right",
                        marker=dict(color="#38BDF8", size=12, symbol="diamond", line=dict(color="white", width=1)),
                    ))

                # C. El Óptimo Exacto (Calculado por tu backend)
                ms_retorno = opt["retorno_anual"]
                ms_riesgo = opt["riesgo_anual"]
                ms_sharpe = opt["sharpe_ratio"]
                
                fig_mk.add_trace(go.Scatter(
                    x=[ms_riesgo * 100], y=[ms_retorno * 100],
                    mode="markers+text", name="Máx. Sharpe ⭐",
                    text=["Máx. Sharpe"], textposition="top left",
                    marker=dict(color="gold", size=17, symbol="star", line=dict(color="black", width=1)),
                ))

                try:
                    fig_mk.update_layout(**plotly_layout(
                        "Modelo de Markowitz", height=550,
                        xaxis_title="Volatilidad anualizada (%)", yaxis_title="Rendimiento esperado (%)"
                    ))
                except:
                    fig_mk.update_layout(title="Frontera de Markowitz", height=550, template="plotly_dark")
                st.plotly_chart(fig_mk, use_container_width=True)

                # 6. MÉTRICAS FINALES
                col_ms, col_mv = st.columns(2)

                with col_ms:
                    st.markdown("#### ⭐ Portafolio Máximo Sharpe")
                    st.metric("Retorno | Riesgo", f"{ms_retorno*100:.2f}% | {ms_riesgo*100:.2f}%")
                    st.metric("Sharpe Ratio", f"{ms_sharpe:.4f}")
                    df_ms = pd.DataFrame(list(opt["pesos"].items()), columns=["Ticker", "Peso"])
                    fig_pie_ms = px.pie(df_ms, values="Peso", names="Ticker", hole=0.3)
                    try: fig_pie_ms.update_layout(**plotly_layout(height=320))
                    except: fig_pie_ms.update_layout(height=320, template="plotly_dark")
                    st.plotly_chart(fig_pie_ms, use_container_width=True)

                with col_mv:
                    st.markdown("#### 💰 Distribución de la inversión (Máx. Sharpe)")
                    st.info("Valores calculados analíticamente.")
                    for t, w in opt["pesos"].items():
                        # Si es venta en corto, el peso es negativo
                        signo = "" if w >= 0 else "🔴 Corto "
                        st.write(f"**{t}:** {w*100:.1f}% → **{signo}${w*valor_portafolio:,.0f}**")

                # ── Comparación fronteras con/sin cortos ──
                st.divider()
                st.markdown("#### 📊 Comparación: Con vs Sin No-Negatividad")
                with st.spinner("Calculando frontera con cortos..."):
                    data_cortos = api_get("/analisis/markowitz", params={"permitir_cortos": True})

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
                        fc = pd.DataFrame(frontera_cortos).sort_values("riesgo")
                        fig_comp.add_trace(go.Scatter(
                            x=fc["riesgo"] * 100, y=fc["retorno"] * 100,
                            mode="lines", name="Con cortos (wi ∈ ℝ)",
                            line=dict(color="#f59e0b", width=3, dash="dash"),
                        ))
                    try:
                        fig_comp.update_layout(**plotly_layout(
                            "Costo de la restricción de no negatividad", height=400,
                            xaxis_title="Volatilidad (%)", yaxis_title="Retorno (%)"))
                    except:
                        fig_comp.update_layout(title="Comparación fronteras", height=400)
                    st.plotly_chart(fig_comp, use_container_width=True)
                    
                    with st.expander("ℹ️ Interpretación"):
                        st.markdown("""
                        - **Sin cortos:** solo posiciones largas. Más conservador, menor universo factible.
                        - **Con cortos:** pesos negativos permitidos. Mayor flexibilidad, frontera más alta.
                        - El **costo de la restricción** es la diferencia vertical entre ambas fronteras.
                        """)

            else:
                st.error("⚠️ El backend no logró calcular la frontera eficiente. Verifica los logs de FastAPI.")

# ═══════════════════ TAB 7 — SEÑALES Y SEMÁFOROS ═══════════════════

with tabs[7]:
    st.subheader("🚦 Semáforo de Trading — Análisis Técnico")
    
    # 1. INYECCIÓN DE CSS PARA LAS TARJETAS DE SEÑAL
    st.markdown("""
        <style>
        .semaforo-verde {
            background-color: rgba(16,185,129,0.12);
            border: 1px solid #10b981;
            padding: 15px; border-radius: 10px; color: #ffffff !important;
        }
        .semaforo-rojo {
            background-color: rgba(239,68,68,0.12);
            border: 1px solid #ef4444;
            padding: 15px; border-radius: 10px; color: #ffffff !important;
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

    if st.button("🔄 Cargar datos macro y benchmark", key="btn_m8"):
        with st.spinner("Consultando FRED y calculando métricas..."):
            data_macro = api_get("/macro/")
            data_bench = api_get("/macro/benchmark", params={"benchmark": benchmark})

        if data_macro:
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Tasa Libre de Riesgo (FRED)", f"{data_macro['tasa_libre_riesgo']*100:.2f}%")
            with col2:
                st.metric("Inflación Anual USA (FRED)", f"{data_macro['inflacion_anual_pct']:.2f}%")

            curva = data_macro["curva"]
            df_curva = pd.DataFrame({"Plazo (años)": curva["plazos"], "Tasa (%)": curva["tasas"]})
            fig_c = px.line(df_curva, x="Plazo (años)", y="Tasa (%)",
                            title="Curva de Rendimiento USA (FRED)", markers=True)
            st.plotly_chart(fig_c, use_container_width=True)

        if data_bench:
            st.markdown(f"### 📊 Desempeño vs {benchmark}")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Tracking Error", f"{data_bench['tracking_error']*100:.2f}%")
            c2.metric("Information Ratio", f"{data_bench['information_ratio']:.4f}")
            c3.metric("Max Drawdown", f"{data_bench['max_drawdown']*100:.2f}%")
            c4.metric("Sharpe Portafolio", f"{data_bench['sharpe_portafolio']:.4f}")

            col1, col2 = st.columns(2)
            with col1:
                st.metric("Retorno Acumulado Portafolio",
                          f"{data_bench['retorno_acumulado_portafolio']*100:.2f}%")
            with col2:
                st.metric(f"Retorno Acumulado {benchmark}",
                          f"{data_bench['retorno_acumulado_benchmark']*100:.2f}%")

            with st.expander("ℹ️ Interpretación"):
                st.markdown(f"""
                - **Tracking Error:** desviación del portafolio respecto al benchmark. Menor = más alineado.
                - **Information Ratio:** exceso de retorno por unidad de tracking error. Mayor = mejor gestión activa.
                - **Max Drawdown:** mayor caída desde un pico. Mide el peor escenario histórico.
                - **Alpha de Jensen:** ver módulo CAPM para el alpha ajustado por riesgo.
                """)

# ═══════════════════ MÓD 9 — RENTA FIJA ═══════════════════

with tabs[9]:
    st.subheader("📐 Renta Fija — Duración y Convexidad")
    
    with st.container(border=True):
        c1, c2, c3 = st.columns(3)
        tasa_cupon = c1.number_input("Tasa Cupón (anual)", value=0.05, step=0.01, format="%.2f")
        vencimiento = c2.number_input("Vencimiento (años)", value=10, min_value=1, max_value=30)
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

    # 1. Aseguramos que la tasa fred exista (definición local por seguridad)
    tasa_fred_local = 0.04 
    try:
        curva_opt = api_get("/renta-fija/curva")
        if curva_opt and "datos_mercado" in curva_opt:
            tasa_fred_local = list(curva_opt["datos_mercado"]["tasas"])[0] / 100
    except:
        pass

    with st.container(border=True):
        c1, c2, c3, c4, c5 = st.columns(5)
        S = c1.number_input("Precio Spot (S)", value=100.0, step=5.0)
        K = c2.number_input("Strike (K)", value=100.0, step=5.0)
        T = c3.number_input("Años (T)", value=1.0, step=0.1)
        # Usamos la tasa detectada
        r_opt = c4.number_input("Tasa (r)", value=tasa_fred_local, format="%.4f")
        sigma = c5.number_input("Volatilidad (σ)", value=0.20, step=0.05)

    if st.button("🔄 Calcular Griegas y Precios", key="btn_m10"):
        with st.spinner("Calculando..."):
            data_bs = api_get("/opciones/black-scholes", params={"S": S, "K": K, "T": T, "r": r_opt, "sigma": sigma})
        
        if data_bs:
            col1, col2 = st.columns([1, 1.5])
            with col1:
                st.markdown("### 💲 Primas")
                st.metric("Call Price", f"${data_bs['precios']['call']:.4f}")
                st.metric("Put Price", f"${data_bs['precios']['put']:.4f}")
                
                st.markdown("### 📊 Griegas")
                g = data_bs["greeks"]
                ga, gb = st.columns(2)
                ga.write(f"**Delta:** {g['delta_call']:.3f}")
                ga.write(f"**Gamma:** {g['gamma']:.5f}")
                gb.write(f"**Vega:** {g['vega']:.3f}")
                gb.write(f"**Theta:** {g['theta_call']:.3f}")

            # ── AQUÍ ESTÁ EL CAMBIO DE COLOR Y ESTÉTICA ──
            with col2:
                st.markdown("### 📈 Perfil de Beneficios")
                st_range = np.linspace(S*0.5, S*1.5, 50)
                payoff_call = np.maximum(st_range - K, 0) - data_bs['precios']['call']
                payoff_put = np.maximum(K - st_range, 0) - data_bs['precios']['put']
                
                fig_opt = go.Figure()

                # Call en Cian con Relleno
                fig_opt.add_trace(go.Scatter(
                    x=st_range, y=payoff_call, 
                    name="Long Call", 
                    line=dict(color="#00f2ff", width=3),
                    fill='tozeroy', 
                    fillcolor='rgba(0, 242, 255, 0.1)'
                ))

                # Put en Rosa con Relleno
                fig_opt.add_trace(go.Scatter(
                    x=st_range, y=payoff_put, 
                    name="Long Put", 
                    line=dict(color="#ED1E79", width=3),
                    fill='tozeroy',
                    fillcolor='rgba(237, 30, 121, 0.1)'
                ))

                # Línea de equilibrio
                fig_opt.add_hline(y=0, line_color="#94a3b8", line_width=1, line_dash="dash")
                
                # --- SOLUCIÓN AL ERROR: Aplicamos el layout en dos pasos ---
                
                # Paso 1: Aplicamos el diseño base de tu función maestra
                fig_opt.update_layout(
                    **plotly_layout(
                        "Perfil de Beneficios al Vencimiento", 
                        height=400, 
                        xaxis_title="Precio Activo Subyacente", 
                        yaxis_title="Pérdida / Ganancia"
                    )
                )
                
                # Paso 2: Aplicamos los ajustes de color que querías sin repetir el nombre del parámetro
                fig_opt.update_layout(
                    title_font=dict(color='#CBD5E1', size=20), # Color de título mejorado
                    xaxis=dict(title_font=dict(color='#94a3b8'), gridcolor="#334155"),
                    yaxis=dict(title_font=dict(color='#94a3b8'), gridcolor="#334155")
                )
                
                st.plotly_chart(fig_opt, use_container_width=True)

                st.divider()
            st.markdown("### 📊 Visualizaciones")
            
            spots = np.linspace(S * 0.5, S * 1.5, 100)
            
            col1, col2 = st.columns(2)
            
            # 1. Payoff a vencimiento
            with col1:
                payoff_call = np.maximum(spots - K, 0)
                payoff_put = np.maximum(K - spots, 0)
                fig_payoff = go.Figure()
                fig_payoff.add_trace(go.Scatter(x=spots, y=payoff_call, name="Call", line=dict(color="#10b981", width=2)))
                fig_payoff.add_trace(go.Scatter(x=spots, y=payoff_put, name="Put", line=dict(color="#ef4444", width=2)))
                fig_payoff.add_vline(x=K, line_dash="dash", annotation_text=f"K={K}")
                fig_payoff.update_layout(title="Payoff a Vencimiento", xaxis_title="Precio Spot", yaxis_title="Payoff ($)", height=320)
                st.plotly_chart(fig_payoff, use_container_width=True)

            # 2. Precio de la opción hoy vs spot
            with col2:
                from scipy.stats import norm as sp_norm
                precios_call = []
                for s in spots:
                    if s <= 0: precios_call.append(0); continue
                    d1 = (np.log(s/K) + (r_opt + sigma**2/2)*T) / (sigma*np.sqrt(T))
                    d2 = d1 - sigma*np.sqrt(T)
                    precios_call.append(s*sp_norm.cdf(d1) - K*np.exp(-r_opt*T)*sp_norm.cdf(d2))
                intrinseco = np.maximum(spots - K, 0)
                fig_precio = go.Figure()
                fig_precio.add_trace(go.Scatter(x=spots, y=precios_call, name="Precio Call BS", line=dict(color="#6366f1", width=2)))
                fig_precio.add_trace(go.Scatter(x=spots, y=intrinseco, name="Valor Intrínseco", line=dict(dash="dot", color="#f59e0b")))
                fig_precio.add_vline(x=S, line_dash="dash", annotation_text=f"S actual={S}")
                fig_precio.update_layout(title="Precio Call vs Spot", xaxis_title="Precio Spot", yaxis_title="Precio ($)", height=320)
                st.plotly_chart(fig_precio, use_container_width=True)

            # 3. Delta vs Spot para distintos T
            fig_delta = go.Figure()
            for t_val, color in [(0.25, "#ef4444"), (0.5, "#f59e0b"), (1.0, "#10b981"), (2.0, "#6366f1")]:
                deltas = []
                for s in spots:
                    if s <= 0: deltas.append(0); continue
                    d1 = (np.log(s/K) + (r_opt + sigma**2/2)*t_val) / (sigma*np.sqrt(t_val))
                    deltas.append(sp_norm.cdf(d1))
                fig_delta.add_trace(go.Scatter(x=spots, y=deltas, name=f"T={t_val}a", line=dict(color=color, width=2)))
            fig_delta.add_vline(x=K, line_dash="dash", annotation_text=f"K={K}")
            fig_delta.update_layout(title="Delta Call vs Spot (distintos T)", xaxis_title="Precio Spot", yaxis_title="Delta", height=350)
            st.plotly_chart(fig_delta, use_container_width=True)



# ═══════════════════ MÓD 11 — STRESS ═══════════════════

with tabs[11]:
    st.subheader("💥 Análisis de Escenarios Extremos (Stress Test)")
    st.warning("Evaluación del impacto del portafolio ante eventos de 'Cisne Negro' históricos y catastróficos.")
    
    if st.button("🔄 Ejecutar Simulación de Crisis", key="btn_m11"):
        if "stress_test" not in st.session_state:
            with st.spinner("Ejecutando simulación de crisis..."):
                st.session_state["stress_test"] = api_get("/analisis/stress-test")
        data_st = st.session_state.get("stress_test")    

        if data_st:
            # 1. Gráfico de Impacto Global
            df_st = pd.DataFrame(data_st["escenarios"])
            df_st["Impacto USD"] = df_st["impacto_portafolio"] * valor_portafolio
            
            fig_st = px.bar(df_st, x="escenario", y="Impacto USD", color="impacto_portafolio",
                           color_continuous_scale="RdYlGn", title="Impacto Monetario por Escenario")
            st.plotly_chart(fig_st, use_container_width=True)

            # 2. Tarjetas Detalladas
            st.markdown("#### 🚨 Detalle de Supervivencia")
            grid = st.columns(3)
            for i, esc in enumerate(data_st["escenarios"]):
                with grid[i % 3]:
                    impacto_pct = esc["impacto_portafolio"] * 100
                    impacto_usd = esc["impacto_portafolio"] * valor_portafolio
                    
                    # Estilo según gravedad
                    bg_color = "rgba(239,68,68,0.1)" if impacto_pct < -5 else "rgba(245,158,11,0.1)"
                    border_color = "#ef4444" if impacto_pct < -5 else "#f59e0b"
                    
                    st.markdown(f"""
                        <div style="background:{bg_color}; border: 1px solid {border_color}; padding: 15px; border-radius: 10px;">
                            <h4 style="margin:0; font-size:14px;">{esc['escenario']}</h4>
                            <p style="font-size:24px; font-weight:bold; margin:5px 0;">{impacto_pct:.2f}%</p>
                            <p style="margin:0; color:{border_color};">Impacto: -${abs(impacto_usd):,.0f}</p>
                        </div>
                    """, unsafe_allow_html=True)
                    st.write("") # Espaciador
            
            # Heatmap activo × escenario
            st.markdown("#### 🗺️ Heatmap de Sensibilidad: Activo × Escenario")
            escenarios = data_st["escenarios"]
            nombres_esc = [e["escenario"] for e in escenarios]
            activos_hm = list(escenarios[0].get("impactos_por_activo", {}).keys()) if escenarios else []
                
            if activos_hm:
                matriz = [[e.get("impactos_por_activo", {}).get(a, 0) * 100 for e in escenarios] for a in activos_hm]
                fig_hm = go.Figure(data=go.Heatmap(
                    z=matriz, x=nombres_esc, y=activos_hm,
                    colorscale="RdYlGn", zmid=0,
                    text=[[f"{v:.1f}%" for v in row] for row in matriz],
                    texttemplate="%{text}", colorbar=dict(title="Impacto %"),
                ))
                fig_hm.update_layout(title="Impacto % por Activo y Escenario", height=350)
                st.plotly_chart(fig_hm, use_container_width=True)


# ═══════════════════ ML ═══════════════════

with tabs[12]:
    st.subheader("🤖 Inteligencia Artificial — Predicción de Tendencia")
    
    with st.container(border=True):
        col1, col2 = st.columns([1, 1.5])
        
        with col1:
            st.markdown("### 🏋️ Entrenamiento")
            ticker_ml = st.selectbox("Activo a entrenar", tickers, key="ml_t")
            if st.button("Entrenar Modelo RF", key="btn_ml_t", use_container_width=True):
                with st.spinner("Entrenando Random Forest..."):
                    d = api_post(f"/ml/entrenar/{ticker_ml}")
                if d: 
                    st.success(f"Modelo Entrenado")
                    st.metric("Precisión (Accuracy)", f"{d['accuracy']:.2%}")

        with col2:
            st.markdown("### 🔮 Predicción")
            ticker_p = st.selectbox("Activo a predecir", tickers, key="ml_p")
            if st.button("Ejecutar Predicción", key="btn_ml_p", use_container_width=True):
                d = api_post(f"/ml/predecir/{ticker_p}")
                if d:
                    prob = d['probabilidad']
                    label = d['direccion'].upper()
                    color = "#10b981" if label == "SUBE" else "#ef4444"
                    
                    # Gráfico de Gauge (Velocímetro)
                    fig_gauge = go.Figure(go.Indicator(
                        mode = "gauge+number",
                        value = prob * 100,
                        domain = {'x': [0, 1], 'y': [0, 1]},
                        title = {'text': f"Confianza en: {label}"},
                        gauge = {
                            'axis': {'range': [0, 100]},
                            'bar': {'color': color},
                            'steps': [
                                {'range': [0, 50], 'color': "lightgray"},
                                {'range': [50, 100], 'color': "gray"}
                            ]
                        }
                    ))
                    fig_gauge.update_layout(height=300, margin=dict(l=20, r=20, t=50, b=20))
                    st.plotly_chart(fig_gauge, use_container_width=True)

    with st.expander("🧠 ¿Cómo funciona este modelo?"):
        st.markdown("""
        Este módulo utiliza un algoritmo de **Random Forest Classifier**. 
        - **Entradas:** Precios históricos, volumen e indicadores técnicos (RSI, Medias Móviles).
        - **Salida:** Clasifica si el precio de cierre de mañana será superior (**Sube**) o inferior (**Baja**) al de hoy.
        - **Probabilidad:** Indica qué tan seguro está el modelo de su decisión.
        """)


# ═══════════════════ AGENTE IA ═══════════════════

with tabs[13]:
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
                    resp = api_post("/agente/chat", {
                        "pregunta": pregunta,
                        "contexto": contexto_port,
                    })
                if resp:
                    st.markdown(resp["respuesta"])
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": resp["respuesta"],
                    })