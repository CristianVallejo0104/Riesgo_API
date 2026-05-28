from fastapi import APIRouter, HTTPException, status

from app.services.databricks import DatabricksService


router = APIRouter(prefix="/databricks", tags=["Databricks"])


@router.get("/estado")
def estado_databricks():
    servicio = DatabricksService()
    if not servicio.configurado():
        return {
            "configurado": False,
            "conectado": False,
            "detail": "Configura DATABRICKS_SERVER_HOSTNAME, DATABRICKS_HTTP_PATH y DATABRICKS_TOKEN.",
        }

    try:
        resultado = servicio.probar_conexion()
        return {"configurado": True, **resultado}
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"No se pudo conectar con Databricks: {exc}",
        )


@router.get("/risklab-prices/resumen")
def resumen_risklab_prices():
    servicio = DatabricksService()
    if not servicio.configurado():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Credenciales de Databricks no configuradas.",
        )

    try:
        return {
            "tabla": "risklab_prices",
            "datos": servicio.resumen_precios(),
        }
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"No se pudo consultar risklab_prices en Databricks: {exc}",
        )


@router.get("/consultas")
def listar_consultas_databricks():
    servicio = DatabricksService()
    return {"consultas": servicio.consultas_predefinidas()}


@router.get("/consultas/{consulta_id}")
def ejecutar_consulta_databricks(consulta_id: str):
    servicio = DatabricksService()
    if not servicio.configurado():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Credenciales de Databricks no configuradas.",
        )

    try:
        return servicio.ejecutar_consulta(consulta_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"No se pudo ejecutar la consulta en Databricks: {exc}",
        )
