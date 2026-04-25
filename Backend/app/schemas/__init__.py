# app/schemas/__init__.py
"""
Punto de importación único para todos los schemas Pydantic v2.
Cualquier router o service importa desde aquí.

Uso:
    from app.schemas import RemisionCreate, RemisionOut
    from app.schemas import UserOut, TokenOut
    from app.schemas import GranjaCreate, LoteOut
"""

# ── Granja / estructura ───────────────────
from .granja import (
    GranjaBase,
    GranjaCreate,
    GranjaUpdate,
    GranjaOut,
    GranjaSummary,
    ModuloBase,
    ModuloCreate,
    ModuloUpdate,
    ModuloOut,
    ModuloSummary,
    GalponBase,
    GalponCreate,
    GalponUpdate,
    GalponOut,
    GalponSummary,
    LoteBase,
    LoteCreate,
    LoteUpdate,
    LoteOut,
    LoteSummary,
)

# ── Usuarios y autenticación ──────────────
from .user import (
    UserBase,
    UserCreate,
    UserUpdate,
    UserChangePassword,
    UserOut,
    UserSummary,
    LoginRequest,
    TokenOut,
    TokenRefreshRequest,
    TokenRefreshOut,
    LogAuditoriaOut,
)

# ── Remisiones ────────────────────────────
from .remision import (
    CalculadoraInput,
    EmpaqueOut,
    RemisionDetalleCreate,
    RemisionDetalleOut,
    RecepcionDetalleCreate,
    RecepcionCreate,
    HuevoPendienteCreate,
    HuevoPendienteOut,
    RemisionCreate,
    RemisionUpdate,
    RemisionOut,
    RemisionSummary,
    ResumenDiarioOut,
    SyncPayload,
    SyncResultItem,
    SyncOut,
)

__all__ = [
    # Granja
    "GranjaBase", "GranjaCreate", "GranjaUpdate", "GranjaOut", "GranjaSummary",
    # Módulo
    "ModuloBase", "ModuloCreate", "ModuloUpdate", "ModuloOut", "ModuloSummary",
    # Galpón
    "GalponBase", "GalponCreate", "GalponUpdate", "GalponOut", "GalponSummary",
    # Lote
    "LoteBase", "LoteCreate", "LoteUpdate", "LoteOut", "LoteSummary",
    # Usuario / Auth
    "UserBase", "UserCreate", "UserUpdate", "UserChangePassword",
    "UserOut", "UserSummary",
    "LoginRequest", "TokenOut", "TokenRefreshRequest", "TokenRefreshOut",
    "LogAuditoriaOut",
    # Remisión
    "CalculadoraInput", "EmpaqueOut",
    "RemisionDetalleCreate", "RemisionDetalleOut",
    "RecepcionDetalleCreate", "RecepcionCreate",
    "HuevoPendienteCreate", "HuevoPendienteOut",
    "RemisionCreate", "RemisionUpdate", "RemisionOut", "RemisionSummary",
    "ResumenDiarioOut",
    "SyncPayload", "SyncResultItem", "SyncOut",
]