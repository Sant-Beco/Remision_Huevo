# app/schemas/user.py
"""
Schemas Pydantic v2 para User y autenticación JWT.

La contraseña NUNCA viaja en schemas de respuesta (*Out).
El campo hashed_password vive solo en el modelo SQLAlchemy.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models.user import Rol


# ══════════════════════════════════════════
# USER
# ══════════════════════════════════════════

class UserBase(BaseModel):
    email:     EmailStr = Field(..., examples=["operario@incubant.co"])
    nombre:    str      = Field(..., min_length=2, max_length=100, examples=["Carlos Ríos"])
    rol:       Rol      = Field(default=Rol.OPERARIO_GRANJA)
    granja_id: Optional[str] = Field(
        None,
        description="UUID de la granja asignada. None = acceso global (superadmin / admin_planta)"
    )


class UserCreate(UserBase):
    password: str = Field(
        ...,
        min_length=8,
        max_length=64,
        description="Contraseña en texto plano — se hashea antes de persistir",
        examples=["S3guroIncubant!"],
    )


class UserUpdate(BaseModel):
    nombre:    Optional[str]  = Field(None, min_length=2, max_length=100)
    rol:       Optional[Rol]  = None
    granja_id: Optional[str]  = None
    is_active: Optional[bool] = None


class UserChangePassword(BaseModel):
    password_actual: str = Field(..., min_length=8)
    password_nuevo:  str = Field(..., min_length=8, max_length=64)

    @field_validator("password_nuevo")
    @classmethod
    def distinto_al_actual(cls, v: str, info) -> str:
        if v == info.data.get("password_actual"):
            raise ValueError("La contraseña nueva debe ser diferente a la actual")
        return v


class UserOut(UserBase):
    id:         str
    is_active:  bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UserSummary(BaseModel):
    """Para referencias en remisiones (despachado_por, recibido_por)."""
    id:     str
    nombre: str
    rol:    Rol

    model_config = {"from_attributes": True}


# ══════════════════════════════════════════
# AUTH / JWT
# ══════════════════════════════════════════

class LoginRequest(BaseModel):
    email:    EmailStr = Field(..., examples=["operario@incubant.co"])
    password: str      = Field(..., min_length=1, examples=["S3guroIncubant!"])


class TokenOut(BaseModel):
    """Respuesta del endpoint /auth/login."""
    access_token:  str
    refresh_token: str
    token_type:    str = "bearer"
    expires_in:    int = Field(..., description="Segundos hasta que expira el access_token")
    user:          UserOut


class TokenRefreshRequest(BaseModel):
    refresh_token: str


class TokenRefreshOut(BaseModel):
    access_token: str
    token_type:   str = "bearer"
    expires_in:   int


# ══════════════════════════════════════════
# LOG AUDITORÍA
# ══════════════════════════════════════════

class LogAuditoriaOut(BaseModel):
    """Solo lectura — el log nunca se crea directamente desde el cliente."""
    id:              str
    tabla_afectada:  str
    registro_id:     str
    campo:           Optional[str]
    accion:          str
    valor_anterior:  Optional[str]
    valor_nuevo:     Optional[str]
    motivo:          Optional[str]
    ip_origen:       Optional[str]
    timestamp:       datetime
    usuario:         Optional[UserSummary]

    model_config = {"from_attributes": True}