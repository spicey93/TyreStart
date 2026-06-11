"""Shared UI helpers: autocomplete combobox, sortable tables, VAT options."""
import tkinter as tk
from tkinter import ttk

from ui import theme


# VAT rate options for the line dialog: (label shown, rate percent).
VAT_RATE_OPTIONS = [("20% (Standard)", 20.0), ("5% (Reduced)", 5.0), ("0% (Zero)", 0.0)]


class AutocompleteCombobox(ttk.Combobox):
    """Editable combobox that autocompletes and narrows its list as you type.

    Call set_completion_list() once with all options. As the user types, the
    entry completes to the first matching option (the auto-filled remainder is
    selected, so the next keystroke replaces it) and the dropdown is filtered to
    options starting with what was typed. Press Down to browse the filtered
    matches, Backspace to broaden.
    """

    # Keys that edit/navigate rather than add a character to filter on.
    _SKIP = {
        "Up", "Down", "Left", "Right", "Return", "Escape", "Tab",
        "Shift_L", "Shift_R", "Control_L", "Control_R", "Alt_L", "Alt_R",
        "Home", "End",
    }

    def set_completion_list(self, options):
        # Note: do NOT name this attribute `_options` — that shadows a tkinter
        # internal method (Widget._options) and breaks all widget config calls.
        self._completion = sorted(options, key=str.lower)
        self["values"] = self._completion
        self.bind("<KeyRelease>", self._on_keyrelease)

    def _matches(self, text):
        text = text.lower()
        return [opt for opt in self._completion if opt.lower().startswith(text)]

    def _on_keyrelease(self, event):
        if event.keysym in ("BackSpace", "Delete"):
            # Broaden the filtered list, but don't re-autocomplete over the user.
            self["values"] = self._matches(self.get()) or self._completion
            return
        if event.keysym in self._SKIP:
            return
        typed = self.get()
        if not typed:
            self["values"] = self._completion
            return
        matches = self._matches(typed)
        self["values"] = matches or self._completion
        if matches:
            best = matches[0]
            self.delete(0, tk.END)
            self.insert(0, best)
            self.select_range(len(typed), tk.END)  # highlight the auto-filled part
            self.icursor(len(typed))


def _sort_value(text):
    """Sort key for a cell: numbers (after stripping £ , % etc.) sort numerically
    and ahead of text; everything else sorts case-insensitively as a string."""
    s = str(text).strip()
    cleaned = s.lstrip("£$€").replace(",", "").rstrip("%").strip()
    try:
        return (0, float(cleaned), "")
    except ValueError:
        return (1, 0.0, s.lower())


def _attach_row_hover(tree):
    """Highlight the row under the mouse with a faint amber wash, so it's always
    obvious which row you're pointing at. Applied to every table in the app."""
    tree.tag_configure("hover", background=theme.ROW_HOVER)

    def set_hover(row):
        prev = getattr(tree, "_hover_row", "")
        if row == prev:
            return
        if prev and tree.exists(prev):  # un-hover the previous row
            tree.item(prev, tags=[t for t in tree.item(prev, "tags") if t != "hover"])
        if row:                         # hover the new one
            tree.item(row, tags=list(tree.item(row, "tags")) + ["hover"])
        tree._hover_row = row

    tree.bind("<Motion>", lambda e: set_hover(tree.identify_row(e.y)), add="+")
    tree.bind("<Leave>", lambda e: set_hover(""), add="+")


def make_sortable(tree):
    """Make a Treeview's column headings click-to-sort, toggling asc/desc.
    Sorts the currently displayed rows; a later refresh restores natural order.
    Row iids are preserved (tree.move only reorders), so any code that maps an
    iid to a list index keeps working. Applied to every table in the app."""
    _attach_row_hover(tree)
    state = {"col": None, "reverse": False}

    def sort_by(col):
        reverse = not state["reverse"] if state["col"] == col else False
        state["col"], state["reverse"] = col, reverse
        rows = [(tree.set(iid, col), iid) for iid in tree.get_children("")]
        rows.sort(key=lambda pair: _sort_value(pair[0]), reverse=reverse)
        for index, (_, iid) in enumerate(rows):
            tree.move(iid, "", index)

    for col in tree["columns"]:
        # Preserve the heading text already set; just attach the sort command.
        # Centre both the heading and the cell text (applied to every table).
        tree.heading(col, text=tree.heading(col, "text"), anchor="center",
                     command=lambda c=col: sort_by(c))
        tree.column(col, anchor="center")
