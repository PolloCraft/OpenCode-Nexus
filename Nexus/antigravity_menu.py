import os
import sys
import re
import json
import shutil
import datetime
import subprocess
import webbrowser

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


# ------------------------------------------------------------------ UI -----

def clear():
    os.system('cls' if os.name == 'nt' else 'clear')


def pause():
    print()
    input("  Presione Enter para continuar...")


def print_banner():
    print()
    print("  \033[35m========================================================\033[0m")
    print("  \033[1;35m   ANTIGRAVITY + OPENCODE  -  GESTOR DE CUENTAS\033[0m")
    print("  \033[35m========================================================\033[0m")
    print()


def print_section(title):
    print()
    print(f"  \033[35m{'=' * 54}\033[0m")
    print(f"   \033[1;37m{title}\033[0m")
    print(f"  \033[35m{'=' * 54}\033[0m")
    print()


def print_option(num, text, desc=""):
    if desc:
        print(f"  \033[35m[{num}]\033[0m {text:40} \033[90m- {desc}\033[0m")
    else:
        print(f"  \033[35m[{num}]\033[0m {text}")


def ok(text):
    print(f"  \033[32m[OK]\033[0m {text}")


def warn(text):
    print(f"  \033[33m[!]\033[0m {text}")


def err(text):
    print(f"  \033[31m[ERROR]\033[0m {text}")


def note(text):
    print(f"  \033[90m- {text}\033[0m")


# --------------------------------------------------------------- utils -----

def strip_json_comments(text):
    sb = []
    in_string = False
    in_line = False
    in_block = False
    escaped = False
    i = 0
    n = len(text)
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
    shutil.copy2(path, dest)
    return dest


# ---------------------------------------------------------------- paths ----

def get_user_home():
    home = os.environ.get("USERPROFILE") or os.environ.get("HOME") or os.path.expanduser("~")
    return home


def get_config_dir():
    env_dir = os.environ.get("OPENCODE_CONFIG_DIR", "")
    if env_dir and os.path.isdir(env_dir):
        return os.path.abspath(env_dir)
    candidates = []
    xdg = os.environ.get("XDG_CONFIG_HOME", "")
    if xdg:
        candidates.append(os.path.join(xdg, "opencode"))
    candidates.append(os.path.join(get_user_home(), ".config", "opencode"))
    appdata = os.environ.get("APPDATA", "")
    if appdata:
        candidates.append(os.path.join(appdata, "opencode"))
    for c in candidates:
        if os.path.isdir(c):
            return c
    return candidates[0] if candidates else os.path.join(get_user_home(), ".config", "opencode")


def get_config_file(config_dir):
    jsonc = os.path.join(config_dir, "opencode.jsonc")
    json_path = os.path.join(config_dir, "opencode.json")
    if os.path.isfile(jsonc):
        return jsonc
    if os.path.isfile(json_path):
        return json_path
    return None


def get_accounts_file(config_dir):
    primary = os.path.join(config_dir, "antigravity-accounts.json")
    if os.path.isfile(primary):
        return primary
    appdata = os.environ.get("APPDATA", "")
    if appdata:
        legacy = os.path.join(appdata, "opencode", "antigravity-accounts.json")
        if os.path.isfile(legacy):
            return legacy
    return primary


def get_opencode_path():
    found = shutil.which("opencode")
    if found:
        return found
    ps1 = shutil.which("opencode.ps1")
    if ps1:
        return ps1
    return None


def get_plugin_cache_roots():
    home = get_user_home()
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
    seen = set()
    unique = []
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


def test_plugin_configured(config_file):
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
    try:
        result = subprocess.run(
            ["tasklist", "/FO", "CSV", "/NH"],
            capture_output=True, text=True, timeout=10,
        )
        return "opencode" in (result.stdout or "").lower()
    except Exception:
        return False


# ------------------------------------------- parche Node compatibilidad -----

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
        return
    obj["auto_update"] = False
    backup_file(path)
    try:
        save_json(obj, path)
        note("Auto-update del plugin desactivado (el parche se mantiene).")
    except OSError as e:
        warn(f"No se pudo escribir antigravity.json: {e}")


def invoke_node_repair():
    try:
        patched, checked = repair_plugin_node_compat()
        if checked == 0:
            note("Cache del plugin vacia: se parcheara tras instalarla (opcion 8).")
        elif patched > 0:
            ok(f"Parche Node aplicado a {patched} archivo(s) (app escritorio lista).")
        else:
            ok("Plugin ya compatible con Node: nada que parchear.")
    except Exception as e:
        warn(f"No se pudo parchear el plugin: {e}")
    disable_plugin_auto_update()


def install_plugin_to_cache():
    root = None
    for r in get_plugin_cache_roots():
        if os.path.isdir(r):
            root = r
            break
    if not root:
        root = os.path.join(get_user_home(), ".cache", "opencode", "packages")
    cache_dir = os.path.join(root, f"{PLUGIN_NAME}@latest")
    os.makedirs(cache_dir, exist_ok=True)
    npm = shutil.which("npm")
    if not npm:
        return False
    try:
        subprocess.run(
            [npm, "install", f"{PLUGIN_NAME}@latest", "--prefix", cache_dir, "--no-audit", "--no-fund"],
            capture_output=True, timeout=600,
        )
    except Exception:
        return False
    return os.path.isdir(os.path.join(cache_dir, "node_modules", PLUGIN_NAME))


# ------------------------------------------------------------- acciones -----

def diagnostics():
    clear()
    print_banner()
    print_section("DIAGNOSTICO DEL SISTEMA")

    opencode_path = get_opencode_path()
    if opencode_path:
        ok(f"opencode: {opencode_path}")
    else:
        err("opencode: NO encontrado en el PATH")

    config_dir = get_config_dir()
    config_file = get_config_file(config_dir)
    note(f"Carpeta de config: {config_dir}")
    if config_file:
        note(f"Archivo de config: {config_file}")
    else:
        warn("Archivo de config: no existe (opencode.json/jsonc)")

    configured = test_plugin_configured(config_file)
    cached = test_plugin_cached()
    if configured:
        ok("Plugin Antigravity configurado en opencode.json(c)")
    else:
        warn('Plugin Antigravity NO esta en la lista "plugin" de la config')
    if cached:
        ok("Paquete del plugin descargado en cache")
    else:
        note("Paquete del plugin: aun no en cache (se descarga al primer uso)")

    accounts_file = get_accounts_file(config_dir)
    if os.path.isfile(accounts_file):
        data = read_json(accounts_file)
        accounts = (data or {}).get("accounts") or []
        ok(f"Cuentas guardadas: {len(accounts)}  ({accounts_file})")
    else:
        warn(f"Cuentas: no hay archivo {accounts_file}")

    cache_dirs = get_plugin_cache_dirs()
    if cache_dirs:
        note(f"Cache del plugin: {len(cache_dirs)} carpeta(s)")
    else:
        note("Cache del plugin: aun no descargada")

    print()
    if configured and opencode_path:
        ok("Todo listo: puedes agregar cuentas (opcion 5).")
    elif not configured:
        warn("Plugin desactivado: usa la opcion 6 para activarlo.")
    pause()


def _load_accounts():
    config_dir = get_config_dir()
    accounts_file = get_accounts_file(config_dir)
    if not os.path.isfile(accounts_file):
        return accounts_file, None
    data = read_json(accounts_file)
    return accounts_file, data


def show_accounts():
    clear()
    print_banner()
    print_section("CUENTAS GUARDADAS")
    accounts_file, data = _load_accounts()
    if data is None:
        warn("No hay cuentas guardadas todavia.")
        note("Usa la opcion 5 para iniciar sesion con Google.")
        pause()
        return
    accounts = data.get("accounts") or []
    if not accounts:
        warn("El archivo de cuentas no tiene cuentas validas.")
        pause()
        return
    for i, account in enumerate(accounts, start=1):
        email = account.get("email") or f"Cuenta {i}"
        enabled = account.get("enabled", True)
        state = "ACTIVA" if enabled else "DESACTIVADA"
        if enabled:
            print(f"  \033[32m{i}. {email}   [{state}]\033[0m")
        else:
            print(f"  \033[90m{i}. {email}   [{state}]\033[0m")
        project_id = account.get("projectId")
        if project_id:
            note(f"    projectId: {project_id}")
        added = account.get("addedAt")
        if added:
            try:
                dt = datetime.datetime.fromtimestamp(int(added) / 1000)
                note(f"    agregada: {dt.strftime('%Y-%m-%d %H:%M')}")
            except (ValueError, OSError, OverflowError):
                pass
    print()
    note(f"Total: {len(accounts)} cuenta(s)")
    pause()


def show_quotas():
    clear()
    print_banner()
    print_section("CUOTAS (cache local)")
    accounts_file, data = _load_accounts()
    if data is None:
        warn("No hay cuentas guardadas todavia.")
        pause()
        return
    accounts = data.get("accounts") or []
    if not accounts:
        warn("Sin datos de cuotas.")
        pause()
        return
    for i, account in enumerate(accounts, start=1):
        email = account.get("email") or f"Cuenta {i}"
        print(f"  \033[1;37m{email}\033[0m")
        quota = account.get("cachedQuota")
        if not quota:
            note("    (sin datos de cuota en cache)")
        else:
            if isinstance(quota, dict):
                for pool_name, info in quota.items():
                    if not isinstance(info, dict):
                        continue
                    frac = info.get("remainingFraction")
                    when = info.get("resetTime")
                    pct = "?"
                    if frac is not None:
                        try:
                            pct = f"{round(float(frac) * 100)}%"
                        except (ValueError, TypeError):
                            pct = "?"
                    line = f"    {pool_name}: {pct} disponible"
                    if when:
                        line += f"  (reset: {when})"
                    note(line)
    print()
    note("Para actualizar cuotas en red usa la opcion 5 (menu del plugin).")
    pause()


def set_account_enabled():
    clear()
    print_banner()
    print_section("ACTIVAR / DESACTIVAR CUENTA")
    accounts_file, data = _load_accounts()
    if data is None:
        warn("No hay cuentas guardadas.")
        pause()
        return
    accounts = data.get("accounts") or []
    if not accounts:
        warn("No hay cuentas guardadas.")
        pause()
        return

    for i, account in enumerate(accounts, start=1):
        email = account.get("email") or f"Cuenta {i}"
        enabled = account.get("enabled", True)
        state = "ACTIVA" if enabled else "DESACTIVADA"
        print(f"  \033[35m{i})\033[0m {email}  [{state}]")

    print()
    sel = input("  Numero de cuenta (ENTER para cancelar): ").strip()
    if sel == "":
        return
    try:
        idx = int(sel)
    except ValueError:
        warn("Entrada no valida.")
        pause()
        return
    if idx < 1 or idx > len(accounts):
        warn("Numero fuera de rango.")
        pause()
        return
    if opencode_running():
        warn("opencode parece estar abierto; cierralo para evitar conflictos.")

    target = accounts[idx - 1]
    new_state = not target.get("enabled", True)
    target["enabled"] = new_state

    bak = backup_file(accounts_file)
    try:
        save_json(data, accounts_file)
        ok(f"Cuenta {idx} -> {'ACTIVA' if new_state else 'DESACTIVADA'}")
        if bak:
            note(f"Respaldo: {bak}")
    except OSError as e:
        err(f"No se pudo guardar: {e}")
    pause()


def _run_opencode(args, timeout=300):
    opencode_path = get_opencode_path()
    if not opencode_path:
        return None, "opencode no encontrado"
    try:
        result = subprocess.run(
            [opencode_path] + args,
            capture_output=True, text=True, timeout=timeout,
        )
        out = (result.stdout or "") + (result.stderr or "")
        return result.returncode, out
    except Exception as e:
        return None, str(e)


def open_plugin_menu():
    clear()
    print_banner()
    print_section("AGREGAR CUENTA / MENU DEL PLUGIN")
    opencode_path = get_opencode_path()
    if not opencode_path:
        err("No se encontro opencode en el PATH.")
        pause()
        return

    config_dir = get_config_dir()
    config_file = get_config_file(config_dir)
    if not test_plugin_configured(config_file):
        warn("El plugin Antigravity no esta activado en la configuracion.")
        note("Sin el plugin, opencode mostrara su menu generico (pide API keys).")
        print()
        yn = input("  Activar el plugin ahora? (s/n): ").strip().lower()
        if yn not in ("s", "si", "y", "yes"):
            note("Cancelado.")
            pause()
            return
        enable_plugin(silent=True)
        config_file = get_config_file(get_config_dir())

    print()
    code, help_out = _run_opencode(["auth", "login", "--help"], timeout=30)
    supports_flags = False
    if help_out and "--provider" in help_out:
        supports_flags = True

    note("Abriendo el gestor del plugin...")
    note("Con cuentas guardadas veras: Add / Check quotas / Verify / Manage.")
    print()
    try:
        if supports_flags:
            print(f"  \033[90mEjecutando: opencode auth login -p google -m 'OAuth with Google (Antigravity)'\033[0m")
            subprocess.run(
                [opencode_path, "auth", "login", "-p", "google", "-m", "OAuth with Google (Antigravity)"],
                timeout=900,
            )
        else:
            warn("Tu version de opencode no acepta -p/-m; elige manualmente:")
            note("   Google -> OAuth with Google (Antigravity)")
            subprocess.run([opencode_path, "auth", "login"], timeout=900)
    except Exception as e:
        err(f"opencode termino con un error: {e}")
    print()
    pause()


def enable_plugin(silent=False):
    if not silent:
        clear()
        print_banner()
        print_section("ACTIVAR PLUGIN EN OPENCODE")
    config_dir = get_config_dir()
    config_file = get_config_file(config_dir) or os.path.join(config_dir, "opencode.json")

    if test_plugin_configured(config_file):
        ok("El plugin ya esta configurado.")
        if not silent:
            pause()
        return

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

    bak = backup_file(config_file)
    try:
        save_json(obj, config_file)
        ok(f"Plugin activado en: {config_file}")
        if bak:
            note(f"Respaldo: {bak}")
        invoke_node_repair()
        note("Reinicia opencode para que se cargue el plugin.")
    except OSError as e:
        err(f"No se pudo guardar la config: {e}")
    if not silent:
        pause()


def disable_plugin(silent=False):
    if not silent:
        clear()
        print_banner()
        print_section("DESACTIVAR PLUGIN EN OPENCODE")
    config_dir = get_config_dir()
    config_file = get_config_file(config_dir)
    if not config_file:
        warn("No hay archivo de config (opencode.json/jsonc).")
        if not silent:
            pause()
        return
    if not test_plugin_configured(config_file):
        ok("El plugin ya esta desactivado.")
        if not silent:
            pause()
        return

    obj = read_json(config_file)
    if not obj:
        warn("No se pudo leer la config.")
        if not silent:
            pause()
        return

    existing = obj.get("plugin") or []
    if isinstance(existing, str):
        existing = [existing]
    kept = [p for p in existing if not (isinstance(p, str) and PLUGIN_NAME in p)]
    obj["plugin"] = kept

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

    bak = backup_file(config_file)
    try:
        save_json(obj, config_file)
        ok("Plugin DESACTIVADO y modelos eliminados de la config.")
        note(f"Config: {config_file}")
        if bak:
            note(f"Respaldo: {bak}")
        note("Reinicia opencode para que surta efecto.")
    except OSError as e:
        err(f"No se pudo guardar: {e}")
    if not silent:
        pause()


def toggle_plugin():
    clear()
    print_banner()
    config_file = get_config_file(get_config_dir())
    if test_plugin_configured(config_file):
        disable_plugin()
    else:
        enable_plugin()


def configure_models():
    clear()
    print_banner()
    print_section("CONFIGURAR MODELOS EN OPENCODE")
    config_dir = get_config_dir()
    config_file = get_config_file(config_dir) or os.path.join(config_dir, "opencode.json")

    obj = read_json(config_file)
    if obj is None:
        obj = {
            "$schema": "https://opencode.ai/config.json",
            "plugin": [f"{PLUGIN_NAME}@latest"],
        }

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

    bak = backup_file(config_file)
    try:
        save_json(obj, config_file)
        ok(f"Modelos configurados en: {config_file}")
        if bak:
            note(f"Respaldo: {bak}")
        invoke_node_repair()
        note("Reinicia opencode para ver los modelos nuevos.")
    except OSError as e:
        err(f"No se pudo guardar la config: {e}")
    pause()


def reset_all():
    clear()
    print_banner()
    print_section("BORRAR TODO (RESET CON RESPALDO)")
    accounts_file, _data = _load_accounts()
    if not os.path.isfile(accounts_file):
        warn("No hay cuentas que borrar.")
        pause()
        return
    if opencode_running():
        warn("opencode parece estar abierto. Cierralo antes de continuar.")
    warn("Esto quita TODAS las cuentas guardadas (se guarda un respaldo).")
    print()
    yn = input("  Escribe SI para confirmar: ").strip().upper()
    if yn != "SI":
        note("Cancelado.")
        pause()
        return
    bak = backup_file(accounts_file)
    try:
        os.remove(accounts_file)
        ok("Cuentas borradas.")
        if bak:
            note(f"Respaldo guardado en: {bak}")
    except OSError as e:
        err(f"No se pudo borrar: {e}")
    pause()


def repair_plugin_menu():
    clear()
    print_banner()
    print_section("REPARAR PLUGIN (COMPATIBILIDAD APP ESCRITORIO)")
    note("La app de escritorio usa Node; el plugin viene listo solo para Bun.")
    note("Este parche local hace que el plugin cargue en ambos. No usa red.")
    print()

    dirs = get_plugin_cache_dirs()
    if not dirs:
        warn("El plugin no esta en cache todavia.")
        yn = input("  Instalarlo ahora (requiere internet)? (s/n): ").strip().lower()
        if yn not in ("s", "si", "y", "yes"):
            note("Cancelado.")
            pause()
            return
        note("Descargando plugin...")
        if not install_plugin_to_cache():
            err("No se pudo instalar (falta npm o fallo de red).")
            pause()
            return
        ok("Plugin instalado en cache.")

    patched, checked = repair_plugin_node_compat()
    if patched > 0:
        ok(f"Parche aplicado a {patched} de {checked} archivo(s).")
    elif checked > 0:
        ok(f"Nada que parchear: los {checked} archivo(s) ya eran compatibles.")
    else:
        warn("No se encontraron archivos .js del plugin para parchear.")
    disable_plugin_auto_update()
    note("Reinicia la app de escritorio si estaba abierta.")
    pause()


def _mask_key(key):
    if not key:
        return "(ninguna)"
    if len(key) > 8:
        return key[:4] + "..." + key[-4:]
    return "(definida)"


def set_google_api_key():
    clear()
    print_banner()
    print_section("API KEY DE GOOGLE (camino sin plugin)")
    note('Este es el camino "normal" de Google: usa una API key en vez de OAuth.')
    note("Con el plugin desactivado, los modelos google/gemini-* usan tu key.")
    note("(Los modelos antigravity-* solo funcionan con OAuth, no con API key.)")
    print()

    current = os.environ.get("GOOGLE_GENERATIVE_AI_API_KEY") or os.environ.get("GEMINI_API_KEY")
    note(f"API key actual: {_mask_key(current)}")
    print()

    key = input("  Pega tu API key (ENTER vacio = quitar la key): ").strip()

    if key == "":
        for var in ("GOOGLE_GENERATIVE_AI_API_KEY", "GEMINI_API_KEY"):
            subprocess.run(
                ["reg", "delete", "HKCU\\Environment", "/v", var, "/f"],
                capture_output=True, timeout=10,
            )
            os.environ.pop(var, None)
        ok("API key eliminada (sesion y registro de usuario).")
        note("Reinicia opencode/terminal para que surta efecto.")
        pause()
        return

    for var in ("GOOGLE_GENERATIVE_AI_API_KEY", "GEMINI_API_KEY"):
        try:
            subprocess.run(["setx", var, key], capture_output=True, timeout=10)
        except Exception:
            pass
        os.environ[var] = key
    ok("API key guardada (persiste en procesos nuevos).")

    if test_plugin_configured(get_config_file(get_config_dir())):
        warn("El plugin sigue activo y podria ignorar tu API key en los modelos google/*.")
        yn = input("  Desactivar el plugin ahora? (recomendado) (s/n): ").strip().lower()
        if yn in ("s", "si", "y", "yes"):
            disable_plugin(silent=True)
        else:
            note("Si ignora la key, usala con la opcion 6 (desactivar plugin).")
    print()
    note("Reinicia opencode (y la app de escritorio) para usar la API key.")
    pause()


# ------------------------------------------------------------------ menu ----

def show_menu():
    while True:
        clear()
        print_banner()
        print_section("GESTOR DE CUENTAS  -  ANTIGRAVITY")

        config_file = get_config_file(get_config_dir())
        configured = test_plugin_configured(config_file)
        status = "\033[32mACTIVO\033[0m" if configured else "\033[33mDESACTIVADO\033[0m"
        print(f"  \033[90mPlugin: {status}\033[0m")
        print(f"  \033[90mConfig: {get_config_dir()}\033[0m")

        print()
        print_option("1", "Diagnostico / estado del sistema")
        print_option("2", "Ver cuentas guardadas")
        print_option("3", "Ver cuotas (cache local)")
        print_option("4", "Activar / desactivar una cuenta")
        print_option("5", "Agregar cuenta / abrir menu del plugin")
        print_option("6", "Activar / Desactivar plugin (+ modelos)")
        print_option("7", "Configurar modelos en opencode")
        print_option("8", "Reparar plugin (app escritorio / Node)")
        print_option("9", "API key de Google (camino sin plugin)")
        print_option("10", "Borrar TODO (reset con respaldo)")
        print_option("0", "Volver al menu principal")
        print()
        print(f"  \033[35m{'=' * 54}\033[0m")
        print()

        opt = input("  \033[1;35m>>\033[0m Selecciona: ").strip()
        if opt == "1":
            diagnostics()
        elif opt == "2":
            show_accounts()
        elif opt == "3":
            show_quotas()
        elif opt == "4":
            set_account_enabled()
        elif opt == "5":
            open_plugin_menu()
        elif opt == "6":
            toggle_plugin()
        elif opt == "7":
            configure_models()
        elif opt == "8":
            repair_plugin_menu()
        elif opt == "9":
            set_google_api_key()
        elif opt == "10":
            reset_all()
        elif opt == "0":
            break


def startup_silent_repair():
    try:
        repair_plugin_node_compat()
    except Exception:
        pass
