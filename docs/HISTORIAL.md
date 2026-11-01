# Historial de versiones (V1 → V7.3.1)

Este archivo reconstruye la evolución real del proyecto a partir de los nueve paquetes
históricos del autor. No hay commits de git para las primeras épocas: el repositorio público
empezó a versionarse en la era 7.2.0, así que las releases V1–V6 son **instantáneas
históricas** (archivo de código fuente), no reconstrucciones desde un commit.

## Línea de tiempo

```text
V1 ─ V2 ─ V3 ─ V4 ─ V5          Época OPLIRE .......... Rust nativo, sin GUI Python
        │
        v
      V6                        Época NEXUS temprano .. 3 servicios independientes
        │
        v
   V7.2 → V7.3 → V7.3.1         Época SUITE ........... consola única Tkinter
```

## Época Oplire (V1–V5) — motor Rust nativo

Un solo crate, `oplire-reset`, con instaladores para Windows (`.ps1`), Arch
(`aur/PKGBUILD`), winget (`winget/oplire.yaml`), workflow de CI y un menú de consola en
Python (`oplire_menu.py`). Todavía no existía la GUI de la suite.

| Release | Contenido del paquete | Delta verificado |
| --- | --- | --- |
| [`v1.0.0`](https://github.com/PolloCraft/OpenCode-Nexus/releases/tag/v1.0.0) | 29 archivos · motor `oplire-reset` **3.0.0** | Base: `bypass`, `config`, `dashboard`, `main`, `watch`, `proxy/`, `transform/`, `warp/` + scripts, aur, winget, CI |
| [`v2.0.0`](https://github.com/PolloCraft/OpenCode-Nexus/releases/tag/v2.0.0) | 30 archivos | **Añade `src/sessions.rs`**; ajustes en `bypass`, `lib`, `main`, `watch`, `proxy/handlers` y `warp/resolver` |
| [`v3.0.0`](https://github.com/PolloCraft/OpenCode-Nexus/releases/tag/v3.0.0) | 30 archivos | Refinamiento de `dashboard`, `main`, `sessions`, `proxy/handlers` y `proxy/server` |
| [`v4.0.0`](https://github.com/PolloCraft/OpenCode-Nexus/releases/tag/v4.0.0) | 31 archivos · README etiqueta el motor 3.1.0 | **Añade `src/network.rs`** (adaptadores, DHCP/estático, respaldo y restauración de red); 12 archivos tocados, incluido el menú Python |
| [`v5.0.0`](https://github.com/PolloCraft/OpenCode-Nexus/releases/tag/v5.0.0) | 31 archivos · motor **4.0.0** | `Cargo.toml`/`Cargo.lock` a 4.0.0, workflow de build, `config`, `dashboard`, `main`, `proxy/*`; **último Oplire “nativo”** |

## Época Nexus temprano (V6) — servicios independientes

[`v6.0.0`](https://github.com/PolloCraft/OpenCode-Nexus/releases/tag/v6.0.0) — 1223 archivos.
Primera vez que el nombre “Nexus” agrupa varias cosas, pero **sin consola común**: tres
carpetas que cada uno arrancaba por su cuenta.

| Servicio | Qué era |
| --- | --- |
| `Nexus-Claude` | Copia completa de *Free Claude Code* (Python/uv, con `src`, `tests`, `e2e`, `smoke`, `INICIAR-FCC.bat`) |
| `OpenCode-Oplire` | El motor Rust de la época V5 con su propio menú |
| `Opencode-Antigravity` | El plugin TypeScript *opencode-antigravity-auth* con gestores `.bat`/`.ps1` |

La experiencia de esta época —tres lanzadores, tres entornos, ningún diagnóstico unificado—
es lo que motivó la suite.

## Época Suite (V7.x) — consola única

| Release | Qué cambió |
| --- | --- |
| [`v7.2.0`](https://github.com/PolloCraft/OpenCode-Nexus/releases/tag/v7.2.0) | Nace la GUI unificada (`nexus_app.py`, 2003 líneas) sobre `modules/` compartidos (`common` 781, `oplire_ops` 743, `antigravity_ops` 879, `ui` 288). Motor Oplire **4.0.0** embebido en `Nexus.exe` (PyInstaller onefile, Python 3.13) y plugin de Antigravity instalado desde npm en tiempo de ejecución, no versionado. |
| [`v7.3.0`](https://github.com/PolloCraft/OpenCode-Nexus/releases/tag/v7.3.0) | Entra el **módulo Claude** como ciudadano de primera clase: nuevo `modules/claude_ops.py` (953 líneas), GUI hasta 2848 líneas y 13 páginas, `common.py` crece a 1230 y `oplire_ops.py` a 1291. Se añaden auditoría del equipo, gestión de `PATH`/variables y protección de procesos. |
| [`v7.3.1`](https://github.com/PolloCraft/OpenCode-Nexus/releases/tag/v7.3.1) | Estado del arte actual. |

### Nota honesta sobre v7.3.0 y v7.3.1

Los dos paquetes históricos comparados archivo por archivo son **idénticos salvo un asset**:
`v7.3.1` añade `Documentación/Banner.jpg` y no modifica ni una línea de código. Además, las
constantes internas iban por detrás de la etiqueta del paquete:

| Paquete | `APP_VERSION` en `common.py` | `VERSION` en `nexus_menu.py` |
| --- | --- | --- |
| V7-2 | `7.0.0` | `6.0.0 Nexus` |
| V7-3 | `7.3.1` | `7.3.0 Nexus` |
| V7-3-1 | `7.3.1` | `7.3.0 Nexus` |

En el árbol actual del repositorio esas etiquetas están **unificadas a 7.3.1** y la página
*Acerca de* ya no muestra dos versiones distintas a la vez: `APP_VERSION` en
`modules/common.py:33` es la única fuente de la versión.

## Qué se publica y qué no

En las releases de esta época se omiten deliberadamente:

- `node_modules/`, `.venv/`, `target/`, `dist/`, `__pycache__/` y el `.git/` de los upstream;
- `uv.exe` (binario de terceros; se instala de forma oficial);
- `Documentación/Documentacion 1.md`: es la **transcripción del chat de desarrollo**, no
  documentación de usuario, y no debe publicarse como guía;
- `Nexus/oplire/src/identity.rs` y `quota.rs` — no están declarados en `lib.rs` ni en
  `main.rs` (no se compilan), y sintetizan cabeceras de identidad del cliente oficial y
  enrutado entre cuotas de cuenta. Este repositorio no publica ni documenta esa maquinaria:
  los límites los aplica el servidor del proveedor.

Su exclusión no afecta al build. Cada paquete incluye un `MANIFEST.txt` que consigna
exactamente qué se quitó y por qué.
