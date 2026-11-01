# -*- coding: utf-8 -*-
"""
NEXUS Suite - claude_ops (MODULO CLAUDE)
========================================
Integra Free Claude Code (FCC) dentro de NEXUS Suite.

Free Claude Code es un proxy local que conecta agentes de codigo (Claude Code,
Codex, OpenCode, Cline, Aider, Hermes, DSH, Grok, Muse, Pi...) con decenas de
proveedores de IA compatibles (NVIDIA NIM, Groq, OpenRouter, Google, etc.).
Su Admin UI corre en http://127.0.0.1:8082/admin.

Este modulo expone funciones limpias (sin imprimir) que la GUI consume:

  * Deteccion del proyecto y de uv (gestor de Python de FCC).
  * Estado en tiempo real del servidor, del Admin UI y de la configuracion.
  * Arranque / parada del servidor y lanzamiento de cada agente.
  * Instalacion real de uv, sincronizacion de dependencias y auto-update.
  * Doctor, modelos y variables del archivo ~/.fcc/.env.

Sin dependencias externas: solo biblioteca estandar.
"""

import os
import re
import json
import hashlib
import time
import shutil
import tempfile
import datetime
import stat
import subprocess
import urllib.request
import zipfile

from . import common as C

FCC_FALLBACK_VERSION = "6.16.16"
DEFAULT_PORT = 8082
DEFAULT_HOST = "127.0.0.1"
ENV_FILE_ENV = "FCC_ENV_FILE"

AGENTS = {
    "claude":   ("Claude Code", "fcc-claude"),
    "codex":    ("Codex", "fcc-codex"),
    "opencode": ("OpenCode 2", "fcc-opencode"),
    "cline":    ("Cline", "fcc-cline"),
    "aider":    ("Aider", "fcc-aider"),
    "hermes":   ("Hermes", "fcc-hermes"),
    "dsh":      ("DeepSeek Harness", "fcc-dsh"),
    "grok":     ("Grok Build", "fcc-grok"),
    "muse":     ("Muse Code", "fcc-muse"),
    "pi":       ("Pi", "fcc-pi"),
}

AGENT_BINARIES = {
    "claude": "claude",
    "codex": "codex",
    "opencode": "opencode",
    "cline": "cline",
    "aider": "aider",
    "hermes": "hermes",
    "dsh": "dsh",
    "grok": "grok",
    "muse": "muse",
    "pi": "pi",
}

AGENT_HINTS = {
    "claude": "npm install -g @anthropic-ai/claude-code",
    "codex": "npm install -g @openai/codex",
    "opencode": "Requiere OpenCode 2 (https://opencode.ai/v2/docs/migrate-v1/)",
    "cline": "https://docs.cline.bot/getting-started/installing-cline",
    "aider": "https://aider.chat/docs/install.html",
    "hermes": "https://hermes-agent.nousresearch.com/docs/installation",
    "dsh": "npm install -g @deepseek-ai/dsh@latest",
    "grok": "irm https://x.ai/cli/install.ps1 | iex",
    "muse": "irm https://raw.githubusercontent.com/Alishahryar1/free-claude-code/main/scripts/install-muse.ps1",
    "pi": 'powershell -c "irm https://pi.dev/install.ps1 | iex"',
}

FCC_REPO_ZIP = "https://github.com/Alishahryar1/free-claude-code/archive/refs/heads/main.zip"

MODEL_PROVIDER_KEYS = {
    "open_router": "OPENROUTER_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "nvidia_nim": "NVIDIA_NIM_API_KEY",
    "nvidia": "NVIDIA_NIM_API_KEY",
    "groq": "GROQ_API_KEY",
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "xai": "XAI_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "google": "GEMINI_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "mistral": "MISTRAL_API_KEY",
    "codestral": "CODESTRAL_API_KEY",
    "opencode": "OPENCODE_API_KEY",
    "together": "TOGETHER_API_KEY",
    "siliconflow": "SILICONFLOW_API_KEY",
    "nebius": "NEBIUS_API_KEY",
    "huggingface": "HUGGINGFACE_API_KEY",
    "cohere": "COHERE_API_KEY",
}

PROVIDER_KEYS = (
    "NVIDIA_NIM_API_KEY", "OPENROUTER_API_KEY", "GROQ_API_KEY",
    "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "XAI_API_KEY", "GEMINI_API_KEY",
    "DEEPSEEK_API_KEY", "MISTRAL_API_KEY", "CODESTRAL_API_KEY",
    "OPENCODE_API_KEY", "TOGETHER_API_KEY", "SILICONFLOW_API_KEY",
    "NEBIUS_API_KEY", "HUGGINGFACE_API_KEY", "COHERE_API_KEY",
)


# ============================================================== rutas =======

def project_dir():
    """Carpeta REAL del proyecto Free Claude Code, o '' si no esta instalado."""
    d = C.claude_dir()
    if d and C._is_fcc_project(d):
        return d
    # Respaldo: buscar junto a NEXUS validando el pyproject de FCC.
    for base in C.candidate_bases():
        for cand in (os.path.join(base, "claude"),
                     os.path.join(base, "claude", "free-claude-code"),
                     os.path.join(base, "free-claude-code")):
            if C._is_fcc_project(cand):
                return os.path.abspath(cand)
    return ""


def project_exists():
    return bool(project_dir())


def config_dir():
    """Carpeta de configuracion de FCC (~/.fcc)."""
    home = C.user_home()
    return os.path.join(home, ".fcc")


def env_path():
    explicit = os.environ.get(ENV_FILE_ENV, "").strip()
    if explicit:
        return os.path.abspath(os.path.expanduser(explicit))
    return os.path.join(config_dir(), ".env")


def log_path():
    return os.path.join(config_dir(), "logs", "server.log")


def venv_path(project=None):
    """Entorno POR EQUIPO, fuera de la carpeta portable (nunca se copia)."""
    project = project or project_dir()
    if not project:
        return ""
    root = os.environ.get("LOCALAPPDATA") or os.path.join(C.user_home(), ".local", "share")
    digest = hashlib.sha1(
        os.path.normcase(os.path.abspath(project)).encode("utf-8", "ignore")
    ).hexdigest()[:8]
    return os.path.join(root, "Nexus", "fcc", f"venv-{digest}")


def legacy_venv_path(project=None):
    """Antiguo .venv dentro del proyecto (puede venir roto de otro PC)."""
    project = project or project_dir()
    return os.path.join(project, ".venv") if project else ""


def _venv_home_ok(v):
    """Comprueba que el Python base del venv exista en ESTE equipo."""
    cfg = os.path.join(v, "pyvenv.cfg")
    try:
        with open(cfg, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if line.lower().startswith("home"):
                    home = line.split("=", 1)[1].strip().strip('"')
                    if not os.path.isdir(home):
                        return False
                    py = os.path.join(home, "python.exe" if os.name == "nt" else "python")
                    if not os.path.isfile(py):
                        return False
                    break
    except OSError:
        return False
    return True


def venv_ready(project=None):
    """True si el entorno es de este equipo y tiene el ejecutable de FCC."""
    v = venv_path(project)
    if not v or not os.path.isdir(v) or not _venv_home_ok(v):
        return False
    for sub in ("Scripts", "bin"):
        exe = os.path.join(v, sub, "fcc-server.exe" if os.name == "nt" else "fcc-server")
        py = os.path.join(v, sub, "python.exe" if os.name == "nt" else "python")
        if os.path.isfile(exe) and os.path.isfile(py):
            return True
    return False


def _pids_matching(needle):
    """PIDs cuyo ejecutable o linea de comandos contiene needle (Windows)."""
    if os.name != "nt" or not needle:
        return []
    safe = needle.replace("'", "''")
    script = (
        f"$p='{safe}'; "
        "Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | "
        "Where-Object { $_.ProcessId -ne $PID -and ("
        "($_.ExecutablePath -and $_.ExecutablePath.IndexOf($p, "
        "[System.StringComparison]::OrdinalIgnoreCase) -ge 0) -or "
        "($_.CommandLine -and $_.CommandLine.IndexOf($p, "
        "[System.StringComparison]::OrdinalIgnoreCase) -ge 0)) } | "
        "ForEach-Object { try { Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop; "
        "$_.ProcessId } catch {} }"
    )
    rc, out = C.run_cmd(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                        timeout=30)
    ids = []
    for line in (out or "").splitlines():
        line = line.strip()
        if line.isdigit():
            ids.append(int(line))
    return ids


def _kill_venv_processes(v):
    """Cierra procesos que ejecutan binarios desde el .venv activo o copiado."""
    return _pids_matching(v)


def _rmtree_force(path):
    def onerror(func, target, _exc):
        try:
            os.chmod(target, stat.S_IWRITE)
            func(target)
        except Exception:
            pass
    try:
        shutil.rmtree(path, onerror=onerror)
        return True
    except OSError:
        return False


def repair_venv(project=None):
    """Elimina un .venv copiado de otro PC para que uv lo recree."""
    v = venv_path(project)
    if not v or not os.path.isdir(v):
        return True, "No hay .venv que reparar."
    if venv_ready(project):
        return True, "El entorno .venv es valido."
    killed = _kill_venv_processes(v)
    if killed:
        time.sleep(1.5)
    if _rmtree_force(v):
        return True, "Entorno .venv invalido eliminado; uv creara uno nuevo."
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    for _ in range(3):
        old = f"{v}.old-{stamp}"
        try:
            os.rename(v, old)
        except OSError:
            time.sleep(2)
            continue
        shutil.rmtree(old, ignore_errors=True)
        return True, "Entorno .venv invalido apartado; uv creara uno nuevo."
    return False, ("No se pudo liberar .venv porque otro proceso lo usa.\n"
                   "Cierra todas las consolas de FCC/Claude Code y vuelve a intentarlo.")


def cleanup_legacy_venv(project=None):
    """Borra el .venv que venia dentro de la carpeta portable (ya no se usa)."""
    v = legacy_venv_path(project)
    if not v or not os.path.isdir(v):
        return True, ""
    if os.path.normcase(v) == os.path.normcase(venv_path(project)):
        return True, ""
    _kill_venv_processes(v)
    time.sleep(1)
    if _rmtree_force(v):
        return True, "Antiguo .venv de la carpeta eliminado."
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    old = f"{v}.old-{stamp}"
    try:
        os.rename(v, old)
    except OSError:
        return False, "No se pudo borrar el antiguo .venv (esta en uso); se ignorara."
    shutil.rmtree(old, ignore_errors=True)
    return True, "Antiguo .venv apartado; se ignorara."


def _fcc_version(project):
    """Version instalada o del ultimo tag git; sirve de fallback para hatch-vcs."""
    if not project:
        return ""
    for root in (venv_path(project), legacy_venv_path(project)):
        vdir = os.path.join(root or "", "Lib", "site-packages")
        try:
            for name in os.listdir(vdir):
                if name.lower().startswith("free_claude_code-") and name.endswith(".dist-info"):
                    meta = os.path.join(vdir, name, "METADATA")
                    with open(meta, "r", encoding="utf-8", errors="ignore") as f:
                        for line in f:
                            if line.lower().startswith("version:"):
                                return line.split(":", 1)[1].strip()
        except OSError:
            pass
    git = shutil.which("git")
    if git and os.path.isdir(os.path.join(project, ".git")):
        try:
            rc, out = C.run_cmd([git, "describe", "--tags", "--always"],
                                timeout=15, cwd=project)
            if rc == 0 and out.strip():
                return out.strip().splitlines()[0].lstrip("v")
        except Exception:
            pass
    return ""


def _ensure_build_fallback(project=None):
    """Anade fallback_version a proyectos copiados sin .git (hatch-vcs)."""
    project = project or project_dir()
    if not project:
        return False
    path = os.path.join(project, "pyproject.toml")
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return False
    if "fallback_version" in text or "[tool.hatch.version]" not in text:
        return False
    version = _fcc_version(project) or FCC_FALLBACK_VERSION
    block = ('\n[tool.hatch.version.raw-options]\n'
             f'fallback_version = "{version}"\n')
    m = re.search(r'\[tool\.hatch\.version\][^\[]*?source\s*=\s*"vcs"', text)
    if m:
        text = text[:m.end()] + block + text[m.end():]
    else:
        text = text.rstrip("\n") + block
    try:
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        return True
    except OSError:
        return False


def _fcc_build_env():
    """Evita el fallo de hatch-vcs/setuptools_scm cuando falta .git."""
    env = os.environ.copy()
    project = project_dir()
    if not project:
        return env
    active_venv = venv_path(project)
    if active_venv:
        env["UV_PROJECT_ENVIRONMENT"] = active_venv
    env["UV_LINK_MODE"] = "copy"
    has_git = os.path.isdir(os.path.join(project, ".git"))
    if has_git and shutil.which("git"):
        return env
    version = _fcc_version(project) or FCC_FALLBACK_VERSION
    env["SETUPTOOLS_SCM_PRETEND_VERSION"] = version
    env["SETUPTOOLS_SCM_PRETEND_VERSION_FOR_FREE_CLAUDE_CODE"] = version
    return env


def uv_path():
    found = shutil.which("uv")
    if found:
        return found
    home = C.user_home()
    base = C.get_base_dir()
    for cand in (os.path.join(home, ".local", "bin", "uv.exe"),
                 os.path.join(home, ".cargo", "bin", "uv.exe"),
                 os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "uv", "uv.exe"),
                 os.path.join(base, "tools", "uv.exe"),
                 os.path.join(base, "Nexus", "tools", "uv.exe")):
        if cand and os.path.isfile(cand):
            return cand
    return None


def uv_available():
    return uv_path() is not None


def _ensure_uv_in_path():
    uv = uv_path()
    if uv:
        C._ensure_process_path(os.path.dirname(uv))
    return uv


# ========================================================== config .env =====

def read_env():
    """Lee ~/.fcc/.env como dict (sin romper con comentarios ni comillas)."""
    path = env_path()
    values = {}
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                if line.lower().startswith("export "):
                    line = line[7:]
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key:
                    values[key] = value
    except OSError:
        pass
    return values


def backup_env():
    path = env_path()
    if not os.path.isfile(path):
        return None
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = f"{path}.bak-{stamp}"
    try:
        shutil.copy2(path, dest)
        return dest
    except OSError:
        return None


def set_env_value(key, value):
    """Crea/actualiza una clave de ~/.fcc/.env preservando el resto."""
    key = (key or "").strip()
    if not key or not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", key):
        return False, "Nombre de variable no valido."
    path = env_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
    except OSError as e:
        return False, f"No se pudo crear la carpeta de configuracion: {e}"
    lines = []
    found = False
    try:
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8-sig") as f:
                lines = f.read().splitlines()
    except OSError:
        lines = []
    out = []
    for line in lines:
        m = re.match(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=", line)
        if m and m.group(1) == key:
            if not found:
                out.append(f"{key}={value}")
                found = True
            continue
        out.append(line)
    if not found:
        out.append(f"{key}={value}")
    backup_env()
    try:
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(out).rstrip("\n") + "\n")
        return True, f"{key} guardada en {path}"
    except OSError as e:
        return False, f"No se pudo escribir .env: {e}"


def delete_env_value(key):
    path = env_path()
    if not os.path.isfile(path):
        return True, "No habia configuracion que modificar."
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            lines = f.read().splitlines()
    except OSError as e:
        return False, f"No se pudo leer .env: {e}"
    out = []
    removed = False
    for line in lines:
        m = re.match(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=", line)
        if m and m.group(1) == key:
            removed = True
            continue
        out.append(line)
    backup_env()
    try:
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(out).rstrip("\n") + ("\n" if out else ""))
    except OSError as e:
        return False, f"No se pudo escribir .env: {e}"
    return True, (f"{key} eliminada." if removed else f"{key} no estaba definida.")


def mask_secret(value):
    if not value:
        return "(sin definir)"
    if len(value) > 10:
        return value[:4] + "..." + value[-4:]
    return "(definida)"


def provider_issue():
    """Explica por que FCC devolveria 503 por falta de API key o modelo cruzado."""
    env = read_env()
    keys = [k for k in PROVIDER_KEYS if env.get(k)]
    model = (env.get("MODEL") or "").strip()
    provider = model.split("/", 1)[0].lower() if "/" in model else ""
    needed = MODEL_PROVIDER_KEYS.get(provider)
    if needed and not env.get(needed):
        if keys:
            return (f"El modelo '{model}' usa {provider}, pero falta {needed}. "
                    f"Claves presentes: {', '.join(keys)}. Cambia MODEL o anade {needed}.")
        return (f"El modelo '{model}' usa {provider}, pero {needed} no esta configurada. "
                f"Anade la clave en el Admin UI.")
    if not keys:
        return ("No hay ninguna API key de proveedor configurada. "
                "Abre el Admin UI y anade la clave de tu proveedor.")
    return ""


# =========================================================== servidor =======

def server_host():
    env = os.environ.copy()
    env.update(read_env())
    host = (env.get("HOST") or DEFAULT_HOST).strip()
    return host if host not in ("0.0.0.0", "::") else "127.0.0.1"


def server_port():
    env = os.environ.copy()
    env.update(read_env())
    try:
        return int(env.get("PORT") or DEFAULT_PORT)
    except (TypeError, ValueError):
        return DEFAULT_PORT


def admin_url():
    return f"http://{server_host()}:{server_port()}/admin"


def proxy_url():
    return f"http://{server_host()}:{server_port()}"


def server_running(port=None):
    return C.port_open("127.0.0.1", port or server_port(), timeout=0.35)


def server_owner(port=None):
    return C.port_owner(port or server_port(), fast=True)


def server_health():
    """Estado HTTP del Admin UI (tiempo real). Devuelve (ok, mensaje)."""
    if not server_running():
        return False, "Servidor FCC detenido."
    ok, data = C.http_get_json(f"http://127.0.0.1:{server_port()}/v1/models", timeout=4)
    if ok:
        count = len(data.get("data", [])) if isinstance(data, dict) and isinstance(data.get("data"), list) else "?"
        return True, f"Servidor FCC activo en {proxy_url()} (modelos expuestos: {count})."
    # /v1/models puede requerir auth; el Admin sigue siendo valido si responde.
    return True, f"Servidor FCC escuchando en {proxy_url()}."


def start_server():
    """Inicia fcc-server en una consola visible (uv run --no-dev fcc-server)."""
    uv = _ensure_uv_in_path()
    if not uv:
        return False, "uv no esta instalado. Usa 'Instalar uv' en la seccion Claude."
    project = project_dir()
    if not project:
        return False, ("No se encontro el proyecto Free Claude Code.\n"
                       "Debe existir Nexus/claude con pyproject.toml.")
    if server_running():
        return True, f"El servidor FCC ya esta activo. Admin: {admin_url()}"
    args = ["run", "--project", project, "--no-dev", "fcc-server"]
    if C.open_new_console([uv] + args, cwd=project, title="FCC Server", env=_fcc_build_env()):
        return True, ("Iniciando Free Claude Code en una consola nueva. "
                      f"Admin UI: {admin_url()} (tarda unos segundos).")
    return False, "No se pudo abrir la consola del servidor FCC."


def stop_server():
    """Detiene el servidor SOLO si el puerto pertenece a Python/uv/FCC."""
    if not server_running():
        return True, "El servidor FCC ya estaba detenido."
    pid, image = server_owner()
    if not pid:
        # netstat a veces tarda en exponer el PID justo tras arrancar.
        pid, image = C.port_owner(server_port(), fast=False)
    if pid:
        low = (image or "").lower()
        if not any(tag in low for tag in ("python", "uv", "fcc", "uvicorn")):
            return False, (f"El puerto {server_port()} lo usa '{image}' (PID {pid}); "
                           "no parece ser FCC. NO se detiene para no afectar otros servicios.")
        return C.safe_kill(pid, ("python", "uv", "fcc", "uvicorn"))
    # Respaldo: localizar por linea de comandos (uv/venv a veces ocultan el PID).
    pids = _pids_matching("fcc-server")
    if pids:
        time.sleep(1)
        return True, f"Servidor FCC detenido ({len(pids)} proceso(s))."
    return False, "No se pudo identificar el proceso que usa el puerto; cierra la consola FCC."


def open_admin():
    import webbrowser
    return webbrowser.open(admin_url())


def open_proxy():
    import webbrowser
    return webbrowser.open(proxy_url())


# ========================================================== agentes =========

def run_agent(agent, extra_args=None, cwd=None):
    """Abre un agente FCC en una consola visible. agent: clave de AGENTS."""
    uv = _ensure_uv_in_path()
    if not uv:
        return False, "uv no esta instalado. Usa 'Instalar uv' en la seccion Claude."
    key = (agent or "").lower()
    if key not in AGENTS:
        return False, f"Agente desconocido: {agent}"
    project = project_dir()
    if not project or not os.path.isdir(project):
        return False, "No se encontro el proyecto Free Claude Code (Nexus/claude)."
    label, command = AGENTS[key]
    workdir = os.path.abspath(cwd or C.get_base_dir())
    # uv debe resolver el proyecto FCC; --directory fija la carpeta de trabajo
    # del agente sin perder las dependencias y scripts del proyecto.
    args = ["run", "--project", project, "--no-dev"]
    if os.path.normcase(workdir) != os.path.normcase(os.path.abspath(project)):
        args += ["--directory", workdir]
    args += [command] + list(extra_args or [])
    if C.open_new_console([uv] + args, cwd=workdir, title=f"FCC {label}", env=_fcc_build_env()):
        return True, (f"{label} iniciado en una consola nueva.\n"
                      "Si el agente no esta instalado, FCC mostrara el comando oficial "
                      "para instalarlo. Si el servidor no estaba activo, FCC lo arrancara.")
    return False, f"No se pudo abrir la consola de {label}."


# ================================================== instalacion / update ====

_VERSION_CACHE = {}


def _binary_version(binary, ttl=300):
    now = time.time()
    hit = _VERSION_CACHE.get(binary)
    if hit and now - hit[0] < ttl:
        return hit[1]
    version = ""
    if C.tool_available(binary):
        exe = C.which(binary) or C._which_ext(binary) or binary
        try:
            rc, out = C.run_program([exe, "--version"], timeout=12)
            if rc == 0:
                m = re.search(r"(\d+)\.(\d+)\.(\d+)", out or "")
                if m:
                    version = ".".join(m.groups())
        except Exception:
            version = ""
    _VERSION_CACHE[binary] = (now, version)
    return version


def _version_at_least(version, minimum):
    try:
        have = tuple(int(x) for x in version.split("."))
    except (TypeError, ValueError):
        return False
    return have >= tuple(minimum)


def agent_issue(agent):
    """'' si el agente puede usarse; si no, explica exactamente que falta."""
    key = (agent or "").lower()
    binary = AGENT_BINARIES.get(key)
    if not binary:
        return "agente desconocido"
    if not C.tool_available(binary):
        return "falta CLI: " + AGENT_HINTS.get(key, binary)
    if key == "opencode":
        version = _binary_version(binary)
        if version and not _version_at_least(version, (2, 0, 0)):
            return f"OpenCode {version} instalado; FCC requiere OpenCode 2"
    return ""


def agent_available(agent):
    """True si el CLI nativo del agente esta instalado y cumple la version."""
    return not agent_issue(agent)


def agent_status():
    return {k: agent_available(k) for k in AGENTS}


def _install_target():
    """Ruta objetivo del proyecto FCC: <base>/Nexus/claude (sin nivel extra)."""
    base = C.get_base_dir()
    if os.path.basename(base).lower() == "nexus":
        return os.path.join(base, "claude")
    if os.path.isdir(os.path.join(base, "Nexus")):
        return os.path.join(base, "Nexus", "claude")
    return os.path.join(base, "claude")


def install_project():
    """Descarga FCC desde GitHub si la carpeta del proyecto no existe o esta rota."""
    if project_exists():
        return True, f"El proyecto FCC ya esta instalado en {project_dir()}."
    target = _install_target()
    tmp = tempfile.mkdtemp(prefix="nexus-fcc-")
    archive = os.path.join(tmp, "fcc.zip")
    try:
        os.makedirs(os.path.dirname(target), exist_ok=True)
        req = urllib.request.Request(FCC_REPO_ZIP, headers={"User-Agent": "NEXUS-Suite"})
        with urllib.request.urlopen(req, timeout=90) as resp, open(archive, "wb") as f:
            shutil.copyfileobj(resp, f)
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(tmp)
        root = None
        for name in os.listdir(tmp):
            cand = os.path.join(tmp, name)
            if C._is_fcc_project(cand):
                root = cand
                break
        if not root:
            return False, "El paquete descargado no contiene el proyecto Free Claude Code."
        if os.path.isdir(target):
            shutil.rmtree(target, ignore_errors=True)
        shutil.copytree(root, target)
        _ensure_build_fallback(target)
        if C._is_fcc_project(target):
            return True, (f"Free Claude Code instalado en:\n{target}\n\n"
                          "Ahora pulsa 'Sincronizar dependencias'.")
        return False, "La descarga termino, pero el proyecto no quedo en una ruta valida."
    except Exception as e:
        return False, (f"No se pudo descargar Free Claude Code: {e}\n"
                       "Comprueba tu conexion o copia manualmente la carpeta Nexus/claude.")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def prepare():
    """Prepara FCC en un PC nuevo: proyecto + uv + dependencias."""
    lines = []
    if server_running():
        ok, msg = stop_server()
        lines.append(("[OK] " if ok else "[!] ") + msg)
    if not project_exists():
        ok, msg = install_project()
        lines.append(("[OK] " if ok else "[!] ") + msg.replace("\n", "\n      "))
        if not ok:
            return False, "\n".join(lines)
    uv = _ensure_uv_in_path()
    if not uv:
        ok, msg = install_uv()
        lines.append(("[OK] " if ok else "[!] ") + msg)
        lines.append("Cuando termine el instalador, pulsa 'Preparar FCC' otra vez.")
        return False, "\n".join(lines)
    ok, out = sync_dependencies()
    lines.append(("[OK] " if ok else "[!] ") + "uv sync --no-dev")
    if out:
        lines.append(out)
    if ok:
        lines.append("FCC listo. Inicia el servidor y configura el proveedor en el Admin UI.")
    return ok, "\n".join(lines)


def install_uv():
    """Instala uv de forma real con el instalador oficial (PowerShell)."""
    cmd = ("$ErrorActionPreference='Stop'; "
           "irm https://astral.sh/uv/install.ps1 | iex; "
           "Write-Host ''; Write-Host 'uv instalado. Cierra y abre NEXUS para refrescar el PATH.'")
    try:
        if C.open_new_console(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                               "-Command", cmd], title="NEXUS - Instalar uv"):
            return True, ("Instalador oficial de uv abierto en una consola. "
                          "Al terminar, pulsa 'Refrescar estado'.")
        return False, "No se pudo abrir la consola del instalador de uv."
    except Exception as e:
        return False, f"No se pudo abrir el instalador de uv: {e}"


def sync_dependencies():
    """Sincroniza dependencias (uv sync --no-dev). Crea el entorno de Python."""
    uv = _ensure_uv_in_path()
    if not uv:
        return False, "uv no esta instalado."
    project = project_dir()
    if not project:
        return False, "No se encontro el proyecto Free Claude Code."
    if server_running():
        return False, ("El servidor FCC esta activo y bloquea el entorno .venv.\n"
                       "Detenlo primero con 'Detener servidor' y vuelve a sincronizar.")
    _ensure_build_fallback(project)
    rc, out = C.run_cmd([uv, "sync", "--project", project, "--no-dev"],
                        timeout=1800, cwd=project, env=_fcc_build_env())
    return rc == 0, (out or "").strip()


def update_uv():
    uv = _ensure_uv_in_path()
    if not uv:
        return False, "uv no esta instalado."
    return C.run_program([uv, "self", "update"], timeout=300)


def update_project():
    """Actualiza uv + dependencias del proyecto (equivalente al iniciador)."""
    lines = []
    ok1, out1 = update_uv()
    lines.append(("[OK] " if ok1 else "[!] ") + "uv self update")
    lines.append((out1 or "").strip())
    ok2, out2 = sync_dependencies()
    lines.append(("[OK] " if ok2 else "[!] ") + "uv sync --no-dev")
    lines.append((out2 or "").strip())
    return ok2, "\n".join([ln for ln in lines if ln is not None])


def install_claude_code():
    """Instala Claude Code globalmente con npm (real)."""
    npm = shutil.which("npm")
    if not npm:
        return False, "npm no esta instalado. Instala Node.js primero."
    cmd = f'echo [NEXUS] Instalando Claude Code... & "{npm}" install -g @anthropic-ai/claude-code & echo. & echo Listo. & pause'
    if C.open_new_console(cmd, title="NEXUS - Instalar Claude Code"):
        return True, "Instalacion de Claude Code abierta (npm install -g @anthropic-ai/claude-code)."
    return False, "No se pudo abrir la consola de instalacion."


# =========================================================== doctor =========

def doctor():
    """Ejecuta fcc-doctor y devuelve su salida real."""
    uv = _ensure_uv_in_path()
    if not uv:
        return False, "uv no esta instalado."
    project = project_dir()
    if not project:
        return False, ("No se encontro el proyecto Free Claude Code.\n"
                       "Debe existir Nexus/claude con pyproject.toml.")
    _ensure_build_fallback(project)
    rc, out = C.run_cmd([uv, "run", "--project", project, "--no-dev", "fcc-doctor"],
                        timeout=1800, cwd=project, env=_fcc_build_env())
    return rc == 0, (out or "").strip()


def local_diagnostics():
    """Diagnostico propio de NEXUS (rapido, sin red) para la seccion Claude."""
    env = read_env()
    keys = [k for k in PROVIDER_KEYS if env.get(k)]
    agents_present = []
    for key, (label, _cmd) in AGENTS.items():
        issue = agent_issue(key)
        agents_present.append(f"{label} [{'OK' if not issue else issue}]")
    lines = [
        f"Proyecto FCC : {project_dir() or 'NO ENCONTRADO'}",
        f"pyproject    : {'si' if project_exists() else 'no'}",
        f"uv           : {uv_path() or 'NO INSTALADO'}",
        f"Entorno py   : {'listo' if venv_ready() else ('incompleto' if venv_path() and os.path.isdir(venv_path()) else 'no')}  ({venv_path()})",
        f"Metadatos    : {'git OK' if os.path.isdir(os.path.join(project_dir() or '', '.git')) else 'sin .git (version de respaldo: ' + (_fcc_version(project_dir()) or FCC_FALLBACK_VERSION) + ')'}",
        f"Config .env  : {env_path()}{'' if os.path.isfile(env_path()) else '  (no existe)'}",
        f"Servidor     : {'ACTIVO' if server_running() else 'detenido'} en {proxy_url()}",
        f"Admin UI     : {admin_url()}",
        f"Modelo       : {env.get('MODEL') or '(por defecto en Admin)'}",
        f"Proveedores  : {', '.join(keys) if keys else '(ninguno con API key en .env)'}",
        f"Estado API   : {provider_issue() or 'OK (modelo y clave compatibles)'}",
        "Agentes      : " + "; ".join(agents_present),
        f"Log servidor : {log_path()}",
    ]
    return "\n".join(lines)


def _agent_installed(command):
    """True si el entrypoint existe en el entorno del proyecto o en el PATH."""
    if shutil.which(command):
        return True
    v = venv_path()
    if v:
        for sub in ("Scripts", "bin"):
            cand = os.path.join(v, sub, command + (".exe" if os.name == "nt" else ""))
            if os.path.isfile(cand):
                return True
    return False


# =========================================================== estado =========

def status():
    env = read_env()
    return {
        "project_dir": project_dir(),
        "project_exists": project_exists(),
        "config_dir": config_dir(),
        "env_path": env_path(),
        "env_exists": os.path.isfile(env_path()),
        "uv": uv_path(),
        "uv_ok": uv_available(),
        "venv": venv_ready(),
        "server_running": server_running(),
        "server_owner": server_owner()[1] or "",
        "admin_url": admin_url(),
        "proxy_url": proxy_url(),
        "port": server_port(),
        "model": env.get("MODEL") or "",
        "providers": [k for k in PROVIDER_KEYS if env.get(k)],
        "provider_issue": provider_issue(),
        "agents": agent_status(),
        "log": log_path(),
        "claude_code": shutil.which("claude"),
        "node": shutil.which("node"),
        "npm": shutil.which("npm"),
    }


def requirements():
    """Lista de requisitos para que la seccion Claude indique que falta."""
    return [
        {"name": "Proyecto Free Claude Code", "ok": project_exists(), "required": True,
         "value": project_dir() or "no encontrado",
         "hint": "Debe existir la carpeta Nexus/claude con pyproject.toml."},
        {"name": "uv", "ok": uv_available(), "required": True,
         "value": uv_path() or "no instalado",
         "hint": "Pulsa 'Instalar uv' (instalador oficial)."},
        {"name": "Dependencias (uv sync)", "ok": venv_ready(), "required": True,
         "value": "entorno listo" if venv_ready() else
                  ("entorno incompleto (sincroniza)" if venv_path() and os.path.isdir(venv_path())
                   else "sin sincronizar"),
         "hint": "Pulsa 'Preparar FCC'. El entorno se crea por equipo y no se copia con la carpeta."},
        {"name": "API key proveedor", "ok": not provider_issue(), "required": True,
         "value": provider_issue() or "modelo y clave compatibles",
         "hint": "Abre el Admin UI y configura el proveedor; o edita MODEL/API keys en el Panel."},
        {"name": "Servidor FCC", "ok": server_running(), "required": False,
         "value": f"{proxy_url()} ({'activo' if server_running() else 'detenido'})",
         "hint": "Pulsa 'Iniciar servidor FCC' y configura el proveedor en el Admin UI."},
        {"name": "Claude Code", "ok": bool(shutil.which("claude")), "required": False,
         "value": shutil.which("claude") or "no instalado",
         "hint": "Herramientas > Instalar Claude Code (npm)."},
        {"name": "Node.js / npm", "ok": bool(shutil.which("node") and shutil.which("npm")),
         "required": True, "value": shutil.which("node") or "no instalado",
         "hint": "https://nodejs.org (LTS)."},
    ]
