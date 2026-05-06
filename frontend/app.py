"""
frontend/app.py — RiskLab USTA Dashboard CIII
Consume los endpoints del backend FastAPI.
Correr: streamlit run frontend/app.py
"""

import requests
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px

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
    .stTabs [data-baseweb="tab-list"] { gap: 4px; }
    .stTabs [data-baseweb="tab"] { border-radius: 8px 8px 0 0; padding: 8px 16px; font-weight: 600; font-size: 0.82rem; }
</style>
""", unsafe_allow_html=True)

API = "http://127.0.0.1:8000"

# ═══════════════════ HELPERS ═══════════════════

def api_get(ep, params=None):
    try:
        r = requests.get(f"{API}{ep}", params=params, timeout=120); r.raise_for_status(); return r.json()
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

def descargar_si_no_existe(ticker):
    """Descarga precios si no existen en BD."""
    r = api_get(f"/precios/{ticker}")
    if r is not None and len(r) == 0:
        api_post(f"/precios/descargar/{ticker}")

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

# ═══════════════════ TABS ═══════════════════

tabs = st.tabs([
    "🎯 Contexto", "📈 1. Técnico", "📉 2. Rendimientos", "🌊 3. Volatilidad",
    "🎯 4. CAPM", "🛡️ 5. VaR/CVaR", "⚡ 6. Markowitz",
    "🚦 7. Señales", "🌐 8. Macro", "📐 9. Renta Fija",
    "🧮 10. Opciones", "💥 11. Stress", "🤖 ML",
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

    # Descargar todos los tickers
    with st.spinner("Descargando precios de todos los activos..."):
        for t in tickers:
            descargar_si_no_existe(t)

    # Comparación de todos
    st.markdown("### Rendimiento comparado — Todos los activos (Base 100)")
    fig_comp = go.Figure()
    for t in tickers:
        r_p = api_get(f"/precios/{t}")
        if r_p and len(r_p) > 0:
            df_t = pd.DataFrame(r_p)
            df_t["fecha"] = pd.to_datetime(df_t["fecha"])
            df_t["norm"] = df_t["close"] / df_t["close"].iloc[0] * 100
            fig_comp.add_trace(go.Scatter(x=df_t["fecha"], y=df_t["norm"], name=t))
    fig_comp.update_layout(height=400, legend=dict(orientation="h", yanchor="bottom", y=1.02),
                           yaxis_title="Valor (base 100)")
    st.plotly_chart(fig_comp, use_container_width=True)

    st.divider()
    st.markdown(f"### Análisis individual — {ticker_sel}")

    # Velas japonesas
    r_precios = api_get(f"/precios/{ticker_sel}")
    if r_precios and len(r_precios) > 0:
        df_p = pd.DataFrame(r_precios)
        df_p["fecha"] = pd.to_datetime(df_p["fecha"])
        fig_velas = go.Figure(data=go.Candlestick(
            x=df_p["fecha"], open=df_p["open"], high=df_p["high"],
            low=df_p["low"], close=df_p["close"]))
        fig_velas.update_layout(title=f"Velas Japonesas — {ticker_sel}",
                                 xaxis_rangeslider_visible=False, height=400)
        st.plotly_chart(fig_velas, use_container_width=True)

    # Indicadores
    data_ind = api_get(f"/analisis/indicadores/{ticker_sel}")
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
        fig.update_layout(title=f"Indicadores — {ticker_sel}", height=420,
                          legend=dict(orientation="h", yanchor="bottom", y=1.02))
        st.plotly_chart(fig, use_container_width=True)

        col1, col2 = st.columns(2)
        with col1:
            fig_rsi = go.Figure()
            fig_rsi.add_trace(go.Scatter(x=df.index, y=df["rsi"], name="RSI", line=dict(color="#6366F1", width=2)))
            fig_rsi.add_hline(y=70, line_dash="dash", line_color="red", annotation_text="Sobrecompra")
            fig_rsi.add_hline(y=30, line_dash="dash", line_color="green", annotation_text="Sobreventa")
            fig_rsi.update_layout(title="RSI (14)", height=250, yaxis=dict(range=[0, 100]))
            st.plotly_chart(fig_rsi, use_container_width=True)
        with col2:
            fig_macd = go.Figure()
            fig_macd.add_trace(go.Scatter(x=df.index, y=df["macd"], name="MACD"))
            fig_macd.add_trace(go.Scatter(x=df.index, y=df["macd_signal"], name="Señal"))
            colors = ["green" if v >= 0 else "red" for v in df["macd_histograma"].fillna(0)]
            fig_macd.add_trace(go.Bar(x=df.index, y=df["macd_histograma"], marker_color=colors, opacity=0.6, name="Hist"))
            fig_macd.update_layout(title="MACD", height=250)
            st.plotly_chart(fig_macd, use_container_width=True)

        fig_stoch = go.Figure()
        fig_stoch.add_trace(go.Scatter(x=df.index, y=df["stochastic_k"], name="%K"))
        fig_stoch.add_trace(go.Scatter(x=df.index, y=df["stochastic_d"], name="%D"))
        fig_stoch.add_hline(y=80, line_dash="dash", line_color="red")
        fig_stoch.add_hline(y=20, line_dash="dash", line_color="green")
        fig_stoch.update_layout(title="Estocástico", height=250, yaxis=dict(range=[0, 100]))
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
    ticker_r = st.selectbox("Activo", tickers, key="m2_ticker")

    with st.spinner("Calculando rendimientos..."):
        data_r = api_get(f"/analisis/rendimientos/{ticker_r}")

    if data_r:
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Media diaria", f"{data_r['media_diaria']*100:.4f}%")
        c2.metric("Vol. diaria", f"{data_r['std_diaria']*100:.4f}%")
        c3.metric("Asimetría", f"{data_r['asimetria']:.3f}")
        c4.metric("Curtosis", f"{data_r['curtosis']:.3f}")
        c5.metric("Observaciones", data_r["n_observaciones"])

        col1, col2 = st.columns(2)
        with col1:
            st.metric("Media anualizada", f"{data_r['media_anual']*100:.2f}%")
            st.metric("Volatilidad anualizada", f"{data_r['std_anual']*100:.2f}%")
        with col2:
            jb, sw = data_r["jarque_bera"], data_r["shapiro_wilk"]
            st.metric("Jarque-Bera p-value", f"{jb['p_value']:.6f}",
                      delta="Normal ✅" if jb["es_normal"] else "No normal ⚠️",
                      delta_color="normal" if jb["es_normal"] else "inverse")
            st.metric("Shapiro-Wilk p-value", f"{sw['p_value']:.6f}",
                      delta="Normal ✅" if sw["es_normal"] else "No normal ⚠️",
                      delta_color="normal" if sw["es_normal"] else "inverse")

        with st.expander("ℹ️ Hechos estilizados"):
            st.markdown("""
            - **Colas pesadas:** curtosis > 3 → más eventos extremos que la normal
            - **Agrupamiento de volatilidad:** períodos agitados se suceden
            - **Asimetría negativa:** caídas más pronunciadas que subidas
            - **No normalidad:** Jarque-Bera y Shapiro-Wilk rechazan normalidad → justifica GARCH y VaR histórico
            """)


# ═══════════════════ MÓD 3 — VOLATILIDAD ═══════════════════

with tabs[3]:
    st.subheader("🌊 Volatilidad — EWMA + GARCH")
    if st.button("🔄 Calcular volatilidad", key="btn_m3"):
        with st.spinner("Ajustando modelos..."):
            ewma = api_get(f"/analisis/ewma/{ticker_sel}")
            garch = api_get(f"/analisis/garch/{ticker_sel}")
        if ewma and garch:
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("### EWMA")
                st.metric("Volatilidad EWMA Anual", f"{ewma['volatilidad_ewma']:.4f}")
                st.info("Lambda = 0.94 (estándar RiskMetrics). Da más peso a datos recientes.")
            with col2:
                st.markdown("### GARCH")
                st.metric("Modelo", garch.get("orden", "N/A"))
                c1, c2 = st.columns(2)
                c1.metric("AIC", garch.get("aic", "N/A"))
                c2.metric("BIC", garch.get("bic", "N/A"))
                st.metric("Persistencia", garch.get("persistencia", "N/A"))
                st.info("Se prueban GARCH(1,1), (1,2), (2,1), (2,2) y se elige por menor AIC.")


# ═══════════════════ MÓD 4 — CAPM ═══════════════════

with tabs[4]:
    st.subheader("🎯 CAPM y Beta")
    st.info("El CAPM compara el rendimiento del activo vs el benchmark para determinar "
            "si genera valor por encima del riesgo asumido.")
    st.warning("⚠️ Módulo CAPM en desarrollo — requiere sincronización de rendimientos con el benchmark.")


# ═══════════════════ MÓD 5 — VaR ═══════════════════

with tabs[5]:
    st.subheader("🛡️ Value at Risk y CVaR")
    ticker_v = st.selectbox("Activo", tickers, key="m5_ticker")

    with st.spinner("Calculando VaR..."):
        data_v = api_get(f"/analisis/var/{ticker_v}")

    if data_v:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("VaR Paramétrico", f"{data_v['var_parametrico']:.6f}",
                  delta=f"-${abs(data_v['var_parametrico'])*valor_portafolio:,.0f}")
        c2.metric("VaR Histórico", f"{data_v['var_historico']:.6f}",
                  delta=f"-${abs(data_v['var_historico'])*valor_portafolio:,.0f}")
        c3.metric("VaR Monte Carlo", f"{data_v['var_montecarlo']:.6f}",
                  delta=f"-${abs(data_v['var_montecarlo'])*valor_portafolio:,.0f}")
        c4.metric("CVaR", f"{data_v['cvar']:.6f}",
                  delta=f"-${abs(data_v['cvar'])*valor_portafolio:,.0f}")

        fig = go.Figure()
        nombres = ["Paramétrico", "Histórico", "Monte Carlo", "CVaR"]
        valores = [data_v["var_parametrico"], data_v["var_historico"], data_v["var_montecarlo"], data_v["cvar"]]
        fig.add_trace(go.Bar(x=nombres, y=valores, marker_color=["#636EFA", "#EF553B", "#00CC96", "#AB63FA"]))
        fig.update_layout(title=f"VaR — {ticker_v} (conf. {confianza_var:.0%})", yaxis_title="Pérdida diaria", height=350)
        st.plotly_chart(fig, use_container_width=True)

        with st.expander("ℹ️ Interpretación"):
            st.markdown(f"""
            Con **${valor_portafolio:,.0f}** al **{confianza_var:.0%}** de confianza:
            - **VaR Paramétrico:** peor pérdida diaria ≈ **${abs(data_v['var_parametrico'])*valor_portafolio:,.0f}**
            - **CVaR:** si se supera el VaR, pérdida promedio ≈ **${abs(data_v['cvar'])*valor_portafolio:,.0f}**
            """)


# ═══════════════════ MÓD 6 — MARKOWITZ ═══════════════════

with tabs[6]:
    st.subheader("⚡ Optimización — Markowitz")
    permitir_cortos = st.checkbox("Permitir ventas en corto", key="m6_cortos")
    if st.button("🔄 Optimizar portafolio", key="btn_m6"):
        with st.spinner("Optimizando..."):
            data_m = api_get("/analisis/markowitz", params={"permitir_cortos": permitir_cortos})
        if data_m:
            opt = data_m["optimizacion"]
            c1, c2, c3 = st.columns(3)
            c1.metric("Retorno Anual", f"{opt['retorno_anual']*100:.2f}%")
            c2.metric("Riesgo Anual", f"{opt['riesgo_anual']*100:.2f}%")
            c3.metric("Sharpe Ratio", f"{opt['sharpe_ratio']:.4f}")

            col_a, col_b = st.columns(2)
            with col_a:
                fig_p = px.pie(names=list(opt["pesos"].keys()), values=list(opt["pesos"].values()), title="Pesos Óptimos")
                st.plotly_chart(fig_p, use_container_width=True)
            with col_b:
                frontera = pd.DataFrame(data_m["frontera"])
                if not frontera.empty:
                    fig_f = px.scatter(frontera, x="riesgo", y="retorno", title="Frontera Eficiente")
                    fig_f.add_scatter(x=[opt["riesgo_anual"]], y=[opt["retorno_anual"]],
                                      mode="markers", marker=dict(size=14, color="red", symbol="star"), name="Óptimo")
                    st.plotly_chart(fig_f, use_container_width=True)

            st.markdown("#### 💰 Distribución de la inversión")
            for t, w in opt["pesos"].items():
                st.write(f"**{t}:** {w*100:.1f}% → **${w*valor_portafolio:,.0f}**")


# ═══════════════════ MÓD 7 — SEÑALES ═══════════════════

with tabs[7]:
    st.subheader("🚦 Señales de Trading — Todos los activos")

    for t in tickers:
        data_s = api_get(f"/analisis/indicadores/{t}")
        if data_s:
            df_s = pd.DataFrame(data_s["indicadores"]).T
            if len(df_s) == 0:
                continue
            ultimo = df_s.iloc[-1]
            señales = []

            if ultimo["rsi"] > 70: señales.append(("RSI", "🔴 VENTA", f"RSI={ultimo['rsi']:.1f}"))
            elif ultimo["rsi"] < 30: señales.append(("RSI", "🟢 COMPRA", f"RSI={ultimo['rsi']:.1f}"))
            else: señales.append(("RSI", "🟡 NEUTRAL", f"RSI={ultimo['rsi']:.1f}"))

            if ultimo["close"] > ultimo["bollinger_upper"]: señales.append(("Bollinger", "🔴 VENTA", "Sobre banda sup"))
            elif ultimo["close"] < ultimo["bollinger_lower"]: señales.append(("Bollinger", "🟢 COMPRA", "Bajo banda inf"))
            else: señales.append(("Bollinger", "🟡 NEUTRAL", "Dentro de bandas"))

            if ultimo["macd"] > ultimo["macd_signal"]: señales.append(("MACD", "🟢 COMPRA", "MACD > señal"))
            else: señales.append(("MACD", "🔴 VENTA", "MACD < señal"))

            if ultimo["stochastic_k"] > 80: señales.append(("Estocástico", "🔴 VENTA", f"%K={ultimo['stochastic_k']:.1f}"))
            elif ultimo["stochastic_k"] < 20: señales.append(("Estocástico", "🟢 COMPRA", f"%K={ultimo['stochastic_k']:.1f}"))
            else: señales.append(("Estocástico", "🟡 NEUTRAL", f"%K={ultimo['stochastic_k']:.1f}"))

            compras = sum(1 for s in señales if "COMPRA" in s[1])
            ventas = sum(1 for s in señales if "VENTA" in s[1])
            if compras > ventas: emoji, resumen = "🟢", "COMPRA"
            elif ventas > compras: emoji, resumen = "🔴", "VENTA"
            else: emoji, resumen = "🟡", "NEUTRAL"

            st.markdown(f"### {emoji} {t} — {resumen}")
            df_sen = pd.DataFrame(señales, columns=["Indicador", "Señal", "Detalle"])
            st.dataframe(df_sen.set_index("Indicador"), use_container_width=True)
            st.divider()


# ═══════════════════ MÓD 8 — MACRO ═══════════════════

with tabs[8]:
    st.subheader("🌐 Contexto Macroeconómico")
    if st.button("🔄 Cargar datos FRED", key="btn_m8"):
        with st.spinner("Consultando FRED..."):
            data_c = api_get("/renta-fija/curva")
        if data_c:
            datos = data_c["datos_mercado"]
            df_curva = pd.DataFrame({"Plazo (años)": datos["plazos"], "Tasa (%)": datos["tasas"]})
            fig = px.line(df_curva, x="Plazo (años)", y="Tasa (%)",
                          title="Curva de Rendimiento USA (FRED)", markers=True)
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(df_curva, use_container_width=True)
            with st.expander("ℹ️ Interpretación"):
                st.markdown("""
                - **Pendiente positiva:** economía estable
                - **Invertida:** señal de recesión
                - **Plana:** incertidumbre
                """)


# ═══════════════════ MÓD 9 — RENTA FIJA ═══════════════════

with tabs[9]:
    st.subheader("📐 Renta Fija — Duración y Convexidad")
    c1, c2 = st.columns(2)
    tasa_cupon = c1.number_input("Tasa Cupón", value=0.05, step=0.01, format="%.2f")
    vencimiento = c2.number_input("Vencimiento (años)", value=10, min_value=1, max_value=30)
    if st.button("🔄 Calcular", key="btn_m9"):
        with st.spinner("Calculando..."):
            data_rf = api_get("/renta-fija/duracion", params={"tasa_cupon": tasa_cupon, "vencimiento": vencimiento})
        if data_rf:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Precio Bono", f"${data_rf['precio_bono']:.2f}")
            c2.metric("Duración", f"{data_rf['duracion']:.4f} años")
            c3.metric("Convexidad", f"{data_rf['convexidad']:.4f}")
            c4.metric("Tasa descuento", f"{data_rf['tasa_descuento']:.4%}")


# ═══════════════════ MÓD 10 — OPCIONES ═══════════════════

with tabs[10]:
    st.subheader("🧮 Opciones — Black-Scholes")

    # Intentar traer tasa FRED
    tasa_fred = 0.04
    try:
        curva = api_get("/renta-fija/curva")
        if curva:
            tasa_fred = curva["datos_mercado"]["tasas"][0] / 100
    except:
        pass

    c1, c2, c3, c4, c5 = st.columns(5)
    S = c1.number_input("Spot (S)", value=100.0, step=5.0)
    K = c2.number_input("Strike (K)", value=100.0, step=5.0)
    T = c3.number_input("Tiempo (T)", value=1.0, step=0.1)
    r_opt = c4.number_input("Tasa (r)", value=round(tasa_fred, 4), step=0.01, format="%.4f",
                             help=f"Tasa FRED actual: {tasa_fred:.4f}")
    sigma = c5.number_input("Vol (σ)", value=0.20, step=0.05, format="%.2f")

    if st.button("🔄 Calcular Black-Scholes", key="btn_m10"):
        with st.spinner("Calculando..."):
            data_bs = api_get("/opciones/black-scholes", params={"S": S, "K": K, "T": T, "r": r_opt, "sigma": sigma})
        if data_bs:
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("### 💲 Precios")
                a, b = st.columns(2)
                a.metric("Call", f"${data_bs['precios']['call']:.4f}")
                b.metric("Put", f"${data_bs['precios']['put']:.4f}")
            with col2:
                st.markdown("### 📊 Greeks")
                g = data_bs["greeks"]
                a, b, c = st.columns(3)
                a.metric("Delta Call", f"{g['delta_call']:.4f}")
                a.metric("Delta Put", f"{g['delta_put']:.4f}")
                b.metric("Gamma", f"{g['gamma']:.6f}")
                b.metric("Vega", f"{g['vega']:.4f}")
                c.metric("Theta", f"{g['theta_call']:.4f}")
                c.metric("Rho", f"{g['rho_call']:.4f}")


# ═══════════════════ MÓD 11 — STRESS ═══════════════════

with tabs[11]:
    st.subheader("💥 Stress Testing")
    if st.button("🔄 Ejecutar Stress Test", key="btn_m11"):
        with st.spinner("Simulando..."):
            data_st = api_get("/analisis/stress-test")
        if data_st:
            for esc in data_st["escenarios"]:
                usd = esc["impacto_portafolio"] * valor_portafolio
                if esc["impacto_portafolio"] < 0:
                    st.error(f"🔴 **{esc['escenario']}** → {esc['impacto_portafolio']:.4f} (**-${abs(usd):,.0f}**)")
                else:
                    st.warning(f"🟡 **{esc['escenario']}** → {esc['impacto_portafolio']:.4f} (**${usd:,.0f}**)")
            df_st = pd.DataFrame(data_st["escenarios"])
            fig = px.bar(df_st, x="escenario", y="impacto_portafolio", color="tipo", title="Impacto por Escenario")
            st.plotly_chart(fig, use_container_width=True)


# ═══════════════════ ML ═══════════════════

with tabs[12]:
    st.subheader("🤖 Machine Learning — Predicción")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### 🏋️ Entrenar")
        ticker_ml = st.selectbox("Ticker", tickers if tickers else ["AAPL"], key="ml_t")
        if st.button("Entrenar Random Forest", key="btn_ml_t"):
            with st.spinner("Entrenando..."):
                d = api_post(f"/ml/entrenar/{ticker_ml}")
            if d: st.success(f"✅ Accuracy: {d['accuracy']:.4f}")
    with col2:
        st.markdown("### 🔮 Predecir")
        ticker_p = st.selectbox("Ticker", tickers if tickers else ["AAPL"], key="ml_p")
        if st.button("Predecir dirección", key="btn_ml_p"):
            with st.spinner("Prediciendo..."):
                d = api_post(f"/ml/predecir/{ticker_p}")
            if d:
                emoji = "📈" if d["direccion"] == "sube" else "📉"
                st.metric("Predicción", f"{emoji} {d['direccion'].upper()}")
                st.metric("Probabilidad", f"{d['probabilidad']:.2%}")