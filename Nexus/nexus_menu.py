import os
import sys
import subprocess
import ctypes
import time
import webbrowser
import random
import shutil

VERSION = "6.0.0 Nexus"
ANTIGRAVITY_FOLDER_NAME = "antigravity"
OPLIRE_FOLDER_NAME = "oplire"
EVERYTHING_URL = "https://www.voidtools.com/es-es/"
CLOUDFLARE_CLIENT_URL = "https://developers.cloudflare.com/cloudflare-one/team-and-resources/devices/cloudflare-one-client/download/"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
]

try:
    import antigravity_menu
except ImportError:
    antigravity_menu = None


def clear():
    os.system('cls' if os.name == 'nt' else 'clear')


def pause():
    print()
    input("  Presione Enter para continuar...")


def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


def run_as_admin():
    if is_admin():
        return True
    try:
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, " ".join(sys.argv), None, 1
        )
        return False
    except Exception:
        return False


def get_script_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def is_oplire_project_dir(path):
    if not path or not os.path.isdir(path):
        return False
    return os.path.isfile(os.path.join(path, "Cargo.toml")) or os.path.isfile(
        os.path.join(path, "src", "main.rs")
    )


def is_antigravity_project_dir(path):
    if not path or not os.path.isdir(path):
        return False
    if os.path.isfile(os.path.join(path, "Gestor-Antigravity.ps1")):
        return True
    return os.path.isfile(os.path.join(path, "package.json")) and os.path.isdir(
        os.path.join(path, "src")
    )


def find_oplire_exe_in(folder):
    for sub in ["target/release", "target/debug"]:
        exe = os.path.join(folder, sub, "oplire.exe")
        if os.path.isfile(exe):
            return exe
    return None


def resolve_system_dirs():
    script_dir = get_script_dir()
    oplire_dir = os.path.join(script_dir, OPLIRE_FOLDER_NAME)
    antigravity_dir = os.path.join(script_dir, ANTIGRAVITY_FOLDER_NAME)

    if not is_oplire_project_dir(oplire_dir):
        env = os.environ.get("OPLIRE_PROJECT_PATH", "")
        if env and is_oplire_project_dir(env):
            oplire_dir = env
        else:
            oplire_dir = None

    if not is_antigravity_project_dir(antigravity_dir):
        env = os.environ.get("ANTIGRAVITY_PROJECT_PATH", "")
        if env and is_antigravity_project_dir(env):
            antigravity_dir = env
        else:
            antigravity_dir = None

    return oplire_dir, antigravity_dir


def check_everything_installed():
    try:
        result = subprocess.run(
            ["es", "-version"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return True
    except Exception:
        pass

    everything_paths = [
        os.path.join(os.environ.get("PROGRAMFILES", ""), "Everything", "Everything.exe"),
        os.path.join(os.environ.get("PROGRAMFILES(X86)", ""), "Everything", "Everything.exe"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Everything", "Everything.exe"),
    ]
    for path in everything_paths:
        if os.path.isfile(path):
            return True
    return False


def check_cloudflare_client_installed():
    try:
        result = subprocess.run(
            ["warp-cli", "--version"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return True, result.stdout.strip()
    except Exception:
        pass

    cf_paths = [
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Cloudflare", "Cloudflare WARP", "warp-cli.exe"),
        os.path.join(os.environ.get("PROGRAMFILES", ""), "Cloudflare", "Cloudflare WARP", "warp-cli.exe"),
        os.path.join(os.environ.get("PROGRAMFILES(X86)", ""), "Cloudflare", "Cloudflare WARP", "warp-cli.exe"),
    ]
    for path in cf_paths:
        if os.path.isfile(path):
            return True, path

    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-ItemProperty 'HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*' | Where-Object { $_.DisplayName -like '*Cloudflare*' } | Select-Object -ExpandProperty DisplayName"],
            capture_output=True, text=True, timeout=10
        )
        if result.stdout.strip():
            return True, result.stdout.strip()
    except Exception:
        pass

    return False, "No encontrado"


def get_random_user_agent():
    return random.choice(USER_AGENTS)


def random_delay(min_ms=100, max_ms=500):
    time.sleep(random.uniform(min_ms / 1000, max_ms / 1000))


def run_cmd(cmd, work_dir=None):
    if work_dir:
        full_cmd = f'cmd /k "cd /d "{work_dir}" && {cmd}"'
    else:
        full_cmd = f'cmd /k "{cmd}"'
    subprocess.Popen(full_cmd, shell=True)


def run_oplire(subcmd, work_dir):
    exe = find_oplire_exe_in(work_dir)
    if not exe:
        run_cmd(f'echo [ERROR] oplire.exe no encontrado en {work_dir}', work_dir)
        return
    cmd = f'"{exe}" {subcmd}'
    run_cmd(cmd, work_dir)


def run_ps(cmd):
    ps_cmd = f'powershell -NoProfile -Command "{cmd}; Write-Host ''; Write-Host Presione Enter para cerrar...; Read-Host"'
    subprocess.Popen(f'cmd /k {ps_cmd}', shell=True)


def print_banner():
    print()
    print("  \033[36m╔══════════════════════════════════════════════════════════════╗\033[0m")
    print("  \033[36m║\033[0m                                                            \033[36m║\033[0m")
    print("  \033[36m║\033[0m   \033[1;36m███╗   ██╗███████╗██╗  ██╗██╗   ██╗███████╗\033[0m             \033[36m║\033[0m")
    print("  \033[36m║\033[0m   \033[1;36m████╗  ██║██╔════╝╚██╗██╔╝██║   ██║██╔════╝\033[0m             \033[36m║\033[0m")
    print("  \033[36m║\033[0m   \033[1;36m██╔██╗ ██║█████╗   ╚███╔╝ ██║   ██║███████╗\033[0m             \033[36m║\033[0m")
    print("  \033[36m║\033[0m   \033[1;36m██║╚██╗██║██╔══╝   ██╔██╗ ██║   ██║╚════██║\033[0m             \033[36m║\033[0m")
    print("  \033[36m║\033[0m   \033[1;36m██║ ╚████║███████╗██╔╝ ██╗╚██████╔╝███████║\033[0m             \033[36m║\033[0m")
    print("  \033[36m║\033[0m   \033[1;36m╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚══════╝\033[0m             \033[36m║\033[0m")
    print("  \033[36m║\033[0m                                                            \033[36m║\033[0m")
    print("  \033[36m║\033[0m   \033[1;33mSuite Unificada: Oplire + Antigravity\033[0m                  \033[36m║\033[0m")
    print("  \033[36m║\033[0m   \033[90mVersion {}\033[0m                                          \033[36m║\033[0m".format(VERSION))
    print("  \033[36m║\033[0m                                                            \033[36m║\033[0m")
    print("  \033[36m╚══════════════════════════════════════════════════════════════╝\033[0m")
    print()


def print_section(title):
    print()
    print(f"  \033[36m{'=' * 54}\033[0m")
    print(f"   \033[1;37m{title}\033[0m")
    print(f"  \033[36m{'=' * 54}\033[0m")
    print()


def print_option(num, text, desc=""):
    if desc:
        print(f"  \033[36m[{num}]\033[0m {text:25} \033[90m- {desc}\033[0m")
    else:
        print(f"  \033[36m[{num}]\033[0m {text}")


def print_status(ok_flag, text):
    if ok_flag:
        print(f"  \033[32m[OK]\033[0m {text}")
    else:
        print(f"  \033[31m[!!]\033[0m {text}")


def tools_menu():
    while True:
        clear()
        print_banner()
        print_section("HERRAMIENTAS")

        everything_installed = check_everything_installed()
        cf_installed, cf_info = check_cloudflare_client_installed()

        print_status(everything_installed, f"Everything:       {'INSTALADO' if everything_installed else 'NO INSTALADO'}")
        print_status(cf_installed, f"Cloudflare Client: {'INSTALADO (' + cf_info + ')' if cf_installed else 'NO INSTALADO'}")

        print()
        print_option("1", "Descargar Everything")
        print_option("2", "Descargar Cloudflare One Client")
        print_option("3", "Abrir Everything (si instalado)")
        print_option("4", "Verificar estado WARP")
        print_option("0", "Volver")
        print()
        print(f"  \033[36m{'=' * 54}\033[0m")
        print()
        opt = input("  \033[1;36m>>\033[0m Selecciona: ").strip()

        if opt == "1":
            clear()
            print_banner()
            print()
            print("  Abriendo pagina de Everything...")
            webbrowser.open(EVERYTHING_URL)
            time.sleep(1)
            print(f"  URL: {EVERYTHING_URL}")
            pause()
        elif opt == "2":
            clear()
            print_banner()
            print()
            print("  Abriendo pagina de Cloudflare One Client...")
            webbrowser.open(CLOUDFLARE_CLIENT_URL)
            time.sleep(1)
            print(f"  URL: {CLOUDFLARE_CLIENT_URL}")
            pause()
        elif opt == "3":
            if everything_installed:
                everything_paths = [
                    os.path.join(os.environ.get("PROGRAMFILES", ""), "Everything", "Everything.exe"),
                    os.path.join(os.environ.get("PROGRAMFILES(X86)", ""), "Everything", "Everything.exe"),
                    os.path.join(os.environ.get("LOCALAPPDATA", ""), "Everything", "Everything.exe"),
                ]
                for path in everything_paths:
                    if os.path.isfile(path):
                        subprocess.Popen([path])
                        print(f"\n  Everything abierto: {path}")
                        break
            else:
                print("\n  Everything no esta instalado")
                print("  Usa opcion [1] para descargar")
            pause()
        elif opt == "4":
            run_ps("if (Get-Command warp-cli -ErrorAction SilentlyContinue) { Write-Host '[OK] WARP:' (warp-cli --version); warp-cli status } else { Write-Host '[OFF] WARP CLI no encontrado' }")
        elif opt == "0":
            break


def dashboard_menu(work_dir):
    while True:
        clear()
        print_banner()
        print_section("PANEL DE CONTROL OPLIRE")

        print_option("1", "Iniciar Dashboard")
        print_option("2", "Detener todos oplire.exe")
        print_option("3", "Verificar estado")
        print_option("0", "Volver")
        print()
        print(f"  \033[36m{'=' * 54}\033[0m")
        print()
        opt = input("  \033[1;36m>>\033[0m Selecciona: ").strip()
        if opt == "1":
            run_oplire("dashboard", work_dir)
        elif opt == "2":
            run_cmd("taskkill /F /IM oplire.exe", work_dir)
        elif opt == "3":
            run_ps("try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8080' -TimeoutSec 3 -UseBasicParsing; Write-Host '[OK] Dashboard activo' } catch { Write-Host '[OFF] Dashboard no disponible' }")
        elif opt == "0":
            break


def doctor_menu(work_dir):
    while True:
        clear()
        print_banner()
        print_section("DIAGNOSTICO DEL SISTEMA")

        print_option("1", "Diagnostico completo (Oplire)")
        print_option("2", "Verificar WARP")
        print_option("3", "Verificar OpenCode")
        print_option("4", "Verificar Claude Code")
        print_option("5", "Verificar Node.js")
        print_option("0", "Volver")
        print()
        print(f"  \033[36m{'=' * 54}\033[0m")
        print()
        opt = input("  \033[1;36m>>\033[0m Selecciona: ").strip()
        if opt == "1":
            run_oplire("doctor", work_dir)
        elif opt == "2":
            run_ps("if (Get-Command warp-cli -ErrorAction SilentlyContinue) { Write-Host '[OK] WARP instalado:' (warp-cli --version) } else { Write-Host '[FAIL] WARP no encontrado' }")
        elif opt == "3":
            run_ps("if (Get-Command opencode -ErrorAction SilentlyContinue) { Write-Host '[OK] OpenCode instalado' } else { Write-Host '[FAIL] OpenCode no encontrado' }")
        elif opt == "4":
            run_ps("if (Get-Command claude -ErrorAction SilentlyContinue) { Write-Host '[OK] Claude Code instalado:' (claude --version) } else { Write-Host '[FAIL] Claude Code no encontrado' }")
        elif opt == "5":
            run_ps("if (Get-Command node -ErrorAction SilentlyContinue) { Write-Host '[OK] Node.js:' (node --version) } else { Write-Host '[FAIL] Node.js no encontrado' }")
        elif opt == "0":
            break


def find_antigravity_files_in_config(config_path):
    protected = []
    if not os.path.isdir(config_path):
        return protected
    try:
        for name in os.listdir(config_path):
            lower = name.lower()
            full = os.path.join(config_path, name)
            if not os.path.isfile(full):
                continue
            if lower.startswith("antigravity") or "antigravity" in lower:
                protected.append(full)
    except OSError:
        pass
    return protected


def backup_antigravity_files(config_path):
    files = find_antigravity_files_in_config(config_path)
    if not files:
        return None
    stamp = time.strftime("%Y%m%d-%H%M%S")
    backup_dir = os.path.join(os.path.dirname(config_path), f"antigravity-backup-{stamp}")
    os.makedirs(backup_dir, exist_ok=True)
    for f in files:
        try:
            shutil.copy2(f, os.path.join(backup_dir, os.path.basename(f)))
        except OSError:
            pass
    return backup_dir


def clear_opencode_menu():
    user_profile = os.environ.get("USERPROFILE", "")
    paths = {
        "config": os.path.join(user_profile, ".config", "opencode"),
        "cache": os.path.join(user_profile, ".cache", "opencode"),
        "data": os.path.join(user_profile, ".local", "share", "opencode"),
    }

    while True:
        clear()
        print_banner()
        print_section("LIMPIAR DATOS DE OPENCODE")

        for name, path in paths.items():
            exists = "\033[32m[EXISTE]\033[0m" if os.path.isdir(path) else "\033[90m[vacio]\033[0m"
            print(f"    {name:10} {exists}  {path}")

        ag_files = find_antigravity_files_in_config(paths["config"])
        print()
        if ag_files:
            print_status(True, f"Antigravity: {len(ag_files)} archivo(s) PROTEGIDOS (no se borran)")
        else:
            print_status(False, "Antigravity: sin archivos en config")

        print()
        print_option("1", "Limpiar TODO (protege Antigravity)")
        print_option("2", "Limpiar solo cache")
        print_option("3", "Limpiar solo config (protege Antigravity)")
        print_option("4", "Limpiar solo datos locales")
        print_option("5", "Borrar tambien datos Antigravity", "requiere confirmacion")
        print_option("0", "Volver")
        print()
        print(f"  \033[36m{'=' * 54}\033[0m")
        print()
        opt = input("  \033[1;36m>>\033[0m Selecciona: ").strip()

        if opt == "1":
            clear()
            print_banner()
            print()
            print("  \033[1;33mLos archivos de Antigravity se conservaran y respaldaran.\033[0m")
            print()
            confirm = input("  ¿Esta seguro? (S/N): ").strip().upper()
            if confirm != "S":
                continue
            cmds = []
            cfg = paths["config"]
            if os.path.isdir(cfg):
                bak = backup_antigravity_files(cfg)
                if bak:
                    print(f"  \033[32m[OK]\033[0m Antigravity respaldado en: {bak}")
                ag_names = {os.path.basename(f) for f in find_antigravity_files_in_config(cfg)}
                for name in os.listdir(cfg):
                    if name in ag_names:
                        print(f"  \033[90m[KEEP]\033[0m {name}")
                        continue
                    cmds.append(f'Remove-Item -Recurse -Force "{os.path.join(cfg, name)}"')
                print(f"  \033[32m[OK]\033[0m config marcado para limpiar")
            else:
                print(f"  \033[90m[SKIP]\033[0m config no existe")
            for name in ("cache", "data"):
                p = paths[name]
                if os.path.isdir(p):
                    cmds.append(f'Remove-Item -Recurse -Force "{p}"')
                    print(f"  \033[32m[OK]\033[0m {name} marcado para eliminar")
                else:
                    print(f"  \033[90m[SKIP]\033[0m {name} no existe")
            if cmds:
                ps_script = "; ".join(cmds)
                run_ps(ps_script)
        elif opt == "2":
            p = paths["cache"]
            if os.path.isdir(p):
                run_ps(f'Remove-Item -Recurse -Force "{p}"')
            else:
                print(f"\n  \033[90m[SKIP]\033[0m Cache no existe")
                pause()
        elif opt == "3":
            p = paths["config"]
            if os.path.isdir(p):
                print(f"\n  \033[1;33mLos archivos de Antigravity se conservaran y respaldaran.\033[0m")
                confirm = input("  ¿Eliminar configuracion? (S/N): ").strip().upper()
                if confirm == "S":
                    bak = backup_antigravity_files(p)
                    if bak:
                        print(f"  \033[32m[OK]\033[0m Antigravity respaldado en: {bak}")
                    ag_names = {os.path.basename(f) for f in find_antigravity_files_in_config(p)}
                    cmds = [
                        f'Remove-Item -Recurse -Force "{os.path.join(p, name)}"'
                        for name in os.listdir(p) if name not in ag_names
                    ]
                    if cmds:
                        run_ps("; ".join(cmds))
            else:
                print(f"\n  \033[90m[SKIP]\033[0m Config no existe")
                pause()
        elif opt == "4":
            p = paths["data"]
            if os.path.isdir(p):
                run_ps(f'Remove-Item -Recurse -Force "{p}"')
            else:
                print(f"\n  \033[90m[SKIP]\033[0m Datos no existen")
                pause()
        elif opt == "5":
            clear()
            print_banner()
            print()
            print("  \033[1;31m¡PRECAUCION! Esto eliminara TAMBIEN las cuentas y config de Antigravity.\033[0m")
            print()
            ag_files = find_antigravity_files_in_config(paths["config"])
            if not ag_files:
                print("  No hay archivos de Antigravity que borrar.")
                pause()
                continue
            for f in ag_files:
                print(f"  \033[90m- {f}\033[0m")
            print()
            confirm = input("  ¿Borrar datos de Antigravity? (SI para confirmar): ").strip().upper()
            if confirm != "SI":
                continue
            bak = backup_antigravity_files(paths["config"])
            if bak:
                print(f"  \033[32m[OK]\033[0m Respaldo previo en: {bak}")
            cmds = [f'Remove-Item -Force "{f}"' for f in ag_files]
            run_ps("; ".join(cmds))
        elif opt == "0":
            break


def proxy_menu(work_dir):
    while True:
        clear()
        print_banner()
        print_section("SERVIDOR PROXY OPLIRE")

        print_option("1", "Iniciar proxy")
        print_option("2", "Detener todos oplire.exe")
        print_option("3", "Verificar estado")
        print_option("0", "Volver")
        print()
        print(f"  \033[36m{'=' * 54}\033[0m")
        print()
        opt = input("  \033[1;36m>>\033[0m Selecciona: ").strip()
        if opt == "1":
            run_oplire("proxy", work_dir)
        elif opt == "2":
            run_cmd("taskkill /F /IM oplire.exe", work_dir)
        elif opt == "3":
            run_ps("try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8080' -TimeoutSec 3 -UseBasicParsing; Write-Host '[OK] Proxy activo' } catch { Write-Host '[OFF] Proxy no disponible' }")
        elif opt == "0":
            break


def local_server_menu(work_dir):
    while True:
        clear()
        print_banner()
        print_section("SERVIDOR LOCAL OPENCODE")

        print_option("1", "Iniciar servidor (127.0.0.1:3000)")
        print_option("2", "Puerto personalizado")
        print_option("3", "Abrir navegador")
        print_option("4", "Verificar estado")
        print_option("0", "Volver")
        print()
        print(f"  \033[36m{'=' * 54}\033[0m")
        print()
        opt = input("  \033[1;36m>>\033[0m Selecciona: ").strip()
        if opt == "1":
            run_cmd("opencode serve --hostname 127.0.0.1 --port 3000", work_dir)
        elif opt == "2":
            port = input("\n  Puerto (default 3000): ").strip()
            if not port:
                port = "3000"
            run_cmd(f"opencode serve --hostname 127.0.0.1 --port {port}", work_dir)
        elif opt == "3":
            webbrowser.open("http://127.0.0.1:3000")
            print("\n  Abriendo navegador...")
            time.sleep(1)
        elif opt == "4":
            run_ps("try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:3000' -TimeoutSec 3 -UseBasicParsing; Write-Host '[OK] Servidor activo - Status:' $r.StatusCode } catch { Write-Host '[OFF] Servidor no disponible' }")
        elif opt == "0":
            break


def main():
    if not is_admin():
        clear()
        print_banner()
        print_section("PERMISOS DE ADMINISTRADOR")
        print("  Se requieren permisos de administrador para algunas funciones.")
        print()
        print_option("S", "Elevar a administrador")
        print_option("N", "Continuar sin admin")
        print()
        choice = input("  \033[1;36m>>\033[0m Selecciona: ").strip().upper()
        if choice == "S":
            if not run_as_admin():
                print("\n  No se pudieron obtener permisos.")
                time.sleep(2)
        elif choice != "N":
            return

    clear()
    print_banner()
    print("  \033[90mCargando sistema unificado Nexus...\033[0m")

    oplire_dir, antigravity_dir = resolve_system_dirs()
    oplire_exe = find_oplire_exe_in(oplire_dir) if oplire_dir else None

    if not oplire_dir:
        print()
        print("  \033[33mNo se encontro el motor Oplire (carpeta oplire/).\033[0m")
        time.sleep(2)

    if oplire_dir and not oplire_exe:
        print()
        print("  \033[33moplire.exe no esta compilado.\033[0m")
        print(f"  \033[90mCompilar con: cd \"{oplire_dir}\" && .\\build.ps1 -Release\033[0m")
        time.sleep(2)

    if not antigravity_menu:
        print()
        print("  \033[33mModulo antigravity_menu.py no encontrado junto a nexus_menu.py.\033[0m")
        time.sleep(2)

    if not antigravity_dir:
        print()
        print("  \033[33mNo se encontro el motor Antigravity (carpeta antigravity/).\033[0m")
        time.sleep(2)

    work_dir = oplire_dir

    if antigravity_menu and antigravity_dir:
        try:
            antigravity_menu.startup_silent_repair()
        except Exception:
            pass

    while True:
        clear()
        print_banner()
        print_section("NEXUS - SISTEMA UNIFICADO")

        oplire_state = oplire_dir if oplire_dir else "\033[31mno encontrado\033[0m"
        ag_state = antigravity_dir if antigravity_dir else "\033[31mno encontrado\033[0m"
        print(f"  \033[90mMotor Oplire:       {oplire_state}\033[0m")
        print(f"  \033[90mMotor Antigravity:  {ag_state}\033[0m")
        admin_status = "\033[32mAdmin\033[0m" if is_admin() else "\033[33mUsuario\033[0m"
        print(f"  \033[90mPermisos:           {admin_status}\033[0m")
        print(f"  \033[90mVersion:            {VERSION}\033[0m")

        print()
        print_option("1", "Dashboard Oplire", "Panel de control")
        print_option("2", "Doctor", "Diagnostico del sistema")
        print_option("3", "Limpiar OpenCode", "Protege Antigravity")
        print_option("4", "Proxy Oplire", "Servidor proxy")
        print_option("5", "OpenCode Local", "Servidor local")
        print_option("6", "Herramientas", "Everything / Cloudflare")
        if antigravity_menu and antigravity_dir:
            print_option("7", "Antigravity", "Cuentas Google / plugin")
        else:
            print(f"  \033[90m[7] Antigravity                - no disponible\033[0m")
        print_option("0", "Salir")
        print()
        print(f"  \033[36m{'=' * 54}\033[0m")
        print()

        option = input("  \033[1;36m>>\033[0m Selecciona una opcion: ").strip()

        if option == "1":
            if oplire_dir and oplire_exe:
                dashboard_menu(work_dir)
            else:
                clear()
                print_banner()
                print_section("NO DISPONIBLE")
                print("  \033[33mOplire no esta listo (carpeta o oplire.exe).\033[0m")
                pause()
        elif option == "2":
            if oplire_dir and oplire_exe:
                doctor_menu(work_dir)
            else:
                clear()
                print_banner()
                print_section("NO DISPONIBLE")
                print("  \033[33mOplire no esta listo (carpeta o oplire.exe).\033[0m")
                pause()
        elif option == "3":
            clear_opencode_menu()
        elif option == "4":
            if oplire_dir and oplire_exe:
                proxy_menu(work_dir)
            else:
                clear()
                print_banner()
                print_section("NO DISPONIBLE")
                print("  \033[33mOplire no esta listo (carpeta o oplire.exe).\033[0m")
                pause()
        elif option == "5":
            local_server_menu(work_dir)
        elif option == "6":
            tools_menu()
        elif option == "7":
            if antigravity_menu and antigravity_dir:
                antigravity_menu.show_menu()
            else:
                clear()
                print_banner()
                print_section("NO DISPONIBLE")
                print("  \033[33mEl modulo Antigravity no esta disponible.\033[0m")
                print()
                print("  Verifica que antigravity_menu.py este junto a nexus_menu.py")
                print("  y que exista la carpeta antigravity/.")
                pause()
        elif option == "0":
            clear()
            print_banner()
            print()
            print("  \033[32mSaliendo de Nexus...\033[0m")
            print()
            break


if __name__ == "__main__":
    main()
