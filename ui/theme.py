"""Central place for the app's colors, fonts and ttk styling.

The look is a *retro green-phosphor CRT* scheme — the classic P1 monochrome
monitor: a black page with glowing green text, green (inverted) buttons and
selection, pale-green emphasis, in a monospace typeface. Per DESIGN.md, colors
live here and nowhere else — screens ask for a named color/font from this module
rather than hardcoding hex values.

Call `apply(root)` once, right after the root window is created.
"""
from tkinter import ttk
import tkinter.font as tkfont

# --- Palette -----------------------------------------------------------------
# Green-on-black phosphor CRT: black page, glowing green text, green accents.
BG = "#001100"          # near-black with a faint green CRT glow
BG_RAISED = "#0A1F0A"   # dim green panels (label frames, headings, menubar)
FG = "#33FF33"          # glowing phosphor green — primary text
FG_BRIGHT = "#CCFFCC"   # pale green — titles / emphasis
FG_MUTED = "#1F9F1F"    # dim green — hints, secondary text
FIELD_BG = "#001A00"    # input wells: near-black green
BORDER = "#2E6E2E"      # soft green outline (so the pale focus ring stands out)
ACCENT = "#33FF33"      # phosphor green — buttons and selection (inverted)
ACCENT_TEXT = "#001100" # dark text drawn on green
SELECT_BG = "#33FF33"   # selected row / active item: green bar
SELECT_FG = "#001100"
SELECT_DIM = "#0E5A0E"  # selected row when its table is NOT focused (dim green)
FOCUS = "#AFFFAF"        # pale green — outlines whatever widget has focus
ROW_HOVER = "#0A2A0A"   # row the mouse is over: faint green wash

# --- Fonts -------------------------------------------------------------------
# "Consolas" ships on Windows; the family falls back gracefully elsewhere.
FONT_FAMILY = "Consolas"
FONT_BASE = (FONT_FAMILY, 11)
FONT_TITLE = (FONT_FAMILY, 20, "bold")
FONT_SUBTITLE = (FONT_FAMILY, 12, "bold")
FONT_HINT = (FONT_FAMILY, 9)


def apply(root):
    """Style `root` and every ttk widget with the retro high-contrast theme."""
    # Default font for classic tk widgets (Menu, Listbox, Text, message boxes).
    default = tkfont.nametofont("TkDefaultFont")
    default.configure(family=FONT_FAMILY, size=11)
    tkfont.nametofont("TkTextFont").configure(family=FONT_FAMILY, size=11)
    tkfont.nametofont("TkMenuFont").configure(family=FONT_FAMILY, size=11)

    root.configure(background=BG)

    # Classic (non-ttk) widget defaults: Menu, Listbox, Toplevel, Text, etc.
    # option_add seeds these without touching each widget individually.
    root.option_add("*background", BG)
    root.option_add("*foreground", FG)
    root.option_add("*Menu.background", BG_RAISED)
    root.option_add("*Menu.foreground", FG)
    root.option_add("*Menu.activeBackground", ACCENT)
    root.option_add("*Menu.activeForeground", ACCENT_TEXT)
    root.option_add("*Menu.relief", "flat")
    root.option_add("*Listbox.background", FIELD_BG)
    root.option_add("*Listbox.foreground", FG)
    root.option_add("*Listbox.selectBackground", SELECT_BG)
    root.option_add("*Listbox.selectForeground", SELECT_FG)
    root.option_add("*Toplevel.background", BG)
    # messagebox / dialog text stays readable on the dark backdrop.
    root.option_add("*Dialog.msg.background", BG)
    root.option_add("*Dialog.msg.foreground", FG)

    style = ttk.Style(root)
    # 'clam' is the most fully colorable built-in theme across platforms.
    style.theme_use("clam")

    style.configure(".",
                    background=BG, foreground=FG, fieldbackground=FIELD_BG,
                    bordercolor=BORDER, font=FONT_BASE)

    style.configure("TFrame", background=BG)
    style.configure("TLabel", background=BG, foreground=FG)
    style.configure("Title.TLabel", foreground=FG_BRIGHT, font=FONT_TITLE)
    style.configure("Hint.TLabel", foreground=FG_MUTED, font=FONT_HINT)

    style.configure("TLabelframe", background=BG, bordercolor=BORDER,
                    relief="solid", borderwidth=2)
    style.configure("TLabelframe.Label", background=BG, foreground=FG_BRIGHT,
                    font=FONT_SUBTITLE)

    # Buttons rest dark (yellow-on-black, yellow outline); the focused or hovered
    # button fills bright yellow with black text and a white outline, so the active
    # button clearly stands out from the rest.
    style.configure("TButton",
                    background=BG, foreground=ACCENT,
                    bordercolor=FG, focuscolor=ACCENT_TEXT,
                    relief="raised", borderwidth=2, padding=(10, 4),
                    font=(FONT_FAMILY, 11, "bold"))
    style.map("TButton",
              background=[("pressed", "#22BB22"), ("active", ACCENT), ("focus", ACCENT)],
              foreground=[("pressed", ACCENT_TEXT), ("active", ACCENT_TEXT), ("focus", ACCENT_TEXT)],
              bordercolor=[("focus", FOCUS), ("active", ACCENT)],
              lightcolor=[("focus", FOCUS)], darkcolor=[("focus", FOCUS)],
              relief=[("pressed", "sunken")])

    for widget in ("TEntry", "TCombobox", "TSpinbox"):
        style.configure(widget,
                        fieldbackground=FIELD_BG, background=FIELD_BG,
                        foreground=FG, insertcolor=ACCENT_TEXT, bordercolor=BORDER,
                        borderwidth=2, padding=2, arrowcolor=FG)
        # Both hover (`active`) and keyboard focus (`focus`) invert the field to
        # black-on-yellow; focus additionally gets the white outline. The caret is
        # black (set above) so it's clearly visible on the yellow focused field.
        style.map(widget,
                  foreground=[("active", ACCENT_TEXT), ("focus", ACCENT_TEXT)],
                  fieldbackground=[("active", ACCENT), ("focus", ACCENT)],
                  background=[("active", ACCENT), ("focus", ACCENT)],
                  arrowcolor=[("active", ACCENT_TEXT), ("focus", ACCENT_TEXT)],
                  bordercolor=[("focus", FOCUS), ("active", FOCUS)],
                  lightcolor=[("focus", FOCUS), ("active", FOCUS)],
                  darkcolor=[("focus", FOCUS), ("active", FOCUS)])
    # The combobox needs `active`/`focus` listed before `readonly` so hover and
    # focus win over the readonly styling.
    style.map("TCombobox",
              foreground=[("active", ACCENT_TEXT), ("focus", ACCENT_TEXT), ("readonly", FG)],
              fieldbackground=[("active", ACCENT), ("focus", ACCENT), ("readonly", FIELD_BG)],
              background=[("active", ACCENT), ("focus", ACCENT)],
              arrowcolor=[("active", ACCENT_TEXT), ("focus", ACCENT_TEXT)],
              bordercolor=[("focus", FOCUS), ("active", FOCUS)],
              lightcolor=[("focus", FOCUS), ("active", FOCUS)],
              darkcolor=[("focus", FOCUS), ("active", FOCUS)],
              selectbackground=[("readonly", SELECT_BG)],
              selectforeground=[("readonly", SELECT_FG)])
    # The Combobox drop-down list (a classic Listbox) reads from these.
    root.option_add("*TCombobox*Listbox.background", FIELD_BG)
    root.option_add("*TCombobox*Listbox.foreground", FG)
    root.option_add("*TCombobox*Listbox.selectBackground", SELECT_BG)
    root.option_add("*TCombobox*Listbox.selectForeground", SELECT_FG)

    # Tables. A focused table is framed in white; the selected row, when
    # the table has focus, uses the bright select bar (dimmer when it doesn't).
    style.configure("Treeview",
                    background=FIELD_BG, fieldbackground=FIELD_BG,
                    foreground=FG, bordercolor=BORDER, borderwidth=2,
                    rowheight=22)
    style.map("Treeview",
              bordercolor=[("focus", FOCUS)],
              lightcolor=[("focus", FOCUS)], darkcolor=[("focus", FOCUS)],
              # Bright yellow selection when the table has focus; dim amber when it
              # doesn't, so you can always see where you are but which table is live.
              background=[("selected", "focus", SELECT_BG),
                          ("selected", SELECT_DIM)],
              foreground=[("selected", "focus", SELECT_FG),
                          ("selected", FG)])
    style.configure("Treeview.Heading",
                    background=BG_RAISED, foreground=FG_BRIGHT,
                    bordercolor=BORDER, relief="raised",
                    font=(FONT_FAMILY, 10, "bold"))
    style.map("Treeview.Heading",
              background=[("active", ACCENT)],
              foreground=[("active", ACCENT_TEXT)])

    # Notebook tabs.
    style.configure("TNotebook", background=BG, bordercolor=BORDER)
    style.configure("TNotebook.Tab",
                    background=BG_RAISED, foreground=FG,
                    bordercolor=BORDER, padding=(12, 5),
                    font=(FONT_FAMILY, 10, "bold"))
    style.map("TNotebook.Tab",
              background=[("selected", ACCENT)],
              foreground=[("selected", ACCENT_TEXT)])

    # Scrollbars.
    style.configure("TScrollbar",
                    background=BG_RAISED, troughcolor=FIELD_BG,
                    bordercolor=BORDER, arrowcolor=FG)
    style.map("TScrollbar", background=[("active", ACCENT)])

    style.configure("TCheckbutton", background=BG, foreground=FG)
    style.map("TCheckbutton",
              background=[("active", ACCENT)], foreground=[("active", ACCENT_TEXT)])
    style.configure("TMenubutton", background=ACCENT, foreground=ACCENT_TEXT)

    _hover_invert(root)


def _hover_invert(root):
    """Force the `active` state on the field widgets while the mouse is over them.

    Buttons and checkbuttons get `active` on hover automatically (clam), but
    entries/comboboxes/spinboxes don't — so we toggle it ourselves. The styles
    above map `active` to the inverted palette, giving every input/button a clear
    black-on-yellow (or yellow-on-black) highlight under the cursor.
    """
    def enter(event):
        widget = event.widget
        if "disabled" not in widget.state():
            widget.state(["active"])

    def leave(event):
        event.widget.state(["!active"])

    for cls in ("TEntry", "TCombobox", "TSpinbox"):
        root.bind_class(cls, "<Enter>", enter, add="+")
        root.bind_class(cls, "<Leave>", leave, add="+")

    # Render the whole UI in upper case (display + typed entry text).
    force_uppercase(root)


# --- Upper-case everything ---------------------------------------------------
# The app shows only upper-case characters. Rather than upper-casing hundreds of
# literal strings, we patch the text-*display* paths once, here, so every widget
# created afterwards renders upper case. Logic values are deliberately NOT
# touched: Combobox option lists and StringVars keep their real case, so code that
# compares e.g. status == "Invoice" still works. Text typed into an Entry is
# upper-cased (so stored data matches what's shown) except where a widget is
# flagged ``_allow_mixed_case`` (e.g. a case-sensitive API key).
import tkinter as tk  # noqa: E402  (kept local to this feature)

_UPPERCASED = False


def _up(value):
    return value.upper() if isinstance(value, str) else value


def force_uppercase(root):
    """Patch Tk text paths so the UI renders upper case. Idempotent."""
    global _UPPERCASED
    if not _UPPERCASED:
        _UPPERCASED = True
        _patch_ttk_text()
        _patch_classic_text()
        _patch_treeview()
        _patch_notebook()
    _bind_entry_uppercase(root)


def _patch_ttk_text():
    orig_init = ttk.Widget.__init__

    def init(self, master, widgetname, kw=None):
        if kw and "text" in kw:
            kw = dict(kw)
            kw["text"] = _up(kw["text"])
        orig_init(self, master, widgetname, kw)
    ttk.Widget.__init__ = init

    orig_cfg = ttk.Widget.configure

    def configure(self, cnf=None, **kw):
        if "text" in kw:
            kw["text"] = _up(kw["text"])
        if isinstance(cnf, dict) and "text" in cnf:
            cnf = dict(cnf)
            cnf["text"] = _up(cnf["text"])
        return orig_cfg(self, cnf, **kw)
    ttk.Widget.configure = configure
    ttk.Widget.config = configure


def _patch_classic_text():
    for cls in (tk.Label, tk.Button):
        orig_init = cls.__init__

        def make_init(orig):
            def init(self, master=None, cnf={}, **kw):
                if "text" in kw:
                    kw["text"] = _up(kw["text"])
                if isinstance(cnf, dict) and "text" in cnf:
                    cnf = dict(cnf)
                    cnf["text"] = _up(cnf["text"])
                orig(self, master, cnf, **kw)
            return init
        cls.__init__ = make_init(orig_init)

        orig_cfg = cls.configure

        def make_cfg(orig):
            def configure(self, cnf=None, **kw):
                if "text" in kw:
                    kw["text"] = _up(kw["text"])
                if isinstance(cnf, dict) and "text" in cnf:
                    cnf = dict(cnf)
                    cnf["text"] = _up(cnf["text"])
                return orig(self, cnf, **kw)
            return configure
        cls.configure = make_cfg(orig_cfg)
        cls.config = cls.configure

    orig_lb_insert = tk.Listbox.insert

    def lb_insert(self, index, *elements):
        return orig_lb_insert(self, index, *[_up(e) for e in elements])
    tk.Listbox.insert = lb_insert


def _patch_treeview():
    orig_insert = ttk.Treeview.insert

    def insert(self, parent, index, iid=None, **kw):
        if "values" in kw:
            kw["values"] = tuple(_up(v) for v in kw["values"])
        if "text" in kw:
            kw["text"] = _up(kw["text"])
        return orig_insert(self, parent, index, iid, **kw)
    ttk.Treeview.insert = insert

    orig_heading = ttk.Treeview.heading

    def heading(self, column, option=None, **kw):
        if "text" in kw:
            kw["text"] = _up(kw["text"])
        return orig_heading(self, column, option, **kw)
    ttk.Treeview.heading = heading

    orig_item = ttk.Treeview.item

    def item(self, item_id, option=None, **kw):
        if "values" in kw:
            kw["values"] = tuple(_up(v) for v in kw["values"])
        if "text" in kw:
            kw["text"] = _up(kw["text"])
        return orig_item(self, item_id, option, **kw)
    ttk.Treeview.item = item

    orig_set = ttk.Treeview.set

    def tset(self, item_id, column=None, value=None):
        if value is None:
            return orig_set(self, item_id, column, value)  # query
        return orig_set(self, item_id, column, _up(value))
    ttk.Treeview.set = tset


def _patch_notebook():
    orig_add = ttk.Notebook.add

    def add(self, child, **kw):
        if "text" in kw:
            kw["text"] = _up(kw["text"])
        return orig_add(self, child, **kw)
    ttk.Notebook.add = add

    orig_tab = ttk.Notebook.tab

    def tab(self, tab_id, option=None, **kw):
        if "text" in kw:
            kw["text"] = _up(kw["text"])
        return orig_tab(self, tab_id, option, **kw)
    ttk.Notebook.tab = tab


def _bind_entry_uppercase(root):
    def handler(event):
        widget = event.widget
        if getattr(widget, "_allow_mixed_case", False):
            return
        try:
            value = widget.get()
        except Exception:
            return
        upper = value.upper()
        if value != upper:
            # Guarded so read-only/disabled entries (which can't be edited) are
            # simply skipped.
            try:
                pos = widget.index("insert")
                widget.delete(0, "end")
                widget.insert(0, upper)
                widget.icursor(pos)
            except Exception:
                pass

    for cls in ("TEntry", "Entry"):
        root.bind_class(cls, "<KeyRelease>", handler, add="+")
