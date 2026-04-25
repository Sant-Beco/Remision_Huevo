# app/models/remision.py
"""
Modelos: Remision, RemisionDetalle, HuevoPendiente

Flujo operativo:
  1. Operario Granja crea Remision + detalles por galpón (offline, UUID cliente).
  2. Operario Planta registra "huevo_real" recibido en cada detalle.
  3. Si huevo_real ≠ huevo_despachado → sistema genera Ajuste automático.
  4. Si el camión se llena o faltan cajas → HuevoPendiente con motivo.
  5. Toda edición posterior queda en LogAuditoria (tabla separada).

Cálculo de empaques (Hibridez de Carga):
  cajas             = huevo_incubable // 360
  cubetas_completas = huevo_incubable // 30
  cubetas_sobrantes = (huevo_incubable % 360) // 30
  unidades_sueltas  = huevo_incubable % 30
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (
    Date, DateTime, ForeignKey, Integer, Numeric,
    String, Text, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import AuditMixin, Base

if TYPE_CHECKING:
    from .granja import Galpon, Lote, Modulo
    from .user import User


# ─────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────

class EstadoRemision(str, Enum):
    BORRADOR    = "borrador"    # Creada offline, pendiente de envío
    ENVIADA     = "enviada"     # Sincronizada con servidor, read-only para operario
    RECIBIDA    = "recibida"    # Planta confirmó recepción
    CON_AJUSTE  = "con_ajuste"  # Planta registró diferencia → ajuste generado
    CERRADA     = "cerrada"     # Admin Planta cerró inventario del día


class MotivoPendiente(str, Enum):
    CAMION_LLENO      = "camion_lleno"
    FALTA_CAJAS       = "falta_cajas"
    AVE_MUERTA        = "ave_muerta"
    HUEVO_NO_APTO     = "huevo_no_apto"
    OTRO              = "otro"


# ─────────────────────────────────────────────
# Remisión (cabecera)
# ─────────────────────────────────────────────

class Remision(AuditMixin, Base):
    """
    Documento principal de despacho de huevo desde granja hacia planta.

    numero_remision: se asigna en el SERVIDOR al sincronizar (no en cliente)
    para garantizar secuencia sin gaps visible en documentos físicos.

    El UUID (id) se genera en el cliente para permitir trabajo offline.
    """
    __tablename__ = "remisiones"

    # Número secuencial legible (asignado por servidor en /sync)
    numero_remision: Mapped[Optional[int]] = mapped_column(
        Integer, unique=True, nullable=True,
        comment="Número secuencial asignado al sincronizar con el servidor"
    )

    # Fechas
    fecha: Mapped[date] = mapped_column(
        Date, nullable=False,
        comment="Fecha de despacho desde la granja"
    )
    fecha_produccion: Mapped[Optional[date]] = mapped_column(
        Date, nullable=True,
        comment="Fecha en que fue puesto el huevo (puede diferir del despacho)"
    )

    # Estado del documento
    estado: Mapped[EstadoRemision] = mapped_column(
        String(20), default=EstadoRemision.BORRADOR, nullable=False
    )

    # Totales de cabecera (calculados desde detalles)
    huevo_incubable:    Mapped[int] = mapped_column(Integer, default=0)
    total_sucio:        Mapped[int] = mapped_column(Integer, default=0)
    total_roto:         Mapped[int] = mapped_column(Integer, default=0)
    total_extra:        Mapped[int] = mapped_column(Integer, default=0)
    total_huevos:       Mapped[int] = mapped_column(Integer, default=0)

    # Empaques calculados (Hibridez de Carga)
    cajas:              Mapped[int] = mapped_column(Integer, default=0, comment="= huevo_incubable // 360")
    cubetas:            Mapped[int] = mapped_column(Integer, default=0, comment="= huevo_incubable // 30")
    cubetas_sobrantes:  Mapped[int] = mapped_column(Integer, default=0, comment="= (huevo_incubable % 360) // 30")
    unidades_sueltas:   Mapped[int] = mapped_column(Integer, default=0, comment="= huevo_incubable % 30")

    # Personal
    despachado_por: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    recibido_por:   Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    numero_sello:   Mapped[Optional[str]] = mapped_column(String(50),  nullable=True)
    observaciones:  Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Marca de sincronización (para Upsert en /sync)
    sincronizado_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="Timestamp de última sincronización exitosa con el servidor"
    )

    # FKs
    granja_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("granjas.id", ondelete="RESTRICT"), nullable=False
    )
    creado_por_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
        comment="Operario granja que creó el documento"
    )

    # Relaciones
    detalles: Mapped[List["RemisionDetalle"]] = relationship(
        "RemisionDetalle",
        back_populates="remision",
        cascade="all, delete-orphan",
        lazy="select",
    )
    pendientes: Mapped[List["HuevoPendiente"]] = relationship(
        "HuevoPendiente",
        back_populates="remision",
        cascade="all, delete-orphan",
    )


# ─────────────────────────────────────────────
# Detalle por Galpón
# ─────────────────────────────────────────────

class RemisionDetalle(AuditMixin, Base):
    """
    Línea de detalle: cantidad de huevo por tipo para un galpón específico.

    huevo_real_*: registrado por Operario Planta al recibir.
    Si difiere de lo despachado → campo ajuste_* se calcula automáticamente.

    HIBRIDEZ DE CARGA:
    El campo entrada_modo indica si el operario usó entrada directa
    o la calculadora de cajas/cubetas/unidades.
    """
    __tablename__ = "remision_detalles"

    # Cantidades despachadas (Operario Granja)
    huevo_incubable: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_sucio:     Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_roto:      Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    huevo_extra:     Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Cantidades recibidas (Operario Planta — Azar)
    huevo_real_incubable: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    huevo_real_sucio:     Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    huevo_real_roto:      Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    huevo_real_extra:     Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Ajuste automático (calculado: real - despachado)
    ajuste_incubable: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    ajuste_sucio:     Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    ajuste_roto:      Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    ajuste_extra:     Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Metadata de entrada (Hibridez de Carga)
    entrada_modo: Mapped[str] = mapped_column(
        String(20), default="directo", nullable=False,
        comment="'directo' = unidades, 'calculadora' = cajas+cubetas+unidades"
    )
    # Desglose si usó calculadora
    entrada_cajas:   Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    entrada_cubetas: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    entrada_unidades:Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Validación contra histórico / curva genética
    validacion_estado:  Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True,
        comment="ok / alerta / fuera_rango"
    )
    validacion_mensaje: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="Explicación del resultado de validación"
    )

    observaciones: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # FKs
    remision_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("remisiones.id", ondelete="CASCADE"), nullable=False
    )
    galpon_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("galpones.id", ondelete="RESTRICT"), nullable=False
    )
    modulo_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("modulos.id", ondelete="RESTRICT"), nullable=False
    )
    lote_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("lotes.id", ondelete="SET NULL"), nullable=True,
        comment="Lote activo en el galpón al momento del despacho"
    )
    recibido_por_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
        comment="Operario Planta que registró los valores reales"
    )

    # Relaciones
    remision: Mapped["Remision"] = relationship("Remision", back_populates="detalles")
    galpon:   Mapped["Galpon"]   = relationship("Galpon",   back_populates="remision_detalles")
    lote:     Mapped[Optional["Lote"]] = relationship("Lote", back_populates="remision_detalles")


# ─────────────────────────────────────────────
# Huevo Pendiente
# ─────────────────────────────────────────────

class HuevoPendiente(AuditMixin, Base):
    """
    Registro de huevo que no pudo despacharse en la remisión original.
    Motivo obligatorio. Se asocia a la remisión del día y al galpón.
    Se resuelve en la próxima remisión vinculándolo como 'pendiente_resuelto'.
    """
    __tablename__ = "huevos_pendientes"

    cantidad:          Mapped[int]         = mapped_column(Integer, nullable=False)
    motivo:            Mapped[MotivoPendiente] = mapped_column(String(30), nullable=False)
    descripcion:       Mapped[Optional[str]]   = mapped_column(Text, nullable=True)
    resuelto:          Mapped[bool]            = mapped_column(default=False, nullable=False)
    resuelto_en_remision_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("remisiones.id", ondelete="SET NULL"), nullable=True
    )

    # FKs
    remision_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("remisiones.id", ondelete="RESTRICT"), nullable=False
    )
    galpon_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("galpones.id", ondelete="RESTRICT"), nullable=False
    )

    # Relaciones
    remision: Mapped["Remision"] = relationship(
        "Remision", back_populates="pendientes",
        foreign_keys=[remision_id]
    )