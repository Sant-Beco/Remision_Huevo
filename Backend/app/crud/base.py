# app/crud/base.py
"""
CRUD genérico parametrizado por tipo de modelo y schema.
Todas las operaciones concretas heredan de esta clase
y solo sobreescriben lo que necesiten.

Principios aplicados:
- Soft-delete: nunca se elimina físicamente (is_active = False).
- UUID como PK string: compatible con generación en cliente (offline).
- Pydantic v2: usa .model_dump() en vez de .dict().
- Type-safe: Generic[ModelType, CreateSchema, UpdateSchema].
"""
from __future__ import annotations

from typing import Any, Dict, Generic, List, Optional, Type, TypeVar

from fastapi import HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.base import Base

ModelType      = TypeVar("ModelType", bound=Base)
CreateSchema   = TypeVar("CreateSchema", bound=BaseModel)
UpdateSchema   = TypeVar("UpdateSchema", bound=BaseModel)


class CRUDBase(Generic[ModelType, CreateSchema, UpdateSchema]):

    def __init__(self, model: Type[ModelType]):
        self.model = model

    # ─────────────────────────────────────
    # READ
    # ─────────────────────────────────────

    def get(self, db: Session, id: str) -> Optional[ModelType]:
        """Obtiene un registro por UUID. Retorna None si no existe o está inactivo."""
        stmt = select(self.model).where(
            self.model.id == id,
            self.model.is_active == True,  # noqa: E712
        )
        return db.execute(stmt).scalar_one_or_none()

    def get_or_404(self, db: Session, id: str) -> ModelType:
        """Como get(), pero lanza HTTP 404 si no encuentra."""
        obj = self.get(db, id)
        if not obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"{self.model.__tablename__} con id '{id}' no encontrado",
            )
        return obj

    def get_multi(
        self,
        db: Session,
        *,
        skip: int = 0,
        limit: int = 100,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[ModelType]:
        """
        Lista registros activos con paginación.
        `filters` acepta pares {campo: valor} para filtros exactos simples.
        """
        stmt = select(self.model).where(self.model.is_active == True)  # noqa: E712

        if filters:
            for field, value in filters.items():
                if value is not None and hasattr(self.model, field):
                    stmt = stmt.where(getattr(self.model, field) == value)

        stmt = stmt.offset(skip).limit(limit)
        return list(db.execute(stmt).scalars().all())

    def count(
        self,
        db: Session,
        filters: Optional[Dict[str, Any]] = None,
    ) -> int:
        from sqlalchemy import func
        stmt = select(func.count()).select_from(self.model).where(
            self.model.is_active == True  # noqa: E712
        )
        if filters:
            for field, value in filters.items():
                if value is not None and hasattr(self.model, field):
                    stmt = stmt.where(getattr(self.model, field) == value)
        return db.execute(stmt).scalar_one()

    # ─────────────────────────────────────
    # CREATE
    # ─────────────────────────────────────

    def create(
        self,
        db: Session,
        *,
        obj_in: CreateSchema,
        extra: Optional[Dict[str, Any]] = None,
    ) -> ModelType:
        """
        Crea un nuevo registro.
        `extra` permite inyectar campos calculados o FKs que no vienen
        directamente del schema (ej: creado_por_id desde el JWT).
        """
        data = obj_in.model_dump(exclude_unset=False)
        if extra:
            data.update(extra)

        db_obj = self.model(**data)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    # ─────────────────────────────────────
    # UPDATE
    # ─────────────────────────────────────

    def update(
        self,
        db: Session,
        *,
        db_obj: ModelType,
        obj_in: UpdateSchema | Dict[str, Any],
    ) -> ModelType:
        """
        Actualiza solo los campos enviados (exclude_unset=True).
        Nunca toca campos no incluidos en el payload.
        """
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            if hasattr(db_obj, field):
                setattr(db_obj, field, value)

        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    # ─────────────────────────────────────
    # SOFT DELETE
    # ─────────────────────────────────────

    def soft_delete(self, db: Session, *, id: str) -> ModelType:
        """
        Marca is_active = False. NUNCA elimina físicamente.
        Lanza 404 si el registro no existe o ya está inactivo.
        """
        db_obj = self.get_or_404(db, id)
        db_obj.is_active = False
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    # ─────────────────────────────────────
    # UPSERT (para sincronización offline)
    # ─────────────────────────────────────

    def upsert(
        self,
        db: Session,
        *,
        obj_in: CreateSchema,
        extra: Optional[Dict[str, Any]] = None,
    ) -> tuple[ModelType, bool]:
        """
        INSERT si el UUID no existe, UPDATE si ya existe.
        Retorna (objeto, created) donde created=True si fue INSERT.
        Usado por el endpoint /sync para reconciliar datos offline.
        """
        data = obj_in.model_dump(exclude_unset=False)
        if extra:
            data.update(extra)

        record_id = data.get("id")
        existing = None
        if record_id:
            existing = db.get(self.model, record_id)

        if existing:
            for field, value in data.items():
                if hasattr(existing, field) and field != "id":
                    setattr(existing, field, value)
            db.add(existing)
            db.commit()
            db.refresh(existing)
            return existing, False
        else:
            db_obj = self.model(**data)
            db.add(db_obj)
            db.commit()
            db.refresh(db_obj)
            return db_obj, True