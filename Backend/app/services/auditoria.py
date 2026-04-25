# app/services/auditoria.py
"""
Service de Auditoría Inmutable — Shadow Logging.

Reglas del Master Prompt:
  - No se permiten DELETE físicos.
  - Cualquier cambio post-creación registra:
      tabla, registro_id, campo, valor_anterior,
      valor_nuevo, usuario_id, timestamp, ip_origen.
  - La tabla log_auditoria NUNCA se modifica ni elimina.

Uso en routers (via dependencia FastAPI):
    from app.services.auditoria import AuditoriaService

    @router.put("/{id}")
    def update(id, payload, db=Depends(get_db), req=Request,
               user=Depends(get_current_user)):
        rem_antes = crud.remision.get_remision(db, id)
        resultado = crud.remision.update_remision(db, ...)
        AuditoriaService.log_update(
            db, req=req, usuario_id=user.id,
            tabla="remisiones", registro_id=id,
            antes=rem_antes, despues=resultado,
            campos_a_auditar=["estado", "observaciones"],
        )
        return resultado

El service también se puede usar como dependencia de FastAPI
para inyectar automáticamente request e usuario_id.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional, Sequence

from fastapi import Request
from sqlalchemy.orm import Session

from app.models.user import LogAuditoria


# ─────────────────────────────────────────
# Serializador seguro de valores
# ─────────────────────────────────────────

def _serializar(valor: Any) -> Optional[str]:
    """
    Convierte cualquier valor a JSON string para almacenar en el log.
    Maneja fechas, datetimes, enums, modelos SQLAlchemy y primitivos.
    """
    if valor is None:
        return None
    try:
        return json.dumps(valor, default=_json_default, ensure_ascii=False)
    except Exception:
        return str(valor)


def _json_default(obj: Any) -> Any:
    """Serializador para tipos que json.dumps no maneja nativamente."""
    if hasattr(obj, "isoformat"):           # date / datetime
        return obj.isoformat()
    if hasattr(obj, "value"):               # Enum (str/int)
        return obj.value
    if hasattr(obj, "__dict__"):            # Modelo SQLAlchemy básico
        return {
            k: v for k, v in obj.__dict__.items()
            if not k.startswith("_")
        }
    return str(obj)


# ─────────────────────────────────────────
# Extractor de IP del cliente
# ─────────────────────────────────────────

def _get_ip(request: Optional[Request]) -> Optional[str]:
    if not request:
        return None
    # Soporta X-Forwarded-For (nginx reverse proxy en Hostinger)
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


def _get_user_agent(request: Optional[Request]) -> Optional[str]:
    if not request:
        return None
    return request.headers.get("User-Agent", "")[:255]


# ══════════════════════════════════════════
# CLASE PRINCIPAL
# ══════════════════════════════════════════

class AuditoriaService:
    """
    API estática para registrar logs de auditoría.
    Todos los métodos son @classmethod — no requiere instanciación.
    """

    # ─────────────────────────────────────
    # Método base: un log por campo
    # ─────────────────────────────────────

    @classmethod
    def _insertar_log(
        cls,
        db: Session,
        *,
        tabla:           str,
        registro_id:     str,
        campo:           Optional[str],
        accion:          str,
        valor_anterior:  Any = None,
        valor_nuevo:     Any = None,
        usuario_id:      Optional[str] = None,
        motivo:          Optional[str] = None,
        request:         Optional[Request] = None,
    ) -> LogAuditoria:
        log = LogAuditoria(
            id=str(uuid.uuid4()),
            tabla_afectada=tabla,
            registro_id=registro_id,
            campo=campo,
            accion=accion,
            valor_anterior=_serializar(valor_anterior),
            valor_nuevo=_serializar(valor_nuevo),
            usuario_id=usuario_id,
            motivo=motivo,
            ip_origen=_get_ip(request),
            user_agent=_get_user_agent(request),
            timestamp=datetime.now(timezone.utc),
        )
        db.add(log)
        # No hacemos commit aquí — el caller lo controla
        return log

    # ─────────────────────────────────────
    # CREATE: un solo log con el objeto completo
    # ─────────────────────────────────────

    @classmethod
    def log_create(
        cls,
        db: Session,
        *,
        tabla:       str,
        registro_id: str,
        objeto:      Any,
        usuario_id:  Optional[str] = None,
        request:     Optional[Request] = None,
    ) -> None:
        """
        Registra la creación de un registro.
        Guarda el objeto completo en valor_nuevo.
        """
        cls._insertar_log(
            db,
            tabla=tabla,
            registro_id=registro_id,
            campo=None,
            accion="CREATE",
            valor_anterior=None,
            valor_nuevo=objeto,
            usuario_id=usuario_id,
            request=request,
        )

    # ─────────────────────────────────────
    # UPDATE: un log por campo que cambió
    # ─────────────────────────────────────

    @classmethod
    def log_update(
        cls,
        db: Session,
        *,
        tabla:               str,
        registro_id:         str,
        antes:               Any,
        despues:             Any,
        campos_a_auditar:    Sequence[str],
        usuario_id:          Optional[str] = None,
        motivo:              Optional[str] = None,
        request:             Optional[Request] = None,
    ) -> int:
        """
        Compara 'antes' y 'despues' campo a campo.
        Solo registra los campos que efectivamente cambiaron.
        Retorna el número de logs insertados.
        """
        insertados = 0
        for campo in campos_a_auditar:
            val_antes   = getattr(antes,   campo, None)
            val_despues = getattr(despues, campo, None)

            # Comparación con manejo de None
            if val_antes != val_despues:
                cls._insertar_log(
                    db,
                    tabla=tabla,
                    registro_id=registro_id,
                    campo=campo,
                    accion="UPDATE",
                    valor_anterior=val_antes,
                    valor_nuevo=val_despues,
                    usuario_id=usuario_id,
                    motivo=motivo,
                    request=request,
                )
                insertados += 1

        return insertados

    # ─────────────────────────────────────
    # SOFT DELETE
    # ─────────────────────────────────────

    @classmethod
    def log_soft_delete(
        cls,
        db: Session,
        *,
        tabla:       str,
        registro_id: str,
        motivo:      Optional[str] = None,
        usuario_id:  Optional[str] = None,
        request:     Optional[Request] = None,
    ) -> None:
        cls._insertar_log(
            db,
            tabla=tabla,
            registro_id=registro_id,
            campo="is_active",
            accion="SOFT_DELETE",
            valor_anterior=True,
            valor_nuevo=False,
            usuario_id=usuario_id,
            motivo=motivo,
            request=request,
        )

    # ─────────────────────────────────────
    # SYNC: registro de cada Upsert offline
    # ─────────────────────────────────────

    @classmethod
    def log_sync(
        cls,
        db: Session,
        *,
        registro_id:  str,
        tabla:        str,
        accion_sync:  str,         # "created" | "updated" | "conflict"
        device_id:    Optional[str] = None,
        usuario_id:   Optional[str] = None,
        request:      Optional[Request] = None,
    ) -> None:
        cls._insertar_log(
            db,
            tabla=tabla,
            registro_id=registro_id,
            campo=None,
            accion="SYNC",
            valor_nuevo={"accion_sync": accion_sync, "device_id": device_id},
            usuario_id=usuario_id,
            request=request,
        )

    # ─────────────────────────────────────
    # AJUSTE: diferencia huevo granja vs planta
    # ─────────────────────────────────────

    @classmethod
    def log_ajuste(
        cls,
        db: Session,
        *,
        detalle_id:  str,
        campo:       str,
        despachado:  int,
        recibido:    int,
        ajuste:      int,
        usuario_id:  Optional[str] = None,
        request:     Optional[Request] = None,
    ) -> None:
        """
        Registra la diferencia entre huevo despachado y huevo real recibido.
        Se llama desde crud.remision.registrar_recepcion() por cada campo
        que tenga ajuste != 0.
        """
        cls._insertar_log(
            db,
            tabla="remision_detalles",
            registro_id=detalle_id,
            campo=campo,
            accion="AJUSTE",
            valor_anterior={"despachado": despachado},
            valor_nuevo={"recibido": recibido, "ajuste": ajuste},
            usuario_id=usuario_id,
            request=request,
        )

    # ─────────────────────────────────────
    # CONSULTA: historial de un registro
    # ─────────────────────────────────────

    @classmethod
    def get_historial(
        cls,
        db: Session,
        *,
        tabla:       str,
        registro_id: str,
        limit:       int = 50,
    ) -> list[LogAuditoria]:
        """Retorna el historial de cambios de un registro específico."""
        from sqlalchemy import select
        stmt = (
            select(LogAuditoria)
            .where(
                LogAuditoria.tabla_afectada == tabla,
                LogAuditoria.registro_id    == registro_id,
            )
            .order_by(LogAuditoria.timestamp.desc())
            .limit(limit)
        )
        return list(db.execute(stmt).scalars().all())

    @classmethod
    def get_historial_usuario(
        cls,
        db: Session,
        *,
        usuario_id: str,
        limit:      int = 100,
    ) -> list[LogAuditoria]:
        """Retorna todos los logs de un usuario específico."""
        from sqlalchemy import select
        stmt = (
            select(LogAuditoria)
            .where(LogAuditoria.usuario_id == usuario_id)
            .order_by(LogAuditoria.timestamp.desc())
            .limit(limit)
        )
        return list(db.execute(stmt).scalars().all())