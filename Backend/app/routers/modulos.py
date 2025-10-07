from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from .. import models, schemas, database

router = APIRouter(
    prefix="/modulos",
    tags=["modulos"]
)

# Crear módulo
@router.post("/", response_model=schemas.Modulo)
def create_modulo(modulo: schemas.ModuloCreate, db: Session = Depends(database.get_db)):
    db_modulo = models.Modulo(**modulo.dict())
    db.add(db_modulo)
    db.commit()
    db.refresh(db_modulo)
    return db_modulo


# Listar todos los módulos
@router.get("/", response_model=list[schemas.Modulo])
def list_modulos(db: Session = Depends(database.get_db)):
    return db.query(models.Modulo).all()


# Obtener módulo por ID
@router.get("/{modulo_id}", response_model=schemas.Modulo)
def get_modulo(modulo_id: int, db: Session = Depends(database.get_db)):
    modulo = db.query(models.Modulo).filter(models.Modulo.id == modulo_id).first()
    if not modulo:
        raise HTTPException(status_code=404, detail="Módulo no encontrado")
    return modulo


# Actualizar módulo
@router.put("/{modulo_id}", response_model=schemas.Modulo)
def update_modulo(modulo_id: int, modulo_data: schemas.ModuloCreate, db: Session = Depends(database.get_db)):
    modulo = db.query(models.Modulo).filter(models.Modulo.id == modulo_id).first()
    if not modulo:
        raise HTTPException(status_code=404, detail="Módulo no encontrado")

    for key, value in modulo_data.dict().items():
        setattr(modulo, key, value)

    db.commit()
    db.refresh(modulo)
    return modulo


# Eliminar módulo
@router.delete("/{modulo_id}")
def delete_modulo(modulo_id: int, db: Session = Depends(database.get_db)):
    modulo = db.query(models.Modulo).filter(models.Modulo.id == modulo_id).first()
    if not modulo:
        raise HTTPException(status_code=404, detail="Módulo no encontrado")

    db.delete(modulo)
    db.commit()
    return {"message": "Módulo eliminado correctamente"}