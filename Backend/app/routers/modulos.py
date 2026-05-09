# app/routers/modulos.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import crud, schemas
from app.database import get_db

router = APIRouter(prefix="/modulos", tags=["módulos"])


@router.get("/", response_model=list[schemas.ModuloOut])
def listar_modulos(db: Session = Depends(get_db)):
    return crud.modulo.get_multi(db)


@router.post("/", response_model=schemas.ModuloOut, status_code=201)
def crear_modulo(payload: schemas.ModuloCreate, db: Session = Depends(get_db)):
    return crud.modulo.create(db, obj_in=payload)


@router.get("/{modulo_id}", response_model=schemas.ModuloOut)
def obtener_modulo(modulo_id: int, db: Session = Depends(get_db)):
    obj = crud.modulo.get(db, modulo_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Módulo no encontrado")
    return obj


@router.put("/{modulo_id}", response_model=schemas.ModuloOut)
def actualizar_modulo(
    modulo_id: int,
    payload: schemas.ModuloUpdate,
    db: Session = Depends(get_db),
):
    obj = crud.modulo.get(db, modulo_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Módulo no encontrado")
    return crud.modulo.update(db, db_obj=obj, obj_in=payload)


@router.delete("/{modulo_id}", status_code=204)
def eliminar_modulo(modulo_id: int, db: Session = Depends(get_db)):
    obj = crud.modulo.get(db, modulo_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Módulo no encontrado")
    crud.modulo.remove(db, id=modulo_id)