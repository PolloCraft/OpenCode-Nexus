# -*- coding: utf-8 -*-
"""
NEXUS Suite - Aplicacion unificada (v7.2.0)
===========================================
Dos modulos en una sola suite:

  * MODULO OPENCODE  -> motor Oplire: control de IP (WARP), proxy/dashboard,
                        desktop bypass, cache (vCache) en tiempo real, doctor.
  * MODULO ANTIGRAVITY -> general, cuentas, plugin, modelos, mantenimiento.

Diseno responsivo (se adapta a cualquier tamano de ventana), iconos 100%
compatibles (sin emoji), reconocimiento del equipo y refresco en tiempo real.
Portable y sin errores. Todo el codigo, sin omisiones.
"""

import os
import sys
import time
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
from modules import ui

THEME = ui.THEME
APP_TITLE = C.APP_NAME
APP_VERSION = "7.2.0"
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

        self._build_statusbar()

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

    def _build_statusbar(self):
        bar = tk.Frame(self, bg=THEME["sidebar"], height=30)
        bar.grid(row=1, column=0, columnspan=2, sticky="ew")
        bar.grid_propagate(False)
        self.status_label = tk.Label(bar, text="", bg=THEME["sidebar"], fg=THEME["muted"],
                                     font=(ui.MONO, 9), anchor="w")
        self.status_label.pack(side="left", padx=16)
        self.clock = tk.Label(bar, text="", bg=THEME["sidebar"], fg=THEME["dim"],
                              font=(ui.MONO, 9), anchor="e")
        self.clock.pack(side="right", padx=16)
        self.refresh_statusbar()

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

        def section(text, color=None):
            f = tk.Frame(self.sidebar, bg=THEME["sidebar"])
            f.pack(fill="x", padx=22, pady=(12, 4))
            tk.Label(f, text=text, bg=THEME["sidebar"], fg=color or THEME["dim"],
                     font=(ui.FONT, 8, "bold"), anchor="w").pack(side="left")

        def nav(key, icon, label):
            self._nav_items[key] = self._nav_button(key, icon, label)

        section("OPENCODE  (motor Oplire)")
        nav("home", ICONS["home"], "Inicio")
        nav("ip", ICONS["ip"], "Control de IP")
        nav("server", ICONS["server"], "Proxy / Servidor")
        nav("local", ICONS["local"], "OpenCode Local")
        nav("desktop", ICONS["desktop"], "Desktop Bypass")
        nav("cache", ICONS["cache"], "Caché (vCache)")
        nav("doctor", ICONS["doctor"], "Doctor")
        nav("tools", ICONS["tools"], "Herramientas")
        nav("path", ICONS["path"], "PATH / OpenCode")

        section("ANTIGRAVITY", THEME["accent2"])
        nav("ag_general", ICONS["ag_general"], "General")
        nav("ag_accounts", ICONS["ag_accounts"], "Cuentas")
        nav("ag_plugin", ICONS["ag_plugin"], "Plugin")
        nav("ag_models", ICONS["ag_models"], "Modelos")
        nav("ag_maint", ICONS["ag_maint"], "Mantenimiento")

        section("SISTEMA")
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
        "home":        ("Inicio", "Resumen del sistema NEXUS"),
        "ip":          ("Control de IP  ·  WARP", "Rotacion, reset y restauracion de IP en tiempo real"),
        "server":      ("Proxy / Servidor", "Dashboard y proxy local en 127.0.0.1:8080"),
        "local":       ("OpenCode Local", "Servidor de OpenCode en 127.0.0.1:3000 (upstream del proxy)"),
        "desktop":     ("Desktop Bypass", "Activa o restaura el enrutado de OpenCode Desktop"),
        "cache":       ("Caché de OpenCode  ·  vCache", "Deteccion en tiempo real, limpieza y borrado de datos"),
        "doctor":      ("Doctor", "Diagnostico del motor y dependencias"),
        "tools":       ("Herramientas", "Utilidades, componentes e instalacion"),
        "path":        ("PATH / OpenCode", "Instalacion de OpenCode, PATH y variables de entorno"),
        "ag_general":  ("Antigravity  ·  General", "Estado del plugin, diagnostico y menu en tiempo real"),
        "ag_accounts": ("Antigravity  ·  Cuentas", "Cuentas Google: agregar, activar, borrar"),
        "ag_plugin":   ("Antigravity  ·  Plugin", "Activar / desactivar el plugin"),
        "ag_models":   ("Antigravity  ·  Modelos", "Modelos de la configuracion de OpenCode"),
        "ag_maint":    ("Antigravity  ·  Mantenimiento", "Reparacion, auto-update y API key"),
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
            self.refresh_statusbar()

        self.run_bg(func, done)

    def need_engine(self):
        if OP.has_engine():
            return True
        messagebox.showerror(
            "Oplire",
            "No se encontro oplire.exe.\n\n"
            f"Ubicacion esperada:\n{os.path.join(OP.oplire_dir(), 'target', 'release', 'oplire.exe')}\n\n"
            "Compila el motor (build.ps1 -Release) o instala el binario.")
        return False

    # ------------------------------------------------------ live / status ----
    def _tick(self):
        self.clock.configure(text=time.strftime("%H:%M:%S"))
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
                    "plugin": AG.test_plugin_configured()}

        def done(res, err):
            if err or not isinstance(res, dict):
                return
            self._set_pill("engine", "OPLIRE", res["engine"])
            self._set_pill("warp", "WARP", res["warp"])
            self._set_pill("opencode", "OPENCODE", res["opencode"])
            self._set_pill("plugin", "PLUGIN", res["plugin"])
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
        self.refresh_statusbar()
        self._update_pills_async()
        for r in list(self._refreshers):
            try:
                r()
            except Exception:
                pass

    def refresh_statusbar(self):
        exe = OP.has_engine()
        node = C.tool_available("node")
        npm = C.tool_available("npm")
        warp = C.tool_available("warp-cli")
        opc = AG.get_opencode_path() is not None
        dot = lambda b: "●" if b else "○"
        parts = [f"{dot(exe)} oplire", f"{dot(node)} node", f"{dot(npm)} npm",
                 f"{dot(warp)} warp", f"{dot(opc)} opencode", f"v{APP_VERSION}"]
        if hasattr(self, "status_label"):
            self.status_label.configure(text="    ".join(parts) + "        F5 actualiza")

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
            if w < 900:
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
            ("node", "Node / npm", THEME["accent"]),
            ("ag", "Antigravity", THEME["accent2"]),
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
            (f"{ICONS['play']}  Iniciar Dashboard", self._qa_dashboard, "green"),
            (f"{ICONS['ip']}  Rotar IP (WARP)", self._qa_rotate, "accent"),
            (f"{ICONS['ag_general']}  Panel Antigravity", lambda: self.show_page("ag_general"), "ghost"),
            (f"{ICONS['doctor']}  Doctor", lambda: self.show_page("doctor"), "ghost"),
        ])

        outer, body = self.card(parent, title="Ubicaciones", accent=THEME["muted"])
        outer.grid(row=2, column=0, sticky="ew", pady=(14, 0))
        self._kv(body, "Base", C.get_base_dir())
        self._kv(body, "Oplire", OP.oplire_dir() + ("" if OP.has_engine() else "   (sin binario)"))
        self._kv(body, "Antigravity", C.antigravity_dir() or "no encontrada")
        self._kv(body, "Config OpenCode", AG.get_config_dir())

        outer, body = self.card(parent, title="Equipo", accent=THEME["accent"])
        outer.grid(row=3, column=0, sticky="ew", pady=(14, 0))
        self._kv(body, "Sistema", info["os"])
        self._kv(body, "Host", f"{info['host']}  ({info['user']})")
        self._kv(body, "CPU", f"{info['cpu']}  ·  {info['cores']} nucleos")
        self._kv(body, "RAM", f"{C.human_size(info['ram_free'])} libres de {C.human_size(info['ram_total'])}")
        self._kv(body, "Disco", f"{C.human_size(info['disk_free'])} libres de {C.human_size(info['disk_total'])}")

    def _home_refresh(self):
        if not getattr(self, "_home_vals", None):
            return

        def compute():
            return {"engine": OP.has_engine(),
                    "warp": C.tool_available("warp-cli"),
                    "node": node_ok(),
                    "ag": AG.test_plugin_configured()}

        def apply(res):
            if not res:
                return
            self._set_home("engine", "COMPILADO" if res["engine"] else "SIN COMPILAR",
                           THEME["green"] if res["engine"] else THEME["yellow"],
                           "oplire.exe listo" if res["engine"] else "Motor no disponible")
            self._set_home("warp", "GESTIONADO" if res["warp"] else "NO INSTALADO",
                           THEME["green"] if res["warp"] else THEME["muted"],
                           "Rotacion de IP disponible" if res["warp"] else "Instala Cloudflare WARP")
            self._set_home("node", "LISTO" if res["node"] else "FALTA",
                           THEME["green"] if res["node"] else THEME["red"],
                           "Requerido por Antigravity" if res["node"] else "Instala Node.js")
            self._set_home("ag", "ACTIVO" if res["ag"] else "DESACTIVADO",
                           THEME["green"] if res["ag"] else THEME["yellow"],
                           "Plugin de cuentas Google" if res["ag"] else "Activalo en la pestana Antigravity")

        self._schedule_refresh("home", compute, apply)

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

    def _qa_dashboard(self):
        if not self.need_engine():
            return
        if OP.dashboard_running():
            OP.open_dashboard_browser()
            return
        OP.start_dashboard()

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
        self.btnrow(body2, [
            ("Sesiones: estado", self._srv_sessions_status, "ghost"),
            ("Sesiones: listar", self._srv_sessions_list, "ghost"),
            ("Reparar sesiones", self._srv_fix_sessions, "accent"),
        ])

        outer3, body3 = self.card(parent, title="Avanzado (Oplire)", accent=THEME["accent2"])
        outer3.grid(row=2, column=0, sticky="ew", pady=(14, 0))
        tk.Label(body3, text="Conecta herramientas al proxy y ejecuta utilidades del motor.",
                 bg=THEME["card"], fg=THEME["muted"], font=(ui.FONT, 9), anchor="w").pack(fill="x", pady=(0, 10))
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
        self.run_action(self._srv_box,
                        lambda: (OP.dashboard_running(), f"Dashboard {'ACTIVO' if OP.dashboard_running() else 'no disponible'}"),
                        "[...] Verificando dashboard...")

    def _srv_api(self):
        self.run_action(self._srv_box, OP.api_status, "[...] Consultando API /api/status...")

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
    def page_local(self, parent):
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
    def page_desktop(self, parent):
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
            txt = (f"Config encontrada: {'si' if res.get('config_found') else 'no'}\n"
                   f"Bypass activo: {'SI' if proxied else 'no'}\n"
                   f"Ruta: {res.get('config_path') or '(no detectada)'}\n"
                   f"API base: {res.get('api_base_url') or '-'}\n"
                   f"Respaldo: {'si' if res.get('backup_exists') else 'no'}")
            if res.get("source") == "cli" and res.get("raw"):
                txt += f"\n\n{res['raw']}"
            self._desk_status.configure(text=txt, fg=THEME["green"] if proxied else THEME["text"])

        self.run_bg(work, done)

    def _desk_setup(self):
        def func():
            return OP.api_setup_desktop() if OP.dashboard_running() else OP.setup_desktop()
        self.run_action(self._desk_box, func, "[...] Activando bypass de Desktop...")

    def _desk_restore(self):
        def func():
            return OP.api_restore_desktop() if OP.dashboard_running() else OP.restore_desktop()
        self.run_action(self._desk_box, func, "[...] Restaurando configuracion original...")

    def _desk_status_btn(self):
        self.run_action(self._desk_box, OP.desktop_status, "[...] Consultando estado...")

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

        box = ui.LogBox(parent, height=7)
        box.frame.grid(row=2, column=0, sticky="nsew", pady=(14, 0))
        self._cache_box = box
        self._cache_refresh()
        self._refreshers.append(self._cache_refresh)

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
        try:
            os.startfile(target)
        except Exception:
            messagebox.showinfo("Carpeta", target)

    # ------------------------------------------------------------- DOCTOR -----
    def page_doctor(self, parent):
        outer, body = self.card(parent, title="Diagnostico del motor", accent=THEME["yellow"])
        outer.grid(row=0, column=0, sticky="ew")
        self.btnrow(body, [
            ("Oplire doctor", self._doc_oplire, "accent"),
            ("Modelos", self._doc_models, "ghost"),
            ("Version", self._doc_version, "ghost"),
            ("Todo (local)", self._doc_local, "green"),
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
                out[key] = text.strip().splitlines()[0] if text.strip() else ""
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
            self.run_action(self._doc_box, OP.models, "[...] Consultando modelos...")

    def _doc_version(self):
        if self.need_engine():
            self.run_action(self._doc_box, OP.version, "[...] Consultando version...")

    def _doc_local(self):
        def func():
            lines = [f"Base: {C.get_base_dir()}",
                     f"Oplire dir: {OP.oplire_dir()}",
                     f"Oplire exe: {OP.find_oplire_exe() or 'NO ENCONTRADO'}",
                     f"Antigravity: {C.antigravity_dir() or 'no encontrada'}",
                     f"Config OpenCode: {AG.get_config_dir()}",
                     f"Admin: {C.is_admin()}"]
            for name in ("node", "npm", "opencode", "claude", "warp-cli", "git"):
                lines.append(f"{name}: {C.which(name) or 'no encontrado'}")
            return True, "\n".join(lines)
        self.run_action(self._doc_box, func, "[...] Recopilando informacion local...")

    # ----------------------------------------------------------- TOOLS --------
    def page_tools(self, parent):
        outer, body = self.card(parent, title="Utilidades", accent=THEME["accent2"])
        outer.grid(row=0, column=0, sticky="ew")
        self.btnrow(body, [
            ("Abrir Everything", self._tool_everything, "ghost"),
            ("Descargar Everything", lambda: self._open_url(EVERYTHING_URL), "ghost"),
            ("Descargar Cloudflare One Client", lambda: self._open_url(CLOUDFLARE_CLIENT_URL), "ghost"),
            ("Estado WARP", self._tool_warp, "ghost"),
            ("Abrir carpeta OpenCode", lambda: self._open_folder(AG.get_config_dir()), "ghost"),
        ])

        outer2, body2 = self.card(parent, title="Instalar componentes", accent=THEME["green"])
        outer2.grid(row=1, column=0, sticky="ew", pady=(14, 0))
        self.btnrow(body2, [
            ("Instalar WARP", lambda: self._tool_install("warp"), "accent"),
            ("Instalar OpenCode", lambda: self._tool_install("opencode"), "accent"),
            ("Instalar Claude Code", lambda: self._tool_install("claude-code"), "accent"),
            ("Instalar TODO", lambda: self._tool_install("all"), "green"),
        ])

        outer3, body3 = self.card(parent, title="Consola del sistema (CMD)", accent=THEME["accent"])
        outer3.grid(row=2, column=0, sticky="ew", pady=(14, 0))
        tk.Label(body3, text="Abre una consola CMD nueva, visible e interactiva en la carpeta indicada.",
                 bg=THEME["card"], fg=THEME["muted"], font=(ui.FONT, 9), anchor="w").pack(fill="x", pady=(0, 10))
        self.btnrow(body3, [
            (f"{ICONS['server']}  CMD en NEXUS", lambda: self._tool_cmd(C.get_base_dir()), "accent"),
            (f"{ICONS['server']}  CMD en Oplire", lambda: self._tool_cmd(OP.oplire_dir()), "ghost"),
            (f"{ICONS['server']}  CMD en OpenCode", lambda: self._tool_cmd(AG.get_config_dir()), "ghost"),
        ])

        box = ui.LogBox(parent)
        box.frame.grid(row=3, column=0, sticky="nsew", pady=(14, 0))
        self._tools_box = box
        self.log(box, "Utilidades y componentes de Oplire. Las descargas requieren internet.")

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
        if self.need_engine():
            self.run_action(self._tools_box, lambda: OP.install(target),
                            f"[...] Instalando {target} (puede tardar)...")

    # ====================================================== ANTIGRAVITY ========
    # ----------------------------------------------------------- GENERAL ------
    def page_ag_general(self, parent):
        outer, body = self.card(parent, title="Estado del plugin", accent=THEME["accent2"])
        outer.grid(row=0, column=0, sticky="ew")
        self._ag_state = tk.Label(body, text="...", bg=THEME["card"], fg=THEME["text"],
                                  font=(ui.FONT, 13, "bold"), anchor="w")
        self._ag_state.pack(fill="x")

        info = tk.Frame(body, bg=THEME["card"])
        info.pack(fill="x", pady=(6, 10))
        self._ag_live = {}
        for key, label in [("accounts", "Cuentas"), ("cache", "Cache plugin"),
                           ("opencode", "OpenCode"), ("cfg", "Config")]:
            line = tk.Frame(info, bg=THEME["card"])
            line.pack(fill="x", pady=1)
            tk.Label(line, text=label, bg=THEME["card"], fg=THEME["muted"], font=(ui.FONT, 9),
                     width=14, anchor="w").pack(side="left")
            lbl = tk.Label(line, text="...", bg=THEME["card"], fg=THEME["text"],
                           font=(ui.MONO, 9), anchor="w", justify="left")
            lbl.pack(side="left")
            self._ag_live[key] = lbl

        self.btnrow(body, [
            (f"{ICONS['refresh']}  Refrescar", self._ag_refresh, "ghost"),
            ("Diagnostico", self._ag_diag, "accent"),
            (f"{ICONS['star']}  Menu del plugin (OAuth)", self._ag_login, "green"),
        ])

        box = ui.LogBox(parent)
        box.frame.grid(row=1, column=0, sticky="nsew", pady=(14, 0))
        self._ag_gen_box = box
        self._ag_refresh()
        self._refreshers.append(self._ag_refresh)

    def _ag_refresh(self):
        if not hasattr(self, "_ag_state") or not self._ag_state.winfo_exists():
            return
        try:
            d = AG.diagnostics()
            configured = d["plugin_configured"]
            self._ag_state.configure(
                text="PLUGIN ACTIVO" if configured else "PLUGIN DESACTIVADO",
                fg=THEME["green"] if configured else THEME["yellow"])
            self._ag_live["accounts"].configure(
                text=f"{d['accounts_count']} cuenta(s)  ·  {d['accounts_file']}")
            self._ag_live["cache"].configure(
                text=("descargado" if d["plugin_cached"] else "no descargado") + f"  ·  {d['cache_dirs']} carpeta(s)")
            self._ag_live["opencode"].configure(
                text=(d["opencode_path"] or "no encontrado") + ("  [ABIERTO]" if d["opencode_running"] else "  [cerrado]"),
                fg=THEME["green"] if d["opencode_path"] else THEME["red"])
            self._ag_live["cfg"].configure(text=d["config_dir"])
        except Exception as e:
            self._ag_state.configure(text=f"Error: {e}", fg=THEME["red"])

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
        self.run_action(self._ag_gen_box, func, "[...] Ejecutando diagnostico...")

    def _ag_login(self):
        def func():
            if not AG.test_plugin_configured():
                AG.enable_plugin()
            return AG.open_plugin_login_console()
        if self._active_page == "ag_accounts":
            box = getattr(self, "_ag_acc_box", None)
        else:
            box = getattr(self, "_ag_gen_box", None)
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
            (f"{ICONS['warn']}  Ver cuotas", lambda: self._ag_plugin_action("check"), "accent"),
            (f"{ICONS['ok']}  Verificar cuenta", lambda: self._ag_plugin_action("verify"), "accent"),
            (f"{ICONS['ok']}  Verificar todas", lambda: self._ag_plugin_action("verify-all"), "accent"),
            (f"{ICONS['tools']}  Configurar modelos", self._ag_acc_configure_models, "ghost"),
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
        self._ag_plugin_detail = tk.Label(body, text="", bg=THEME["card"], fg=THEME["muted"],
                                          font=(ui.MONO, 9), anchor="w", justify="left")
        self._ag_plugin_detail.pack(fill="x", pady=(0, 10))
        self.btnrow(body, [
            (f"{ICONS['ok']}  Activar plugin", self._ag_plugin_enable, "green"),
            (f"{ICONS['x']}  Desactivar plugin", self._ag_plugin_disable, "danger"),
            (f"{ICONS['tools']}  Configurar modelos", self._ag_plugin_models, "ghost"),
        ])

        box = ui.LogBox(parent)
        box.frame.grid(row=1, column=0, sticky="nsew", pady=(14, 0))
        self._ag_plugin_box = box
        self._ag_plugin_refresh()
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
        tk.Label(body, text="Se anaden al provider 'google' de opencode.json. Haz clic para marcarlos.",
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
            (f"{ICONS['tools']}  Configurar modelos en opencode.json", self._ag_configure_models, "accent"),
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

    def _ag_configure_models(self):
        self.run_action(self._ag_models_box, AG.configure_models, "[...] Configurando modelos...")
        self.after(700, self._ag_models_refresh)

    def _ag_remove_models(self):
        if messagebox.askyesno("Modelos", "Quitar los modelos gestionados de la configuracion?"):
            self.run_action(self._ag_models_box, AG.remove_models, "[...] Quitando modelos...")
            self.after(700, self._ag_models_refresh)

    # ------------------------------------------------------ MANTENIMIENTO -----
    def page_ag_maint(self, parent):
        outer, body = self.card(parent, title="Reparacion (compatibilidad Node)", accent=THEME["yellow"])
        outer.grid(row=0, column=0, sticky="ew")
        tk.Label(body, text="El plugin viene listo para Bun; este parche local lo hace cargar tambien en la "
                            "app de escritorio (Node/Electron). No usa red.",
                 bg=THEME["card"], fg=THEME["muted"], font=(ui.FONT, 9), anchor="w",
                 justify="left", wraplength=860).pack(fill="x", pady=(0, 10))
        self.btnrow(body, [
            (f"{ICONS['tools']}  Reparar plugin", self._ag_repair, "accent"),
            (f"{ICONS['refresh']}  Auto-update OFF", self._ag_autoupdate, "ghost"),
        ])

        outer2, body2 = self.card(parent, title="API Key de Google (camino sin plugin)", accent=THEME["accent"])
        outer2.grid(row=1, column=0, sticky="ew", pady=(14, 0))
        tk.Label(body2, text="Con el plugin desactivado, los modelos gemini-* usan tu API key. "
                             "Los modelos antigravity-* requieren OAuth.",
                 bg=THEME["card"], fg=THEME["muted"], font=(ui.FONT, 9), anchor="w",
                 justify="left", wraplength=860).pack(fill="x", pady=(0, 8))
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

        box = ui.LogBox(parent, height=6)
        box.frame.grid(row=2, column=0, sticky="nsew", pady=(14, 0))
        self._ag_maint_box = box
        self._ag_key_refresh()

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

    # ------------------------------------------------------------ SISTEMA -----
    # ------------------------------------------------- PATH / OPENCODE --------
    def page_path(self, parent):
        outer, body = self.card(parent, title="PATH de Windows (OpenCode)", accent=THEME["green"])
        outer.grid(row=0, column=0, sticky="ew")
        tk.Label(body, text="Si OpenCode no se detecta, anade su carpeta al PATH del usuario. "
                            "Afecta solo a tu usuario y surte efecto en programas nuevos.",
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

        outer2, body2 = self.card(parent, title="Entorno", accent=THEME["accent2"])
        outer2.grid(row=1, column=0, sticky="ew", pady=(14, 0))
        self._sys_env = tk.Label(body2, text="", bg=THEME["card"], fg=THEME["text"],
                                 font=(ui.MONO, 9), anchor="w", justify="left")
        self._sys_env.pack(fill="x")
        self._sys_env_refresh()
        self._refreshers.append(self._sys_env_refresh)

    def _sys_env_refresh(self):
        if not hasattr(self, "_sys_env") or not self._sys_env.winfo_exists():
            return

        def compute():
            lines = [
                f"Base de la app : {C.get_base_dir()}",
                f"Oplire dir     : {OP.oplire_dir()}",
                f"Oplire exe      : {OP.find_oplire_exe() or 'NO ENCONTRADO'}",
                f"Antigravity    : {C.antigravity_dir() or 'no encontrada'}",
                f"Config OpenCode: {AG.get_config_dir()}",
                f"OpenCode (bin) : {AG.get_opencode_path() or 'NO ENCONTRADO'}",
                "",
                "Herramientas:",
            ]
            for name in ("node", "npm", "opencode", "claude", "warp-cli", "git", "everything"):
                lines.append(f"  {name:12}: {C.which(name) or 'no encontrado'}")
            return "\n".join(lines)

        def apply(text):
            if not hasattr(self, "_sys_env") or not self._sys_env.winfo_exists():
                return
            self._sys_env.configure(text=text or "")

        self._schedule_refresh("sys", compute, apply)

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
        ok, msg = C.add_to_user_path(folder)
        messagebox.showinfo("PATH", msg)
        self._refresh_now()

    def _path_add_npm(self):
        folder = os.path.join(os.environ.get("APPDATA", ""), "npm")
        ok, msg = C.add_to_user_path(folder)
        messagebox.showinfo("PATH", msg)
        self._refresh_now()

    def _path_install_opencode(self):
        if AG.get_opencode_path():
            messagebox.showinfo("OpenCode", f"OpenCode ya esta instalado:\n{AG.get_opencode_path()}")
            return

        def work():
            return OP.install("opencode")

        def done(res, err):
            if err:
                messagebox.showerror("OpenCode", f"Error al instalar:\n{err}")
                return
            _ok, out = self._wrap(res)
            found = AG.get_opencode_path()
            if found:
                C.add_to_user_path(os.path.dirname(found))
                messagebox.showinfo("OpenCode", f"Instalado y anadido al PATH:\n{found}")
            else:
                messagebox.showwarning(
                    "OpenCode",
                    "No se pudo detectar OpenCode tras instalar.\n"
                    "Asegurate de tener Node.js/npm instalado.\n\n" + (out or "")[:600])
            self._refresh_now()

        self.run_bg(work, done)

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
        tk.Label(head, text=f"  v{APP_VERSION}  ", bg=THEME["accent"], fg="#06101c",
                 font=(ui.FONT, 10, "bold"), padx=6, pady=3).pack(side="left", padx=(14, 0), pady=(10, 0))
        tk.Label(hero, text="Suite unificada con dos motores: OpenCode (Oplire) y Antigravity. "
                            "Portable y responsiva.",
                 bg=THEME["card"], fg=THEME["muted"], font=(ui.FONT, 10), anchor="w",
                 justify="left", wraplength=900).pack(fill="x", padx=24, pady=(0, 18))

        engines = tk.Frame(parent, bg=THEME["bg"])
        engines.grid(row=1, column=0, sticky="ew", pady=(14, 0))
        engines.grid_columnconfigure(0, weight=1, uniform="eng")
        engines.grid_columnconfigure(1, weight=1, uniform="eng")
        blocks = [
            ("MODULO OPENCODE (motor Oplire)", THEME["accent"], [
                "Control de IP: rotar, reconectar, reset, restaurar, estado WARP",
                "Proxy / Dashboard / Daemon en 127.0.0.1:8080",
                "OpenCode Local: servidor 'opencode serve' (upstream del proxy)",
                "Desktop bypass: activar / restaurar / estado",
                "Cache en tiempo real: limpiar (protege Antigravity)",
                "Sesiones, doctor, modelos e instalacion de componentes",
            ]),
            ("MODULO ANTIGRAVITY", THEME["accent2"], [
                "General: estado, diagnostico en tiempo real y plugin (OAuth)",
                "Cuentas: refrescar, activar/desactivar, agregar y borrar",
                "Plugin: activar / desactivar y configurar modelos",
                "Modelos: provider google (configurar / quitar)",
                "Mantenimiento: reparar Node, auto-update, API key Google",
            ]),
        ]
        for col, (title, color, items) in enumerate(blocks):
            outer, body = self.card(engines, title=title, accent=color)
            outer.grid(row=0, column=col, sticky="nsew", padx=(0 if col == 0 else 10, 0))
            for it in items:
                tk.Label(body, text="•  " + it, bg=THEME["card"], fg=THEME["muted"],
                         font=(ui.FONT, 9), anchor="w", justify="left",
                         wraplength=410).pack(fill="x", pady=1)

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

        outer, body = self.card(parent, title="Accesos", accent=THEME["muted"])
        outer.grid(row=3, column=0, sticky="ew", pady=(14, 0))
        self.btnrow(body, [
            ("Abrir config Antigravity", lambda: self._open_folder(AG.get_config_dir()), "ghost"),
            ("Abrir carpeta de la app", lambda: self._open_folder(C.get_base_dir()), "ghost"),
            ("Ver equipo", lambda: self.show_page("system"), "accent"),
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
