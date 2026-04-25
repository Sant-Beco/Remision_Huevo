# app/crud/remision.py
"""
CRUD para Remision, RemisionDetalle y HuevoPendiente.

Responsabilidades de esta capa (solo DB — sin lógica de negocio):
  - Persistir remisiones y detalles.
  - Calcular totales y empaques (operación matemática pura).
  - Resolver FKs: modulo_id desde galpon si no se envía.
  - Upsert para sincronización offline.

La validación contra histórico / curva genética vive en
  app/services/validacion.py  (siguiente paso).
El registro de LogAuditoria vive en
  app/services/auditoria.py.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.granja import Galpon
from app.models.remision import (
    EstadoRemision,
    HuevoPendiente,
    Remision,
    RemisionDetalle,
)
from app.schemas.remision import (
    HuevoPendienteCreate,
    RecepcionCreate,
    RemisionCreate,
    RemisionUpdate,
    ResumenDiarioOut,
    SyncOut,
    SyncPayload,
    SyncResultItem,
)


# ─────────────────────────────────────────
# Helpers internos
# ─────────────────────────────────────────

def _calcular_empaques(incubable: int) -> dict:
    """Hibridez de Carga: descompone huevo_incubable en cajas, cubetas, sueltos."""
    return {
        "cajas":             incubable // 360,
        "cubetas":           incubable // 30,
        "cubetas_sobrantes": (incubable % 360) // 30,
        "unidades_sueltas":  incubable % 30,
    }


def _resolver_modulo_id(db: Session, galpon_id: str, modulo_id_hint: Optional[str]) -> str:
    """
    Si el operario no envió modulo_id, lo resuelve desde el galpón.
    Valida que el galpón exista y esté activo.
    """
    galpon = db.get(Galpon, galpon_id)
    if not galpon or not galpon.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Galpón '{galpon_id}' no existe o está inactivo",
        )
    if modulo_id_hint and galpon.modulo_id != modulo_id_hint:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Galpón '{galpon_id}' no pertenece al módulo '{modulo_id_hint}'",
        )
    return galpon.modulo_id


# ══════════════════════════════════════════
# CREATE
# ══════════════════════════════════════════

def create_remision(
    db: Session,
    *,
    obj_in: RemisionCreate,
    creado_por_id: Optional[str] = None,
) -> Remision:
    """
    Crea remisión con todos sus detalles y pendientes en una transacción.
    El UUID puede venir del cliente (offline) o ser generado aquí.
    """
    remision_id = obj_in.id or str(uuid.uuid4())

    # Verificar que no exista ya (idempotencia para sync)
    existing = db.get(Remision, remision_id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ya existe una remisión con id '{remision_id}'",
        )

    db_rem = Remision(
        id=remision_id,
        granja_id=obj_in.granja_id,
        fecha=obj_in.fecha,
        fecha_produccion=obj_in.fecha_produccion,
        despachado_por=obj_in.despachado_por,
        recibido_por=obj_in.recibido_por,
        numero_sello=obj_in.numero_sello,
        observaciones=obj_in.observaciones,
        estado=EstadoRemision.BORRADOR,
        creado_por_id=creado_por_id,
    )
    db.add(db_rem)
    db.flush()  # necesita id antes de insertar detalles

    # Número secuencial (asignado al sincronizar, no en offline)
    db_rem.numero_remision = db_rem.id  # temporal; el service lo reasigna al hacer /sync

    total_incubable = total_sucio = total_roto = total_extra = total_huevos = 0

    for d in obj_in.detalles:
        modulo_id = _resolver_modulo_id(db, d.galpon_id, d.modulo_id)

        detalle = RemisionDetalle(
            id=str(uuid.uuid4()),
            remision_id=db_rem.id,
            galpon_id=d.galpon_id,
            modulo_id=modulo_id,
            lote_id=d.lote_id,
            huevo_incubable=d.huevo_incubable,
            total_sucio=d.total_sucio,
            total_roto=d.total_roto,
            huevo_extra=d.huevo_extra,
            entrada_modo=d.entrada_modo,
            entrada_cajas=d.calculadora_incubable.cajas if d.calculadora_incubable else None,
            entrada_cubetas=d.calculadora_incubable.cubetas if d.calculadora_incubable else None,
            entrada_unidades=d.calculadora_incubable.unidades if d.calculadora_incubable else None,
            observaciones=d.observaciones,
        )
        db.add(detalle)

        total_incubable += d.huevo_incubable
        total_sucio     += d.total_sucio
        total_roto      += d.total_roto
        total_extra     += d.huevo_extra
        total_huevos    += d.huevo_incubable + d.total_sucio + d.total_roto + d.huevo_extra

    # Pendientes
    for p in obj_in.pendientes:
        pendiente = HuevoPendiente(
            id=str(uuid.uuid4()),
            remision_id=db_rem.id,
            galpon_id=p.galpon_id,
            cantidad=p.cantidad,
            motivo=p.motivo,
            descripcion=p.descripcion,
        )
        db.add(pendiente)

    # Totales y empaques en cabecera
    empaques = _calcular_empaques(total_incubable)
    db_rem.huevo_incubable   = total_incubable
    db_rem.total_sucio       = total_sucio
    db_rem.total_roto        = total_roto
    db_rem.total_extra       = total_extra
    db_rem.total_huevos      = total_huevos
    db_rem.cajas             = empaques["cajas"]
    db_rem.cubetas           = empaques["cubetas"]
    db_rem.cubetas_sobrantes = empaques["cubetas_sobrantes"]
    db_rem.unidades_sueltas  = empaques["unidades_sueltas"]

    db.commit()
    db.refresh(db_rem)
    return db_rem


# ══════════════════════════════════════════
# READ
# ══════════════════════════════════════════

def get_remision(db: Session, remision_id: str) -> Optional[Remision]:
    stmt = (
        select(Remision)
        .where(Remision.id == remision_id, Remision.is_active == True)  # noqa: E712
        .options(
            selectinload(Remision.detalles),
            selectinload(Remision.pendientes),
        )
    )
    return db.execute(stmt).scalar_one_or_none()


def get_remision_or_404(db: Session, remision_id: str) -> Remision:
    rem = get_remision(db, remision_id)
    if not rem:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Remisión '{remision_id}' no encontrada",
        )
    return rem


def list_remisiones(
    db: Session,
    *,
    granja_id: Optional[str] = None,
    fecha_desde: Optional[date] = None,
    fecha_hasta: Optional[date] = None,
    estado: Optional[EstadoRemision] = None,
    skip: int = 0,
    limit: int = 100,
) -> List[Remision]:
    stmt = (
        select(Remision)
        .where(Remision.is_active == True)  # noqa: E712
        .options(selectinload(Remision.detalles))
        .order_by(Remision.fecha.desc(), Remision.created_at.desc())
    )
    if granja_id:
        stmt = stmt.where(Remision.granja_id == granja_id)
    if fecha_desde:
        stmt = stmt.where(Remision.fecha >= fecha_desde)
    if fecha_hasta:
        stmt = stmt.where(Remision.fecha <= fecha_hasta)
    if estado:
        stmt = stmt.where(Remision.estado == estado)

    return list(db.execute(stmt.offset(skip).limit(limit)).scalars().all())


# ══════════════════════════════════════════
# UPDATE (solo Admin+)
# ══════════════════════════════════════════

def update_remision(
    db: Session,
    *,
    remision_id: str,
    obj_in: RemisionUpdate,
) -> Remision:
    db_rem = get_remision_or_404(db, remision_id)

    # Bloquear edición de cantidades directamente (deben ir por /recepcion o /sync)
    update_data = obj_in.model_dump(exclude_unset=True)
    campos_bloqueados = {"huevo_incubable", "total_sucio", "total_roto", "total_extra"}
    bloqueados = campos_bloqueados & set(update_data.keys())
    if bloqueados:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Campos {bloqueados} no se pueden editar directamente. Use /recepcion.",
        )

    for field, value in update_data.items():
        setattr(db_rem, field, value)

    db.add(db_rem)
    db.commit()
    db.refresh(db_rem)
    return db_rem


# ══════════════════════════════════════════
# SOFT DELETE
# ══════════════════════════════════════════

def soft_delete_remision(db: Session, *, remision_id: str) -> Remision:
    db_rem = get_remision_or_404(db, remision_id)
    if db_rem.estado not in (EstadoRemision.BORRADOR,):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se puede eliminar una remisión en estado '{db_rem.estado}'",
        )
    db_rem.is_active = False
    db.add(db_rem)
    db.commit()
    return db_rem


# ══════════════════════════════════════════
# RECEPCIÓN EN PLANTA (Operario Planta)
# ══════════════════════════════════════════

def registrar_recepcion(
    db: Session,
    *,
    remision_id: str,
    obj_in: RecepcionCreate,
    recibido_por_id: Optional[str] = None,
) -> Remision:
    """
    Operario Planta registra huevo_real en cada detalle.
    El sistema calcula ajuste = real - despachado automáticamente.
    Si hay diferencia → estado pasa a CON_AJUSTE.
    """
    db_rem = get_remision_or_404(db, remision_id)

    if db_rem.estado not in (EstadoRemision.ENVIADA, EstadoRemision.BORRADOR):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se puede recepcionar una remisión en estado '{db_rem.estado}'",
        )

    hay_ajuste = False

    for rec in obj_in.detalles:
        # Buscar el detalle
        detalle = db.get(RemisionDetalle, rec.detalle_id)
        if not detalle or detalle.remision_id != remision_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Detalle '{rec.detalle_id}' no pertenece a esta remisión",
            )

        detalle.huevo_real_incubable = rec.huevo_real_incubable
        detalle.huevo_real_sucio     = rec.huevo_real_sucio
        detalle.huevo_real_roto      = rec.huevo_real_roto
        detalle.huevo_real_extra     = rec.huevo_real_extra

        # Calcular ajustes
        detalle.ajuste_incubable = rec.huevo_real_incubable - detalle.huevo_incubable
        detalle.ajuste_sucio     = rec.huevo_real_sucio     - detalle.total_sucio
        detalle.ajuste_roto      = rec.huevo_real_roto      - detalle.total_roto
        detalle.ajuste_extra     = rec.huevo_real_extra     - detalle.huevo_extra

        if any([
            detalle.ajuste_incubable != 0,
            detalle.ajuste_sucio     != 0,
            detalle.ajuste_roto      != 0,
            detalle.ajuste_extra     != 0,
        ]):
            hay_ajuste = True

        if recibido_por_id:
            detalle.recibido_por_id = recibido_por_id

        if rec.observaciones:
            detalle.observaciones = rec.observaciones

        db.add(detalle)

    # Actualizar estado de la remisión
    db_rem.estado = EstadoRemision.CON_AJUSTE if hay_ajuste else EstadoRemision.RECIBIDA
    if obj_in.recibido_por:
        db_rem.recibido_por = obj_in.recibido_por

    db.add(db_rem)
    db.commit()
    db.refresh(db_rem)
    return db_rem


# ══════════════════════════════════════════
# RESUMEN DIARIO
# ══════════════════════════════════════════

def get_resumen_diario(
    db: Session,
    *,
    fecha: date,
    modulo_id: Optional[str] = None,
    granja_id: Optional[str] = None,
) -> ResumenDiarioOut:
    """
    Dos queries separadas para evitar inflado de totales por JOIN N→M.
    Query 1: totales por tipo desde remision_detalles.
    Query 2: totales de cabecera desde remisiones (sin JOIN a detalles).
    """
    # ── Query 1: por tipo de huevo (desde detalles) ──
    q_det = (
        db.query(
            func.coalesce(func.sum(RemisionDetalle.huevo_incubable), 0).label("incubable"),
            func.coalesce(func.sum(RemisionDetalle.total_sucio),     0).label("sucio"),
            func.coalesce(func.sum(RemisionDetalle.total_roto),      0).label("roto"),
            func.coalesce(func.sum(RemisionDetalle.huevo_extra),     0).label("extra"),
        )
        .join(Remision, Remision.id == RemisionDetalle.remision_id)
        .filter(Remision.fecha == fecha, Remision.is_active == True)  # noqa: E712
    )
    if modulo_id:
        q_det = q_det.filter(RemisionDetalle.modulo_id == modulo_id)
    if granja_id:
        q_det = q_det.filter(Remision.granja_id == granja_id)
    det = q_det.one()

    # ── Query 2: totales de cabecera (desde remisiones) ──
    q_rem = (
        db.query(
            func.coalesce(func.sum(Remision.total_huevos),      0).label("total_huevos"),
            func.coalesce(func.sum(Remision.cajas),             0).label("cajas"),
            func.coalesce(func.sum(Remision.cubetas),           0).label("cubetas"),
            func.coalesce(func.sum(Remision.cubetas_sobrantes), 0).label("cubetas_sobrantes"),
            func.count(Remision.id).label("num_remisiones"),
        )
        .filter(Remision.fecha == fecha, Remision.is_active == True)  # noqa: E712
    )
    if granja_id:
        q_rem = q_rem.filter(Remision.granja_id == granja_id)
    if modulo_id:
        sub = (
            select(RemisionDetalle.remision_id)
            .where(RemisionDetalle.modulo_id == modulo_id)
            .scalar_subquery()
        )
        q_rem = q_rem.filter(Remision.id.in_(sub))
    rem = q_rem.one()

    return ResumenDiarioOut(
        fecha=fecha,
        modulo_id=modulo_id,
        incubable=int(det.incubable),
        sucio=int(det.sucio),
        roto=int(det.roto),
        extra=int(det.extra),
        total_huevos=int(rem.total_huevos),
        cajas=int(rem.cajas),
        cubetas=int(rem.cubetas),
        cubetas_sobrantes=int(rem.cubetas_sobrantes),
        num_remisiones=int(rem.num_remisiones),
    )


# ══════════════════════════════════════════
# SINCRONIZACIÓN OFFLINE — /sync
# ══════════════════════════════════════════

def sync_remisiones(
    db: Session,
    *,
    payload: SyncPayload,
    creado_por_id: Optional[str] = None,
) -> SyncOut:
    """
    Upsert de todas las remisiones enviadas desde el cliente offline.
    - Si el UUID no existe → INSERT (created).
    - Si ya existe y el estado es BORRADOR → UPDATE (updated).
    - Si ya existe y está ENVIADA/RECIBIDA → conflicto (no se toca).

    El numero_remision secuencial se asigna aquí en el servidor.
    """
    resultados: List[SyncResultItem] = []
    exitosos = conflictos = 0

    # Obtener el máximo número de remisión actual
    max_num = db.execute(
        select(func.max(Remision.numero_remision))
    ).scalar() or 0
    siguiente_num = int(max_num) + 1

    for rem_in in payload.remisiones:
        existing = db.get(Remision, rem_in.id)

        # ── Conflicto: ya procesada ──
        if existing and existing.estado not in (
            EstadoRemision.BORRADOR, None
        ):
            resultados.append(SyncResultItem(
                id=rem_in.id,
                numero_remision=existing.numero_remision,
                estado="conflict",
                mensaje=f"Remisión ya en estado '{existing.estado}', no se modificó",
            ))
            conflictos += 1
            continue

        try:
            if existing:
                # UPDATE: recalcular totales con los nuevos detalles
                # Borrar detalles anteriores
                db.query(RemisionDetalle).filter(
                    RemisionDetalle.remision_id == existing.id
                ).delete()
                db.flush()

                # Reinyectar detalles
                total_incubable = total_sucio = total_roto = total_extra = total_huevos = 0
                for d in rem_in.detalles:
                    modulo_id = _resolver_modulo_id(db, d.galpon_id, d.modulo_id)
                    det = RemisionDetalle(
                        id=str(uuid.uuid4()),
                        remision_id=existing.id,
                        galpon_id=d.galpon_id,
                        modulo_id=modulo_id,
                        lote_id=d.lote_id,
                        huevo_incubable=d.huevo_incubable,
                        total_sucio=d.total_sucio,
                        total_roto=d.total_roto,
                        huevo_extra=d.huevo_extra,
                        entrada_modo=d.entrada_modo,
                    )
                    db.add(det)
                    total_incubable += d.huevo_incubable
                    total_sucio     += d.total_sucio
                    total_roto      += d.total_roto
                    total_extra     += d.huevo_extra
                    total_huevos    += d.huevo_incubable + d.total_sucio + d.total_roto + d.huevo_extra

                empaques = _calcular_empaques(total_incubable)
                existing.huevo_incubable   = total_incubable
                existing.total_sucio       = total_sucio
                existing.total_roto        = total_roto
                existing.total_extra       = total_extra
                existing.total_huevos      = total_huevos
                existing.cajas             = empaques["cajas"]
                existing.cubetas           = empaques["cubetas"]
                existing.cubetas_sobrantes = empaques["cubetas_sobrantes"]
                existing.estado            = EstadoRemision.ENVIADA
                existing.sincronizado_at   = datetime.now(timezone.utc)
                db.add(existing)
                db.commit()

                resultados.append(SyncResultItem(
                    id=existing.id,
                    numero_remision=existing.numero_remision,
                    estado="updated",
                ))

            else:
                # INSERT
                nueva = create_remision(db, obj_in=rem_in, creado_por_id=creado_por_id)
                nueva.numero_remision = siguiente_num
                nueva.estado = EstadoRemision.ENVIADA
                nueva.sincronizado_at = datetime.now(timezone.utc)
                siguiente_num += 1
                db.add(nueva)
                db.commit()

                resultados.append(SyncResultItem(
                    id=nueva.id,
                    numero_remision=nueva.numero_remision,
                    estado="created",
                ))

            exitosos += 1

        except HTTPException as exc:
            db.rollback()
            resultados.append(SyncResultItem(
                id=rem_in.id,
                numero_remision=None,
                estado="conflict",
                mensaje=exc.detail,
            ))
            conflictos += 1

    return SyncOut(
        procesados=len(payload.remisiones),
        exitosos=exitosos,
        conflictos=conflictos,
        resultados=resultados,
    )