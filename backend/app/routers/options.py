from fastapi import APIRouter, HTTPException, Query
from app.services.options import OptionsService
from app.models.schemas import OptionResponse

router = APIRouter(prefix="/opciones", tags=["Opciones"])


@router.get("/black-scholes", response_model=OptionResponse)
def calcular_black_scholes(
    S: float = Query(default=100, gt=0, description="Precio Spot del activo subyacente (debe ser > 0)"),
    K: float = Query(default=100, gt=0, description="Precio de ejercicio Strike (debe ser > 0)"),
    T: float = Query(default=1, gt=0, le=50, description="Tiempo al vencimiento en años (debe ser > 0)"),
    r: float = Query(default=0.04, ge=-0.20, le=1.0, description="Tasa libre de riesgo (puede ser negativa)"),
    sigma: float = Query(default=0.2, gt=0, le=5.0, description="Volatilidad anualizada (debe ser > 0)")
):
    if S <= 0:
        raise HTTPException(status_code=422, detail="El precio Spot (S) debe ser mayor a 0.")
    if K <= 0:
        raise HTTPException(status_code=422, detail="El Strike (K) debe ser mayor a 0.")
    if T <= 0:
        raise HTTPException(status_code=422, detail="El tiempo (T) debe ser mayor a 0.")
    if sigma <= 0:
        raise HTTPException(status_code=422, detail="La volatilidad (sigma) debe ser mayor a 0.")

    servicio = OptionsService(S, K, T, r, sigma)
    return {
        "parametros": {"S": S, "K": K, "T": T, "r": r, "sigma": sigma},
        "precios": servicio.black_scholes(),
        "greeks": servicio.greeks(),
    }


@router.get("/volatilidad-implicita")
def calcular_vol_implicita(
    S: float = Query(default=100, gt=0, description="Precio Spot (debe ser > 0)"),
    K: float = Query(default=100, gt=0, description="Strike (debe ser > 0)"),
    T: float = Query(default=1, gt=0, le=50, description="Tiempo en años (debe ser > 0)"),
    r: float = Query(default=0.04, ge=-0.20, le=1.0, description="Tasa libre de riesgo"),
    precio_mercado: float = Query(default=10, gt=0, description="Precio de mercado de la opción (debe ser > 0)"),
    tipo: str = Query(default="call", pattern="^(call|put)$", description="Tipo de opción: 'call' o 'put'")
):
    if precio_mercado <= 0:
        raise HTTPException(status_code=422, detail="El precio de mercado debe ser mayor a 0.")

    servicio = OptionsService(S, K, T, r, 0.2)
    vol = servicio.volatilidad_implicita(precio_mercado, tipo)
    return {
        "volatilidad_implicita": vol,
        "precio_mercado": precio_mercado,
        "tipo": tipo,
    }