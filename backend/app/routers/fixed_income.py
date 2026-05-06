from fastapi import APIRouter, HTTPException

from app.services.fixed_income import FixedIncomeService
from app.services.macro import MacroService

router = APIRouter(prefix="/renta-fija", tags=["Renta Fija"])


@router.get("/nelson-siegel")
def calcular_nelson_siegel():
    plazos = [0.25, 1, 2, 5, 10, 30]
    tasas = [4.5, 4.2, 4.0, 3.8, 3.9, 4.1]  # Valores ejemplo
    servicio = FixedIncomeService(plazos, tasas)
    return servicio.ajustar_nelson_siegel()


@router.get("/duracion")
def calcular_duracion(tasa_cupon: float = 0.05, vencimiento: int = 10):
    plazos = [0.25, 1, 2, 5, 10, 30]
    tasas = [4.5, 4.2, 4.0, 3.8, 3.9, 4.1]
    servicio = FixedIncomeService(plazos, tasas)
    return servicio.duracion_y_convexidad(tasa_cupon=tasa_cupon, vencimiento=vencimiento)

@router.get("/curva")
def obtener_curva():
    macro = MacroService()
    datos = macro.curva_rendimiento()
    if not datos["plazos"]:
        raise HTTPException(status_code=503, detail="No se pudieron obtener datos de FRED")
    servicio = FixedIncomeService(datos["plazos"], datos["tasas"])
    return {
        "datos_mercado": datos,
        "nelson_siegel": servicio.ajustar_nelson_siegel(),
    }


@router.get("/duracion")
def calcular_duracion(tasa_cupon: float = 0.05, vencimiento: int = 10):
    macro = MacroService()
    datos = macro.curva_rendimiento()
    servicio = FixedIncomeService(datos["plazos"], datos["tasas"])
    return servicio.duracion_y_convexidad(tasa_cupon=tasa_cupon, vencimiento=vencimiento)