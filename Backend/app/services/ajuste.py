# app/services/ajuste.py
"""
Service de Ajuste Automático.

Cuando el Operario Planta registra el huevo_real recibido,
este service calcula las diferencias vs lo despachado,
clasifica el tipo de ajuste y genera los logs de auditoría.

Flujo:
  crud.remision.registrar_recepcion()
    → AjusteService.procesar_ajustes()
      → Calcula delta por campo
      → Clasifica: SOBRANTE | FALTANTE | CUADRADO
      → Llama AuditoriaService.log_ajuste() por cada campo con delta != 0
      → Retorna AjusteResumen para responder al cliente

Clasificación:
  delta > 0  → SOBRANTE  (planta recibió más de lo despachado)
  delta < 0  → FALTANTE  (planta recibió menos)
  delta == 0 → CUADRADO
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from fastapi import Request
from sqlalchemy.orm import Session

from app.models.remision import RemisionDetalle
from app.services.auditoria import AuditoriaService


# ─────────────────────────────────────────
# Tipos de ajuste
# ─────────────────────────────────────────

SOBRANTE  = "sobrante"
FALTANTE  = "faltante"
CUADRADO  = "cuadrado"


@dataclass
class AjusteCampo:
    campo:      str
    despachado: int
    recibido:   int
    delta:      int
    tipo:       str  # SOBRANTE | FALTANTE | CUADRADO

    @property
    def tiene_diferencia(self) -> bool:
        return self.delta != 0


@dataclass
class AjusteResumen:
    """
    Resumen del ajuste de un detalle completo.
    Se retorna al cliente en la respuesta de /recepcion.
    """
    detalle_id: str
    galpon_id:  str
    ajustes:    list[AjusteCampo] = field(default_factory=list)

    @property
    def tiene_diferencias(self) -> bool:
        return any(a.tiene_diferencia for a in self.ajustes)

    @property
    def total_delta(self) -> int:
        return sum(a.delta for a in self.ajustes)

    @property
    def estado_semaforo(self) -> str:
        """
        Verde  → sin diferencias
        Rojo   → faltante (planta recibió menos)
        Amarillo → sobrante (planta recibió más)
        """
        if not self.tiene_diferencias:
            return "verde"
        if any(a.tipo == FALTANTE for a in self.ajustes):
            return "rojo"
        return "amarillo"

    def to_dict(self) -> dict:
        return {
            "detalle_id":       self.detalle_id,
            "galpon_id":        self.galpon_id,
            "tiene_diferencias": self.tiene_diferencias,
            "total_delta":      self.total_delta,
            "estado_semaforo":  self.estado_semaforo,
            "ajustes": [
                {
                    "campo":      a.campo,
                    "despachado": a.despachado,
                    "recibido":   a.recibido,
                    "delta":      a.delta,
                    "tipo":       a.tipo,
                }
                for a in self.ajustes
            ],
        }


# ══════════════════════════════════════════
# SERVICE
# ══════════════════════════════════════════

class AjusteService:

    # Campos que se comparan entre despachado y recibido
    CAMPOS_AJUSTE = [
        ("huevo_incubable", "huevo_real_incubable", "ajuste_incubable"),
        ("total_sucio",     "huevo_real_sucio",     "ajuste_sucio"),
        ("total_roto",      "huevo_real_roto",      "ajuste_roto"),
        ("huevo_extra",     "huevo_real_extra",     "ajuste_extra"),
    ]

    @classmethod
    def procesar_ajustes(
        cls,
        db: Session,
        *,
        detalle: RemisionDetalle,
        usuario_id: Optional[str] = None,
        request: Optional[Request] = None,
    ) -> AjusteResumen:
        """
        Calcula y persiste los ajustes de un detalle ya guardado en BD.
        Debe llamarse DESPUÉS de que crud guarda los valores huevo_real_*.
        Registra log de auditoría por cada campo con diferencia.
        """
        resumen = AjusteResumen(
            detalle_id=detalle.id,
            galpon_id=detalle.galpon_id,
        )

        for campo_desp, campo_real, campo_ajuste in cls.CAMPOS_AJUSTE:
            despachado = getattr(detalle, campo_desp, 0) or 0
            recibido   = getattr(detalle, campo_real, None)

            # Si el operario planta no registró este campo, saltar
            if recibido is None:
                continue

            delta = recibido - despachado
            tipo  = CUADRADO if delta == 0 else (SOBRANTE if delta > 0 else FALTANTE)

            ajuste_campo = AjusteCampo(
                campo=campo_desp,
                despachado=despachado,
                recibido=recibido,
                delta=delta,
                tipo=tipo,
            )
            resumen.ajustes.append(ajuste_campo)

            # Persistir ajuste en el detalle
            setattr(detalle, campo_ajuste, delta)

            # Log de auditoría solo si hay diferencia
            if delta != 0:
                AuditoriaService.log_ajuste(
                    db,
                    detalle_id=detalle.id,
                    campo=campo_desp,
                    despachado=despachado,
                    recibido=recibido,
                    ajuste=delta,
                    usuario_id=usuario_id,
                    request=request,
                )

        db.add(detalle)
        # El commit lo hace el caller (crud.remision.registrar_recepcion)
        return resumen

    @classmethod
    def get_resumen_ajustes_remision(
        cls,
        db: Session,
        remision_id: str,
    ) -> list[AjusteResumen]:
        """
        Retorna el resumen de ajustes de todos los detalles
        de una remisión. Útil para el panel de Admin Planta.
        """
        from sqlalchemy import select
        stmt = select(RemisionDetalle).where(
            RemisionDetalle.remision_id == remision_id,
            RemisionDetalle.huevo_real_incubable.isnot(None),
        )
        detalles = list(db.execute(stmt).scalars().all())

        resumenes = []
        for det in detalles:
            resumen = AjusteResumen(detalle_id=det.id, galpon_id=det.galpon_id)
            for campo_desp, campo_real, campo_ajuste in cls.CAMPOS_AJUSTE:
                despachado = getattr(det, campo_desp, 0) or 0
                recibido   = getattr(det, campo_real, None)
                if recibido is None:
                    continue
                delta = recibido - despachado
                tipo  = CUADRADO if delta == 0 else (SOBRANTE if delta > 0 else FALTANTE)
                resumen.ajustes.append(AjusteCampo(
                    campo=campo_desp,
                    despachado=despachado,
                    recibido=recibido,
                    delta=delta,
                    tipo=tipo,
                ))
            resumenes.append(resumen)

        return resumenes