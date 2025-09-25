# app/models.py
from sqlalchemy import Column, Integer, String, ForeignKey, Date, DateTime, func
from sqlalchemy.orm import relationship
from .database import Base

class Modulo(Base):
    __tablename__ = "modulos"
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(50), unique=True, index=True)  # ej: "100"
    estado = Column(String(20), default="produccion")
    galpones = relationship("Galpon", back_populates="modulo")

class Galpon(Base):
    __tablename__ = "galpones"
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(50), index=True)  # ej: "101"
    modulo_id = Column(Integer, ForeignKey("modulos.id"))
    modulo = relationship("Modulo", back_populates="galpones")
    remision_detalles = relationship("RemisionDetalle", back_populates="galpon")

class Remision(Base):
    __tablename__ = "remisiones"
    id = Column(Integer, primary_key=True, index=True)

    numero_remision = Column(Integer, unique=True, index=True, nullable=True)  # asignaremos con id
    fecha = Column(Date, nullable=False)
    fecha_produccion = Column(Date, nullable=True)

    # cabecera (sin galpon directo: los galpones van en detalles)
    total_huevos = Column(Integer, default=0)
    cajas = Column(Integer, default=0)
    cubetas = Column(Integer, default=0)
    cubetas_sobrantes = Column(Integer, default=0)

    observaciones = Column(String(255), nullable=True)
    despachado_por = Column(String(100), nullable=True)
    recibido_por = Column(String(100), nullable=True)
    numero_sello = Column(String(50), nullable=True)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    detalles = relationship("RemisionDetalle", back_populates="remision", cascade="all, delete-orphan")


class RemisionDetalle(Base):
    __tablename__ = "remision_detalles"
    id = Column(Integer, primary_key=True, index=True)
    remision_id = Column(Integer, ForeignKey("remisiones.id", ondelete="CASCADE"))
    galpon_id = Column(Integer, ForeignKey("galpones.id"))
    modulo_id = Column(Integer, ForeignKey("modulos.id"))

    huevo_incubable = Column(Integer, default=0)
    huevo_sucio = Column(Integer, default=0)
    huevo_roto = Column(Integer, default=0)
    huevo_extra = Column(Integer, default=0)

    remision = relationship("Remision", back_populates="detalles")
    galpon = relationship("Galpon", back_populates="remision_detalles")
    # modulo relationship no es estrictamente necesaria, pero puedes añadirla:
    # modulo = relationship("Modulo")



