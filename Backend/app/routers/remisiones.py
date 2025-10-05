# app/routers/remisiones.py
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from datetime import datetime
from app import schemas, database, crud

router = APIRouter(prefix="/remisiones", tags=["remisiones"])

# 🔹 Crear remisión
@router.post("/", response_model=schemas.Remision, status_code=status.HTTP_201_CREATED)
def create_remision(remision: schemas.RemisionCreate, db: Session = Depends(database.get_db)):
    return crud.create_remision(db, remision)

# 🔹 Obtener resumen diario (mover arriba para evitar conflicto con /{id})
@router.get("/summary", response_model=schemas.DailySummary)
def daily_summary(
    fecha: str = Query(..., description="Fecha en formato YYYY-MM-DD"),
    modulo_id: int | None = Query(default=None, description="Filtrar por módulo"),
    db: Session = Depends(database.get_db)
):
    try:
        d = datetime.fromisoformat(fecha).date()
    except Exception:
        raise HTTPException(status_code=400, detail="Fecha inválida. Use formato YYYY-MM-DD")

    result = crud.get_daily_summary(db, d, modulo_id)
    return schemas.DailySummary(
        incubable=result.incubable or 0,
        sucio=result.sucio or 0,
        roto=result.roto or 0,
        extra=result.extra or 0,
        total_huevos=result.total_huevos or 0,
        cajas=result.cajas or 0,
        cubetas=result.cubetas or 0,
        cubetas_sobrantes=result.cubetas_sobrantes or 0
    )

# 🔹 Obtener remisión por ID
@router.get("/{remision_id}", response_model=schemas.Remision)
def get_remision(remision_id: int, db: Session = Depends(database.get_db)):
    rem = crud.get_remision(db, remision_id)
    if not rem:
        raise HTTPException(status_code=404, detail="Remisión no encontrada")
    return rem

# 🔹 Actualizar remisión
@router.put("/{remision_id}", response_model=schemas.Remision)
def update_remision(remision_id: int, remision: schemas.RemisionCreate, db: Session = Depends(database.get_db)):
    db_rem = crud.update_remision(db, remision_id, remision)
    if not db_rem:
        raise HTTPException(status_code=404, detail="Remisión no encontrada")
    return db_rem

# 🔹 Eliminar remisión
@router.delete("/{remision_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_remision(remision_id: int, db: Session = Depends(database.get_db)):
    success = crud.delete_remision(db, remision_id)
    if not success:
        raise HTTPException(status_code=404, detail="Remisión no encontrada")
    return {"message": f"Remisión {remision_id} eliminada"}



