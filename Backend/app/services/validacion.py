# app/services/validacion.py
"""
Service de Validación de Producción.

Implementa las dos lógicas de validación definidas en el Master Prompt:

  ┌─────────────────────────────────────────────────────────────┐
  │  La Esperanza (TipoGranja.MADURA)                           │
  │  → Compara contra el promedio histórico de las últimas      │
  │    4 semanas del mismo lote.                                │
  │  → Alerta si la desviación supera ±5%.                      │
  ├─────────────────────────────────────────────────────────────┤
  │  La Fe (TipoGranja.CRECIMIENTO)                             │
  │  → Compara contra la curva genética teórica según la        │
  │    edad del lote en semanas.                                │
  │  → Alerta si producción real < 80% o > 120% de la teórica. │
  └─────────────────────────────────────────────────────────────┘

Resultado de validación (ValidacionResultado):
  - estado:  "ok" | "alerta" | "fuera_rango"
  - mensaje: explicación legible para el operario
  - detalle: dict con números para el frontend (semáforo de color)

Este service NO escribe en la BD — solo calcula y retorna.
El CRUD de remisión llama a este service antes de persistir
y guarda el resultado en detalle.validacion_estado / mensaje.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy.orm import Session

from app.crud.granja import CRUDLote, galpon as crud_galpon, lote as crud_lote
from app.models.granja import Lote, TipoGranja
from app.models.remision import RemisionDetalle
from app.schemas.remision import RemisionDetalleCreate


# ─────────────────────────────────────────
# Resultado de validación
# ─────────────────────────────────────────

@dataclass
class ValidacionResultado:
    """
    Resultado que se guarda en RemisionDetalle.validacion_estado/mensaje.
    El frontend usa 'estado' para el semáforo de color:
      ok          → verde  (#1B6B35)
      alerta      → amarillo (#7A5A00)
      fuera_rango → rojo   (#8B2500)
    """
    estado:  str                         # "ok" | "alerta" | "fuera_rango"
    mensaje: str
    detalle: dict = field(default_factory=dict)

    @property
    def es_ok(self) -> bool:
        return self.estado == "ok"

    @property
    def es_alerta(self) -> bool:
        return self.estado == "alerta"

    @property
    def es_fuera_rango(self) -> bool:
        return self.estado == "fuera_rango"


# ─────────────────────────────────────────
# Umbrales configurables
# ─────────────────────────────────────────

# La Esperanza — desviación máxima permitida vs histórico
UMBRAL_ALERTA_HISTORICO    = 0.05   # ±5%  → alerta amarilla
UMBRAL_FUERA_RANGO_HIST    = 0.15   # ±15% → fuera de rango rojo

# La Fe — desviación vs curva genética teórica
UMBRAL_ALERTA_CURVA_INF    = 0.80   # < 80% de la teórica → alerta
UMBRAL_ALERTA_CURVA_SUP    = 1.20   # > 120% de la teórica → alerta
UMBRAL_FUERA_RANGO_CURVA   = 0.60   # < 60% → fuera de rango crítico

# Semanas mínimas de historial para validar en La Esperanza
MIN_SEMANAS_HISTORIAL       = 2


# ══════════════════════════════════════════
# VALIDACIÓN LA ESPERANZA — Histórico ±5%
# ══════════════════════════════════════════

def _validar_historico(
    db: Session,
    lote: Lote,
    huevo_incubable: int,
) -> ValidacionResultado:
    """
    Compara la cantidad actual contra el promedio de las últimas 4 semanas.

    Fórmula:
        desviacion = (actual - promedio) / promedio

    Si no hay historial suficiente → retorna "ok" con aviso informativo.
    """
    historico = crud_lote.get_historico_produccion(
        db, lote_id=lote.id, ultimas_n_semanas=4
    )

    if len(historico) < MIN_SEMANAS_HISTORIAL:
        return ValidacionResultado(
            estado="ok",
            mensaje=(
                f"Sin historial suficiente (necesita {MIN_SEMANAS_HISTORIAL} semanas). "
                "Validación automática desactivada."
            ),
            detalle={"semanas_disponibles": len(historico)},
        )

    promedio = sum(h["promedio"] for h in historico) / len(historico)

    if promedio == 0:
        return ValidacionResultado(
            estado="ok",
            mensaje="Promedio histórico es 0 — primer ciclo de producción.",
        )

    desviacion = (huevo_incubable - promedio) / promedio
    pct = round(desviacion * 100, 1)

    detalle = {
        "promedio_historico": round(promedio, 1),
        "actual":             huevo_incubable,
        "desviacion_pct":     pct,
        "semanas_analizadas": len(historico),
    }

    if abs(desviacion) <= UMBRAL_ALERTA_HISTORICO:
        return ValidacionResultado(
            estado="ok",
            mensaje=f"Dentro del rango histórico ({pct:+.1f}% vs promedio {round(promedio):,} huevos).",
            detalle=detalle,
        )
    elif abs(desviacion) <= UMBRAL_FUERA_RANGO_HIST:
        direccion = "por encima" if desviacion > 0 else "por debajo"
        return ValidacionResultado(
            estado="alerta",
            mensaje=(
                f"Producción {pct:+.1f}% {direccion} del promedio histórico "
                f"({round(promedio):,} huevos). Verifique el conteo."
            ),
            detalle=detalle,
        )
    else:
        direccion = "excede" if desviacion > 0 else "está muy por debajo de"
        return ValidacionResultado(
            estado="fuera_rango",
            mensaje=(
                f"⚠ Producción {pct:+.1f}% — {direccion} significativamente el promedio "
                f"histórico ({round(promedio):,} huevos). Requiere revisión de Admin."
            ),
            detalle=detalle,
        )


# ══════════════════════════════════════════
# VALIDACIÓN LA FE — Curva Genética Teórica
# ══════════════════════════════════════════

def _validar_curva_genetica(
    db: Session,
    lote: Lote,
    huevo_incubable: int,
    fecha_remision,
) -> ValidacionResultado:
    """
    Compara la producción real contra el porcentaje de postura teórico
    según la semana de vida del lote.

    La curva genética se almacena en lote.curva_genetica_ref como JSON:
        [{"semana": 1, "porcentaje_postura": 5.0}, ...]

    Cálculo:
        produccion_teorica = (aves_actuales * porcentaje_postura) / 100
        ratio = actual / teorica
    """
    edad_semanas = crud_lote.get_edad_semanas(lote, referencia=fecha_remision)

    detalle_base = {
        "edad_semanas":  edad_semanas,
        "aves_actuales": lote.numero_aves_actual,
        "actual":        huevo_incubable,
    }

    # Sin curva genética configurada
    if not lote.curva_genetica_ref:
        return ValidacionResultado(
            estado="alerta",
            mensaje=(
                f"Lote '{lote.codigo}' no tiene curva genética configurada. "
                "Configure la curva en Admin para activar la validación."
            ),
            detalle=detalle_base,
        )

    # Parsear curva
    try:
        curva: list[dict] = json.loads(lote.curva_genetica_ref)
    except (json.JSONDecodeError, TypeError):
        return ValidacionResultado(
            estado="alerta",
            mensaje="Curva genética con formato inválido. Contacte al Admin.",
            detalle=detalle_base,
        )

    # Buscar la semana más cercana en la curva
    punto = _buscar_punto_curva(curva, edad_semanas)

    if punto is None:
        return ValidacionResultado(
            estado="ok",
            mensaje=f"Semana {edad_semanas} fuera del rango de la curva genética. Sin validación.",
            detalle={**detalle_base, "semana_buscada": edad_semanas},
        )

    porcentaje_teorico = punto["porcentaje_postura"]

    if lote.numero_aves_actual == 0:
        return ValidacionResultado(
            estado="alerta",
            mensaje="Número de aves actuales es 0 — actualice el conteo del lote.",
            detalle=detalle_base,
        )

    produccion_teorica = (lote.numero_aves_actual * porcentaje_teorico) / 100
    ratio = huevo_incubable / produccion_teorica if produccion_teorica > 0 else 0
    pct_vs_teorica = round((ratio - 1) * 100, 1)

    detalle = {
        **detalle_base,
        "semana_lote":         edad_semanas,
        "porcentaje_teorico":  porcentaje_teorico,
        "produccion_teorica":  round(produccion_teorica, 1),
        "ratio_vs_teorica":    round(ratio, 3),
        "desviacion_pct":      pct_vs_teorica,
    }

    if ratio < UMBRAL_FUERA_RANGO_CURVA:
        return ValidacionResultado(
            estado="fuera_rango",
            mensaje=(
                f"⚠ Producción {pct_vs_teorica:+.1f}% vs curva genética semana {edad_semanas} "
                f"(teórico: {round(produccion_teorica):,} huevos). "
                "Producción crítica — revise sanidad del lote."
            ),
            detalle=detalle,
        )
    elif UMBRAL_ALERTA_CURVA_INF <= ratio <= UMBRAL_ALERTA_CURVA_SUP:
        return ValidacionResultado(
            estado="ok",
            mensaje=(
                f"Dentro del rango esperado semana {edad_semanas} "
                f"({pct_vs_teorica:+.1f}% vs teórico {round(produccion_teorica):,} huevos)."
            ),
            detalle=detalle,
        )
    else:
        direccion = "por encima" if ratio > 1 else "por debajo"
        return ValidacionResultado(
            estado="alerta",
            mensaje=(
                f"Producción {pct_vs_teorica:+.1f}% {direccion} de la curva genética "
                f"semana {edad_semanas} (teórico: {round(produccion_teorica):,} huevos)."
            ),
            detalle=detalle,
        )


def _buscar_punto_curva(curva: list[dict], semana: int) -> Optional[dict]:
    """
    Busca el punto de la curva correspondiente a la semana del lote.
    Si no hay coincidencia exacta, usa interpolación lineal entre
    los dos puntos más cercanos.
    """
    # Coincidencia exacta
    for punto in curva:
        if punto.get("semana") == semana:
            return punto

    # Interpolación lineal
    ordenada = sorted(curva, key=lambda x: x["semana"])
    anterior = siguiente = None

    for punto in ordenada:
        if punto["semana"] < semana:
            anterior = punto
        elif punto["semana"] > semana and siguiente is None:
            siguiente = punto

    if anterior and siguiente:
        rango = siguiente["semana"] - anterior["semana"]
        fraccion = (semana - anterior["semana"]) / rango
        porcentaje_interpolado = (
            anterior["porcentaje_postura"]
            + fraccion * (siguiente["porcentaje_postura"] - anterior["porcentaje_postura"])
        )
        return {"semana": semana, "porcentaje_postura": round(porcentaje_interpolado, 2)}

    # Fuera del rango de la curva
    return None


# ══════════════════════════════════════════
# PUNTO DE ENTRADA PÚBLICO
# ══════════════════════════════════════════

def validar_detalle(
    db: Session,
    *,
    detalle_in: RemisionDetalleCreate,
    fecha_remision,
) -> ValidacionResultado:
    """
    Función principal que el CRUD llama para validar cada detalle.

    1. Obtiene el lote activo del galpón.
    2. Obtiene el tipo de granja (desde módulo → granja).
    3. Despacha a la validación correspondiente.
    4. Si no hay lote activo → retorna "ok" sin validar.
    """
    # Obtener lote activo del galpón
    lote_activo: Optional[Lote] = crud_galpon.get_lote_activo(db, detalle_in.galpon_id)

    if not lote_activo:
        return ValidacionResultado(
            estado="ok",
            mensaje="Sin lote activo en el galpón — validación omitida.",
        )

    # Obtener tipo de granja
    galpon_obj = crud_galpon.get(db, detalle_in.galpon_id)
    if not galpon_obj:
        return ValidacionResultado(estado="ok", mensaje="Galpón no encontrado.")

    from app.models.granja import Modulo as ModuloModel, Granja as GranjaModel
    modulo_obj = db.get(ModuloModel, galpon_obj.modulo_id)
    if not modulo_obj:
        return ValidacionResultado(estado="ok", mensaje="Módulo no encontrado.")

    granja_obj = db.get(GranjaModel, modulo_obj.granja_id)
    if not granja_obj:
        return ValidacionResultado(estado="ok", mensaje="Granja no encontrada.")

    # Despachar según tipo de granja
    if granja_obj.tipo == TipoGranja.MADURA:
        return _validar_historico(db, lote_activo, detalle_in.huevo_incubable)
    else:
        return _validar_curva_genetica(
            db, lote_activo, detalle_in.huevo_incubable, fecha_remision
        )