# app/routers/galpones.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import crud, schemas
from app.database import get_db

router = APIRouter(prefix="/galpones", tags=["galpones"])


@router.get("/", response_model=list[schemas.GalponOut])
def listar_galpones(db: Session = Depends(get_db)):
    return crud.galpon.get_multi(db)


@router.post("/", response_model=schemas.GalponOut, status_code=201)
def crear_galpon(payload: schemas.GalponCreate, db: Session = Depends(get_db)):
    return crud.galpon.create(db, obj_in=payload)


@router.get("/{galpon_id}", response_model=schemas.GalponOut)
def obtener_galpon(galpon_id: int, db: Session = Depends(get_db)):
    obj = crud.galpon.get(db, galpon_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Galpón no encontrado")
    return obj


@router.put("/{galpon_id}", response_model=schemas.GalponOut)
def actualizar_galpon(
    galpon_id: int,
    payload: schemas.GalponUpdate,
    db: Session = Depends(get_db),
):
    obj = crud.galpon.get(db, galpon_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Galpón no encontrado")
    return crud.galpon.update(db, db_obj=obj, obj_in=payload)


@router.delete("/{galpon_id}", status_code=204)
def eliminar_galpon(galpon_id: int, db: Session = Depends(get_db)):
    obj = crud.galpon.get(db, galpon_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Galpón no encontrado")
    crud.galpon.remove(db, id=galpon_id)