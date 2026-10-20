<br>

<p align="center">
  <img src="https://img.shields.io/badge/Rust-1.75%2B-orange?style=for-the-badge&logo=rust" alt="Rust">
  <img src="https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python" alt="Python">
  <img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="License">
  <img src="https://img.shields.io/badge/Version-3.1.0-purple?style=for-the-badge" alt="Version">
  <img src="https://img.shields.io/badge/Windows-10%2F11-0078D4?style=for-the-badge&logo=windows" alt="Windows">
  <img src="https://img.shields.io/badge/Status-Stable-brightgreen?style=for-the-badge" alt="Status">
</p>

<h1 align="center">Oplire-OpenCode</h1>

<p align="center">
  <em>OpenCode Limit Reset + Anthropic Proxy Bridge</em><br>
  <sub>Rotacion de IP via WARP | Proxy inverso para Claude Code | Dashboard web en tiempo real</sub>
</p>

<br>

<p align="center">
  <a href="#que-es">Que es</a> &bull;
  <a href="#caracteristicas">Caracteristicas</a> &bull;
  <a href="#tecnologias">Tecnologias</a> &bull;
  <a href="#instalacion">Instalacion</a> &bull;
  <a href="#reglas-de-uso">Reglas</a> &bull;
  <a href="#menu">Menu</a> &bull;
  <a href="#dashboard">Dashboard</a> &bull;
  <a href="#inspiracion">Creditos</a>
</p>

<br>

---

## Que es

<p align="center">
  <img src="https://img.shields.io/badge/How%20It%20Works-Blue?style=flat-square" alt="How It Works">
</p>

**Oplire-OpenCode** es una herramienta de doble proposito disenada para trabajar con OpenCode y Claude Code. Permite rotar tu IP automaticamente cuando se alcanza el limite de solicitudes, y ofrece un proxy inverso que conecta Claude Code a modelos gratuitos.

<table>
<tr>
<td width="33%" valign="top">

#### Modo WARP Reset

OpenCode rastrea a los usuarios por IP. Cuando alcanzas el limite:

1. **Detiene** el tunel WARP actual
2. **Limpia** los datos de sesion cacheados
3. **Crea** un nuevo tunel con IP nueva
4. **Reinicia** WARP con una IP fresca

</td>
<td width="33%" valign="top">

#### Modo Proxy Bridge

```
Claude Code -> oplire proxy (127.0.0.1:8080) -> OpenCode Zen
```

- Traduce formato Anthropic API a formato OpenAI
- Streaming SSE en tiempo real
- Modelos gratuitos via endpoint `/v1/models`
- **Auto-reset WARP** en errores 429

</td>
<td width="33%" valign="top">

#### Restored IP (Sin WARP)

Boton en dashboard para restaurar tu IP original sin depender de WARP:

1. **Desconecta** WARP completamente
2. **Elimina** el registro de WARP
3. **Restaura** la configuracion de red original desde backup
4. **Verifica** que la IP sea la original

**Cuando usar:**
- Si no quieres depender de WARP
- Si WARP no funciona correctamente
- Si prefieres tu IP original

</td>
</tr>
</table>

---

## Caracteristicas

<table>
<tr>
<td>

- Rotacion automatica de IP en limites 429
- Streaming SSE en tiempo real
- Dashboard web en `localhost:8080`
- Menu interactivo (`oplire-menu.exe`)

</td>
<td>

- Bypass de OpenCode Desktop
- Herramienta de diagnostico (`doctor`)
- Soporte multiplataforma
- Configuracion por defecto

</td>
</tr>
<tr>
<td>

- **Gestion de sesiones** — Preserva sesiones que alcanzan limites de tokens
- **Restaurar IP (Restored IP)** — Restaura IP original sin WARP, desde dashboard o CLI
- **Backup de red** — Guarda y restaura configuracion de red completa

</td>
<td>

- **Monitor de sesiones** — Lista y detalles de sesiones activas
- **Verificacion de red** — Verifica estado de adaptadores y proxy
- **Logs de red** — Registro de todas las operaciones de red

</td>
</tr>
</table>

---

## Tecnologias

<table>
<tr>
<th>Nucleo (Rust)</th>
<th>Menu (Python)</th>
<th>Herramientas</th>
</tr>
<tr>
<td>

| Componente | Version |
|------------|---------|
| Rust | 1.75+ |
| Axum | 0.7 |
| Tokio | 1.x |
| Reqwest | 0.12 |
| Clap | 4.5 |
| Serde | 1.0 |
| Hyper | 1.x |
| Tower | 0.5 |
| Tracing | 0.1 |

</td>
<td>

| Componente | Version |
|------------|---------|
| Python | 3.10+ |
| PyInstaller | 6.22+ |

</td>
<td>

| Herramienta | Proposito |
|-------------|-----------|
| Cloudflare One Client | Rotacion de IP y gestion WARP |
| Everything | Busqueda archivos |

</td>
</tr>
</table>

---

## Instalacion

<p align="center">
  <img src="https://img.shields.io/badge/Step--by--Step%20Guide-0078D4?style=for-the-badge" alt="Guide">
</p>

### Requisitos Previos

<table>
<tr>
<th>Software</th>
<th>Descarga</th>
<th>Proposito</th>
</tr>
<tr>
<td><strong>Rust + Cargo</strong></td>
<td><a href="https://rustup.rs">rustup-init.exe</a></td>
<td>Compilar el proxy</td>
</tr>
<tr>
<td><strong>Python 3.10+</strong></td>
<td><a href="https://www.python.org/downloads/">python.org</a></td>
<td>Sistema de menu</td>
</tr>
<tr>
<td><strong>Git</strong></td>
<td><a href="https://git-scm.com/download/win">git-scm.com</a></td>
<td>Clonar repositorio</td>
</tr>
<tr>
<td><strong>Cloudflare One Client</strong></td>
<td><a href="https://developers.cloudflare.com/cloudflare-one/team-and-resources/devices/cloudflare-one-client/download/">Cloudflare</a></td>
<td>Rotacion de IP y gestion WARP</td>
</tr>
</table>

### Opcionales

| Software | Descarga | Proposito |
|----------|----------|-----------|
| Everything | [voidtools.com](https://www.voidtools.com/es-es/) | Busqueda rapida de archivos |

---

### Paso 1: Instalar Rust y Cargo

**Cargo** es el gestor de paquetes de Rust. Se instala junto con Rust.

**Windows:**
```powershell
# 1. Descarga rustup-init.exe desde https://rustup.rs
# 2. Ejecuta el instalador
# 3. Selecciona opcion por defecto (presiona Enter)
# 4. Reinicia tu terminal

# Verifica:
rustc --version
cargo --version
```

**Linux / macOS:**
```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source $HOME/.cargo/env
```

---

### Paso 2: Instalar Python

```powershell
# Descarga desde https://www.python.org/downloads/
# IMPORTANTE: Marca "Add Python to PATH"

# Verifica:
python --version
pip --version
```

---

### Paso 3: Instalar Git

```powershell
# Descarga desde https://git-scm.com/download/win

# Verifica:
git --version
```

---

### Paso 4: Instalar Cloudflare One Client

```powershell
# 1. Descarga desde: https://developers.cloudflare.com/cloudflare-one/team-and-resources/devices/cloudflare-one-client/download/
# 2. Instala y crea cuenta gratuita
# 3. Registra y conecta:

warp-cli registration new
warp-cli connect
warp-cli status
```

---

### Paso 5: Clonar y Compilar

```powershell
# Clonar
cd ~/Desktop
git clone https://github.com/PolloCraft/Oplire-OpenCode.git
cd Oplire-OpenCode

# Compilar nucleo Rust
cargo build --release

# Compilar menu
pip install pyinstaller
python -m PyInstaller --onefile --name oplire-menu --console --clean --noconfirm oplire_menu.py

# Limpiar archivos temporales
Remove-Item -Path "build" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -Path "oplire-menu.spec" -Force -ErrorAction SilentlyContinue
```

---

### (Opcional) Agregar al PATH

Para ejecutar `oplire` desde cualquier carpeta:

**Metodo PowerShell (Permanente):**
```powershell
$currentPath = [Environment]::GetEnvironmentVariable("Path", "User")
$newPath = "C:\Users\TU_USUARIO\Desktop\Oplire-OpenCode\target\release"
[Environment]::SetEnvironmentVariable("Path", "$currentPath;$newPath", "User")
```

**Metodo GUI:**
1. Presiona `Windows + R`, escribe `sysdm.cpl`
2. **Avanzadas** > **Variables de entorno**
3. Selecciona **Path** > **Editar** > **Nuevo**
4. Pega la ruta a `target\release`
5. Abre una nueva terminal

---

## Reglas de Uso

<p align="center">
  <img src="https://img.shields.io/badge/IMPORTANT-RULES-red?style=for-the-badge" alt="Important">
</p>

> **Lee atentamente estas especificaciones antes de usar Oplire-OpenCode.**

<table>
<tr>
<th width="5%">#</th>
<th width="30%">Regla</th>
<th>Descripcion</th>
</tr>
<tr>
<td align="center">1</td>
<td><strong>Verificar WARP</strong></td>
<td>Al abrir el dashboard, verifica que el <strong>WARP Tunnel</strong> este en estado <strong>Connected</strong>.</td>
</tr>
<tr>
<td align="center">2</td>
<td><strong>Cloudflare One Client</strong></td>
<td>Debe estar <strong>instalado y activado</strong> en todo momento, especialmente antes de ejecutar oplire-menu.</td>
</tr>
<tr>
<td align="center">3</td>
<td><strong>Sesiones activas</strong></td>
<td>No desactives oplire con sesiones activas. Quedaran inservibles.</td>
</tr>
<tr>
<td align="center">4</td>
<td><strong style="color: #ff3366;">Sesiones sin oplire</strong></td>
<td><strong style="color: #ff3366;">Si escribes en una sesion sin oplire activo, el chat no respondera y quedara permanentemente inservible.</strong></td>
</tr>
<tr>
<td align="center">5</td>
<td><strong>Abrir menu para resetear</strong></td>
<td>Debes abrir oplire-menu e iniciar el servidor proxy para resetear tu IP.</td>
</tr>
<tr>
<td align="center">6</td>
<td><strong>Saltar espera</strong></td>
<td>Cuando se agoten tus tokens, ejecuta oplire-menu para volver a usar el sistema.</td>
</tr>
<tr>
<td align="center">7</td>
<td><strong>Verificar sesion</strong></td>
<td>Si desactivas Cloudflare por error, usa <strong>Clear OpenCode</strong> (opcion 3 del menu).</td>
</tr>
<tr>
<td align="center">8</td>
<td><strong>No abusar</strong></td>
<td>Usa oplire-menu solo cuando se acabe el tiempo de uso de las IA.</td>
</tr>
<tr>
<td align="center">9</td>
<td><strong>Ser etico</strong></td>
<td>Usa estas herramientas de forma etica y responsable.</td>
</tr>
</table>

---

## Uso

### Ejecutar el Menu

```powershell
.\dist\oplire-menu.exe
```

### Comandos CLI

```powershell
.\target\release\oplire.exe --help          # Ver ayuda
.\target\release\oplire.exe proxy           # Iniciar proxy
.\target\release\oplire.exe reset           # Reset de WARP
.\target\release\oplire.exe dashboard       # Entrar al Dashboard
.\target\release\oplire.exe doctor          # Diagnostico
.\target\release\oplire.exe sessions list   # Listar sesiones activas
.\target\release\oplire.exe sessions detail # Ver detalles de una sesion
```

---

## Menu

<table>
<tr>
<th>Opcion</th>
<th>Descripcion</th>
</tr>
<tr>
<td><code>[1]</code></td>
<td><strong>Dashboard</strong> — Abrir panel de control web en localhost:8080</td>
</tr>
<tr>
<td><code>[2]</code></td>
<td><strong>Doctor</strong> — Ejecutar diagnosticos del sistema</td>
</tr>
<tr>
<td><code>[3]</code></td>
<td><strong>Clear OpenCode</strong> — Limpiar datos de OpenCode</td>
</tr>
<tr>
<td><code>[4]</code></td>
<td><strong>Proxy</strong> — Gestionar el servidor proxy</td>
</tr>
<tr>
<td><code>[5]</code></td>
<td><strong>OpenCode Local</strong> — Iniciar OpenCode local</td>
</tr>
<tr>
<td><code>[6]</code></td>
<td><strong>Programs</strong> — Herramientas recomendadas</td>
</tr>
<tr>
<td><code>[0]</code></td>
<td><strong>Salir</strong> — Cerrar el menu</td>
</tr>
</table>

---

## Dashboard

El dashboard se ejecuta en `http://localhost:8080` y ofrece monitoreo en tiempo real.

<table>
<tr>
<th>Seccion</th>
<th>Descripcion</th>
</tr>
<tr>
<td><strong>Overview</strong></td>
<td>Estado del proxy, tunel WARP, URL upstream, reintentos, boton <strong>Restored IP</strong></td>
</tr>
<tr>
<td><strong>Models</strong></td>
<td>Modelos gratuitos disponibles en OpenCode Zen</td>
</tr>
<tr>
<td><strong>Logs</strong></td>
<td>Registros de actividad del proxy</td>
</tr>
<tr>
<td><strong>Config</strong></td>
<td>Configuracion actual del servidor</td>
</tr>
<tr>
<td><strong>Sessions</strong></td>
<td>Gestion de sesiones: listar, ver detalles, estado de tokens</td>
</tr>
<tr>
<td><strong>Network</strong></td>
<td>Backup y restauracion de configuracion de red, verificacion de adaptadores</td>
</tr>
<tr>
<td><strong>Desktop</strong></td>
<td>Configuracion de bypass para OpenCode Desktop</td>
</tr>
<tr>
<td><strong>Programs</strong></td>
<td>Herramientas recomendadas para descargar</td>
</tr>
</table>

---

## Restored IP — Restaurar IP Original

El boton **Restored IP** en el dashboard permite restaurar tu IP original sin depender de WARP. Esto es util cuando:

- **No quieres usar WARP** — Prefieres tu IP de proveedor de internet
- **WARP no funciona** — Error de conexion o configuracion
- **Quieres volver a la normalidad** — Despues de usar WARP para resetear limites

### Como funciona

```
1. Desconecta WARP completamente
2. Elimina el registro de WARP
3. Restaura la configuracion de red original desde backup
4. Verifica que la IP sea la original
```

### Uso desde Dashboard

1. Abre el dashboard en `http://localhost:8080`
2. En la seccion **Overview**, haz clic en **Restored IP**
3. Confirma la accion
4. Espera a que se complete la restauracion

### API Endpoint

```http
POST /api/restore-ip
```

**Respuesta:**
```json
{
  "success": true,
  "original_ip": "190.123.45.67",
  "current_ip": "190.123.45.67",
  "ip_matches": true,
  "network_restoration": {
    "status": "completed",
    "restored_items": ["dhcp", "dns", "metrics"],
    "verification_passed": true
  },
  "message": "Full restoration completed. IP: 190.123.45.67 → 190.123.45.67. 3 items restored."
}
```

---

## Modelos Disponibles

<table>
<tr>
<th>Modelo</th>
<th>ID</th>
<th>Contexto</th>
</tr>
<tr>
<td>GLM 4.7 Free</td>
<td><code>glm-4.7-free</code></td>
<td>128K</td>
</tr>
<tr>
<td>MiniMax M2.1 Free</td>
<td><code>minimax-m2.1-free</code></td>
<td>128K</td>
</tr>
<tr>
<td>Kimi K2.5 Free</td>
<td><code>kimi-k2.5-free</code></td>
<td>128K</td>
</tr>
<tr>
<td>Qwen 2.5 72B Free</td>
<td><code>qwen-2.5-72b-free</code></td>
<td>128K</td>
</tr>
<tr>
<td>Llama 3.3 70B Free</td>
<td><code>llama-3.3-70b-free</code></td>
<td>128K</td>
</tr>
</table>

---

## Estructura del Proyecto

```
Oplire-OpenCode/
├── src/
│   ├── main.rs              # Punto de entrada CLI
│   ├── lib.rs               # Exportaciones de libreria
│   ├── config.rs            # Manejo de configuracion
│   ├── dashboard.rs         # HTML/API del dashboard web
│   ├── bypass.rs            # Logica de bypass Desktop
│   ├── watch.rs             # Monitor de archivos
│   ├── sessions.rs          # Gestion de sesiones y limites de tokens
│   ├── network.rs           # Backup/restore de red, verificacion de adaptadores
│   ├── proxy/               # Servidor proxy
│   │   ├── server.rs        # Servidor HTTP con SessionGuard
│   │   └── handlers.rs      # Manejadores con deteccion de limites
│   ├── transform/           # Transformacion de formato API
│   └── warp/                # Manejo del tunel WARP
│       └── resolver.rs      # Captura y restauracion de IP original
├── oplire_menu.py           # Script de menu Python
├── dist/
│   └── oplire-menu.exe      # Ejecutable del menu
├── scripts/                 # Scripts auxiliares
├── Cargo.toml               # Dependencias Rust
├── LICENSE                  # Licencia MIT
└── README.md                # Esta documentacion
```

---

## Inspiracion y Creditos

<table>
<tr>
<td align="center">
  <a href="https://github.com/BerkeOruc">
    <img src="https://github.com/BerkeOruc.png" width="100" style="border-radius:50%"><br>
    <sub><b>Berke Oruc</b></sub>
  </a>
  <br>
  <sub>Inspiracion Principal</sub>
</td>
<td align="center">
  <a href="https://github.com/TobiManGenobi">
    <img src="https://github.com/TobiManGenobi.png" width="100" style="border-radius:50%"><br>
    <sub><b>TobiManGenobi</b></sub>
  </a>
  <br>
  <sub>Complemento de Aprendizaje</sub>
</td>
</tr>
</table>

<table>
<tr>
<td>

**Berke Oruc** — Autor del proyecto original [oplire](https://github.com/BerkeOruc/oplire). Sin su trabajo, Oplire-OpenCode no existiria.

- **GitHub:** [github.com/BerkeOruc](https://github.com/BerkeOruc)
- **Repositorio:** [github.com/BerkeOruc/oplire](https://github.com/BerkeOruc/oplire)

</td>
<td>

**TobiManGenobi** — Autor de [Oplire-mini](https://github.com/TobiManGenobi/Oplire-mini). Complemento el aprendizaje con su version simplificada.

- **GitHub:** [github.com/TobiManGenobi](https://github.com/TobiManGenobi)
- **Repositorio:** [github.com/TobiManGenobi/Oplire-mini](https://github.com/TobiManGenobi/Oplire-mini)

</td>
</tr>
</table>

---

## Solucion de Problemas

<table>
<tr>
<th>Problema</th>
<th>Solucion</th>
</tr>
<tr>
<td><code>cargo is not recognized</code></td>
<td>Reinicia la terminal o ejecuta <code>$env:PATH += ";$env:USERPROFILE\.cargo\bin"</code></td>
</tr>
<tr>
<td><code>oplire is not recognized</code></td>
<td>Agrega oplire al PATH (ver seccion "Agregar al PATH")</td>
</tr>
<tr>
<td><code>warp-cli not found</code></td>
<td>Instala Cloudflare One Client desde el enlace en Requisitos</td>
</tr>
<tr>
<td><code>python is not recognized</code></td>
<td>Reinstala Python marcando "Add Python to PATH"</td>
</tr>
<tr>
<td>Dashboard no carga modelos</td>
<td>Verifica que OpenCode este corriendo en puerto 3000</td>
</tr>
<tr>
<td>Puerto 8080 en uso</td>
<td>Cambia el puerto: <code>oplire.exe proxy --listen 0.0.0.0:9000</code></td>
</tr>
<tr>
<td>Menu exe no inicia</td>
<td>Recompila con PyInstaller (ver Paso 5)</td>
</tr>
<tr>
<td><code>error: cannot find crate</code></td>
<td>Actualiza Rust: <code>rustup update</code></td>
</tr>
<tr>
<td>Sesion desaparece al alcanzar limite</td>
<td>Verifica que el proxy este ejecutando la version 3.1.0+ con gestion de sesiones</td>
</tr>
<tr>
<td>Boton Restored IP no aparece</td>
<td>Recompila con <code>cargo build --release</code> y reinicia el proxy</td>
</tr>
<tr>
<td>Error en backup de red</td>
<td>Verifica que tengas permisos de administrador para ejecutar comandos de red</td>
</tr>
<tr>
<td>Sesiones no se preservan</td>
<td>Revisa los logs del proxy para ver si hay errores en la deteccion de limites</td>
</tr>
<tr>
<td>Restored IP no restaura la IP original</td>
<td>Verifica que se haya capturado el backup de red antes de usar WARP. El backup se crea automaticamente al iniciar el proxy.</td>
</tr>
<tr>
<td>Quiero usar mi IP original sin WARP</td>
<td>Usa el boton <strong>Restored IP</strong> en el dashboard. Esto desconecta WARP y restaura tu configuracion de red original.</td>
</tr>
</table>

---

## Sobre el Proyecto

Oplire-OpenCode es un proyecto completo que integra varias herramientas para facilitar el uso de OpenCode y Claude Code sin limites de tasa. A continuacion se explica cada componente.

### El Nucleo: oplire.exe

Es el corazon del sistema. Un ejecutable compilado en Rust que ofrece:

- **Proxy inverso** — Recibe peticiones de Claude Code en formato Anthropic API y las reenvia a OpenCode Zen en formato OpenAI. Esto permite usar modelos gratuitos como GLM 4.7, MiniMax M2.1, Kimi K2.5, Qwen 2.5 72B y Llama 3.3 70B.

- **Reset de WARP** — Cuando detecta un error 429 (limite de tasa), automaticamente detiene el tunel WARP, limpia la sesion y crea un nuevo tunel con IP diferente. Esto resetea el contador de solicitudes.

- **Dashboard web** — Un servidor HTTP en el puerto 8080 que sirve una pagina web con monitoreo en tiempo real del estado del proxy, el tunel WARP, los modelos disponibles y la configuracion actual.

- **Desktop bypass** — Modifica la configuracion de OpenCode Desktop para que todas sus peticiones pasen por el proxy de oplire, permitiendo el reset automatico de limites.

### Nuevas Funcionalidades (v3.1.0)

#### Gestion de Sesiones

- **Deteccion de limites** — Identifica automaticamente cuando una sesion alcanza el limite de tokens
- **Preservacion de sesiones** — Las sesiones con status `limit_reached` no se eliminan durante la limpieza
- **Estados de sesion** — `active`, `limit_reached`, `paused`, `resumable`, `completed`
- **Monitoreo de tokens** — Rastrea uso de tokens por sesion y calcula estimaciones

#### Backup y Restauracion de Red

- **NetworkManager** — Sistema completo de gestion de red con soporte Windows, Linux y macOS
- **Backup de configuracion** — Guarda adaptadores, DHCP/estatico, proxy, DNS y metricas
- **Restauracion de red** — Restaura toda la configuracion de red desde un backup
- **Verificacion** — Verifica estado de adaptadores, proxy y conectividad
- **Restaurar IP** — Boton en dashboard para restaurar la IP original de WARP
- **Logs de red** — Registro detallado de todas las operaciones de red

### El Menu: oplire-menu.exe

Un ejecutable compilado desde Python que ofrece una interfaz de texto simple para gestionar todas las funcionalidades sin necesidad de memorizar comandos. Incluye:

- **Dashboard** — Abre el navegador con el panel de control
- **Doctor** — Verifica que WARP, OpenCode y Claude Code esten correctamente instalados
- **Clear OpenCode** — Limpia archivos temporales y cache de OpenCode
- **Proxy** — Inicia o detiene el servidor proxy
- **OpenCode Local** — Inicia un servidor OpenCode en el puerto 3000
- **Programs** — Enlaces para descargar Everything y Cloudflare One Client

### Herramientas Externas

#### Cloudflare One Client

Es el cliente oficial de Cloudflare para gestionar tuneles WARP. Permite rotar tu IP automaticamente conectandote a la red global de Cloudflare. Es esencial para que oplire pueda resetear tu IP cuando alcanzas el limite de solicitudes.

#### Everything (Voidtools)

Un buscador de archivos ultra rapido para Windows. Permite encontrar cualquier archivo, carpeta o configuracion en milisegundos. Es util para localizar archivos de configuracion de OpenCode en todo el sistema.

### Flujo de Uso Tipico

```
1. Instalar requisitos (Rust, Python, Cloudflare One Client)
2. Compilar oplire.exe y oplire-menu.exe
3. Ejecutar oplire-menu.exe
4. Iniciar el Dashboard (opcion 1)
5. Verificar que WARP este Connected
6. Abrir Claude Code o OpenCode
7. Cuando aparezca limite de tiempo, usar oplire para resetear
8. Continuar trabajando
```

### Modelos Gratuitos Disponibles

| Modelo | Fabricante | Contexto | Uso Recomendado |
|--------|------------|----------|-----------------|
| GLM 4.7 Free | Zhipu AI | 128K | Codigo general, chat |
| MiniMax M2.1 Free | MiniMax | 128K | Analisis de texto largo |
| Kimi K2.5 Free | Moonshot AI | 128K | Documentacion, resumenes |
| Qwen 2.5 72B Free | Alibaba | 128K | Tareas complejas, razonamiento |
| Llama 3.3 70B Free | Meta | 128K | Codigo, creatividad |

### Arquitectura Tecnica

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Claude Code /  │────▶│  oplire proxy    │────▶│  OpenCode Zen   │
│  OpenCode       │     │  (127.0.0.1:8080)│     │  (upstream)     │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                              │
                              ▼
                        ┌──────────────────┐
                        │  Cloudflare WARP │
                        │  (Rotacion IP)   │
                        └──────────────────┘
                              │
                              ▼
                        ┌──────────────────┐
                        │  NetworkManager  │
                        │  (Backup/Restore)│
                        └──────────────────┘
```

---

## Licencia

Este proyecto esta licenciado bajo la **Licencia MIT**. Ver [LICENSE](LICENSE) para los terminos completos.

---

<br>

<p align="center">
  <img src="https://img.shields.io/badge/Made_with-❤_by_PolloCraft20-0078D4?style=for-the-badge" alt="Made by PolloCraft20">
</p>

<p align="center">
  <a href="https://github.com/PolloCraft/Oplire-OpenCode">
    <img src="https://img.shields.io/badge/GitHub-Repository-181717?style=for-the-badge&logo=github" alt="GitHub">
  </a>
</p>
