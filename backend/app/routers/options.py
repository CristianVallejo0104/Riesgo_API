from fastapi import APIRouter

from app.services.options import OptionsService
from app.models.schemas import OptionResponse

router = APIRouter(prefix="/opciones", tags=["Opciones"])


@router.get("/black-scholes", response_model=OptionResponse)
def calcular_black_scholes(S: float = 100, K: float = 100, T: float = 1, r: float = 0.04, sigma: float = 0.2):
    servicio = OptionsService(S, K, T, r, sigma)
    return {
        "parametros": {"S": S, "K": K, "T": T, "r": r, "sigma": sigma},
        "precios": servicio.black_scholes(),
        "greeks": servicio.greeks(),
    }


@router.get("/volatilidad-implicita")
def calcular_vol_implicita(S: float = 100, K: float = 100, T: float = 1, r: float = 0.04, precio_mercado: float = 10, tipo: str = "call"):
    servicio = OptionsService(S, K, T, r, 0.2)
    vol = servicio.volatilidad_implicita(precio_mercado, tipo)
    return {
        "volatilidad_implicita": vol,
        "precio_mercado": precio_mercado,
        "tipo": tipo,
    }


