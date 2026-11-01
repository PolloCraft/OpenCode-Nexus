# Arquitectura de NEXUS Suite 7.3.1

NEXUS es una **capa de orquestación**: no reimplementa los motores, los localiza, los lanza
y gestiona su entorno. Todo el código propio vive en `Nexus/`.

## Vista general

```text
┌──────────────────────────────────────────────────────────────┐
│  nexus_app.py            GUI Tkinter (13 paginas, 2848 lineas)│
│  nexus_menu.py           Menu de consola integral             │
│  antigravity_menu.py     Menu de consola de Antigravity       │
└───────────────┬──────────────────────────────────────────────┘
                │  llama solo a  modules/  (ningun hilo toca subprocess directo)
┌───────────────┴──────────────────────────────────────────────┐
│  modules/common.py      rutas portables, procesos, PATH,      │
│                         hardware, dependencia_audit(), red     │
│  modules/ui.py          THEME (20 colores), estilos ttk,       │
│                         ICONOS BMP, card/pill/LogBox/FlowFrame │
├──────────────────────────────────────────────────────────────┤
│  modules/oplire_ops.py       │ modules/antigravity_ops.py     │
│  motor Rust: WARP, proxy,    │ plugin npm, cuentas, modelos,  │
│  dashboard, sesiones, vCache │ cuotas, API key Google         │
│                              │                                │
│  modules/claude_ops.py       │                                │
│  servidor FCC, agentes, .env │                                │
└──────────┬───────────────────┴──────────────┬─────────────────┘
           │                                  │
   oplire.exe (:8080)                  opencode / uv
   dashboard + proxy                   + FCC server (:8082)
```

## Los cinco módulos de `modules/`

### `common.py` — infraestructura compartida (1230 líneas)

Define las constantes de identidad de la aplicación y todas las utilidades transversales:

| Elemento | Línea | Función |
| --- | --- | --- |
| `APP_NAME` / `APP_VERSION` | `common.py:32-33` | `"NEXUS Suite"` / `"7.3.1"`; única fuente de la versión |
| `OPLIRE_ENGINE`, `ANTIGRAVITY_ENGINE`, `CLAUDE_ENGINE` | `:35-37` | Nombres canónicos de motor |
| `ENV_HELP` | `:41-99` | Documentación de las variables de entorno que gestiona la suite |
| `get_base_dir()` | `:108-112` | Devuelve la carpeta raíz; detecta ejecución congelada (`sys.frozen`) |
| `candidate_bases()` | `:115-130` | Posibles ubicaciones de `Nexus/` cuando el `.exe` está en otra unidad |
| `resolve_engine_dir(name)` | `:133+` | Localiza el motor respetando `OPLIRE_PROJECT_PATH`, `ANTIGRAVITY_PROJECT_PATH`, `CLAUDE_PROJECT_PATH` |
| `claude_dir()` | `:160-210` | Valida que la carpeta sea realmente `free-claude-code` comprobando su `pyproject.toml` |
| lectura/escritura de `PATH` y `HKCU\Environment` | `:364-521` | Escribe variables y emite `WM_SETTINGCHANGE` para que las vean los procesos nuevos |
| información de equipo | `:521-869` | CPU, GPU, RAM, adaptadores de red |
| `dependency_audit()` | `:869-920` | Inventario de dependencias instaladas/faltantes |
| kill seguro | `:967-1081` | Detiene procesos respetando `PROTECTED_PROCESSES` |
| cliente HTTP mínimo | — | Sin dependencias externas, para `localhost` |
| `enable_dpi_awareness()` | `:1121` | Escalado correcto en pantallas HiDPI |
| integración con Everything | `:1142-1221` | Descarga/detección y clave de registro `Software\Classes\*\shell\NexusEverything` |

### `ui.py` — capa visual (289 líneas)

`THEME` de 20 colores, detección automática de tipografía, `ICONS` construidos solo con
glifos BMP (evita los “tofu” de emoji en Tk), cinco estilos de botón y estilos `ttk` para
`Notebook`, `Treeview`, `Scrollbar` y `Progressbar`, más los helpers `card()`, `button()`,
`pill()`, `LogBox()` y `FlowFrame()`.

### `oplire_ops.py` — motor Rust (1291 líneas)

- **Búsqueda del binario** (`:34-96`): `NEXUS_OPLIRE_EXE` → `dist/` → `target/release` →
  `target/debug` → copia congelada, que se extrae a `%LOCALAPPDATA%\Nexus\bin\oplire.exe`.
- **Configuración y datos** (`:103-114`): config en `%APPDATA%\oplire`, datos en
  `%LOCALAPPDATA%\oplire`.
- **WARP** (`:181-221`), **dashboard/proxy/daemon** en `:8080` (`:230-302`) y ciclo de vida
  de `opencode serve` (`:327-414`).
- **~20 llamadas a la API del dashboard** (`:416-501`).
- **Reparación de OpenCode** (`:541-674`): reinstala el paquete npm y comprueba que
  `opencode-ai/bin/opencode.exe` sea un PE real (`MZ`) y no el aviso de un postinstall roto.
- **Sesiones** (`:1027-1257`): reparar, listar, respaldar, restaurar y borrar; los respaldos
  se crean en `%LOCALAPPDATA%\Nexus\backups\sessions\< marca-de-tiempo >`.
- **Caché** (`:818-1026`): escaneo y limpieza con protección de los archivos de Antigravity.
- **Bypass de OpenCode Desktop** (`:679-816`): estado en `%LOCALAPPDATA%\oplire\bypass_state.json`,
  siempre con respaldo previo y restauración.

### `antigravity_ops.py` — plugin npm (1039 líneas)

- `PLUGIN_NAME = "opencode-antigravity-auth"` (`:27`) y catálogo `MODELS` (`:29+`).
- Resolución de configuración (`:190-229`): `OPENCODE_CONFIG_DIR` → XDG → `~/.config/opencode`
  → `%APPDATA%\opencode`, con los archivos `opencode.jsonc|json`, `antigravity-accounts.json`
  y `antigravity.json`.
- Detección del binario `opencode` (`:232-288`) en `%APPDATA%\npm`, enlaces de WinGet y `~/.opencode/bin`.
- **Instalación del plugin** (`install_plugin_to_cache`, `:438-477`): `npm install
  opencode-antigravity-auth@latest --prefix ~/.cache/opencode/packages/<plugin>@latest`
  con `--no-audit --no-fund`, validación de la caché resultante y limpieza si falla.
- **Cuotas** (`:534-641`): lectura en vivo ejecutando `antigravity/scripts/check-quota.mjs`.
- Activación/desactivación del plugin y alta/baja de modelos (`:699-846`), siempre con
  `backup_file()` antes de escribir.
- API key de Google en el entorno de usuario (`:942-979`), reparación de compatibilidad Node
  y desactivación de la auto-actualización del plugin (`:365-1026`).

### `claude_ops.py` — Free Claude Code (953 líneas)

- `FCC_FALLBACK_VERSION = "6.16.16"`, servidor en `127.0.0.1:8082` (`:38-40`).
- **10 agentes** (`:43-54`) mapeados a consolas `fcc-*`: `claude`, `codex`, `opencode`,
  `cline`, `aider`, `hermes`, `dsh`, `grok`, `muse`, `pi`, cada uno con su `AGENT_HINTS`
  de instalación (`:69-80`).
- 20 proveedores y sus variables de clave (`MODEL_PROVIDER_KEYS`, `:84-112`).
- Archivos de trabajo: `~/.fcc/.env` (con copia `.bak-< marca >`) y `~/.fcc/logs/server.log`
  (`:136-162`); el venv se crea por máquina en `%LOCALAPPDATA%\Nexus\fcc\venv-<sha1[:8]>`.
- Ejecución mediante `uv run --project <carpeta> --no-dev <cmd>` (`:624-650`); arranque y
  parada del servidor con verificación de propiedad del proceso (`:572-611`).
- `_ensure_build_fallback()` (`:323-350`) escribe
  `[tool.hatch.version.raw-options] fallback_version` en el `pyproject.toml` del upstream
  cuando no hay metadatos de git: es una **modificación del AGPL upstream**, debe declararse
  (ver `docs/LICENCIAS.md`).

## GUI y modelo de ejecución

- **Barra lateral** con 13 páginas definidas en `PAGE_META` (`nexus_app.py:286-300`).
- **`ScrollFrame`** con rueda del ratón (`:50-75`) y **`btnrow`**, fila de botones que reflowea
  sola al cambiar el ancho (`:361-367`).
- **Responsivo**: `minsize(720, 560)`; por debajo de 980 px se oculta el subtítulo y por debajo
  de 1040 px las píldoras de estado (`:528-555`).
- **Cola de UI segura entre hilos** (`:383-397`): los procesos hijos nunca tocan widgets, publican en
  una cola que consume el hilo principal.
- **Tick global de 1 s** que solo refresca los *refreshers* de la página activa (`:476-485`)
  y **F5** para refrescar todo (`:100`).
- **Píldoras de estado** en cabecera: OPLIRE, WARP, OPENCODE, PLUGIN, CLAUDE (`:145-149`).
- **Insignia de administrador** con acción “Elevar a Admin” (`:151-157`).

## Dónde vive cada dato

| Dato | Ruta |
| --- | --- |
| Binario del motor extraído | `%LOCALAPPDATA%\Nexus\bin\oplire.exe` |
| Respaldos de sesiones | `%LOCALAPPDATA%\Nexus\backups\sessions\…` |
| Entorno virtual de FCC | `%LOCALAPPDATA%\Nexus\fcc\venv-<hash>` |
| Estado del bypass | `%LOCALAPPDATA%\oplire\bypass_state.json` |
| Configuración de Oplire | `%APPDATA%\oplire\config.json` |
| Configuración de OpenCode/Antigravity | `%APPDATA%\opencode\` o `~/.config/opencode/` |
| Caché del plugin | `~/.cache/opencode/packages/` |
| Entorno y logs de FCC | `~/.fcc/.env`, `~/.fcc/logs/server.log` |
| Variables y `PATH` | `HKCU\Environment` |

Ninguna de esas rutas se versiona ni se incluye en los paquetes de release.
