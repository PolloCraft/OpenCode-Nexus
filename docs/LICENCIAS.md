# Licencias y atribución

NEXUS Suite es un **envoltorio de integración**. El código propio y los tres motores tienen
licencias distintas, y ninguna se mezcla: cada componente conserva la suya.

## Mapa de licencias

| Componente | Ruta en el repo / origen | Licencia | Titular del copyright |
| --- | --- | --- | --- |
| **NEXUS Suite (código propio)** | `Nexus/nexus_app.py`, `Nexus/nexus_menu.py`, `Nexus/antigravity_menu.py`, `Nexus/modules/*`, `Iniciar Nexus.bat`, `docs/*` | **MIT** | © 2026 PolloCraft |
| **Oplire (motor Rust)** | `Nexus/oplire/` — fork de [BerkeOruc/oplire](https://github.com/BerkeOruc/oplire) | **MIT** | © 2025 Berke Oruc |
| **opencode-antigravity-auth** | upstream npm / [NoeFabris/opencode-antigravity-auth](https://github.com/NoeFabris/opencode-antigravity-auth); `Nexus/antigravity/` **no se versiona** | **MIT** | © 2025 “Jens” (literal del `LICENSE` del upstream) |
| **Free Claude Code (FCC)** | upstream [Alishahryar1/free-claude-code](https://github.com/Alishahryar1/free-claude-code); `Nexus/claude/` **no se versiona** | **AGPL-3.0-only** | © 2026 Ali Khokhar |
| **uv** | `Nexus/tools/uv.exe` en los paquetes históricos; **excluido** del repo y de las releases | Apache-2.0 / MIT (dual) | Astral |
| **Cloudflare WARP** | software externo, no incluido | propietaria | Cloudflare |

> El `LICENSE` del plugin de Antigravity declara `Copyright (c) 2025 Jens` mientras que el
> repositorio corresponde a la cuenta `NoeFabris`. Se reproduce el texto tal cual, sin
> reinterpretarlo: si vas a redistribuir ese componente, verifica el titular con su autor.

## Obligaciones que este repo cumple

### MIT (código propio y Oplire)

- Se conservan los avisos de copyright y el texto de la licencia: `LICENSE` en la raíz y
  `Nexus/oplire/LICENSE`.
- Cualquier copia sustancial del software debe incluir ese aviso.

### AGPL-3.0-only (Free Claude Code)

Es la licencia más restrictiva del proyecto, y conviene entenderla:

- FCC **no se versiona en este repositorio** para evitar crear una segunda distribución de un
  trabajo AGPL con autoría confusa. Se obtiene del upstream oficial
  (`git clone` o el instalador de la propia suite).
- La suite **modifica** el `pyproject.toml` de FCC cuando no hay metadatos de git, añadiendo
  `fallback_version` en `[tool.hatch.version.raw-options]`
  (`Nexus/modules/claude_ops.py:323-350`). Es una modificación del material AGPL y por eso se
  declara aquí explícitamente.
- La comunicación entre la GUI y FCC es por **proceso separado** (`uv run … fcc-*` en consola
  nueva, servidor en `127.0.0.1:8082`): la suite no enlaza ni incorpora código AGPL dentro del
  suyo. Aun así, si redistribuyes una copia de trabajo de `Nexus/claude/`, debes hacerlo bajo
  AGPL-3.0 con su `LICENSE` y sus avisos.
- Si modificas FCC y lo ofreces como servicio de red, el AGPL obliga a poner el código fuente
  disponible a los usuarios de ese servicio.

## La suite no reescribe a los upstream

Lo que NEXUS hace con cada motor es localizarlo, lanzarlo y mantener su entorno:

| Motor | Cómo lo invoca |
| --- | --- |
| Oplire | `oplire.exe` (subproceso) y su dashboard HTTP en `:8080` |
| Antigravity | `npm install opencode-antigravity-auth@latest` en la caché de OpenCode; parche de *import specifiers* en `dist/*.js` y desactivación de auto-update, siempre con respaldo previo |
| Claude | `uv run --project <carpeta> --no-dev fcc-<agente>`; servidor en `127.0.0.1:8082` |

## Aviso de no afiliación

Ningún componente es oficial. No hay relación ni endoso de **Anthropic** (FCC lo declara
expresamente), **Google** (el upstream de Antigravity avisa de que su uso puede incumplir sus
Términos de Servicio), **OpenCode** ni **Cloudflare**.

## Uso aceptable

Este proyecto documenta e integra herramientas de administración local. **No** se publica ni
se documenta como medio para eludir límites de uso, cuotas de cuenta o controles de las
aplicaciones oficiales: esas restricciones las evalúa el servidor del proveedor, y sortearlas
incumple sus términos. Las propuestas de contribución orientadas a ese fin se cierran sin
revisión (ver [`CONTRIBUCION.md`](CONTRIBUCION.md)).

## Reportar un problema de licencias

Abre un [Issue](https://github.com/PolloCraft/OpenCode-Nexus/issues) indicando la ruta
afectada y el texto de licencia que falta o está mal atribuido. Los cambios de atribución de
terceros se corrigen el mismo día.
