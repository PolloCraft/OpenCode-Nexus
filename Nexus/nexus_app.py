# -*- coding: utf-8 -*-
"""
NEXUS Suite - Aplicacion unificada (v7.3.1)
===========================================
Una sola suite con tres modulos:

  * OPENCODE   -> motor Oplire: IP (WARP), servidor (proxy/dashboard,
                  OpenCode local y desktop bypass), vCache/backups y
                  mantenimiento (doctor, herramientas y PATH).
  * ANTIGRAVITY -> cuentas, plugin (con mantenimiento) y modelos.
  * CLAUDE     -> Free Claude Code (FCC): servidor, agentes, config y doctor.

Diseno responsivo (se adapta a cualquier tamano de ventana), iconos 100%
compatibles (sin emoji), reconocimiento del equipo y refresco en tiempo real.
Portable y sin errores. Todo el codigo, sin omisiones.
"""

import os
import sys
import json
import queue
import threading

import tkinter as tk
from tkinter import ttk, messagebox

# Asegura que el paquete 'modules' sea importable (script o .exe).
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from modules import common as C
from modules import oplire_ops as OP
from modules import antigravity_ops as AG
from modules import claude_ops as CL
from modules import ui

THEME = ui.THEME
APP_TITLE = C.APP_NAME
APP_VERSION = C.APP_VERSION
ICONS = ui.ICONS

CLOUDFLARE_CLIENT_URL = ("https://developers.cloudflare.com/cloudflare-one/"
                         "team-and-resources/devices/cloudflare-one-client/download/")

EVERYTHING_URL = "https://www.voidtools.com/es-es/"


# --------------------------------------------------------------- scroll -----
class ScrollFrame(tk.Frame):
    """Contenedor con desplazamiento vertical (rueda del raton soportada)."""

    def __init__(self, parent):
        super().__init__(parent, bg=THEME["bg"])
        self.canvas = tk.Canvas(self, bg=THEME["bg"], highlightthickness=0)
        self.vsb = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview,
                                 style="Nexus.Vertical.TScrollbar")
        self.inner = tk.Frame(self.canvas, bg=THEME["bg"])
        self._win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=self.vsb.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.vsb.pack(side="right", fill="y")
        self.inner.bind("<Configure>", self._on_inner)
        self.canvas.bind("<Configure>", self._on_canvas)
        for w in (self.canvas, self.inner):
            w.bind("<MouseWheel>", self._on_wheel)

    def _on_inner(self, _e):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas(self, e):
        self.canvas.itemconfigure(self._win, width=e.width)

    def _on_wheel(self, e):
        self.canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")


class NexusApp(tk.Tk):
    def __init__(self):
        super().__init__()
        C.enable_dpi_awareness()
        ui.init_fonts()
        self.title(APP_TITLE)
        self.geometry("1240x800")
        self.minsize(720, 560)
        self.configure(bg=THEME["bg"])

        self._active_page = "home"
        self._refreshers = []
        self._tick_count = 0
        self._refresh_busy = set()
        self._ui_queue = queue.Queue()
        self._pills = {}
        self._home_cols = None
        self._resize_job = None
        self._width = 1240

        ui.apply_styles(self)
        self._build()
        self.bind("<F5>", lambda e: self._refresh_now())
        self.bind("<Configure>", self._on_resize)
        self.show_page("home")
        self.after(80, self._poll_ui_queue)
        self.after(400, self._update_pills_async)
        self._tick()

    # ------------------------------------------------------------- layout ----
    def _build(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.sidebar = tk.Frame(self, bg=THEME["sidebar"], width=250)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)
        self._build_sidebar()

        right = tk.Frame(self, bg=THEME["bg"])
        right.grid(row=0, column=1, sticky="nsew")
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(1, weight=1)

        self._build_header(right)

        self.content_host = ScrollFrame(right)
        self.content_host.grid(row=1, column=0, sticky="nsew")

    def _build_header(self, parent):
        header = tk.Frame(parent, bg=THEME["bg"], height=96)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)
        header.grid_columnconfigure(0, weight=1)

        titles = tk.Frame(header, bg=THEME["bg"])
        titles.grid(row=0, column=0, rowspan=2, sticky="w", padx=30, pady=(18, 0))
        self.page_title = tk.Label(titles, text="", bg=THEME["bg"], fg=THEME["text"],
                                   font=(ui.FONT, 22, "bold"), anchor="w")
        self.page_title.pack(anchor="w")
        self.page_sub = tk.Label(titles, text="", bg=THEME["bg"], fg=THEME["muted"],
                                 font=(ui.FONT, 10), anchor="w")
        self.page_sub.pack(anchor="w", pady=(2, 0))

        pills = tk.Frame(header, bg=THEME["bg"])
        pills.grid(row=0, column=1, rowspan=2, sticky="e", padx=30)
        self._pills_frame = pills
        self._pills["engine"] = self._mk_pill(pills, "OPLIRE", THEME["muted"])
        self._pills["warp"] = self._mk_pill(pills, "WARP", THEME["muted"])
        self._pills["opencode"] = self._mk_pill(pills, "OPENCODE", THEME["muted"])
        self._pills["plugin"] = self._mk_pill(pills, "PLUGIN", THEME["muted"])
        self._pills["claude"] = self._mk_pill(pills, "CLAUDE", THEME["muted"])

        admin = tk.Label(pills, text="  ADMIN  ", bg="#12351f", fg=THEME["green"],
                         font=(ui.FONT, 8, "bold"), padx=6, pady=5)
        self._admin_label = admin
        self._admin_elev = tk.Label(pills, text="  Elevar a Admin  ", bg="#3a2f10", fg=THEME["yellow"],
                                    font=(ui.FONT, 8, "bold"), padx=6, pady=5, cursor="hand2")
        self._admin_elev.bind("<Button-1>", lambda e: self._elevate())
        self._sync_admin()

        sep = tk.Frame(parent, bg=THEME["border"], height=1)
        sep.grid(row=0, column=0, sticky="sew")

    def _mk_pill(self, parent, text, color):
        lbl = tk.Label(parent, text=ICONS["home"] and "●  " + text, bg=THEME["bg"], fg=color,
                       font=(ui.FONT, 8, "bold"), padx=6)
        lbl.pack(side="left", padx=4)
        return lbl

    def _sync_admin(self):
        if C.is_admin():
            self._admin_label.pack(side="left", padx=(8, 0))
            self._admin_elev.pack_forget()
        else:
            self._admin_elev.pack(side="left", padx=(8, 0))
            self._admin_label.pack_forget()

    def _elevate(self):
        if messagebox.askyesno("Permisos", "Reiniciar NEXUS como Administrador?"):
            if C.run_as_admin():
                self.destroy()
            else:
                messagebox.showerror("Permisos", "No se pudo solicitar elevacion.")

    # ------------------------------------------------------------ sidebar ----
    def _build_sidebar(self):
        brand = tk.Frame(self.sidebar, bg=THEME["sidebar"])
        brand.pack(fill="x", pady=(22, 2))
        tk.Label(brand, text="◆", bg=THEME["sidebar"], fg=THEME["accent"],
                 font=(ui.SYMBOL, 18, "bold")).pack(side="left", padx=(22, 6))
        tk.Label(brand, text="NEXUS", bg=THEME["sidebar"], fg=THEME["text"],
                 font=(ui.FONT, 16, "bold")).pack(side="left")
        tk.Label(self.sidebar, text=f"Suite v{APP_VERSION}", bg=THEME["sidebar"],
                 fg=THEME["dim"], font=(ui.FONT, 8), anchor="w").pack(fill="x", padx=24, pady=(0, 10))

        self._nav_items = {}

        section_count = [0]

        def section(text, color=None, icon=None, icon_raise=0):
            if section_count[0]:
                tk.Frame(self.sidebar, bg=THEME["border"], height=1).pack(
                    fill="x", padx=18, pady=(10, 0))
            section_count[0] += 1
            f = tk.Frame(self.sidebar, bg=THEME["sidebar"])
            f.pack(fill="x", padx=22, pady=(8, 4))
            tk.Label(f, text=text.upper(), bg=THEME["sidebar"], fg=color or THEME["dim"],
                     font=(ui.FONT, 9, "bold"), anchor="w").pack(side="left")
            if icon:
                tk.Label(f, text=icon, bg=THEME["sidebar"], fg=color or THEME["dim"],
                         font=(ui.SYMBOL, 10, "bold"), anchor="w").pack(
                             side="left", padx=(6, 0), pady=(0, icon_raise))

        def nav(key, icon, label):
            self._nav_items[key] = self._nav_button(key, icon, label)

        section("GENERAL", icon=ICONS["home"], icon_raise=2)
        nav("home", ICONS["home"], "Dashboard")

        section("Oplire", "#5b7fbd", ICONS["server"])
        nav("ip", ICONS["ip"], "Control de IP")
        nav("server", ICONS["server"], "Servidor")
        nav("cache", ICONS["cache"], "Datos y caché")
        nav("maintenance", ICONS["tools"], "Mantenimiento")

        section("Antigravity", "#b06cff", ICONS["ag_general"])
        nav("ag_accounts", ICONS["ag_accounts"], "Cuentas")
        nav("ag_plugin", ICONS["ag_plugin"], "Plugin")
        nav("ag_models", ICONS["ag_models"], "Modelos")

        section("Claude", "#ff9f43", ICONS["claude"])
        nav("claude", ICONS["ag_general"], "Panel")
        nav("claude_agents", ICONS["play"], "Agentes")
        nav("claude_doctor", ICONS["doctor"], "Doctor")

        section("SISTEMA", icon=ICONS["path"], icon_raise=2)
        nav("system", ICONS["system"], "Equipo")
        nav("about", ICONS["about"], "Acerca de")

    def _nav_button(self, key, icon, label):
        item = tk.Frame(self.sidebar, bg=THEME["sidebar"], cursor="hand2")
        item.pack(fill="x")
        bar = tk.Frame(item, bg=THEME["sidebar"], width=3)
        bar.pack(side="left", fill="y")
        inner = tk.Frame(item, bg=THEME["sidebar"])
        inner.pack(side="left", fill="x", expand=True)
        ic = tk.Label(inner, text=icon, bg=THEME["sidebar"], fg=THEME["muted"],
                      font=(ui.SYMBOL, 12), width=3)
        ic.pack(side="left", padx=(14, 0), pady=9)
        tx = tk.Label(inner, text=label, bg=THEME["sidebar"], fg=THEME["muted"],
                      font=(ui.FONT, 10), anchor="w")
        tx.pack(side="left", padx=(6, 10), pady=9)
        widgets = [item, inner, ic, tx]

        def set_bg(color):
            for w in widgets:
                w.configure(bg=color)

        def on_enter(_):
            if self._active_page != key:
                set_bg(THEME["hover"])

        def on_leave(_):
            if self._active_page != key:
                set_bg(THEME["sidebar"])

        def on_click(_):
            self.show_page(key)

        for w in widgets:
            w.bind("<Enter>", on_enter)
            w.bind("<Leave>", on_leave)
            w.bind("<Button-1>", on_click)
        item._widgets, item._bar, item._ic, item._tx, item._key = widgets, bar, ic, tx, key
        return item

    def _set_nav_active(self, active_key):
        for key, item in self._nav_items.items():
            active = key == active_key
            bg = THEME["nav_active"] if active else THEME["sidebar"]
            for w in item._widgets:
                w.configure(bg=bg)
            item._bar.configure(bg=THEME["accent"] if active else THEME["sidebar"])
            item._ic.configure(fg=THEME["accent"] if active else THEME["muted"])
            item._tx.configure(fg=THEME["text"] if active else THEME["muted"])

    # --------------------------------------------------------------- pages ----
    PAGE_META = {
        "home":        ("Dashboard", "Resumen general del sistema y estado de todos los motores"),
        "ip":          ("Control de IP  ·  WARP", "Rotacion, reset y restauracion de IP en tiempo real"),
        "server":      ("Servidor", "Proxy, OpenCode local y Desktop Bypass en un solo flujo"),
        "cache":       ("Datos y caché  ·  vCache", "Deteccion en tiempo real, limpieza y borrado de datos"),
        "maintenance": ("Mantenimiento", "Diagnostico, instalacion, PATH y variables del sistema"),
        "ag_accounts": ("Antigravity  ·  Cuentas", "Cuentas Google, cuotas reales y verificacion"),
        "ag_plugin":   ("Antigravity  ·  Plugin", "Activar/desactivar, mantenimiento y API key"),
        "ag_models":   ("Antigravity  ·  Modelos", "Modelos cargados en la configuracion de OpenCode"),
        "claude":      ("Claude  ·  Panel", "Free Claude Code: servidor, configuracion y API keys"),
        "claude_agents": ("Claude  ·  Agentes", "Lanza Claude Code, Codex, OpenCode y mas agentes FCC"),
        "claude_doctor": ("Claude  ·  Doctor", "Diagnostico, dependencias y actualizacion de FCC"),
        "system":      ("Equipo", "Reconocimiento del hardware y del entorno"),
        "about":       ("Acerca de", "Informacion de NEXUS Suite"),
    }

    def show_page(self, key):
        self._active_page = key
        self._refreshers = []
        self._set_nav_active(key)
        title, sub = self.PAGE_META.get(key, (key, ""))
        self.page_title.configure(text=title)
        self.page_sub.configure(text=sub)

        inner = self.content_host.inner
        for child in inner.winfo_children():
            child.destroy()

        page = tk.Frame(inner, bg=THEME["bg"])
        page.pack(fill="both", expand=True, padx=24, pady=18)
        page.grid_columnconfigure(0, weight=1)

        builder = getattr(self, f"page_{key}", None)
        if builder:
            builder(page)

    def _tabbed_page(self, parent, tabs):
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(0, weight=1)
        nb = ttk.Notebook(parent)
        nb.grid(row=0, column=0, sticky="nsew")
        self._tab_refreshers = {}
        for idx, (label, builder) in enumerate(tabs):
            host = tk.Frame(nb, bg=THEME["bg"])
            nb.add(host, text=label)
            body = tk.Frame(host, bg=THEME["bg"])
            body.pack(fill="both", expand=True, padx=4, pady=(12, 4))
            body.grid_columnconfigure(0, weight=1)
            start = len(self._refreshers)
            builder(body)
            self._tab_refreshers[idx] = list(self._refreshers[start:])
        self._refreshers = list(self._tab_refreshers.get(0, []))

        def on_tab(_event=None):
            try:
                idx = nb.index(nb.select())
            except Exception:
                return
            self._refreshers = list(self._tab_refreshers.get(idx, []))
            for refresh in self._refreshers:
                try:
                    refresh()
                except Exception:
                    pass

        nb.bind("<<NotebookTabChanged>>", on_tab)
        return nb

    # ------------------------------------------------------------- helpers ----
    def card(self, parent, title=None, accent=None, subtitle=None):
        return ui.card(parent, title=title, accent=accent, subtitle=subtitle)

    def btn(self, parent, text, cmd, kind="accent"):
        return ui.button(parent, text=text, cmd=cmd, kind=kind)

    def btnrow(self, parent, items, bg=None):
        """Fila de botones que se reacomoda (responsive) segun el ancho."""
        ff = ui.FlowFrame(parent, gap=10, row_gap=10, bg=bg or THEME["card"])
        ff.pack(fill="x")
        for text, cmd, kind in items:
            ff.add(self.btn(ff, text, cmd, kind))
        return ff

    def log(self, box, text, color=None):
        if box:
            try:
                box.write(text, color)
            except Exception:
                pass

    def log_clear(self, box):
        if box:
            try:
                box.clear()
            except Exception:
                pass

    def _poll_ui_queue(self):
        """Drena callbacks pendientes en el hilo de la GUI (thread-safe)."""
        try:
            while True:
                fn = self._ui_queue.get_nowait()
                try:
                    fn()
                except Exception:
                    pass
        except queue.Empty:
            pass
        try:
            self.after(80, self._poll_ui_queue)
        except RuntimeError:
            pass

    def run_bg(self, fn, on_done=None):
        def worker():
            res, err = None, None
            try:
                res = fn()
            except Exception as e:  # pragma: no cover
                err = e
            if on_done:
                self._ui_queue.put(lambda: on_done(res, err))
        threading.Thread(target=worker, daemon=True).start()

    def _schedule_refresh(self, key, compute, apply):
        """
        Ejecuta 'compute' en un hilo (si no hay uno activo para esa clave) y
        aplica el resultado en el hilo de la GUI via cola. Evita bloquear la
        interfaz con operaciones lentas (procesos, puertos, recorrido de carpetas).
        """
        if key in self._refresh_busy:
            return
        self._refresh_busy.add(key)

        def work():
            try:
                res = compute()
            except Exception:
                res = None

            def finish():
                self._refresh_busy.discard(key)
                try:
                    apply(res)
                except Exception:
                    pass

            self._ui_queue.put(finish)

        threading.Thread(target=work, daemon=True).start()

    @staticmethod
    def _wrap(res):
        if isinstance(res, tuple) and len(res) >= 2:
            first, second = res[0], res[1]
            if isinstance(first, bool):
                return first, str(second)
            return (first == 0), str(second)
        return True, str(res)

    def run_action(self, box, func, busy, ok_color=None):
        if box:
            self.log_clear(box)
            self.log(box, busy or "[...] Ejecutando...", THEME["accent"])

        def done(res, err):
            if box:
                self.log_clear(box)
            if err:
                self.log(box, f"[ERROR] {err}", THEME["red"])
                return
            ok, txt = self._wrap(res)
            col = (ok_color or THEME["green"]) if ok else THEME["red"]
            lines = (txt or "").splitlines() or ["(sin salida)"]
            for ln in lines:
                self.log(box, ln, col if ln.strip() else None)

        self.run_bg(func, done)

    def need_engine(self):
        if OP.has_engine():
            return True
        messagebox.showerror(
            "Oplire",
            "No se encontro oplire.exe.\n\n"
            f"Ubicacion esperada:\n{os.path.join(OP.oplire_dir(), 'dist', 'oplire.exe')}\n\n"
            "Copia el motor a Nexus/oplire/dist/oplire.exe o compilalo con build.ps1 -Release.")
        return False

    # ------------------------------------------------------ live / status ----
    def _tick(self):
        self._tick_count += 1
        if self._tick_count % 3 == 0:
            self._update_pills_async()
            for r in list(self._refreshers):
                try:
                    r()
                except Exception:
                    pass
        self.after(1000, self._tick)

    def _update_pills_async(self):
        def work():
            return {"engine": OP.has_engine(),
                    "warp": OP.warp_connected(),
                    "opencode": AG.get_opencode_path() is not None,
                    "plugin": AG.test_plugin_configured(),
                    "claude": CL.server_running()}

        def done(res, err):
            if err or not isinstance(res, dict):
                return
            self._set_pill("engine", "OPLIRE", res["engine"])
            self._set_pill("warp", "WARP", res["warp"])
            self._set_pill("opencode", "OPENCODE", res["opencode"])
            self._set_pill("plugin", "PLUGIN", res["plugin"])
            self._set_pill("claude", "CLAUDE", res["claude"])
            self._sync_admin()

        self.run_bg(work, done)

    def _set_pill(self, key, name, state):
        lbl = self._pills.get(key)
        if not lbl:
            return
        if state is True:
            color, tail = THEME["green"], "ON"
        elif state is False:
            color, tail = THEME["dim"], "OFF"
        else:
            color, tail = THEME["muted"], "?"
        lbl.configure(text=f"●  {name} {tail}", fg=color)

    def _refresh_now(self):
        self._update_pills_async()
        for r in list(self._refreshers):
            try:
                r()
            except Exception:
                pass

    # ------------------------------------------------------- responsive -------
    def _on_resize(self, event):
        if event.widget is not self:
            return
        w = event.width
        self._width = w
        try:
            if w < 980:
                self.page_sub.pack_forget()
            else:
                if not self.page_sub.winfo_ismapped():
                    self.page_sub.pack(anchor="w", pady=(2, 0))
            if w < 1040:
                self._pills_frame.grid_remove()
            else:
                self._pills_frame.grid()
        except Exception:
            pass

        avail = w - 250 - 60
        cols = 4 if avail >= 940 else 3 if avail >= 700 else 2 if avail >= 460 else 1
        if self._active_page == "home" and cols != self._home_cols:
            self._home_cols = cols
            if self._resize_job:
                try:
                    self.after_cancel(self._resize_job)
                except Exception:
                    pass
            self._resize_job = self.after(160, lambda: self.show_page("home"))

    # ============================================================== PAGES =====
    def page_home(self, parent):
        info = C.system_info()
        avail = self._width - 250 - 60
        cols = 4 if avail >= 940 else 3 if avail >= 700 else 2 if avail >= 460 else 1
        self._home_cols = cols

        cards = [
            ("engine", "Motor Oplire", THEME["accent"]),
            ("warp", "Cloudflare WARP", THEME["accent"]),
            ("local", "OpenCode Local", THEME["green"]),
            ("server", "Proxy / Servidor", THEME["accent"]),
            ("ag", "Antigravity", THEME["accent2"]),
            ("claude", "Claude FCC  ·  Servidor", THEME["green"]),
            ("claude_code", "Claude Code  ·  CLI", THEME["green"]),
            ("claude_env", "Claude FCC  ·  Entorno", THEME["accent2"]),
        ]
        grid = tk.Frame(parent, bg=THEME["bg"])
        grid.grid(row=0, column=0, sticky="ew")
        for i in range(cols):
            grid.grid_columnconfigure(i, weight=1, uniform="c")
        self._home_vals = {}
        for i, (key, title, accent) in enumerate(cards):
            outer, body = self.card(grid, title=title, accent=accent)
            outer.grid(row=i // cols, column=i % cols, sticky="nsew",
                       padx=(0 if i % cols == 0 else 10, 0), pady=(0, 10))
            val = tk.Label(body, text="...", bg=THEME["card"], fg=THEME["muted"],
                           font=(ui.FONT, 14, "bold"), anchor="w")
            val.pack(fill="x")
            sub = tk.Label(body, text="", bg=THEME["card"], fg=THEME["muted"],
                           font=(ui.FONT, 9), anchor="w", wraplength=220, justify="left")
            sub.pack(fill="x", pady=(4, 0))
            self._home_vals[key] = (val, sub)
        self._home_refresh()
        self._refreshers.append(self._home_refresh)

        outer, body = self.card(parent, title="Acciones rapidas", accent=THEME["accent2"])
        outer.grid(row=1, column=0, sticky="ew", pady=(14, 0))
        self.btnrow(body, [
            (f"{ICONS['ip']}  Rotar IP (quick-reset)", self._qa_rotate, "green"),
            (f"{ICONS['local']}  Iniciar OpenCode Local", self._qa_local, "accent"),
            (f"{ICONS['play']}  Iniciar Claude FCC", self._qa_claude_start, "green"),
            (f"{ICONS['external']}  Abrir Admin Claude", self._qa_claude_admin, "accent"),
            (f"{ICONS['ag_plugin']}  Menu Plugin", lambda: self.show_page("ag_plugin"), "ghost"),
            (f"{ICONS['doctor']}  Mantenimiento", lambda: self.show_page("maintenance"), "ghost"),
            (f"{ICONS['cache']}  Datos y caché", lambda: self.show_page("cache"), "ghost"),
        ])

        outer, body = self.card(parent, title="Ubicaciones (tiempo real)", accent=THEME["muted"])
        outer.grid(row=2, column=0, sticky="ew", pady=(14, 0))
        self._kv(body, "Base", C.get_base_dir())
        self._kv(body, "Oplire", OP.oplire_dir() + ("" if OP.has_engine() else "   (sin binario)"))
        self._kv(body, "Antigravity", C.antigravity_dir() or "no encontrada")
        self._kv(body, "Claude FCC", CL.project_dir() or "no encontrado")
        self._kv(body, "Config OpenCode", AG.get_config_dir())

        outer, body = self.card(parent, title="Equipo y red (en vivo)", accent=THEME["accent"])
        outer.grid(row=3, column=0, sticky="ew", pady=(14, 0))
        self._home_live = {}
        rows = [
            ("Sistema", info["os"]), ("Host", f"{info['host']}  ({info['user']})"),
            ("CPU", f"{info['cpu']}  ·  {info['cores']} nucleos"),
            ("GPU", info.get("gpu") or "no detectada"),
            ("RAM", f"{C.human_size(info['ram_free'])} libres de {C.human_size(info['ram_total'])}"),
            ("Activo desde", C.human_uptime(info.get("uptime") or C._uptime_seconds())),
            ("Red local", f"{info.get('local_ip') or 'consultando...'}"),
            ("Red publica", "consultando..."),
            ("Puerta de enlace", "consultando..."),
            ("DNS", "consultando..."),
        ]
        for key, value in rows:
            line = tk.Frame(body, bg=THEME["card"])
            line.pack(fill="x", pady=2)
            tk.Label(line, text=key, bg=THEME["card"], fg=THEME["muted"],
                     font=(ui.FONT, 9), width=16, anchor="w").pack(side="left")
            lbl = tk.Label(line, text=str(value), bg=THEME["card"], fg=THEME["text"],
                           font=(ui.MONO, 9), anchor="w", justify="left")
            lbl.pack(side="left")
            self._home_live[key] = lbl
        self._home_live_refresh()
        self._home_net_refresh()
        self._refreshers.append(self._home_live_refresh)

    def _home_refresh(self):
        if not getattr(self, "_home_vals", None):
            return

        def compute():
            local_port = OP.opencode_server_port()
            claude_prepared = (CL.project_exists() and CL.uv_available()
                               and CL.venv_ready())
            return {
                "engine": OP.has_engine(),
                "warp": C.tool_available("warp-cli"),
                "local": OP.opencode_server_running(local_port, verify=False, fast=True),
                "server": OP.dashboard_running(),
                "ag": AG.test_plugin_configured(),
                "claude": CL.server_running(),
                "claude_ok": claude_prepared,
                "claude_code": C.tool_available("claude"),
                "claude_prepared": claude_prepared,
                "claude_issue": CL.provider_issue(),
            }

        def apply(res):
            if not res:
                return
            self._set_home("engine", "COMPILADO" if res["engine"] else "SIN COMPILAR",
                           THEME["green"] if res["engine"] else THEME["yellow"],
                           "oplire.exe listo" if res["engine"] else "Motor no disponible")
            self._set_home("warp", "GESTIONADO" if res["warp"] else "NO INSTALADO",
                           THEME["green"] if res["warp"] else THEME["muted"],
                           "Rotacion de IP disponible" if res["warp"] else "Instala Cloudflare WARP")
            self._set_home("local", "ACTIVO" if res["local"] else "DETENIDO",
                           THEME["green"] if res["local"] else THEME["muted"],
                           f"127.0.0.1:{OP.opencode_server_port()}")
            self._set_home("server", "ACTIVO" if res["server"] else "DETENIDO",
                           THEME["green"] if res["server"] else THEME["muted"],
                           OP.dashboard_base())
            self._set_home("ag", "ACTIVO" if res["ag"] else "DESACTIVADO",
                           THEME["green"] if res["ag"] else THEME["yellow"],
                           "Plugin de cuentas Google" if res["ag"] else "Activalo en Antigravity")
            if res["claude"]:
                self._set_home("claude", "SERVIDOR ON", THEME["green"], CL.admin_url())
            elif res["claude_ok"]:
                self._set_home("claude", "LISTO", THEME["yellow"], "Inicia el servidor en Claude > Panel")
            else:
                self._set_home("claude", "SIN CONFIGURAR", THEME["muted"], "Prepara FCC en Claude > Panel")

            if res["claude_code"]:
                self._set_home("claude_code", "INSTALADO", THEME["green"],
                               C.which("claude") or "Claude Code disponible")
            else:
                self._set_home("claude_code", "NO INSTALADO", THEME["muted"],
                               "Instalalo desde Claude > Agentes")

            if res["claude_prepared"] and not res["claude_issue"]:
                self._set_home("claude_env", "LISTO", THEME["green"],
                               "Proyecto, uv, entorno y API configurados")
            elif res["claude_prepared"]:
                issue = " ".join((res["claude_issue"] or "").split())
                issue = issue[:130] + ("..." if len(issue) > 130 else "")
                self._set_home("claude_env", "REVISAR", THEME["yellow"],
                               issue or "Configura modelo y API key en Claude > Panel")
            else:
                self._set_home("claude_env", "SIN PREPARAR", THEME["muted"],
                               "Usa Preparar FCC en Claude > Panel")

        self._schedule_refresh("home", compute, apply)

    def _home_live_refresh(self):
        if not getattr(self, "_home_live", None):
            return

        def compute():
            total, free = C.memory_info()
            return {
                "ram": f"{C.human_size(free)} libres de {C.human_size(total)}",
                "uptime": C.human_uptime(C._uptime_seconds()),
                "ip": C.local_ip() or "no detectada",
            }

        def apply(res):
            if not res:
                return
            for key, value in (("RAM", res["ram"]), ("Activo desde", res["uptime"]),
                               ("Red local", res["ip"])):
                lbl = self._home_live.get(key)
                if lbl is not None:
                    try:
                        lbl.configure(text=value)
                    except Exception:
                        pass

        self._schedule_refresh("home_live", compute, apply)

    def _home_net_refresh(self):
        if not getattr(self, "_home_live", None):
            return

        def compute():
            return C.network_info()

        def apply(net):
            if not net:
                return
            values = {
                "Red local": f"{net.get('local_ip') or '?'}  "
                             f"({'privada' if net.get('private') else 'publica' if net.get('private') is False else '?'})",
                "Red publica": net.get("public_ip") or
                               ("sin salida a internet" if net.get("internet") is False else "no disponible"),
                "Puerta de enlace": net.get("gateway") or "no detectada",
                "DNS": net.get("dns") or "automatico",
            }
            for key, value in values.items():
                lbl = self._home_live.get(key)
                if lbl is not None:
                    try:
                        lbl.configure(text=value)
                    except Exception:
                        pass

        self._schedule_refresh("home_net", compute, apply)

    def _set_home(self, key, value, color, sub):
        pair = self._home_vals.get(key)
        if not pair:
            return
        val, subl = pair
        try:
            val.configure(text=value, fg=color)
            subl.configure(text=sub)
        except Exception:
            pass

    def _kv(self, parent, key, value):
        line = tk.Frame(parent, bg=THEME["card"])
        line.pack(fill="x", pady=2)
        tk.Label(line, text=f"{key}", bg=THEME["card"], fg=THEME["muted"],
                 font=(ui.FONT, 9), width=16, anchor="w").pack(side="left")
        tk.Label(line, text=str(value), bg=THEME["card"], fg=THEME["text"],
                 font=(ui.MONO, 9), anchor="w", justify="left").pack(side="left")

    def _qa_local(self):
        port = OP.opencode_server_port()
        if OP.opencode_server_running(port, verify=False, fast=True):
            OP.open_opencode_browser(port)
            return
        conflict = OP.opencode_server_conflict(port, fast=True)
        if conflict:
            port = C.find_free_port(3005, 3099)
        self.show_page("server")
        try:
            self._server_nb.select(1)
        except Exception:
            pass
        self.after(150, lambda: self._loc_start(port))

    def _qa_claude_start(self):
        ok, msg = CL.start_server()
        if ok:
            messagebox.showinfo("Claude FCC", msg)
        else:
            messagebox.showwarning("Claude FCC", msg)
        self.after(800, self._home_refresh)

    def _qa_claude_admin(self):
        if CL.server_running():
            self._open_claude_admin()
            return
        if not messagebox.askyesno("Claude FCC",
                                   "El servidor FCC no esta activo.\n\n"
                                   "Quieres iniciarlo y abrir el Admin UI?"):
            return
        ok, msg = CL.start_server()
        if not ok:
            messagebox.showwarning("Claude FCC", msg)
            return
        self.after(700, lambda: self._qa_claude_admin_ready(8))

    def _qa_claude_admin_ready(self, attempts):
        if CL.server_running():
            self._open_claude_admin()
            self._home_refresh()
            return
        if attempts <= 0:
            messagebox.showinfo("Claude FCC",
                                "El servidor sigue iniciando.\n"
                                f"Admin UI: {CL.admin_url()}")
            return
        self.after(700, lambda: self._qa_claude_admin_ready(attempts - 1))

    def _open_claude_admin(self):
        if not CL.open_admin():
            messagebox.showinfo("Claude FCC", CL.admin_url())

    def _qa_rotate(self):
        if self.need_engine():
            OP.run_cli_console(["quick-reset"], title="Oplire Rotar IP")

    # ------------------------------------------------------- CONTROL DE IP ----
    def page_ip(self, parent):
        outer, body = self.card(parent, title="Estado WARP (tiempo real)", accent=THEME["accent"])
        outer.grid(row=0, column=0, sticky="ew")
        self._ip_status = tk.Label(body, text="Consultando...", bg=THEME["card"], fg=THEME["text"],
                                   font=(ui.MONO, 10), anchor="w", justify="left")
        self._ip_status.pack(fill="x")
        self.btnrow(body, [
            (f"{ICONS['refresh']}  Actualizar estado", self._ip_refresh, "ghost")], bg=THEME["card"])

        outer, body = self.card(parent, title="Operaciones de IP", accent=THEME["green"])
        outer.grid(row=1, column=0, sticky="ew", pady=(14, 0))
        tk.Label(body, text="Rotacion y restauracion del tunel WARP. En tiempo real sobre 127.0.0.1.",
                 bg=THEME["card"], fg=THEME["muted"], font=(ui.FONT, 9), anchor="w",
                 justify="left", wraplength=860).pack(fill="x", pady=(0, 10))
        self.btnrow(body, [
            (f"{ICONS['ip']}  Rotar IP (quick-reset)", self._ip_rotate, "green"),
            (f"{ICONS['refresh']}  Reconectar (actualizar)", self._ip_reconnect, "accent"),
            (f"{ICONS['warn']}  Forzar reset (completo)", self._ip_force, "warn"),
            (f"{ICONS['restore']}  Restaurar IP original", self._ip_restore, "accent"),
            (f"{ICONS['stop']}  Desconectar WARP", self._ip_stop, "danger"),
            (f"{ICONS['ok']}  Estado WARP", self._ip_status_btn, "ghost"),
        ])

        box = ui.LogBox(parent)
        box.frame.grid(row=2, column=0, sticky="nsew", pady=(14, 0))
        self._ip_box = box
        self._ip_refresh()
        self._refreshers.append(self._ip_refresh)

    def _ip_refresh(self):
        def work():
            return OP.warp_status_raw()

        def done(res, err):
            if not hasattr(self, "_ip_status") or not self._ip_status.winfo_exists():
                return
            if err:
                self._ip_status.configure(text=f"Error: {err}", fg=THEME["red"])
                return
            rc, out = res
            low = (out or "").lower()
            connected = rc == 0 and "connected" in low and "disconnected" not in low
            self._ip_status.configure(text=out or "(sin salida)",
                                      fg=THEME["green"] if connected else (THEME["yellow"] if rc == 0 else THEME["red"]))

        self.run_bg(work, done)

    def _ip_rotate(self):
        if self.need_engine():
            self.run_action(self._ip_box, OP.rotate_ip, "[...] Rotando IP (quick-reset)...")

    def _ip_reconnect(self):
        self.run_action(self._ip_box, OP.reconnect_warp, "[...] Reconectando WARP...")

    def _ip_force(self):
        if not self.need_engine():
            return
        if messagebox.askyesno("Forzar reset", "Esto reinicia TODO el tunel WARP (reset completo).\nContinuar?"):
            self.run_action(self._ip_box, OP.force_reset, "[...] Forzando reset completo...")

    def _ip_restore(self):
        def func():
            if OP.dashboard_running():
                ok, data = OP.api_restore_ip()
                return ok, (data if isinstance(data, str) else json.dumps(data, indent=2, ensure_ascii=False))
            return OP.stop_warp()
        self.run_action(self._ip_box, func, "[...] Restaurando IP original...")

    def _ip_stop(self):
        if self.need_engine():
            self.run_action(self._ip_box, OP.stop_warp, "[...] Desconectando WARP...")

    def _ip_status_btn(self):
        self.run_action(self._ip_box, OP.warp_status_raw, "[...] Consultando estado WARP...")

    # --------------------------------------------------- PROXY / SERVIDOR -----
    def page_server(self, parent):
        self._server_nb = self._tabbed_page(parent, [
            ("Proxy / Dashboard", self._section_server),
            ("OpenCode Local", self._section_local),
            ("Desktop Bypass", self._section_desktop),
        ])

    def _section_server(self, parent):
        outer, body = self.card(parent, title="Servidor local", accent=THEME["accent"])
        outer.grid(row=0, column=0, sticky="ew")
        self._srv_status = tk.Label(body, text="...", bg=THEME["card"], fg=THEME["text"],
                                    font=(ui.MONO, 9), anchor="w", justify="left")
        self._srv_status.pack(fill="x")
        tk.Label(body, text="El dashboard/proxy escucha en 127.0.0.1:8080 (configurable en oplire config).",
                 bg=THEME["card"], fg=THEME["muted"], font=(ui.FONT, 9), anchor="w").pack(fill="x", pady=(6, 10))
        self.btnrow(body, [
            (f"{ICONS['play']}  Iniciar Dashboard", self._srv_dashboard, "green"),
            (f"{ICONS['play']}  Iniciar Proxy", self._srv_proxy, "accent"),
            (f"{ICONS['play']}  Daemon", self._srv_daemon, "ghost"),
            (f"{ICONS['stop']}  Detener oplire", self._srv_stop, "danger"),
            (f"{ICONS['external']}  Abrir navegador", lambda: OP.open_dashboard_browser(), "ghost"),
            (f"{ICONS['ok']}  Verificar estado", self._srv_check, "ghost"),
            (f"{ICONS['refresh']}  Estado API", self._srv_api, "ghost"),
        ])

        outer2, body2 = self.card(parent, title="Sesiones de OpenCode", accent=THEME["accent2"])
        outer2.grid(row=1, column=0, sticky="ew", pady=(14, 0))
        tk.Label(body2, text=(
            "Sesiones: estado  ->  cuenta las sesiones guardadas y detecta archivos danados.\n"
            "Sesiones: listar  ->  muestra las sesiones existentes con su identificador.\n"
            "Reparar sesiones  ->  corrige sesiones corruptas (hace respaldo antes de tocar nada)."),
            bg=THEME["card"], fg=THEME["muted"], font=(ui.FONT, 9), anchor="w",
            justify="left", wraplength=900).pack(fill="x", pady=(0, 8))
        self.btnrow(body2, [
            ("Sesiones: estado", self._srv_sessions_status, "ghost"),
            ("Sesiones: listar", self._srv_sessions_list, "ghost"),
            ("Reparar sesiones", self._srv_fix_sessions, "accent"),
        ])

        outer3, body3 = self.card(parent, title="Avanzado (Oplire)", accent=THEME["accent2"])
        outer3.grid(row=2, column=0, sticky="ew", pady=(14, 0))
        tk.Label(body3, text=(
            "Conectar Claude Code  ->  configura Claude Code para que use el proxy local de Oplire "
            "(127.0.0.1:8080) en lugar de la API directa.\n"
            "Conectar Desktop      ->  hace lo mismo con OpenCode Desktop (equivale al bypass).\n"
            "Monitor (watch)       ->  consola en vivo con las sesiones y peticiones del proxy.\n"
            "Config (show)         ->  muestra la configuracion efectiva del motor."),
            bg=THEME["card"], fg=THEME["muted"], font=(ui.FONT, 9), anchor="w",
            justify="left", wraplength=900).pack(fill="x", pady=(0, 10))
        self.btnrow(body3, [
            (f"{ICONS['star']}  Conectar Claude Code", lambda: self._adv_connect("claude-code"), "accent"),
            (f"{ICONS['desktop']}  Conectar Desktop", lambda: self._adv_connect("desktop"), "accent"),
            (f"{ICONS['server']}  Monitor (watch)", self._adv_watch, "ghost"),
            (f"{ICONS['about']}  Config (show)", self._adv_config, "ghost"),
        ])

        box = ui.LogBox(parent)
        box.frame.grid(row=3, column=0, sticky="nsew", pady=(14, 0))
        self._srv_box = box
        self._srv_refresh()
        self._refreshers.append(self._srv_refresh)

    def _srv_refresh(self):
        if not hasattr(self, "_srv_status") or not self._srv_status.winfo_exists():
            return

        def compute():
            return OP.dashboard_running(), OP.oplire_running()

        def apply(res):
            if not hasattr(self, "_srv_status") or not self._srv_status.winfo_exists():
                return
            up, running = res if res else (False, False)
            if not up:
                state, color = "○ inactivo", THEME["muted"]
            elif running:
                state, color = "● ACTIVO", THEME["green"]
            else:
                state, color = "● OCUPADO por otro servicio", THEME["yellow"]
            self._srv_status.configure(
                text=f"Dashboard: {state}  en  {OP.dashboard_base()}\n"
                     f"Proceso oplire.exe: {'● en ejecucion' if running else '○ detenido'}",
                fg=color)

        self._schedule_refresh("srv", compute, apply)

    def _srv_dashboard(self):
        if not self.need_engine():
            return
        if OP.dashboard_running():
            if OP.oplire_running() or OP.dashboard_is_oplire():
                self.log(self._srv_box,
                         f"[i] El dashboard ya esta activo en {OP.dashboard_base()}. "
                         f"Abriendo en el navegador...", THEME["yellow"])
                OP.open_dashboard_browser()
            else:
                self.log(self._srv_box,
                         f"[!] El puerto {OP.dashboard_port()} esta ocupado por otro servicio "
                         f"(no es oplire). No se puede iniciar el dashboard.", THEME["red"])
            self._srv_refresh()
            return
        if OP.start_dashboard():
            self.log(self._srv_box, "[OK] Iniciando dashboard en una consola nueva...", THEME["green"])
        else:
            self.log(self._srv_box, "[!] No se pudo abrir la consola del dashboard.", THEME["red"])
        self.after(2000, self._srv_refresh)

    def _srv_proxy(self):
        if not self.need_engine():
            return
        if OP.dashboard_running():
            self.log(self._srv_box,
                     f"[!] El puerto {OP.dashboard_port()} ya esta en uso (dashboard/proxy activo). "
                     f"Detenlo antes de iniciar el proxy.", THEME["yellow"])
            self._srv_refresh()
            return
        if OP.start_proxy():
            self.log(self._srv_box, "[OK] Iniciando proxy en una consola nueva...", THEME["green"])
        self.after(2000, self._srv_refresh)

    def _srv_daemon(self):
        if not self.need_engine():
            return
        if OP.dashboard_running():
            self.log(self._srv_box,
                     f"[!] El puerto {OP.dashboard_port()} ya esta en uso (dashboard/proxy activo). "
                     f"Detenlo antes de iniciar el daemon.", THEME["yellow"])
            return
        if OP.start_daemon():
            self.log(self._srv_box, "[OK] Iniciando daemon en una consola nueva...", THEME["green"])
        self.after(2000, self._srv_refresh)

    def _srv_stop(self):
        if not OP.oplire_running() and not OP.dashboard_running():
            self.log(self._srv_box, "[i] No hay ningun servidor oplire en ejecucion.", THEME["yellow"])
            self._srv_refresh()
            return
        if not messagebox.askyesno("Detener servidor",
                                   "Detener el dashboard/proxy de oplire en ejecucion?"):
            return
        self.run_action(self._srv_box, OP.stop_oplire, "[...] Deteniendo servidor oplire...")
        self.after(1500, self._srv_refresh)

    def _srv_check(self):
        self.run_action(self._srv_box, OP.server_status_report,
                        "[...] Verificando dashboard, proceso y upstream...")

    def _srv_api(self):
        self.run_action(self._srv_box, OP.api_status_report,
                        "[...] Consultando API /api/status...")

    def _srv_sessions_status(self):
        if self.need_engine():
            self.run_action(self._srv_box, OP.sessions_status, "[...] Leyendo estado de sesiones...")

    def _srv_sessions_list(self):
        if self.need_engine():
            self.run_action(self._srv_box, OP.sessions_list, "[...] Listando sesiones...")

    def _srv_fix_sessions(self):
        if self.need_engine():
            self.run_action(self._srv_box, OP.fix_sessions, "[...] Reparando sesiones...")

    def _adv_connect(self, target):
        if self.need_engine():
            self.run_action(self._srv_box, lambda: OP.connect(target),
                            f"[...] Conectando {target} al proxy...")

    def _adv_config(self):
        if self.need_engine():
            self.run_action(self._srv_box, OP.config_show, "[...] Leyendo configuracion...")

    def _adv_watch(self):
        if self.need_engine():
            ok = OP.watch()
            self.log(self._srv_box, "[OK] Monitor abierto en consola." if ok
                     else "[!] No se pudo abrir el monitor.", THEME["green"] if ok else THEME["yellow"])

    # ----------------------------------------------------- OPENCODE LOCAL -----
    def _section_local(self, parent):
        outer, body = self.card(parent, title="Servidor de OpenCode (tiempo real)", accent=THEME["green"])
        outer.grid(row=0, column=0, sticky="ew")
        self._loc_status = tk.Label(body, text="Consultando...", bg=THEME["card"], fg=THEME["text"],
                                    font=(ui.MONO, 9), anchor="w", justify="left")
        self._loc_status.pack(fill="x")
        tk.Label(body, text="Levanta 'opencode serve' en 127.0.0.1:3000. Es el upstream por defecto del "
                            "proxy de Oplire (Claude Code / Desktop enrutan aqui).",
                 bg=THEME["card"], fg=THEME["muted"], font=(ui.FONT, 9), anchor="w",
                 justify="left", wraplength=860).pack(fill="x", pady=(6, 10))
        self.btnrow(body, [
            (f"{ICONS['play']}  Iniciar servidor", self._loc_start_auto, "green"),
            (f"{ICONS['add']}  Puerto personalizado", self._loc_start_custom, "accent"),
            (f"{ICONS['external']}  Abrir navegador", lambda: OP.open_opencode_browser(OP.opencode_server_port()), "ghost"),
            (f"{ICONS['ok']}  Verificar estado", self._loc_check, "ghost"),
            (f"{ICONS['stop']}  Detener servidor", self._loc_stop, "danger"),
        ])
        tk.Label(body, text="Sugerencia: inicia el servidor y luego conecta las herramientas desde "
                            "'Avanzado' en la pagina Proxy / Servidor.",
                 bg=THEME["card"], fg=THEME["dim"], font=(ui.FONT, 9), anchor="w",
                 justify="left", wraplength=860).pack(fill="x", pady=(10, 0))

        box = ui.LogBox(parent)
        box.frame.grid(row=1, column=0, sticky="nsew", pady=(14, 0))
        self._loc_box = box
        self.log(box, "Servidor local de OpenCode. Inicia el servidor antes de conectar herramientas.", THEME["muted"])
        self._loc_refresh()
        self._refreshers.append(self._loc_refresh)

    def _loc_refresh(self):
        if not hasattr(self, "_loc_status") or not self._loc_status.winfo_exists():
            return

        def compute():
            port = OP.opencode_server_port()
            opc = OP.opencode_command()
            up = OP.opencode_server_running(port, fast=True)
            conflict = None if up else OP.opencode_server_conflict(port, fast=True)
            return port, opc, up, conflict

        def apply(res):
            if not hasattr(self, "_loc_status") or not self._loc_status.winfo_exists():
                return
            if res:
                port, opc, up, conflict = res
            else:
                port, opc, up, conflict = OP.opencode_server_port(), None, False, None
            lines = [f"Servidor 127.0.0.1:{port}: {'● ACTIVO' if up else '○ inactivo'}"]
            if conflict:
                lines.append(f"[!] Puerto {port} ocupado por '{conflict}' (p. ej. Docker). "
                             f"Pulsa 'Iniciar servidor' para elegir un puerto libre.")
            lines.append(f"OpenCode: {opc or 'no encontrado en el PATH'}")
            if up:
                color = THEME["green"]
            elif conflict:
                color = THEME["yellow"]
            else:
                color = THEME["yellow"] if opc else THEME["red"]
            self._loc_status.configure(text="\n".join(lines), fg=color)

        self._schedule_refresh("loc", compute, apply)

    def _loc_start_auto(self):
        port = OP.opencode_server_port()
        conflict = OP.opencode_server_conflict(port)
        if conflict:
            if not messagebox.askyesno(
                    "Puerto ocupado",
                    f"El puerto {port} lo usa '{conflict}' (Docker/otro servicio).\n\n"
                    f"Usar automaticamente un puerto libre?"):
                return
            port = C.find_free_port(3005, 3099)
        self._loc_start(port)

    def _loc_start(self, port):
        self.run_action(self._loc_box, lambda: OP.start_opencode_server(port),
                        f"[...] Iniciando OpenCode en 127.0.0.1:{port}...")
        self.after(1200, self._loc_refresh)

    def _loc_start_custom(self):
        from tkinter import simpledialog
        port = simpledialog.askinteger("Puerto", "Puerto del servidor OpenCode:", initialvalue=3000,
                                       minvalue=1, maxvalue=65535, parent=self)
        if port:
            self._loc_start(port)

    def _loc_check(self):
        def func():
            port = OP.opencode_server_port()
            up = OP.opencode_server_running(port)
            return up, (f"Servidor 127.0.0.1:{port} {'ACTIVO' if up else 'no disponible'}")
        self.run_action(self._loc_box, func, "[...] Verificando servidor local...")

    def _loc_stop(self):
        if messagebox.askyesno("Detener servidor", "Detener el servidor local de OpenCode?"):
            self.run_action(self._loc_box, OP.stop_opencode_server, "[...] Deteniendo servidor...")
            self.after(1200, self._loc_refresh)

    # ------------------------------------------------------- DESKTOP BYPASS ---
    def _section_desktop(self, parent):
        outer, body = self.card(parent, title="Estado del Desktop bypass", accent=THEME["accent"])
        outer.grid(row=0, column=0, sticky="ew")
        self._desk_status = tk.Label(body, text="...", bg=THEME["card"], fg=THEME["text"],
                                     font=(ui.MONO, 9), anchor="w", justify="left")
        self._desk_status.pack(fill="x")
        self.btnrow(body, [(f"{ICONS['refresh']}  Actualizar", self._desk_refresh, "ghost")], bg=THEME["card"])

        outer, body = self.card(parent, title="Bypass de OpenCode Desktop", accent=THEME["green"])
        outer.grid(row=1, column=0, sticky="ew", pady=(14, 0))
        tk.Label(body, text="Hace que la app de escritorio enrute por el proxy local. Se guarda un respaldo "
                            "de la configuracion original antes de tocar nada.",
                 bg=THEME["card"], fg=THEME["muted"], font=(ui.FONT, 9), anchor="w",
                 justify="left", wraplength=860).pack(fill="x", pady=(0, 10))
        self.btnrow(body, [
            (f"{ICONS['star']}  Activar bypass", self._desk_setup, "green"),
            (f"{ICONS['refresh']}  Restaurar original", self._desk_restore, "accent"),
            (f"{ICONS['ok']}  Ver estado", self._desk_status_btn, "ghost"),
        ])

        box = ui.LogBox(parent)
        box.frame.grid(row=2, column=0, sticky="nsew", pady=(14, 0))
        self._desk_box = box
        self._desk_refresh()
        self._refreshers.append(self._desk_refresh)

    def _desk_refresh(self):
        def work():
            return OP.desktop_status_data()

        def done(res, err):
            if not hasattr(self, "_desk_status") or not self._desk_status.winfo_exists():
                return
            if err or not isinstance(res, dict):
                self._desk_status.configure(text=f"(sin datos) {err or ''}", fg=THEME["muted"])
                return
            proxied = res.get("is_proxied")
            txt = (f"Config Desktop : {'encontrado' if res.get('config_found') else 'NO encontrado'}\n"
                   f"Bypass activo  : {'SI' if proxied else 'no'}\n"
                   f"Ruta           : {res.get('config_path') or '(no detectada)'}\n"
                   f"API base_url   : {res.get('api_base_url') or '(sin definir)'}\n"
                   f"Respaldo .bak  : {'si' if res.get('backup_exists') else 'no'}")
            if res.get("proxy_addr"):
                txt += f"\nProxy guardado : {res['proxy_addr']}"
            self._desk_status.configure(text=txt, fg=THEME["green"] if proxied else THEME["text"])

        self.run_bg(work, done)

    def _desk_setup(self):
        self.run_action(self._desk_box, OP.setup_desktop,
                        "[...] Activando bypass (API/CLI inteligente)...")
        self.after(1500, self._desk_refresh)

    def _desk_restore(self):
        self.run_action(self._desk_box, OP.restore_desktop,
                        "[...] Restaurando configuracion original...")
        self.after(1200, self._desk_refresh)

    def _desk_status_btn(self):
        self.run_action(self._desk_box,
                        lambda: (True, OP.desktop_report()),
                        "[...] Leyendo estado real del bypass...")

    # ------------------------------------------------------ CACHE / VCACHE ----
    def page_cache(self, parent):
        outer, body = self.card(parent, title="Deteccion de caché (tiempo real)", accent=THEME["yellow"])
        outer.grid(row=0, column=0, sticky="ew")
        self._cache_summary = tk.Label(body, text="Escaneando...", bg=THEME["card"], fg=THEME["text"],
                                       font=(ui.MONO, 9), anchor="w", justify="left")
        self._cache_summary.pack(fill="x", pady=(0, 8))

        tf = tk.Frame(body, bg=THEME["card"], highlightbackground=THEME["border"], highlightthickness=1)
        tf.pack(fill="both", expand=True)
        cols = ("tipo", "ruta", "tamano")
        self._cache_tree = ttk.Treeview(tf, columns=cols, show="headings", height=6)
        for c, w, t in zip(cols, (170, 560, 120), ("Tipo", "Ruta", "Tamano")):
            self._cache_tree.heading(c, text=t)
            self._cache_tree.column(c, width=w, minwidth=90, anchor="w", stretch=(c == "ruta"))
        self._cache_tree.pack(side="left", fill="both", expand=True, padx=1, pady=1)
        sbn = ttk.Scrollbar(tf, orient="vertical", command=self._cache_tree.yview,
                            style="Nexus.Vertical.TScrollbar")
        self._cache_tree.configure(yscrollcommand=sbn.set)
        sbn.pack(side="right", fill="y")

        outer2, body2 = self.card(parent, title="Limpieza", accent=THEME["red"])
        outer2.grid(row=1, column=0, sticky="ew", pady=(14, 0))
        tk.Label(body2, text="Limpia la caché o borra los datos. Se PROTEGEN siempre los archivos de Antigravity.",
                 bg=THEME["card"], fg=THEME["muted"], font=(ui.FONT, 9), anchor="w",
                 justify="left", wraplength=860).pack(fill="x", pady=(0, 10))
        self.btnrow(body2, [
            (f"{ICONS['cache']}  Limpiar caché", self._cache_clear, "accent"),
            (f"{ICONS['warn']}  Limpiar solo configuración", self._cache_clear_config, "warn"),
            (f"{ICONS['trash']}  Borrar TODOS los datos", self._cache_clear_all, "danger"),
            (f"{ICONS['desktop']}  Abrir carpeta caché", self._cache_open, "ghost"),
        ])

        outer3, body3 = self.card(parent, title="Backup de contexto de chat (sesiones)", accent=THEME["green"])
        outer3.grid(row=2, column=0, sticky="ew", pady=(14, 0))
        tk.Label(body3, text=(
            "Copia REAL de sesiones y almacenamiento de OpenCode/Oplire (mensajes, partes y diffs). "
            "Restaurar hace merge sin borrar y crea antes un backup de seguridad."),
            bg=THEME["card"], fg=THEME["muted"], font=(ui.FONT, 9), anchor="w",
            justify="left", wraplength=900).pack(fill="x", pady=(0, 8))
        self._backup_summary = tk.Label(body3, text="Buscando backups...", bg=THEME["card"],
                                        fg=THEME["text"], font=(ui.MONO, 9), anchor="w")
        self._backup_summary.pack(fill="x", pady=(0, 6))
        tf2 = tk.Frame(body3, bg=THEME["card"], highlightbackground=THEME["border"], highlightthickness=1)
        tf2.pack(fill="both", expand=True)
        cols2 = ("fecha", "carpetas", "tamano", "nota")
        self._backup_tree = ttk.Treeview(tf2, columns=cols2, show="headings", height=5, selectmode="browse")
        for c, w, t in zip(cols2, (180, 90, 100, 480), ("Fecha", "Carpetas", "Tamano", "Nota")):
            self._backup_tree.heading(c, text=t)
            self._backup_tree.column(c, width=w, minwidth=70, anchor="w", stretch=(c == "nota"))
        self._backup_tree.pack(side="left", fill="both", expand=True, padx=1, pady=1)
        sbn2 = ttk.Scrollbar(tf2, orient="vertical", command=self._backup_tree.yview,
                             style="Nexus.Vertical.TScrollbar")
        self._backup_tree.configure(yscrollcommand=sbn2.set)
        sbn2.pack(side="right", fill="y")
        self.btnrow(body3, [
            (f"{ICONS['add']}  Crear backup ahora", self._backup_create, "green"),
            (f"{ICONS['restore']}  Restaurar seleccionado", self._backup_restore, "accent"),
            (f"{ICONS['trash']}  Eliminar backup", self._backup_delete, "danger"),
            (f"{ICONS['refresh']}  Refrescar", self._backup_refresh, "ghost"),
            (f"{ICONS['external']}  Abrir carpeta", lambda: OP.open_backups_folder(), "ghost"),
        ])

        box = ui.LogBox(parent, height=7)
        box.frame.grid(row=3, column=0, sticky="nsew", pady=(14, 0))
        self._cache_box = box
        self._cache_refresh()
        self._backup_refresh()
        self._refreshers.append(self._cache_refresh)
        self._refreshers.append(self._backup_refresh)

    def _cache_refresh(self):
        if not hasattr(self, "_cache_tree") or not self._cache_tree.winfo_exists():
            return

        def compute():
            items, total = OP.find_vcache()
            folders = OP.opencode_folders()
            return items, total, folders

        def apply(res):
            if not hasattr(self, "_cache_tree") or not self._cache_tree.winfo_exists():
                return
            tree = self._cache_tree
            for i in tree.get_children():
                tree.delete(i)
            if not res:
                tree.insert("", "end", values=("(sin datos)", "-", "-"))
                return
            items, total, folders = res
            found = False
            for f in folders:
                if f["exists"]:
                    found = True
                    tree.insert("", "end", values=(f["name"], f["path"], f["size_h"]))
            if not found:
                tree.insert("", "end", values=("(sin caché detectada)", "-", "-"))
            cache_total = sum(it["size"] for it in items if it.get("kind") == "cache")
            total_all = sum(f["size"] for f in folders if f["exists"])
            self._cache_summary.configure(
                text=f"Caché: {C.human_size(cache_total)}   ·   Cache + datos: {C.human_size(total)}   ·   "
                     f"Total OpenCode (config+cache+datos): {C.human_size(total_all)}",
                fg=THEME["green"] if found else THEME["muted"])

        self._schedule_refresh("cache", compute, apply)

    def _cache_clear(self):
        if messagebox.askyesno("Limpiar caché", "Limpiar SOLO la caché de OpenCode?\n(No toca config ni cuentas)"):
            self.run_action(self._cache_box, OP.clear_cache, "[...] Limpiando caché...")
            self.after(900, self._cache_refresh)

    def _cache_clear_config(self):
        if messagebox.askyesno("Limpiar configuración",
                               "Limpiar la carpeta de configuración de OpenCode?\n"
                               "Se CONSERVAN opencode.json/jsonc y todo lo de Antigravity "
                               "(cuentas y plugin)."):
            self.run_action(self._cache_box, OP.clear_config, "[...] Limpiando configuración...")
            self.after(900, self._cache_refresh)

    def _cache_clear_all(self):
        if messagebox.askyesno("Borrar datos", "Borrar caché + datos de OpenCode?\nSe protege Antigravity.\nContinuar?"):
            self.run_action(self._cache_box, OP.clear_all_data, "[...] Borrando datos...")
            self.after(900, self._cache_refresh)

    def _cache_open(self):
        items, _ = OP.find_vcache()
        target = items[0]["path"] if items else os.path.join(C.user_home(), ".cache", "opencode")
        if not C.open_path(target):
            messagebox.showinfo("Carpeta", target)

    def _backup_selected(self):
        sel = self._backup_tree.selection() if hasattr(self, "_backup_tree") else None
        if not sel:
            messagebox.showinfo("Backup", "Selecciona un backup en la lista.")
            return None
        return self._backup_tree.item(sel[0], "values")[0]

    def _backup_refresh(self):
        if not hasattr(self, "_backup_tree") or not self._backup_tree.winfo_exists():
            return

        def compute():
            return OP.list_sessions_backups()

        def apply(res):
            tree = self._backup_tree
            if not tree.winfo_exists():
                return
            selected = None
            sel = tree.selection()
            if sel:
                selected = tree.item(sel[0], "values")[0]
            for i in tree.get_children():
                tree.delete(i)
            if not res:
                self._backup_summary.configure(
                    text="Sin backups todavia. Crea uno antes de limpiar o reparar sesiones.",
                    fg=THEME["muted"])
                return
            for b in res:
                iid = tree.insert("", "end", values=(b["name"], len(b.get("sources") or []),
                                                     b["size_h"], b.get("note") or ""))
                if selected == b["name"]:
                    tree.selection_set(iid)
            total = sum(b["size"] for b in res)
            self._backup_summary.configure(
                text=f"{len(res)} backup(s)  ·  {C.human_size(total)}  ·  {OP.sessions_backup_root()}",
                fg=THEME["green"])

        self._schedule_refresh("backups", compute, apply)

    def _backup_create(self):
        self.run_action(self._cache_box,
                        lambda: OP.create_sessions_backup("Backup manual desde NEXUS"),
                        "[...] Copiando sesiones y contexto de chat...")
        self.after(1500, self._backup_refresh)

    def _backup_restore(self):
        name = self._backup_selected()
        if not name:
            return
        if not messagebox.askyesno("Restaurar backup",
                                   f"Restaurar el backup:\n{name}\n\n"
                                   "Se hara merge sobre las carpetas actuales y se creara "
                                   "antes un backup de seguridad. Continuar?"):
            return
        self.run_action(self._cache_box, lambda: OP.restore_sessions_backup(name),
                        "[...] Restaurando sesiones...")
        self.after(1500, self._backup_refresh)
        self.after(1500, self._cache_refresh)

    def _backup_delete(self):
        name = self._backup_selected()
        if not name:
            return
        if not messagebox.askyesno("Eliminar backup", f"Eliminar el backup:\n{name}\n\nEsta accion no se puede deshacer."):
            return
        ok, msg = OP.delete_sessions_backup(name)
        self.log(self._cache_box, ("[OK] " if ok else "[ERROR] ") + msg,
                 THEME["green"] if ok else THEME["red"])
        self._backup_refresh()

    # --------------------------------------------------------- MANTENIMIENTO ---
    def page_maintenance(self, parent):
        self._maintenance_nb = self._tabbed_page(parent, [
            ("Diagnostico", self._section_doctor),
            ("Instalar / Reparar", self._section_tools),
            ("PATH / Variables", self._section_path),
        ])

    # ------------------------------------------------------------- DOCTOR -----
    def _section_doctor(self, parent):
        outer, body = self.card(parent, title="Diagnostico completo del sistema", accent=THEME["yellow"])
        outer.grid(row=0, column=0, sticky="ew")
        tk.Label(body, text=("Analiza equipo, red, motores, dependencias, sesiones y modelos. "
                             "Cada boton ejecuta comprobaciones REALES (sin datos inventados)."),
                 bg=THEME["card"], fg=THEME["muted"], font=(ui.FONT, 9), anchor="w",
                 justify="left", wraplength=900).pack(fill="x", pady=(0, 8))
        self.btnrow(body, [
            ("Analisis completo", self._doc_full, "green"),
            ("Oplire doctor", self._doc_oplire, "accent"),
            ("Modelos disponibles", self._doc_all_models, "accent"),
            ("Version", self._doc_version, "ghost"),
            ("Reparar sesiones", self._doc_fix_sessions, "ghost"),
            ("Reparar plugin", self._doc_repair_plugin, "ghost"),
            ("Reparar OpenCode", self._doc_repair_opencode, "warn"),
            ("Comprobar puertos", self._doc_ports, "ghost"),
        ])

        outer2, body2 = self.card(parent, title="Dependencias (tiempo real)", accent=THEME["accent"])
        outer2.grid(row=1, column=0, sticky="ew", pady=(14, 0))
        self._dep_labels = {}
        for key, label, cmd in [
            ("node", "Node.js", ["node", "--version"]),
            ("npm", "npm", ["npm", "--version"]),
            ("opencode", "OpenCode", ["opencode", "--version"]),
            ("claude", "Claude Code", ["claude", "--version"]),
            ("warp", "Cloudflare WARP", ["warp-cli", "--version"]),
            ("git", "Git", ["git", "--version"]),
        ]:
            line = tk.Frame(body2, bg=THEME["card"])
            line.pack(fill="x", pady=1)
            tk.Label(line, text=label, bg=THEME["card"], fg=THEME["muted"], font=(ui.FONT, 9),
                     width=18, anchor="w").pack(side="left")
            lbl = tk.Label(line, text="...", bg=THEME["card"], fg=THEME["text"],
                           font=(ui.MONO, 9), anchor="w")
            lbl.pack(side="left")
            self._dep_labels[key] = (lbl, cmd)

        box = ui.LogBox(parent)
        box.frame.grid(row=2, column=0, sticky="nsew", pady=(14, 0))
        self._doc_box = box
        self._doc_refresh()
        self._refreshers.append(self._doc_refresh)

    def _doc_refresh(self):
        if not hasattr(self, "_dep_labels") or not self._dep_labels:
            return

        def work():
            out = {}
            for key, (lbl, cmd) in self._dep_labels.items():
                rc, text = C.run_cmd(cmd, timeout=20)
                value = text.strip().splitlines()[0] if text.strip() else ""
                if not value:
                    exe = C.which(cmd[0]) or C._which_ext(cmd[0])
                    if exe:
                        value = f"instalado: {exe}"
                out[key] = value
            return out

        def done(res, err):
            if err or not isinstance(res, dict):
                return
            for key, val in res.items():
                if key not in self._dep_labels:
                    continue
                lbl = self._dep_labels[key][0]
                try:
                    if not lbl.winfo_exists():
                        continue
                    if val:
                        lbl.configure(text=val[:90], fg=THEME["green"])
                    else:
                        lbl.configure(text="no encontrado", fg=THEME["red"])
                except Exception:
                    pass

        self.run_bg(work, done)

    def _doc_oplire(self):
        if self.need_engine():
            self.run_action(self._doc_box, OP.doctor, "[...] Ejecutando oplire doctor...")

    def _doc_models(self):
        if self.need_engine():
            self.run_action(self._doc_box, OP.models, "[...] Consultando modelos de Oplire...")

    def _doc_version(self):
        if self.need_engine():
            self.run_action(self._doc_box, OP.version, "[...] Consultando version de Oplire...")

    def _doc_all_models(self):
        def func():
            lines = ["=== MODELOS OPENCODE (anti Gravity / plugin) ==="]
            for m in AG.models_catalog():
                ctx = C.human_size(m["context"]) if m.get("context") else "?"
                out = C.human_size(m["output"]) if m.get("output") else "?"
                lines.append(f"  {m['id']:<44} ctx {ctx:<9} salida {out}")
            lines += ["", "=== MODELOS OPLIRE (motor local) ==="]
            rc, out = OP.models()
            lines.append(out.strip() if out.strip() else "(sin salida: motor no disponible)")
            lines += ["", "=== MODELO FREE CLAUDE CODE ==="]
            st = CL.status()
            lines.append(f"  MODEL = {st.get('model') or '(por defecto en el Admin UI)'}")
            lines.append(f"  Admin = {st.get('admin_url')}")
            return True, "\n".join(lines)
        self.run_action(self._doc_box, func, "[...] Recopilando modelos de todos los motores...")

    def _doc_full(self):
        def func():
            info = C.system_info()
            net = C.network_info()
            lines = [
                "================ NEXUS SUITE  ·  ANALISIS COMPLETO ================",
                f"Version NEXUS : {APP_VERSION}",
                f"Base          : {C.get_base_dir()}",
                f"Sistema       : {info['os']}",
                f"Arquitectura  : {info['arch']}   Python {info['python']}",
                f"Equipo        : {info['host']}  ·  usuario {info['user']}",
                f"CPU           : {info['cpu']}  ·  {info['cores']} nucleos",
                f"GPU           : {info.get('gpu') or 'no detectada'}",
                f"RAM           : {C.human_size(info['ram_free'])} libres / {C.human_size(info['ram_total'])}",
                f"Disco         : {C.human_size(info['disk_free'])} libres / {C.human_size(info['disk_total'])}",
                f"Encendido     : {C.human_uptime(info.get('uptime') or 0)}",
                f"Administrador : {'SI' if info['admin'] else 'no'}",
                "",
                "--- RED ---",
                f"IP local      : {net['local_ip']}  ({'privada' if net['private'] else 'publica' if net['private'] is False else '?'})",
                f"IP publica    : {net.get('public_ip') or '(sin salida o no consultada)'}",
                f"Internet      : {'SI' if net['internet'] else 'NO' if net['internet'] is False else '?'}",
                f"Gateway       : {net.get('gateway') or 'no detectado'}",
                f"DNS           : {net.get('dns') or 'automatico'}",
            ]
            for ad in (net.get("adapters") or [])[:5]:
                lines.append(f"  {ad.get('alias')}: {ad.get('ip')}  [{ad.get('category') or 'sin categoria'}]")
            lines += ["", "--- DEPENDENCIAS ---"]
            for d in C.dependency_audit():
                mark = "OK " if d["ok"] else ("FALTA" if d["required"] else "opc.")
                lines.append(f"  [{mark:5}] {d['name']:<18} {d['value']}")
                if not d["ok"] and d.get("hint"):
                    lines.append(f"          -> {d['hint']}")
            lines += ["", "--- MOTORES ---"]
            lines.append(f"Oplire exe    : {OP.find_oplire_exe() or 'NO ENCONTRADO'}")
            lines.append(f"Dashboard     : {'ACTIVO' if OP.dashboard_running() else 'detenido'} en {OP.dashboard_base()}")
            port = OP.opencode_server_port()
            lines.append(f"OpenCode local: {'ACTIVO' if OP.opencode_server_running(port, verify=False, fast=True) else 'detenido'} en 127.0.0.1:{port}")
            lines.append(f"Antigravity   : {'PLUGIN ACTIVO' if AG.test_plugin_configured() else 'plugin desactivado'}")
            lines.append(f"Cuentas AG    : {len(AG.list_accounts())}")
            lines.append(f"Claude FCC    : {'SERVIDOR ACTIVO' if CL.server_running() else 'detenido'}  ·  {CL.proxy_url()}")
            lines.append(f"uv / FCC      : {CL.uv_path() or 'NO INSTALADO'}  ·  proyecto {'OK' if CL.project_exists() else 'NO'}")
            lines += ["", "--- MODELOS DISPONIBLES ---"]
            catalog = AG.models_catalog()
            try:
                cfg = AG.read_json(AG.get_config_file()) or {}
                loaded = (((cfg.get("provider") or {}).get("google") or {}).get("models") or {})
            except Exception:
                loaded = {}
            lines.append(f"Antigravity   : {len(catalog)} en catalogo  ·  {len(loaded)} cargados en opencode.json")
            for m in catalog[:20]:
                lines.append(f"  [{'OK' if m['id'] in loaded else ' -'}] {m['id']}")
            if len(catalog) > 20:
                lines.append(f"  ... y {len(catalog) - 20} mas (ver Antigravity > Modelos)")
            lines.append(f"Claude FCC    : {CL.status().get('model') or '(por defecto en Admin UI)'}")
            lines += ["", "--- SESIONES ---"]
            rc, out = OP.sessions_status()
            lines.append(out.strip() if out.strip() else "(sin datos: motor Oplire no disponible)")
            lines.append("")
            lines.append("Recomendacion: usa 'Reparar sesiones' y 'Reparar plugin' si algo falla.")
            return True, "\n".join(lines)
        self.run_action(self._doc_box, func, "[...] Analizando equipo, red, motores y modelos...")

    def _doc_fix_sessions(self):
        if not self.need_engine():
            return
        if not messagebox.askyesno("Reparar sesiones",
                                   "Reparar sesiones corruptas de OpenCode?\n"
                                   "Se recomienda crear un backup en vCache antes."):
            return
        self.run_action(self._doc_box, OP.fix_sessions, "[...] Reparando sesiones...")

    def _doc_repair_plugin(self):
        def func():
            ok, msg, _patched, _checked = AG.repair_plugin()
            return ok, msg
        self.run_action(self._doc_box, func, "[...] Reparando plugin Antigravity...")

    def _doc_repair_opencode(self):
        self.run_action(self._doc_box, OP.repair_opencode,
                        "[...] Reparando OpenCode (postinstall npm)...")
        self.after(2500, self._doc_refresh)

    def _doc_ports(self):
        def func():
            dport = OP.dashboard_port()
            oport = OP.opencode_server_port()
            cport = CL.server_port()
            lines = [
                f"Dashboard Oplire 127.0.0.1:{dport} : {'OCUPADO' if OP.dashboard_running() else 'libre'}",
                f"OpenCode local  127.0.0.1:{oport} : {'OCUPADO' if OP.opencode_server_running(oport, verify=False, fast=True) else 'libre'}",
                f"Claude FCC      127.0.0.1:{cport} : {'OCUPADO' if CL.server_running() else 'libre'}",
            ]
            for port in (dport, oport, cport):
                pid, img = C.port_owner(port, fast=True)
                if pid:
                    lines.append(f"  puerto {port}: PID {pid} ({img or 'desconocido'})")
            return True, "\n".join(lines)
        self.run_action(self._doc_box, func, "[...] Comprobando puertos locales...")

    # ----------------------------------------------------------- TOOLS --------
    def _section_tools(self, parent):
        outer, body = self.card(parent, title="Instalacion real de componentes", accent=THEME["green"])
        outer.grid(row=0, column=0, sticky="ew")
        tk.Label(body, text=("Abre una consola real de NEXUS y ejecuta npm/winget de verdad. "
                             "Al terminar, pulsa F5 para refrescar la deteccion."),
                 bg=THEME["card"], fg=THEME["muted"], font=(ui.FONT, 9), anchor="w",
                 justify="left", wraplength=900).pack(fill="x", pady=(0, 8))
        self.btnrow(body, [
            ("Instalar OpenCode (npm)", lambda: self._tool_install("opencode"), "accent"),
            ("Reparar OpenCode (postinstall)", self._tool_repair_opencode, "warn"),
            ("Instalar Claude Code (npm)", lambda: self._tool_install("claude-code"), "accent"),
            ("Instalar WARP (winget)", lambda: self._tool_install("warp"), "accent"),
            ("Instalar TODO", lambda: self._tool_install("all"), "green"),
        ])

        outer2, body2 = self.card(parent, title="Estado de componentes (tiempo real)", accent=THEME["accent"])
        outer2.grid(row=1, column=0, sticky="ew", pady=(14, 0))
        self._tool_state = tk.Label(body2, text="Consultando...", bg=THEME["card"], fg=THEME["text"],
                                    font=(ui.MONO, 9), anchor="w", justify="left")
        self._tool_state.pack(fill="x")
        self._tool_refresh()
        self._refreshers.append(self._tool_refresh)

        outer3, body3 = self.card(parent, title="Descargas oficiales", accent=THEME["accent2"])
        outer3.grid(row=2, column=0, sticky="ew", pady=(14, 0))
        tk.Label(body3, text="Enlaces oficiales. Se abren en el navegador predeterminado.",
                 bg=THEME["card"], fg=THEME["muted"], font=(ui.FONT, 9), anchor="w",
                 justify="left", wraplength=900).pack(fill="x", pady=(0, 8))
        self.btnrow(body3, [
            ("Descargar Cloudflare One Client", lambda: self._open_url(CLOUDFLARE_CLIENT_URL), "accent"),
            ("Descargar Node.js (LTS)", lambda: self._open_url("https://nodejs.org/"), "ghost"),
            ("Descargar Everything", lambda: self._open_url(EVERYTHING_URL), "ghost"),
            ("Descargar WARP", lambda: self._open_url("https://1.1.1.1/"), "ghost"),
        ])

        outer4, body4 = self.card(parent, title="Accesos del sistema", accent=THEME["accent"])
        outer4.grid(row=3, column=0, sticky="ew", pady=(14, 0))
        self.btnrow(body4, [
            ("Abrir carpeta NEXUS", lambda: self._open_folder(C.get_base_dir()), "ghost"),
            ("Abrir backups de sesiones", lambda: self._open_folder(OP.sessions_backup_root()), "ghost"),
            ("Abrir config Claude FCC", lambda: self._open_folder(CL.config_dir()), "ghost"),
            ("Abrir config Antigravity", lambda: self._open_folder(AG.get_config_dir()), "ghost"),
        ])

        outer5, body5 = self.card(parent, title="Consolas CMD del sistema", accent=THEME["accent2"])
        outer5.grid(row=4, column=0, sticky="ew", pady=(14, 0))
        tk.Label(body5, text="Consola CMD nueva, visible e interactiva en la carpeta del componente.",
                 bg=THEME["card"], fg=THEME["muted"], font=(ui.FONT, 9), anchor="w",
                 justify="left", wraplength=900).pack(fill="x", pady=(0, 10))
        self.btnrow(body5, [
            (f"{ICONS['server']}  CMD en NEXUS", lambda: self._tool_cmd(C.get_base_dir()), "accent"),
            (f"{ICONS['server']}  CMD en Oplire", lambda: self._tool_cmd(OP.oplire_dir()), "ghost"),
            (f"{ICONS['server']}  CMD en OpenCode", lambda: self._tool_cmd(AG.get_config_dir()), "ghost"),
            (f"{ICONS['server']}  CMD en Antigravity", lambda: self._tool_cmd(C.antigravity_dir()), "ghost"),
            (f"{ICONS['server']}  CMD en Claude FCC", lambda: self._tool_cmd(CL.project_dir() or C.get_base_dir()), "ghost"),
        ])

        box = ui.LogBox(parent)
        box.frame.grid(row=5, column=0, sticky="nsew", pady=(14, 0))
        self._tools_box = box
        self.log(box, "Instaladores, descargas y accesos. Cada accion abre su propia consola o navegador.")

    def _tool_refresh(self):
        if not hasattr(self, "_tool_state") or not self._tool_state.winfo_exists():
            return

        def compute():
            def ver(cmd):
                rc, out = C.run_program(cmd, timeout=15)
                return (out or "").strip().splitlines()[0][:70] if rc == 0 and out.strip() else "no detectado"
            return {
                "node": ver(["node", "--version"]),
                "npm": ver(["npm", "--version"]),
                "opencode": ("DANADO: usa Reparar OpenCode" if OP.opencode_broken()
                             else (AG.get_opencode_path() or "no instalado")),
                "claude": C.which("claude") or "no instalado",
                "uv": CL.uv_path() or "no instalado",
                "warp": C.which("warp-cli") or "no instalado",
            }

        def apply(res):
            if not res or not hasattr(self, "_tool_state") or not self._tool_state.winfo_exists():
                return
            lines = [f"{k:<9}: {v}" for k, v in res.items()]
            missing = [k for k, v in res.items()
                       if "no " in str(v) or "DANADO" in str(v)]
            if missing:
                lines.append("")
                lines.append("Falta: " + ", ".join(missing) + ". Usa los botones de instalacion de arriba.")
            self._tool_state.configure(text="\n".join(lines),
                                       fg=THEME["yellow"] if missing else THEME["green"])

        self._schedule_refresh("tools", compute, apply)

    def _open_url(self, url):
        import webbrowser
        webbrowser.open(url)

    def _open_folder(self, path):
        try:
            os.startfile(path)
        except Exception:
            messagebox.showinfo("Carpeta", path)

    def _tool_everything(self):
        found = C.find_everything()
        if not found:
            if messagebox.askyesno(
                    "Everything",
                    "No se encontro Everything (ni instalado ni portable).\n\n"
                    "Abrir la pagina de descarga?"):
                self._open_url(EVERYTHING_URL)
            return
        try:
            os.startfile(found["path"])
            self._tool_output(f"[OK] Everything abierto ({found['kind']}): {found['path']}", THEME["green"])
        except Exception as exc:
            messagebox.showwarning("Everything", f"No se pudo abrir Everything:\n{exc}")

    def _tool_output(self, text, color=None):
        try:
            self.log(self._tools_box, text, color)
        except Exception:
            messagebox.showinfo("NEXUS", text)

    def _tool_cmd(self, cwd=None):
        cwd = cwd or C.get_base_dir()
        if C.open_terminal(cwd, title="NEXUS CMD"):
            self._tool_output(f"[OK] Consola CMD abierta en: {cwd}", THEME["green"])
        else:
            self._tool_output(f"[!] No se pudo abrir CMD en: {cwd}", THEME["yellow"])

    def _tool_warp(self):
        self.run_action(self._tools_box, OP.warp_status_raw, "[...] Consultando WARP...")

    def _tool_install(self, target):
        self.run_action(self._tools_box,
                        lambda: OP.install_component(target),
                        f"[...] Preparando instalacion real de {target}...")
        self.after(2500, self._tool_refresh)

    def _tool_repair_opencode(self):
        self.run_action(self._tools_box, OP.repair_opencode,
                        "[...] Reparando binario de OpenCode (postinstall)...")
        self.after(2500, self._tool_refresh)

    # ====================================================== ANTIGRAVITY ========
    def _ag_diag(self):
        def func():
            d = AG.diagnostics()
            lines = [
                f"opencode: {d['opencode_path'] or 'NO ENCONTRADO'}",
                f"node: {d['node'] or 'no encontrado'}",
                f"npm: {d['npm'] or 'no encontrado'}",
                f"Config dir: {d['config_dir']}",
                f"Config file: {d['config_file'] or '(ninguno)'}",
                f"Plugin configurado: {'SI' if d['plugin_configured'] else 'no'}",
                f"Plugin en cache: {'si' if d['plugin_cached'] else 'no'} ({d['cache_dirs']} carpeta/s)",
                f"Cuentas: {d['accounts_count']}  ({d['accounts_file']})",
                f"OpenCode abierto: {'si' if d['opencode_running'] else 'no'}",
            ]
            return True, "\n".join(lines)
        box = getattr(self, "_ag_acc_box", None) or getattr(self, "_ag_plugin_box", None)
        self.run_action(box, func, "[...] Ejecutando diagnostico...")

    def _ag_quotas(self):
        def func():
            ok, text, _data = AG.quotas_report()
            return ok, text
        box = getattr(self, "_ag_acc_box", None)
        self.run_action(box, func, "[...] Consultando cuotas reales en linea...")

    def _ag_login(self):
        def func():
            if not AG.test_plugin_configured():
                AG.enable_plugin()
            return AG.open_plugin_login_console()
        if self._active_page == "ag_accounts":
            box = getattr(self, "_ag_acc_box", None)
        else:
            box = getattr(self, "_ag_plugin_box", None)
        self.run_action(box, func, "[...] Abriendo gestor OAuth...")

    # ----------------------------------------------------------- CUENTAS ------
    def page_ag_accounts(self, parent):
        parent.grid_rowconfigure(1, weight=1)
        toolbar = tk.Frame(parent, bg=THEME["bg"])
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        self.btnrow(toolbar, [
            (f"{ICONS['refresh']}  Refrescar", self._ag_accounts_refresh, "ghost"),
            (f"{ICONS['swap']}  Activar / Desactivar", self._ag_toggle_account, "accent"),
            (f"{ICONS['add']}  Agregar cuenta", self._ag_login, "green"),
            (f"{ICONS['warn']}  Ver cuotas (real)", self._ag_quotas, "accent"),
            (f"{ICONS['ok']}  Verificar cuenta", lambda: self._ag_plugin_action("verify"), "accent"),
            (f"{ICONS['ok']}  Verificar todas", lambda: self._ag_plugin_action("verify-all"), "accent"),
            ("Diagnostico", self._ag_diag, "ghost"),
            (f"{ICONS['x']}  Borrar cuenta", self._ag_delete_account, "danger"),
            (f"{ICONS['trash']}  Borrar todo", self._ag_reset_accounts, "danger"),
        ], bg=THEME["bg"])

        tf = tk.Frame(parent, bg=THEME["card"], highlightbackground=THEME["border"], highlightthickness=1)
        tf.grid(row=1, column=0, sticky="nsew")
        tf.grid_columnconfigure(0, weight=1)
        tf.grid_rowconfigure(0, weight=1)
        cols = ("email", "estado", "projectId", "agregada")
        self._ag_tree = ttk.Treeview(tf, columns=cols, show="headings", selectmode="browse")
        for c, w, t in zip(cols, (300, 130, 240, 160), ("Email", "Estado", "Project ID", "Agregada")):
            self._ag_tree.heading(c, text=t)
            self._ag_tree.column(c, width=w, minwidth=80, anchor="w", stretch=(c in ("email", "projectId")))
        self._ag_tree.grid(row=0, column=0, sticky="nsew", padx=1, pady=1)
        sbn = ttk.Scrollbar(tf, orient="vertical", command=self._ag_tree.yview,
                            style="Nexus.Vertical.TScrollbar")
        self._ag_tree.configure(yscrollcommand=sbn.set)
        sbn.grid(row=0, column=1, sticky="ns")

        self._ag_acc_box = ui.LogBox(parent, height=5, title="CUENTAS - SALIDA")
        self._ag_acc_box.frame.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        self._ag_accounts_refresh()
        self._refreshers.append(self._ag_accounts_refresh)

    def _ag_accounts_refresh(self):
        if not hasattr(self, "_ag_tree") or not self._ag_tree.winfo_exists():
            return
        tree = self._ag_tree
        selected = None
        sel = tree.selection()
        if sel:
            selected = tree.item(sel[0], "values")[0]
        for i in tree.get_children():
            tree.delete(i)
        try:
            accounts = AG.list_accounts()
            if not accounts:
                tree.insert("", "end", values=("(sin cuentas)", "", "", ""))
                return
            for a in accounts:
                iid = tree.insert("", "end", values=(a["email"],
                                                     "ACTIVA" if a["enabled"] else "DESACTIVADA",
                                                     a["projectId"], a["added"]))
                if selected and a["email"] == selected:
                    tree.selection_set(iid)
        except Exception as e:
            tree.insert("", "end", values=(f"Error: {e}", "", "", ""))

    def _ag_selected_email(self):
        sel = self._ag_tree.selection() if hasattr(self, "_ag_tree") else None
        if not sel:
            return None
        return self._ag_tree.item(sel[0], "values")[0]

    def _ag_toggle_account(self):
        email = self._ag_selected_email()
        if not email:
            messagebox.showinfo("Cuentas", "Selecciona una cuenta en la lista.")
            return
        for a in AG.list_accounts():
            if a["email"] == email:
                ok, msg = AG.set_account_enabled(a["index"])
                self.log(self._ag_acc_box, ("[OK] " if ok else "[ERROR] ") + msg,
                         THEME["green"] if ok else THEME["red"])
                break
        self._ag_accounts_refresh()

    def _ag_delete_account(self):
        email = self._ag_selected_email()
        if not email or email.startswith("("):
            messagebox.showinfo("Cuentas", "Selecciona una cuenta en la lista.")
            return
        if not messagebox.askyesno("Borrar cuenta", f"Eliminar la cuenta:\n{email}\n\n(Se guarda un respaldo)"):
            return
        for a in AG.list_accounts():
            if a["email"] == email:
                ok, msg = AG.delete_account(a["index"])
                self.log(self._ag_acc_box, ("[OK] " if ok else "[ERROR] ") + msg,
                         THEME["green"] if ok else THEME["red"])
                break
        self._ag_accounts_refresh()

    def _ag_reset_accounts(self):
        if not messagebox.askyesno("Borrar TODO", "Borrar TODAS las cuentas (se respalda)?"):
            return
        ok, msg = AG.reset_accounts()
        self.log(self._ag_acc_box, ("[OK] " if ok else "[ERROR] ") + msg,
                 THEME["green"] if ok else THEME["red"])
        self._ag_accounts_refresh()

    def _ag_plugin_action(self, action):
        """Abre la consola del plugin con la opcion indicada preseleccionada."""
        if not AG.test_plugin_configured():
            AG.enable_plugin()
        idx = None
        if action == "verify":
            email = self._ag_selected_email()
            if not email or email.startswith("("):
                messagebox.showinfo("Cuentas", "Selecciona en la lista la cuenta a verificar.")
                return
            for a in AG.list_accounts():
                if a["email"] == email:
                    idx = a["index"]
                    break
        self.run_action(self._ag_acc_box,
                        lambda: AG.open_plugin_menu(action, index=idx),
                        "[...] Abriendo consola del plugin...")

    def _ag_acc_configure_models(self):
        self.run_action(self._ag_acc_box, AG.configure_models, "[...] Configurando modelos...")

    # ------------------------------------------------------------ PLUGIN ------
    def page_ag_plugin(self, parent):
        outer, body = self.card(parent, title="Control del plugin", accent=THEME["green"])
        outer.grid(row=0, column=0, sticky="ew")
        self._ag_plugin_state = tk.Label(body, text="...", bg=THEME["card"], fg=THEME["text"],
                                         font=(ui.FONT, 13, "bold"), anchor="w")
        self._ag_plugin_state.pack(fill="x", pady=(0, 4))
        self._ag_plugin_detail =         tk.Label(body, text="", bg=THEME["card"], fg=THEME["muted"],
                                          font=(ui.MONO, 9), anchor="w", justify="left")
        self._ag_plugin_detail.pack(fill="x", pady=(0, 6))
        tk.Label(body, text=("Activar el plugin tambien carga los modelos en opencode.json. "
                             "El mantenimiento (reparacion Node, auto-update y API key) vive aqui; "
                             "no hay secciones separadas."),
                 bg=THEME["card"], fg=THEME["muted"], font=(ui.FONT, 9), anchor="w",
                 justify="left", wraplength=900).pack(fill="x", pady=(0, 10))
        self.btnrow(body, [
            (f"{ICONS['ok']}  Activar plugin", self._ag_plugin_enable, "green"),
            (f"{ICONS['x']}  Desactivar plugin", self._ag_plugin_disable, "danger"),
            (f"{ICONS['star']}  Menu OAuth / cuentas", self._ag_login, "accent"),
            (f"{ICONS['tools']}  Reparar plugin (Node)", self._ag_repair, "accent"),
            (f"{ICONS['refresh']}  Auto-update OFF", self._ag_autoupdate, "ghost"),
            ("Diagnostico", self._ag_diag, "ghost"),
        ])

        box = ui.LogBox(parent, height=6)
        box.frame.grid(row=1, column=0, sticky="nsew", pady=(14, 0))
        self._ag_plugin_box = box

        outer2, body2 = self.card(parent, title="API Key de Google (camino sin plugin)", accent=THEME["accent"])
        outer2.grid(row=2, column=0, sticky="ew", pady=(14, 0))
        tk.Label(body2, text="Con el plugin desactivado, los modelos gemini-* usan tu API key. "
                             "Los modelos antigravity-* requieren OAuth.",
                 bg=THEME["card"], fg=THEME["muted"], font=(ui.FONT, 9), anchor="w",
                 justify="left", wraplength=900).pack(fill="x", pady=(0, 8))
        self._ag_key_label = tk.Label(body2, text="", bg=THEME["card"], fg=THEME["muted"],
                                      font=(ui.MONO, 9), anchor="w")
        self._ag_key_label.pack(fill="x", pady=(0, 8))
        kr = tk.Frame(body2, bg=THEME["card"])
        kr.pack(fill="x", pady=(0, 10))
        tk.Label(kr, text="API Key:", bg=THEME["card"], fg=THEME["text"], font=(ui.FONT, 10)).pack(side="left")
        self._ag_key_var = tk.StringVar()
        tk.Entry(kr, textvariable=self._ag_key_var, show="•", width=46, bg=THEME["card2"],
                 fg=THEME["text"], insertbackground=THEME["text"], relief="flat",
                 font=(ui.MONO, 10)).pack(side="left", padx=8, ipady=4)
        self.btnrow(body2, [
            ("Guardar API Key", self._ag_save_key, "green"),
            ("Quitar API Key", self._ag_clear_key, "danger"),
        ])

        self._ag_maint_box = box
        self._ag_plugin_refresh()
        self._ag_key_refresh()
        self._refreshers.append(self._ag_plugin_refresh)

    def _ag_plugin_refresh(self):
        if not hasattr(self, "_ag_plugin_state") or not self._ag_plugin_state.winfo_exists():
            return
        try:
            configured = AG.test_plugin_configured()
            self._ag_plugin_state.configure(
                text="PLUGIN ACTIVO" if configured else "PLUGIN DESACTIVADO",
                fg=THEME["green"] if configured else THEME["yellow"])
            self._ag_plugin_detail.configure(
                text=f"Config: {AG.get_config_file() or '(ninguno)'}\n"
                     f"Cache: {'descargado' if AG.test_plugin_cached() else 'no descargado'}")
        except Exception as e:
            self._ag_plugin_state.configure(text=f"Error: {e}", fg=THEME["red"])

    def _ag_plugin_enable(self):
        self.run_action(self._ag_plugin_box, AG.enable_plugin, "[...] Activando plugin...")
        self.after(700, self._ag_plugin_refresh)

    def _ag_plugin_disable(self):
        self.run_action(self._ag_plugin_box, AG.disable_plugin, "[...] Desactivando plugin...")
        self.after(700, self._ag_plugin_refresh)

    def _ag_plugin_models(self):
        self.show_page("ag_models")

    # ----------------------------------------------------------- MODELOS ------
    def page_ag_models(self, parent):
        outer, body = self.card(parent, title="Modelos gestionados", accent=THEME["accent2"])
        outer.grid(row=0, column=0, sticky="ew")
        tk.Label(body, text=("Se cargan automaticamente al ACTIVAR el plugin (provider 'google' de "
                             "opencode.json). No hay boton manual de configuracion: si falta alguno, "
                             "pulsa 'Recargar' o reactiva el plugin."),
                 bg=THEME["card"], fg=THEME["muted"], font=(ui.FONT, 9), anchor="w").pack(fill="x", pady=(0, 6))
        tf = tk.Frame(body, bg=THEME["card"], highlightbackground=THEME["border"], highlightthickness=1)
        tf.pack(fill="both", expand=True)
        cols = ("sel", "clave", "nombre")
        self._ag_models_tree = ttk.Treeview(tf, columns=cols, show="headings", height=8, selectmode="browse")
        for c, w, t in zip(cols, (60, 300, 320), ("", "Clave", "Nombre")):
            self._ag_models_tree.heading(c, text=t)
            self._ag_models_tree.column(c, width=w, minwidth=40, anchor="w", stretch=(c == "nombre"))
        self._ag_models_tree.pack(side="left", fill="both", expand=True, padx=1, pady=1)
        sbn = ttk.Scrollbar(tf, orient="vertical", command=self._ag_models_tree.yview,
                            style="Nexus.Vertical.TScrollbar")
        self._ag_models_tree.configure(yscrollcommand=sbn.set)
        sbn.pack(side="right", fill="y")
        self._ag_models_refresh()

        self.btnrow(body, [
            (f"{ICONS['refresh']}  Recargar estado", self._ag_models_refresh, "accent"),
            (f"{ICONS['ok']}  Recargar modelos (activar plugin)", self._ag_models_reload, "green"),
            (f"{ICONS['external']}  Abrir opencode.json", self._ag_open_config, "ghost"),
            (f"{ICONS['x']}  Quitar modelos gestionados", self._ag_remove_models, "danger"),
        ])

        box = ui.LogBox(parent, height=6)
        box.frame.grid(row=1, column=0, sticky="nsew", pady=(14, 0))
        self._ag_models_box = box
        self.log(box, "Configura o quita los modelos gestionados por Antigravity.")

    def _ag_models_refresh(self):
        tree = getattr(self, "_ag_models_tree", None)
        if tree is None or not tree.winfo_exists():
            return
        for i in tree.get_children():
            tree.delete(i)
        try:
            configured = AG.read_json(AG.get_config_file()) or {}
            gm = (((configured.get("provider") or {}).get("google") or {}).get("models") or {})
            for key, meta in AG.MODELS.items():
                tree.insert("", "end", values=("OK" if key in gm else "-", key, meta.get("name", "")))
        except Exception as e:
            tree.insert("", "end", values=("", f"[Error] {e}", ""))

    def _ag_models_reload(self):
        self.run_action(self._ag_models_box, AG.enable_plugin,
                        "[...] Activando/recargando plugin y modelos...")
        self.after(1200, self._ag_models_refresh)

    def _ag_open_config(self):
        path = AG.get_config_file()
        if not path:
            messagebox.showinfo("Modelos",
                                "Todavia no existe opencode.json.\n"
                                "Activa el plugin para crearlo con los modelos.")
            return
        if not C.open_path(path):
            messagebox.showinfo("Modelos", path)

    def _ag_remove_models(self):
        if messagebox.askyesno("Modelos", "Quitar los modelos gestionados de la configuracion?"):
            self.run_action(self._ag_models_box, AG.remove_models, "[...] Quitando modelos...")
            self.after(700, self._ag_models_refresh)

    # ------------------------------------------------------ MANTENIMIENTO -----
    def _ag_key_refresh(self):
        if hasattr(self, "_ag_key_label") and self._ag_key_label.winfo_exists():
            self._ag_key_label.configure(text=f"API key actual: {AG.mask_key(AG.get_google_api_key())}")

    def _ag_repair(self):
        def func():
            ok, msg, patched, checked = AG.repair_plugin()
            return ok, msg
        self.run_action(self._ag_maint_box, func, "[...] Reparando compatibilidad Node...")

    def _ag_autoupdate(self):
        self.run_action(self._ag_maint_box, AG.disable_plugin_auto_update, "[...] Desactivando auto-update...")

    def _ag_save_key(self):
        key = self._ag_key_var.get().strip()
        if not key:
            messagebox.showinfo("API Key", "Pega una API key primero.")
            return
        ok, msg = AG.set_google_api_key(key)
        self._ag_key_var.set("")
        self.log(self._ag_maint_box, ("[OK] " if ok else "[ERROR] ") + msg,
                 THEME["green"] if ok else THEME["red"])
        self._ag_key_refresh()

    def _ag_clear_key(self):
        ok, msg = AG.clear_google_api_key()
        self.log(self._ag_maint_box, ("[OK] " if ok else "[ERROR] ") + msg,
                 THEME["yellow"] if ok else THEME["red"])
        self._ag_key_refresh()

    # =========================================================== CLAUDE ========
    def page_claude(self, parent):
        outer, body = self.card(parent, title="Free Claude Code (servidor)", accent=THEME["green"])
        outer.grid(row=0, column=0, sticky="ew")
        self._cl_status = tk.Label(body, text="Consultando...", bg=THEME["card"], fg=THEME["text"],
                                   font=(ui.MONO, 9), anchor="w", justify="left")
        self._cl_status.pack(fill="x", pady=(0, 8))
        self.btnrow(body, [
            (f"{ICONS['play']}  Iniciar servidor FCC", self._cl_start, "green"),
            (f"{ICONS['stop']}  Detener servidor", self._cl_stop, "danger"),
            (f"{ICONS['external']}  Abrir Admin UI", CL.open_admin, "accent"),
            (f"{ICONS['external']}  Abrir proxy", CL.open_proxy, "ghost"),
            (f"{ICONS['refresh']}  Refrescar", self._cl_status_refresh, "ghost"),
            (f"{ICONS['doctor']}  fcc-doctor", self._cl_doctor_run, "accent"),
        ])

        outer2, body2 = self.card(parent, title="Requisitos (tiempo real)", accent=THEME["yellow"])
        outer2.grid(row=1, column=0, sticky="ew", pady=(14, 0))
        self._cl_reqs = tk.Label(body2, text="...", bg=THEME["card"], fg=THEME["text"],
                                 font=(ui.MONO, 9), anchor="w", justify="left")
        self._cl_reqs.pack(fill="x", pady=(0, 8))
        self.btnrow(body2, [
            (f"{ICONS['tools']}  Preparar FCC (auto)", self._cl_prepare, "green"),
            (f"{ICONS['tools']}  Instalar uv", self._cl_install_uv, "accent"),
            (f"{ICONS['tools']}  Sincronizar dependencias", self._cl_sync, "accent"),
            (f"{ICONS['refresh']}  Actualizar uv + deps", self._cl_update, "ghost"),
            (f"{ICONS['add']}  Instalar Claude Code", self._cl_install_claude, "ghost"),
            (f"{ICONS['server']}  Instalar/reparar FCC", self._cl_install_fcc, "ghost"),
            (f"{ICONS['server']}  Abrir carpeta FCC", lambda: C.open_path(CL.project_dir() or C.get_base_dir()), "ghost"),
        ])

        outer3, body3 = self.card(parent, title="Configuracion (~/.fcc/.env)", accent=THEME["accent2"])
        outer3.grid(row=2, column=0, sticky="ew", pady=(14, 0))
        self._cl_conf = tk.Label(body3, text="", bg=THEME["card"], fg=THEME["muted"],
                                 font=(ui.MONO, 9), anchor="w", justify="left")
        self._cl_conf.pack(fill="x", pady=(0, 8))
        mr = tk.Frame(body3, bg=THEME["card"])
        mr.pack(fill="x", pady=(0, 8))
        tk.Label(mr, text="MODEL:", bg=THEME["card"], fg=THEME["text"],
                 font=(ui.FONT, 10), width=9, anchor="w").pack(side="left")
        self._cl_model_var = tk.StringVar()
        tk.Entry(mr, textvariable=self._cl_model_var, width=58, bg=THEME["card2"],
                 fg=THEME["text"], insertbackground=THEME["text"], relief="flat",
                 font=(ui.MONO, 10)).pack(side="left", padx=6, ipady=4)
        ui.button(mr, "Guardar MODEL", self._cl_save_model, "accent").pack(side="left", padx=6)
        kr = tk.Frame(body3, bg=THEME["card"])
        kr.pack(fill="x", pady=(0, 8))
        tk.Label(kr, text="API KEY:", bg=THEME["card"], fg=THEME["text"],
                 font=(ui.FONT, 10), width=9, anchor="w").pack(side="left")
        self._cl_key_name = ttk.Combobox(kr, values=list(CL.PROVIDER_KEYS), width=28,
                                         state="readonly")
        self._cl_key_name.pack(side="left", padx=(0, 6))
        self._cl_key_name.set("NVIDIA_NIM_API_KEY")
        self._cl_key_value = tk.Entry(kr, show="•", width=40, bg=THEME["card2"],
                                      fg=THEME["text"], insertbackground=THEME["text"],
                                      relief="flat", font=(ui.MONO, 10))
        self._cl_key_value.pack(side="left", padx=6, ipady=4)
        ui.button(kr, "Guardar key", self._cl_save_key, "green").pack(side="left", padx=4)
        ui.button(kr, "Borrar key", self._cl_delete_key, "danger").pack(side="left", padx=4)
        self.btnrow(body3, [
            (f"{ICONS['external']}  Abrir .env", self._cl_open_env, "ghost"),
            (f"{ICONS['refresh']}  Recargar config", self._cl_status_refresh, "ghost"),
        ])

        box = ui.LogBox(parent, height=7)
        box.frame.grid(row=3, column=0, sticky="nsew", pady=(14, 0))
        self._cl_box = box
        self.log(box, "Free Claude Code integrado. Inicia el servidor y abre el Admin UI para "
                      "elegir proveedor/modelo; tambien puedes fijar MODEL y API keys aqui.")
        self._cl_status_refresh()
        self._refreshers.append(self._cl_status_refresh)

    def _cl_status_refresh(self):
        if not hasattr(self, "_cl_status") or not self._cl_status.winfo_exists():
            return

        def compute():
            return CL.status(), CL.requirements()

        def apply(res):
            if not res or not hasattr(self, "_cl_status") or not self._cl_status.winfo_exists():
                return
            st, reqs = res
            lines = [
                f"Proyecto   : {st['project_dir'] or 'NO ENCONTRADO'}",
                f"uv         : {st['uv'] or 'NO INSTALADO'}",
                f"Entorno    : {'listo (por equipo)' if st['venv'] else 'sin sincronizar'}",
                f"Servidor   : {'● ACTIVO' if st['server_running'] else '○ detenido'}  ·  {st['proxy_url']}",
                f"Admin UI   : {st['admin_url']}",
                f"Config     : {st['env_path']}{'  (existe)' if st['env_exists'] else '  (no existe)'}",
                f"Modelo     : {st['model'] or '(por defecto en Admin UI)'}",
                f"Proveedores: {', '.join(st['providers']) if st['providers'] else '(ninguno con API key)'}",
                f"API key    : {st.get('provider_issue') or 'OK (modelo y clave compatibles)'}",
                f"Claude Code: {st['claude_code'] or 'no instalado'}",
            ]
            self._cl_status.configure(
                text="\n".join(lines),
                fg=(THEME["green"] if st["server_running"] and not st.get("provider_issue")
                    else THEME["yellow"] if st["uv_ok"] and st["project_exists"]
                    else THEME["red"]))
            missing = [r for r in reqs if r["required"] and not r["ok"]]
            req_lines = []
            for r in reqs:
                mark = "OK   " if r["ok"] else ("FALTA" if r["required"] else "opc. ")
                req_lines.append(f"[{mark}] {r['name']:<24} {r['value']}")
                if not r["ok"] and r.get("hint"):
                    req_lines.append(f"        -> {r['hint']}")
            self._cl_reqs.configure(text="\n".join(req_lines),
                                    fg=THEME["yellow"] if missing else THEME["green"])
            if hasattr(self, "_cl_conf") and self._cl_conf.winfo_exists():
                self._cl_conf.configure(
                    text=f"Archivo: {st['env_path']}\n"
                         f"Modelo actual: {st['model'] or '(sin definir)'}\n"
                         f"Claves detectadas: {', '.join(st['providers']) or '(ninguna)'}")
            if hasattr(self, "_cl_model_var"):
                current = self._cl_model_var.get().strip()
                if not current and st["model"]:
                    self._cl_model_var.set(st["model"])

        self._schedule_refresh("claude", compute, apply)

    def _cl_log_box(self):
        order = {
            "claude_agents": ("_cl_agents_box", "_cl_box", "_cl_doc_box"),
            "claude_doctor": ("_cl_doc_box", "_cl_box", "_cl_agents_box"),
        }.get(getattr(self, "_active_page", ""), ("_cl_box", "_cl_agents_box", "_cl_doc_box"))
        for name in order:
            box = getattr(self, name, None)
            try:
                if box is not None and box.frame.winfo_exists():
                    return box
            except Exception:
                pass
        return getattr(self, "_cl_box", None)

    def _cl_start(self):
        self.run_action(self._cl_log_box(), CL.start_server, "[...] Iniciando servidor FCC...")
        self.after(2500, self._cl_status_refresh)

    def _cl_stop(self):
        if messagebox.askyesno("Free Claude Code", "Detener el servidor FCC?"):
            self.run_action(self._cl_log_box(), CL.stop_server, "[...] Deteniendo servidor FCC...")
            self.after(1500, self._cl_status_refresh)

    def _cl_install_uv(self):
        self.run_action(self._cl_log_box(), CL.install_uv, "[...] Abriendo instalador oficial de uv...")

    def _cl_prepare(self):
        self.run_action(self._cl_log_box(), CL.prepare,
                        "[...] Preparando FCC (proyecto + uv + dependencias)...")
        self.after(3000, self._cl_status_refresh)

    def _cl_install_fcc(self):
        self.run_action(self._cl_log_box(), CL.install_project,
                        "[...] Descargando Free Claude Code si falta...")
        self.after(3000, self._cl_status_refresh)

    def _cl_sync(self):
        self.run_action(self._cl_log_box(), CL.sync_dependencies,
                        "[...] Sincronizando dependencias (puede tardar)...")
        self.after(3000, self._cl_status_refresh)

    def _cl_update(self):
        self.run_action(self._cl_log_box(), CL.update_project,
                        "[...] Actualizando uv y dependencias...")
        self.after(3000, self._cl_status_refresh)

    def _cl_install_claude(self):
        self.run_action(self._cl_log_box(), CL.install_claude_code,
                        "[...] Abriendo instalador de Claude Code...")

    def _cl_doctor_run(self):
        self.run_action(self._cl_log_box(), CL.doctor, "[...] Ejecutando fcc-doctor...")

    def _cl_save_model(self):
        model = self._cl_model_var.get().strip()
        if not model:
            messagebox.showinfo("Claude", "Escribe el identificador del modelo (p. ej. provider/modelo).")
            return
        ok, msg = CL.set_env_value("MODEL", model)
        self.log(self._cl_box, ("[OK] " if ok else "[ERROR] ") + msg +
                 ("\nReinicia el servidor FCC para aplicarlo." if ok else ""),
                 THEME["green"] if ok else THEME["red"])
        self._cl_status_refresh()

    def _cl_save_key(self):
        name = (self._cl_key_name.get() or "").strip()
        value = self._cl_key_value.get().strip()
        if not name or not value:
            messagebox.showinfo("Claude", "Elige la variable y pega la API key.")
            return
        ok, msg = CL.set_env_value(name, value)
        self._cl_key_value.delete(0, "end")
        self.log(self._cl_box, ("[OK] " if ok else "[ERROR] ") + msg, THEME["green"] if ok else THEME["red"])
        self._cl_status_refresh()

    def _cl_delete_key(self):
        name = (self._cl_key_name.get() or "").strip()
        if not name:
            return
        ok, msg = CL.delete_env_value(name)
        self.log(self._cl_box, ("[OK] " if ok else "[ERROR] ") + msg,
                 THEME["yellow"] if ok else THEME["red"])
        self._cl_status_refresh()

    def _cl_open_env(self):
        path = CL.env_path()
        if not os.path.isfile(path):
            messagebox.showinfo("Claude",
                                "Todavia no existe .fcc/.env.\n\nGuarda MODEL o una API key primero "
                                "para crearlo.")
            return
        if not C.open_path(path):
            messagebox.showinfo("Claude", path)

    def page_claude_agents(self, parent):
        outer, body = self.card(parent, title="Agentes de Free Claude Code", accent=THEME["green"])
        outer.grid(row=0, column=0, sticky="ew")
        tk.Label(body, text=("Cada boton abre una consola real con el agente elegido. FCC enruta ese "
                             "agente por su proxy local (127.0.0.1:8082) y usa el proveedor configurado "
                             "en el Admin UI. Si el agente no esta instalado, FCC mostrara en la consola "
                             "el comando oficial para instalarlo."),
                 bg=THEME["card"], fg=THEME["muted"], font=(ui.FONT, 9), anchor="w",
                 justify="left", wraplength=900).pack(fill="x", pady=(0, 10))
        ff = ui.FlowFrame(body, gap=10, row_gap=10, bg=THEME["card"])
        ff.pack(fill="x")
        missing = []
        for key, (label, cmd) in CL.AGENTS.items():
            issue = CL.agent_issue(key)
            if issue:
                missing.append(f"{label}: {issue}")
            ff.add(self.btn(ff, f"{ICONS['play']}  {label}  {'(OK)' if not issue else '(revisar)'}",
                            lambda k=key: self._cl_agent(k), "green" if not issue else "accent"))
        if missing:
            tk.Label(body, text=("Agentes que necesitan atencion (FCC mostrara el comando oficial):\n  "
                                 + "\n  ".join(missing)),
                     bg=THEME["card"], fg=THEME["yellow"], font=(ui.MONO, 8), anchor="w",
                     justify="left", wraplength=900).pack(fill="x", pady=(8, 0))

        outer2, body2 = self.card(parent, title="Servidor y utilidades", accent=THEME["accent"])
        outer2.grid(row=1, column=0, sticky="ew", pady=(14, 0))
        self.btnrow(body2, [
            (f"{ICONS['play']}  Iniciar servidor", self._cl_start, "green"),
            (f"{ICONS['external']}  Abrir Admin UI", CL.open_admin, "accent"),
            (f"{ICONS['doctor']}  fcc-doctor", self._cl_doctor_run, "ghost"),
            (f"{ICONS['refresh']}  Actualizar", self._cl_update, "ghost"),
        ])

        box = ui.LogBox(parent)
        box.frame.grid(row=2, column=0, sticky="nsew", pady=(14, 0))
        self._cl_agents_box = box
        self.log(box, "Elige un agente. Si es la primera vez, usa 'Preparar FCC (auto)' en el Panel.")

    def _cl_agent(self, key):
        label = CL.AGENTS.get(key, (key, ""))[0]
        self.run_action(self._cl_agents_box,
                        lambda: CL.run_agent(key, cwd=C.get_base_dir()),
                        f"[...] Abriendo {label}...")

    def page_claude_doctor(self, parent):
        outer, body = self.card(parent, title="Diagnostico de Claude / FCC", accent=THEME["yellow"])
        outer.grid(row=0, column=0, sticky="ew")
        tk.Label(body, text="Diagnostico local rapido + fcc-doctor oficial. Sin inventar datos.",
                 bg=THEME["card"], fg=THEME["muted"], font=(ui.FONT, 9), anchor="w").pack(fill="x", pady=(0, 8))
        self.btnrow(body, [
            ("Diagnostico local", self._cl_doc_local, "green"),
            ("fcc-doctor", self._cl_doctor_run, "accent"),
            ("Actualizar uv + deps", self._cl_update, "ghost"),
            ("Instalar Claude Code", self._cl_install_claude, "ghost"),
            ("Abrir .env", self._cl_open_env, "ghost"),
            ("Abrir logs", lambda: C.open_path(CL.log_path()), "ghost"),
        ])

        box = ui.LogBox(parent)
        box.frame.grid(row=1, column=0, sticky="nsew", pady=(14, 0))
        self._cl_doc_box = box
        self.log(box, "Pulsa 'Diagnostico local' para ver proyecto, uv, entorno, servidor y claves.")

    def _cl_doc_local(self):
        self.run_action(self._cl_doc_box, lambda: (True, CL.local_diagnostics()),
                        "[...] Recopilando diagnostico local...")

    # ------------------------------------------------------------ SISTEMA -----
    # ------------------------------------------------- PATH / OPENCODE --------
    def _section_path(self, parent):
        outer, body = self.card(parent, title="PATH de Windows (OpenCode)", accent=THEME["green"])
        outer.grid(row=0, column=0, sticky="ew")
        tk.Label(body, text=(
            "PATH: si OpenCode no se detecta, anade su carpeta al PATH del usuario. "
            "Afecta solo a tu usuario y surte efecto en programas nuevos.\n\n"
            "Crear / Instalar OpenCode (si falta): ejecuta 'npm install -g opencode-ai' en una "
            "consola real y luego coloca la carpeta de npm al PRINCIPIO del PATH para que esta "
            "version tenga prioridad. Si ya esta instalado, solo repara el PATH."),
            bg=THEME["card"], fg=THEME["muted"], font=(ui.FONT, 9), anchor="w",
            justify="left", wraplength=880).pack(fill="x", pady=(0, 8))
        self._path_state = tk.Label(body, text="", bg=THEME["card"], fg=THEME["text"],
                                    font=(ui.MONO, 9), anchor="w", justify="left", wraplength=880)
        self._path_state.pack(fill="x", pady=(0, 10))
        self.btnrow(body, [
            ("Crear / Instalar OpenCode (si falta)", self._path_install_opencode, "green"),
            (f"{ICONS['add']}  Anadir OpenCode al PATH", self._path_add_opencode, "accent"),
            ("Anadir carpeta npm al PATH", self._path_add_npm, "ghost"),
            ("Abrir Variables de entorno", self._path_open_env, "ghost"),
        ])
        self._path_refresh()
        self._refreshers.append(self._path_refresh)

        outer2, body2 = self.card(parent, title="Variables de entorno", accent=THEME["accent2"])
        outer2.grid(row=1, column=0, sticky="ew", pady=(14, 0))
        tk.Label(body2, text="Crea variables de usuario (HKCU) sin abrir el panel de Windows. "
                             "Aplican a los programas que se abran despues.",
                 bg=THEME["card"], fg=THEME["muted"], font=(ui.FONT, 9), anchor="w",
                 justify="left", wraplength=880).pack(fill="x", pady=(0, 8))
        self._env_state = tk.Label(body2, text="", bg=THEME["card"], fg=THEME["text"],
                                   font=(ui.MONO, 9), anchor="w", justify="left", wraplength=880)
        self._env_state.pack(fill="x", pady=(0, 8))
        tk.Label(body2, text=(
            "OPENCODE_EXPERIMENTAL_OUTPUT_TOKEN_MAX = 512000: amplia el maximo de tokens de SALIDA "
            "por respuesta de OpenCode (512.000). Solo afecta a respuestas nuevas y a procesos "
            "iniciados despues de guardarla; no cambia el contexto de entrada.\n"
            "Otras variables utiles: OPENCODE_CONFIG_DIR (carpeta de config), OPENCODE_BIN (binario), "
            "NEXUS_OPENCODE, OPLIRE_PROJECT_PATH, ANTIGRAVITY_PROJECT_PATH, CLAUDE_PROJECT_PATH, "
            "GOOGLE_GENERATIVE_AI_API_KEY / GEMINI_API_KEY, NO_PROXY."),
            bg=THEME["card"], fg=THEME["muted"], font=(ui.FONT, 9), anchor="w",
            justify="left", wraplength=880).pack(fill="x", pady=(0, 8))
        self.btnrow(body2, [
            ("Establecer OPENCODE_EXPERIMENTAL_OUTPUT_TOKEN_MAX = 512000", self._env_set_token_max, "accent"),
            ("Abrir Variables de entorno (sysdm.cpl)", self._env_open_dialog, "ghost"),
            ("Quitar OPENCODE_EXPERIMENTAL_OUTPUT_TOKEN_MAX", self._env_del_token_max, "ghost"),
        ])
        row = tk.Frame(body2, bg=THEME["card"])
        row.pack(fill="x", pady=(10, 0))
        tk.Label(row, text="Nombre", bg=THEME["card"], fg=THEME["muted"],
                 font=(ui.FONT, 9)).pack(side="left")
        self._env_name = tk.Entry(row, width=36, bg=THEME["card2"], fg=THEME["text"],
                                  insertbackground=THEME["text"], relief="flat")
        self._env_name.pack(side="left", padx=(6, 14))
        tk.Label(row, text="Valor", bg=THEME["card"], fg=THEME["muted"],
                 font=(ui.FONT, 9)).pack(side="left")
        self._env_value = tk.Entry(row, width=18, bg=THEME["card2"], fg=THEME["text"],
                                   insertbackground=THEME["text"], relief="flat")
        self._env_value.pack(side="left", padx=(6, 14))
        ui.button(row, "Guardar variable", self._env_save_custom, "accent").pack(side="left")
        self._env_refresh()
        self._refreshers.append(self._env_refresh)

    def page_system(self, parent):
        outer, body = self.card(parent, title="Reconocimiento del equipo", accent=THEME["accent"])
        outer.grid(row=0, column=0, sticky="ew")
        info = C.system_info()
        rows = [
            ("Sistema", info["os"]),
            ("Version SO", info["os_version"][:80]),
            ("Arquitectura", info["arch"]),
            ("Equipo", info["host"]),
            ("Usuario", info["user"]),
            ("Administrador", "SI" if info["admin"] else "no"),
            ("CPU", info["cpu"]),
            ("Nucleos", str(info["cores"])),
            ("RAM total", C.human_size(info["ram_total"])),
            ("RAM libre", C.human_size(info["ram_free"])),
            ("Disco total", C.human_size(info["disk_total"])),
            ("Disco libre", C.human_size(info["disk_free"])),
            ("Python", info["python"]),
        ]
        if info.get("gpu"):
            rows.append(("GPU", info["gpu"]))
        for k, v in rows:
            self._kv(body, k, v)

        outer2, body2 = self.card(parent, title="Red (privada / publica)", accent=THEME["green"])
        outer2.grid(row=1, column=0, sticky="ew", pady=(14, 0))
        self._sys_net = tk.Label(body2, text="Consultando red real (IP, adaptadores, DNS)...",
                                 bg=THEME["card"], fg=THEME["text"], font=(ui.MONO, 9),
                                 anchor="w", justify="left")
        self._sys_net.pack(fill="x")
        self._sys_net_refresh()

        outer3, body3 = self.card(parent, title="Dependencias (que falta y como resolverlo)", accent=THEME["yellow"])
        outer3.grid(row=2, column=0, sticky="ew", pady=(14, 0))
        self._sys_deps = tk.Label(body3, text="Comprobando...", bg=THEME["card"], fg=THEME["text"],
                                  font=(ui.MONO, 9), anchor="w", justify="left")
        self._sys_deps.pack(fill="x")

        outer4, body4 = self.card(parent, title="Entorno", accent=THEME["accent2"])
        outer4.grid(row=3, column=0, sticky="ew", pady=(14, 0))
        self._sys_env = tk.Label(body4, text="", bg=THEME["card"], fg=THEME["text"],
                                 font=(ui.MONO, 9), anchor="w", justify="left")
        self._sys_env.pack(fill="x")
        self._sys_env_refresh()
        self._refreshers.append(self._sys_env_refresh)
        self._sys_deps_refresh()
        self._refreshers.append(self._sys_deps_refresh)

    def _sys_env_refresh(self):
        if not hasattr(self, "_sys_env") or not self._sys_env.winfo_exists():
            return

        def compute():
            lines = [
                f"Base de la app : {C.get_base_dir()}",
                f"Oplire dir     : {OP.oplire_dir()}",
                f"Oplire exe      : {OP.find_oplire_exe() or 'NO ENCONTRADO'}",
                f"Antigravity    : {C.antigravity_dir() or 'no encontrada'}",
                f"Claude FCC     : {CL.project_dir() or 'no encontrado'}",
                f"Config OpenCode: {AG.get_config_dir()}",
                f"OpenCode (bin) : {AG.get_opencode_path() or 'NO ENCONTRADO'}",
                f"uv (Claude)    : {CL.uv_path() or 'NO INSTALADO'}",
                "",
                "Herramientas:",
            ]
            for name in ("node", "npm", "opencode", "claude", "warp-cli", "git", "uv"):
                lines.append(f"  {name:12}: {C.which(name) or C._which_ext(name) or 'no encontrado'}")
            return "\n".join(lines)

        def apply(text):
            if not hasattr(self, "_sys_env") or not self._sys_env.winfo_exists():
                return
            self._sys_env.configure(text=text or "")

        self._schedule_refresh("sys", compute, apply)

    def _sys_net_refresh(self):
        if not hasattr(self, "_sys_net") or not self._sys_net.winfo_exists():
            return

        def compute():
            return C.network_info()

        def apply(net):
            if not hasattr(self, "_sys_net") or not self._sys_net.winfo_exists():
                return
            if not net:
                self._sys_net.configure(text="No se pudo consultar la red.", fg=THEME["muted"])
                return
            lines = [
                f"IP local       : {net.get('local_ip') or '?'}  "
                f"·  {'red privada' if net.get('private') else 'red publica' if net.get('private') is False else 'tipo desconocido'}",
                f"IP publica     : {net.get('public_ip') or ('sin salida a internet' if net.get('internet') is False else 'no disponible')}",
                f"Internet       : {'SI' if net.get('internet') else 'NO' if net.get('internet') is False else '?'}",
                f"Puerta enlace  : {net.get('gateway') or 'no detectada'}",
                f"DNS            : {net.get('dns') or 'automatico'}",
            ]
            adapters = net.get("adapters") or []
            if adapters:
                lines.append("Adaptadores:")
                for ad in adapters[:6]:
                    lines.append(f"  {ad.get('alias') or '?'}: {ad.get('ip')}  "
                                 f"[{ad.get('category') or 'sin categoria'}]  "
                                 f"{(ad.get('description') or '')[:70]}")
            self._sys_net.configure(text="\n".join(lines), fg=THEME["green"])

        self._schedule_refresh("sysnet", compute, apply)

    def _sys_deps_refresh(self):
        if not hasattr(self, "_sys_deps") or not self._sys_deps.winfo_exists():
            return

        def compute():
            return C.dependency_audit()

        def apply(res):
            if not hasattr(self, "_sys_deps") or not self._sys_deps.winfo_exists():
                return
            if not res:
                self._sys_deps.configure(text="Sin datos de dependencias.", fg=THEME["muted"])
                return
            lines = []
            missing_required = 0
            for d in res:
                mark = "OK   " if d["ok"] else ("FALTA" if d["required"] else "opc. ")
                if not d["ok"] and d["required"]:
                    missing_required += 1
                lines.append(f"[{mark}] {d['name']:<18} {d['value']}")
                if not d["ok"] and d.get("hint"):
                    lines.append(f"        -> {d['hint']}")
            lines.append("")
            if missing_required:
                lines.append(f"{missing_required} dependencia(s) OBLIGATORIA(S) faltante(s). "
                             "NEXUS sigue funcionando; instala lo indicado para completar funciones.")
            else:
                lines.append("Todas las dependencias obligatorias estan presentes.")
            self._sys_deps.configure(text="\n".join(lines),
                                     fg=THEME["yellow"] if missing_required else THEME["green"])

        self._schedule_refresh("sysdeps", compute, apply)

    def _path_refresh(self):
        if not hasattr(self, "_path_state") or not self._path_state.winfo_exists():
            return

        def compute():
            oc = AG.get_opencode_path()
            oc_dir = os.path.dirname(oc) if oc else ""
            npm_dir = os.path.join(os.environ.get("APPDATA", ""), "npm")
            lines = [f"OpenCode detectado : {oc or 'NO ENCONTRADO'}"]
            lines.append(f"Carpeta OpenCode   : {oc_dir or '(desconocida)'}"
                         + ("   [en PATH]" if oc_dir and C.path_contains(oc_dir) else "   [fuera del PATH]"))
            lines.append(f"Carpeta npm        : {npm_dir}"
                         + ("   [en PATH]" if C.path_contains(npm_dir) else "   [fuera del PATH]"))
            return "\n".join(lines)

        def apply(text):
            if hasattr(self, "_path_state") and self._path_state.winfo_exists():
                self._path_state.configure(text=text or "")

        self._schedule_refresh("path", compute, apply)

    def _path_add_opencode(self):
        oc = AG.get_opencode_path()
        folder = os.path.dirname(oc) if oc else os.path.join(os.environ.get("APPDATA", ""), "npm")
        ok, msg = C.add_to_user_path(folder, prepend=True)
        messagebox.showinfo("PATH", msg)
        self._refresh_now()

    def _path_add_npm(self):
        folder = os.path.join(os.environ.get("APPDATA", ""), "npm")
        ok, msg = C.add_to_user_path(folder, prepend=True)
        messagebox.showinfo("PATH", msg)
        self._refresh_now()

    def _path_install_opencode(self):
        found = AG.get_opencode_path()
        if found:
            folder = os.path.dirname(found)
            ok, msg = C.add_to_user_path(folder, prepend=True)
            messagebox.showinfo("OpenCode",
                                f"OpenCode ya esta instalado:\n{found}\n\nPATH: {msg}")
            self._refresh_now()
            return
        if not C.tool_available("npm"):
            messagebox.showerror("OpenCode",
                                 "npm no esta instalado.\nInstala Node.js LTS desde la pagina "
                                 "Utilidades > Descargar Node.js y vuelve a intentarlo.")
            return
        self.run_action(self._tool_state if hasattr(self, "_tool_state") else None,
                        lambda: OP.install_component("opencode"),
                        "[...] Abriendo instalador real de OpenCode (npm)...")
        messagebox.showinfo(
            "OpenCode",
            "Se abrio una consola con 'npm install -g opencode-ai'.\n\n"
            "Al terminar:\n1) Pulsa F5 para refrescar.\n2) Pulsa 'Anadir OpenCode al PATH'.\n\n"
            "Si npm no se reconoce, anade primero la carpeta npm al PATH.")
        self.after(3000, self._refresh_now)

    def _path_open_env(self):
        if not C.open_env_vars_dialog():
            messagebox.showinfo(
                "PATH",
                "Abre manualmente:\n\nInicio > sysdm.cpl > Opciones avanzadas > "
                "Variables de entorno")

    def _env_refresh(self):
        if not hasattr(self, "_env_state") or not self._env_state.winfo_exists():
            return

        def compute():
            name = "OPENCODE_EXPERIMENTAL_OUTPUT_TOKEN_MAX"
            val = C.get_user_env(name)
            return f"{name} = {val if val is not None else '(no definida)'}"

        def apply(text):
            if hasattr(self, "_env_state") and self._env_state.winfo_exists():
                self._env_state.configure(text=text or "")

        self._schedule_refresh("env", compute, apply)

    def _env_set_token_max(self):
        ok, msg = C.set_user_env("OPENCODE_EXPERIMENTAL_OUTPUT_TOKEN_MAX", "512000")
        messagebox.showinfo("Variables de entorno", msg)
        self._env_refresh()

    def _env_del_token_max(self):
        ok, msg = C.delete_user_env("OPENCODE_EXPERIMENTAL_OUTPUT_TOKEN_MAX")
        messagebox.showinfo("Variables de entorno", msg)
        self._env_refresh()

    def _env_save_custom(self):
        name = self._env_name.get().strip()
        value = self._env_value.get().strip()
        if not name:
            messagebox.showwarning("Variables de entorno", "Escribe el nombre de la variable.")
            return
        ok, msg = C.set_user_env(name, value)
        messagebox.showinfo("Variables de entorno", msg)
        self._env_refresh()

    def _env_open_dialog(self):
        if not C.open_env_vars_dialog():
            messagebox.showinfo("Variables de entorno",
                                "No se pudo abrir. Usa: Inicio > sysdm.cpl > Opciones avanzadas.")

    # ------------------------------------------------------------- ABOUT ------
    def page_about(self, parent):
        hero = tk.Frame(parent, bg=THEME["card"], highlightbackground=THEME["border"],
                        highlightthickness=1)
        hero.grid(row=0, column=0, sticky="ew")
        head = tk.Frame(hero, bg=THEME["card"])
        head.pack(fill="x", padx=24, pady=(20, 6))
        tk.Label(head, text="NEXUS SUITE", bg=THEME["card"], fg=THEME["text"],
                 font=(ui.FONT, 24, "bold"), anchor="w").pack(side="left")
        tk.Label(head, text=f"  V.{APP_VERSION}  ", bg=THEME["accent"], fg="#06101c",
                 font=(ui.FONT, 10, "bold"), padx=6, pady=3).pack(side="left", padx=(14, 0), pady=(10, 0))
        tk.Label(hero, text=f"NEXUS SUITE V.{APP_VERSION}  ·  Suite unificada con OpenCode (Oplire), "
                            "Antigravity y Claude (Free Claude Code). Portable y responsiva.",
                 bg=THEME["card"], fg=THEME["muted"], font=(ui.FONT, 10), anchor="w",
                 justify="left", wraplength=900).pack(fill="x", padx=24, pady=(0, 18))

        engines = tk.Frame(parent, bg=THEME["bg"])
        engines.grid(row=1, column=0, sticky="ew", pady=(14, 0))
        for col in range(3):
            engines.grid_columnconfigure(col, weight=1, uniform="eng")
        blocks = [
            ("MODULO OPENCODE (motor Oplire)", THEME["accent"], [
                "Control de IP: rotar, reconectar, reset, restaurar, estado WARP",
                "Servidor: Proxy / Dashboard / Daemon en 127.0.0.1:8080",
                "OpenCode Local y Desktop Bypass en la misma seccion",
                "vCache: limpieza protegida + backup/restauracion de sesiones",
                "Mantenimiento: Doctor, Herramientas, PATH y variables",
                "Sesiones y consolas CMD del sistema",
            ]),
            ("MODULO ANTIGRAVITY", THEME["accent2"], [
                "Cuentas Google: agregar, activar/desactivar y borrar",
                "Cuotas REALES en linea (check-quota.mjs) con cache de respaldo",
                "Plugin: activar (carga modelos), reparar Node y API key",
                "Modelos: catalogo cargado en opencode.json",
                "Sin secciones redundantes: todo en Cuentas / Plugin / Modelos",
            ]),
            ("MODULO CLAUDE (Free Claude Code)", THEME["green"], [
                "Servidor FCC en 127.0.0.1:8082 y Admin UI integrada",
                "10 agentes: Claude, Codex, OpenCode, Cline, Aider, Hermes...",
                "uv + dependencias + fcc-doctor con un clic",
                "Configuracion de MODEL y API keys en ~/.fcc/.env",
                "Integrado como modulo de primera clase de NEXUS",
            ]),
        ]
        for col, (title, color, items) in enumerate(blocks):
            outer, body = self.card(engines, title=title, accent=color)
            outer.grid(row=0, column=col, sticky="nsew", padx=(0 if col == 0 else 10, 0))
            for it in items:
                tk.Label(body, text="•  " + it, bg=THEME["card"], fg=THEME["muted"],
                         font=(ui.FONT, 9), anchor="w", justify="left",
                         wraplength=300).pack(fill="x", pady=1)

        feat = tk.Frame(parent, bg=THEME["card"], highlightbackground=THEME["border"],
                        highlightthickness=1)
        feat.grid(row=2, column=0, sticky="ew", pady=(14, 0))
        tk.Label(feat, text="PORTABLE Y RESPONSIVO", bg=THEME["card"], fg=THEME["green"],
                 font=(ui.FONT, 10, "bold"), anchor="w").pack(fill="x", padx=20, pady=(14, 4))
        tk.Label(feat, text="Detecta el equipo, los motores y las herramientas automaticamente. "
                            "Sin rutas fijas: funciona en cualquier PC donde copies la carpeta. "
                            "La interfaz se adapta a cualquier tamano de ventana y refresca estados "
                            "en tiempo real.",
                 bg=THEME["card"], fg=THEME["muted"], font=(ui.FONT, 9), anchor="w",
                 justify="left", wraplength=880).pack(fill="x", padx=20, pady=(0, 14))

        outer, body = self.card(parent, title="Desarrollador", accent=THEME["accent2"])
        outer.grid(row=3, column=0, sticky="ew", pady=(14, 0))
        self._kv(body, "Desarrollador", "PolloCraft")
        self._kv(body, "GitHub", "https://github.com/PolloCraft")
        self._kv(body, "Repositorio", "https://github.com/PolloCraft/OpenCode-Nexus")
        self._kv(body, "Version", f"NEXUS SUITE V.{APP_VERSION}")
        self.btnrow(body, [
            (f"{ICONS['external']}  Abrir perfil del desarrollador",
             lambda: self._open_url("https://github.com/PolloCraft"), "accent"),
            (f"{ICONS['external']}  Abrir repositorio",
             lambda: self._open_url("https://github.com/PolloCraft/OpenCode-Nexus"), "green"),
        ])


def node_ok():
    return C.tool_available("node") and C.tool_available("npm")


def main():
    app = NexusApp()

    def repair():
        try:
            AG.startup_silent_repair()
        except Exception:
            pass

    app.after(1500, lambda: threading.Thread(target=repair, daemon=True).start())
    app.mainloop()


if __name__ == "__main__":
    main()
