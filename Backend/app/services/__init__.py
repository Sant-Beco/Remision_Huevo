# app/services/__init__.py
"""
Capa de servicios — lógica de negocio de Incubant.

Importar desde aquí en routers y CRUD:
    from app.services import AuditoriaService, AjusteService
    from app.services import validar_detalle
"""

from .auditoria  import AuditoriaService
from .ajuste     import AjusteService, AjusteResumen, AjusteCampo
from .validacion import validar_detalle, ValidacionResultado

__all__ = [
    "AuditoriaService",
    "AjusteService",
    "AjusteResumen",
    "AjusteCampo",
    "validar_detalle",
    "ValidacionResultado",
]