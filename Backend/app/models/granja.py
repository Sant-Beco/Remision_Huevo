# app/models/granja.py
"""
Modelos: Granja → Módulo → Galpón → Lote
Jerarquía operativa real de Antioqueña de Incubación S.A.S.

Granjas conocidas:
  - "La Esperanza" (granja madura): validación por promedio histórico ±5%
  - "La Fe" (granja en crecimiento): validación contra curva genética por edad de lote
"""
from __future__ import annotations

from datetime import date
from enum import Enum
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Date, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import AuditMixin, Base

if TYPE_CHECKING:
    from .remision import Remision, RemisionDetalle
    from .user import User


# ─────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────

class TipoGranja(str, Enum):
    MADURA     = "madura"       # La Esperanza — validación por histórico ±5%
    CRECIMIENTO = "crecimiento" # La Fe — validación por curva genética


class EstadoGalpon(str, Enum):
    PRODUCCION = "produccion"
    DESCANSO   = "descanso"
    CUARENTENA = "cuarentena"


class EstadoLote(str, Enum):
    ACTIVO    = "activo"
    FINALIZADO = "finalizado"
    DESCARTE  = "descarte"


# ─────────────────────────────────────────────
# Granja
# ─────────────────────────────────────────────

class Granja(AuditMixin, Base):
    """
    Unidad productiva top-level.
    Dos granjas actualmente: La Esperanza y La Fe.
    El tipo determina la lógica de validación de remisiones.
    """
    __tablename__ = "granjas"

    nombre: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False,
        comment="Nombre de la granja (ej: 'La Esperanza')"
    )
    tipo: Mapped[TipoGranja] = mapped_column(
        String(20), nullable=False,
        comment="madura=histórico±5% / crecimiento=curva genética"
    )
    ubicacion: Mapped[Optional[str]] = mapped_column(
        String(200), nullable=True,
        comment="Dirección o descripción geográfica"
    )
    contacto: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True,
        comment="Encargado o contacto principal"
    )

    # Relaciones
    modulos: Mapped[List["Modulo"]] = relationship(
        "Modulo", back_populates="granja", cascade="all, delete-orphan"
    )


# ─────────────────────────────────────────────
# Módulo
# ─────────────────────────────────────────────

class Modulo(AuditMixin, Base):
    """
    Agrupación de galpones dentro de una granja.
    Ej: Módulo '100', Módulo '200'.
    """
    __tablename__ = "modulos"

    nombre: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="Nombre del módulo (ej: '100')"
    )
    estado: Mapped[str] = mapped_column(
        String(20), default="produccion", nullable=False
    )

    # FK
    granja_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("granjas.id", ondelete="RESTRICT"), nullable=False
    )

    # Relaciones
    granja: Mapped["Granja"] = relationship("Granja", back_populates="modulos")
    galpones: Mapped[List["Galpon"]] = relationship(
        "Galpon", back_populates="modulo", cascade="all, delete-orphan"
    )


# ─────────────────────────────────────────────
# Galpón
# ─────────────────────────────────────────────

class Galpon(AuditMixin, Base):
    """
    Unidad física de alojamiento de aves.
    Contiene uno o más lotes a lo largo del tiempo.
    """
    __tablename__ = "galpones"

    nombre: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="Nombre del galpón (ej: '101', '102')"
    )
    estado: Mapped[EstadoGalpon] = mapped_column(
        String(20), default=EstadoGalpon.PRODUCCION, nullable=False
    )
    capacidad_aves: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True,
        comment="Capacidad máxima de aves en el galpón"
    )

    # FK
    modulo_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("modulos.id", ondelete="RESTRICT"), nullable=False
    )

    # Relaciones
    modulo: Mapped["Modulo"] = relationship("Modulo", back_populates="galpones")
    lotes: Mapped[List["Lote"]] = relationship(
        "Lote", back_populates="galpon", cascade="all, delete-orphan"
    )
    remision_detalles: Mapped[List["RemisionDetalle"]] = relationship(
        "RemisionDetalle", back_populates="galpon"
    )


# ─────────────────────────────────────────────
# Lote
# ─────────────────────────────────────────────

class Lote(AuditMixin, Base):
    """
    Grupo de aves con la misma fecha de ingreso y línea genética.

    CRÍTICO para La Fe (granja crecimiento):
    La edad_semanas se calcula desde fecha_ingreso para comparar
    contra la curva genética teórica de producción semanal.

    Para La Esperanza (granja madura):
    El sistema promedia el histórico de este lote y valida ±5%.
    """
    __tablename__ = "lotes"

    codigo: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False,
        comment="Código único del lote (ej: 'LOT-2024-101-A')"
    )
    linea_genetica: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True,
        comment="Línea genética (ej: 'Ross 308', 'Cobb 500')"
    )
    fecha_ingreso: Mapped[date] = mapped_column(
        Date, nullable=False,
        comment="Fecha en que las aves ingresaron al galpón"
    )
    fecha_fin: Mapped[Optional[date]] = mapped_column(
        Date, nullable=True,
        comment="Fecha de salida o sacrificio del lote"
    )
    numero_aves_inicial: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="Cantidad de aves al inicio del lote"
    )
    numero_aves_actual: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="Cantidad de aves vivas actualmente (se actualiza por mortalidad)"
    )
    estado: Mapped[EstadoLote] = mapped_column(
        String(20), default=EstadoLote.ACTIVO, nullable=False
    )
    observaciones: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )

    # Curva genética teórica (solo aplica a La Fe)
    # Almacena JSON [{semana: 1, porcentaje_postura: 5.0}, ...]
    # Se compara contra producción real para validación
    curva_genetica_ref: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="JSON con curva genética teórica por semana de vida"
    )

    # FK
    galpon_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("galpones.id", ondelete="RESTRICT"), nullable=False
    )

    # Relaciones
    galpon: Mapped["Galpon"] = relationship("Galpon", back_populates="lotes")
    remision_detalles: Mapped[List["RemisionDetalle"]] = relationship(
        "RemisionDetalle", back_populates="lote"
    )