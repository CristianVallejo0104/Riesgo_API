"""
backend/app/routers/agente.py — RiskLab USTA CIII
Agente IA local con Ollama para análisis financiero en lenguaje natural.
"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
import requests
import os

router = APIRouter(prefix="/agente", tags=["Agente IA"])

OLLAMA_URL  = os.getenv("OLLAMA_URL",  "http://localhost:11434/api/generate")
OLLAMA_TAGS = os.getenv("OLLAMA_TAGS", "http://localhost:11434/api/tags")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")


# ── Helper ────────────────────────────────────────────────────────────────────

def _llamar_ollama(prompt: str) -> str:
    """Envía un prompt al modelo local via Ollama y retorna la respuesta."""
    try:
        r = requests.post(
            OLLAMA_URL,
            json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
            timeout=180,
        )
        r.raise_for_status()
        return r.json().get("response", "Sin respuesta del modelo.")
    except requests.exceptions.ConnectionError:
        raise HTTPException(
            status_code=503,
            detail="Ollama no disponible. Ejecuta 'ollama serve' en tu terminal.",
        )
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Error del modelo: {str(e)}")


# ── Schemas ───────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    pregunta: str
    contexto: Optional[str] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/estado")
def estado_ollama():
    """Verifica si Ollama está disponible y lista los modelos instalados."""
    try:
        r = requests.get(OLLAMA_TAGS, timeout=5)
        modelos = [m["name"] for m in r.json().get("models", [])]
        return {"disponible": True, "modelo_activo": OLLAMA_MODEL, "modelos": modelos}
    except Exception:
        return {"disponible": False, "modelo_activo": OLLAMA_MODEL, "modelos": []}


@router.get("/analisis")
def analisis_portafolio(
    tickers:          list[str] = Query(...),
    benchmark:        str       = Query("^GSPC"),
    var_historico:    float     = Query(...),
    cvar:             float     = Query(...),
    sharpe:           float     = Query(...),
    retorno_anual:    float     = Query(...),
    volatilidad_anual: float    = Query(...),
    beta_promedio:    float     = Query(...),
    inversion:        float     = Query(100_000.0),
):
    """Genera un informe ejecutivo de riesgo usando llama3."""
    perdida_var  = abs(var_historico)  * inversion
    perdida_cvar = abs(cvar) * inversion

    clasificacion_riesgo = (
        "ALTO"   if abs(var_historico) > 0.025 else
        "MEDIO"  if abs(var_historico) > 0.015 else
        "BAJO"
    )
    clasificacion_beta = (
        "AGRESIVO (amplifica movimientos del mercado)"  if beta_promedio > 1.2 else
        "DEFENSIVO (menos volátil que el mercado)"      if beta_promedio < 0.8 else
        "NEUTRO (correlacionado con el mercado)"
    )

    prompt = f"""Eres RiskLab AI, un analista de riesgo financiero cuantitativo senior.
Analiza el siguiente portafolio de renta variable y redacta un informe ejecutivo profesional en español.

═══════════════════════════════════════
DATOS DEL PORTAFOLIO
═══════════════════════════════════════
Activos       : {', '.join(tickers)}
Benchmark     : {benchmark}
Inversión     : ${inversion:,.0f} USD

MÉTRICAS DE RIESGO (NIVEL DE CONFIANZA 95%):
• VaR Histórico diario : {var_historico*100:.4f}%  →  pérdida máxima estimada: ${perdida_var:,.0f}
• CVaR / Exp. Shortfall: {cvar*100:.4f}%            →  pérdida en escenario extremo: ${perdida_cvar:,.0f}
• Clasificación riesgo : {clasificacion_riesgo}

MÉTRICAS DE MERCADO:
• Beta promedio        : {beta_promedio:.3f}  ({clasificacion_beta})
• Retorno anual esp.   : {retorno_anual*100:.2f}%
• Volatilidad anual    : {volatilidad_anual*100:.2f}%
• Sharpe Ratio         : {sharpe:.4f}
═══════════════════════════════════════

Redacta el informe con EXACTAMENTE estas 5 secciones (usa los emojis como encabezados):

🎯 EVALUACIÓN GENERAL DEL RIESGO
Interpreta el nivel de riesgo global del portafolio.

📊 ANÁLISIS VaR Y CVaR
Explica qué significan estas cifras para el inversor en términos prácticos y monetarios.

📈 EXPOSICIÓN AL MERCADO (BETA)
Analiza la sensibilidad del portafolio frente al benchmark y sus implicaciones.

⚡ EFICIENCIA RIESGO-RETORNO
Evalúa el Sharpe Ratio y si la compensación riesgo-retorno es adecuada.

💡 RECOMENDACIONES
Da 3 recomendaciones concretas de gestión de riesgo basadas en los datos.

Sé directo, profesional y usa terminología financiera apropiada. Máximo 400 palabras."""

    respuesta = _llamar_ollama(prompt)
    return {
        "analisis":   respuesta,
        "modelo":     OLLAMA_MODEL,
        "portafolio": tickers,
        "riesgo":     clasificacion_riesgo,
    }


@router.post("/chat")
def chat_financiero(body: ChatRequest):
    """Chat con el agente sobre el portafolio y conceptos de riesgo."""
    system = (
        "Eres RiskLab AI, asistente especializado en análisis de riesgo financiero cuantitativo. "
        "Dominas: VaR, CVaR, CAPM, Beta, Markowitz, GARCH, EWMA, renta fija (duración, convexidad), "
        "opciones Black-Scholes y stress testing. "
        "Respondes SIEMPRE en español, de forma concisa y profesional (máximo 150 palabras). "
        "Si no conoces algo, lo dices claramente sin inventar."
    )

    prompt = f"{system}\n\n"
    if body.contexto:
        prompt += f"CONTEXTO DEL PORTAFOLIO:\n{body.contexto}\n\n"
    prompt += f"PREGUNTA: {body.pregunta}\n\nRESPUESTA:"

    respuesta = _llamar_ollama(prompt)
    return {"respuesta": respuesta, "modelo": OLLAMA_MODEL}