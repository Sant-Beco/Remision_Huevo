# app/routers/remisiones.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app import schemas, database, crud

router = APIRouter(prefix="/remisiones", tags=["remisiones"])

@router.post("/", response_model=schemas.Remision)
def create_remision(remision: schemas.RemisionCreate, db: Session = Depends(database.get_db)):
    return crud.create_remision(db, remision)

@router.get("/", response_model=list[schemas.Remision])
def list_remisiones(skip: int = 0, limit: int = 100, db: Session = Depends(database.get_db)):
    return crud.list_remisiones(db, skip=skip, limit=limit)

@router.get("/summary")
def daily_summary(fecha: str = Query(..., description="YYYY-MM-DD"), modulo_id: int | None = None, db: Session = Depends(database.get_db)):
    from datetime import datetime
    try:
        d = datetime.fromisoformat(fecha).date()
    except Exception:
        raise HTTPException(status_code=400, detail="Fecha inválida (usar YYYY-MM-DD)")
    summary = crud.get_daily_summary(db, d, modulo_id)
    return {k: int(v or 0) for k, v in zip(["incubable","sucio","roto","extra","total_huevos","cajas","cubetas","cubetas_sobrantes"], summary)}
    
