from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app import models, schemas, database

router = APIRouter(
    prefix="/remisiones",
    tags=["remisiones"]
)

@router.post("/", response_model=schemas.Remision)
def create_remision(remision: schemas.RemisionCreate, db: Session = Depends(database.get_db)):
    # 🥚 Calcular cajas y cubetas a partir de huevo_incubable
    total_huevos = remision.huevo_incubable
    cajas = total_huevos // 360       # 1 caja = 360 huevos
    cubetas = (total_huevos % 360) // 30  # 1 cubeta = 30 huevos

    # Crear objeto Remisión con valores calculados
    db_remision = models.Remision(
        **remision.dict(),
        cajas=cajas,
        cubetas=cubetas
    )

    db.add(db_remision)
    db.commit()
    db.refresh(db_remision)
    return db_remision



@router.get("/", response_model=list[schemas.Remision])
def list_remisiones(db: Session = Depends(database.get_db)):
    return db.query(models.Remision).all()
