# app/crud/__init__.py
"""
Punto de importación único para todas las operaciones CRUD.

Uso en routers y services:
    from app import crud

    crud.granja.get(db, id)
    crud.remision.create_remision(db, obj_in=payload)
    crud.lote.get_edad_semanas(lote)
"""

from .granja import granja, modulo, galpon, lote
from . import remision   # funciones sueltas (no clase instanciada)

__all__ = [
    "granja",
    "modulo",
    "galpon",
    "lote",
    "remision",
]