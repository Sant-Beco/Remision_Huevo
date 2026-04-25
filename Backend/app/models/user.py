# app/models/user.py
"""
Modelos: User (con roles) y LogAuditoria (shadow log inmutable).

ROLES (Matriz de permisos del Master Prompt):
  - operario_granja  : Crea remisiones. Read-only post-envío.
  - operario_planta  : Registra huevo_real. Genera ajustes.
  - admin_granja     : Historial, datos masivos, gestión de lotes.
  - admin_planta     : Valida saldos globales, cierra inventarios.
  - superadmin       : Gestión total: usuarios, galpones, auditoría.

LogAuditoria:
  INMUTABLE — No se actualiza ni elimina nunca.
  Registra cualquier cambio en cantidades post-creación.
  Campos obligatorios: tabla, registro_id, campo, valor_anterior,
                       valor_nuevo, usuario_id, timestamp.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import AuditMixin, Base


# ─────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────

class Rol(str, Enum):
    OPERARIO_GRANJA  = "operario_granja"
    OPERARIO_PLANTA  = "operario_planta"
    ADMIN_GRANJA     = "admin_granja"
    ADMIN_PLANTA     = "admin_planta"
    SUPERADMIN       = "superadmin"


# ─────────────────────────────────────────────
# Usuario
# ─────────────────────────────────────────────

class User(AuditMixin, Base):
    """
    Usuario del sistema. El rol determina permisos en cada endpoint.
    La contraseña se almacena siempre hasheada (bcrypt vía passlib).
    """
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    nombre: Mapped[str] = mapped_column(
        String(100), nullable=False
    )
    hashed_password: Mapped[str] = mapped_column(
        String(255), nullable=False
    )
    rol: Mapped[Rol] = mapped_column(
        String(30), nullable=False, default=Rol.OPERARIO_GRANJA
    )

    # Granja asignada (null = acceso a todas → superadmin / admin_planta)
    granja_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("granjas.id", ondelete="SET NULL"), nullable=True,
        comment="Granja a la que pertenece este usuario. NULL = acceso global."
    )

    # Refresh token almacenado para invalidación
    refresh_token: Mapped[Optional[str]] = mapped_column(
        String(512), nullable=True
    )

    # Relaciones (lazy para no cargar siempre)
    logs: Mapped[list["LogAuditoria"]] = relationship(
        "LogAuditoria", back_populates="usuario", lazy="dynamic"
    )


# ─────────────────────────────────────────────
# Log de Auditoría — INMUTABLE (Shadow Log)
# ─────────────────────────────────────────────

class LogAuditoria(Base):
    """
    Registro INMUTABLE de cada cambio en el sistema.

    REGLAS:
    - No tiene AuditMixin (no necesita updated_at ni is_active).
    - Nunca se modifica ni elimina (la BD debe tener la tabla en schema
      separado o con trigger que rechace UPDATE/DELETE).
    - El campo 'accion' puede ser: CREATE, UPDATE, SYNC, AJUSTE.
    - 'valor_anterior' y 'valor_nuevo' se serializan como JSON string.
    - Cuando se llama a /sync, cada Upsert genera un log con accion=SYNC.

    Índices recomendados: (tabla_afectada, registro_id), (usuario_id), (timestamp)
    """
    __tablename__ = "log_auditoria"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True,
        comment="UUID generado en el servidor al momento de registrar el log"
    )

    # Qué cambió
    tabla_afectada: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True,
        comment="Nombre de la tabla modificada (ej: 'remision_detalles')"
    )
    registro_id: Mapped[str] = mapped_column(
        String(36), nullable=False, index=True,
        comment="UUID del registro afectado"
    )
    campo: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True,
        comment="Campo específico modificado (null si es CREATE completo)"
    )
    accion: Mapped[str] = mapped_column(
        String(20), nullable=False,
        comment="CREATE | UPDATE | SYNC | AJUSTE | SOFT_DELETE"
    )

    # Valores antes y después
    valor_anterior: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="Valor anterior serializado como JSON"
    )
    valor_nuevo: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="Valor nuevo serializado como JSON"
    )

    # Contexto
    motivo: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="Razón del cambio (ingresada por el usuario o generada por el sistema)"
    )
    ip_origen: Mapped[Optional[str]] = mapped_column(
        String(45), nullable=True,
        comment="IP del cliente. Soporta IPv6 (máx 45 chars)."
    )
    user_agent: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )

    # Cuándo y quién
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
    usuario_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
        index=True,
    )

    # Relación (solo lectura)
    usuario: Mapped[Optional["User"]] = relationship(
        "User", back_populates="logs"
    )