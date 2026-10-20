# OpenCode Nexus

Suite de escritorio (Tkinter) que unifica en una sola interfaz dos herramientas:

| Módulo | Motor | Funciones principales |
| --- | --- | --- |
| **OpenCode** | [Oplire](Nexus/oplire) (Rust) | Rotación/restauración de IP con Cloudflare WARP, proxy y dashboard local, bypass de OpenCode Desktop, caché vCache en tiempo real, sesiones y diagnóstico |
| **Antigravity** | [opencode-antigravity-auth](https://www.npmjs.com/package/opencode-antigravity-auth) (npm) | Gestión de cuentas Google/Antigravity, cuotas, activación del plugin, modelos y mantenimiento |

Versión actual de la suite: **7.2.0**.

## Requisitos

- Windows 10/11.
- Python 3.10+ con Tkinter (incluido en el instalador oficial de Python).
- Para el módulo OpenCode:
  - Rust 1.75+ si vas a compilar Oplire, o un `oplire.exe` ya compilado.
  - Cloudflare WARP instalado para la rotación de IP.
  - Permisos de administrador para las operaciones de red.
- Para el módulo Antigravity:
  - Node.js/npm y `opencode` instalados.
  - El módulo instala el plugin `opencode-antigravity-auth@latest` desde npm.

## Inicio rápido

```bat
git clone https://github.com/PolloCraft/OpenCode-Nexus.git
cd OpenCode-Nexus
python Nexus\nexus_app.py
```

También puedes hacer doble clic en `Iniciar Nexus.bat`. El lanzador usa `Nexus.exe` si existe; si no, arranca la GUI con Python.

## Compilar Oplire

```powershell
# Oplire (Rust) -> Nexus\oplire\target\release\oplire.exe
powershell -ExecutionPolicy Bypass -File .\Nexus\oplire\build.ps1 -Release
```

La GUI busca `oplire.exe` en `Nexus\oplire\target\release`, en `%LOCALAPPDATA%\Nexus\bin` o junto al ejecutable. También puedes definir la variable de entorno `NEXUS_OPLIRE_EXE` con la ruta al binario.

## Plugin Antigravity

El código del plugin no se incluye en este repositorio. El módulo Antigravity lo instala y actualiza desde npm:

```bat
npm install opencode-antigravity-auth@latest --prefix "%USERPROFILE%\.cache\opencode\packages\opencode-antigravity-auth@latest"
```

El código fuente del plugin está en [NoeFabris/opencode-antigravity-auth](https://github.com/NoeFabris/opencode-antigravity-auth).

## Estructura

```text
OpenCode-Nexus/
├─ Iniciar Nexus.bat          Lanzador para Windows
├─ Nexus/
│  ├─ nexus_app.py            GUI principal de la suite
│  ├─ nexus_menu.py           Menú de consola
│  ├─ antigravity_menu.py     Menú de consola del módulo Antigravity
│  ├─ modules/                Lógica compartida (UI, Oplire, Antigravity)
│  └─ oplire/                 Motor Rust: proxy, WARP, dashboard, sesiones
├─ README.md
└─ .gitignore
```

## Qué no se versiona

Para mantener el repositorio liviano no se incluyen artefactos de compilación:

- `Nexus.exe` y binarios `.exe`, `.dll`, `.pdb`.
- `Nexus/oplire/target/`, `Nexus/oplire/dist/`.
- `node_modules/`, `__pycache__/`, entornos virtuales, archivos `.env` y logs.

Compila Oplire con el comando de arriba o publica los binarios como *Releases*.

## Aviso

- El plugin de Antigravity es un proyecto no oficial y su uso puede violar los Términos de Servicio de Google. Úsalo bajo tu responsabilidad.
- La rotación de IP mediante WARP y las modificaciones a la configuración de OpenCode Desktop pueden afectar tu red o tus credenciales. Haz respaldos antes de operar.

## Créditos y licencias

- **Oplire**: basado en [BerkeOruc/oplire](https://github.com/BerkeOruc/oplire), licencia MIT (`Nexus/oplire/LICENSE`).
- **opencode-antigravity-auth**: proyecto de [NoeFabris](https://github.com/NoeFabris/opencode-antigravity-auth), licencia MIT; se consume desde npm.
- **OpenCode Nexus**: código de integración y GUI de [PolloCraft](https://github.com/PolloCraft).

Cada componente conserva su propia licencia.
