# app/crud.py
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload
from fastapi import HTTPException
from app import models, schemas


# -----------------------------
# Módulos y Galpones
# -----------------------------
def create_modulo(db: Session, modulo: schemas.ModuloCreate):
    db_mod = models.Modulo(**modulo.dict())
    db.add(db_mod)
    db.commit()
    db.refresh(db_mod)
    return db_mod


def create_galpon(db: Session, galpon: schemas.GalponCreate):
    mod = db.query(models.Modulo).filter(models.Modulo.id == galpon.modulo_id).first()
    if not mod:
        raise HTTPException(status_code=400, detail="Módulo no existe")
    db_g = models.Galpon(**galpon.dict())
    db.add(db_g)
    db.commit()
    db.refresh(db_g)
    return db_g


def list_modulos(db: Session):
    return db.query(models.Modulo).all()


def list_galpones(db: Session):
    return db.query(models.Galpon).all()


# -----------------------------
# Remisiones
# -----------------------------
def get_next_numero_remision(db: Session):
    current = db.query(func.max(models.Remision.numero_remision)).scalar() or 0
    return int(current) + 1

def create_remision(db: Session, remision: schemas.RemisionCreate):
    if not remision.detalles or len(remision.detalles) == 0:
        raise HTTPException(status_code=400, detail="La remisión debe tener al menos un detalle")

    db_rem = models.Remision(
        fecha=remision.fecha,
        fecha_produccion=remision.fecha_produccion,
        observaciones=remision.observaciones,
        despachado_por=remision.despachado_por,
        recibido_por=remision.recibido_por,
        numero_sello=remision.numero_sello
    )
    db.add(db_rem)
    db.flush()  # para obtener id
    db_rem.numero_remision = db_rem.id

    total_incubable = total_sucio = total_roto = total_extra = total_huevos = 0

    # 🔁 Recorremos detalles
    for d in remision.detalles:
        gal = db.query(models.Galpon).filter(models.Galpon.id == d.galpon_id).first()
        if not gal:
            db.rollback()
            raise HTTPException(status_code=400, detail=f"Galpón {d.galpon_id} no existe")

        if d.modulo_id is not None and gal.modulo_id != d.modulo_id:
            db.rollback()
            raise HTTPException(status_code=400, detail=f"Galpón {d.galpon_id} no pertenece al módulo {d.modulo_id}")

        detalle = models.RemisionDetalle(
            remision_id=db_rem.id,
            galpon_id=d.galpon_id,
            modulo_id=gal.modulo_id,
            huevo_incubable=d.huevo_incubable,
            huevo_sucio=d.huevo_sucio,
            huevo_roto=d.huevo_roto,
            huevo_extra=d.huevo_extra,
        )
        db.add(detalle)

        # Acumular totales
        total_incubable += d.huevo_incubable
        total_sucio += d.huevo_sucio
        total_roto += d.huevo_roto
        total_extra += d.huevo_extra
        total_huevos += d.huevo_incubable + d.huevo_sucio + d.huevo_roto + d.huevo_extra

    # Totales finales
    db_rem.huevo_incubable = total_incubable
    db_rem.huevo_sucio = total_sucio
    db_rem.huevo_roto = total_roto
    db_rem.huevo_extra = total_extra
    db_rem.total_huevos = total_huevos

    # 🧮 Empaques
    db_rem.cajas = total_incubable // 360
    db_rem.cubetas = total_incubable // 30
    db_rem.cubetas_sobrantes = (total_incubable % 360) // 30

    try:
        db.commit()
        db.refresh(db_rem)
        return db_rem
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error al guardar remisión: {str(e)}")


def list_remisiones(db: Session, skip: int = 0, limit: int = 100):
    return (
        db.query(models.Remision)
        .options(joinedload(models.Remision.detalles))
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_remision(db: Session, remision_id: int):
    return (
        db.query(models.Remision)
        .options(joinedload(models.Remision.detalles))
        .filter(models.Remision.id == remision_id)
        .first()
    )


def update_remision(db: Session, remision_id: int, remision: schemas.RemisionCreate):
    db_rem = get_remision(db, remision_id)
    if not db_rem:
        return None

    db_rem.fecha = remision.fecha
    db_rem.fecha_produccion = remision.fecha_produccion
    db_rem.observaciones = remision.observaciones
    db_rem.despachado_por = remision.despachado_por
    db_rem.recibido_por = remision.recibido_por
    db_rem.numero_sello = remision.numero_sello

    db.query(models.RemisionDetalle).filter(models.RemisionDetalle.remision_id == db_rem.id).delete()

    total_incubable = total_sucio = total_roto = total_extra = total_huevos = 0

    for d in remision.detalles:
        gal = db.query(models.Galpon).filter(models.Galpon.id == d.galpon_id).first()
        if not gal:
            raise HTTPException(status_code=400, detail=f"Galpón {d.galpon_id} no existe")

        detalle = models.RemisionDetalle(
            remision_id=db_rem.id,
            galpon_id=d.galpon_id,
            modulo_id=gal.modulo_id,
            huevo_incubable=d.huevo_incubable,
            huevo_sucio=d.huevo_sucio,
            huevo_roto=d.huevo_roto,
            huevo_extra=d.huevo_extra,
        )
        db.add(detalle)

        total_incubable += d.huevo_incubable
        total_sucio += d.huevo_sucio
        total_roto += d.huevo_roto
        total_extra += d.huevo_extra
        total_huevos += d.huevo_incubable + d.huevo_sucio + d.huevo_roto + d.huevo_extra

    db_rem.huevo_incubable = total_incubable
    db_rem.huevo_sucio = total_sucio
    db_rem.huevo_roto = total_roto
    db_rem.huevo_extra = total_extra
    db_rem.total_huevos = total_huevos
    db_rem.cajas = total_incubable // 360
    db_rem.cubetas = total_incubable // 30
    db_rem.cubetas_sobrantes = (total_incubable % 360) // 30

    db.commit()
    db.refresh(db_rem)
    return db_rem


def delete_remision(db: Session, remision_id: int):
    db_rem = get_remision(db, remision_id)
    if not db_rem:
        return None
    db.delete(db_rem)
    db.commit()
    return True


def get_daily_summary(db: Session, fecha, modulo_id: int | None = None):
    q = db.query(
        func.sum(models.RemisionDetalle.huevo_incubable).label("incubable"),
        func.sum(models.RemisionDetalle.huevo_sucio).label("sucio"),
        func.sum(models.RemisionDetalle.huevo_roto).label("roto"),
        func.sum(models.RemisionDetalle.huevo_extra).label("extra"),
        func.sum(models.Remision.total_huevos).label("total_huevos"),
        func.sum(models.Remision.cajas).label("cajas"),
        func.sum(models.Remision.cubetas).label("cubetas"),
        func.sum(models.Remision.cubetas_sobrantes).label("cubetas_sobrantes"),
    ).join(models.Remision, models.Remision.id == models.RemisionDetalle.remision_id)\
     .filter(models.Remision.fecha == fecha)

    if modulo_id:
        q = q.filter(models.RemisionDetalle.modulo_id == modulo_id)

    return q.one()


