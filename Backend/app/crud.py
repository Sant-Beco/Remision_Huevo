# app/crud.py
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload
from fastapi import HTTPException
from app import schemas, schemas


# -----------------------------
# Módulos y Galpones
# -----------------------------
def create_modulo(db: Session, modulo: schemas.ModuloCreate):
    db_mod = schemas.Modulo(**modulo.model_dump())  # FIX: .dict() → .model_dump() (Pydantic v2)
    db.add(db_mod)
    db.commit()
    db.refresh(db_mod)
    return db_mod


def create_galpon(db: Session, galpon: schemas.GalponCreate):
    mod = db.query(schemas.Modulo).filter(schemas.Modulo.id == galpon.modulo_id).first()
    if not mod:
        raise HTTPException(status_code=400, detail="Módulo no existe")
    db_g = schemas.Galpon(**galpon.model_dump())  # FIX: .dict() → .model_dump() (Pydantic v2)
    db.add(db_g)
    db.commit()
    db.refresh(db_g)
    return db_g


def list_modulos(db: Session):
    return db.query(schemas.Modulo).all()


def list_galpones(db: Session):
    return db.query(schemas.Galpon).all()


# -----------------------------
# Remisiones
# -----------------------------
def create_remision(db: Session, remision: schemas.RemisionCreate):
    if not remision.detalles or len(remision.detalles) == 0:
        raise HTTPException(status_code=400, detail="La remisión debe tener al menos un detalle")

    db_rem = schemas.Remision(
        fecha=remision.fecha,
        fecha_produccion=remision.fecha_produccion,
        observaciones=remision.observaciones,
        despachado_por=remision.despachado_por,
        recibido_por=remision.recibido_por,
        numero_sello=remision.numero_sello,
    )
    db.add(db_rem)
    db.flush()  # obtener id antes del commit
    db_rem.numero_remision = db_rem.id

    total_incubable = total_sucio = total_roto = total_extra = total_huevos = 0

    for d in remision.detalles:
        gal = db.query(schemas.Galpon).filter(schemas.Galpon.id == d.galpon_id).first()
        if not gal:
            db.rollback()
            raise HTTPException(status_code=400, detail=f"Galpón {d.galpon_id} no existe")

        if d.modulo_id is not None and gal.modulo_id != d.modulo_id:
            db.rollback()
            raise HTTPException(
                status_code=400,
                detail=f"Galpón {d.galpon_id} no pertenece al módulo {d.modulo_id}",
            )

        detalle = schemas.RemisionDetalle(
            remision_id=db_rem.id,
            galpon_id=d.galpon_id,
            modulo_id=gal.modulo_id,
            huevo_incubable=d.huevo_incubable,
            total_sucio=d.total_sucio,
            total_roto=d.total_roto,   # FIX: era d.total_roto → correcto, se mantiene
            huevo_extra=d.huevo_extra,
        )
        db.add(detalle)

        total_incubable += d.huevo_incubable
        total_sucio     += d.total_sucio
        total_roto      += d.total_roto
        total_extra     += d.huevo_extra
        total_huevos    += d.huevo_incubable + d.total_sucio + d.total_roto + d.huevo_extra

    db_rem.huevo_incubable   = total_incubable
    db_rem.total_sucio       = total_sucio
    db_rem.total_roto        = total_roto   # FIX: era db_rem.huevo_roto (columna fantasma)
    db_rem.total_extra       = total_extra
    db_rem.total_huevos      = total_huevos
    db_rem.cajas             = total_incubable // 360
    db_rem.cubetas           = total_incubable // 30
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
        db.query(schemas.Remision)
        .options(joinedload(schemas.Remision.detalles))
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_remision(db: Session, remision_id: int):
    return (
        db.query(schemas.Remision)
        .options(joinedload(schemas.Remision.detalles))
        .filter(schemas.Remision.id == remision_id)
        .first()
    )


def update_remision(db: Session, remision_id: int, remision: schemas.RemisionCreate):
    db_rem = get_remision(db, remision_id)
    if not db_rem:
        return None

    db_rem.fecha            = remision.fecha
    db_rem.fecha_produccion = remision.fecha_produccion
    db_rem.observaciones    = remision.observaciones
    db_rem.despachado_por   = remision.despachado_por
    db_rem.recibido_por     = remision.recibido_por
    db_rem.numero_sello     = remision.numero_sello

    # Borrar detalles anteriores para reemplazarlos
    db.query(schemas.RemisionDetalle).filter(
        schemas.RemisionDetalle.remision_id == db_rem.id
    ).delete()

    total_incubable = total_sucio = total_roto = total_extra = total_huevos = 0

    for d in remision.detalles:
        gal = db.query(schemas.Galpon).filter(schemas.Galpon.id == d.galpon_id).first()
        if not gal:
            raise HTTPException(status_code=400, detail=f"Galpón {d.galpon_id} no existe")

        detalle = schemas.RemisionDetalle(
            remision_id=db_rem.id,
            galpon_id=d.galpon_id,
            modulo_id=gal.modulo_id,
            huevo_incubable=d.huevo_incubable,
            total_sucio=d.total_sucio,
            total_roto=d.total_roto,   # FIX: era d.huevo_roto → AttributeError
            huevo_extra=d.huevo_extra,
        )
        db.add(detalle)

        total_incubable += d.huevo_incubable
        total_sucio     += d.total_sucio
        total_roto      += d.total_roto   # FIX: era d.huevo_roto → AttributeError
        total_extra     += d.huevo_extra
        total_huevos    += d.huevo_incubable + d.total_sucio + d.total_roto + d.huevo_extra

    db_rem.huevo_incubable   = total_incubable
    db_rem.total_sucio       = total_sucio
    db_rem.total_roto        = total_roto   # FIX: era db_rem.huevo_roto (columna fantasma)
    db_rem.total_extra       = total_extra
    db_rem.total_huevos      = total_huevos
    db_rem.cajas             = total_incubable // 360
    db_rem.cubetas           = total_incubable // 30
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
    """
    FIX: query separada para totales de cabecera (evita inflado por JOIN N→M).
    Los totales por detalle se calculan directo en remision_detalles.
    Los totales de cabecera (cajas, cubetas, total_huevos) se calculan
    sumando desde remisiones filtradas por fecha, sin JOIN a detalles.
    """
    # --- Totales por tipo de huevo (desde detalles) ---
    q_det = (
        db.query(
            func.coalesce(func.sum(schemas.RemisionDetalle.huevo_incubable), 0).label("incubable"),
            func.coalesce(func.sum(schemas.RemisionDetalle.total_sucio), 0).label("sucio"),
            func.coalesce(func.sum(schemas.RemisionDetalle.total_roto), 0).label("roto"),
            func.coalesce(func.sum(schemas.RemisionDetalle.huevo_extra), 0).label("extra"),
        )
        .join(schemas.Remision, schemas.Remision.id == schemas.RemisionDetalle.remision_id)
        .filter(schemas.Remision.fecha == fecha)
    )
    if modulo_id:
        q_det = q_det.filter(schemas.RemisionDetalle.modulo_id == modulo_id)
    det = q_det.one()

    # --- Totales de cabecera (desde remisiones, sin JOIN a detalles) ---
    q_rem = (
        db.query(
            func.coalesce(func.sum(schemas.Remision.total_huevos), 0).label("total_huevos"),
            func.coalesce(func.sum(schemas.Remision.cajas), 0).label("cajas"),
            func.coalesce(func.sum(schemas.Remision.cubetas), 0).label("cubetas"),
            func.coalesce(func.sum(schemas.Remision.cubetas_sobrantes), 0).label("cubetas_sobrantes"),
        )
        .filter(schemas.Remision.fecha == fecha)
    )
    if modulo_id:
        # Filtrar remisiones que tengan al menos un detalle del módulo pedido
        q_rem = q_rem.filter(
            schemas.Remision.id.in_(
                db.query(schemas.RemisionDetalle.remision_id)
                .filter(schemas.RemisionDetalle.modulo_id == modulo_id)
            )
        )
    rem = q_rem.one()

    # Combinar en un objeto compatible con schemas.DailySummary
    class _Summary:
        pass

    s = _Summary()
    s.incubable         = det.incubable
    s.sucio             = det.sucio
    s.roto              = det.roto
    s.extra             = det.extra
    s.total_huevos      = rem.total_huevos
    s.cajas             = rem.cajas
    s.cubetas           = rem.cubetas
    s.cubetas_sobrantes = rem.cubetas_sobrantes
    return s