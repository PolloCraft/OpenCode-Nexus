# -*- coding: utf-8 -*-
"""
NEXUS Suite - antigravity_ops (MODULO ANTIGRAVITY)
==================================================
Todas las operaciones del plugin Antigravity + OpenCode, como funciones
que devuelven datos (sin imprimir). La GUI las consume.

Cubre:
  * General: diagnostico del sistema y del plugin.
  * Cuentas: listar, activar/desactivar, cuotas, borrar todo (con respaldo).
  * Plugin: activar/desactivar, login OAuth.
  * Modelos: configurar modelos en opencode.json.
  * Mantenimiento: reparar compatibilidad Node, auto-update, API key Google.

Sin dependencias externas: solo biblioteca estandar.
"""

import os
import re
import json
import shutil
import datetime
import subprocess

from . import common as C

PLUGIN_NAME = "opencode-antigravity-auth"

MODELS = {
    "antigravity-gemini-3-pro": {
        "name": "Gemini 3 Pro (Antigravity)",
        "limit": {"context": 1048576, "output": 65535},
        "modalities": {"input": ["text", "image", "pdf"], "output": ["text"]},
        "variants": {"low": {"thinkingLevel": "low"}, "high": {"thinkingLevel": "high"}},
    },
    "antigravity-gemini-3.1-pro": {
        "name": "Gemini 3.1 Pro (Antigravity)",
        "limit": {"context": 1048576, "output": 65535},
        "modalities": {"input": ["text", "image", "pdf"], "output": ["text"]},
        "variants": {"low": {"thinkingLevel": "low"}, "high": {"thinkingLevel": "high"}},
    },
    "antigravity-gemini-3-flash": {
        "name": "Gemini 3 Flash (Antigravity)",
        "limit": {"context": 1048576, "output": 65536},
        "modalities": {"input": ["text", "image", "pdf"], "output": ["text"]},
        "variants": {
            "minimal": {"thinkingLevel": "minimal"},
            "low": {"thinkingLevel": "low"},
            "medium": {"thinkingLevel": "medium"},
            "high": {"thinkingLevel": "high"},
        },
    },
    "antigravity-claude-sonnet-4-6": {
        "name": "Claude Sonnet 4.6 (Antigravity)",
        "limit": {"context": 200000, "output": 64000},
        "modalities": {"input": ["text", "image", "pdf"], "output": ["text"]},
    },
    "antigravity-claude-opus-4-6-thinking": {
        "name": "Claude Opus 4.6 Thinking (Antigravity)",
        "limit": {"context": 200000, "output": 64000},
        "modalities": {"input": ["text", "image", "pdf"], "output": ["text"]},
        "variants": {
            "low": {"thinkingConfig": {"thinkingBudget": 8192}},
            "max": {"thinkingConfig": {"thinkingBudget": 32768}},
        },
    },
    "gemini-2.5-flash": {
        "name": "Gemini 2.5 Flash (Gemini CLI)",
        "limit": {"context": 1048576, "output": 65536},
        "modalities": {"input": ["text", "image", "pdf"], "output": ["text"]},
    },
    "gemini-2.5-pro": {
        "name": "Gemini 2.5 Pro (Gemini CLI)",
        "limit": {"context": 1048576, "output": 65536},
        "modalities": {"input": ["text", "image", "pdf"], "output": ["text"]},
    },
    "gemini-3-flash-preview": {
        "name": "Gemini 3 Flash Preview (Gemini CLI)",
        "limit": {"context": 1048576, "output": 65536},
        "modalities": {"input": ["text", "image", "pdf"], "output": ["text"]},
    },
    "gemini-3-pro-preview": {
        "name": "Gemini 3 Pro Preview (Gemini CLI)",
        "limit": {"context": 1048576, "output": 65535},
        "modalities": {"input": ["text", "image", "pdf"], "output": ["text"]},
    },
    "gemini-3.1-pro-preview": {
        "name": "Gemini 3.1 Pro Preview (Gemini CLI)",
        "limit": {"context": 1048576, "output": 65535},
        "modalities": {"input": ["text", "image", "pdf"], "output": ["text"]},
    },
    "gemini-3.1-pro-preview-customtools": {
        "name": "Gemini 3.1 Pro Preview Custom Tools (Gemini CLI)",
        "limit": {"context": 1048576, "output": 65535},
        "modalities": {"input": ["text", "image", "pdf"], "output": ["text"]},
    },
}


# ------------------------------------------------------------- utils -------

def strip_json_comments(text):
    sb = []
    in_string = in_line = in_block = escaped = False
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        nxt = text[i + 1] if i + 1 < n else ''
        if in_line:
            if c == '\n':
                in_line = False
                sb.append(c)
            i += 1
            continue
        if in_block:
            if c == '*' and nxt == '/':
                in_block = False
                i += 2
                continue
            i += 1
            continue
        if in_string:
            sb.append(c)
            if escaped:
                escaped = False
            elif c == '\\':
                escaped = True
            elif c == '"':
                in_string = False
            i += 1
            continue
        if c == '"':
            in_string = True
            sb.append(c)
            i += 1
            continue
        if c == '/' and nxt == '/':
            in_line = True
            i += 2
            continue
        if c == '/' and nxt == '*':
            in_block = True
            i += 2
            continue
        sb.append(c)
        i += 1
    clean = ''.join(sb)
    clean = re.sub(r',(\s*[}\]])', r'\1', clean)
    return clean


def read_json(path):
    if not path or not os.path.isfile(path):
        return None
    try:
        with open(path, 'r', encoding='utf-8-sig') as f:
            raw = f.read()
    except OSError:
        return None
    if not raw.strip():
        return None
    try:
        return json.loads(strip_json_comments(raw))
    except json.JSONDecodeError:
        return None


def save_json(obj, path):
    directory = os.path.dirname(path)
    if directory and not os.path.isdir(directory):
        os.makedirs(directory, exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)


def backup_file(path):
    if not path or not os.path.isfile(path):
        return None
    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')[:-3]
    dest = f"{path}.bak-{stamp}"
    try:
        shutil.copy2(path, dest)
        return dest
    except OSError:
        return None


# ------------------------------------------------------------- rutas -------

def get_config_dir():
    env_dir = os.environ.get("OPENCODE_CONFIG_DIR", "")
    if env_dir and os.path.isdir(env_dir):
        return os.path.abspath(env_dir)
    candidates = []
    xdg = os.environ.get("XDG_CONFIG_HOME", "")
    if xdg:
        candidates.append(os.path.join(xdg, "opencode"))
    candidates.append(os.path.join(C.user_home(), ".config", "opencode"))
    appdata = os.environ.get("APPDATA", "")
    if appdata:
        candidates.append(os.path.join(appdata, "opencode"))
    for c in candidates:
        if os.path.isdir(c):
            return c
    return candidates[0] if candidates else os.path.join(C.user_home(), ".config", "opencode")


def get_config_file(config_dir=None):
    config_dir = config_dir or get_config_dir()
    jsonc = os.path.join(config_dir, "opencode.jsonc")
    js = os.path.join(config_dir, "opencode.json")
    if os.path.isfile(jsonc):
        return jsonc
    if os.path.isfile(js):
        return js
    return None


def get_accounts_file(config_dir=None):
    config_dir = config_dir or get_config_dir()
    primary = os.path.join(config_dir, "antigravity-accounts.json")
    if os.path.isfile(primary):
        return primary
    appdata = os.environ.get("APPDATA", "")
    if appdata:
        legacy = os.path.join(appdata, "opencode", "antigravity-accounts.json")
        if os.path.isfile(legacy):
            return legacy
    return primary


def _opencode_candidates():
    """Ubicaciones tipicas donde queda 'opencode' aunque no este en el PATH."""
    home = C.user_home()
    appdata = os.environ.get("APPDATA", "")
    local = os.environ.get("LOCALAPPDATA", "")
    cands = []
    if appdata:
        cands += [os.path.join(appdata, "npm", "opencode.cmd"),
                  os.path.join(appdata, "npm", "opencode.ps1"),
                  os.path.join(appdata, "npm", "opencode")]
    if local:
        cands += [os.path.join(local, "opencode", "bin", "opencode.exe"),
                  os.path.join(local, "Programs", "opencode", "opencode.exe"),
                  os.path.join(local, "Microsoft", "WinGet", "Links", "opencode.exe")]
    cands += [os.path.join(home, ".opencode", "bin", "opencode.exe"),
              os.path.join(home, ".opencode", "bin", "opencode"),
              os.path.join(home, ".bun", "bin", "opencode.exe"),
              os.path.join(home, ".local", "bin", "opencode.exe"),
              os.path.join(home, ".local", "bin", "opencode")]
    return cands


def get_opencode_path():
    env = os.environ.get("NEXUS_OPENCODE", "") or os.environ.get("OPENCODE_BIN", "")
    if env and os.path.isfile(env):
        return env
    for name in ("opencode", "opencode.cmd", "opencode.ps1", "opencode.exe"):
        p = shutil.which(name)
        if p:
            return p
    for p in _opencode_candidates():
        if p and os.path.isfile(p):
            return p
    return None


def opencode_dirs():
    """Carpetas que contienen opencode (o npm) para anadir al PATH."""
    seen, dirs = set(), []

    def add(p):
        if not p:
            return
        p = os.path.abspath(p)
        key = os.path.normcase(p)
        if key not in seen:
            seen.add(key)
            dirs.append(p)

    found = get_opencode_path()
    if found:
        add(os.path.dirname(found))
    for p in _opencode_candidates():
        add(os.path.dirname(p))
    appdata = os.environ.get("APPDATA", "")
    if appdata:
        add(os.path.join(appdata, "npm"))
    return dirs


def get_plugin_cache_roots():
    home = C.user_home()
    roots = [
        os.path.join(home, ".cache", "opencode", "packages"),
        os.path.join(home, ".local", "share", "opencode", "packages"),
    ]
    xdg = os.environ.get("XDG_CACHE_HOME", "")
    if xdg:
        roots.append(os.path.join(xdg, "opencode", "packages"))
    localappdata = os.environ.get("LOCALAPPDATA", "")
    if localappdata:
        roots.append(os.path.join(localappdata, "opencode", "packages"))
    seen, unique = set(), []
    for r in roots:
        key = os.path.normcase(r)
        if key not in seen:
            seen.add(key)
            unique.append(r)
    return unique


def get_plugin_cache_dirs():
    dirs = []
    for root in get_plugin_cache_roots():
        if not os.path.isdir(root):
            continue
        try:
            for name in os.listdir(root):
                full = os.path.join(root, name)
                if os.path.isdir(full) and name.startswith(PLUGIN_NAME):
                    dirs.append(full)
        except OSError:
            continue
    return dirs


def test_plugin_cached():
    return len(get_plugin_cache_dirs()) > 0


def test_plugin_configured(config_file=None):
    config_file = config_file or get_config_file()
    cfg = read_json(config_file)
    if not cfg:
        return False
    plugins = cfg.get("plugin")
    if not plugins:
        return False
    if isinstance(plugins, str):
        plugins = [plugins]
    for p in plugins:
        if isinstance(p, str) and PLUGIN_NAME in p:
            return True
    return False


def opencode_running():
    return C.process_running("opencode.exe")


# ----------------------------------------- parche compatibilidad Node ------

def repair_js_file(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            text = f.read()
    except OSError:
        return False
    directory = os.path.dirname(path)
    pattern = re.compile(r'from\s+(["\'])(\.[^"\']+)\1')

    def repl(m):
        q = m.group(1)
        s = m.group(2)
        if re.search(r'\.(js|json|mjs|cjs)$', s):
            return m.group(0)
        full = os.path.join(directory, s.replace('/', os.sep))
        if os.path.isfile(full + '.js'):
            return f'from {q}{s}.js{q}'
        if os.path.isdir(full) and os.path.isfile(os.path.join(full, 'index.js')):
            return f'from {q}{s}/index.js{q}'
        return m.group(0)

    new_text = pattern.sub(repl, text)
    if new_text != text:
        try:
            with open(path, 'w', encoding='utf-8', newline='') as f:
                f.write(new_text)
            return True
        except OSError:
            return False
    return False


def repair_plugin_node_compat():
    patched = 0
    checked = 0
    for cache_dir in get_plugin_cache_dirs():
        nm = os.path.join(cache_dir, "node_modules")
        if not os.path.isdir(nm):
            continue
        targets = [
            os.path.join(nm, PLUGIN_NAME, "dist"),
            os.path.join(nm, "@opencode-ai", "plugin", "dist"),
        ]
        for target in targets:
            if not os.path.isdir(target):
                continue
            for dirpath, _dirnames, filenames in os.walk(target):
                for fname in filenames:
                    if not fname.endswith(".js"):
                        continue
                    checked += 1
                    if repair_js_file(os.path.join(dirpath, fname)):
                        patched += 1
    return patched, checked


def disable_plugin_auto_update():
    config_dir = get_config_dir()
    path = os.path.join(config_dir, "antigravity.json")
    obj = read_json(path)
    if obj is None:
        obj = {}
    if obj.get("auto_update") is False:
        return False, "Auto-update ya estaba desactivado."
    obj["auto_update"] = False
    backup_file(path)
    try:
        save_json(obj, path)
        return True, "Auto-update del plugin desactivado (el parche se mantiene)."
    except OSError as e:
        return False, f"No se pudo escribir antigravity.json: {e}"


def install_plugin_to_cache():
    root = None
    for r in get_plugin_cache_roots():
        if os.path.isdir(r):
            root = r
            break
    if not root:
        root = os.path.join(C.user_home(), ".cache", "opencode", "packages")
    cache_dir = os.path.join(root, f"{PLUGIN_NAME}@latest")
    os.makedirs(cache_dir, exist_ok=True)
    npm = shutil.which("npm")
    if not npm:
        return False, "npm no esta instalado."
    try:
        subprocess.run(
            [npm, "install", f"{PLUGIN_NAME}@latest", "--prefix", cache_dir,
             "--no-audit", "--no-fund"],
            capture_output=True, timeout=600,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception as e:
        return False, f"Fallo la instalacion: {e}"
    ok = os.path.isdir(os.path.join(cache_dir, "node_modules", PLUGIN_NAME))
    return ok, ("Plugin instalado en cache." if ok else "No se pudo instalar el plugin.")


# ------------------------------------------------------------ cuentas ------

def load_accounts():
    accounts_file = get_accounts_file()
    data = read_json(accounts_file)
    accounts = (data or {}).get("accounts") or []
    return accounts_file, data, accounts


def list_accounts():
    """Devuelve lista de dicts con email, enabled, projectId, added (formateado)."""
    _file, _data, accounts = load_accounts()
    out = []
    for i, a in enumerate(accounts, start=1):
        added = a.get("addedAt")
        added_h = ""
        if added:
            try:
                added_h = datetime.datetime.fromtimestamp(int(added) / 1000).strftime("%Y-%m-%d %H:%M")
            except (ValueError, OSError, OverflowError):
                added_h = str(added)
        out.append({
            "index": i,
            "email": a.get("email") or f"Cuenta {i}",
            "enabled": bool(a.get("enabled", True)),
            "projectId": a.get("projectId") or "",
            "added": added_h,
            "cachedQuota": a.get("cachedQuota") or {},
        })
    return out


def get_quotas():
    """Devuelve lista de (email, [(pool, pct, reset)]) a partir de la cache."""
    _file, _data, accounts = load_accounts()
    out = []
    for i, a in enumerate(accounts, start=1):
        email = a.get("email") or f"Cuenta {i}"
        pools = []
        quota = a.get("cachedQuota")
        if isinstance(quota, dict):
            for pool_name, info in quota.items():
                if not isinstance(info, dict):
                    continue
                frac = info.get("remainingFraction")
                when = info.get("resetTime") or ""
                pct = "?"
                if frac is not None:
                    try:
                        pct = f"{round(float(frac) * 100)}%"
                    except (ValueError, TypeError):
                        pct = "?"
                pools.append((pool_name, pct, when))
        out.append((email, pools))
    return out


def set_account_enabled(index, enabled=None):
    """Activa/desactiva (o alterna) la cuenta por indice 1-based."""
    accounts_file, data, accounts = load_accounts()
    if data is None:
        return False, "No hay cuentas guardadas."
    if index < 1 or index > len(accounts):
        return False, "Indice fuera de rango."
    target = accounts[index - 1]
    if enabled is None:
        enabled = not target.get("enabled", True)
    target["enabled"] = bool(enabled)
    if opencode_running():
        # No es bloqueante, solo se informa en el mensaje.
        pass
    backup_file(accounts_file)
    try:
        save_json(data, accounts_file)
    except OSError as e:
        return False, f"No se pudo guardar: {e}"
    state = "ACTIVA" if enabled else "DESACTIVADA"
    return True, f"Cuenta {index} -> {state}"


def reset_accounts():
    """Borra TODAS las cuentas (con respaldo)."""
    accounts_file, _data, _accounts = load_accounts()
    if not os.path.isfile(accounts_file):
        return False, "No hay cuentas que borrar."
    bak = backup_file(accounts_file)
    try:
        os.remove(accounts_file)
    except OSError as e:
        return False, f"No se pudo borrar: {e}"
    return True, f"Cuentas borradas. Respaldo: {bak or '(sin respaldo)'}"


def delete_account(index):
    """Elimina UNA cuenta por indice 1-based (con respaldo)."""
    accounts_file, data, accounts = load_accounts()
    if data is None:
        return False, "No hay cuentas guardadas."
    if index < 1 or index > len(accounts):
        return False, "Indice fuera de rango."
    removed = accounts[index - 1].get("email") or f"Cuenta {index}"
    del accounts[index - 1]
    data["accounts"] = accounts
    bak = backup_file(accounts_file)
    try:
        save_json(data, accounts_file)
    except OSError as e:
        return False, f"No se pudo guardar: {e}"
    return True, f"Cuenta eliminada: {removed}. Respaldo: {bak or '(sin respaldo)'}"


# ------------------------------------------------------------ plugin -------

def enable_plugin():
    config_dir = get_config_dir()
    config_file = get_config_file(config_dir) or os.path.join(config_dir, "opencode.json")

    if test_plugin_configured(config_file):
        return True, "El plugin ya estaba configurado."

    obj = read_json(config_file)
    if obj is None:
        obj = {"$schema": "https://opencode.ai/config.json", "plugin": []}

    plugins = obj.get("plugin") or []
    if isinstance(plugins, str):
        plugins = [plugins]
    plugins = list(plugins)
    if not any(isinstance(p, str) and PLUGIN_NAME in p for p in plugins):
        plugins.append(f"{PLUGIN_NAME}@latest")
    obj["plugin"] = plugins
    if not obj.get("$schema"):
        obj["$schema"] = "https://opencode.ai/config.json"

    backup_file(config_file)
    try:
        save_json(obj, config_file)
    except OSError as e:
        return False, f"No se pudo guardar la config: {e}"

    patched, checked = repair_plugin_node_compat()
    disable_plugin_auto_update()
    extra = f" | parche Node: {patched}/{checked}" if checked else ""
    return True, f"Plugin ACTIVADO en {config_file}{extra}. Reinicia OpenCode."


def disable_plugin():
    config_file = get_config_file()
    if not config_file:
        return False, "No hay archivo de config (opencode.json/jsonc)."
    if not test_plugin_configured(config_file):
        return True, "El plugin ya estaba desactivado."

    obj = read_json(config_file)
    if not obj:
        return False, "No se pudo leer la config."

    existing = obj.get("plugin") or []
    if isinstance(existing, str):
        existing = [existing]
    obj["plugin"] = [p for p in existing if not (isinstance(p, str) and PLUGIN_NAME in p)]

    provider = obj.get("provider")
    if isinstance(provider, dict):
        google = provider.get("google")
        if isinstance(google, dict):
            gmodels = google.get("models")
            if isinstance(gmodels, dict):
                for managed in MODELS:
                    gmodels.pop(managed, None)
                if not gmodels:
                    google.pop("models", None)
            if not google:
                provider.pop("google", None)
        if not provider:
            obj.pop("provider", None)

    backup_file(config_file)
    try:
        save_json(obj, config_file)
    except OSError as e:
        return False, f"No se pudo guardar: {e}"
    return True, "Plugin DESACTIVADO y modelos eliminados. Reinicia OpenCode."


def configure_models():
    config_dir = get_config_dir()
    config_file = get_config_file(config_dir) or os.path.join(config_dir, "opencode.json")

    obj = read_json(config_file)
    if obj is None:
        obj = {"$schema": "https://opencode.ai/config.json",
               "plugin": [f"{PLUGIN_NAME}@latest"]}

    provider = obj.get("provider")
    if not isinstance(provider, dict):
        provider = {}
        obj["provider"] = provider
    google = provider.get("google")
    if not isinstance(google, dict):
        google = {}
        provider["google"] = google

    merged = dict(google.get("models") or {})
    merged.update(MODELS)
    google["models"] = merged

    backup_file(config_file)
    try:
        save_json(obj, config_file)
    except OSError as e:
        return False, f"No se pudo guardar la config: {e}"

    patched, checked = repair_plugin_node_compat()
    return True, f"Modelos configurados en {config_file}. Reinicia OpenCode."


def remove_models():
    """Quita los modelos gestionados por Antigravity del provider google."""
    config_file = get_config_file()
    if not config_file:
        return False, "No hay archivo de config (opencode.json/jsonc)."
    obj = read_json(config_file)
    if not obj:
        return False, "No se pudo leer la config."
    provider = obj.get("provider")
    if not isinstance(provider, dict):
        return True, "No habia modelos gestionados que quitar."
    google = provider.get("google")
    if not isinstance(google, dict):
        return True, "No habia modelos gestionados que quitar."
    gmodels = google.get("models")
    if not isinstance(gmodels, dict):
        return True, "No habia modelos gestionados que quitar."
    removed = 0
    for managed in MODELS:
        if managed in gmodels:
            gmodels.pop(managed, None)
            removed += 1
    if not gmodels:
        google.pop("models", None)
    if not google:
        provider.pop("google", None)
    if not provider:
        obj.pop("provider", None)
    backup_file(config_file)
    try:
        save_json(obj, config_file)
    except OSError as e:
        return False, f"No se pudo guardar: {e}"
    return True, f"{removed} modelo(s) gestionado(s) eliminados de la config. Respaldada."


def _opencode_login_args():
    """Devuelve (ruta, lista_args) para 'opencode auth login' con Antigravity."""
    opc = get_opencode_path()
    if not opc:
        return None, None
    _rc, help_out = C.run_program([opc, "auth", "login", "--help"], timeout=25)
    if "--provider" in (help_out or ""):
        args = [opc, "auth", "login", "-p", "google", "-m", "OAuth with Google (Antigravity)"]
    else:
        args = [opc, "auth", "login"]
    return opc, args


def _opencode_missing_msg():
    return ("No se encontro OpenCode en este equipo.\n\n"
            "Instalalo con:  npm install -g opencode-ai\n"
            "Luego pulsa 'Crear / Instalar OpenCode' en 'PATH / OpenCode'.")


def open_plugin_login_console():
    """Abre la consola del gestor OAuth del plugin (menu interactivo completo)."""
    opc, args = _opencode_login_args()
    if not opc:
        return False, _opencode_missing_msg()
    if not C.open_new_console(args, title="Antigravity OAuth"):
        return False, "No se pudo abrir la consola de OpenCode."
    return True, "Menu del plugin abierto. Sigue las instrucciones."


def open_plugin_menu(action="add", index=None):
    """
    Abre la consola del plugin con una accion PRESELECCIONADA.

    action: 'add' | 'check' | 'verify' | 'verify-all'
    index:  numero de cuenta (1-based) para 'verify'.

    Se usa el modo no-interactivo del plugin (stdin por tuberia), que acepta
    comandos escritos: c = cuotas, v + numero = verificar una, va = verificar
    todas. Para 'add' se abre el menu normal (la opcion "Add account" ya viene
    seleccionada por defecto).
    """
    opc, args = _opencode_login_args()
    if not opc:
        return False, _opencode_missing_msg()
    base = subprocess.list2cmdline([str(a) for a in args])
    if action == "add":
        inner = base
        note = "Menu del plugin abierto: elige 'Add account' (ya esta resaltado)."
    else:
        if action == "verify-all":
            feed = "(echo va)"
            label = "Verificar todas las cuentas"
        elif action == "verify":
            feed = f"(echo v& echo {int(index or 1)})"
            label = f"Verificar cuenta {int(index or 1)}"
        else:
            feed = "(echo c)"
            label = "Ver cuotas"
        inner = f"{feed} | {base}"
        banner = f"echo [NEXUS] {label} (preseleccionado). Cierra esta ventana al terminar."
        inner = f"{banner} & {inner}"
        note = (f"Consola abierta: {label} (preseleccionado). "
                "Veras el resultado real; cierra la ventana al terminar.")
    if not C.open_new_console(inner, title="Antigravity OAuth"):
        return False, "No se pudo abrir la consola de OpenCode."
    return True, note


# ------------------------------------------------------ diagnostico ---------

def diagnostics():
    """Diagnostico completo como dict (para mostrar en la GUI)."""
    cfg_dir = get_config_dir()
    cfg_file = get_config_file(cfg_dir)
    configured = test_plugin_configured(cfg_file)
    cached = test_plugin_cached()
    accounts_file, _data, accounts = load_accounts()
    cache_dirs = get_plugin_cache_dirs()
    return {
        "opencode_path": get_opencode_path(),
        "config_dir": cfg_dir,
        "config_file": cfg_file,
        "plugin_configured": configured,
        "plugin_cached": cached,
        "accounts_file": accounts_file,
        "accounts_count": len(accounts),
        "cache_dirs": len(cache_dirs),
        "opencode_running": opencode_running(),
        "node": C.which("node"),
        "npm": C.which("npm"),
    }


# --------------------------------------------------- API key de Google ------

def get_google_api_key():
    return os.environ.get("GOOGLE_GENERATIVE_AI_API_KEY") or os.environ.get("GEMINI_API_KEY")


def set_google_api_key(key):
    if not key:
        return False, "La clave esta vacia."
    for var in ("GOOGLE_GENERATIVE_AI_API_KEY", "GEMINI_API_KEY"):
        try:
            subprocess.run(["setx", var, key], capture_output=True, timeout=15,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except Exception:
            pass
        os.environ[var] = key
    return True, "API key guardada (persiste en procesos nuevos)."


def clear_google_api_key():
    for var in ("GOOGLE_GENERATIVE_AI_API_KEY", "GEMINI_API_KEY"):
        try:
            subprocess.run(["reg", "delete", "HKCU\\Environment", "/v", var, "/f"],
                           capture_output=True, timeout=15,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except Exception:
            pass
        os.environ.pop(var, None)
    return True, "API key eliminada (sesion y registro de usuario)."


def mask_key(key):
    if not key:
        return "(ninguna)"
    if len(key) > 8:
        return key[:4] + "..." + key[-4:]
    return "(definida)"


# --------------------------------------------------------- mantenimiento ----

def repair_plugin():
    dirs = get_plugin_cache_dirs()
    installed = False
    if not dirs:
        ok, msg = install_plugin_to_cache()
        installed = ok
        if not ok:
            return False, msg, 0, 0
    patched, checked = repair_plugin_node_compat()
    disable_plugin_auto_update()
    if checked == 0:
        return True, "Cache del plugin vacia: se parcheara tras instalarla.", patched, checked
    if patched > 0:
        return True, f"Parche Node aplicado a {patched} de {checked} archivo(s).", patched, checked
    return True, f"Plugin ya compatible con Node ({checked} archivo(s) revisados).", patched, checked


def auto_configure_plugin():
    """
    Activa el plugin Antigravity automaticamente en equipos nuevos
    (silencioso). No hace nada si ya esta configurado.
    """
    try:
        if test_plugin_configured():
            return False
        ok, _msg = enable_plugin()
        return bool(ok)
    except Exception:
        return False


def startup_silent_repair():
    try:
        auto_configure_plugin()
    except Exception:
        pass
    try:
        repair_plugin_node_compat()
    except Exception:
        pass
