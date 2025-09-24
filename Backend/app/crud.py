from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app import models, schemas

def create_modulo(db: Session, modulo: schemas.ModuloCreate):
    db_mod = models.Modulo(**modulo.dict())
    db.add(db_mod)
    db.commit()
    db.refresh(db_mod)
    return db_mod

def create_galpon(db: Session, galpon: schemas.GalponCreate):
    # validate module exists
    mod = db.query(models.Modulo).filter(models.Modulo.id == galpon.modulo_id).first()
    if not mod:
        raise HTTPException(status_code=400, detail="Módulo no existe")
    db_g = models.Galpon(**galpon.dict())
    db.add(db_g)
    db.commit()
    db.refresh(db_g)
    return db_g

def get_next_numero_remision(db: Session):
    # Simple next number (global). For concurrencia usar tabla de secuencia o manejo con retry.
    current = db.query(func.max(models.Remision.numero_remision)).scalar() or 0
    return int(current) + 1

def create_remision(db: Session, remision: schemas.RemisionCreate):
    # Validaciones
    galpon = db.query(models.Galpon).filter(models.Galpon.id == remision.galpon_id).first()
    if not galpon:
        raise HTTPException(status_code=400, detail="Galpón no existe")

    if galpon.modulo_id != remision.modulo_id:
        raise HTTPException(status_code=400, detail="El galpón no pertenece al módulo indicado")

    # sumar total de huevos (auditoría)
    total_huevos = (
        remision.huevo_incubable +
        remision.huevo_sucio +
        remision.huevo_roto +
        remision.huevo_extra
    )

    # packaging se calcula usando huevo_incubable (según lo conversado)
    cajas = remision.huevo_incubable // 360
    cubetas_totales = remision.huevo_incubable // 30
    cubetas_sobrantes = (remision.huevo_incubable % 360) // 30

    # número de remisión (consecutivo físico)
    numero_rem = get_next_numero_remision(db)

    db_remision = models.Remision(
        **remision.dict(),
        numero_remision=numero_rem,
        total_huevos=total_huevos,
        cajas=cajas,
        cubetas=cubetas_totales,
        cubetas_sobrantes=cubetas_sobrantes
    )

    try:
        db.add(db_remision)
        db.commit()
        db.refresh(db_remision)
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"DB error: {str(e)}")
    return db_remision

def list_remisiones(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Remision).offset(skip).limit(limit).all()

def get_remision(db: Session, remision_id: int):
    return db.query(models.Remision).filter(models.Remision.id == remision_id).first()

def get_daily_summary(db: Session, fecha, modulo_id: int | None = None):
    q = db.query(
        func.sum(models.Remision.huevo_incubable).label("incubable"),
        func.sum(models.Remision.huevo_sucio).label("sucio"),
        func.sum(models.Remision.huevo_roto).label("roto"),
        func.sum(models.Remision.huevo_extra).label("extra"),
        func.sum(models.Remision.total_huevos).label("total_huevos"),
        func.sum(models.Remision.cajas).label("cajas"),
        func.sum(models.Remision.cubetas).label("cubetas"),
        func.sum(models.Remision.cubetas_sobrantes).label("cubetas_sobrantes"),
    ).filter(models.Remision.fecha == fecha)

    if modulo_id:
        q = q.filter(models.Remision.modulo_id == modulo_id)

    return q.one()
