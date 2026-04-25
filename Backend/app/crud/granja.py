# app/crud/granja.py
"""
CRUD concreto para Granja, Módulo, Galpón y Lote.
Hereda de CRUDBase y agrega queries específicas de negocio.
"""
from __future__ import annotations

from datetime import date
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.crud.base import CRUDBase
from app.models.granja import Galpon, Granja, Lote, Modulo, TipoGranja
from app.schemas import (
    GalponCreate, GalponUpdate,
    GranjaCreate, GranjaUpdate,
    LoteCreate, LoteUpdate,
    ModuloCreate, ModuloUpdate,
)


# ══════════════════════════════════════════
# GRANJA
# ══════════════════════════════════════════

class CRUDGranja(CRUDBase[Granja, GranjaCreate, GranjaUpdate]):

    def get_by_nombre(self, db: Session, nombre: str) -> Optional[Granja]:
        stmt = select(Granja).where(
            Granja.nombre == nombre,
            Granja.is_active == True,  # noqa: E712
        )
        return db.execute(stmt).scalar_one_or_none()

    def create(self, db: Session, *, obj_in: GranjaCreate, extra=None) -> Granja:
        if self.get_by_nombre(db, obj_in.nombre):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Ya existe una granja con el nombre '{obj_in.nombre}'",
            )
        return super().create(db, obj_in=obj_in, extra=extra)

    def get_with_modulos(self, db: Session, granja_id: str) -> Optional[Granja]:
        """Carga granja con sus módulos y galpones en una sola query."""
        stmt = (
            select(Granja)
            .where(Granja.id == granja_id, Granja.is_active == True)  # noqa: E712
            .options(
                selectinload(Granja.modulos).selectinload(Modulo.galpones)
            )
        )
        return db.execute(stmt).scalar_one_or_none()


# ══════════════════════════════════════════
# MÓDULO
# ══════════════════════════════════════════

class CRUDModulo(CRUDBase[Modulo, ModuloCreate, ModuloUpdate]):

    def get_by_granja(self, db: Session, granja_id: str) -> List[Modulo]:
        stmt = select(Modulo).where(
            Modulo.granja_id == granja_id,
            Modulo.is_active == True,  # noqa: E712
        )
        return list(db.execute(stmt).scalars().all())

    def create(self, db: Session, *, obj_in: ModuloCreate, extra=None) -> Modulo:
        # Verificar que la granja existe
        from app.crud import granja as crud_granja_module
        granja = db.get(Granja, obj_in.granja_id)
        if not granja or not granja.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Granja '{obj_in.granja_id}' no existe o está inactiva",
            )
        return super().create(db, obj_in=obj_in, extra=extra)


# ══════════════════════════════════════════
# GALPÓN
# ══════════════════════════════════════════

class CRUDGalpon(CRUDBase[Galpon, GalponCreate, GalponUpdate]):

    def get_by_modulo(self, db: Session, modulo_id: str) -> List[Galpon]:
        stmt = select(Galpon).where(
            Galpon.modulo_id == modulo_id,
            Galpon.is_active == True,  # noqa: E712
        )
        return list(db.execute(stmt).scalars().all())

    def get_by_granja(self, db: Session, granja_id: str) -> List[Galpon]:
        """Trae todos los galpones de una granja (vía JOIN a módulos)."""
        stmt = (
            select(Galpon)
            .join(Modulo, Modulo.id == Galpon.modulo_id)
            .where(
                Modulo.granja_id == granja_id,
                Galpon.is_active == True,  # noqa: E712
                Modulo.is_active == True,  # noqa: E712
            )
        )
        return list(db.execute(stmt).scalars().all())

    def create(self, db: Session, *, obj_in: GalponCreate, extra=None) -> Galpon:
        modulo = db.get(Modulo, obj_in.modulo_id)
        if not modulo or not modulo.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Módulo '{obj_in.modulo_id}' no existe o está inactivo",
            )
        return super().create(db, obj_in=obj_in, extra=extra)

    def get_lote_activo(self, db: Session, galpon_id: str) -> Optional[Lote]:
        """Retorna el lote activo actual del galpón, si existe."""
        stmt = select(Lote).where(
            Lote.galpon_id == galpon_id,
            Lote.estado == "activo",
            Lote.is_active == True,  # noqa: E712
        )
        return db.execute(stmt).scalar_one_or_none()


# ══════════════════════════════════════════
# LOTE
# ══════════════════════════════════════════

class CRUDLote(CRUDBase[Lote, LoteCreate, LoteUpdate]):

    def get_by_codigo(self, db: Session, codigo: str) -> Optional[Lote]:
        stmt = select(Lote).where(Lote.codigo == codigo, Lote.is_active == True)  # noqa: E712
        return db.execute(stmt).scalar_one_or_none()

    def get_by_galpon(
        self,
        db: Session,
        galpon_id: str,
        solo_activos: bool = False,
    ) -> List[Lote]:
        stmt = select(Lote).where(
            Lote.galpon_id == galpon_id,
            Lote.is_active == True,  # noqa: E712
        )
        if solo_activos:
            stmt = stmt.where(Lote.estado == "activo")
        return list(db.execute(stmt).scalars().all())

    def create(self, db: Session, *, obj_in: LoteCreate, extra=None) -> Lote:
        # Código único
        if self.get_by_codigo(db, obj_in.codigo):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Ya existe un lote con el código '{obj_in.codigo}'",
            )
        # Galpón existe
        galpon = db.get(Galpon, obj_in.galpon_id)
        if not galpon or not galpon.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Galpón '{obj_in.galpon_id}' no existe o está inactivo",
            )
        return super().create(db, obj_in=obj_in, extra=extra)

    def get_edad_semanas(self, lote: Lote, referencia: Optional[date] = None) -> int:
        """
        Calcula la edad del lote en semanas desde fecha_ingreso.
        Se usa para la validación contra curva genética en La Fe.
        """
        ref = referencia or date.today()
        delta = ref - lote.fecha_ingreso
        return max(0, delta.days // 7)

    def get_historico_produccion(
        self,
        db: Session,
        lote_id: str,
        ultimas_n_semanas: int = 4,
    ) -> List[dict]:
        """
        Devuelve el promedio de huevo_incubable por semana de las últimas N semanas.
        Usado para validación ±5% en La Esperanza.
        """
        from app.models.remision import RemisionDetalle, Remision
        from sqlalchemy import func, extract

        stmt = (
            db.query(
                func.date_trunc("week", Remision.fecha).label("semana"),
                func.avg(RemisionDetalle.huevo_incubable).label("promedio"),
                func.count(RemisionDetalle.id).label("registros"),
            )
            .join(Remision, Remision.id == RemisionDetalle.remision_id)
            .filter(RemisionDetalle.lote_id == lote_id)
            .group_by("semana")
            .order_by("semana DESC")
            .limit(ultimas_n_semanas)
        )
        rows = stmt.all()
        return [
            {
                "semana": row.semana,
                "promedio": float(row.promedio or 0),
                "registros": row.registros,
            }
            for row in rows
        ]


# ── Instancias exportadas ─────────────────
granja = CRUDGranja(Granja)
modulo = CRUDModulo(Modulo)
galpon = CRUDGalpon(Galpon)
lote   = CRUDLote(Lote)