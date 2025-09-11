from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from .. import models, schemas, database

router = APIRouter(
    prefix="/modulos",
    tags=["modulos"]
)

@router.post("/", response_model=schemas.Modulo)
def create_modulo(modulo: schemas.ModuloCreate, db: Session = Depends(database.get_db)):
    db_modulo = models.Modulo(**modulo.dict())
    db.add(db_modulo)
    db.commit()
    db.refresh(db_modulo)
    return db_modulo

@router.get("/", response_model=list[schemas.Modulo])
def list_modulos(db: Session = Depends(database.get_db)):
    return db.query(models.Modulo).all()
