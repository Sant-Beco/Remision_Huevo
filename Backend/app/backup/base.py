# app/models/base.py
"""
Modelo base compartido por todas las entidades.
- UUID v4 generado en el CLIENTE (para soporte offline sin colisiones).
- Auditoría automática: created_at / updated_at.
- Sin DELETE físico: se usa is_active=False (soft-delete).
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class AuditMixin:
    """
    Mixin de auditoría para todas las tablas.
    El UUID es generado por el cliente (PWA / Dexie.js) antes del envío,
    garantizando unicidad incluso sin conexión.
    """

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="UUID v4 generado en el cliente para soporte offline",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        nullable=False,
        comment="Fecha de creación (UTC)",
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        onupdate=_utcnow,
        nullable=False,
        comment="Última modificación (UTC)",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Soft-delete: False = registro desactivado, nunca eliminado físicamente",
    )