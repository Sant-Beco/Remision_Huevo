from pydantic import BaseModel, Field
from datetime import date, datetime

class RemisionBase(BaseModel):
    fecha: date
    fecha_produccion: date | None = None
    galpon_id: int
    modulo_id: int
    huevo_incubable: int = Field(ge=0)
    huevo_sucio: int = Field(ge=0)
    huevo_roto: int = Field(ge=0)
    huevo_extra: int = Field(ge=0)
    observaciones: str | None = None
    despachado_por: str | None = None
    recibido_por: str | None = None
    numero_sello: str | None = None

class RemisionCreate(RemisionBase):
    pass

class Remision(RemisionBase):
    id: int
    numero_remision: int | None
    total_huevos: int
    cajas: int
    cubetas: int
    cubetas_sobrantes: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Keep Modulo/Galpon schemas as you already have, add from_attributes=True
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


