# Instalación y puesta a punto

Guía completa para dejar **NEXUS Suite 7.3.1** funcionando en Windows 10/11 x64.
La suite es *portable*: no escribe en `Program Files` ni necesita instalación de sistema,
pero **sí** necesita que los motores estén presentes.

## 0. Qué necesitas tener antes de empezar

| Herramienta | Cómo instalarla | Verificación |
| --- | --- | --- |
| Python 3.10+ (con Tkinter) | <https://www.python.org/downloads/> — marca **Add Python to PATH** | `python --version` |
| Node.js LTS + npm | <https://nodejs.org/> | `node -v` y `npm -v` |
| OpenCode | `npm install -g opencode-ai` | `opencode --version` |
| Rust 1.75+ (solo para compilar Oplire) | <https://rustup.rs/> | `cargo --version` |
| [uv](https://docs.astral.sh/uv/) (para el módulo Claude) | `powershell -c "irm https://astral.sh/uv/install.ps1 | iex"` | `uv --version` |
| Cloudflare WARP (para las funciones de red) | Enlace en **Mantenimiento → Instalar/Reparar** | `warp-cli --version` |

> **Nota**: en 7.3.x la suite puede traer un `uv.exe` dentro de `Nexus/tools/`. Ese binario
> está excluido del repositorio y de los paquetes (es un ejecutable de terceros). Instala uv
> de la forma oficial de la tabla.

## 1. Obtener la suite

### Opción A — binario de una release (recomendado)

1. Descarga el `*.zip` de la [release](https://github.com/PolloCraft/OpenCode-Nexus/releases)
   que quieras (la actual es `v7.3.1`).
2. Descomprímelo en una carpeta propia, por ejemplo `D:\Nexus`.
3. Comprueba el hash contra el `*-SHA256SUMS.txt` de la misma release:

```powershell
Get-FileHash .\Nexus-Suite-7.3.1-win64.zip -Algorithm SHA256
```

4. Ejecuta **`Iniciar Nexus.bat`**. El lanzador intenta, en este orden:
   `Nexus.exe` → `pythonw nexus_app.py` → `python nexus_app.py`.

### Opción B — desde el repositorio

```bat
git clone https://github.com/PolloCraft/OpenCode-Nexus.git
cd OpenCode-Nexus
python Nexus\nexus_app.py
```

Con esta opción verás las pestañas pero el motor Oplire responderá “binario no encontrado”
hasta que lo compiles (paso 2) o lo descargues de una release.

## 2. Motor Oplire (Rust)

```powershell
powershell -ExecutionPolicy Bypass -File .\Nexus\oplire\build.ps1 -Release
```

El resultado queda en `Nexus\oplire\target\release\oplire.exe`. La GUI lo busca en:

1. la variable `NEXUS_OPLIRE_EXE`;
2. `Nexus\oplire\target\release`;
3. `%LOCALAPPDATA%\Nexus\bin`;
4. junto al ejecutable de la suite.

Si usas el `Nexus.exe` de una release, el motor 4.0.0 va embebido y se extrae solo a
`%LOCALAPPDATA%\Nexus\bin\oplire.exe` en el primer uso.

## 3. Motor Antigravity (npm)

La vía corta es **AG Plugin → Instalar plugin**: la suite ejecuta

```bat
npm install opencode-antigravity-auth@latest --prefix "%USERPROFILE%\.cache\opencode\packages\opencode-antigravity-auth@latest" --no-audit --no-fund
```

y valida que la caché haya quedado completa (si falla, la limpia). El **parche de
compatibilidad** que aplica `antigravity_ops.py` reescribe *import specifiers* en `dist/*.js`
y desactiva la auto-actualización del plugin, porque si no, `opencode` actualiza el paquete y
rompe las rutas del proyecto. Puedes revertirlo reinstalando el plugin desde npm.

## 4. Motor Claude (Free Claude Code, AGPL)

FCC **no se versiona aquí**: se obtiene de su upstream.

```powershell
# 1) Descargar el zip del upstream y descomprimir, o bien:
git clone https://github.com/Alishahryar1/free-claude-code.git  D:\Nexus-engines\claude

# 2) Decirle a NEXUS dónde está
setx CLAUDE_PROJECT_PATH "D:\Nexus-engines\claude"
```

Requisito importante: el `pyproject.toml` del upstream fija `requires-python == 3.14.7`, así
que **uv** deberá conseguir esa interpretación exacta; la suite lo hace por ti cuando usas
**Claude → Instalar/sincronizar uv**.

Si al construir el paquete no hay metadatos de git, la suite escribe un
`fallback_version` en el `[tool.hatch.version.raw-options]` de ese `pyproject.toml`
(behavior de `claude_ops._ensure_build_fallback`). Es una modificación declarada en
[`LICENCIAS.md`](LICENCIAS.md).

## 5. WARP y permisos

- Instala **Cloudflare One Client** (enlace en *Mantenimiento → Descargas*).
- Ejecuta la suite **como administrador** cuando uses la página *IP / WARP* o edites
  `HKCU\Environment`; la cabecera muestra una insignia `ADMIN` y ofrece “Elevar a Admin”.

## 6. Verificación final

Abre **Mantenimiento → Diagnóstico** y pulsa **Comprobar todo**. La suite te dirá, punto por
punto, qué binarios encontró y cuáles faltan, igual que la pestaña *Sistema*.

## 7. Compilar `Nexus.exe` (opcional)

El repositorio no incluye un `.spec`; el empaquetado histórico de la suite usa PyInstaller
*onefile* con la GUI y el paquete `modules`, y embebe `oplire.exe` para extraerlo en
`%LOCALAPPDATA%\Nexus\bin`. Receta equivalente:

```powershell
pip install pyinstaller
pyinstaller --onefile --windowed --name Nexus `
  --add-data "Nexus\modules;modules" `
  --add-binary "Nexus\oplire\target\release\oplire.exe;." `
  Nexus\nexus_app.py
```

Ajusta `--add-data`/`--add-binary` si reorganizas las rutas. Recuerda que `Nexus.exe` está en
`.gitignore`: el binario publicado vive en Releases, no en el árbol del repo.

## 8. Solución de problemas

| Síntoma | Causa habitual | Solución |
| --- | --- | --- |
| “No se encontró Nexus.exe ni Python” | Python no instalado o fuera de `PATH` | Reinstala marcando **Add Python to PATH** |
| Página Oplire con “motor no encontrado” | Falta compilar o definir `NEXUS_OPLIRE_EXE` | Paso 2, o baja el binario de la release |
| Antigravity “plugin en caché incompleta” | Instalación npm interrumpida | **AG Plugin → Reparar**, o borra la caché y repite el paso 3 |
| Antigravity sin modelos | Plugin desactivado o `opencode.json` sin sección `plugin` | **AG Plugin → Activar plugin** y **Comprobar config** |
| `opencode` no arranca | El `bin/opencode.exe` es el aviso de un *postinstall* roto, no un PE | **Mantenimiento → Reparar OpenCode** (instala/repair de npm) |
| Claude “carpeta de motor no encontrada” | No existe `Nexus/claude` ni `CLAUDE_PROJECT_PATH` | Paso 4 |
| Claude falla al compilar por versión | Sin metadatos de git para `hatch-vcs` | **Claude → Reparar entorno**; la suite añade `fallback_version` |
| Cambios de `PATH` no surten efecto | Proceso ya abierto | Reabre la consola; la suite emite `WM_SETTINGCHANGE` |
| Interfaz cortada en ventana pequeña | Umbral responsivo | Ensancha >1040 px para ver las píldoras; el reflow es automático |
| Interfaz diminuta o borrosa en pantallas HiDPI | Escalado cambiado después de abrir la suite | La aplicación activa la conciencia de DPI al arrancar (`common.enable_dpi_awareness`); reinicia la ventana tras ajustar el escalado de Windows |

---

Siguiente paso: la guía de uso página por página está en [`USO.md`](USO.md).
