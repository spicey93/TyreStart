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
