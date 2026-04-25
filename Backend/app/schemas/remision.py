# app/schemas/remision.py
"""
Schemas Pydantic v2 para Remision, RemisionDetalle, HuevoPendiente
y los schemas auxiliares de resumen diario y sincronización offline.

Flujo de datos:
  Operario Granja (PWA offline)
    → RemisionCreate  (POST /remisiones  ó  POST /sync)
    → RemisionOut     (respuesta con totales calculados)

  Operario Planta (recepción)
    → RecepcionCreate (PUT /remisiones/{id}/recepcion)
    → genera AjusteOut automático si hay diferencia

  Admin / Dashboard
    → ResumenDiarioOut  (GET /remisiones/summary)
    → SyncPayload       (POST /sync — Upsert offline)
"""
from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.remision import EstadoRemision, MotivoPendiente
from app.schemas.granja import GalponSummary, LoteSummary
from app.schemas.user import UserSummary


# ══════════════════════════════════════════
# CALCULADORA DE EMPAQUES
# Hibridez de Carga — regla de negocio central
# ══════════════════════════════════════════

class CalculadoraInput(BaseModel):
    """
    Permite al operario ingresar cantidades usando la calculadora
    en vez de digitar unidades directas.
    La suma resultante se valida en RemisionDetalleCreate.
    """
    cajas:    int = Field(0, ge=0, description="1 caja = 360 huevos")
    cubetas:  int = Field(0, ge=0, description="1 cubeta = 30 huevos")
    unidades: int = Field(0, ge=0, description="Unidades sueltas")

    @property
    def total(self) -> int:
        return (self.cajas * 360) + (self.cubetas * 30) + self.unidades


class EmpaqueOut(BaseModel):
    """Desglose de empaque calculado por el servidor (solo lectura)."""
    cajas:             int
    cubetas:           int
    cubetas_sobrantes: int
    unidades_sueltas:  int


# ══════════════════════════════════════════
# DETALLE POR GALPÓN
# ══════════════════════════════════════════

class RemisionDetalleCreate(BaseModel):
    """
    Detalle de un galpón dentro de una remisión.

    El operario puede usar:
      a) Entrada directa: llena huevo_incubable, total_sucio, etc.
      b) Calculadora: llena calculadora_incubable → el sistema convierte.

    Si ambos están presentes, la calculadora tiene prioridad.
    Si ninguno está presente para incubable, falla la validación.
    """
    galpon_id: str = Field(..., description="UUID del galpón")
    modulo_id: Optional[str] = Field(None, description="UUID del módulo (se infiere del galpón si se omite)")
    lote_id:   Optional[str] = Field(None, description="UUID del lote activo en el galpón")

    # Entrada directa
    huevo_incubable: int = Field(0, ge=0)
    total_sucio:     int = Field(0, ge=0)
    total_roto:      int = Field(0, ge=0)
    huevo_extra:     int = Field(0, ge=0)

    # Calculadora (opcional — si se proporciona, sobreescribe la entrada directa)
    calculadora_incubable: Optional[CalculadoraInput] = None

    # Modo de entrada registrado para auditoría
    entrada_modo: str = Field(
        default="directo",
        pattern="^(directo|calculadora)$",
        description="'directo' o 'calculadora'"
    )

    observaciones: Optional[str] = Field(None, max_length=300)

    @model_validator(mode="after")
    def aplicar_calculadora(self) -> "RemisionDetalleCreate":
        """Si el operario usó la calculadora, convierte cajas+cubetas+unidades → huevo_incubable."""
        if self.calculadora_incubable:
            self.huevo_incubable = self.calculadora_incubable.total
            self.entrada_modo = "calculadora"
        return self


class RemisionDetalleOut(BaseModel):
    id:        str
    galpon_id: str
    modulo_id: str
    lote_id:   Optional[str]

    # Despachado (Granja)
    huevo_incubable: int
    total_sucio:     int
    total_roto:      int
    huevo_extra:     int

    # Recibido (Planta — puede ser None si aún no se ha recepcionado)
    huevo_real_incubable: Optional[int]
    huevo_real_sucio:     Optional[int]
    huevo_real_roto:      Optional[int]
    huevo_real_extra:     Optional[int]

    # Ajuste automático (real - despachado)
    ajuste_incubable: Optional[int]
    ajuste_sucio:     Optional[int]
    ajuste_roto:      Optional[int]
    ajuste_extra:     Optional[int]

    # Empaque
    entrada_modo:    str
    entrada_cajas:   Optional[int]
    entrada_cubetas: Optional[int]
    entrada_unidades:Optional[int]

    # Validación
    validacion_estado:  Optional[str]
    validacion_mensaje: Optional[str]

    observaciones: Optional[str]

    # Relaciones anidadas
    galpon: Optional[GalponSummary] = None
    lote:   Optional[LoteSummary]   = None

    model_config = {"from_attributes": True}


# ══════════════════════════════════════════
# RECEPCIÓN EN PLANTA (Operario Planta)
# ══════════════════════════════════════════

class RecepcionDetalleCreate(BaseModel):
    """
    Registro de huevo_real por el Operario Planta para un detalle existente.
    El ajuste se calcula automáticamente en el service.
    """
    detalle_id:          str
    huevo_real_incubable: int = Field(..., ge=0)
    huevo_real_sucio:     int = Field(0, ge=0)
    huevo_real_roto:      int = Field(0, ge=0)
    huevo_real_extra:     int = Field(0, ge=0)
    observaciones:        Optional[str] = Field(None, max_length=300)


class RecepcionCreate(BaseModel):
    """PUT /remisiones/{id}/recepcion"""
    detalles:    List[RecepcionDetalleCreate]
    recibido_por: Optional[str] = Field(None, max_length=100)


# ══════════════════════════════════════════
# HUEVO PENDIENTE
# ══════════════════════════════════════════

class HuevoPendienteCreate(BaseModel):
    galpon_id:   str
    cantidad:    int          = Field(..., ge=1)
    motivo:      MotivoPendiente
    descripcion: Optional[str] = Field(None, max_length=300)


class HuevoPendienteOut(BaseModel):
    id:                      str
    galpon_id:               str
    cantidad:                int
    motivo:                  MotivoPendiente
    descripcion:             Optional[str]
    resuelto:                bool
    resuelto_en_remision_id: Optional[str]
    created_at:              datetime

    model_config = {"from_attributes": True}


# ══════════════════════════════════════════
# REMISIÓN (cabecera)
# ══════════════════════════════════════════

class RemisionCreate(BaseModel):
    """
    POST /remisiones
    El UUID (id) se genera en el cliente (PWA/Dexie.js) para soporte offline.
    Si no se envía, el servidor lo genera.
    """
    id:              Optional[str]  = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="UUID v4 generado por el cliente para soporte offline"
    )
    granja_id:       str
    fecha:           date
    fecha_produccion:Optional[date] = None
    despachado_por:  Optional[str]  = Field(None, max_length=100)
    recibido_por:    Optional[str]  = Field(None, max_length=100)
    numero_sello:    Optional[str]  = Field(None, max_length=50)
    observaciones:   Optional[str]  = Field(None, max_length=500)

    detalles:   List[RemisionDetalleCreate]  = Field(..., min_length=1)
    pendientes: List[HuevoPendienteCreate]   = Field(default_factory=list)

    @field_validator("detalles")
    @classmethod
    def al_menos_un_detalle(cls, v: list) -> list:
        if not v:
            raise ValueError("La remisión debe incluir al menos un detalle de galpón")
        return v


class RemisionUpdate(BaseModel):
    """
    PUT /remisiones/{id}
    Solo disponible para Admin Granja y SuperAdmin.
    Cualquier cambio post-creación queda en LogAuditoria.
    """
    fecha:           Optional[date] = None
    fecha_produccion:Optional[date] = None
    despachado_por:  Optional[str]  = Field(None, max_length=100)
    recibido_por:    Optional[str]  = Field(None, max_length=100)
    numero_sello:    Optional[str]  = Field(None, max_length=50)
    observaciones:   Optional[str]  = Field(None, max_length=500)
    estado:          Optional[EstadoRemision] = None


class RemisionOut(BaseModel):
    id:               str
    numero_remision:  Optional[int]
    granja_id:        str
    fecha:            date
    fecha_produccion: Optional[date]
    estado:           EstadoRemision

    # Totales calculados
    huevo_incubable:   int
    total_sucio:       int
    total_roto:        int
    total_extra:       int
    total_huevos:      int

    # Empaque
    cajas:             int
    cubetas:           int
    cubetas_sobrantes: int
    unidades_sueltas:  int

    despachado_por:  Optional[str]
    recibido_por:    Optional[str]
    numero_sello:    Optional[str]
    observaciones:   Optional[str]
    sincronizado_at: Optional[datetime]

    created_at: datetime
    updated_at: datetime

    # Relaciones
    detalles:   List[RemisionDetalleOut]  = []
    pendientes: List[HuevoPendienteOut]   = []

    model_config = {"from_attributes": True}


class RemisionSummary(BaseModel):
    """Para listados — evita cargar detalles completos."""
    id:              str
    numero_remision: Optional[int]
    granja_id:       str
    fecha:           date
    estado:          EstadoRemision
    total_huevos:    int
    cajas:           int
    created_at:      datetime

    model_config = {"from_attributes": True}


# ══════════════════════════════════════════
# RESUMEN DIARIO
# ══════════════════════════════════════════

class ResumenDiarioOut(BaseModel):
    """GET /remisiones/summary?fecha=YYYY-MM-DD&modulo_id=..."""
    fecha:             date
    modulo_id:         Optional[str]

    incubable:         int
    sucio:             int
    roto:              int
    extra:             int
    total_huevos:      int

    cajas:             int
    cubetas:           int
    cubetas_sobrantes: int

    num_remisiones:    int = Field(0, description="Cantidad de remisiones en el período")


# ══════════════════════════════════════════
# SINCRONIZACIÓN OFFLINE
# ══════════════════════════════════════════

class SyncPayload(BaseModel):
    """
    POST /sync
    El cliente envía todas las remisiones creadas offline.
    El servidor hace Upsert (INSERT ON CONFLICT DO UPDATE).
    Los UUIDs ya vienen del cliente — no se regeneran.
    """
    remisiones: List[RemisionCreate] = Field(
        ...,
        description="Lista de remisiones creadas offline, en orden cronológico"
    )
    device_id: Optional[str] = Field(
        None, max_length=100,
        description="Identificador del dispositivo para trazabilidad de sync"
    )


class SyncResultItem(BaseModel):
    id:              str
    numero_remision: Optional[int]
    estado:          str  # "created" | "updated" | "conflict"
    mensaje:         Optional[str] = None


class SyncOut(BaseModel):
    """Respuesta del endpoint /sync."""
    procesados:  int
    exitosos:    int
    conflictos:  int
    resultados:  List[SyncResultItem]