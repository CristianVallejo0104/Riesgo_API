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
    datos = MacroService().curva_rendimiento()
    return FixedIncomeService(datos["plazos"], datos["tasas"]).ajustar_nelson_siegel()


_TASA_DESC = Query(default=None, ge=-0.05, le=0.50,
                   description="YTM en decimal. Si se omite se interpola la curva de FRED al plazo del bono.")


@router.get("/duracion")
def calcular_duracion(
    tasa_cupon: float = Query(default=0.05, ge=-0.50, le=1.0, description="Tasa cupón anual"),
    vencimiento: int = Query(default=10, ge=1, le=100, description="Años al vencimiento (mínimo 1)"),
    tasa_descuento: float | None = _TASA_DESC,
):
    datos = MacroService().curva_rendimiento()
    servicio = FixedIncomeService(datos["plazos"], datos["tasas"])
    return servicio.duracion_y_convexidad(tasa_cupon=tasa_cupon, vencimiento=vencimiento,
                                          tasa_descuento=tasa_descuento)


@router.get("/curva")
def obtener_curva():
    datos = MacroService().curva_rendimiento()
    if not datos["plazos"]:
        raise HTTPException(status_code=503, detail="No se pudieron obtener datos de FRED")
    servicio = FixedIncomeService(datos["plazos"], datos["tasas"])
    return {"datos_mercado": datos, "nelson_siegel": servicio.ajustar_nelson_siegel()}


@router.get("/sensibilidad")
def sensibilidad_bono(
    tasa_cupon: float = Query(default=0.05, ge=-0.50, le=1.0, description="Tasa cupón anual"),
    vencimiento: int = Query(default=10, ge=1, le=100, description="Años al vencimiento (mínimo 1)"),
    tasa_descuento: float | None = _TASA_DESC,
):
    datos = MacroService().curva_rendimiento()
    servicio = FixedIncomeService(datos["plazos"], datos["tasas"])
    base = servicio.duracion_y_convexidad(tasa_cupon, 100, vencimiento, tasa_descuento)
    return {
        "precio_base": base["precio_bono"],
        "tasa_descuento": base["tasa_descuento"],
        "shocks": servicio.sensibilidad_shocks(tasa_cupon, 100, vencimiento, tasa_descuento),
    }
