"""Themed message dialogs — a drop-in replacement for ``tkinter.messagebox``.

The standard ``messagebox`` popups are drawn by the OS and ignore our theme, so
they show up as bright native windows against the beige/navy app. These build
the same dialogs as modal ``tk.Toplevel`` windows styled from ``ui/theme.py``,
exposing the same function names and return values (``showinfo`` → ``"ok"``,
``askyesno`` → ``bool``, ``askyesnocancel`` → ``True``/``False``/``None``) so
callers can simply ``from ui import dialogs as messagebox``.
"""
import tkinter as tk
from tkinter import ttk

from ui import theme

# Big bracketed glyph per dialog kind, in the retro terminal spirit. The glyph
# itself distinguishes the kind, so the palette stays monochrome.
_ICONS = {
    "info": ("[i]", theme.FG),
    "question": ("[?]", theme.FG),
    "warning": ("[!]", theme.FG),
    "error": ("[x]", theme.FG),
}


def _show(kind, title, message, parent, buttons, default):
    """Build a modal themed dialog and return the chosen button's value.

    `buttons` is a list of (label, value); `default` is returned if the window
    is closed via Escape or the window manager.
    """
    parent = parent or tk._default_root
    win = tk.Toplevel(parent)
    win.title(title or "")
    win.configure(background=theme.BG)
    win.transient(parent)
    win.resizable(False, False)

    result = {"value": default}

    def done(value):
        result["value"] = value
        win.destroy()

    body = ttk.Frame(win, padding=18)
    body.pack(fill="both", expand=True)

    glyph, color = _ICONS.get(kind, ("", theme.FG))
    if glyph:
        tk.Label(body, text=glyph, font=(theme.FONT_FAMILY, 22, "bold"),
                 background=theme.BG, foreground=color).grid(
            row=0, column=0, sticky="n", padx=(0, 14))
    ttk.Label(body, text=message, wraplength=380, justify="left").grid(
        row=0, column=1, sticky="w")

    btn_bar = ttk.Frame(win, padding=(18, 0, 18, 18))
    btn_bar.pack(fill="x")
    inner = ttk.Frame(btn_bar)
    inner.pack(side="right")
    first = None
    for label, value in buttons:
        btn = ttk.Button(inner, text=label, command=lambda v=value: done(v))
        btn.pack(side="left", padx=(8, 0))
        if first is None:
            first = btn

    # Enter activates the focused button (global TButton binding); Escape and the
    # window's close box both resolve to the default value.
    win.bind("<Escape>", lambda e: done(default))
    win.protocol("WM_DELETE_WINDOW", lambda: done(default))

    win.update_idletasks()
    # Center over the parent window.
    px, py = parent.winfo_rootx(), parent.winfo_rooty()
    pw, ph = parent.winfo_width(), parent.winfo_height()
    w, h = win.winfo_reqwidth(), win.winfo_reqheight()
    win.geometry(f"+{px + (pw - w) // 2}+{py + (ph - h) // 3}")

    win.grab_set()
    if first is not None:
        first.focus_set()
    parent.wait_window(win)
    return result["value"]


def showinfo(title=None, message=None, parent=None, **_kw):
    return _show("info", title, message, parent, [("OK", "ok")], "ok")


def showwarning(title=None, message=None, parent=None, **_kw):
    return _show("warning", title, message, parent, [("OK", "ok")], "ok")


def showerror(title=None, message=None, parent=None, **_kw):
    return _show("error", title, message, parent, [("OK", "ok")], "ok")


def askyesno(title=None, message=None, parent=None, **_kw):
    return _show("question", title, message, parent,
                 [("Yes", True), ("No", False)], False)


def askyesnocancel(title=None, message=None, parent=None, **_kw):
    return _show("question", title, message, parent,
                 [("Yes", True), ("No", False), ("Cancel", None)], None)
