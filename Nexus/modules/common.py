# -*- coding: utf-8 -*-
"""
NEXUS Suite - common
====================
Utilidades compartidas por todos los modulos.

  * Reconocimiento del equipo (OS, CPU, RAM, disco, usuario, host).
  * Resolucion de rutas (portable: funciona en cualquier PC).
  * Ejecucion de procesos y consolas.
  * Cliente HTTP minimo (stdlib) para la API del dashboard Oplire.
  * Helpers de formato (tamano, ansi, etc.).

Sin dependencias externas: solo biblioteca estandar.
"""

import io
import os
import re
import sys
import json
import time
import ctypes
import socket
import platform
import getpass
import shutil
import datetime
import subprocess
import urllib.error
import urllib.request

APP_NAME = "NEXUS Suite"
APP_VERSION = "7.3.1"

OPLIRE_ENGINE = "oplire"
ANTIGRAVITY_ENGINE = "antigravity"
CLAUDE_ENGINE = "claude"

# Documentacion de las variables de entorno que gestiona NEXUS.
# Cada entrada: (para que sirve, valor recomendado, alcance)
ENV_HELP = {
    "OPENCODE_EXPERIMENTAL_OUTPUT_TOKEN_MAX": (
        "Amplia el limite maximo de tokens de SALIDA por respuesta de OpenCode "
        "(por defecto el motor aplica un tope conservador). 512000 permite "
        "respuestas largas (codigo, informes) sin truncarlas. Solo afecta a "
        "OpenCode y a los procesos nuevos que se abran tras aplicarla.",
        "512000",
        "OpenCode",
    ),
    "OPENCODE_CONFIG_DIR": (
        "Fuerza la carpeta de configuracion de OpenCode (cuentas, plugin y "
        "opencode.json). Util si usas una configuracion portable.",
        "",
        "OpenCode",
    ),
    "OPENCODE_BIN": (
        "Ruta explicita al ejecutable de OpenCode. NEXUS lo detecta aqui si no "
        "esta en el PATH.",
        "",
        "OpenCode",
    ),
    "NEXUS_OPENCODE": (
        "Ruta alternativa al ejecutable de OpenCode usada por NEXUS para "
        "detectarlo sin depender del PATH.",
        "",
        "NEXUS",
    ),
    "OPLIRE_PROJECT_PATH": (
        "Ruta a la carpeta del motor Oplire. Permite ubicarlo cuando NEXUS se "
        "ejecuta desde otra unidad o carpeta.",
        "",
        "Oplire",
    ),
    "ANTIGRAVITY_PROJECT_PATH": (
        "Ruta a la carpeta del plugin Antigravity. Permite ubicarlo cuando "
        "NEXUS se ejecuta desde otra unidad o carpeta.",
        "",
        "Antigravity",
    ),
    "GOOGLE_GENERATIVE_AI_API_KEY": (
        "API key de Google AI Studio. Se usa cuando el plugin Antigravity esta "
        "desactivado (modelos gemini-*). Persiste para procesos nuevos.",
        "",
        "Antigravity",
    ),
    "GEMINI_API_KEY": (
        "Alias de la API key de Google usada por la CLI de Gemini y por Free "
        "Claude Code para el proveedor Gemini.",
        "",
        "Compartida",
    ),
    "NO_PROXY": (
        "Lista de hosts que NO deben pasar por el proxy (separados por coma). "
        "Incluye 127.0.0.1,localhost para que el dashboard y OpenCode local "
        "nunca se enruten a traves del proxy.",
        "127.0.0.1,localhost",
        "Red",
    ),
}

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


# --------------------------------------------------------------- rutas -----

def get_base_dir():
    """Carpeta base de la aplicacion (soporta ejecucion como .exe)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def candidate_bases():
    """Posibles ubicaciones de la carpeta 'Nexus' con los motores."""
    base = get_base_dir()
    raw = [
        base,
        os.path.join(base, "Nexus"),
        os.path.join(os.path.dirname(base), "Nexus"),
    ]
    seen, out = set(), []
    for c in raw:
        c = os.path.abspath(c)
        key = os.path.normcase(c)
        if key not in seen:
            seen.add(key)
            out.append(c)
    return out


def resolve_engine_dir(name):
    """Localiza la carpeta de un motor (oplire/antigravity) de forma portable."""
    env_key = {
        OPLIRE_ENGINE: "OPLIRE_PROJECT_PATH",
        ANTIGRAVITY_ENGINE: "ANTIGRAVITY_PROJECT_PATH",
        CLAUDE_ENGINE: "CLAUDE_PROJECT_PATH",
    }.get(name, "")
    if env_key:
        env = os.environ.get(env_key, "")
        if env and os.path.isdir(env):
            return os.path.abspath(env)
    for cand in candidate_bases():
        p = os.path.join(cand, name)
        if os.path.isdir(p):
            return p
    return os.path.join(get_base_dir(), name)


def oplire_dir():
    return resolve_engine_dir(OPLIRE_ENGINE)


def antigravity_dir():
    d = resolve_engine_dir(ANTIGRAVITY_ENGINE)
    return d if os.path.isdir(d) else ""


def _is_fcc_project(path):
    """True solo si la carpeta contiene el pyproject real de Free Claude Code."""
    if not path or not os.path.isdir(path):
        return False
    pyproject = os.path.join(path, "pyproject.toml")
    if not os.path.isfile(pyproject):
        return False
    try:
        with open(pyproject, "r", encoding="utf-8", errors="ignore") as f:
            head = f.read(8192)
        return 'name = "free-claude-code"' in head or "free_claude_code" in head
    except OSError:
        return False


def claude_dir():
    """Carpeta REAL del proyecto Free Claude Code, o '' si no esta instalado."""
    candidates = []
    env = os.environ.get("CLAUDE_PROJECT_PATH", "").strip()
    if env:
        candidates.append(os.path.abspath(os.path.expanduser(env)))
    for base in candidate_bases():
        for sub in (
            ("claude",),
            ("claude", "free-claude-code"),
            ("claude", "free_claude_code"),
            ("Nexus", "claude"),
            ("Nexus", "claude", "free-claude-code"),
            ("free-claude-code",),
        ):
            candidates.append(os.path.join(base, *sub))
    seen = set()
    for cand in candidates:
        key = os.path.normcase(os.path.abspath(cand))
        if key in seen:
            continue
        seen.add(key)
        if _is_fcc_project(cand):
            return os.path.abspath(cand)
    # Ultimo recurso: un unico subdirectorio valido dentro de claude/.
    for base in candidate_bases():
        claude_root = os.path.join(base, "claude")
        try:
            entries = os.listdir(claude_root)
        except OSError:
            continue
        for entry in entries:
            cand = os.path.join(claude_root, entry)
            if _is_fcc_project(cand):
                return os.path.abspath(cand)
    return ""


def user_home():
    return (os.environ.get("USERPROFILE")
            or os.environ.get("HOME")
            or os.path.expanduser("~"))


# ------------------------------------------------------------ procesos -----

def which(name):
    try:
        return shutil.which(name)
    except Exception:
        return None


def tool_available(name):
    return which(name) is not None or bool(_which_ext(name))


def run_cmd(cmd, timeout=60, cwd=None, env=None):
    """Ejecuta un comando capturando salida. cmd puede ser lista o string."""
    try:
        r = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
            env=env,
            shell=isinstance(cmd, str),
            creationflags=_NO_WINDOW,
            encoding="utf-8",
            errors="replace",
        )
        out = (r.stdout or "")
        errtext = (r.stderr or "")
        combined = out + (("\n" + errtext) if errtext.strip() and errtext.strip() not in out else "")
        return r.returncode, combined
    except subprocess.TimeoutExpired:
        return -1, "[TIMEOUT] el comando excedio el limite de tiempo"
    except FileNotFoundError:
        return -1, "[NO ENCONTRADO] el ejecutable no existe"
    except Exception as e:  # pragma: no cover - defensivo
        return -1, f"[ERROR] {e}"


def open_new_console(cmd, cwd=None, title="NEXUS", env=None):
    """
    Abre una consola CMD nueva, VISIBLE y persistente (/k) ejecutando el comando.

    Importante: se usa CREATE_NEW_CONSOLE (no CREATE_NO_WINDOW). Con
    CREATE_NO_WINDOW + 'start' la ventana se creaba oculta (bug que hacia que
    Dashboard/OpenCode Local/Agregar cuenta parecieran 'no hacer nada').
    """
    if isinstance(cmd, (list, tuple)):
        inner = subprocess.list2cmdline([str(c) for c in cmd])
    else:
        inner = str(cmd)
    comspec = os.environ.get("ComSpec") or "cmd.exe"
    # 'title' fija el nombre de la ventana; '&' separa del comando real.
    line = f'{comspec} /k title {title} & {inner}'
    try:
        subprocess.Popen(line, cwd=cwd, env=env, creationflags=subprocess.CREATE_NEW_CONSOLE)
        return True
    except Exception:
        pass
    # Respaldo: usar el shell con 'start' (sin CREATE_NO_WINDOW para no ocultarla).
    try:
        subprocess.Popen(f'start "{title}" cmd /k {inner}', shell=True, cwd=cwd, env=env)
        return True
    except Exception:
        return False


def open_terminal(cwd=None, title="NEXUS Terminal"):
    """Abre una consola CMD interactiva en la carpeta indicada."""
    cwd = cwd or get_base_dir()
    try:
        cwd = os.path.abspath(cwd)
    except Exception:
        cwd = get_base_dir()
    if not os.path.isdir(cwd):
        cwd = get_base_dir()
    return open_new_console(f'cd /d "{cwd}"', cwd=cwd, title=title)


def open_path(path):
    """Abre una carpeta o archivo con la aplicacion predeterminada de Windows."""
    try:
        target = os.path.abspath(os.path.expanduser(path))
    except Exception:
        target = path
    if not os.path.exists(target):
        return False
    try:
        os.startfile(target)
        return True
    except Exception:
        try:
            subprocess.Popen(["explorer", target])
            return True
        except Exception:
            return False


def kill_process(image_name):
    """Termina todos los procesos con ese nombre (Windows taskkill)."""
    if is_protected_process(image_name):
        return 1, (f"[PROTEGIDO] '{image_name}' esta en la lista de procesos protegidos "
                   f"(Docker/WSL/DB/red). No se detiene.")
    return run_cmd(["taskkill", "/F", "/IM", image_name], timeout=15)


def process_running(image_name):
    if os.name == "nt":
        rc, out = run_cmd(["tasklist", "/FI", f"IMAGENAME eq {image_name}", "/NH"], timeout=10)
        return image_name.lower() in (out or "").lower()
    rc, out = run_cmd(["pgrep", "-f", image_name], timeout=10)
    return rc == 0 and bool(out.strip())


# ------------------------------------------------------------ permisos -----

def is_admin():
    if os.name != "nt":
        return hasattr(os, "geteuid") and os.geteuid() == 0
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def run_as_admin(extra_args=""):
    if os.name != "nt":
        return False
    try:
        if getattr(sys, "frozen", False):
            exe = sys.executable
            params = (extra_args or "").strip()
        else:
            exe = sys.executable
            script = os.path.abspath(sys.argv[0])
            params = f'"{script}" {extra_args}'.strip()
        ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, params, None, 1)
        return True
    except Exception:
        return False


# --------------------------------------------------------------- PATH ------

def get_user_path():
    """PATH del usuario guardado en HKCU\\Environment (texto tal cual)."""
    if os.name != "nt":
        return os.environ.get("PATH", "")
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
            value, _ = winreg.QueryValueEx(k, "Path")
            return value or ""
    except Exception:
        return os.environ.get("PATH", "")


def _broadcast_env_change():
    """Avisa a Windows de que cambio el entorno (para procesos nuevos)."""
    try:
        HWND_BROADCAST = 0xFFFF
        WM_SETTINGCHANGE = 0x001A
        SMTO_ABORTIFHUNG = 0x0002
        result = ctypes.c_long()
        ctypes.windll.user32.SendMessageTimeoutW(
            HWND_BROADCAST, WM_SETTINGCHANGE, 0,
            ctypes.c_wchar_p("Environment"), SMTO_ABORTIFHUNG, 5000,
            ctypes.byref(result))
    except Exception:
        pass


def set_user_path(value):
    if os.name != "nt":
        return False, "Solo disponible en Windows."
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0,
                            winreg.KEY_SET_VALUE) as k:
            winreg.SetValueEx(k, "Path", 0, winreg.REG_EXPAND_SZ, value or "")
        _broadcast_env_change()
        return True, "PATH de usuario actualizado."
    except Exception as e:
        return False, f"No se pudo actualizar el PATH: {e}"


def path_contains(folder):
    if not folder:
        return False
    try:
        target = os.path.normcase(os.path.normpath(folder))
    except Exception:
        return False
    for part in get_user_path().split(os.pathsep):
        part = part.strip().strip('"')
        if not part:
            continue
        try:
            if os.path.normcase(os.path.normpath(os.path.expandvars(part))) == target:
                return True
        except Exception:
            continue
    return False


def add_to_user_path(folder, prepend=False):
    """
    Anade una carpeta al PATH del usuario (persistente). Tambien al proceso.
    prepend=True la coloca AL PRINCIPIO para que sus ejecutables ganen en
    prioridad (util para npm/OpenCode cuando hay varias versiones).
    """
    folder = os.path.abspath(folder)
    if not os.path.isdir(folder):
        return False, f"La carpeta no existe: {folder}"
    if path_contains(folder):
        _ensure_process_path(folder)
        return True, "La carpeta ya estaba en el PATH."
    current = get_user_path().rstrip(os.pathsep)
    if prepend:
        new_value = (folder + os.pathsep + current) if current else folder
    else:
        new_value = (current + os.pathsep + folder) if current else folder
    ok, msg = set_user_path(new_value)
    if ok:
        _ensure_process_path(folder)
        return True, f"Anadido al PATH: {folder}" + (" (al principio)" if prepend else "")
    return False, msg


def _ensure_process_path(folder):
    """Refleja la carpeta en el PATH del proceso actual (deteccion inmediata)."""
    cur = os.environ.get("PATH", "")
    parts = [p for p in cur.split(os.pathsep) if p]
    norm = os.path.normcase(os.path.normpath(folder))
    if not any(os.path.normcase(os.path.normpath(p)) == norm for p in parts):
        os.environ["PATH"] = cur + (os.pathsep if cur else "") + folder


# -------------------------------------------------- variables de entorno ----

def get_user_env(name):
    """Lee una variable de entorno del usuario (HKCU\\Environment)."""
    if os.name != "nt":
        return os.environ.get(name)
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
            value, _ = winreg.QueryValueEx(k, name)
            return value
    except Exception:
        return None


def set_user_env(name, value, expand=False):
    """Crea/actualiza una variable de entorno del usuario (persistente)."""
    if os.name != "nt":
        return False, "Solo disponible en Windows."
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0,
                            winreg.KEY_SET_VALUE) as k:
            winreg.SetValueEx(k, name, 0,
                              winreg.REG_EXPAND_SZ if expand else winreg.REG_SZ,
                              str(value))
        _broadcast_env_change()
        os.environ[name] = str(value)
        return True, f"{name} = {value}"
    except Exception as e:
        return False, f"No se pudo crear la variable: {e}"


def delete_user_env(name):
    """Elimina una variable de entorno del usuario."""
    if os.name != "nt":
        return False, "Solo disponible en Windows."
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0,
                            winreg.KEY_SET_VALUE) as k:
            winreg.DeleteValue(k, name)
        _broadcast_env_change()
        os.environ.pop(name, None)
        return True, f"{name} eliminada."
    except FileNotFoundError:
        return True, f"{name} no existia."
    except Exception as e:
        return False, f"No se pudo eliminar: {e}"


def open_env_vars_dialog():
    """Abre directamente 'Variables de entorno' (sysdm.cpl, opciones avanzadas)."""
    if os.name != "nt":
        return False
    for args in (["rundll32.exe", "sysdm.cpl,EditEnvironmentVariables"],
                 ["sysdm.cpl"]):
        try:
            subprocess.Popen(args)
            return True
        except Exception:
            continue
    return False


def run_program(args, timeout=60, cwd=None, env=None):
    """Ejecuta un programa manejando .cmd/.bat en Windows."""
    if not args:
        return -1, "[ERROR] comando vacio"
    exe = str(args[0])
    if os.name == "nt" and exe.lower().endswith((".cmd", ".bat")):
        line = subprocess.list2cmdline([str(a) for a in args])
        return run_cmd(line, timeout=timeout, cwd=cwd, env=env)
    return run_cmd(list(args), timeout=timeout, cwd=cwd, env=env)


# --------------------------------------------------------------- disco -----

def human_size(num):
    try:
        num = float(num)
    except (TypeError, ValueError):
        return "?"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(num) < 1024.0:
            return f"{num:3.1f} {unit}".strip()
        num /= 1024.0
    return f"{num:.1f} PB"


def dir_size(path):
    """Tamano total de una carpeta en bytes (tolerante a errores)."""
    total = 0
    if not path or not os.path.isdir(path):
        return 0
    for dirpath, _dirs, files in os.walk(path, onerror=lambda e: None):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(dirpath, f))
            except OSError:
                continue
    return total


def strip_ansi(text):
    if not text:
        return ""
    return _ANSI_RE.sub("", text)


# --------------------------------------------------------- equipo/sistema ---

class _MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


def memory_info():
    """Devuelve (total, disponible) en bytes. Portable con fallback."""
    if os.name == "nt":
        try:
            stat = _MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(_MEMORYSTATUSEX)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
            return int(stat.ullTotalPhys), int(stat.ullAvailPhys)
        except Exception:
            pass
    try:
        if hasattr(os, "sysconf"):
            total = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
            avail = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_AVPHYS_PAGES")
            return int(total), int(avail)
    except Exception:
        pass
    return 0, 0


def _os_pretty():
    """Nombre comercial del sistema (Windows 11/10, build) sin dependencias."""
    if os.name != "nt":
        return f"{platform.system()} {platform.release()}"
    try:
        edition = platform.win32_edition()
    except Exception:
        edition = ""
    rel = platform.release()
    build = platform.version().split(".")[-1] if platform.version() else ""
    # Windows 11 comparte "10" en platform.release(); el build lo distingue.
    if rel == "10":
        try:
            if int(build) >= 22000:
                rel = "11"
        except (TypeError, ValueError):
            pass
    label = f"Windows {rel}"
    if edition:
        label += f" {edition}"
    if build:
        label += f" (build {build})"
    return label


def _cpu_name():
    if os.name == "nt":
        try:
            import winreg
            key = r"HARDWARE\DESCRIPTION\System\CentralProcessor\0"
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key) as k:
                name, _ = winreg.QueryValueEx(k, "ProcessorNameString")
                if name:
                    return str(name).strip()
        except Exception:
            pass
    return platform.processor() or "?"


def _uptime_seconds():
    if os.name == "nt":
        try:
            return int(ctypes.windll.kernel32.GetTickCount64() / 1000)
        except Exception:
            pass
    try:
        with open("/proc/uptime", "r", encoding="utf-8") as f:
            return int(float(f.read().split()[0]))
    except Exception:
        return 0


def human_uptime(seconds):
    try:
        seconds = int(seconds)
    except (TypeError, ValueError):
        return "?"
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    mins, _ = divmod(rem, 60)
    if days:
        return f"{days}d {hours}h {mins}m"
    if hours:
        return f"{hours}h {mins}m"
    return f"{mins}m"


def local_ip():
    """IP local preferida (no envia trafico real: UDP connect sin datos)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        pass
    try:
        return socket.gethostbyname(socket.gethostname())
    except Exception:
        return ""


def is_private_ip(ip):
    try:
        parts = [int(p) for p in str(ip).split(".")]
        if len(parts) != 4:
            return None
        a, b = parts[0], parts[1]
        if a == 10 or (a == 172 and 16 <= b <= 31) or (a == 192 and b == 168):
            return True
        if a == 127:
            return True
        if a == 169 and b == 254:
            return True
        return False
    except Exception:
        return None


def public_ip(timeout=4):
    """IP publica (salida a internet). Devuelve '' si no hay conexion."""
    for url in ("https://api.ipify.org", "https://ifconfig.me/ip"):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "NEXUS-Suite"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                value = r.read(64).decode("ascii", "ignore").strip()
            if value and len(value) <= 45:
                return value
        except Exception:
            continue
    return ""


_NET_CACHE = {"ts": 0.0, "data": None}


def network_info(ttl=15):
    """
    Red del equipo en tiempo real: IP local, IP publica, tipo de red
    (privada/publica), adaptadores activos, puerta de enlace y conectividad.
    Portable: si no hay PowerShell o falla, devuelve lo basico sin romper la UI.
    Cache breve (ttl) para no lanzar PowerShell en cada refresco.
    """
    cached = _NET_CACHE.get("data")
    if cached and (time.time() - _NET_CACHE.get("ts", 0)) < ttl:
        return cached
    ip = local_ip()
    info = {
        "local_ip": ip or "no detectada",
        "public_ip": "",
        "private": is_private_ip(ip) if ip else None,
        "hostname": socket.gethostname(),
        "gateway": "",
        "adapters": [],
        "dns": "",
        "internet": None,
    }
    if os.name == "nt":
        ps = (
            "$ErrorActionPreference='SilentlyContinue';"
            "$cfg = Get-NetIPConfiguration | Where-Object {$_.IPv4Address} | "
            "Select-Object InterfaceAlias,InterfaceDescription,@{n='ip';e={$_.IPv4Address.IPAddress}},"
            "@{n='gw';e={$_.IPv4DefaultGateway.NextHop}};"
            "$prof = Get-NetConnectionProfile | Select-Object Name,InterfaceAlias,NetworkCategory;"
            "@{cfg=@($cfg);prof=@($prof);dns=(Get-DnsClientServerAddress -AddressFamily IPv4 | "
            "Where-Object {$_.ServerAddresses} | Select-Object -First 1 -ExpandProperty ServerAddresses)} | "
            "ConvertTo-Json -Depth 4 -Compress"
        )
        rc, out = run_cmd(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps], timeout=20)
        if rc == 0 and out.strip():
            try:
                data = json.loads(out.strip())
                cfg = data.get("cfg") or []
                prof = data.get("prof") or []
                if isinstance(cfg, dict):
                    cfg = [cfg]
                if isinstance(prof, dict):
                    prof = [prof]
                cat = {p.get("InterfaceAlias"): p.get("NetworkCategory") for p in prof if isinstance(p, dict)}
                for c in cfg:
                    if not isinstance(c, dict) or not c.get("ip"):
                        continue
                    alias = c.get("InterfaceAlias") or "?"
                    info["adapters"].append({
                        "alias": alias,
                        "description": c.get("InterfaceDescription") or "",
                        "ip": c.get("ip"),
                        "gateway": c.get("gw") or "",
                        "category": cat.get(alias, ""),
                    })
                    if not info["gateway"] and c.get("gw"):
                        info["gateway"] = c.get("gw")
                dns = data.get("dns")
                if isinstance(dns, list):
                    dns = ", ".join(str(d) for d in dns)
                info["dns"] = dns or ""
            except (ValueError, TypeError):
                pass
        if not info["adapters"]:
            rc, out = run_cmd(["ipconfig"], timeout=15)
            if rc == 0:
                info["adapters"].append({"alias": "ipconfig", "description": out.strip()[:1200],
                                         "ip": ip, "gateway": "", "category": ""})
    try:
        info["internet"] = port_open("1.1.1.1", 443, timeout=0.4) or port_open("8.8.8.8", 53, timeout=0.4)
    except Exception:
        info["internet"] = None
    if info["internet"]:
        info["public_ip"] = public_ip()
    _NET_CACHE["data"] = info
    _NET_CACHE["ts"] = time.time()
    return info


def system_info():
    """Reconocimiento completo del equipo (para adaptarse a cualquier PC)."""
    info = {
        "os": _os_pretty(),
        "os_version": platform.version(),
        "arch": platform.machine() or platform.processor() or "?",
        "host": socket.gethostname(),
        "user": getpass.getuser(),
        "python": platform.python_version(),
        "python_exe": sys.executable,
        "cpu": _cpu_name(),
        "cores": os.cpu_count() or 0,
        "uptime": 0,
        "ram_total": 0,
        "ram_free": 0,
        "disk_total": 0,
        "disk_free": 0,
        "admin": is_admin(),
        "base": get_base_dir(),
    }
    try:
        info["ram_total"], info["ram_free"] = memory_info()
    except Exception:
        pass
    try:
        info["uptime"] = _uptime_seconds()
    except Exception:
        pass
    try:
        usage = shutil.disk_usage(get_base_dir())
        info["disk_total"] = usage.total
        info["disk_free"] = usage.free
    except Exception:
        pass
    try:
        if os.name == "nt":
            info["gpu"] = _windows_gpu()
    except Exception:
        pass
    try:
        info["local_ip"] = local_ip()
    except Exception:
        info["local_ip"] = ""
    return info


_GPU_CACHE = {"done": False, "value": ""}


def _windows_gpu():
    if _GPU_CACHE["done"]:
        return _GPU_CACHE["value"]
    rc, out = run_cmd(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command",
         "Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name"],
        timeout=20,
    )
    if rc == 0 and out:
        names = [ln.strip() for ln in out.splitlines() if ln.strip()]
        if names:
            _GPU_CACHE["value"] = ", ".join(dict.fromkeys(names))[:160]
            _GPU_CACHE["done"] = True
            return _GPU_CACHE["value"]
    rc, out = run_cmd(["wmic", "path", "win32_videocontroller", "get", "name"], timeout=15)
    if rc == 0 and out:
        names = [ln.strip() for ln in out.splitlines() if ln.strip() and "Name" not in ln]
        if names:
            _GPU_CACHE["value"] = ", ".join(dict.fromkeys(names))[:160]
    _GPU_CACHE["done"] = True
    return _GPU_CACHE["value"]


def dependency_audit():
    """
    Auditoria universal de dependencias. Devuelve una lista de dicts con:
    name, ok, value, required, hint, group. Sirve para que Equipo/Doctor
    indiquen exactamente que falta y como resolverlo en cualquier PC.
    """
    checks = []

    def add(name, ok, value="", required=False, hint="", group="Sistema"):
        checks.append({"name": name, "ok": bool(ok), "value": value or "",
                       "required": bool(required), "hint": hint, "group": group})

    frozen = bool(getattr(sys, "frozen", False))
    add("Python", True,
        "incluido en Nexus.exe" if frozen else sys.version.split()[0],
        not frozen,
        ("Incluido en el ejecutable; no requiere instalacion." if frozen else
         "Necesario para ejecutar NEXUS en modo Python."), "Base")
    add("Node.js", tool_available("node"), _version_of("node"), True,
        "Requerido por OpenCode, Antigravity y Claude Code. https://nodejs.org", "Base")
    add("npm", tool_available("npm"), _version_of("npm"), True,
        "Gestor de paquetes de Node (viene con Node.js).", "Base")
    add("Git", tool_available("git"), _version_of("git"), False,
        "Util para clonar/actualizar proyectos. https://git-scm.com", "Base")
    add("uv", tool_available("uv"), _version_of("uv"), False,
        "Requerido por Free Claude Code. Instalalo desde la seccion Claude.", "Claude")
    oplire_engine = ""
    try:
        from . import oplire_ops as _op
        opencode_broken = _op.opencode_broken()
        oplire_engine = _op.find_oplire_exe() or ""
    except Exception:
        opencode_broken = False
    add("OpenCode", (tool_available("opencode") or bool(_which_ext("opencode")))
        and not opencode_broken,
        "DANADO (postinstall no ejecutado)" if opencode_broken else _version_of("opencode"),
        True,
        ("Herramientas > Reparar OpenCode (postinstall)." if opencode_broken else
         "Instalalo desde Herramientas > Instalar OpenCode (npm)."), "OpenCode")
    add("Oplire engine", bool(oplire_engine), oplire_engine or "no encontrado", False,
        "Copia oplire.exe a Nexus/oplire/dist/ o compilalo con build.ps1 -Release.", "OpenCode")
    add("Cloudflare WARP", tool_available("warp-cli"), _version_of("warp-cli"), False,
        "Necesario para rotar IP (Control de IP). https://1.1.1.1", "Red")
    add("Claude Code", tool_available("claude"), _version_of("claude"), False,
        "Instalalo desde Herramientas > Instalar Claude Code (npm).", "Claude")
    add("Free Claude Code", bool(claude_dir()), claude_dir() or "no encontrado", False,
        "Incluido en la carpeta Nexus/claude del proyecto.", "Claude")
    add("Antigravity", bool(antigravity_dir()), antigravity_dir() or "no encontrado", False,
        "Incluido en la carpeta antigravity/ del proyecto.", "Antigravity")
    add("Administrador", is_admin(), "SI" if is_admin() else "no", False,
        "Algunas operaciones de red y PATH requieren elevacion.", "Sistema")
    return checks


def _which_ext(name):
    """Busqueda ampliada para executables que no estan en el PATH."""
    try:
        from . import antigravity_ops as _ag  # import perezoso para evitar ciclos
        if name == "opencode":
            return _ag.get_opencode_path()
    except Exception:
        pass
    if name == "uv":
        home = os.path.expanduser("~")
        base = get_base_dir()
        for cand in (
            os.path.join(home, ".local", "bin", "uv.exe"),
            os.path.join(home, ".cargo", "bin", "uv.exe"),
            os.path.join(base, "tools", "uv.exe"),
            os.path.join(base, "Nexus", "tools", "uv.exe"),
        ):
            if os.path.isfile(cand):
                return cand
    return None


def _version_of(name):
    if not tool_available(name):
        return ""
    exe = which(name) or _which_ext(name) or name
    rc, out = run_program([exe, "--version"], timeout=10)
    if rc != 0:
        return ""
    line = (out or "").strip().splitlines()
    return line[0][:80] if line else ""


# ---------------------------------------------------------------- red ------

def port_open(host, port, timeout=0.2):
    try:
        with socket.create_connection((host, int(port)), timeout=timeout):
            return True
    except Exception:
        return False


# Procesos que NUNCA deben terminarse (contenedores/DB/red del usuario).
PROTECTED_PROCESSES = (
    "docker", "com.docker", "wslrelay", "wsl", "vpnkit", "docker-agent",
    "postgres", "postgresql", "mysql", "mariadb", "redis", "mongodb", "mongo",
    "nginx", "caddy", "java", "dotnet", "vmmem", "vmwp",
)


def process_image(pid):
    """Nombre de imagen (proceso) para un PID, o '' si no existe."""
    try:
        rc, out = run_cmd(["tasklist", "/FI", f"PID eq {int(pid)}", "/NH", "/FO", "CSV"], timeout=15)
    except Exception:
        return ""
    for line in (out or "").strip().splitlines():
        line = line.strip()
        if not line or line.upper().startswith("INFO:"):
            continue
        # formato CSV: "imagen.exe","PID",...
        return line.split('","')[0].strip().strip('"')
    return ""


def find_free_port(start=3005, end=3099):
    """Primer puerto libre en 127.0.0.1 dentro del rango, para evitar conflictos."""
    for p in range(int(start), int(end) + 1):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(("127.0.0.1", p))
            return p
        except OSError:
            continue
    return int(start)


def port_owner(port, fast=False):
    """
    Devuelve (pid, imagen) del proceso que ESCUCHA en ese puerto (Windows),
    o (None, None) si nadie escucha / no se puede determinar.

    fast=True usa SOLO netstat (rapido, sin PowerShell) para el refresco
    periodico; fast=False anade el respaldo PowerShell para maxima precision.
    """
    if os.name != "nt":
        return None, None
    port = int(port)
    needle = f":{port}"
    for attempt in range(3):
        rc, out = run_cmd(["netstat", "-ano", "-p", "TCP"], timeout=20)
        pid = None
        for line in (out or "").splitlines():
            parts = line.split()
            if (len(parts) >= 5 and parts[0].upper() == "TCP"
                    and parts[1].endswith(needle)
                    and parts[3].upper() in ("LISTENING", "ESCUCHANDO")):
                pid = parts[4]
                break
        if pid and pid.isdigit() and pid != "0":
            return int(pid), process_image(int(pid))
        if attempt < 2:
            time.sleep(0.15)
    if fast:
        return None, None
    pid = _listen_pid_powershell(port)
    if pid:
        return int(pid), process_image(int(pid))
    return None, None


def _listen_pid_powershell(port, attempts=3):
    """Respaldo: obtiene el PID real del socket en escucha via PowerShell.

    Get-NetTCPConnection ocasionalmente devuelve vacio (arranque en frio), por
    eso se reintenta unas cuantas veces.
    """
    ps = ("(Get-NetTCPConnection -LocalPort {} -State Listen "
          "-ErrorAction SilentlyContinue | Select-Object -First 1 "
          "-ExpandProperty OwningProcess)").format(int(port))
    for i in range(max(1, attempts)):
        rc, out = run_cmd(["powershell", "-NoProfile", "-NonInteractive",
                           "-Command", ps], timeout=20)
        for tok in reversed((out or "").split()):
            if tok.isdigit() and tok != "0":
                return tok
        if i < attempts - 1:
            time.sleep(0.3)
    return None


def is_protected_process(image_name):
    low = (image_name or "").lower()
    return any(p in low for p in PROTECTED_PROCESSES)


def safe_kill(pid, allowed_substrings):
    """
    Termina el PID SOLO si su imagen coincide con la lista permitida y NO es un
    proceso protegido (Docker/WSL/DB/etc.). Devuelve (ok, mensaje).
    """
    image = process_image(pid)
    low = (image or "").lower()
    if not image:
        return False, f"PID {pid}: no se pudo identificar el proceso; no se detiene."
    if is_protected_process(image):
        return False, (f"PID {pid} ({image}) es un proceso PROTEGIDO "
                       f"(Docker/WSL/DB/red); no se detiene.")
    if not any(a.lower() in low for a in allowed_substrings):
        return False, (f"PID {pid} ({image}) no esta en la lista permitida {list(allowed_substrings)}; "
                       f"no se detiene.")
    rc, out = run_cmd(["taskkill", "/F", "/PID", str(int(pid)), "/T"], timeout=20)
    if rc == 0:
        return True, f"Proceso detenido (PID {pid}, {image})."
    return False, f"No se pudo detener PID {pid}: {strip_ansi(out).strip()}"


def http_request(url, method="GET", timeout=6, payload=None, headers=None):
    """Realiza una peticion HTTP y devuelve (ok, data) donde data es dict/str."""
    data = None
    hdrs = {"Accept": "application/json"}
    if headers:
        hdrs.update(headers)
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        hdrs["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=hdrs)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", "replace")
            try:
                return True, json.loads(raw)
            except json.JSONDecodeError:
                return True, raw
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8", "replace")
            return False, json.loads(body)
        except Exception:
            return False, f"HTTP {e.code}"
    except urllib.error.URLError as e:
        return False, str(e.reason if hasattr(e, "reason") else e)
    except Exception as e:
        return False, str(e)


def http_get_json(url, timeout=6):
    return http_request(url, "GET", timeout)


def http_post_json(url, timeout=6, payload=None):
    return http_request(url, "POST", timeout, payload)


# ---------------------------------------------------------------- DPI -------

def enable_dpi_awareness():
    """Mejora la nitidez de la interfaz en pantallas High-DPI (Windows)."""
    if os.name != "nt":
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
        return
    except Exception:
        pass
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def timestamp():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ----------------------------------------------------------- Everything -----

EVERYTHING_MENU_BASES = [
    r"Software\Classes\*\shell\NexusEverything",
    r"Software\Classes\Directory\shell\NexusEverything",
    r"Software\Classes\Directory\Background\shell\NexusEverything",
]


def _everything_candidates():
    env = os.environ
    cands = []
    for var in ("ProgramFiles", "ProgramFiles(x86)", "ProgramW6432", "LOCALAPPDATA"):
        root = env.get(var)
        if root:
            cands.append(os.path.join(root, "Everything", "Everything.exe"))
    local = env.get("LOCALAPPDATA", "")
    if local:
        cands.append(os.path.join(local, "Programs", "Everything", "Everything.exe"))
    base = get_base_dir()
    for extra in (
        os.path.join(base, "Everything", "Everything.exe"),
        os.path.join(base, "tools", "Everything", "Everything.exe"),
        os.path.join(os.path.dirname(base), "Everything", "Everything.exe"),
    ):
        cands.append(extra)
    home = os.path.expanduser("~")
    for extra in ("Desktop", "Downloads", "Documents"):
        cands.append(os.path.join(home, extra, "Everything.exe"))
        cands.append(os.path.join(home, extra, "Everything", "Everything.exe"))
    return cands


def find_everything():
    """Detecta Everything.exe instalado o portable. Devuelve dict o None."""
    for p in _everything_candidates():
        if p and os.path.isfile(p):
            low = p.lower()
            kind = "instalado" if "program files" in low else "portable"
            es = os.path.join(os.path.dirname(p), "es.exe")
            return {"path": p, "kind": kind, "es": es if os.path.isfile(es) else None}
    for name in ("Everything.exe", "Everything"):
        w = which(name)
        if w:
            return {"path": w, "kind": "portable", "es": None}
    return None


def _reg(args):
    try:
        r = subprocess.run(["reg"] + args, capture_output=True, text=True,
                           creationflags=_NO_WINDOW)
        return r.returncode == 0, (r.stdout or "") + (r.stderr or "")
    except Exception as exc:
        return False, str(exc)


def everything_context_menu_present():
    ok, _ = _reg(["query", "HKCU\\" + EVERYTHING_MENU_BASES[0]])
    return ok


def everything_context_menu_add(exe):
    """Anade 'Buscar con Everything' al menu de click derecho (solo HKCU)."""
    entries = [
        (EVERYTHING_MENU_BASES[0], "Buscar con Everything", f'"{exe}" -search "%1"'),
        (EVERYTHING_MENU_BASES[1], "Buscar con Everything", f'"{exe}" -search "%1"'),
        (EVERYTHING_MENU_BASES[2], "Buscar con Everything aqui", f'"{exe}" -search "%V"'),
    ]
    ok_all, errs = True, []
    for key, label, cmd in entries:
        o1, m1 = _reg(["add", "HKCU\\" + key, "/ve", "/d", label, "/f"])
        o2, m2 = _reg(["add", "HKCU\\" + key + r"\command", "/ve", "/d", cmd, "/f"])
        if not (o1 and o2):
            ok_all = False
            errs.append((m1 + m2).strip())
    if ok_all:
        return True, "Menu contextual de Everything instalado (click derecho)."
    return False, "No se pudo instalar el menu contextual:\n" + "\n".join(errs)


def everything_context_menu_remove():
    ok_all, errs = True, []
    for key in EVERYTHING_MENU_BASES:
        ok, out = _reg(["delete", "HKCU\\" + key, "/f"])
        if not ok and "no se pudo encontrar" not in out.lower():
            ok_all = False
            errs.append(out.strip())
    if ok_all:
        return True, "Menu contextual de Everything quitado."
    return False, "No se pudo quitar el menu contextual:\n" + "\n".join(errs)
