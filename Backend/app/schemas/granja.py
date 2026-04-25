# app/schemas/granja.py
"""
Schemas Pydantic v2 para Granja, Módulo, Galpón y Lote.

Convenciones:
- *Base      → campos comunes (lectura y escritura)
- *Create    → entrada al crear (POST)
- *Update    → entrada al actualizar (PUT/PATCH) — todos los campos opcionales
- *Out       → respuesta al cliente (incluye id, timestamps)
- *Summary   → versión reducida para listas y dropdowns
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.granja import EstadoGalpon, EstadoLote, TipoGranja


# ══════════════════════════════════════════
# GRANJA
# ══════════════════════════════════════════

class GranjaBase(BaseModel):
    nombre:    str       = Field(..., min_length=2, max_length=100, examples=["La Esperanza"])
    tipo:      TipoGranja = Field(..., description="madura | crecimiento")
    ubicacion: Optional[str] = Field(None, max_length=200)
    contacto:  Optional[str] = Field(None, max_length=100)


class GranjaCreate(GranjaBase):
    pass


class GranjaUpdate(BaseModel):
    nombre:    Optional[str]        = Field(None, min_length=2, max_length=100)
    tipo:      Optional[TipoGranja] = None
    ubicacion: Optional[str]        = Field(None, max_length=200)
    contacto:  Optional[str]        = Field(None, max_length=100)
    is_active: Optional[bool]       = None


class GranjaOut(GranjaBase):
    id:         str
    is_active:  bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class GranjaSummary(BaseModel):
    """Versión compacta para dropdowns y referencias en otros schemas."""
    id:     str
    nombre: str
    tipo:   TipoGranja

    model_config = {"from_attributes": True}


# ══════════════════════════════════════════
# MÓDULO
# ══════════════════════════════════════════

class ModuloBase(BaseModel):
    nombre:    str = Field(..., min_length=1, max_length=50, examples=["100"])
    estado:    str = Field(default="produccion", max_length=20)
    granja_id: str = Field(..., description="UUID de la granja a la que pertenece")


class ModuloCreate(ModuloBase):
    pass


class ModuloUpdate(BaseModel):
    nombre:    Optional[str] = Field(None, min_length=1, max_length=50)
    estado:    Optional[str] = Field(None, max_length=20)
    is_active: Optional[bool] = None


class ModuloOut(ModuloBase):
    id:         str
    is_active:  bool
    created_at: datetime
    updated_at: datetime
    granja:     GranjaSummary

    model_config = {"from_attributes": True}


class ModuloSummary(BaseModel):
    id:     str
    nombre: str
    estado: str

    model_config = {"from_attributes": True}


# ══════════════════════════════════════════
# GALPÓN
# ══════════════════════════════════════════

class GalponBase(BaseModel):
    nombre:         str          = Field(..., min_length=1, max_length=50, examples=["101"])
    estado:         EstadoGalpon = Field(default=EstadoGalpon.PRODUCCION)
    capacidad_aves: Optional[int] = Field(None, ge=0, le=100_000)
    modulo_id:      str          = Field(..., description="UUID del módulo al que pertenece")


class GalponCreate(GalponBase):
    pass


class GalponUpdate(BaseModel):
    nombre:         Optional[str]          = Field(None, min_length=1, max_length=50)
    estado:         Optional[EstadoGalpon] = None
    capacidad_aves: Optional[int]          = Field(None, ge=0, le=100_000)
    is_active:      Optional[bool]         = None


class GalponOut(GalponBase):
    id:         str
    is_active:  bool
    created_at: datetime
    updated_at: datetime
    modulo:     ModuloSummary

    model_config = {"from_attributes": True}


class GalponSummary(BaseModel):
    """Para usar en detalles de remisión y dropdowns de formulario."""
    id:        str
    nombre:    str
    estado:    EstadoGalpon
    modulo_id: str

    model_config = {"from_attributes": True}


# ══════════════════════════════════════════
# LOTE
# ══════════════════════════════════════════

class LoteBase(BaseModel):
    codigo:               str            = Field(..., min_length=3, max_length=50, examples=["LOT-2024-101-A"])
    linea_genetica:       Optional[str]  = Field(None, max_length=50, examples=["Ross 308"])
    fecha_ingreso:        date
    fecha_fin:            Optional[date] = None
    numero_aves_inicial:  int            = Field(..., ge=0, le=100_000)
    numero_aves_actual:   int            = Field(..., ge=0, le=100_000)
    estado:               EstadoLote     = Field(default=EstadoLote.ACTIVO)
    observaciones:        Optional[str]  = Field(None, max_length=500)
    curva_genetica_ref:   Optional[str]  = Field(
        None,
        description="JSON serializado: [{semana: 1, porcentaje_postura: 5.0}, ...]"
    )
    galpon_id: str = Field(..., description="UUID del galpón donde está el lote")

    @field_validator("numero_aves_actual")
    @classmethod
    def aves_actual_no_supera_inicial(cls, v: int, info) -> int:
        inicial = info.data.get("numero_aves_inicial")
        if inicial is not None and v > inicial:
            raise ValueError("numero_aves_actual no puede superar numero_aves_inicial")
        return v

    @model_validator(mode="after")
    def fecha_fin_posterior_a_ingreso(self) -> "LoteBase":
        if self.fecha_fin and self.fecha_fin <= self.fecha_ingreso:
            raise ValueError("fecha_fin debe ser posterior a fecha_ingreso")
        return self


class LoteCreate(LoteBase):
    pass


class LoteUpdate(BaseModel):
    linea_genetica:     Optional[str]       = Field(None, max_length=50)
    fecha_fin:          Optional[date]      = None
    numero_aves_actual: Optional[int]       = Field(None, ge=0)
    estado:             Optional[EstadoLote] = None
    observaciones:      Optional[str]       = Field(None, max_length=500)
    curva_genetica_ref: Optional[str]       = None
    is_active:          Optional[bool]      = None


class LoteOut(LoteBase):
    id:         str
    is_active:  bool
    created_at: datetime
    updated_at: datetime

    # Campos calculados (se computan en el router/service, no en la BD)
    edad_semanas: Optional[int] = Field(
        None, description="Semanas de vida del lote desde fecha_ingreso hasta hoy"
    )

    model_config = {"from_attributes": True}


class LoteSummary(BaseModel):
    """Para referenciar el lote activo dentro de un detalle de remisión."""
    id:             str
    codigo:         str
    linea_genetica: Optional[str]
    estado:         EstadoLote
    edad_semanas:   Optional[int] = None

    model_config = {"from_attributes": True}