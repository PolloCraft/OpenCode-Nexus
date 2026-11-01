# -*- coding: utf-8 -*-
"""
NEXUS Suite - oplire_ops (MODULO OPENCODE)
==========================================
Todas las operaciones del motor Oplire, expuestas como funciones limpias
que devuelven datos (sin imprimir). La GUI las consume.

Cubre:
  * Rotacion / restauracion de IP (WARP): reset, quick-reset, stop, status.
  * Desktop bypass: setup-desktop, restore-desktop, desktop-status.
  * Dashboard / Proxy (servidor local 127.0.0.1:8080).
  * API HTTP del dashboard (tiempo real).
  * Cache "vcache": busqueda en tiempo real, limpiar cache, borrar datos.
  * Sesiones: fix-sessions, sessions-status/list/detail.
  * Diagnostico: doctor, models, install.
"""

import os
import sys
import json
import time
import shutil
import datetime

from . import common as C


# ============================================================ rutas =========

def oplire_dir():
    return C.oplire_dir()


def _bundled_oplire():
    """oplire.exe embebido dentro del .exe (PyInstaller) o junto a el."""
    env = os.environ.get("NEXUS_OPLIRE_EXE", "")
    if env and os.path.isfile(env):
        return env
    dirs = []
    meipass = getattr(sys, "_MEIPASS", "")
    if meipass:
        dirs.append(meipass)
    if getattr(sys, "frozen", False):
        dirs.append(os.path.dirname(sys.executable))
    for d in dirs:
        for p in (os.path.join(d, "oplire.exe"),
                  os.path.join(d, "oplire", "oplire.exe"),
                  os.path.join(d, "bin", "oplire.exe"),
                  os.path.join(d, "tools", "oplire.exe")):
            if os.path.isfile(p):
                return p
    return None


def _stable_bin_dir():
    local = os.environ.get("LOCALAPPDATA") or C.user_home()
    return os.path.join(local, "Nexus", "bin")


def find_oplire_exe():
    env = os.environ.get("NEXUS_OPLIRE_EXE", "")
    if env and os.path.isfile(env):
        return env
    # 1) Binario estable dentro del proyecto (portable) o compilado en target.
    folder = oplire_dir()
    for sub in (("dist",), ("target", "release"), ("target", "debug"), ()):
        exe = os.path.join(folder, *sub, "oplire.exe")
        if os.path.isfile(exe):
            return exe
    # 2) Empaquetado: copia estable en %LOCALAPPDATA%\Nexus\bin para que
    #    funcione aunque el .exe extraiga su contenido temporal y lo borre.
    bundled = _bundled_oplire()
    if bundled:
        dest_dir = _stable_bin_dir()
        dest = os.path.join(dest_dir, "oplire.exe")
        try:
            if not os.path.isfile(dest) or os.path.getsize(dest) != os.path.getsize(bundled):
                os.makedirs(dest_dir, exist_ok=True)
                try:
                    shutil.copy2(bundled, dest)
                except Exception:
                    pass
            if os.path.isfile(dest):
                return dest
        except Exception:
            pass
        return bundled
    # 3) Junto al .exe o en la carpeta base (distribucion por carpeta).
    for base in C.candidate_bases():
        for p in (os.path.join(base, "oplire.exe"),
                  os.path.join(base, "oplire", "oplire.exe"),
                  os.path.join(base, "bin", "oplire.exe"),
                  os.path.join(base, "tools", "oplire.exe")):
            if os.path.isfile(p):
                return p
    return None


def has_engine():
    return find_oplire_exe() is not None


def oplire_config_dir():
    appdata = os.environ.get("APPDATA", "")
    if appdata:
        return os.path.join(appdata, "oplire")
    return os.path.join(C.user_home(), ".config", "oplire")


def oplire_data_dir():
    local = os.environ.get("LOCALAPPDATA", "")
    if local:
        return os.path.join(local, "oplire")
    return os.path.join(C.user_home(), ".local", "share", "oplire")


def read_config():
    path = os.path.join(oplire_config_dir(), "config.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return __import__("json").load(f)
    except Exception:
        return {}


# ======================================================= ejecucion CLI ======

def _engine_env():
    """PATH con OpenCode real visible para el motor Oplire (doctor/local)."""
    dirs = []
    try:
        binary = opencode_binary()
        if binary:
            dirs.append(os.path.dirname(binary))
    except Exception:
        pass
    try:
        from . import antigravity_ops as _ag
        dirs += _ag.opencode_dirs()
    except Exception:
        pass
    seen, clean = set(), []
    for d in dirs:
        if not d:
            continue
        key = os.path.normcase(os.path.abspath(d))
        if key not in seen and os.path.isdir(d):
            seen.add(key)
            clean.append(d)
    if not clean:
        return None
    env = os.environ.copy()
    env["PATH"] = os.pathsep.join(clean + [env.get("PATH", "")])
    return env


def run_cli(args, timeout=120, verbose=False):
    """Ejecuta 'oplire <args>'. Devuelve (rc, salida_limpia)."""
    exe = find_oplire_exe()
    if not exe:
        return -1, ("[ERROR] oplire.exe no encontrado.\n"
                    f"       Ubicacion esperada: {os.path.join(oplire_dir(), 'dist', 'oplire.exe')}\n"
                    "       Copia el motor a Nexus/oplire/dist/oplire.exe o compilalo con build.ps1 -Release")
    cmd = [exe] + list(args)
    if verbose and "-v" not in cmd and "--verbose" not in cmd:
        cmd.append("-v")
    rc, out = C.run_cmd(cmd, timeout=timeout, cwd=oplire_dir(), env=_engine_env())
    return rc, C.strip_ansi(out).strip()


def run_cli_console(args, title="Oplire"):
    exe = find_oplire_exe()
    if not exe:
        return False
    return C.open_new_console([exe] + list(args), cwd=oplire_dir(), title=title,
                              env=_engine_env())


# ================================================ WARP / rotacion de IP =====

def rotate_ip(verbose=False):
    """Rotacion rapida de IP (quick-reset)."""
    return run_cli(["quick-reset"], timeout=180, verbose=verbose)


def force_reset(verbose=False):
    """Reset completo del tunel WARP (reset)."""
    return run_cli(["reset"], timeout=300, verbose=verbose)


def stop_warp(verbose=False):
    """Desconecta WARP (devuelve la IP real)."""
    return run_cli(["stop"], timeout=120, verbose=verbose)


def reconnect_warp():
    """Reconecta / actualiza el tunel WARP (warp-cli connect)."""
    rc, out = C.run_cmd(["warp-cli", "connect"], timeout=60)
    return rc, C.strip_ansi(out).strip()


def warp_status_raw():
    """Estado crudo de WARP (warp-cli status)."""
    if not C.tool_available("warp-cli"):
        return -1, "warp-cli no esta instalado o no esta en el PATH"
    rc, out = C.run_cmd(["warp-cli", "status"], timeout=20)
    return rc, C.strip_ansi(out).strip()


def warp_connected():
    """True si WARP reporta 'Connected' (tiempo real)."""
    rc, out = warp_status_raw()
    if rc != 0:
        return None
    low = (out or "").lower()
    if "connected" in low and "disconnected" not in low:
        return True
    if "disconnected" in low:
        return False
    return None


def cli_status(json_out=True):
    args = ["status"] + (["--json"] if json_out else [])
    return run_cli(args, timeout=20)


# ============================================================ dashboard =====

def dashboard_port():
    cfg = read_config()
    listen = cfg.get("listen") or cfg.get("listen_addr") or "127.0.0.1:8080"
    try:
        return int(str(listen).rsplit(":", 1)[-1])
    except Exception:
        return 8080


def dashboard_base():
    cfg = read_config()
    listen = cfg.get("listen") or cfg.get("listen_addr") or "127.0.0.1:8080"
    if "://" not in str(listen):
        listen = f"http://{listen}"
    return str(listen).rstrip("/")


def dashboard_running():
    return C.port_open("127.0.0.1", dashboard_port())


def dashboard_owner():
    """(pid, imagen) del proceso que escucha en el puerto del dashboard."""
    return C.port_owner(dashboard_port())


def oplire_running():
    return C.process_running("oplire.exe")


def dashboard_is_oplire():
    """True si el dashboard responde y pertenece al motor oplire."""
    if not dashboard_running():
        return False
    _pid, image = dashboard_owner()
    if image:
        return "oplire" in image.lower()
    return oplire_running()


def start_dashboard(port=None):
    args = ["dashboard"]
    if port:
        args += ["--listen", f"127.0.0.1:{int(port)}"]
    return run_cli_console(args, title="Oplire Dashboard")


def start_proxy(port=None):
    args = ["proxy"]
    if port:
        args += ["--listen", f"127.0.0.1:{int(port)}"]
    return run_cli_console(args, title="Oplire Proxy")


def start_daemon(port=None):
    args = ["daemon"]
    if port:
        args += ["--listen", f"127.0.0.1:{int(port)}"]
    return run_cli_console(args, title="Oplire Daemon")


def stop_oplire():
    """Detiene el servidor oplire (dashboard/proxy/daemon) matando el proceso."""
    if not oplire_running():
        return True, "No habia ningun proceso oplire en ejecucion."
    rc, out = C.kill_process("oplire.exe")
    msg = C.strip_ansi(out).strip()
    if rc == 0:
        return rc, msg or "Servidor oplire detenido."
    return rc, msg or "No se pudo detener oplire.exe."


def open_dashboard_browser():
    import webbrowser
    return webbrowser.open(dashboard_base() + "/")


# ================================================ OpenCode Local (servidor) ==

def opencode_command():
    """Ruta al comando 'opencode' (prefiere el .exe real si existe)."""
    binary = opencode_binary()
    if binary and opencode_binary_ok():
        return binary
    for name in ("opencode", "opencode.cmd", "opencode.exe", "opencode.ps1", "opencode.bat"):
        p = C.which(name)
        if p:
            return p
    return None


def opencode_broken():
    """True si npm dejo el aviso de postinstall en lugar del binario real."""
    binary = opencode_binary()
    return bool(binary) and not opencode_binary_ok()


def opencode_server_port():
    """Puerto del servidor local de OpenCode (upstream del proxy). Default 3000."""
    cfg = read_config()
    upstream = cfg.get("opencode_base_url") or cfg.get("upstream") or "http://localhost:3000"
    try:
        return int(str(upstream).rstrip("/").rsplit(":", 1)[-1])
    except Exception:
        return 3000


def opencode_server_owner(port=None, fast=False):
    """(pid, imagen) del proceso que escucha en el puerto del servidor local."""
    return C.port_owner(port or opencode_server_port(), fast=fast)


def opencode_server_running(port=None, verify=True, fast=False):
    """
    True si el servidor local de OpenCode responde en 127.0.0.1:<port>.
    Con verify=True solo cuenta como servidor nuestro si el proceso es 'opencode'
    (evita falsos positivos cuando otro servicio, p.ej. Docker, ocupa el puerto).
    """
    port = port or opencode_server_port()
    if not C.port_open("127.0.0.1", port):
        return False
    if not verify:
        return True
    _pid, name = C.port_owner(port, fast=fast)
    return "opencode" in (name or "").lower()


def opencode_server_conflict(port=None, fast=False):
    """
    Si el puerto del servidor local lo ocupa OTRO proceso (no opencode),
    devuelve el nombre del proceso; si no, None.
    """
    port = port or opencode_server_port()
    if not C.port_open("127.0.0.1", port):
        return None
    _pid, name = C.port_owner(port, fast=fast)
    if name and "opencode" in name.lower():
        return None
    return name or "(otro servicio)"


def start_opencode_server(port=3000):
    """
    Inicia el servidor local de OpenCode en una consola visible
    (opencode serve --hostname 127.0.0.1 --port <port>).
    Este servidor es el upstream por defecto del proxy de Oplire.
    """
    if opencode_broken():
        return False, ("OpenCode esta instalado de forma incompleta (el postinstall no se ejecuto; "
                       "por eso Windows muestra 'Aplicacion de 16 bits no compatible').\n"
                       "Ve a Herramientas > 'Reparar OpenCode' y vuelve a intentarlo.")
    opc = opencode_command()
    if not opc:
        return False, "opencode no esta en el PATH. Instalalo primero (Herramientas)."
    ok = C.open_new_console(
        [opc, "serve", "--hostname", "127.0.0.1", "--port", str(port)],
        title=f"OpenCode Local :{port}")
    if ok:
        return True, f"Servidor OpenCode iniciado en 127.0.0.1:{port}."
    return False, "No se pudo abrir la consola del servidor OpenCode."


def open_opencode_browser(port=3000):
    import webbrowser
    return webbrowser.open(f"http://127.0.0.1:{port}")


def stop_opencode_server(port=None):
    """
    Detiene el servidor local de OpenCode SOLO si el proceso que ocupa el puerto
    es 'opencode'. Nunca detiene procesos protegidos (Docker/WSL/DB/red) ni
    servicios de otros proyectos.
    """
    port = port or opencode_server_port()
    pid, name = C.port_owner(port)
    if not pid:
        return False, f"Ningun proceso escuchando en 127.0.0.1:{port}."
    if "opencode" not in (name or "").lower():
        return False, (f"El puerto {port} lo usa '{name or 'desconocido'}' (PID {pid}), "
                       f"no es el servidor de OpenCode. NO se detiene para no afectar "
                       f"otros servicios (Docker / proyectos).")
    return C.safe_kill(pid, ("opencode",))


# ==================================================== API HTTP (tiempo real) =

def api_get(path, timeout=6):
    ok, data = C.http_get_json(dashboard_base() + path, timeout=timeout)
    return ok, data


def api_post(path, timeout=30):
    ok, data = C.http_post_json(dashboard_base() + path, timeout=timeout)
    return ok, data


def api_reset_ip():
    return api_post("/api/reset-ip", timeout=180)


def api_restore_ip():
    return api_post("/api/restore-ip", timeout=180)


def api_network_backup():
    return api_post("/api/network/backup", timeout=60)


def api_network_status():
    return api_get("/api/network/status")


def api_network_restore():
    return api_post("/api/network/restore", timeout=90)


def api_setup_desktop():
    return api_post("/api/setup-desktop", timeout=30)


def api_restore_desktop():
    return api_post("/api/restore-desktop", timeout=30)


def api_desktop_status():
    return api_get("/api/desktop-status")


def api_clear_cache():
    return api_post("/api/clear-cache", timeout=60)


def api_clear_all_data():
    return api_post("/api/clear-all-data", timeout=120)


def api_status():
    return api_get("/api/status")


def api_models():
    return api_get("/api/models")


def api_config():
    return api_get("/api/config")


def _json_text(data):
    if isinstance(data, str):
        return data
    try:
        return json.dumps(data, indent=2, ensure_ascii=False)
    except (TypeError, ValueError):
        return str(data)


def api_status_report():
    """
    'Estado API': consulta real /api/status y devuelve (ok, texto legible).
    Nunca muestra un dict crudo: formatea la respuesta y explica fallos.
    """
    if not dashboard_running():
        return False, (f"[!] El dashboard no responde en {dashboard_base()}.\n"
                       "    Inicia el Dashboard/Proxy antes de consultar la API.")
    ok, data = api_status()
    if not ok:
        return False, f"[!] La API /api/status no respondio: {_json_text(data)}"
    return True, f"[OK] API /api/status en {dashboard_base()}:\n\n{_json_text(data)}"


def server_status_report():
    """
    'Verificar estado' del Proxy/Servidor: comprueba puerto, proceso real,
    upstream de OpenCode y API. Devuelve (ok, texto multilinea).
    """
    port = dashboard_port()
    up = dashboard_running()
    running = oplire_running()
    owner_pid, owner_img = dashboard_owner() if up else (None, None)
    is_ours = (not owner_img) or ("oplire" in (owner_img or "").lower())
    oc_port = opencode_server_port()
    oc_up = opencode_server_running(oc_port)
    oc_conflict = None if oc_up else opencode_server_conflict(oc_port)
    lines = [
        f"Dashboard/Proxy : {'● ACTIVO' if up else '○ inactivo'}  ({dashboard_base()})",
        f"Proceso oplire  : {'● en ejecucion' if running else '○ detenido'}",
    ]
    if up:
        lines.append(f"Puerto {port}     : PID {owner_pid or '?'} ({owner_img or 'desconocido'})"
                     + ("  [oplire]" if is_ours else "  [otro servicio]"))
    lines.append(f"OpenCode local  : {'● ACTIVO' if oc_up else '○ inactivo'}  (127.0.0.1:{oc_port})")
    if oc_conflict:
        lines.append(f"                  [!] Puerto {oc_port} ocupado por '{oc_conflict}'")
    api_ok = False
    api_note = "no consultada"
    if up:
        api_ok, data = api_status()
        api_note = "responde" if api_ok else f"sin respuesta ({_json_text(data)[:120]})"
    lines.append(f"API /api/status : {'● ' + api_note if api_ok else '○ ' + api_note}")
    if not up:
        lines.append("")
        lines.append("Sugerencia: pulsa 'Iniciar Dashboard' o 'Iniciar Proxy'.")
    elif not is_ours:
        lines.append("")
        lines.append(f"[!] El puerto {port} lo usa otro servicio; no se detendra por seguridad.")
    return (up and (is_ours or running)), "\n".join(lines)


# ================================================ instalacion real (npm) ====

def _npm():
    return shutil.which("npm")


def _npm_root():
    """Carpeta global de paquetes npm (donde vive opencode-ai)."""
    npm = _npm()
    if not npm:
        return ""
    rc, out = C.run_cmd([npm, "root", "-g"], timeout=30)
    if rc != 0:
        return ""
    for line in reversed((out or "").splitlines()):
        line = line.strip()
        if line and os.path.isdir(line):
            return line
    return ""


def opencode_binary():
    """Ruta real del ejecutable de OpenCode dentro del paquete npm global."""
    root = _npm_root()
    if not root:
        return ""
    path = os.path.join(root, "opencode-ai", "bin", "opencode.exe")
    return path if os.path.isfile(path) else ""


def opencode_binary_ok():
    """True si el binario es un PE real (MZ) y no el aviso de postinstall."""
    path = opencode_binary()
    if not path:
        return False
    try:
        with open(path, "rb") as f:
            return f.read(2) == b"MZ"
    except OSError:
        return False


def opencode_postinstall():
    root = _npm_root()
    if not root:
        return ""
    path = os.path.join(root, "opencode-ai", "postinstall.mjs")
    return path if os.path.isfile(path) else ""


def repair_opencode():
    """
    Repara el error 'Aplicacion de 16 bits no compatible': el postinstall de
    opencode-ai no se ejecuto y bin/opencode.exe es solo un aviso de texto.
    Ejecuta el postinstall oficial y verifica el binario real.
    """
    if opencode_binary_ok():
        path = opencode_binary()
        rc, out = C.run_cmd([path, "--version"], timeout=60)
        ver = (out or "").strip().splitlines()[0] if rc == 0 and (out or "").strip() else "instalado"
        return True, f"OpenCode ya esta sano ({ver}).\n{path}"
    post = opencode_postinstall()
    if not post:
        return False, ("No se encontro la instalacion npm de opencode-ai.\n"
                       "Usa 'Instalar OpenCode' en Herramientas.")
    rc, out = C.run_cmd(["node", post], timeout=900, cwd=os.path.dirname(post))
    text = C.strip_ansi(out or "").strip()
    if not opencode_binary_ok():
        return False, ("El postinstall no pudo crear un binario valido.\n"
                       + (text or "Sin salida de node."))
    path = opencode_binary()
    rc2, ver = C.run_cmd([path, "--version"], timeout=60)
    version = (ver or "").strip().splitlines()[0] if rc2 == 0 and (ver or "").strip() else "verificado"
    return True, (f"OpenCode reparado correctamente: {version}\n{path}"
                  + ("\n" + text if text else ""))


def install_npm_console(package, title="NEXUS Install", repair_postinstall=False):
    """Instala un paquete npm global en una consola real de NEXUS."""
    npm = _npm()
    if not npm:
        return False, ("npm no esta instalado. Instala Node.js desde https://nodejs.org "
                       "(marca 'Add to PATH') y vuelve a intentarlo.")
    inner = (f'echo [NEXUS] Instalando {package} ... & '
             f'"{npm}" install -g {package}')
    if repair_postinstall:
        post = opencode_postinstall()
        if post:
            inner += (f' & echo. & echo [NEXUS] Ejecutando postinstall de OpenCode... & '
                      f'node "{post}"')
    inner += ' & echo. & echo [NEXUS] Instalacion finalizada. & pause'
    if C.open_new_console(inner, title=title):
        return True, (f"Consola de instalacion abierta: npm install -g {package}.\n"
                      "Al terminar, pulsa 'Refrescar' o F5 para detectarlo.")
    return False, "No se pudo abrir la consola de instalacion."


def install_component(target):
    """
    Instalacion REAL e independiente de componentes:
      opencode     -> npm install -g opencode-ai
      claude-code  -> npm install -g @anthropic-ai/claude-code
      warp         -> winget install Cloudflare.Cloudflare-WARP
      all          -> los tres en orden
    """
    target = (target or "").lower()
    if target in ("opencode", "opencode-ai"):
        return install_npm_console("opencode-ai", "NEXUS - Instalar OpenCode",
                                   repair_postinstall=True)
    if target in ("claude", "claude-code"):
        return install_npm_console("@anthropic-ai/claude-code", "NEXUS - Instalar Claude Code")
    if target == "warp":
        if shutil.which("winget"):
            inner = ('echo [NEXUS] Instalando Cloudflare WARP... & '
                     'winget install --id Cloudflare.Cloudflare-WARP -e '
                     '--accept-package-agreements --accept-source-agreements & '
                     'echo. & echo [NEXUS] Finalizado. & pause')
            if C.open_new_console(inner, title="NEXUS - Instalar WARP"):
                return True, "Instalacion de Cloudflare WARP abierta (winget)."
        return False, "winget no esta disponible. Descarga WARP desde el boton de Cloudflare."
    if target == "all":
        if not _npm():
            return False, "npm no esta instalado. Instala Node.js primero."
        inner = ('echo [NEXUS] Instalando OpenCode... & '
                 f'"{_npm()}" install -g opencode-ai')
        post = opencode_postinstall()
        if post:
            inner += (f' & echo. & echo [NEXUS] Reparando binario de OpenCode... & '
                      f'node "{post}"')
        inner += (' & echo. & echo [NEXUS] Instalando Claude Code... & '
                  f'"{_npm()}" install -g @anthropic-ai/claude-code & '
                  'echo. & echo [NEXUS] Componentes instalados. & pause')
        if C.open_new_console(inner, title="NEXUS - Instalar TODO"):
            return True, "Instalacion de OpenCode + Claude Code abierta en una consola."
        return False, "No se pudo abrir la consola de instalacion."
    return False, f"Componente desconocido: {target}"


# ======================================================== desktop bypass =====

def desktop_config_path():
    """Ruta del config.json de OpenCode Desktop (mismas candidatas que Oplire)."""
    cands = []
    for env in ("APPDATA", "LOCALAPPDATA"):
        base = os.environ.get(env, "")
        if base:
            cands.append(os.path.join(base, "opencode", "config.json"))
    home = C.user_home()
    cands += [
        os.path.join(home, ".opencode", "config.json"),
        os.path.join(home, ".config", "opencode", "config.json"),
    ]
    for path in cands:
        if os.path.isfile(path):
            return path
    return cands[0] if cands else ""


def bypass_state_path():
    local = os.environ.get("LOCALAPPDATA") or os.path.join(C.user_home(), ".local", "share")
    return os.path.join(local, "oplire", "bypass_state.json")


def bypass_state():
    try:
        with open(bypass_state_path(), "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def desktop_status_data():
    """
    Estado REAL del bypass leyendo el config de Desktop y el estado persistido.
    Rapido (sin CLI), apto para refresco en tiempo real.
    """
    path = desktop_config_path()
    exists = bool(path and os.path.isfile(path))
    cfg = {}
    if exists:
        try:
            with open(path, "r", encoding="utf-8-sig") as f:
                cfg = json.load(f)
        except (OSError, ValueError):
            cfg = {}
    api = cfg.get("api") if isinstance(cfg, dict) else {}
    if not isinstance(api, dict):
        api = {}
    base = str(api.get("base_url") or "")
    marker = bool(cfg.get("__oplire_bypass_active__")) if isinstance(cfg, dict) else False
    proxied = marker or "127.0.0.1:8080" in base or "localhost:8080" in base
    state = bypass_state()
    backup = bool(path and os.path.isfile(path + ".bak"))
    return {
        "source": "local",
        "config_found": exists,
        "config_path": path,
        "is_proxied": proxied,
        "active": proxied or bool(state.get("enabled")),
        "api_base_url": base,
        "api_key_set": bool(api.get("key")),
        "backup_exists": backup,
        "state": state,
        "last_verified": state.get("last_verified"),
        "proxy_addr": state.get("proxy_addr") or "",
    }


def desktop_report():
    """Texto legible del estado del bypass para la GUI."""
    d = desktop_status_data()
    lines = [
        f"Config Desktop : {'encontrado' if d['config_found'] else 'NO encontrado'}",
        f"Ruta           : {d['config_path'] or '(desconocida)'}",
        f"Bypass activo  : {'SI' if d['is_proxied'] else 'no'}",
        f"API base_url   : {d['api_base_url'] or '(sin definir)'}",
        f"Respaldo .bak  : {'si' if d['backup_exists'] else 'no'}",
    ]
    if d.get("proxy_addr"):
        lines.append(f"Proxy guardado : {d['proxy_addr']}")
    return "\n".join(lines)


def _wait_server(seconds=12):
    deadline = time.time() + seconds
    while time.time() < deadline:
        if dashboard_running():
            return True
        time.sleep(0.4)
    return False


def setup_desktop():
    """
    Bypass INTELIGENTE: si el dashboard esta activo usa la API (aplicacion
    inmediata); si no, lo arranca, espera y aplica por API; si nada funciona,
    cae al CLI. Devuelve (ok, mensaje detallado).
    """
    if not has_engine() and not dashboard_running():
        return False, ("No hay motor Oplire ni dashboard activo. "
                       "Compila/instala Oplire o inicia el Dashboard primero.")
    started = False
    if not dashboard_running():
        start_dashboard()
        started = _wait_server(12)
    if dashboard_running():
        ok, data = api_post("/api/setup-desktop", timeout=45)
        if ok:
            msg = "Bypass aplicado por la API de Oplire."
            if started:
                msg += " (el dashboard se inicio automaticamente)"
            return True, msg + "\n" + desktop_report()
    rc, out = run_cli(["setup-desktop"], timeout=60)
    if rc == 0:
        return True, "Bypass aplicado por CLI.\n" + (out or "").strip() + "\n" + desktop_report()
    return False, ("No se pudo aplicar el bypass.\n"
                   f"API: {_json_text(data) if 'data' in locals() else 'sin respuesta'}\n"
                   f"CLI: {out or 'sin salida'}")


def restore_desktop():
    """Restaura la config original. API si esta disponible; si no, CLI."""
    if dashboard_running():
        ok, data = api_post("/api/restore-desktop", timeout=45)
        if ok:
            return True, "Bypass restaurado por la API de Oplire.\n" + desktop_report()
    rc, out = run_cli(["restore-desktop"], timeout=60)
    if rc == 0:
        return True, "Bypass restaurado por CLI.\n" + (out or "").strip() + "\n" + desktop_report()
    return False, f"No se pudo restaurar el bypass: {out or 'sin salida'}"


def desktop_status():
    """Estado del bypass de Desktop (CLI, solo para diagnostico manual)."""
    return run_cli(["desktop-status"], timeout=30)


# ======================================================== cache / vcache ====

def opencode_folders():
    """
    Deteccion en TIEMPO REAL de las carpetas de OpenCode.
    Se recalculan cada vez para reflejar cambios inmediatos.
    """
    home = C.user_home()
    local = os.environ.get("LOCALAPPDATA", "")
    xdg_config = os.environ.get("XDG_CONFIG_HOME", "") or os.path.join(home, ".config")
    xdg_cache = os.environ.get("XDG_CACHE_HOME", "") or os.path.join(home, ".cache")
    xdg_data = os.environ.get("XDG_DATA_HOME", "") or os.path.join(home, ".local", "share")

    candidates = [
        ("Configuracion", os.path.join(xdg_config, "opencode")),
        ("Cache (vcache)", os.path.join(xdg_cache, "opencode")),
        ("Datos", os.path.join(xdg_data, "opencode")),
    ]
    if local:
        candidates.append(("Datos (LocalAppData)", os.path.join(local, "opencode")))
    appdata = os.environ.get("APPDATA", "")
    if appdata:
        candidates.append(("Configuracion (AppData)", os.path.join(appdata, "opencode")))

    seen, result = set(), []
    for name, path in candidates:
        key = os.path.normcase(os.path.abspath(path))
        if key in seen:
            continue
        seen.add(key)
        exists = os.path.isdir(path)
        result.append({
            "name": name,
            "path": path,
            "exists": exists,
            "size": C.dir_size(path) if exists else 0,
            "size_h": C.human_size(C.dir_size(path)) if exists else "0 B",
        })
    return result


def find_vcache():
    """
    Localiza en tiempo real todas las carpetas de OpenCode.
    Cada item incluye 'kind': 'cache' (caché real) o 'data' (datos).
    Devuelve (lista, total_bytes).
    """
    home = C.user_home()
    local = os.environ.get("LOCALAPPDATA", "")
    roots = [
        ("cache", os.path.join(home, ".cache", "opencode")),
        ("data", os.path.join(home, ".local", "share", "opencode")),
    ]
    if local:
        roots.append(("data", os.path.join(local, "opencode")))
    xdg_cache = os.environ.get("XDG_CACHE_HOME", "")
    if xdg_cache:
        roots.append(("cache", os.path.join(xdg_cache, "opencode")))

    seen, items, total = set(), [], 0
    for kind, r in roots:
        key = os.path.normcase(os.path.abspath(r))
        if key in seen:
            continue
        seen.add(key)
        if not os.path.isdir(r):
            continue
        size = C.dir_size(r)
        total += size
        items.append({"path": r, "size": size, "size_h": C.human_size(size), "kind": kind})
    return items, total


def _safe_remove(path, protect_antigravity=True):
    """Elimina una carpeta, protegiendo archivos/carpetas con 'antigravity'."""
    if not path or not os.path.exists(path):
        return False, "no existe"
    if "antigravity" in os.path.basename(path).lower():
        return False, "protegido (antigravity)"
    try:
        if os.path.isdir(path):
            if protect_antigravity:
                for entry in os.listdir(path):
                    low = entry.lower()
                    if ("antigravity" in low or low in ("auth.json", "credentials.json")
                            or low.startswith("account")):
                        continue
                    full = os.path.join(path, entry)
                    if os.path.isdir(full):
                        shutil.rmtree(full, ignore_errors=True)
                    else:
                        try:
                            os.remove(full)
                        except OSError:
                            pass
            else:
                shutil.rmtree(path, ignore_errors=True)
        else:
            os.remove(path)
        return True, "ok"
    except Exception as e:
        return False, str(e)


def clear_cache():
    """
    Limpia SOLO la cache de OpenCode (no datos, no configuracion, no cuentas).
    Devuelve (ok, mensaje).
    """
    items, _total = find_vcache()
    cache_items = [it for it in items if it.get("kind") == "cache"]
    if not cache_items:
        return True, "No hay carpetas de cache que limpiar."
    removed = 0
    freed = 0
    for it in cache_items:
        ok, msg = _safe_remove(it["path"], protect_antigravity=True)
        if ok:
            removed += 1
            freed += it["size"]
    if removed:
        return True, (f"Cache limpiada en {removed} carpeta(s). "
                      f"Liberado aprox. {C.human_size(freed)}.")
    return False, "No se pudo limpiar la cache (permisos o uso activo)."


def clear_all_data():
    """
    Borra cache + datos de OpenCode (protege Antigravity).
    No toca la configuracion ni las cuentas.
    """
    items, _total = find_vcache()
    if not items:
        return True, "No hay datos que borrar."
    removed = 0
    freed = 0
    for it in items:
        if "config" in it["path"].lower():
            continue
        ok, msg = _safe_remove(it["path"], protect_antigravity=True)
        if ok:
            removed += 1
            freed += it["size"]
    if removed:
        return True, (f"Datos borrados en {removed} carpeta(s). "
                      f"Liberado aprox. {C.human_size(freed)}. Antigravity protegido.")
    return False, "No se pudo borrar (archivos en uso)."


def opencode_config_dir():
    """Carpeta de configuracion de OpenCode."""
    env_dir = os.environ.get("OPENCODE_CONFIG_DIR", "")
    if env_dir and os.path.isdir(env_dir):
        return os.path.abspath(env_dir)
    home = C.user_home()
    xdg = os.environ.get("XDG_CONFIG_HOME", "")
    cands = []
    if xdg:
        cands.append(os.path.join(xdg, "opencode"))
    cands.append(os.path.join(home, ".config", "opencode"))
    appdata = os.environ.get("APPDATA", "")
    if appdata:
        cands.append(os.path.join(appdata, "opencode"))
    for c in cands:
        if os.path.isdir(c):
            return c
    return cands[0]


def _config_entry_protected(name):
    """Protege lo critico: config principal y todo lo de Antigravity."""
    low = name.lower()
    if "antigravity" in low:
        return True
    if low in ("opencode.json", "opencode.jsonc", "opencode.json.bak"):
        return True
    return low.startswith("opencode.json.bak-")


def clear_config():
    """
    Limpia la carpeta de configuracion de OpenCode conservando lo critico
    (opencode.json/jsonc y los archivos de Antigravity: cuentas y plugin).
    Devuelve (ok, mensaje).
    """
    cfg = opencode_config_dir()
    if not os.path.isdir(cfg):
        return True, "No hay carpeta de configuracion que limpiar."
    removed = 0
    kept = 0
    for entry in os.listdir(cfg):
        if _config_entry_protected(entry):
            kept += 1
            continue
        full = os.path.join(cfg, entry)
        try:
            if os.path.isdir(full):
                shutil.rmtree(full, ignore_errors=True)
            else:
                os.remove(full)
            removed += 1
        except OSError:
            pass
    if removed:
        return True, (f"Configuracion limpiada en {cfg}. "
                      f"{removed} elemento(s) eliminado(s); {kept} critico(s) conservado(s).")
    return True, f"Configuracion ya limpia (nada que borrar); {kept} critico(s) conservado(s)."


# ============================================================ sesiones ======

def fix_sessions():
    """Repara sesiones corruptas. El CLI pregunta por stdin, enviamos 'y'."""
    exe = find_oplire_exe()
    if not exe:
        return -1, "oplire.exe no encontrado"
    import subprocess
    try:
        r = subprocess.run(
            [exe, "fix-sessions"],
            input="y\n", capture_output=True, text=True, timeout=120,
            cwd=oplire_dir(),
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            encoding="utf-8", errors="replace",
        )
        return r.returncode, C.strip_ansi((r.stdout or "") + (r.stderr or "")).strip()
    except Exception as e:
        return -1, str(e)


def sessions_status():
    return run_cli(["sessions-status"], timeout=60)


def sessions_list():
    return run_cli(["sessions-list"], timeout=60)


def session_detail(session_id):
    args = ["session-detail"]
    if session_id:
        args += ["--id", str(session_id)]
    return run_cli(args, timeout=30)


# ================================== backup de contexto / sesiones (vCache) ===

def session_sources():
    """
    Carpetas que contienen el CONTEXTO de chat y las sesiones:
      * sesiones de OpenCode (varias ubicaciones posibles)
      * almacenamiento de OpenCode (storage: mensajes, partes, diffs)
      * sesiones de Oplire (guard_state.json)
    Devuelve [(label, path, exists)] en tiempo real.
    """
    home = C.user_home()
    appdata = os.environ.get("APPDATA", "")
    local = os.environ.get("LOCALAPPDATA", "")
    xdg_data = os.environ.get("XDG_DATA_HOME", "") or os.path.join(home, ".local", "share")
    cands = []
    if appdata:
        cands += [
            ("OpenCode sesiones (Roaming)", os.path.join(appdata, "opencode", "sessions")),
            ("OpenCode storage (Roaming)", os.path.join(appdata, "opencode", "storage")),
        ]
    if local:
        cands += [
            ("OpenCode sesiones (Local)", os.path.join(local, "opencode", "sessions")),
            ("OpenCode storage (Local)", os.path.join(local, "opencode", "storage")),
            ("Oplire sesiones", os.path.join(local, "oplire", "sessions")),
        ]
    cands += [
        ("OpenCode sesiones (~/.opencode)", os.path.join(home, ".opencode", "sessions")),
        ("OpenCode sesiones (~/.config)", os.path.join(home, ".config", "opencode", "sessions")),
        ("OpenCode storage (XDG data)", os.path.join(xdg_data, "opencode", "storage")),
    ]
    seen, out = set(), []
    for label, path in cands:
        key = os.path.normcase(os.path.abspath(path))
        if key in seen:
            continue
        seen.add(key)
        out.append((label, path, os.path.isdir(path)))
    return out


def sessions_backup_root():
    local = os.environ.get("LOCALAPPDATA") or os.path.join(C.user_home(), ".local", "share")
    return os.path.join(local, "Nexus", "backups", "sessions")


def create_sessions_backup(note=""):
    """
    Copia REAL del contexto de chat (sesiones + storage) a una carpeta con
    fecha. Devuelve (ok, mensaje). No borra ni modifica nada del original.
    """
    sources = [s for s in session_sources() if s[2]]
    if not sources:
        return False, ("No se encontro ninguna carpeta de sesiones de OpenCode/Oplire. "
                       "Abre OpenCode al menos una vez para que se cree.")
    stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    root = sessions_backup_root()
    dest_root = os.path.join(root, stamp)
    try:
        os.makedirs(dest_root, exist_ok=True)
    except OSError as e:
        return False, f"No se pudo crear la carpeta de backup: {e}"
    manifest = {
        "created": stamp,
        "note": note or "",
        "sources": [],
        "nexus_version": C.APP_VERSION,
    }
    total_files = 0
    errors = []
    for idx, (label, path, _exists) in enumerate(sources, 1):
        dest = os.path.join(dest_root, f"{idx:02d}-{_safe_name(label)}")
        try:
            shutil.copytree(path, dest, dirs_exist_ok=True,
                            ignore_dangling_symlinks=True)
            files = sum(len(fs) for _r, _d, fs in os.walk(dest))
            total_files += files
            manifest["sources"].append({
                "label": label, "origin": path, "copy": dest, "files": files,
                "size": C.dir_size(dest),
            })
        except Exception as e:
            errors.append(f"{label}: {e}")
    try:
        with open(os.path.join(dest_root, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
    except OSError as e:
        errors.append(f"manifest: {e}")
    size = C.dir_size(dest_root)
    if not manifest["sources"]:
        return False, "No se pudo copiar ninguna sesion:\n" + "\n".join(errors)
    msg = (f"Backup de contexto creado: {dest_root}\n"
           f"{len(manifest['sources'])} carpeta(s), {total_files} archivo(s), "
           f"{C.human_size(size)}.")
    if errors:
        msg += "\nAvisos:\n" + "\n".join(errors)
    return True, msg


def _safe_name(text):
    keep = "-_()[] ."
    return "".join(ch if ch.isalnum() or ch in keep else "_" for ch in text).strip(" ._") or "item"


def list_sessions_backups():
    """Lista backups con metadatos reales (fecha, tamano, carpetas, nota)."""
    root = sessions_backup_root()
    out = []
    try:
        names = sorted(os.listdir(root), reverse=True)
    except OSError:
        return out
    for name in names:
        path = os.path.join(root, name)
        if not os.path.isdir(path):
            continue
        manifest = {}
        mpath = os.path.join(path, "manifest.json")
        try:
            with open(mpath, "r", encoding="utf-8") as f:
                manifest = json.load(f)
        except (OSError, ValueError):
            pass
        out.append({
            "name": name,
            "path": path,
            "note": manifest.get("note", ""),
            "sources": manifest.get("sources", []),
            "created": manifest.get("created", name),
            "size": C.dir_size(path),
            "size_h": C.human_size(C.dir_size(path)),
        })
    return out


def restore_sessions_backup(name):
    """
    Restaura un backup sobre las carpetas originales (merge, sin borrar).
    Antes crea un backup de seguridad del estado actual.
    """
    back = None
    for b in list_sessions_backups():
        if b["name"] == name or b["path"] == name:
            back = b
            break
    if not back:
        return False, f"Backup no encontrado: {name}"
    sources = back.get("sources") or []
    if not sources:
        return False, "El backup no tiene manifiesto de origenes; no se puede restaurar."
    ok_safety, msg_safety = create_sessions_backup("Auto-backup antes de restaurar")
    errors = []
    restored = 0
    for item in sources:
        origin = item.get("origin")
        copy = item.get("copy")
        if not origin or not copy or not os.path.isdir(copy):
            errors.append(f"{item.get('label', '?')}: copia ausente")
            continue
        try:
            os.makedirs(origin, exist_ok=True)
            shutil.copytree(copy, origin, dirs_exist_ok=True,
                            ignore_dangling_symlinks=True)
            restored += 1
        except Exception as e:
            errors.append(f"{item.get('label', '?')}: {e}")
    msg = f"Restauradas {restored}/{len(sources)} carpeta(s) desde {back['name']}."
    if ok_safety:
        msg += "\n" + msg_safety
    else:
        msg += f"\n[!] No se pudo crear el backup de seguridad: {msg_safety}"
    if errors:
        msg += "\nAvisos:\n" + "\n".join(errors)
    return restored > 0, msg


def delete_sessions_backup(name):
    for b in list_sessions_backups():
        if b["name"] == name:
            try:
                shutil.rmtree(b["path"])
                return True, f"Backup eliminado: {b['name']}"
            except OSError as e:
                return False, f"No se pudo eliminar el backup: {e}"
    return False, "Backup no encontrado."


def open_backups_folder():
    root = sessions_backup_root()
    try:
        os.makedirs(root, exist_ok=True)
    except OSError:
        pass
    return C.open_path(root)


# ======================================================== diagnostico =======

def doctor():
    return run_cli(["doctor"], timeout=90)


def models():
    return run_cli(["models"], timeout=60)


def install(target):
    """target: warp | opencode | claude-code | all"""
    return run_cli(["install", target], timeout=900)


def about():
    return run_cli(["about"], timeout=20)


def version():
    return run_cli(["--version"], timeout=20)


def config_show():
    return run_cli(["config", "show"], timeout=30)


def connect(target="claude-code"):
    """target: claude-code | desktop. Enruta la herramienta por el proxy."""
    return run_cli(["connect", target], timeout=90)


def watch():
    """Monitor de sesiones en tiempo real (proceso persistente -> consola)."""
    return run_cli_console(["watch"], title="Oplire Watch")
