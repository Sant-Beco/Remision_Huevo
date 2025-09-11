from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app import models, schemas, database  # 👈 importante usar app. en lugar de ..

router = APIRouter(
    prefix="/remisiones",
    tags=["remisiones"]
)

@router.post("/", response_model=schemas.Remision)
def create_remision(remision: schemas.RemisionCreate, db: Session = Depends(database.get_db)):
    db_remision = models.Remision(**remision.dict())
    db.add(db_remision)
    db.commit()
    db.refresh(db_remision)
    return db_remision

@router.get("/", response_model=list[schemas.Remision])
def list_remisiones(db: Session = Depends(database.get_db)):
    return db.query(models.Remision).all()

