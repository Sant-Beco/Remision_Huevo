# app/models/__init__.py
"""
Punto de importación único para todos los modelos.
Alembic y cualquier módulo del sistema importan desde aquí.

Uso:
    from app.models import Base, Granja, Galpon, Lote
    from app.models import Remision, RemisionDetalle, HuevoPendiente
    from app.models import User, LogAuditoria
"""

from .base import Base, AuditMixin

from .user import User, Rol, LogAuditoria

from .granja import (
    Granja,
    TipoGranja,
    Modulo,
    Galpon,
    EstadoGalpon,
    Lote,
    EstadoLote,
)

from .remision import (
    Remision,
    EstadoRemision,
    RemisionDetalle,
    HuevoPendiente,
    MotivoPendiente,
)

__all__ = [
    # Base
    "Base",
    "AuditMixin",
    # Usuarios
    "User",
    "Rol",
    "LogAuditoria",
    # Granja / estructura
    "Granja",
    "TipoGranja",
    "Modulo",
    "Galpon",
    "EstadoGalpon",
    "Lote",
    "EstadoLote",
    # Remisiones
    "Remision",
    "EstadoRemision",
    "RemisionDetalle",
    "HuevoPendiente",
    "MotivoPendiente",
]