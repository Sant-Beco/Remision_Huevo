# app/routers/granjas.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import crud, schemas
from app.database import get_db

router = APIRouter(prefix="/granjas", tags=["granjas"])


@router.get("/", response_model=list[schemas.GranjaOut])
def listar_granjas(db: Session = Depends(get_db)):
    return crud.granja.get_multi(db)


@router.post("/", response_model=schemas.GranjaOut, status_code=201)
def crear_granja(payload: schemas.GranjaCreate, db: Session = Depends(get_db)):
    return crud.granja.create(db, obj_in=payload)


@router.get("/{granja_id}", response_model=schemas.GranjaOut)
def obtener_granja(granja_id: str, db: Session = Depends(get_db)):
    obj = crud.granja.get(db, granja_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Granja no encontrada")
    return obj


@router.get("/{granja_id}/detalle", response_model=schemas.GranjaOut)
def obtener_granja_con_modulos(granja_id: str, db: Session = Depends(get_db)):
    """Retorna la granja con sus módulos y galpones anidados."""
    obj = crud.granja.get_with_modulos(db, granja_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Granja no encontrada")
    return obj


@router.put("/{granja_id}", response_model=schemas.GranjaOut)
def actualizar_granja(
    granja_id: str,
    payload: schemas.GranjaUpdate,
    db: Session = Depends(get_db),
):
    obj = crud.granja.get(db, granja_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Granja no encontrada")
    return crud.granja.update(db, db_obj=obj, obj_in=payload)


@router.delete("/{granja_id}", status_code=204)
def eliminar_granja(granja_id: str, db: Session = Depends(get_db)):
    obj = crud.granja.get(db, granja_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Granja no encontrada")
    crud.granja.remove(db, id=granja_id)