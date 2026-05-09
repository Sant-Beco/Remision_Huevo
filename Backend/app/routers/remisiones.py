# app/routers/remisiones.py
from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import crud, schemas
from app.database import get_db

router = APIRouter(prefix="/remisiones", tags=["remisiones"])


@router.get("/", response_model=list[schemas.RemisionOut])
def listar_remisiones(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return crud.remision.list_remisiones(db, skip=skip, limit=limit)


@router.post("/", response_model=schemas.RemisionOut, status_code=201)
def crear_remision(payload: schemas.RemisionCreate, db: Session = Depends(get_db)):
    return crud.remision.create_remision(db, payload)


@router.get("/resumen-diario", response_model=schemas.ResumenDiarioOut)
def resumen_diario(
    fecha: date,
    modulo_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    return crud.remision.get_daily_summary(db, fecha=fecha, modulo_id=modulo_id)


@router.get("/{remision_id}", response_model=schemas.RemisionOut)
def obtener_remision(remision_id: int, db: Session = Depends(get_db)):
    obj = crud.remision.get_remision(db, remision_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Remisión no encontrada")
    return obj


@router.put("/{remision_id}", response_model=schemas.RemisionOut)
def actualizar_remision(
    remision_id: int,
    payload: schemas.RemisionCreate,
    db: Session = Depends(get_db),
):
    obj = crud.remision.update_remision(db, remision_id, payload)
    if not obj:
        raise HTTPException(status_code=404, detail="Remisión no encontrada")
    return obj


@router.delete("/{remision_id}", status_code=204)
def eliminar_remision(remision_id: int, db: Session = Depends(get_db)):
    result = crud.remision.delete_remision(db, remision_id)
    if not result:
        raise HTTPException(status_code=404, detail="Remisión no encontrada")