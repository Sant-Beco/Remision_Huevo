from pydantic import BaseModel
from datetime import date

# ===== Remisiones =====
class RemisionBase(BaseModel):
    fecha: date
    galpon_id: int
    modulo_id: int
    huevo_incubable: int
    huevo_sucio: int
    huevo_roto: int
    huevo_extra: int


class RemisionCreate(RemisionBase):
    pass


class Remision(RemisionBase):
    id: int
    cajas: int   # 👈 calculados
    cubetas: int

    class Config:
        from_attributes = True



# ===== Módulos =====
class ModuloBase(BaseModel):
    nombre: str
    estado: str = "produccion"

class ModuloCreate(ModuloBase):
    pass

class Modulo(ModuloBase):
    id: int
    class Config:
        from_attributes = True


# ===== Galpones =====
class GalponBase(BaseModel):
    nombre: str
    modulo_id: int

class GalponCreate(GalponBase):
    pass

class Galpon(GalponBase):
    id: int
    class Config:
        from_attributes = True


