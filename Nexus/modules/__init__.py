# -*- coding: utf-8 -*-
"""
NEXUS Suite - modulos funcionales
---------------------------------
Separacion por modulos:

  * common           -> utilidades compartidas (rutas, sistema, red, procesos)
  * oplire_ops       -> modulo OPENCODE (motor Oplire: IP, proxy, dashboard, cache)
  * antigravity_ops  -> modulo ANTIGRAVITY (cuentas Google, plugin, modelos)
  * claude_ops       -> modulo CLAUDE (Free Claude Code: servidor, agentes, .env)
  * ui               -> tema y widgets reutilizables de la interfaz

Todo el codigo es autonomo: no requiere dependencias externas a Python stdlib.
"""

__all__ = ["common", "oplire_ops", "antigravity_ops", "claude_ops", "ui"]
__version__ = "7.3.1"
