"""
frontend/app.py
Dashboard RiskLab USTA — Streamlit

Corre con:
    streamlit run frontend/app.py
    (desde la raíz del proyecto, con el backend corriendo en :8000)
"""

import requests
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px

# ── Configuración de página ──────────────────────────────────────────────────
st.set_page_config(
    page_title="RiskLab USTA",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ──────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Montserrat', sans-serif; }
    .main-header {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
        padding: 1.5rem 2rem; border-radius: 12px; margin-bottom: 1.5rem; color: white;
    }
    .main-header h1 { margin: 0; font-size: 1.8rem; font-weight: 700; }
    .main-header p  { margin: 0.3rem 0 0; opacity: 0.85; font-size: 0.9rem; }
    .stTabs [data-baseweb="tab-list"] { gap: 4px; }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px 8px 0 0; padding: 8px 16px;
        font-weight: 600; font-size: 0.82rem;
    }
</style>
""", unsafe_allow_html=True)

BACKEND_URL = "http://127.0.0.1:8000"


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def api_get(endpoint: str, params: dict = None) -> dict | None:
    try:
        r = requests.get(f"{BACKEND_URL}{endpoint}", params=params, timeout=120)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        st.error("❌ No se puede conectar con el backend. Asegúrate de que esté corriendo en :8000")
        return None
    except requests.exceptions.HTTPError as e:
        st.error(f"❌ Error {e.response.status_code}: {e.response.json().get('detail', str(e))}")
        return None
    except Exception as e:
        st.error(f"❌ Error inesperado: {e}")
        return None


def api_post(endpoint: str, body: dict = None) -> dict | None:
    try:
        r = requests.post(f"{BACKEND_URL}{endpoint}", json=body or {}, timeout=120)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        st.error("❌ No se puede conectar con el backend.")
        return None
    except requests.exceptions.HTTPError as e:
        st.error(f"❌ Error {e.response.status_code}: {e.response.json().get('detail', str(e))}")
        return None
    except Exception as e:
        st.error(f"❌ Error inesperado: {e}")
        return None


# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════

TICKERS_DB = {
    "AAPL": "Apple Inc. (Tech)", "JPM": "JPMorgan Chase (Financiero)",
    "JNJ": "Johnson & Johnson (Salud)", "XOM": "ExxonMobil (Energía)",
    "KO": "Coca-Cola (Consumo)", "MSFT": "Microsoft (Tech)",
    "GOOGL": "Alphabet (Tech)", "AMZN": "Amazon (Tech)",
    "TSLA": "Tesla (Tech)", "NVDA": "NVIDIA (Tech)",
    "META": "Meta Platforms (Tech)", "BAC": "Bank of America (Financiero)",
    "PFE": "Pfizer (Salud)", "CVX": "Chevron (Energía)",
    "WMT": "Walmart (Consumo)", "HD": "Home Depot (Consumo)",
}

with st.sidebar:
    st.markdown("## ⚙️ Configuración")
    st.markdown("---")

    tickers = st.multiselect(
        "📦 Tickers del portafolio",
        options=list(TICKERS_DB.keys()),
        default=["AAPL", "JPM", "JNJ", "XOM", "KO"],
        format_func=lambda t: f"{t} — {TICKERS_DB[t]}",
    )
    ticker_sel = st.selectbox("🔍 Ticker a analizar", tickers if tickers else ["AAPL"])
    ticker_manual = st.text_input("✍️ Agregar otro ticker (ej: NVDA, BMW)", value="")
    if ticker_manual:
        ticker_upper = ticker_manual.strip().upper()
        if ticker_upper not in tickers:
            try:
                import yfinance as yf
                info = yf.Ticker(ticker_upper).info
                if info.get("regularMarketPrice"):
                    tickers.append(ticker_upper)
                    st.success(f"✅ {ticker_upper} agregado")
                else:
                    st.error(f"❌ {ticker_upper} no es un ticker válido")
            except:
                st.error(f"❌ No se pudo validar {ticker_upper}")

    benchmark = st.selectbox("📊 Benchmark", 
        ["^GSPC", "^IXIC", "^DJI", "^RUT"],
        format_func=lambda b: {"^GSPC": "S&P 500", "^IXIC": "Nasdaq", "^DJI": "Dow Jones", "^RUT": "Russell 2000"}[b]
    )

    st.markdown("---")
    st.markdown("**📐 Parámetros de Riesgo**")

    confianza_var = st.slider(
        "Nivel de confianza VaR", min_value=0.90, max_value=0.99,
        value=0.95, step=0.01, format="%.2f",
    )

    valor_portafolio = st.number_input(
        "💰 Valor del portafolio (USD)",
        min_value=1.0, max_value=10_000_000.0,
        value=100_000.0, step=1_000.0,
    )

    st.markdown("---")
    st.markdown("**⚖️ Pesos del portafolio**")
    peso_igual = st.checkbox("Pesos iguales", value=True)
    if tickers:
        if peso_igual:
            pesos = {t: round(1 / len(tickers), 4) for t in tickers}
            st.caption(f"Cada activo: {list(pesos.values())[0]*100:.1f}%")
        else:
            pesos = {}
            for t in tickers:
                p = st.number_input(f"Peso {t}", 0.0, 1.0, value=round(1/len(tickers), 2), step=0.05, key=f"w_{t}")
                pesos[t] = p
            if abs(sum(pesos.values()) - 1.0) > 0.01:
                st.warning(f"⚠️ Los pesos suman {sum(pesos.values()):.2f}, no 1.0")

    st.markdown("---")
    st.caption("**RiskLab USTA** · Teoría del Riesgo + Python APIs · CIII")


# ══════════════════════════════════════════════════════════════════════════════
# HEADER
# ══════════════════════════════════════════════════════════════════════════════

st.markdown(f"""
<div class="main-header" style="background: linear-gradient(135deg, #1a56db 0%, #1e40af 100%);">
    <h1 style="color: white;">📊 RiskLab USTA — Análisis de Riesgo Financiero</h1>
    <p style="color: #e2e8f0;">Portafolio: <strong>{' · '.join(tickers)}</strong> &nbsp;|&nbsp;
       Benchmark: <strong>{benchmark}</strong> &nbsp;|&nbsp;
       Confianza VaR: <strong>{confianza_var:.0%}</strong> &nbsp;|&nbsp;
       Inversión: <strong>${valor_portafolio:,.0f}</strong></p>
</div>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# TABS
# ══════════════════════════════════════════════════════════════════════════════

tabs = st.tabs([
    "📈 1. Técnico", "📉 2. Rendimientos", "🌊 3. Volatilidad",
    "🎯 4. CAPM", "🛡️ 5. VaR/CVaR", "⚡ 6. Markowitz",
    "🚦 7. Señales", "🌐 8. Macro", "📐 9. Renta Fija",
    "🧮 10. Opciones", "💥 11. Stress Test", "🤖 ML",
])


# ══════════════════════════════════════════════════════════════════════════════
# MÓD. 1 — ANÁLISIS TÉCNICO
# ══════════════════════════════════════════════════════════════════════════════

with tabs[0]:
    st.subheader("📈 Análisis Técnico e Indicadores")

    if st.button("🔄 Descargar precios y calcular indicadores", key="btn_m1"):
        # ── Gráfico comparativo de todos los tickers ──
        st.markdown("### Comparación de precios — Todos los activos")
        fig_comp = go.Figure()
        for t in tickers:
            with st.spinner(f"Descargando {t}..."):
                api_post(f"/precios/descargar/{t}")
                r_p = api_get(f"/precios/{t}")
                if r_p:
                    df_t = pd.DataFrame(r_p)
                    df_t["fecha"] = pd.to_datetime(df_t["fecha"])
                    # Normalizar a base 100 para comparar
                    df_t["precio_norm"] = df_t["close"] / df_t["close"].iloc[0] * 100
                    fig_comp.add_trace(go.Scatter(x=df_t["fecha"], y=df_t["precio_norm"], name=t))

        fig_comp.update_layout(
            title="Rendimiento comparado (Base 100)",
            yaxis_title="Valor (base 100)", height=400,
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
        )
        st.plotly_chart(fig_comp, use_container_width=True)

        st.divider()

        # ── Análisis individual del ticker seleccionado ──
        st.markdown(f"### Análisis individual — {ticker_sel}")

        r_precios = api_get(f"/precios/{ticker_sel}")
        if r_precios:
            df_p = pd.DataFrame(r_precios)
            df_p["fecha"] = pd.to_datetime(df_p["fecha"])
            fig_velas = go.Figure(data=go.Candlestick(
                x=df_p["fecha"], open=df_p["open"], high=df_p["high"],
                low=df_p["low"], close=df_p["close"],
            ))
            fig_velas.update_layout(title=f"Velas Japonesas — {ticker_sel}",
                                     xaxis_rangeslider_visible=False, height=400)
            st.plotly_chart(fig_velas, use_container_width=True)

        data = api_get(f"/analisis/indicadores/{ticker_sel}")
        if data:
            df = pd.DataFrame(data["indicadores"]).T
            df.index = pd.to_datetime(df.index)

            fig = go.Figure()
            fig.add_trace(go.Scatter(x=df.index, y=df["close"], name="Precio", line=dict(width=2)))
            fig.add_trace(go.Scatter(x=df.index, y=df["sma_short"], name="SMA 20", line=dict(dash="dot")))
            fig.add_trace(go.Scatter(x=df.index, y=df["sma_long"], name="SMA 50", line=dict(dash="dash")))
            fig.add_trace(go.Scatter(x=df.index, y=df["bollinger_upper"], name="BB Sup", line=dict(color="rgba(100,100,200,0.5)")))
            fig.add_trace(go.Scatter(x=df.index, y=df["bollinger_lower"], name="BB Inf",
                                      line=dict(color="rgba(100,100,200,0.5)"), fill="tonexty", fillcolor="rgba(100,100,200,0.07)"))
            fig.update_layout(title=f"Precio e Indicadores — {ticker_sel}", height=420,
                              legend=dict(orientation="h", yanchor="bottom", y=1.02))
            st.plotly_chart(fig, use_container_width=True)

            col1, col2 = st.columns(2)
            with col1:
                fig_rsi = go.Figure()
                fig_rsi.add_trace(go.Scatter(x=df.index, y=df["rsi"], name="RSI", line=dict(color="#6366F1", width=2)))
                fig_rsi.add_hline(y=70, line_dash="dash", line_color="red", annotation_text="Sobrecompra (70)")
                fig_rsi.add_hline(y=30, line_dash="dash", line_color="green", annotation_text="Sobreventa (30)")
                fig_rsi.update_layout(title="RSI (14)", height=250, yaxis=dict(range=[0, 100]))
                st.plotly_chart(fig_rsi, use_container_width=True)

            with col2:
                fig_macd = go.Figure()
                fig_macd.add_trace(go.Scatter(x=df.index, y=df["macd"], name="MACD", line=dict(width=1.5)))
                fig_macd.add_trace(go.Scatter(x=df.index, y=df["macd_signal"], name="Señal", line=dict(width=1.5)))
                colors = ["green" if v >= 0 else "red" for v in df["macd_histograma"].fillna(0)]
                fig_macd.add_trace(go.Bar(x=df.index, y=df["macd_histograma"], name="Histograma", marker_color=colors, opacity=0.6))
                fig_macd.update_layout(title="MACD", height=250)
                st.plotly_chart(fig_macd, use_container_width=True)

            fig_stoch = go.Figure()
            fig_stoch.add_trace(go.Scatter(x=df.index, y=df["stochastic_k"], name="%K", line=dict(width=1.5)))
            fig_stoch.add_trace(go.Scatter(x=df.index, y=df["stochastic_d"], name="%D", line=dict(width=1.5)))
            fig_stoch.add_hline(y=80, line_dash="dash", line_color="red")
            fig_stoch.add_hline(y=20, line_dash="dash", line_color="green")
            fig_stoch.update_layout(title="Oscilador Estocástico", height=250, yaxis=dict(range=[0, 100]))
            st.plotly_chart(fig_stoch, use_container_width=True)

            with st.expander("ℹ️ Interpretación de indicadores"):
                st.markdown("""
                | Indicador | Señal alcista | Señal bajista |
                |---|---|---|
                | **SMA/EMA** | Precio > media | Precio < media |
                | **Bollinger** | Precio toca banda inferior | Precio toca banda superior |
                | **RSI** | RSI < 30 (sobreventa) | RSI > 70 (sobrecompra) |
                | **MACD** | MACD cruza señal ↑ | MACD cruza señal ↓ |
                | **Estocástico** | %K cruza %D ↑ en zona <20 | %K cruza %D ↓ en zona >80 |
                """)


# ══════════════════════════════════════════════════════════════════════════════
# MÓD. 2 — RENDIMIENTOS
# ══════════════════════════════════════════════════════════════════════════════

with tabs[1]:
    st.subheader("📉 Rendimientos y Propiedades Empíricas")

    if st.button("🔄 Calcular rendimientos", key="btn_m2"):
        with st.spinner("Calculando..."):
            data_r = api_get(f"/analisis/rendimientos/{ticker_sel}")

        if data_r:
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("Media diaria", f"{data_r['media_diaria']*100:.4f}%")
            c2.metric("Vol. diaria", f"{data_r['std_diaria']*100:.4f}%")
            c3.metric("Asimetría", f"{data_r['asimetria']:.3f}")
            c4.metric("Curtosis", f"{data_r['curtosis']:.3f}")
            c5.metric("Observaciones", data_r["n_observaciones"])

            st.markdown("---")

            col1, col2 = st.columns(2)
            with col1:
                st.metric("Media anualizada", f"{data_r['media_anual']*100:.2f}%")
                st.metric("Volatilidad anualizada", f"{data_r['std_anual']*100:.2f}%")
            with col2:
                jb = data_r["jarque_bera"]
                sw = data_r["shapiro_wilk"]
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
                """)


# ══════════════════════════════════════════════════════════════════════════════
# MÓD. 3 — VOLATILIDAD
# ══════════════════════════════════════════════════════════════════════════════

with tabs[2]:
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
                st.info("EWMA da más peso a datos recientes. Lambda = 0.94 (estándar RiskMetrics).")

            with col2:
                st.markdown("### GARCH")
                st.metric("Modelo seleccionado", garch.get("orden", "N/A"))
                c1, c2 = st.columns(2)
                c1.metric("AIC", garch.get("aic", "N/A"))
                c2.metric("BIC", garch.get("bic", "N/A"))
                st.metric("Persistencia", garch.get("persistencia", "N/A"))
                st.info("Se prueban GARCH(1,1), (1,2), (2,1), (2,2) y se elige el de menor AIC.")


# ══════════════════════════════════════════════════════════════════════════════
# MÓD. 4 — CAPM
# ══════════════════════════════════════════════════════════════════════════════

with tabs[3]:
    st.subheader("🎯 CAPM y Beta")
    st.info("El CAPM compara el rendimiento del activo contra el S&P 500 (benchmark) "
            "para determinar si el activo genera valor por encima del riesgo asumido.")
    st.warning("⚠️ Endpoint CAPM en desarrollo — requiere rendimientos del benchmark sincronizados.")


# ══════════════════════════════════════════════════════════════════════════════
# MÓD. 5 — VaR y CVaR
# ══════════════════════════════════════════════════════════════════════════════

with tabs[4]:
    st.subheader("🛡️ Value at Risk y Conditional VaR")

    if st.button("🔄 Calcular VaR", key="btn_m5"):
        with st.spinner("Calculando..."):
            data_v = api_get(f"/analisis/var/{ticker_sel}")

        if data_v:
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("VaR Paramétrico", f"{data_v['var_parametrico']:.6f}",
                        delta=f"${abs(data_v['var_parametrico'])*valor_portafolio:,.0f}")
            col2.metric("VaR Histórico", f"{data_v['var_historico']:.6f}",
                        delta=f"${abs(data_v['var_historico'])*valor_portafolio:,.0f}")
            col3.metric("VaR Monte Carlo", f"{data_v['var_montecarlo']:.6f}",
                        delta=f"${abs(data_v['var_montecarlo'])*valor_portafolio:,.0f}")
            col4.metric("CVaR", f"{data_v['cvar']:.6f}",
                        delta=f"${abs(data_v['cvar'])*valor_portafolio:,.0f}")

            fig = go.Figure()
            nombres = ["Paramétrico", "Histórico", "Monte Carlo", "CVaR"]
            valores = [data_v["var_parametrico"], data_v["var_historico"],
                       data_v["var_montecarlo"], data_v["cvar"]]
            colores = ["#636EFA", "#EF553B", "#00CC96", "#AB63FA"]
            fig.add_trace(go.Bar(x=nombres, y=valores, marker_color=colores))
            fig.update_layout(title=f"Comparación de VaR — {ticker_sel} (conf. {confianza_var:.0%})",
                              yaxis_title="Pérdida diaria", height=350)
            st.plotly_chart(fig, use_container_width=True)

            with st.expander("ℹ️ Interpretación"):
                st.markdown(f"""
                Con una inversión de **${valor_portafolio:,.0f}**, al nivel de confianza del **{confianza_var:.0%}**:
                - **VaR Paramétrico:** la peor pérdida diaria esperada es **${abs(data_v['var_parametrico'])*valor_portafolio:,.0f}**
                - **CVaR:** si se supera el VaR, la pérdida promedio sería **${abs(data_v['cvar'])*valor_portafolio:,.0f}**
                """)


# ══════════════════════════════════════════════════════════════════════════════
# MÓD. 6 — MARKOWITZ
# ══════════════════════════════════════════════════════════════════════════════

with tabs[5]:
    st.subheader("⚡ Optimización de Portafolio — Markowitz")
    permitir_cortos = st.checkbox("Permitir ventas en corto", key="m6_cortos")

    if st.button("🔄 Optimizar portafolio", key="btn_m6"):
        with st.spinner("Optimizando con programación cuadrática (cvxpy)..."):
            data_m = api_get("/analisis/markowitz", params={"permitir_cortos": permitir_cortos})

        if data_m:
            opt = data_m["optimizacion"]
            col1, col2, col3 = st.columns(3)
            col1.metric("Retorno Anual", f"{opt['retorno_anual']*100:.2f}%")
            col2.metric("Riesgo Anual", f"{opt['riesgo_anual']*100:.2f}%")
            col3.metric("Sharpe Ratio", f"{opt['sharpe_ratio']:.4f}")

            col_a, col_b = st.columns(2)
            with col_a:
                fig_pesos = px.pie(names=list(opt["pesos"].keys()),
                                   values=list(opt["pesos"].values()),
                                   title="Pesos Óptimos del Portafolio")
                st.plotly_chart(fig_pesos, use_container_width=True)

            with col_b:
                frontera = pd.DataFrame(data_m["frontera"])
                if not frontera.empty:
                    fig_f = px.scatter(frontera, x="riesgo", y="retorno",
                                       title="Frontera Eficiente")
                    fig_f.add_scatter(x=[opt["riesgo_anual"]], y=[opt["retorno_anual"]],
                                      mode="markers", marker=dict(size=14, color="red", symbol="star"),
                                      name="Portafolio Óptimo")
                    fig_f.update_layout(xaxis_title="Riesgo (σ)", yaxis_title="Retorno esperado")
                    st.plotly_chart(fig_f, use_container_width=True)

            st.markdown("#### 💰 Distribución de la inversión")
            for t, w in opt["pesos"].items():
                monto = w * valor_portafolio
                st.write(f"**{t}:** {w*100:.1f}% → ${monto:,.0f}")


# ══════════════════════════════════════════════════════════════════════════════
# MÓD. 7 — SEÑALES
# ══════════════════════════════════════════════════════════════════════════════

with tabs[6]:
    st.subheader("🚦 Señales de Trading")

    if st.button("🔄 Generar señales", key="btn_m7"):
        with st.spinner("Analizando indicadores..."):
            data_s = api_get(f"/analisis/indicadores/{ticker_sel}")

        if data_s:
            df_s = pd.DataFrame(data_s["indicadores"]).T
            ultimo = df_s.iloc[-1]

            st.markdown(f"### Señales para {ticker_sel}")
            señales = []

            # RSI
            if ultimo["rsi"] > 70:
                señales.append(("RSI", "🔴 VENTA", f"RSI = {ultimo['rsi']:.1f} — Sobrecompra"))
            elif ultimo["rsi"] < 30:
                señales.append(("RSI", "🟢 COMPRA", f"RSI = {ultimo['rsi']:.1f} — Sobreventa"))
            else:
                señales.append(("RSI", "🟡 NEUTRAL", f"RSI = {ultimo['rsi']:.1f}"))

            # Bollinger
            if ultimo["close"] > ultimo["bollinger_upper"]:
                señales.append(("Bollinger", "🔴 VENTA", "Precio sobre banda superior"))
            elif ultimo["close"] < ultimo["bollinger_lower"]:
                señales.append(("Bollinger", "🟢 COMPRA", "Precio bajo banda inferior"))
            else:
                señales.append(("Bollinger", "🟡 NEUTRAL", "Precio dentro de las bandas"))

            # MACD
            if ultimo["macd"] > ultimo["macd_signal"]:
                señales.append(("MACD", "🟢 COMPRA", "MACD sobre línea de señal"))
            else:
                señales.append(("MACD", "🔴 VENTA", "MACD bajo línea de señal"))

            # Estocástico
            if ultimo["stochastic_k"] > 80:
                señales.append(("Estocástico", "🔴 VENTA", f"%K = {ultimo['stochastic_k']:.1f} — Sobrecompra"))
            elif ultimo["stochastic_k"] < 20:
                señales.append(("Estocástico", "🟢 COMPRA", f"%K = {ultimo['stochastic_k']:.1f} — Sobreventa"))
            else:
                señales.append(("Estocástico", "🟡 NEUTRAL", f"%K = {ultimo['stochastic_k']:.1f}"))

            df_señales = pd.DataFrame(señales, columns=["Indicador", "Señal", "Descripción"])
            st.dataframe(df_señales.set_index("Indicador"), use_container_width=True)

            compras = sum(1 for s in señales if "COMPRA" in s[1])
            ventas = sum(1 for s in señales if "VENTA" in s[1])
            if compras > ventas:
                st.success(f"✅ Señal general: COMPRA ({compras} de {len(señales)} indicadores)")
            elif ventas > compras:
                st.error(f"⚠️ Señal general: VENTA ({ventas} de {len(señales)} indicadores)")
            else:
                st.warning(f"🟡 Señal general: NEUTRAL")


# ══════════════════════════════════════════════════════════════════════════════
# MÓD. 8 — MACRO
# ══════════════════════════════════════════════════════════════════════════════

with tabs[7]:
    st.subheader("🌐 Contexto Macroeconómico")

    if st.button("🔄 Cargar datos macro", key="btn_m8"):
        with st.spinner("Consultando FRED..."):
            data_curva = api_get("/renta-fija/curva")

        if data_curva:
            datos = data_curva["datos_mercado"]
            df_curva = pd.DataFrame({"Plazo (años)": datos["plazos"], "Tasa (%)": datos["tasas"]})

            fig = px.line(df_curva, x="Plazo (años)", y="Tasa (%)",
                          title="Curva de Rendimiento del Tesoro USA (datos FRED en tiempo real)",
                          markers=True)
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)

            st.dataframe(df_curva, use_container_width=True)

            with st.expander("ℹ️ Interpretación"):
                st.markdown("""
                - **Curva normal (pendiente positiva):** mayor plazo → mayor tasa. Economía estable.
                - **Curva invertida:** tasas cortas > tasas largas. Señal histórica de recesión.
                - **Curva plana:** incertidumbre sobre la dirección económica.
                """)


# ══════════════════════════════════════════════════════════════════════════════
# MÓD. 9 — RENTA FIJA
# ══════════════════════════════════════════════════════════════════════════════

with tabs[8]:
    st.subheader("📐 Renta Fija — Duración y Convexidad")

    col1, col2 = st.columns(2)
    with col1:
        tasa_cupon = st.number_input("Tasa Cupón anual", value=0.05, step=0.01, format="%.2f")
    with col2:
        vencimiento = st.number_input("Vencimiento (años)", value=10, min_value=1, max_value=30)

    if st.button("🔄 Calcular duración y convexidad", key="btn_m9"):
        with st.spinner("Calculando..."):
            data_rf = api_get("/renta-fija/duracion",
                              params={"tasa_cupon": tasa_cupon, "vencimiento": vencimiento})

        if data_rf:
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Precio del Bono", f"${data_rf['precio_bono']:.2f}")
            col2.metric("Duración", f"{data_rf['duracion']:.4f} años")
            col3.metric("Convexidad", f"{data_rf['convexidad']:.4f}")
            col4.metric("Tasa descuento", f"{data_rf['tasa_descuento']:.4%}")

            with st.expander("ℹ️ Interpretación"):
                st.markdown(f"""
                - **Duración {data_rf['duracion']:.2f} años:** si las tasas suben 1%, el precio del bono cae ≈{data_rf['duracion']:.2f}%
                - **Convexidad:** corrección de segundo orden. A mayor convexidad, mejor comportamiento ante cambios grandes de tasas.
                """)


# ══════════════════════════════════════════════════════════════════════════════
# MÓD. 10 — OPCIONES
# ══════════════════════════════════════════════════════════════════════════════

with tabs[9]:
    st.subheader("🧮 Opciones — Black-Scholes y Greeks")

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        S = st.number_input("Precio Spot (S)", value=100.0, step=5.0)
    with col2:
        K = st.number_input("Strike (K)", value=100.0, step=5.0)
    with col3:
        T = st.number_input("Tiempo (T años)", value=1.0, step=0.1)
    with col4:
        r_opt = st.number_input("Tasa libre riesgo", value=0.04, step=0.01, format="%.2f")
    with col5:
        sigma = st.number_input("Volatilidad (σ)", value=0.20, step=0.05, format="%.2f")

    if st.button("🔄 Calcular Black-Scholes", key="btn_m10"):
        with st.spinner("Calculando..."):
            data_bs = api_get("/opciones/black-scholes",
                              params={"S": S, "K": K, "T": T, "r": r_opt, "sigma": sigma})

        if data_bs:
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("### 💲 Precios")
                c1, c2 = st.columns(2)
                c1.metric("Call", f"${data_bs['precios']['call']:.4f}")
                c2.metric("Put", f"${data_bs['precios']['put']:.4f}")

            with col2:
                st.markdown("### 📊 Greeks")
                greeks = data_bs["greeks"]
                g1, g2, g3 = st.columns(3)
                g1.metric("Delta Call", f"{greeks['delta_call']:.4f}")
                g1.metric("Delta Put", f"{greeks['delta_put']:.4f}")
                g2.metric("Gamma", f"{greeks['gamma']:.6f}")
                g2.metric("Vega", f"{greeks['vega']:.4f}")
                g3.metric("Theta", f"{greeks['theta_call']:.4f}")
                g3.metric("Rho", f"{greeks['rho_call']:.4f}")


# ══════════════════════════════════════════════════════════════════════════════
# MÓD. 11 — STRESS TESTING
# ══════════════════════════════════════════════════════════════════════════════

with tabs[10]:
    st.subheader("💥 Stress Testing")

    if st.button("🔄 Ejecutar Stress Test", key="btn_m11"):
        with st.spinner("Simulando escenarios extremos..."):
            data_st = api_get("/analisis/stress-test")

        if data_st:
            escenarios = data_st["escenarios"]

            for esc in escenarios:
                impacto_usd = esc["impacto_portafolio"] * valor_portafolio
                if esc["impacto_portafolio"] < 0:
                    st.error(f"🔴 **{esc['escenario']}** — Impacto: {esc['impacto_portafolio']:.4f} "
                             f"(${impacto_usd:,.0f})")
                else:
                    st.warning(f"🟡 **{esc['escenario']}** — Impacto: {esc['impacto_portafolio']:.4f} "
                               f"(${impacto_usd:,.0f})")

            df_stress = pd.DataFrame(escenarios)
            fig = px.bar(df_stress, x="escenario", y="impacto_portafolio",
                         color="tipo", title="Impacto por Escenario de Estrés")
            st.plotly_chart(fig, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# ML
# ══════════════════════════════════════════════════════════════════════════════

with tabs[11]:
    st.subheader("🤖 Machine Learning — Predicción de Dirección")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### 🏋️ Entrenar Modelo")
        ticker_ml = st.selectbox("Ticker para entrenar", tickers if tickers else ["AAPL"], key="ml_train")
        if st.button("🔄 Entrenar Random Forest", key="btn_ml_train"):
            with st.spinner("Entrenando modelo..."):
                data_ml = api_post(f"/ml/entrenar/{ticker_ml}")
            if data_ml:
                st.success(f"✅ Modelo entrenado — Accuracy: {data_ml['accuracy']:.4f}")
                st.caption(f"Guardado en: {data_ml['ruta']}")

    with col2:
        st.markdown("### 🔮 Predecir")
        ticker_pred = st.selectbox("Ticker para predecir", tickers if tickers else ["AAPL"], key="ml_pred")
        if st.button("🔄 Predecir dirección", key="btn_ml_pred"):
            with st.spinner("Prediciendo..."):
                data_pred = api_post(f"/ml/predecir/{ticker_pred}")
            if data_pred:
                emoji = "📈" if data_pred["direccion"] == "sube" else "📉"
                st.metric("Predicción", f"{emoji} {data_pred['direccion'].upper()}")
                st.metric("Probabilidad", f"{data_pred['probabilidad']:.2%}")
                st.info("El modelo usa los retornos de los últimos 5 días como features "
                        "para predecir si el precio sube o baja al día siguiente.")