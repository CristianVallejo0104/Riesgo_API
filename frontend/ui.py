"""
frontend/ui.py — Sistema de diseño de RiskLab USTA.

Reúne en un solo lugar los estilos, colores y componentes visuales para que
todas las páginas se vean consistentes:
  * hero(), encabezado()        -> títulos de página
  * kpi_grid()                  -> tarjetas de métricas con semáforo
  * guia_lectura()              -> tabla "cómo leer este resultado"
  * en_simple(), nota()         -> recuadros explicativos para no expertos
  * layout()                    -> estilo común de los gráficos Plotly
"""
from __future__ import annotations

import html

import streamlit as st

# ─────────────────────────── Paleta ───────────────────────────
# Colores categóricos en ORDEN FIJO (validados para daltonismo).
# Cada activo conserva siempre el mismo color en todos los gráficos.
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]

# Colores de estado: reservados para el semáforo (nunca para series).
ESTADO = {
    "bueno": "#0ca30c",
    "alerta": "#fab219",
    "serio": "#ec835a",
    "critico": "#d03b3b",
    "neutral": "#898781",
}
ICONO_ESTADO = {"bueno": "●", "alerta": "▲", "serio": "▲", "critico": "■", "neutral": "○"}
TEXTO_ESTADO = {"bueno": "Favorable", "alerta": "Atención", "serio": "Elevado",
                "critico": "Crítico", "neutral": "Informativo"}

AZUL = "#2a78d6"
NARANJA = "#eb6834"
TINTA = "#0b0b0b"
TINTA_2 = "#52514e"
TINTA_3 = "#898781"
GRILLA = "#e1e0d9"
EJE = "#c3c2b7"
SUPERFICIE = "#fcfcfb"
DIVERGENTE = [[0, "#d03b3b"], [0.5, "#f0efec"], [1, "#2a78d6"]]   # rojo - gris - azul
SECUENCIAL = [[0, "#cde2fb"], [0.5, "#3987e5"], [1, "#0d366b"]]


def color_activo(ticker: str, tickers: list[str]) -> str:
    """El color sigue a la entidad, no a su posición en un ranking."""
    try:
        return SERIES[tickers.index(ticker) % len(SERIES)]
    except ValueError:
        return TINTA_3


# ─────────────────────────── Formatos ───────────────────────────
def pct(x, dec: int = 2, signo: bool = False) -> str:
    if x is None:
        return "—"
    return f"{x * 100:+.{dec}f}%" if signo else f"{x * 100:.{dec}f}%"


def usd(x, dec: int = 0) -> str:
    if x is None:
        return "—"
    return f"USD {x:,.{dec}f}"


def num(x, dec: int = 2) -> str:
    return "—" if x is None else f"{x:,.{dec}f}"


# ─────────────────────────── CSS global ───────────────────────────
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

:root {
  --rl-ink: #0b0b0b; --rl-ink-2: #52514e; --rl-ink-3: #898781;
  --rl-surface: #ffffff; --rl-plane: #f6f7f9; --rl-line: #e4e6eb;
  --rl-brand: #1c5cab; --rl-brand-2: #2a78d6; --rl-brand-soft: #eaf2fc;
  --rl-good: #0ca30c; --rl-warn: #fab219; --rl-serious: #ec835a; --rl-crit: #d03b3b;
  --rl-radius: 12px;
}
html, body, [class*="css"], .stMarkdown, .stText, button, input, textarea, select {
  font-family: 'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif;
}
.stApp { background: var(--rl-plane); }
#MainMenu, footer { visibility: hidden; }
header[data-testid="stHeader"] { background: transparent; }
.block-container { padding-top: 1.6rem; padding-bottom: 3rem; max-width: 1320px; }

/* ── Sidebar ── */
section[data-testid="stSidebar"] { background: #0f1b2d; }
section[data-testid="stSidebar"] * { color: #dbe3ee; }
section[data-testid="stSidebar"] .stMarkdown h1,
section[data-testid="stSidebar"] .stMarkdown h2,
section[data-testid="stSidebar"] .stMarkdown h3 { color: #ffffff; }
section[data-testid="stSidebar"] input, section[data-testid="stSidebar"] textarea,
section[data-testid="stSidebar"] [data-baseweb="select"] > div,
section[data-testid="stSidebar"] [data-baseweb="input"] > div {
  background: #18273d !important; color: #fff !important; border-color: #2b3d57 !important;
}
section[data-testid="stSidebar"] [data-baseweb="select"] div { background-color: #18273d !important; }
section[data-testid="stSidebar"] input::placeholder { color: #7f93ae !important; opacity: 1; }
section[data-testid="stSidebar"] [data-testid="stExpander"] summary,
section[data-testid="stSidebar"] [data-testid="stExpander"] details { background: #132238 !important; }
section[data-testid="stSidebar"] [data-testid="stExpander"] summary * { color: #ffffff !important; }
section[data-testid="stSidebar"] .stButton > button { background: #18273d; border: 1px solid #2b3d57; color: #fff; }
section[data-testid="stSidebar"] .stButton > button:hover { border-color: #2a78d6; background: #1c3150; }
section[data-testid="stSidebar"] .stButton > button * { color: #fff !important; }
section[data-testid="stSidebar"] [data-baseweb="tag"],
section[data-testid="stSidebar"] [data-baseweb="tag"] div { background: #2a78d6 !important; }
section[data-testid="stSidebar"] [data-baseweb="tag"] * { color: #fff !important; }
section[data-testid="stSidebar"] hr { border-color: #24354d; }
section[data-testid="stSidebar"] [data-testid="stExpander"] {
  background: #132238 !important; border: 1px solid #24354d !important;
}
section[data-testid="stSidebar"] [role="radiogroup"] label {
  padding: 6px 10px; border-radius: 8px; margin: 1px 0; width: 100%;
}
section[data-testid="stSidebar"] [role="radiogroup"] label:hover { background: #18273d; }
section[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) {
  background: #2a78d6;
}
section[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) * { color: #fff !important; }
.rl-side-brand { display:flex; align-items:center; gap:10px; margin: 4px 0 14px; }
.rl-side-brand .logo { width:36px; height:36px; border-radius:10px; display:grid; place-items:center;
  background: linear-gradient(135deg,#2a78d6,#1c5cab); font-weight:700; color:#fff; font-size:15px; }
.rl-side-brand .t1 { font-weight:700; font-size:16px; color:#fff; line-height:1.1; }
.rl-side-brand .t2 { font-size:11.5px; color:#8fa3bf; }
.rl-side-label { font-size:10.5px; letter-spacing:.08em; text-transform:uppercase; color:#8fa3bf !important;
  font-weight:600; margin: 14px 0 4px; }

/* ── Hero ── */
.rl-hero { background: linear-gradient(120deg,#0f1b2d 0%,#16335a 55%,#1c5cab 100%);
  border-radius: 16px; padding: 22px 28px; color: #fff; margin-bottom: 18px;
  box-shadow: 0 8px 30px rgba(15,27,45,.18); position: relative; overflow: hidden; }
.rl-hero:after { content:""; position:absolute; right:-60px; top:-60px; width:240px; height:240px;
  border-radius:50%; background: radial-gradient(circle, rgba(255,255,255,.12), transparent 70%); }
.rl-hero .eyebrow { font-size: 11.5px; letter-spacing: .1em; text-transform: uppercase; color: #a9c4ea; font-weight:600; }
.rl-hero h1 { color:#fff; font-size: 1.65rem; font-weight: 700; margin: 4px 0 6px; padding:0; }
.rl-hero p { color: #d6e2f3; margin: 0; font-size: .92rem; max-width: 900px; }
.rl-chips { display:flex; flex-wrap:wrap; gap:6px; margin-top: 12px; }
.rl-chip { background: rgba(255,255,255,.12); border: 1px solid rgba(255,255,255,.18);
  color:#fff; font-size: 11.5px; padding: 3px 10px; border-radius: 999px; }

/* ── Encabezado de sección ── */
.rl-h { margin: 22px 0 10px; }
.rl-h .t { font-size: 1.12rem; font-weight: 700; color: var(--rl-ink); }
.rl-h .s { font-size: .86rem; color: var(--rl-ink-2); margin-top: 2px; }

/* ── KPI cards ── */
.rl-kpis { display:grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 12px; margin: 6px 0 8px; }
.rl-kpi { background: var(--rl-surface); border: 1px solid var(--rl-line); border-radius: var(--rl-radius);
  padding: 14px 16px 12px; box-shadow: 0 1px 2px rgba(16,24,40,.04); position: relative; }
.rl-kpi .lab { font-size: 11.5px; font-weight: 600; color: var(--rl-ink-2); text-transform: uppercase; letter-spacing: .04em; }
.rl-kpi .val { font-size: 1.55rem; font-weight: 700; color: var(--rl-ink); margin-top: 4px; line-height: 1.15; }
.rl-kpi .sub { font-size: 12px; color: var(--rl-ink-2); margin-top: 4px; }
.rl-kpi .tag { display:inline-flex; align-items:center; gap:5px; font-size: 11px; font-weight: 600;
  margin-top: 8px; padding: 2px 8px; border-radius: 999px; background:#f2f3f5; color: var(--rl-ink); }
.rl-kpi .bar { position:absolute; left:0; top:12px; bottom:12px; width:3px; border-radius: 0 3px 3px 0; }

/* ── Recuadros ── */
.rl-box { border-radius: var(--rl-radius); padding: 14px 16px; margin: 8px 0 12px; font-size: .9rem;
  line-height: 1.55; border: 1px solid var(--rl-line); background: var(--rl-surface); color: var(--rl-ink); }
.rl-box .bt { font-weight: 700; margin-bottom: 4px; display:flex; align-items:center; gap:8px; }
.rl-simple { background: #f3f8fe; border-color: #cde2fb; }
.rl-simple .bt { color: #1c5cab; }
.rl-warn { background: #fff8e8; border-color: #f6dc9b; }
.rl-warn .bt { color: #8a5a00; }
.rl-ok { background: #effaf0; border-color: #bfe6c1; }
.rl-ok .bt { color: #006300; }
.rl-bad { background: #fdf0f0; border-color: #f2c4c4; }
.rl-bad .bt { color: #9b2222; }

/* ── Guía de lectura ── */
.rl-guide { background: var(--rl-surface); border: 1px solid var(--rl-line); border-radius: var(--rl-radius);
  overflow: hidden; margin: 8px 0 16px; }
.rl-guide .gh { padding: 12px 16px; border-bottom: 1px solid var(--rl-line); background: #fafbfc;
  font-weight: 700; font-size: .95rem; display:flex; align-items:center; gap:8px; }
.rl-guide table { width: 100%; border-collapse: collapse; font-size: .85rem; }
.rl-guide th { text-align: left; font-size: 11px; text-transform: uppercase; letter-spacing: .05em;
  color: var(--rl-ink-2); padding: 9px 14px; border-bottom: 1px solid var(--rl-line); background: #fff; }
.rl-guide td { padding: 10px 14px; border-bottom: 1px solid #f0f1f3; vertical-align: top; color: var(--rl-ink); line-height: 1.45; }
.rl-guide tr:last-child td { border-bottom: none; }
.rl-guide td:first-child { font-weight: 600; white-space: nowrap; }
.rl-guide .lvl { display:inline-flex; align-items:center; gap:6px; white-space: nowrap; font-weight:600; }

/* ── Tarjetas de módulo (inicio) ── */
.rl-mods { display:grid; grid-template-columns: repeat(auto-fit,minmax(250px,1fr)); gap: 12px; }
.rl-mod { background: var(--rl-surface); border: 1px solid var(--rl-line); border-radius: var(--rl-radius); padding: 14px 16px; }
.rl-mod .mt { font-weight: 700; font-size: .95rem; }
.rl-mod .mq { color: var(--rl-brand); font-size: .84rem; margin: 4px 0 6px; font-style: italic; }
.rl-mod .md { color: var(--rl-ink-2); font-size: .84rem; line-height: 1.45; }
.rl-steps { display:grid; grid-template-columns: repeat(auto-fit,minmax(220px,1fr)); gap: 12px; }
.rl-step { background: var(--rl-surface); border: 1px solid var(--rl-line); border-radius: var(--rl-radius); padding: 14px 16px; }
.rl-step .n { width: 26px; height: 26px; border-radius: 50%; background: var(--rl-brand-soft); color: var(--rl-brand);
  display:grid; place-items:center; font-weight:700; font-size: 13px; margin-bottom: 8px; }
.rl-step .st { font-weight: 700; font-size: .92rem; }
.rl-step .sd { color: var(--rl-ink-2); font-size: .84rem; margin-top: 3px; line-height: 1.45; }

/* ── Widgets nativos ── */
[data-testid="stMetric"] { background: var(--rl-surface); border: 1px solid var(--rl-line);
  border-radius: var(--rl-radius); padding: 12px 14px; }
[data-testid="stMetricLabel"] p { font-size: 12px !important; font-weight: 600 !important; color: var(--rl-ink-2) !important; }
[data-testid="stMetricValue"] { font-size: 1.4rem !important; font-weight: 700 !important; }
[data-testid="stExpander"] { background: var(--rl-surface); border: 1px solid var(--rl-line) !important; border-radius: var(--rl-radius) !important; }
[data-testid="stPlotlyChart"], [data-testid="stDataFrame"] {
  background: var(--rl-surface); border: 1px solid var(--rl-line); border-radius: var(--rl-radius); padding: 6px; }
.stButton > button, .stDownloadButton > button { border-radius: 9px; font-weight: 600; }
.stButton > button[kind="primary"] { background: var(--rl-brand-2); border-color: var(--rl-brand-2); }
.stTabs [data-baseweb="tab-list"] { gap: 4px; border-bottom: 1px solid var(--rl-line); }
.stTabs [data-baseweb="tab"] { font-weight: 600; font-size: .88rem; padding: 8px 14px; }
</style>
"""


def aplicar_estilos():
    st.markdown(CSS, unsafe_allow_html=True)


# ─────────────────────────── Componentes ───────────────────────────
def _e(texto) -> str:
    """Escapa texto para HTML, permitiendo **negritas** estilo markdown."""
    t = html.escape(str(texto))
    partes = t.split("**")
    return "".join(f"<b>{p}</b>" if i % 2 else p for i, p in enumerate(partes))


def hero(titulo: str, descripcion: str, eyebrow: str = "RiskLab USTA", chips: list[str] | None = None):
    chips_html = "".join(f'<span class="rl-chip">{_e(c)}</span>' for c in (chips or []))
    st.markdown(
        f'<div class="rl-hero"><div class="eyebrow">{_e(eyebrow)}</div><h1>{_e(titulo)}</h1>'
        f'<p>{_e(descripcion)}</p>{"<div class=rl-chips>" + chips_html + "</div>" if chips_html else ""}</div>',
        unsafe_allow_html=True)


def encabezado(titulo: str, subtitulo: str = ""):
    st.markdown(f'<div class="rl-h"><div class="t">{_e(titulo)}</div>'
                f'{f"<div class=s>{_e(subtitulo)}</div>" if subtitulo else ""}</div>',
                unsafe_allow_html=True)


def kpi_grid(items: list[dict]):
    """items: [{label, value, sub?, estado?: bueno|alerta|serio|critico|neutral, tag?}]"""
    cards = []
    for it in items:
        est = it.get("estado")
        bar = f'<div class="bar" style="background:{ESTADO[est]}"></div>' if est else ""
        tag = ""
        if est:
            txt = it.get("tag") or TEXTO_ESTADO[est]
            tag = (f'<div class="tag"><span style="color:{ESTADO[est]}">{ICONO_ESTADO[est]}</span>'
                   f'{_e(txt)}</div>')
        sub = f'<div class="sub">{_e(it["sub"])}</div>' if it.get("sub") else ""
        cards.append(f'<div class="rl-kpi">{bar}<div class="lab">{_e(it["label"])}</div>'
                     f'<div class="val">{_e(it["value"])}</div>{sub}{tag}</div>')
    st.markdown(f'<div class="rl-kpis">{"".join(cards)}</div>', unsafe_allow_html=True)


def _box(clase: str, titulo: str, texto: str, icono: str):
    st.markdown(f'<div class="rl-box {clase}"><div class="bt">{icono} {_e(titulo)}</div>'
                f'<div>{_e(texto)}</div></div>', unsafe_allow_html=True)


def en_simple(texto: str, titulo: str = "En palabras simples"):
    _box("rl-simple", titulo, texto, "💬")


def nota(texto: str, tipo: str = "warn", titulo: str | None = None):
    clases = {"warn": ("rl-warn", "⚠️", "Ten en cuenta"), "ok": ("rl-ok", "✅", "Buena señal"),
              "bad": ("rl-bad", "⛔", "Alerta"), "info": ("rl-simple", "ℹ️", "Dato útil")}
    c, ico, t = clases[tipo]
    _box(c, titulo or t, texto, ico)


def guia_lectura(titulo: str, filas: list[dict], columnas: tuple = ("Indicador", "Qué mide", "Cómo leerlo")):
    """Tabla de lectura. Cada fila es un dict con las claves de `columnas`.
    Si una celda es una tupla (estado, texto) se pinta con el ícono del semáforo."""
    def celda(v):
        if isinstance(v, tuple):
            est, txt = v
            return (f'<span class="lvl"><span style="color:{ESTADO[est]}">{ICONO_ESTADO[est]}</span>'
                    f'{_e(txt)}</span>')
        return _e(v)
    th = "".join(f"<th>{_e(c)}</th>" for c in columnas)
    trs = "".join("<tr>" + "".join(f"<td>{celda(f.get(c, ''))}</td>" for c in columnas) + "</tr>" for f in filas)
    st.markdown(f'<div class="rl-guide"><div class="gh">📘 {_e(titulo)}</div>'
                f'<table><thead><tr>{th}</tr></thead><tbody>{trs}</tbody></table></div>',
                unsafe_allow_html=True)


def tarjetas_modulos(mods: list[dict]):
    html_mods = "".join(
        f'<div class="rl-mod"><div class="mt">{_e(m["titulo"])}</div><div class="mq">“{_e(m["pregunta"])}”</div>'
        f'<div class="md">{_e(m["desc"])}</div></div>' for m in mods)
    st.markdown(f'<div class="rl-mods">{html_mods}</div>', unsafe_allow_html=True)


def pasos(items: list[tuple[str, str]]):
    html_p = "".join(f'<div class="rl-step"><div class="n">{i}</div><div class="st">{_e(t)}</div>'
                     f'<div class="sd">{_e(d)}</div></div>' for i, (t, d) in enumerate(items, 1))
    st.markdown(f'<div class="rl-steps">{html_p}</div>', unsafe_allow_html=True)


# ─────────────────────────── Plotly ───────────────────────────
def layout(titulo: str = "", height: int = 360, xaxis_title: str = "", yaxis_title: str = "",
           legend: bool = True, **extra) -> dict:
    base = {
        "title": {"text": titulo, "font": {"size": 14, "color": TINTA}, "x": 0.01, "xanchor": "left"},
        "paper_bgcolor": "white",
        "plot_bgcolor": "white",
        "height": height,
        "margin": dict(l=56, r=20, t=56 if titulo else 24, b=44),
        "font": {"family": "Inter, system-ui, sans-serif", "color": TINTA_2, "size": 12},
        "xaxis": {"title": {"text": xaxis_title, "font": {"size": 12, "color": TINTA_2}},
                  "gridcolor": GRILLA, "linecolor": EJE, "zerolinecolor": EJE,
                  "tickfont": {"size": 11, "color": TINTA_3}, "showgrid": False},
        "yaxis": {"title": {"text": yaxis_title, "font": {"size": 12, "color": TINTA_2}},
                  "gridcolor": GRILLA, "linecolor": EJE, "zerolinecolor": EJE,
                  "tickfont": {"size": 11, "color": TINTA_3}},
        "showlegend": legend,
        "legend": {"orientation": "h", "yanchor": "bottom", "y": 1.0, "xanchor": "right", "x": 1,
                   "font": {"size": 11, "color": TINTA_2}, "bgcolor": "rgba(0,0,0,0)"},
        "hoverlabel": {"bgcolor": "white", "bordercolor": GRILLA, "font": {"size": 12, "color": TINTA}},
        "hovermode": "closest",
    }
    base.update(extra)
    return base
