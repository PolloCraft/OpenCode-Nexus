# -*- coding: utf-8 -*-
"""
NEXUS Suite - ui
================
Tema visual y widgets reutilizables (Tkinter puro, sin dependencias).

  * Paleta oscura moderna y tipografias auto-detectadas.
  * apply_styles(): registra estilos ttk (botones, notebook, treeview, scroll).
  * Card / LogBox / pills / botones como fabricas reutilizables.
"""

import tkinter as tk
from tkinter import ttk

THEME = {
    "bg":         "#0b0f17",
    "bg2":        "#0e1420",
    "sidebar":    "#080b11",
    "card":       "#131a26",
    "card2":      "#1a2332",
    "border":     "#222d3f",
    "accent":     "#4f9cf9",
    "accent2":    "#a371f7",
    "green":      "#3fb950",
    "yellow":     "#e3b341",
    "red":        "#f85149",
    "text":       "#e8eef7",
    "muted":      "#8b96a8",
    "dim":        "#5a6473",
    "sel":        "#1f6feb",
    "hover":      "#151d2b",
    "nav_active": "#111a29",
    "log_bg":     "#070a10",
    "log_fg":     "#c9d5e5",
}


def _pick_fonts():
    try:
        from tkinter import font as tkfont
        families = set(tkfont.families())
    except Exception:
        families = set()
    ui_choices = ["Segoe UI", "Inter", "Cantarell", "Noto Sans", "Arial", "Helvetica"]
    mono_choices = ["Cascadia Mono", "Consolas", "JetBrains Mono", "DejaVu Sans Mono", "Courier New"]
    ui = next((f for f in ui_choices if f in families), "TkDefaultFont")
    mono = next((f for f in mono_choices if f in families), "Courier")
    return ui, mono


FONT = "Segoe UI"
MONO = "Consolas"
SYMBOL = "Segoe UI Symbol"

# Iconos SEGUROS: solo simbolos BMP sin presentacion emoji (compatibles con
# Segoe UI / Segoe UI Symbol en cualquier Windows). Evitan cuadros (tofu).
ICONS = {
    "home": "\u2302", "ip": "\u21c5", "server": "\u25a3", "desktop": "\u25a4",
    "local": "\u2318",
    "cache": "\u232b", "doctor": "\u271a", "tools": "\u2692",
    "ag_general": "\u2726", "ag_accounts": "\u25c9", "ag_plugin": "\u2756",
    "ag_models": "\u25c8", "ag_maint": "\u2692",
    "system": "\u25a5", "about": "\u24d8", "path": "\u2699",
    "play": "\u25ba", "stop": "\u25a0", "ok": "\u2713", "x": "\u00d7",
    "refresh": "\u21bb", "swap": "\u21c4", "star": "\u2605", "warn": "\u2691",
    "restore": "\u21a9", "add": "\u271a", "external": "\u2197", "trash": "\u232b",
}

BUTTON_STYLES = {
    "accent": "Accent.TButton",
    "green":  "Green.TButton",
    "ghost":  "Ghost.TButton",
    "danger": "Danger.TButton",
    "warn":   "Warn.TButton",
}


def init_fonts():
    global FONT, MONO, SYMBOL
    FONT, MONO = _pick_fonts()
    try:
        from tkinter import font as tkfont
        fams = set(tkfont.families())
    except Exception:
        fams = set()
    SYMBOL = "Segoe UI Symbol" if "Segoe UI Symbol" in fams else FONT
    return FONT, MONO


def apply_styles(root):
    s = ttk.Style(root)
    try:
        s.theme_use("clam")
    except Exception:
        pass
    c = THEME

    s.configure("TFrame", background=c["bg"])
    s.configure("Card.TFrame", background=c["card"])
    s.configure("TLabel", background=c["bg"], foreground=c["text"], font=(FONT, 10))
    s.configure("Card.TLabel", background=c["card"], foreground=c["text"], font=(FONT, 10))
    s.configure("Muted.TLabel", background=c["bg"], foreground=c["muted"], font=(FONT, 9))
    s.configure("CardMuted.TLabel", background=c["card"], foreground=c["muted"], font=(FONT, 9))
    s.configure("CardTitle.TLabel", background=c["card"], foreground=c["muted"], font=(FONT, 9, "bold"))
    s.configure("Big.TLabel", background=c["card"], foreground=c["text"], font=(FONT, 15, "bold"))
    s.configure("TEntry", fieldbackground=c["card2"], background=c["card2"],
                foreground=c["text"], insertcolor=c["text"], borderwidth=0)
    s.configure("TSeparator", background=c["border"])

    # Botones
    s.configure("Accent.TButton", background=c["accent"], foreground="#06121f",
                font=(FONT, 10, "bold"), padding=(16, 9), borderwidth=0, focusthickness=0)
    s.map("Accent.TButton", background=[("active", "#74b3fb"), ("pressed", "#3f86da"), ("disabled", "#2c3d52")],
          foreground=[("disabled", c["dim"])])

    s.configure("Green.TButton", background="#238636", foreground="#ffffff",
                font=(FONT, 10, "bold"), padding=(16, 9), borderwidth=0, focusthickness=0)
    s.map("Green.TButton", background=[("active", "#2ea043"), ("pressed", "#1c6f2c"), ("disabled", "#243a28")],
          foreground=[("disabled", c["dim"])])

    s.configure("Warn.TButton", background="#7a5a12", foreground="#ffe6a3",
                font=(FONT, 10, "bold"), padding=(16, 9), borderwidth=0, focusthickness=0)
    s.map("Warn.TButton", background=[("active", "#96701a"), ("pressed", "#5c430c")],
          foreground=[("disabled", c["dim"])])

    s.configure("Ghost.TButton", background=c["card2"], foreground=c["text"],
                font=(FONT, 10), padding=(16, 9), borderwidth=0, focusthickness=0)
    s.map("Ghost.TButton", background=[("active", c["hover"]), ("pressed", c["border"])],
          foreground=[("disabled", c["dim"])])

    s.configure("Danger.TButton", background="#5a1e1e", foreground="#ffb4b4",
                font=(FONT, 10, "bold"), padding=(16, 9), borderwidth=0, focusthickness=0)
    s.map("Danger.TButton", background=[("active", "#7a2626"), ("pressed", "#421616")],
          foreground=[("disabled", c["dim"])])

    # Scrollbar
    s.configure("Nexus.Vertical.TScrollbar", background=c["card2"], troughcolor=c["bg"],
                bordercolor=c["bg"], arrowcolor=c["muted"], borderwidth=0, relief="flat")
    s.map("Nexus.Vertical.TScrollbar", background=[("active", c["border"])])

    # Treeview
    s.configure("Treeview", background=c["card"], foreground=c["text"],
                fieldbackground=c["card"], borderwidth=0, rowheight=30, font=(FONT, 10))
    s.map("Treeview", background=[("selected", c["sel"])], foreground=[("selected", "#ffffff")])
    s.configure("Treeview.Heading", background=c["card2"], foreground=c["muted"],
                font=(FONT, 9, "bold"), borderwidth=0, relief="flat")
    s.map("Treeview.Heading", background=[("active", c["border"])])

    # Notebook
    s.configure("TNotebook", background=c["bg"], borderwidth=0, tabmargins=(0, 0, 0, 0))
    s.configure("TNotebook.Tab", background=c["bg"], foreground=c["muted"],
                padding=(20, 10), font=(FONT, 10), borderwidth=0)
    s.map("TNotebook.Tab",
          background=[("selected", c["card"])],
          foreground=[("selected", c["accent"])],
          expand=[("selected", (0, 0, 0, 0))])

    # Progressbar
    s.configure("Nexus.Horizontal.TProgressbar", background=c["accent"],
                troughcolor=c["card2"], borderwidth=0, thickness=4)
    return s


# ------------------------------------------------------------ widgets ------

def card(parent, title=None, accent=None, subtitle=None, bg=None):
    """Tarjeta con borde sutil, punto de acento y titulo opcional."""
    c = THEME
    accent = accent or c["accent"]
    outer = tk.Frame(parent, bg=bg or c["card"], highlightbackground=c["border"],
                     highlightthickness=1)
    if title:
        head = tk.Frame(outer, bg=bg or c["card"])
        head.pack(fill="x", padx=18, pady=(14, 0))
        tk.Frame(head, bg=accent, width=8, height=8).pack(side="left", padx=(0, 8))
        tk.Label(head, text=title.upper(), bg=bg or c["card"], fg=c["muted"],
                 font=(FONT, 9, "bold")).pack(side="left")
        if subtitle:
            tk.Label(head, text="·  " + subtitle, bg=bg or c["card"], fg=c["dim"],
                     font=(FONT, 9)).pack(side="left")
    body = tk.Frame(outer, bg=bg or c["card"])
    body.pack(fill="both", expand=True, padx=18, pady=(12, 16))
    return outer, body


def button(parent, text, cmd, kind="accent"):
    return ttk.Button(parent, text=text, command=cmd,
                      style=BUTTON_STYLES.get(kind, "Accent.TButton"))


def pill(parent, text, color, bg=None):
    """Etiqueta tipo insignia."""
    return tk.Label(parent, text="  " + text + "  ", bg=bg or THEME["card"],
                    fg=color, font=(FONT, 8, "bold"), padx=8, pady=4)


class LogBox:
    """Caja de salida con write()/clear() y colores por linea."""

    def __init__(self, parent, height=12, title="SALIDA"):
        c = THEME
        self.frame = tk.Frame(parent, bg=c["card"], highlightbackground=c["border"],
                              highlightthickness=1)
        top = tk.Frame(self.frame, bg=c["card"])
        top.pack(fill="x")
        tk.Frame(top, bg=c["accent"], width=8, height=8).pack(side="left", padx=(18, 8), pady=12)
        tk.Label(top, text=title, bg=c["card"], fg=c["muted"],
                 font=(FONT, 9, "bold")).pack(side="left")
        self.text = tk.Text(self.frame, bg=c["log_bg"], fg=c["log_fg"], font=(MONO, 9),
                            insertbackground=c["text"], relief="flat", wrap="word",
                            state="disabled", padx=12, pady=10, height=height)
        self.text.pack(fill="both", expand=True, padx=12, pady=(0, 12))

    def _alive(self):
        try:
            return bool(self.text.winfo_exists())
        except Exception:
            return False

    def write(self, text, color=None):
        if not self._alive():
            return
        try:
            self.text.configure(state="normal")
            if color:
                tag = "c" + color.replace("#", "")
                self.text.tag_config(tag, foreground=color)
                self.text.insert("end", text + "\n", tag)
            else:
                self.text.insert("end", text + "\n")
            self.text.see("end")
            self.text.configure(state="disabled")
        except Exception:
            pass

    def clear(self):
        if not self._alive():
            return
        try:
            self.text.configure(state="normal")
            self.text.delete("1.0", "end")
            self.text.configure(state="disabled")
        except Exception:
            pass


class FlowFrame(tk.Frame):
    """
    Contenedor responsive: coloca sus hijos en fila y salta de linea
    automaticamente cuando no caben (se adapta a cualquier ancho).
    """

    def __init__(self, parent, gap=10, row_gap=10, bg=None, **kw):
        super().__init__(parent, bg=bg or THEME["bg"], **kw)
        self.gap = gap
        self.row_gap = row_gap
        self._widgets = []
        self._last_w = -1
        self.bind("<Configure>", self._on_configure)

    def add(self, widget):
        self._widgets.append(widget)
        widget.place(x=0, y=0)
        return widget

    def _on_configure(self, event):
        if event.width < 2 or abs(event.width - self._last_w) < 2:
            return
        self._last_w = event.width
        self.reflow(event.width)

    def reflow(self, width):
        x = y = 0
        row_h = 0
        for w in self._widgets:
            if not w.winfo_exists():
                continue
            w.update_idletasks()
            iw = w.winfo_reqwidth()
            ih = w.winfo_reqheight()
            if x > 0 and (x + iw) > width:
                x = 0
                y += row_h + self.row_gap
                row_h = 0
            w.place(x=x, y=y, width=iw, height=ih)
            x += iw + self.gap
            row_h = max(row_h, ih)
        self.configure(height=y + row_h)
