# app/schemas.py
from pydantic import BaseModel, Field
from datetime import date, datetime
from typing import List, Optional

class RemisionDetalleBase(BaseModel):
    galpon_id: int
    modulo_id: Optional[int] = None
    huevo_incubable: int = Field(ge=0)
    huevo_sucio: int = Field(ge=0)
    huevo_roto: int = Field(ge=0)
    huevo_extra: int = Field(ge=0)

class RemisionDetalleCreate(RemisionDetalleBase):
    pass

class RemisionDetalle(RemisionDetalleBase):
    id: int
    class Config:
        from_attributes = True

class RemisionBase(BaseModel):
    fecha: date
    fecha_produccion: Optional[date] = None
    observaciones: Optional[str] = None
    despachado_por: Optional[str] = None
    recibido_por: Optional[str] = None
    numero_sello: Optional[str] = None

class RemisionCreate(RemisionBase):
    detalles: List[RemisionDetalleCreate]

class Remision(RemisionBase):
    id: int
    numero_remision: Optional[int]
    total_huevos: int
    cajas: int
    cubetas: int
    cubetas_sobrantes: int
    detalles: List[RemisionDetalle]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Modulo / Galpon schemas (iguales que antes)
class ModuloBase(BaseModel):
    nombre: str
    estado: str = "produccion"
class ModuloCreate(ModuloBase): pass
class Modulo(ModuloBase):
    id: int
    class Config:
        from_attributes = True

class GalponBase(BaseModel):
    nombre: str
    modulo_id: int
class GalponCreate(GalponBase): pass
class Galpon(GalponBase):
    id: int
    class Config:
        from_attributes = True


class DailySummary(BaseModel):
    incubable: int
    sucio: int
    roto: int
    extra: int
    total_huevos: int
    cajas: int
    cubetas: int
    cubetas_sobrantes: int

