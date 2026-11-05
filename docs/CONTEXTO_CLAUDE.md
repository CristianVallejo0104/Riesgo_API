# RiskLab USTA — Resumen del trabajo y contexto para seguir en Claude Desktop

> Este archivo resume **qué se cambió, por qué (teoría de riesgo y estadística), cómo probarlo en tu PC
> y cómo pasarlo a `main`**. Al final hay un **prompt listo para copiar** en Claude Desktop (o Claude Code)
> y seguir trabajando con todo el contexto.

---

## 1. Estado del repositorio

| Rama | Contenido |
|---|---|
| `main` | **Versión nueva (v2.1)**, la principal. Incluye todos los cambios de este documento. |
| `version-original` | Código inicial (commit `770ec14`), conservado sin cambios para no perder nada. |
| `ccr-bd062cce-jewh0m` | Rama de trabajo donde se hicieron los cambios (ya está fusionada en `main`). |

Commits de la v2.1, en orden:
1. Corrige la teoría de riesgo en el backend y agrega pruebas de coherencia.
2. Rediseña el tablero: navegación por secciones y guías de lectura.
3. Bonos con frecuencia y nominal, confianza libre, caché incremental y colores coherentes.
4. Markowitz: contexto e interpretación de las ventas en corto.
5. Mercado colombiano: tickers BVC, COLCAP, tasa libre de riesgo de Colombia y COP.
6. README coherente y aclaración de pesos negativos.

---

## 2. Cómo funciona, desde la teoría de riesgo y la estadística

### 2.1 Rendimientos: ¿log o simples?
- **Activo individual → rendimiento logarítmico** `r = ln(Pₜ/Pₜ₋₁)`. Se usa porque es **aditivo en el
  tiempo**: el rendimiento de 10 días es la suma de los 10 diarios. Eso simplifica escalar el VaR y modelar la volatilidad.
- **Portafolio → rendimiento simple** `R = Pₜ/Pₜ₋₁ − 1`. El rendimiento de un portafolio es el
  **promedio ponderado de rendimientos simples** `R_p = Σ wᵢ Rᵢ`. Esa igualdad **no** se cumple con logs, así que
  promediar logs entre activos (como hacía el código original) era un error.
- Anualización: media × 252 y desviación × √252 (252 días hábiles; la √ viene de que la varianza de una suma de
  variables independientes es la suma de las varianzas).

### 2.2 ¿Los rendimientos son normales?
- **Asimetría** (sesgo) y **curtosis en exceso**. Ojo: pandas entrega la curtosis *en exceso*, que vale 0 para la
  normal. El código viejo la comparaba contra 3, y eso estaba mal.
- **Jarque-Bera** (usa asimetría y curtosis) y **Shapiro-Wilk**. H₀: los datos son normales. p < 0,05 → se rechaza.
- **Gráfico Q-Q** con posiciones de graficación `(i − 0,5)/n`: si los extremos se despegan de la línea, hay **colas pesadas**.
- Se reporta además cuántos días caen a más de 3σ frente a lo que predice la normal (0,27 %).
- Consecuencia práctica: con colas pesadas, el VaR normal **subestima** el riesgo.

### 2.3 Volatilidad condicional
- **EWMA (RiskMetrics)**: `σ²ₜ = λσ²ₜ₋₁ + (1−λ)r²ₜ₋₁`, con λ = 0,94. Le da más peso a lo reciente.
- **GARCH(p,q)**: `σ²ₜ = ω + Σαᵢ r²ₜ₋ᵢ + Σβⱼ σ²ₜ₋ⱼ`. Se ajustan 6 modelos (GARCH 1,1/1,2/2,1/2,2, GJR-GARCH y
  EGARCH) y se elige el de **menor AIC**. AIC = 2k − 2ln L premia el ajuste y castiga los parámetros.
- **Persistencia**: α+β en GARCH; α + γ/2 + β en GJR (el choque negativo pesa α+γ, en promedio la mitad de las veces);
  β en EGARCH. Si es < 1 el proceso es estacionario y revierte a la **volatilidad de largo plazo** `√(ω/(1−persistencia))`.
- **Vida media de un choque** = ln(0,5)/ln(persistencia): los días que tarda un choque en reducirse a la mitad.
- **Test ARCH-LM de Engle** sobre los residuos estandarizados al cuadrado: se regresa z²ₜ sobre sus rezagos y LM = n·R² ~ χ²(q).
  p > 0,05 → el modelo capturó la heterocedasticidad. (El código viejo usaba `normaltest` con el nombre equivocado.)

### 2.4 VaR y CVaR (Expected Shortfall)
Convención: se reportan como rendimiento negativo; en dinero, |VaR| × capital. α = 1 − nivel de confianza.
| Método | Fórmula / idea | Cuándo sirve |
|---|---|---|
| Paramétrico (normal) | μ + z_α σ | Datos aproximadamente normales |
| Cornish-Fisher | z corregido: z + (z²−1)S/6 + (z³−3z)K/24 − (2z³−5z)S²/36 | Normal ajustada por asimetría S y curtosis K |
| Histórico | Percentil α de los rendimientos reales | No supone distribución |
| Monte Carlo | Simulación con **t de Student** ajustada por máxima verosimilitud (semilla fija) | Colas pesadas. Con una normal solo repetiría el paramétrico |
| CVaR histórico | Promedio de los rendimientos ≤ VaR | Mide qué tan mala es la cola (Basilea III, 97,5 %) |
| CVaR normal | μ − σ φ(z_α)/α | Referencia teórica |

- **Horizonte h días**: regla de la raíz del tiempo, VaR_h ≈ VaR₁·√h (supone días independientes).
- **Portafolio**: VaR con los **pesos del usuario**. Monte Carlo con **normal multivariada** (respeta las correlaciones).
- **Subaditividad / diversificación**: VaR_portafolio ≤ Σ VaR individuales. La diferencia es el ahorro por diversificar.
- **VaR por componentes (Euler)**: CVaRᵢ = wᵢ·∂VaR/∂wᵢ = wᵢ(μᵢ + z(Σw)ᵢ/σ_p). Las contribuciones **suman el VaR
  total** y dicen qué activo aporta más riesgo que su peso.
- **Backtesting de Kupiec (POF)**, **fuera de muestra**: cada día se calcula el VaR solo con los 250 días anteriores
  y se cuenta si la pérdida real lo superó. LR = −2 ln[(1−p)^(n−x) p^x / (1−π)^(n−x) π^x] ~ χ²(1).
  p > 0,05 → VaR bien calibrado. Hacerlo dentro de muestra (como antes) es tautológico. Se agregan **zonas tipo
  Basilea** (verde/amarilla/roja) con la binomial de excepciones.

### 2.5 CAPM
- Regresión de **excesos** de rendimiento: `(Rᵢ − r_f) = α + β(R_m − r_f) + ε`.
- **β** = riesgo sistemático. **α de Jensen** = intercepto anualizado, con su **p-value**: si p > 0,05 puede ser azar.
- **R²** = parte del riesgo explicada por el mercado. Riesgo total² = β²σ²_m (sistemático) + σ²_ε (idiosincrático, diversificable).
- **SML**: E(R) = r_f + β(E[R_m] − r_f). Un punto sobre la línea tiene α > 0.

### 2.6 Markowitz
- Rendimientos simples anualizados μ y covarianza Σ, resueltos con **cvxpy** (optimización convexa).
- **Mínima varianza**: min w'Σw s.a. Σw = 1 (y w ≥ 0 sin cortos).
- **Máximo Sharpe (portafolio tangente)**: maximizar (μ'w − r_f)/√(w'Σw). Se vuelve convexo con el cambio y = κw:
  min y'Σy s.a. (μ − r_f)'y = 1, Σy = κ, κ ≥ 0. **El código original mostraba el de mínima varianza como si fuera
  el de máximo Sharpe**, y además calculaba el Sharpe sin r_f.
- **Frontera eficiente**: solo la rama superior, desde mínima varianza hasta máximo retorno.
- **Línea del mercado de capitales (CML)**: r_f + Sharpe_max·σ, tangente a la frontera en el portafolio de máximo Sharpe.
- **Ventas en corto**: pesos entre −20 % y 120 %. La frontera con cortos siempre queda ≥ que la sin cortos (más libertad
  nunca empeora el óptimo). **Exposición bruta** = Σ|wᵢ| mide el apalancamiento.

### 2.7 Pruebas de estrés
- **Hipotéticos por beta**: impactoᵢ = βᵢ × caída del mercado (−10 %, −20 %, −34 % tipo COVID). β contra el benchmark.
- **Volatilidad × 2**: pérdida al 99 % en 10 días con σ duplicada.
- **Correlaciones → 1**: σ_p sin diversificación = Σ|wᵢ|σᵢ, comparada con la σ_p actual.
- **Históricos**: peor día, peor semana (5) y peor mes (21) **reales** del portafolio, con rendimiento compuesto.

### 2.8 Renta fija
- Precio = Σ CFₖ/(1 + y/m)^k, con m pagos por año (1, 2, 4, 12) y nominal libre. **Cupón cero**: un solo flujo al final.
- **Duración de Macaulay** (años) = Σ (k/m)·VPₖ / P. En un cupón cero es igual al plazo (está en las pruebas).
- **Duración modificada** = D_Mac/(1 + y/m): % de cambio del precio por 1 punto de tasa.
- **Convexidad** = Σ k(k+1)VPₖ / [P(1 + y/m)² m²]. **DV01** = D_mod·P·0,0001.
- Aproximación: ΔP/P ≈ −D_mod·Δy + ½·C·Δy². Se compara contra el **reprecio exacto**.
- YTM: si no se escribe, se **interpola la curva del Tesoro al plazo del bono** (antes se usaba siempre la de 30 años).
- **Nelson-Siegel**: y(t) = β₀ + β₁f₁ + β₂(f₁ − e^(−t/τ)), con β₀ nivel, β₁ pendiente, β₂ curvatura y τ > 0 (L-BFGS-B con límites).

### 2.9 Opciones (Black-Scholes)
- Call = S N(d₁) − K e^(−rT) N(d₂). Put por **paridad put-call** (se verifica que C − P = S − K e^(−rT)).
- Griegas de call y put en unidades interpretables: **theta por día**, **vega y rho por 1 punto porcentual**.
- N(d₂) = probabilidad de ejercicio en la medida neutral al riesgo.
- **Volatilidad implícita** con el método de Brent, verificando los límites de no arbitraje (Newton podía divergir).

### 2.10 Mercado colombiano
- Selector **Estados Unidos (USD) / Colombia (COP)** en la barra lateral. Cambia la moneda de los montos, el
  portafolio de ejemplo, el benchmark sugerido y la tasa libre de riesgo.
- **Tickers BVC** con el sufijo `.CL` de Yahoo: `ECOPETROL.CL`, `PFBCOLOM.CL`, `ISA.CL`, `GEB.CL`, `GRUPOSURA.CL`,
  `CELSIA.CL`, `PFAVAL.CL`, `PFDAVVNDA.CL`, etc. **ADR en USD**: `EC`, `CIB`, `AVAL`; ETF `GXG`.
- **Benchmark**: `^COLCAP` (no se pudo confirmar que Yahoo lo publique), `ICOLCAP.CL` (ETF iShares MSCI COLCAP,
  recomendado) o `GXG`. Opción **"Otro"** para escribir cualquier índice (`^BVSP`, `^MXX`, …). Si Yahoo no tiene
  datos, la barra lateral lo avisa y sugiere una alternativa.
- **Tasa libre de riesgo de Colombia**: FRED `COLIR3TIB01STM` (interbancaria a 3 meses, mensual). Si FRED no
  responde, se usa un respaldo de 9 % y se puede escribir a mano (TES corto o tasa del Banco de la República).
- **Coherencia de moneda**: si mezclas activos `.CL` (COP) con activos en USD, aparece un aviso. El modelo **no
  incluye el riesgo cambiario** (no convierte monedas). Para Colombia en USD, usa los ADR.

### 2.11 Tablero (frontend)
- Navegación lateral por secciones; **solo se ejecuta la página abierta**.
- En cada módulo: KPIs con **semáforo** (●▲■ + texto, nunca solo color), recuadro **"En palabras simples"** con
  frases generadas a partir de los datos y una tabla **📘 "Cómo leer"** con rangos de referencia.
- El semáforo del VaR se **re-escala al nivel de confianza** elegido (z₉₅/z_nivel), para no marcar todo en rojo al subir al 99 %.
- **Colores**: paleta validada para daltonismo en orden fijo. Cada activo **conserva su color** en todas las páginas.
  Los portafolios usan colores de "rol" (negro = tu portafolio, dorado = máximo Sharpe, aguamarina = mínima varianza,
  gris = referencia).
- **Caché**: cada endpoint queda guardado 1 hora según sus parámetros, compartido entre pestañas y usuarios. Al agregar
  un ticker **solo se descarga y calcula ese**. Los precios se revisan una vez al día por ticker y se descargan solo
  los días faltantes.
- Enlaces directos: `?pagina=var`, `?pagina=Markowitz`, etc.

Archivos clave: `backend/app/services/{risk,portfolio,stress,fixed_income,options,macro}.py`,
`backend/app/routers/analisis.py`, `frontend/app.py` (páginas), `frontend/ui.py` (diseño y componentes).

---

## 3. Probarlo en tu PC (Windows, PowerShell)

```powershell
cd Riesgo_API
git fetch origin
git checkout main
git pull
python -m venv .venv
.venv\Scripts\activate
pip install -r backend/requirements.txt
```
- `git fetch` trae las ramas nuevas, `git checkout main` se ubica en la versión principal y `git pull` descarga los cambios.
- Para ver el código original: `git checkout version-original`. Para volver: `git checkout main`.
- El entorno virtual (`.venv`) aísla las librerías del proyecto.

Correr las pruebas (deben pasar las 46):
```powershell
cd backend
python -m pytest tests -q
cd ..
```

Levantar la app con **dos terminales**:
```powershell
# Terminal 1 — API
cd backend
uvicorn app.main:app --reload --port 8000

# Terminal 2 — Tablero
streamlit run frontend/app.py
```
- Abre http://localhost:8501. La API queda en http://localhost:8000/docs.
- Si tienes `FRED_API_KEY` en `backend/.env`, las tasas son reales; si no, se usan valores de respaldo.

### Lista de verificación
- [ ] Resumen ejecutivo carga con datos reales de Yahoo.
- [ ] Cambiar el monto y la confianza (por ejemplo 99 %) cambia los VaR en USD/COP.
- [ ] Agregar un ticker: solo aparece "Preparando datos de <ticker>" y lo demás carga al instante.
- [ ] Markowitz: activar "Permitir ventas en corto" muestra la comparación y las dos fronteras.
- [ ] Renta fija: cupón cero → duración = plazo; probar semestral y otro nominal.
- [ ] Mercado Colombia: carga ECOPETROL.CL, etc.; probar benchmark `^COLCAP` y, si no hay datos, `ICOLCAP.CL`.
- [ ] Verificar en Yahoo que cada ticker `.CL` de la lista tenga datos (algunos pueden haber cambiado de símbolo).

---

## 3b. Probarlo en Ubuntu (terminal)

**Requisito previo — versión de Python:** el proyecto fija `numpy==1.26.4` y `pandas==2.2.2`, que **no tienen
paquetes para Python 3.13**. Usa **Python 3.12**, la misma versión del CI. Ubuntu 24.04 ya trae 3.12;
en Ubuntu 24.10, 25.04 o superior instálalo con `uv`, como se indica abajo.

```bash
# 1. Herramientas del sistema (una sola vez)
sudo apt update
sudo apt install -y git python3-venv python3-pip curl
python3 --version
```
- `apt update` refresca la lista de paquetes; `apt install` instala git, el módulo de entornos virtuales y pip.
- `python3 --version` debe decir 3.12.x. Si dice 3.13 o más, usa la opción con `uv` del paso 3.

```bash
# 2. Clonar (o actualizar) el repositorio
git clone https://github.com/CristianVallejo0104/Riesgo_API.git   # solo la primera vez
cd Riesgo_API
git checkout main
git pull
```

```bash
# 3a. Entorno virtual con Python 3.12 del sistema
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r backend/requirements.txt

# 3b. (Alternativa si tu Ubuntu trae Python 3.13+)
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.local/bin/env
uv venv --python 3.12 .venv
source .venv/bin/activate
uv pip install -r backend/requirements.txt
```
- `source .venv/bin/activate` activa el entorno; el prompt de la terminal mostrará `(.venv)`. Hay que activarlo en cada terminal nueva.
- `uv` descarga Python 3.12 sin tocar el Python del sistema.

```bash
# 4. Variables de entorno (opcional pero recomendado: tasas reales de FRED)
cp backend/.env.example backend/.env
nano backend/.env        # escribe FRED_API_KEY=tu_clave  (gratis en fred.stlouisfed.org)
```

```bash
# 5. Pruebas (deben pasar las 46)
cd backend && python -m pytest tests -q && cd ..
```

```bash
# 6a. Levantar todo con un solo comando (API + tablero)
chmod +x start.sh
./start.sh
# Abre http://localhost:8501   (API en http://localhost:8000/docs)

# 6b. O en dos terminales (útil para ver errores de cada parte)
# Terminal 1:
source .venv/bin/activate && cd backend && uvicorn app.main:app --reload --port 8000
# Terminal 2:
source .venv/bin/activate && streamlit run frontend/app.py
```
- `start.sh` arranca FastAPI en segundo plano, espera a que responda `/health` y luego abre Streamlit.
- Para detenerlo: `Ctrl + C`. Si un puerto queda ocupado: `fuser -k 8000/tcp` o `fuser -k 8501/tcp`.

```bash
# 7. (Opcional) Agente IA local con Ollama
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3
ollama serve      # si no quedó corriendo como servicio
```

**Problemas comunes en Ubuntu**
| Síntoma | Causa | Solución |
|---|---|---|
| `error: externally-managed-environment` | Usaste pip fuera del entorno virtual | Activa `.venv` (`source .venv/bin/activate`) |
| Falla instalando numpy/pandas | Python 3.13+ | Usa la opción 3b con `uv` (Python 3.12) |
| "Backend no disponible" en el tablero | La API no está corriendo | Levanta la terminal 1 o usa `./start.sh` |
| Un ticker `.CL` no trae datos | Yahoo cambió el símbolo | Corrígelo en `TICKERS_DB` de `frontend/app.py` |
| Tasas en "valor de respaldo" | Falta `FRED_API_KEY` | Agrégala en `backend/.env` y reinicia la API |

---

## 4. Ramas: qué se hizo y cómo deshacerlo si hace falta

- El código nuevo **ya está en `main`**. Se hizo un *fast-forward*: `main` avanzó a los commits nuevos sin crear commits extra.
- El código inicial quedó en la rama **`version-original`** (commit `770ec14`).
- **Despliegue:** Streamlit Cloud y Render toman `main`, así que se redespliegan con la versión nueva (si no, usa "Reboot").
  El frontend necesita `frontend/ui.py` (ya está en el repo).
- **Si quieres volver al código original en `main`** (no recomendado, pero posible sin perder nada):
  ```powershell
  git checkout main
  git revert --no-edit 770ec14..HEAD
  git push
  ```
  `git revert` crea commits nuevos que deshacen los cambios, así que el historial no se pierde.

---

## 5. Prompt para Claude Desktop / Claude Code (Windows)

Copia y pega esto al abrir el proyecto en tu PC:

```text
Estoy trabajando en mi proyecto RiskLab USTA (FastAPI + Streamlit), un sistema de análisis de riesgo
financiero para la universidad. El repositorio está en mi PC. La rama `main` tiene la versión nueva (v2.1) y la rama
`version-original` tiene el código inicial (commit 770ec14).

Lee primero docs/CONTEXTO_CLAUDE.md: ahí está todo lo que se cambió y la teoría detrás. En resumen:
- Backend (backend/app/services): VaR paramétrico, Cornish-Fisher, histórico y Monte Carlo t-Student; CVaR;
  backtesting de Kupiec fuera de muestra; EWMA y 6 modelos GARCH elegidos por AIC con ARCH-LM; CAPM con
  regresión de excesos; Markowitz con máximo Sharpe real (cvxpy) y ventas en corto; VaR de portafolio con
  contribuciones de Euler; stress test por betas, volatilidad, correlaciones y peores ventanas; bonos con
  frecuencia, nominal y cupón cero; Black-Scholes con griegas call/put; tasa libre de riesgo de EE. UU. o
  Colombia (FRED).
- Frontend (frontend/app.py + frontend/ui.py): navegación por secciones, semáforos, recuadros "En palabras
  simples", tablas "Cómo leer", colores estables por activo, caché incremental y selector de mercado
  EE. UU./Colombia.
- Pruebas: backend/tests (46 pruebas, incluyendo propiedades teóricas en test_teoria_riesgo.py).

Quiero que:
1. Me ayudes a correr la app en mi PC (Windows) y verificar que todo funciona con datos reales de Yahoo
   Finance, siguiendo la lista de verificación de la sección 3 del documento.
2. Verifiques que los tickers colombianos (.CL) y el benchmark ^COLCAP / ICOLCAP.CL tengan datos en Yahoo;
   si alguno no existe, corrige la lista en TICKERS_DB y BENCHMARKS_CO de frontend/app.py.
3. Me ayudes a seguir mejorando el proyecto sobre main, explicando la teoría de riesgo detrás de cada cambio.

Explícame el porqué de cada paso y los comandos línea por línea. Responde en español latinoamericano neutro, sin voseo.
```

### Prompt para Ubuntu

```text
Estoy en Ubuntu y trabajo en mi proyecto RiskLab USTA (FastAPI + Streamlit), un sistema de análisis de riesgo
financiero para la universidad. Repositorio: https://github.com/CristianVallejo0104/Riesgo_API
- Rama main = versión nueva (v2.1), la principal.
- Rama version-original = código inicial (commit 770ec14), solo como respaldo.

Lee primero docs/CONTEXTO_CLAUDE.md (secciones 2 y 3b): ahí está la teoría de cada cálculo y los pasos para Ubuntu.
Resumen del proyecto:
- Backend (backend/app/services): VaR paramétrico, Cornish-Fisher, histórico y Monte Carlo t-Student; CVaR;
  backtesting de Kupiec fuera de muestra; EWMA y 6 modelos GARCH por AIC con test ARCH-LM; CAPM con regresión
  de excesos; Markowitz con máximo Sharpe real (cvxpy) y ventas en corto; VaR de portafolio con contribuciones
  de Euler; stress test por betas, volatilidad, correlaciones y peores ventanas; bonos con frecuencia, nominal y
  cupón cero; Black-Scholes con griegas call/put; tasa libre de riesgo de EE. UU. o Colombia (FRED).
- Frontend (frontend/app.py + frontend/ui.py): 16 páginas con semáforos, "En palabras simples" y tablas
  "Cómo leer"; colores estables por activo; caché incremental; selector de mercado EE. UU. (USD) / Colombia (COP).
- Pruebas: backend/tests (46 pruebas, con propiedades teóricas en test_teoria_riesgo.py).
- Importante: requirements.txt fija numpy 1.26.4 y pandas 2.2.2, que necesitan Python 3.12 (no 3.13).

Quiero que, paso a paso:
1. Revises mi versión de Ubuntu y de Python (lsb_release -a, python3 --version) y me digas si uso el Python
   del sistema o uv con Python 3.12.
2. Me ayudes a crear el entorno virtual, instalar dependencias, configurar backend/.env con FRED_API_KEY,
   correr las 46 pruebas y levantar la app con ./start.sh (o en dos terminales).
3. Verifiquemos con datos reales de Yahoo Finance la lista de la sección 3: monto y confianza del VaR,
   agregar un ticker (solo debe descargar ese), ventas en corto en Markowitz, cupón cero y frecuencias en
   renta fija, y el mercado Colombia.
4. Compruebes que los tickers colombianos (.CL) y el benchmark ^COLCAP / ICOLCAP.CL tengan datos en Yahoo; si
   alguno no existe, corrige TICKERS_DB y BENCHMARKS_CO en frontend/app.py, corre las pruebas y haz commit en main.
5. Revises que el CI de GitHub Actions haya pasado en main y, si falló, lo corrijamos.

Explícame el porqué de cada paso y los comandos línea por línea. Si algo falla, muéstrame el error completo
antes de proponer el arreglo. Responde en español latinoamericano neutro, sin voseo.
```
