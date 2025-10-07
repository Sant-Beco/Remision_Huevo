from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from .. import models, schemas, database

router = APIRouter(
    prefix="/galpones",
    tags=["galpones"]
)


# Crear galpón
@router.post("/", response_model=schemas.Galpon)
def create_galpon(galpon: schemas.GalponCreate, db: Session = Depends(database.get_db)):
    modulo = db.query(models.Modulo).filter(models.Modulo.id == galpon.modulo_id).first()
    if not modulo:
        raise HTTPException(status_code=400, detail="El módulo especificado no existe")
    db_galpon = models.Galpon(**galpon.dict())
    db.add(db_galpon)
    db.commit()
    db.refresh(db_galpon)
    return db_galpon


# Listar todos los galpones
@router.get("/", response_model=list[schemas.Galpon])
def list_galpones(db: Session = Depends(database.get_db)):
    return db.query(models.Galpon).all()


# Obtener galpón por ID
@router.get("/{galpon_id}", response_model=schemas.Galpon)
def get_galpon(galpon_id: int, db: Session = Depends(database.get_db)):
    galpon = db.query(models.Galpon).filter(models.Galpon.id == galpon_id).first()
    if not galpon:
        raise HTTPException(status_code=404, detail="Galpón no encontrado")
    return galpon


# Actualizar galpón
@router.put("/{galpon_id}", response_model=schemas.Galpon)
def update_galpon(galpon_id: int, galpon_data: schemas.GalponCreate, db: Session = Depends(database.get_db)):
    galpon = db.query(models.Galpon).filter(models.Galpon.id == galpon_id).first()
    if not galpon:
        raise HTTPException(status_code=404, detail="Galpón no encontrado")

    modulo = db.query(models.Modulo).filter(models.Modulo.id == galpon_data.modulo_id).first()
    if not modulo:
        raise HTTPException(status_code=400, detail="El módulo especificado no existe")

    for key, value in galpon_data.dict().items():
        setattr(galpon, key, value)

    db.commit()
    db.refresh(galpon)
    return galpon


# Eliminar galpón
@router.delete("/{galpon_id}")
def delete_galpon(galpon_id: int, db: Session = Depends(database.get_db)):
    galpon = db.query(models.Galpon).filter(models.Galpon.id == galpon_id).first()
    if not galpon:
        raise HTTPException(status_code=404, detail="Galpón no encontrado")

    db.delete(galpon)
    db.commit()
    return {"message": "Galpón eliminado correctamente"}