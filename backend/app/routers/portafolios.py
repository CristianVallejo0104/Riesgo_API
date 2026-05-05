from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.dependencies import DBSession
from app.models.db_models import Portfolio
from app.models.schemas import PortfolioCreate, PortfolioResponse


router = APIRouter(prefix="/portafolios", tags=["Portafolios"])

@router.post("/", response_model=PortfolioResponse, status_code=status.HTTP_201_CREATED)
def crear_portafolio(datos: PortfolioCreate, db: DBSession):
    portafolio = Portfolio(**datos.model_dump())
    db.add(portafolio)
    db.commit()
    db.refresh(portafolio)
    return portafolio

@router.get("/", response_model=list[PortfolioResponse])
def listar_portafolios(db: DBSession):
    return db.scalars(select(Portfolio)).all()


@router.get("/{portafolio_id}", response_model=PortfolioResponse)
def obtener_portafolio(portafolio_id: int, db: DBSession):
    portafolio = db.get(Portfolio, portafolio_id)
    if not portafolio:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Portafolio {portafolio_id} no encontrado",
        )
    return portafolio