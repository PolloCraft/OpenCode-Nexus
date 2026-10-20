# -*- coding: utf-8 -*-
"""
NEXUS Suite - modulos funcionales
---------------------------------
Separacion por modulos:

  * common           -> utilidades compartidas (rutas, sistema, red, procesos)
  * oplire_ops       -> modulo OPENCODE (motor Oplire: IP, proxy, dashboard, cache)
  * antigravity_ops  -> modulo ANTIGRAVITY (cuentas Google, plugin, modelos)
  * ui               -> tema y widgets reutilizables de la interfaz

Todo el codigo es autonomo: no requiere dependencias externas a Python stdlib.
"""

__all__ = ["common", "oplire_ops", "antigravity_ops", "ui"]
__version__ = "7.0.0"
