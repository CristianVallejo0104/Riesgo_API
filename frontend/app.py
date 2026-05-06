import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

API_URL = "http://127.0.0.1:8000"

st.set_page_config(page_title="RiskLab USTA", layout="wide")

# ── Sidebar con contexto del proyecto ──
st.sidebar.title("RiskLab USTA")
st.sidebar.markdown("""
**Proyecto Integrador CIII**  
Sistema integral de análisis de riesgo financiero.

**Objetivo:** Construir una API REST con FastAPI 
que integre análisis técnico, modelos de riesgo, 
optimización de portafolios, renta fija, opciones 
y machine learning, con persistencia en SQLite 
y despliegue en contenedores.

**Activos:** AAPL, JPM, JNJ, XOM, KO  
**Benchmark:** S&P 500 (^GSPC)  
**Datos:** Yahoo Finance + FRED API
""")

ticker = st.sidebar.text_input("Ticker activo", value="AAPL")

# ── Tabs por módulo ──
tabs = st.tabs([
    "1. Técnico",
    "2. Rendimientos",
    "3. Volatilidad",
    "4. CAPM",
    "5. VaR/CVaR",
    "6. Markowitz",
    "7. Señales",
    "8. Macro",
    "9. Renta Fija",
    "10. Opciones",
    "11. Stress Test",
    "ML",
])

with tabs[0]:
    st.header("Mód. 1: Análisis Técnico")
    
    # ── Precios históricos ──
    if st.button("Descargar Precios", key="btn_precios"):
        with st.spinner("Descargando..."):
            r = requests.post(f"{API_URL}/precios/descargar/{ticker}")
            if r.status_code == 200:
                precios = r.json()
                df_precios = pd.DataFrame(precios)
                df_precios["fecha"] = pd.to_datetime(df_precios["fecha"])
                st.success(f"{len(precios)} precios descargados para {ticker}")

                fig = go.Figure(data=go.Candlestick(
                    x=df_precios["fecha"],
                    open=df_precios["open"], high=df_precios["high"],
                    low=df_precios["low"], close=df_precios["close"],
                ))
                fig.update_layout(title=f"Velas Japonesas — {ticker}", xaxis_rangeslider_visible=False)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.error(r.json().get("detail", "Error"))

    st.divider()

    # ── Indicadores técnicos ──
    if st.button("Cargar Indicadores", key="btn_ind"):
        with st.spinner("Calculando..."):
            requests.post(f"{API_URL}/precios/descargar/{ticker}")
            r = requests.get(f"{API_URL}/analisis/indicadores/{ticker}")
            if r.status_code == 200:
                data = r.json()["indicadores"]
                df = pd.DataFrame(data).T
                df.index = pd.to_datetime(df.index)

                fig = go.Figure()
                fig.add_trace(go.Scatter(x=df.index, y=df["close"], name="Precio"))
                fig.add_trace(go.Scatter(x=df.index, y=df["sma_short"], name="SMA 20"))
                fig.add_trace(go.Scatter(x=df.index, y=df["sma_long"], name="SMA 50"))
                fig.add_trace(go.Scatter(x=df.index, y=df["bollinger_upper"], name="Bollinger Sup", line=dict(dash="dash")))
                fig.add_trace(go.Scatter(x=df.index, y=df["bollinger_lower"], name="Bollinger Inf", line=dict(dash="dash")))
                fig.update_layout(title=f"Precio e Indicadores — {ticker}")
                st.plotly_chart(fig, use_container_width=True)

                col1, col2 = st.columns(2)
                with col1:
                    fig_rsi = px.line(df, y="rsi", title="RSI")
                    fig_rsi.add_hline(y=70, line_dash="dash", line_color="red")
                    fig_rsi.add_hline(y=30, line_dash="dash", line_color="green")
                    st.plotly_chart(fig_rsi, use_container_width=True)
                with col2:
                    fig_macd = go.Figure()
                    fig_macd.add_trace(go.Scatter(x=df.index, y=df["macd"], name="MACD"))
                    fig_macd.add_trace(go.Scatter(x=df.index, y=df["macd_signal"], name="Señal"))
                    fig_macd.add_trace(go.Bar(x=df.index, y=df["macd_histograma"], name="Histograma"))
                    fig_macd.update_layout(title="MACD")
                    st.plotly_chart(fig_macd, use_container_width=True)
            else:
                st.error("Error al cargar indicadores")

with tabs[1]:
    st.header("Mód. 2: Rendimientos")
    if st.button("Calcular Rendimientos", key="btn_rend"):
        with st.spinner("Calculando..."):
            r = requests.get(f"{API_URL}/analisis/rendimientos/{ticker}")
            if r.status_code == 200:
                data = r.json()
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Media Anual", f"{data['media_anual']:.4f}")
                    st.metric("Volatilidad Anual", f"{data['std_anual']:.4f}")
                    st.metric("Asimetría", f"{data['asimetria']:.4f}")
                    st.metric("Curtosis", f"{data['curtosis']:.4f}")
                with col2:
                    st.metric("Observaciones", data["n_observaciones"])
                    jb = data["jarque_bera"]
                    sw = data["shapiro_wilk"]
                    st.metric("Jarque-Bera p-value", f"{jb['p_value']:.6f}")
                    st.write("¿Normal (JB)?", "✅ Sí" if jb["es_normal"] else "❌ No")
                    st.metric("Shapiro-Wilk p-value", f"{sw['p_value']:.6f}")
                    st.write("¿Normal (SW)?", "✅ Sí" if sw["es_normal"] else "❌ No")

with tabs[2]:
    st.header("Mód. 3: Volatilidad — EWMA + GARCH")
    if st.button("Calcular Volatilidad", key="btn_vol"):
        with st.spinner("Calculando..."):
            r_ewma = requests.get(f"{API_URL}/analisis/ewma/{ticker}")
            r_garch = requests.get(f"{API_URL}/analisis/garch/{ticker}")
            if r_ewma.status_code == 200 and r_garch.status_code == 200:
                ewma = r_ewma.json()
                garch = r_garch.json()
                col1, col2 = st.columns(2)
                with col1:
                    st.subheader("EWMA")
                    st.metric("Volatilidad EWMA Anual", f"{ewma['volatilidad_ewma']:.4f}")
                with col2:
                    st.subheader("GARCH")
                    st.metric("Modelo", garch.get("orden", "N/A"))
                    st.metric("AIC", garch.get("aic", "N/A"))
                    st.metric("BIC", garch.get("bic", "N/A"))
                    st.metric("Persistencia", garch.get("persistencia", "N/A"))

with tabs[3]:
    st.header("Mód. 4: CAPM y Beta")
    st.info("El CAPM se calcula comparando el activo contra el S&P 500 como benchmark.")
    if st.button("Calcular CAPM", key="btn_capm"):
        st.warning("Endpoint CAPM en desarrollo — requiere rendimientos del benchmark.")


with tabs[4]:
    st.header("Mód. 5: VaR y CVaR")
    if st.button("Calcular VaR", key="btn_var"):
        with st.spinner("Calculando..."):
            r = requests.get(f"{API_URL}/analisis/var/{ticker}")
            if r.status_code == 200:
                data = r.json()
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("VaR Paramétrico", f"{data['var_parametrico']:.6f}")
                    st.metric("VaR Histórico", f"{data['var_historico']:.6f}")
                with col2:
                    st.metric("VaR Monte Carlo", f"{data['var_montecarlo']:.6f}")
                    st.metric("CVaR", f"{data['cvar']:.6f}")

                fig = go.Figure()
                fig.add_trace(go.Bar(
                    x=["Paramétrico", "Histórico", "Monte Carlo", "CVaR"],
                    y=[data["var_parametrico"], data["var_historico"], data["var_montecarlo"], data["cvar"]],
                    marker_color=["#636EFA", "#EF553B", "#00CC96", "#AB63FA"],
                ))
                fig.update_layout(title=f"Comparación VaR — {ticker}", yaxis_title="Pérdida diaria")
                st.plotly_chart(fig, use_container_width=True)

with tabs[5]:
    st.header("Mód. 6: Markowitz")
    permitir_cortos = st.checkbox("Permitir ventas en corto")
    if st.button("Optimizar Portafolio", key="btn_mark"):
        with st.spinner("Optimizando..."):
            r = requests.get(f"{API_URL}/analisis/markowitz", params={"permitir_cortos": permitir_cortos})
            if r.status_code == 200:
                data = r.json()
                opt = data["optimizacion"]

                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Retorno Anual", f"{opt['retorno_anual']:.4f}")
                    st.metric("Riesgo Anual", f"{opt['riesgo_anual']:.4f}")
                    st.metric("Sharpe Ratio", f"{opt['sharpe_ratio']:.4f}")
                with col2:
                    fig_pesos = px.pie(
                        names=list(opt["pesos"].keys()),
                        values=list(opt["pesos"].values()),
                        title="Pesos Óptimos",
                    )
                    st.plotly_chart(fig_pesos, use_container_width=True)

                frontera = pd.DataFrame(data["frontera"])
                fig_f = px.scatter(frontera, x="riesgo", y="retorno", title="Frontera Eficiente")
                st.plotly_chart(fig_f, use_container_width=True)


with tabs[6]:
    st.header("Mód. 7: Señales")
    st.info("Las señales se generan a partir de los indicadores técnicos del Módulo 1.")
    if st.button("Generar Señales", key="btn_señales"):
        with st.spinner("Analizando..."):
            r = requests.get(f"{API_URL}/analisis/indicadores/{ticker}")
            if r.status_code == 200:
                data = r.json()["indicadores"]
                df = pd.DataFrame(data).T
                ultimo = df.iloc[-1]

                señales = []
                if ultimo["rsi"] > 70:
                    señales.append("⚠️ RSI > 70 — Sobrecompra")
                elif ultimo["rsi"] < 30:
                    señales.append("✅ RSI < 30 — Sobreventa")
                else:
                    señales.append("➡️ RSI neutral")

                if ultimo["close"] > ultimo["bollinger_upper"]:
                    señales.append("⚠️ Precio sobre Bollinger superior")
                elif ultimo["close"] < ultimo["bollinger_lower"]:
                    señales.append("✅ Precio bajo Bollinger inferior")

                if ultimo["macd"] > ultimo["macd_signal"]:
                    señales.append("✅ MACD sobre señal — Tendencia alcista")
                else:
                    señales.append("⚠️ MACD bajo señal — Tendencia bajista")

                for s in señales:
                    st.write(s)

with tabs[7]:
    st.header("Mód. 8: Macro y Benchmark")
    if st.button("Obtener Datos Macro", key="btn_macro"):
        with st.spinner("Consultando FRED..."):
            r = requests.get(f"{API_URL}/renta-fija/curva")
            if r.status_code == 200:
                data = r.json()["datos_mercado"]
                df_curva = pd.DataFrame({"Plazo (años)": data["plazos"], "Tasa (%)": data["tasas"]})
                fig = px.line(df_curva, x="Plazo (años)", y="Tasa (%)", title="Curva de Rendimiento USA", markers=True)
                st.plotly_chart(fig, use_container_width=True)
                st.dataframe(df_curva)

with tabs[8]:
    st.header("Mód. 9: Renta Fija")
    col1, col2 = st.columns(2)
    with col1:
        tasa_cupon = st.number_input("Tasa Cupón", value=0.05, step=0.01)
    with col2:
        vencimiento = st.number_input("Vencimiento (años)", value=10, min_value=1, max_value=30)
    if st.button("Calcular Duración y Convexidad", key="btn_rf"):
        with st.spinner("Calculando..."):
            r = requests.get(f"{API_URL}/renta-fija/duracion", params={"tasa_cupon": tasa_cupon, "vencimiento": vencimiento})
            if r.status_code == 200:
                data = r.json()
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Precio del Bono", f"${data['precio_bono']:.2f}")
                with col2:
                    st.metric("Duración", f"{data['duracion']:.4f} años")
                with col3:
                    st.metric("Convexidad", f"{data['convexidad']:.4f}")
                st.caption(f"Tasa de descuento: {data['tasa_descuento']:.4%}")

with tabs[9]:
    st.header("Mód. 10: Opciones — Black-Scholes")
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        S = st.number_input("Precio Spot (S)", value=100.0)
    with col2:
        K = st.number_input("Strike (K)", value=100.0)
    with col3:
        T = st.number_input("Tiempo (T años)", value=1.0, step=0.1)
    with col4:
        r_opt = st.number_input("Tasa libre riesgo (r)", value=0.04, step=0.01)
    with col5:
        sigma = st.number_input("Volatilidad (σ)", value=0.2, step=0.05)
    if st.button("Calcular Black-Scholes", key="btn_bs"):
        with st.spinner("Calculando..."):
            r = requests.get(f"{API_URL}/opciones/black-scholes", params={"S": S, "K": K, "T": T, "r": r_opt, "sigma": sigma})
            if r.status_code == 200:
                data = r.json()
                col1, col2 = st.columns(2)
                with col1:
                    st.subheader("Precios")
                    st.metric("Call", f"${data['precios']['call']:.4f}")
                    st.metric("Put", f"${data['precios']['put']:.4f}")
                with col2:
                    st.subheader("Greeks")
                    greeks = data["greeks"]
                    for nombre, valor in greeks.items():
                        st.metric(nombre.replace("_", " ").title(), f"{valor:.6f}")


with tabs[10]:
    st.header("Mód. 11: Stress Testing")
    if st.button("Ejecutar Stress Test", key="btn_stress"):
        with st.spinner("Simulando escenarios..."):
            r = requests.get(f"{API_URL}/analisis/stress-test")
            if r.status_code == 200:
                escenarios = r.json()["escenarios"]
                for esc in escenarios:
                    color = "🔴" if esc["impacto_portafolio"] < 0 else "🟢"
                    st.write(f"{color} **{esc['escenario']}** — Impacto: {esc['impacto_portafolio']:.4f}")
                df_stress = pd.DataFrame(escenarios)
                fig = px.bar(df_stress, x="escenario", y="impacto_portafolio", color="tipo", title="Impacto por Escenario")
                st.plotly_chart(fig, use_container_width=True)

with tabs[11]:
    st.header("Machine Learning")
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Entrenar Modelo")
        ticker_ml = st.text_input("Ticker para entrenar", value="AAPL", key="ml_ticker")
        if st.button("Entrenar", key="btn_train"):
            with st.spinner("Entrenando modelo..."):
                r = requests.post(f"{API_URL}/ml/entrenar/{ticker_ml}")
                if r.status_code == 200:
                    data = r.json()
                    st.success(f"Modelo entrenado — Accuracy: {data['accuracy']:.4f}")
                else:
                    st.error("Error al entrenar")
    with col2:
        st.subheader("Predecir")
        ticker_pred = st.text_input("Ticker para predecir", value="AAPL", key="pred_ticker")
        if st.button("Predecir", key="btn_pred"):
            with st.spinner("Prediciendo..."):
                r = requests.post(f"{API_URL}/ml/predecir/{ticker_pred}")
                if r.status_code == 200:
                    data = r.json()
                    emoji = "📈" if data["direccion"] == "sube" else "📉"
                    st.metric("Predicción", f"{emoji} {data['direccion'].upper()}")
                    st.metric("Probabilidad", f"{data['probabilidad']:.2%}")
                else:
                    st.error("Entrena el modelo primero")
