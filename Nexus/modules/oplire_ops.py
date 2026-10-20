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
import shutil

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
    # 1) Modo desarrollo: binario compilado en la carpeta del proyecto.
    folder = oplire_dir()
    for sub in (("target", "release"), ("target", "debug"), ()):
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

def run_cli(args, timeout=120, verbose=False):
    """Ejecuta 'oplire <args>'. Devuelve (rc, salida_limpia)."""
    exe = find_oplire_exe()
    if not exe:
        return -1, ("[ERROR] oplire.exe no encontrado.\n"
                    f"       Ubicacion esperada: {os.path.join(oplire_dir(), 'target', 'release', 'oplire.exe')}\n"
                    "       Compila el motor con: build.ps1 -Release")
    cmd = [exe] + list(args)
    if verbose and "-v" not in cmd and "--verbose" not in cmd:
        cmd.append("-v")
    rc, out = C.run_cmd(cmd, timeout=timeout, cwd=oplire_dir())
    return rc, C.strip_ansi(out).strip()


def run_cli_console(args, title="Oplire"):
    exe = find_oplire_exe()
    if not exe:
        return False
    return C.open_new_console([exe] + list(args), cwd=oplire_dir(), title=title)


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
    """Ruta al comando 'opencode' (cmd/ps1/exe), o None si no esta en el PATH."""
    for name in ("opencode", "opencode.cmd", "opencode.exe", "opencode.ps1", "opencode.bat"):
        p = C.which(name)
        if p:
            return p
    return None


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


# ======================================================== desktop bypass =====

def setup_desktop():
    """Activa el bypass de OpenCode Desktop (via CLI)."""
    return run_cli(["setup-desktop"], timeout=60)


def restore_desktop():
    """Restaura la config original de Desktop (via CLI)."""
    return run_cli(["restore-desktop"], timeout=60)


def desktop_status():
    """Estado del bypass de Desktop (via CLI)."""
    return run_cli(["desktop-status"], timeout=30)


def desktop_status_data():
    """
    Estado del bypass como dict. Prefiere la API si el dashboard esta arriba,
    si no usa el CLI y parsea el texto.
    """
    if dashboard_running():
        ok, data = api_desktop_status()
        if ok and isinstance(data, dict):
            return {
                "config_found": data.get("config_found"),
                "config_path": data.get("config_path"),
                "is_proxied": data.get("is_proxied"),
                "api_base_url": data.get("api_base_url"),
                "backup_exists": data.get("backup_exists"),
                "source": "api",
            }
    rc, out = desktop_status()
    data = {"source": "cli", "raw": out}
    low = (out or "").lower()
    data["config_found"] = "no encontrado" not in low and "not found" not in low and rc == 0
    data["is_proxied"] = ("proxy" in low and "activo" in low) or "bypass: activo" in low or "__oplire_bypass_active__" in (out or "")
    data["backup_exists"] = "respaldo" in low or "backup" in low
    return data


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
                    if "antigravity" in entry.lower():
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
