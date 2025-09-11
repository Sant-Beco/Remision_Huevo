from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from .. import models, schemas, database

router = APIRouter(
    prefix="/galpones",
    tags=["galpones"]
)

@router.post("/", response_model=schemas.Galpon)
def create_galpon(galpon: schemas.GalponCreate, db: Session = Depends(database.get_db)):
    db_galpon = models.Galpon(**galpon.dict())
    db.add(db_galpon)
    db.commit()
    db.refresh(db_galpon)
    return db_galpon

@router.get("/", response_model=list[schemas.Galpon])
def list_galpones(db: Session = Depends(database.get_db)):
    return db.query(models.Galpon).all()

