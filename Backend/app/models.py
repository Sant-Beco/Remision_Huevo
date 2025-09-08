from sqlalchemy import Column, Integer, String, ForeignKey, Date, Float
from sqlalchemy.orm import relationship
from .database import Base

class Modulo(Base):
    __tablename__ = "modulos"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(50), unique=True, index=True)  # ej: 100, 200, 600
    estado = Column(String(20), default="produccion")  # produccion / inactivo

    galpones = relationship("Galpon", back_populates="modulo")


class Galpon(Base):
    __tablename__ = "galpones"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(50), index=True)  # ej: 101, 102, 601
    modulo_id = Column(Integer, ForeignKey("modulos.id"))

    modulo = relationship("Modulo", back_populates="galpones")
    remisiones = relationship("Remision", back_populates="galpon")


class Remision(Base):
    __tablename__ = "remisiones"

    id = Column(Integer, primary_key=True, index=True)
    fecha = Column(Date)
    galpon_id = Column(Integer, ForeignKey("galpones.id"))
    huevo_incubable = Column(Integer, default=0)
    huevo_sucio = Column(Integer, default=0)
    huevo_roto = Column(Integer, default=0)
    huevo_extra = Column(Integer, default=0)
    cajas = Column(Integer, default=0)     # 360 huevos
    cubetas = Column(Integer, default=0)   # 30 huevos

    galpon = relationship("Galpon", back_populates="remisiones")
