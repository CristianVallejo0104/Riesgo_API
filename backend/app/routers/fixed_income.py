from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from app.services.fixed_income import FixedIncomeService
from app.services.macro import MacroService

router = APIRouter(prefix="/renta-fija", tags=["Renta Fija"])


# ── Schema de validación Pydantic ──────────────────────────────────────────
class BondParams(BaseModel):
    tasa_cupon: float = Field(
        default=0.05,
        ge=-0.50,   # Bonos con cupón negativo existen (Suiza, Japón)
        le=1.0,
        description="Tasa cupón anual. Entre -50% y 100%."
    )
    vencimiento: int = Field(
        default=10,
        ge=1,       # Mínimo 1 año
        le=100,     # Máximo 100 años
        description="Años al vencimiento. Debe ser positivo."
    )

    @field_validator("vencimiento")
    @classmethod
    def vencimiento_positivo(cls, v):
        if v <= 0:
            raise ValueError("El vencimiento debe ser mayor a 0 años.")
        return v

    @field_validator("tasa_cupon")
    @classmethod
    def tasa_cupon_razonable(cls, v):
        if v > 1.0:
            raise ValueError("La tasa cupón no puede superar el 100%.")
        return v


# ── Endpoints ──────────────────────────────────────────────────────────────

@router.get("/nelson-siegel")
def calcular_nelson_siegel():
    plazos = [0.25, 1, 2, 5, 10, 30]
    tasas = [4.5, 4.2, 4.0, 3.8, 3.9, 4.1]
    servicio = FixedIncomeService(plazos, tasas)
    return servicio.ajustar_nelson_siegel()


@router.get("/duracion")
def calcular_duracion(
    tasa_cupon: float = Query(default=0.05, ge=-0.50, le=1.0,
                              description="Tasa cupón anual"),
    vencimiento: int = Query(default=10, ge=1, le=100,
                             description="Años al vencimiento (mínimo 1)")
):
    if vencimiento <= 0:
        raise HTTPException(
            status_code=422,
            detail="El vencimiento debe ser mayor a 0 años."
        )
    macro = MacroService()
    datos = macro.curva_rendimiento()
    servicio = FixedIncomeService(datos["plazos"], datos["tasas"])
    return servicio.duracion_y_convexidad(
        tasa_cupon=tasa_cupon,
        vencimiento=vencimiento
    )


@router.get("/curva")
def obtener_curva():
    macro = MacroService()
    datos = macro.curva_rendimiento()
    if not datos["plazos"]:
        raise HTTPException(
            status_code=503,
            detail="No se pudieron obtener datos de FRED"
        )
    servicio = FixedIncomeService(datos["plazos"], datos["tasas"])
    return {
        "datos_mercado": datos,
        "nelson_siegel": servicio.ajustar_nelson_siegel(),
    }


@router.get("/sensibilidad")
def sensibilidad_bono(
    tasa_cupon: float = Query(default=0.05, ge=-0.50, le=1.0,
                              description="Tasa cupón anual"),
    vencimiento: int = Query(default=10, ge=1, le=100,
                             description="Años al vencimiento (mínimo 1)")
):
    if vencimiento <= 0:
        raise HTTPException(
            status_code=422,
            detail="El vencimiento debe ser mayor a 0 años."
        )
    macro = MacroService()
    datos = macro.curva_rendimiento()
    servicio = FixedIncomeService(datos["plazos"], datos["tasas"])
    return {
        "precio_base": servicio.duracion_y_convexidad(
            tasa_cupon, 100, vencimiento)["precio_bono"],
        "shocks": servicio.sensibilidad_shocks(tasa_cupon, 100, vencimiento)
    }