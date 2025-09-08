from pydantic import BaseModel
from datetime import date

class RemisionBase(BaseModel):
    fecha: date
    galpon_id: int
    huevo_incubable: int
    huevo_sucio: int
    huevo_roto: int
    huevo_extra: int
    cajas: int
    cubetas: int

class RemisionCreate(RemisionBase):
    pass

class Remision(RemisionBase):
    id: int

    class Config:
        orm_mode = True
