"""Main application window: composes the per-entity screen mixins.

Each screen group lives in its own ui_*.py module as a mixin; this module
wires them onto one App window alongside the shared navigation, menu, and
form-shortcut infrastructure.
"""
import tkinter as tk
from tkinter import ttk
from ui import dialogs as messagebox

from core import database
from core import daterange

from ui import theme
from ui.common import make_sortable
from ui.suppliers import SuppliersMixin


class SearchEntry(ttk.Entry):
    """A plain Entry that marks itself as the search box of a `_searchable_table`,
    so tab-focus logic can prefer it over the results table."""
from ui.products import ProductsMixin
from ui.pricing import PricingMixin
from ui.purchases import PurchasesMixin
from ui.allocation import AllocationMixin
from ui.payments import PaymentsMixin
from ui.services import ServicesMixin
from ui.customers import CustomersMixin
from ui.sales import SalesMixin
from ui.receipts import ReceiptsMixin


class App(
    SuppliersMixin, ProductsMixin, PricingMixin, PurchasesMixin, AllocationMixin, PaymentsMixin, ServicesMixin, CustomersMixin, SalesMixin, ReceiptsMixin, tk.Tk,
):
    """Main application window with a menu bar and swappable content views."""

    def __init__(self):
        super().__init__()
        self.title("Stock System")
        self.geometry("1000x550")
        # Open windowed; F11 toggles full screen, Ctrl+Q quits the app.
        self.bind_all("<F11>", lambda e: self.attributes(
            "-fullscreen", not self.attributes("-fullscreen")))
        self.bind_all("<Control-q>", lambda e: self._quit())
        # The window-manager close box (when not full screen) confirms too.
        self.protocol("WM_DELETE_WINDOW", self._quit)

        # Retro high-contrast theme — palette and ttk styles live in ui/theme.py.
        theme.apply(self)

        # Ensure all tables (suppliers, products) exist before any view reads them.
        database.init_db()

        self._build_menu()

        # Make Enter activate whichever button currently has focus,
        # matching the default spacebar behavior. Applies to all ttk.Buttons.
        self.bind_class("TButton", "<Return>", lambda e: e.widget.invoke())

        # Keyboard shortcuts for the main views. F-keys open the matching section
        # dropdown; navigate with arrows + Enter. Pressing another F-key while one
        # is open switches straight to it (no Escape needed).
        self.current_view = None
        self._section_popup = None
        self.bind_all("<F2>", lambda e: self._open_section("sales"))
        self.bind_all("<F3>", lambda e: self._open_section("products"))
        self.bind_all("<F4>", lambda e: self._open_section("purchases"))
        self.bind_all("<F5>", lambda e: self._open_section("services"))
        self.bind_all("<F6>", lambda e: self._open_section("customers"))
        self.bind_all("<F7>", lambda e: self._open_section("suppliers"))

        # Container that holds whichever view is currently shown.
        self.container = ttk.Frame(self, padding=20)
        self.container.pack(fill="both", expand=True)

        # The Home page is retired for now (a dashboard will return here later);
        # the app opens on the product catalogue.
        self.show_products()

    # Section key -> [(item label, command), ...]. The dropdown aligns itself
    # under the matching menubar button, so no per-section x-offset is needed.
    def _sections(self):
        return {
            "sales": [("All Sales", self.show_sales),
                      ("New Sale", self.show_sale_form)],
            "products": [("All Products", self.show_products),
                         ("New Product", self.show_product_form),
                         ("Pricing Rules", self.show_pricing_rules)],
            "purchases": [("All Purchases", self.show_purchases),
                          ("New Purchase Order", self.show_purchase_order_form),
                          ("New Purchase Invoice", self.show_purchase_invoice_form),
                          ("New Credit Note", self.show_credit_note)],
            "services": [("All Services", self.show_services),
                         ("New Service", self.show_service_form)],
            "customers": [("All Customers", self.show_customers),
                          ("New Customer", self.show_customer_form),
                          ("New Receipt", self.show_new_receipt)],
            "suppliers": [("All Suppliers", self.show_all_suppliers),
                          ("New Supplier", self.show_create_supplier),
                          ("New Payment", self.show_new_payment)],
        }

    def _build_menu(self):
        """Build a custom in-window menu bar that follows the theme.

        We don't use a native `tk.Menu` menubar: on Windows it's drawn by the OS
        and ignores our colors. Instead the bar is a themed `tk.Frame` of clickable
        labels packed at the top of the window — fully styleable and already the
        anchor our section dropdowns place themselves under.
        """
        menubar = tk.Frame(self, background=theme.BG_RAISED)
        menubar.pack(side="top", fill="x")
        self._menubar = menubar
        self._section_buttons = {}

        def add_item(text, command, key=None):
            item = tk.Label(menubar, text=text, font=(theme.FONT_FAMILY, 11, "bold"),
                            background=theme.BG_RAISED, foreground=theme.FG,
                            padx=12, pady=4, cursor="hand2")
            item.pack(side="left")
            # Hover highlight in amber, matching menus elsewhere in the theme.
            item.bind("<Enter>", lambda e: item.config(background=theme.ACCENT,
                                                        foreground=theme.ACCENT_TEXT))
            item.bind("<Leave>", lambda e: item.config(background=theme.BG_RAISED,
                                                       foreground=theme.FG))
            item.bind("<Button-1>", lambda e: command())
            if key is not None:
                self._section_buttons[key] = item

        labels = {
            "sales": "Sales [F2]", "products": "Products [F3]",
            "purchases": "Purchases [F4]", "services": "Services [F5]",
            "customers": "Customers [F6]", "suppliers": "Suppliers [F7]",
        }
        for key, label in labels.items():
            add_item(label, lambda k=key: self._open_section(k), key=key)

    def _open_section(self, key):
        """Open (or switch to) a section's dropdown as an in-window overlay.

        It's a placed Frame inside the main window (not a separate window), so it
        reliably takes keyboard focus and — because it stays in Tk's event loop —
        pressing another F-key while it's open switches straight to that section
        with no Escape needed.
        """
        items = self._sections()[key]
        self._section_commands = [command for _, command in items]

        frame = getattr(self, "_section_popup", None)
        if frame is None or not frame.winfo_exists():
            frame = tk.Frame(self, background=theme.BORDER)  # bright retro border
            listbox = tk.Listbox(
                frame, activestyle="none", exportselection=False, relief="flat",
                highlightthickness=0, font=(theme.FONT_FAMILY, 11), bd=0,
                background=theme.FIELD_BG, foreground=theme.FG,
                selectbackground=theme.SELECT_BG, selectforeground=theme.SELECT_FG,
            )
            listbox.pack(padx=1, pady=1)
            listbox.bind("<Return>", self._section_choose)
            listbox.bind("<Double-Button-1>", self._section_choose)
            # Return "break" so Esc that closes the dropdown doesn't also fall
            # through to a form's Esc=cancel shortcut behind it.
            listbox.bind("<Escape>", lambda e: (self._close_section(), "break")[1])
            listbox.bind("<FocusOut>", self._on_section_focusout)
            self._section_popup = frame
            self._section_listbox = listbox

        listbox = self._section_listbox
        listbox.delete(0, "end")
        widest = 0
        for label, _ in items:
            listbox.insert("end", "  " + label)
            widest = max(widest, len(label) + 4)
        listbox.config(height=len(items), width=widest)
        listbox.selection_clear(0, "end")
        listbox.selection_set(0)
        listbox.activate(0)

        self._section_opening = True
        # Align the dropdown under its menubar button, just below the bar.
        button = self._section_buttons[key]
        frame.place(x=button.winfo_x(), y=self._menubar.winfo_height())
        frame.lift()
        listbox.focus_set()
        # Clear the "opening" guard after transient focus events settle, so a real
        # focus-loss (clicking elsewhere) still closes the popup.
        self.after_idle(lambda: setattr(self, "_section_opening", False))

    def _section_choose(self, event=None):
        listbox = self._section_listbox
        selection = listbox.curselection()
        index = selection[0] if selection else listbox.index("active")
        self._close_section()
        if 0 <= index < len(self._section_commands):
            self._go(self._section_commands[index])

    def _on_section_focusout(self, event):
        if not getattr(self, "_section_opening", False):
            self._close_section()

    def _close_section(self):
        frame = getattr(self, "_section_popup", None)
        if frame is not None and frame.winfo_exists() and frame.winfo_ismapped():
            frame.place_forget()

    # Keys that move around a form without editing it — they don't mark it dirty.
    _NAV_KEYS = {
        "Escape", "Tab", "ISO_Left_Tab", "Up", "Down", "Left", "Right", "Prior",
        "Next", "Home", "End", "Return", "Shift_L", "Shift_R", "Control_L",
        "Control_R", "Alt_L", "Alt_R", "Win_L", "Win_R", "Caps_Lock",
    }

    def mark_form_dirty(self):
        """Flag the current form as having unsaved changes (e.g. a line added)."""
        self._form_dirty = True

    def _can_leave(self):
        """True if it's OK to leave the current form. With unsaved edits, ask
        whether to save first: Yes saves (and only leaves if the save succeeds),
        No discards, Cancel stays. Forms opt in by registering a save via
        _register_form; older forms (no registered save) fall back to a simple
        discard-or-stay prompt."""
        if not getattr(self, "_form_dirty", False):
            return True
        save = getattr(self, "_form_save", None)
        if save is None:
            return messagebox.askyesno(
                "Unsaved changes", "You have unsaved changes. Discard them?"
            )
        answer = messagebox.askyesnocancel(
            "Unsaved changes", "Save your changes before leaving?"
        )
        if answer is None:       # Cancel -> stay on the form
            return False
        if answer is False:      # No -> leave without saving
            return True
        return bool(save())      # Yes -> leave only if the save succeeds

    def _quit(self):
        """Confirm before closing the application."""
        if messagebox.askyesno("Quit", "Are you sure you want to close the program?"):
            self.destroy()

    def _go(self, target):
        """Navigate by calling `target` (a no-arg callable), first offering to
        save any unsaved edits on the current form."""
        if self._can_leave():
            target()

    def _register_form(self, save, back):
        """Mark the current view as an editable form. Tracks edits (so leaving
        while dirty offers to save), remembers how to `save` (a callable that
        persists and returns a truthy value on success / falsy on validation
        failure), and binds Esc to leave back to `back`. Replaces the explicit
        Save/Cancel buttons. Cleared on the next view switch."""
        self._unbind_form_shortcuts()
        self._form_shortcuts = []
        self._form_dirty = False
        self._form_save = save

        def on_key(event):
            # Widgets tagged `_ignore_dirty` (e.g. in-form search bars) don't count
            # as edits to the record being saved.
            if getattr(event.widget, "_ignore_dirty", False):
                return
            if event.keysym not in self._NAV_KEYS and not event.keysym.startswith("F"):
                self._form_dirty = True
        self._form_shortcuts.append(("<Key>", self.bind("<Key>", on_key, add="+")))

        def on_combo(event):
            if not getattr(event.widget, "_ignore_dirty", False):
                self.mark_form_dirty()
        self._form_shortcuts.append((
            "<<ComboboxSelected>>", self.bind("<<ComboboxSelected>>", on_combo, add="+"),
        ))

        def leave(_event):
            self._go(back)
            return "break"
        self._form_shortcuts.append(("<Escape>", self.bind("<Escape>", leave)))

    def _bind_tab_shortcuts(self, notebook):
        """Bind Ctrl+1, Ctrl+2, … to select the matching tab of `notebook`, label
        each tab with its shortcut, and focus the first item of a tab when it's
        shown.

        Registered alongside the current form's shortcuts so they're cleared on
        the next view switch. Call after `_register_form` (which resets the list).
        """
        for index, tab_id in enumerate(notebook.tabs()):
            seq = f"<Control-Key-{index + 1}>"
            notebook.tab(tab_id, text=f"{notebook.tab(tab_id, 'text')} (Ctrl+{index + 1})")

            def select(_event, idx=index):
                notebook.select(idx)
                return "break"

            funcid = self.bind(seq, select)
            self._form_shortcuts.append((seq, funcid))

        # Highlight the first item of whichever tab becomes visible.
        notebook.bind(
            "<<NotebookTabChanged>>",
            lambda e: self.after_idle(lambda: self._focus_tab(notebook)),
        )

    def _focus_tab(self, notebook):
        """Focus the first item of the notebook's current tab: a search box if the
        tab has one, else a table's first row, else the first entry/button."""
        selected = notebook.select()
        if not selected:
            return
        frame = notebook.nametowidget(selected)
        # A searchable tab (list-style) starts in its search box.
        search_box = self._first_descendant(frame, (SearchEntry,))
        if search_box is not None:
            search_box.focus_set()
            return
        tree = self._first_descendant(frame, (ttk.Treeview,))
        if tree is not None:
            tree.focus_set()
            children = tree.get_children()
            if children:
                tree.selection_set(children[0])
                tree.focus(children[0])
                tree.see(children[0])
            return
        target = (self._first_descendant(frame, (ttk.Entry, ttk.Combobox))
                  or self._first_descendant(frame, (ttk.Button,)))
        if target is not None:
            target.focus_set()

    def _make_date_filter(self, parent, on_change):
        """Build a Period + Start + End date-filter group inside `parent`.

        Choosing a period (Today, This week, …) fills the Start/End boxes; editing
        either box switches the period to 'Custom'. Returns `(frame, get_range)`
        where `get_range()` -> `(start_date|None, end_date|None)` parsed from the
        boxes (an open bound means no limit on that side).
        """
        frame = ttk.Frame(parent)
        period_var = tk.StringVar(value="All")
        start_var = tk.StringVar()
        end_var = tk.StringVar()
        guard = {"syncing": False}

        ttk.Label(frame, text="Period:").grid(row=0, column=0, sticky="w", padx=(0, 6))
        period = ttk.Combobox(frame, state="readonly", width=12,
                              textvariable=period_var, values=list(daterange.PERIODS))
        period.grid(row=0, column=1, padx=(0, 10))
        period.current(0)
        ttk.Label(frame, text="Start:").grid(row=0, column=2, sticky="w", padx=(0, 6))
        start = ttk.Entry(frame, width=10, textvariable=start_var)
        start.grid(row=0, column=3, padx=(0, 10))
        ttk.Label(frame, text="End:").grid(row=0, column=4, sticky="w", padx=(0, 6))
        end = ttk.Entry(frame, width=10, textvariable=end_var)
        end.grid(row=0, column=5, padx=(0, 10))
        # Filter controls, not record fields — never dirty an edit form.
        for w in (period, start, end):
            w._ignore_dirty = True

        def on_period(_event=None):
            guard["syncing"] = True
            if period_var.get() in ("All", "Custom"):
                if period_var.get() == "All":
                    start_var.set("")
                    end_var.set("")
            else:
                s, e = daterange.period_range(period_var.get())
                start_var.set(daterange.format(s))
                end_var.set(daterange.format(e))
            guard["syncing"] = False
            on_change()

        def on_edit(*_):
            if guard["syncing"]:
                return
            period_var.set("Custom")
            on_change()

        period.bind("<<ComboboxSelected>>", on_period)
        start_var.trace_add("write", on_edit)
        end_var.trace_add("write", on_edit)

        return frame, (lambda: (daterange.parse(start_var.get()),
                                daterange.parse(end_var.get())))

    def _searchable_table(self, parent, columns, headings, rows, cells,
                          widths=None, right_cols=(), field_labels=None,
                          empty_text="No records.", iid=None,
                          on_open=None, on_delete=None, height=8,
                          search_first=False):
        """Build a search/filter bar above a Treeview inside `parent`.

        - `rows`: source records; `cells(r)` returns {column_id: display string}.
        - `field_labels`: (label, column_id|None) pairs for the Filter combo — a
          None column searches every column. Defaults to All + one per column.
        - `iid(r)`: the tree iid for a row (enables `on_open`/`on_delete`, which
          receive the selected int iid on double-click/Enter and Delete).
        - `search_first`: start with an empty table (no rows listed until a search
          term is entered).
        Returns the Treeview.
        """
        field_labels = field_labels or ([("All", None)]
                                        + [(h, c) for c, h in zip(columns, headings)])
        field_map = dict(field_labels)

        bar = ttk.Frame(parent)
        bar.pack(fill="x", pady=(0, 8))
        bar.columnconfigure(1, weight=1)
        search_var = tk.StringVar()
        field_var = tk.StringVar(value=field_labels[0][0])
        ttk.Label(bar, text="Search:").grid(row=0, column=0, sticky="w")
        # A search-first tab starts focused in its box (SearchEntry); the others
        # keep highlighting the table's first row, so use a plain Entry there.
        entry = (SearchEntry if search_first else ttk.Entry)(bar, textvariable=search_var)
        entry.grid(row=0, column=1, sticky="ew", padx=(8, 10))
        ttk.Label(bar, text="Filter:").grid(row=0, column=2, sticky="w")
        field_combo = ttk.Combobox(
            bar, state="readonly", width=12, textvariable=field_var,
            values=[label for label, _ in field_labels],
        )
        field_combo.grid(row=0, column=3, sticky="w", padx=(8, 10))
        field_combo.current(0)
        # These belong to a search bar, not the record — don't dirty an edit form.
        entry._ignore_dirty = field_combo._ignore_dirty = True
        ttk.Button(bar, text="Search", command=lambda: refresh()).grid(row=0, column=4, padx=(0, 8))
        ttk.Button(bar, text="Clear", command=lambda: clear()).grid(row=0, column=5)

        table_frame = ttk.Frame(parent)
        table_frame.pack(fill="both", expand=True)
        tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=height)
        sb = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        tree.pack(side="left", fill="both", expand=True)
        widths = widths or [120] * len(columns)
        for col, heading, width in zip(columns, headings, widths):
            tree.heading(col, text=heading)
            tree.column(col, width=width)
        for col in right_cols:
            tree.column(col, anchor="e")
        make_sortable(tree)

        status = ttk.Label(parent, text="")
        status.pack(anchor="w", pady=(8, 0))

        prepared = [(iid(r) if iid else None, cells(r)) for r in rows]

        def refresh():
            query = search_var.get().strip().lower()
            col = field_map[field_var.get()]
            tree.delete(*tree.get_children())
            if not rows:
                status.config(text=empty_text)
                return
            if search_first and not query:
                # Wait for a search term before listing anything.
                status.config(text=f"Type a search term to list {len(rows)} record(s).")
                return
            shown = 0
            for row_iid, c in prepared:
                hay = (" ".join(c[k] for k in columns) if col is None else c[col]).lower()
                if not query or query in hay:
                    kwargs = {"iid": row_iid} if row_iid is not None else {}
                    tree.insert("", "end", values=tuple(c[k] for k in columns), **kwargs)
                    shown += 1
            if shown == 0:
                status.config(text="No matches for the current search.")
            else:
                status.config(text=f"Showing {shown} of {len(rows)}.")

        def clear():
            search_var.set("")
            field_var.set(field_labels[0][0])
            field_combo.current(0)
            refresh()
            entry.focus_set()

        def act(fn):
            selection = tree.selection()
            if selection:
                fn(int(selection[0]))
            return "break"

        entry.bind("<Return>", lambda e: refresh())
        field_combo.bind("<<ComboboxSelected>>", lambda e: refresh())
        if on_open:
            tree.bind("<Double-1>", lambda e: act(on_open))
            tree.bind("<Return>", lambda e: act(on_open))
        if on_delete:
            tree.bind("<Delete>", lambda e: act(on_delete))

        refresh()
        return tree

    def _unbind_form_shortcuts(self):
        for sequence, funcid in getattr(self, "_form_shortcuts", []):
            self.unbind(sequence, funcid)
        self._form_shortcuts = []

    def _clear_container(self):
        self._close_section()  # dismiss any open section dropdown on view switch
        self._unbind_form_shortcuts()  # drop the previous form's shortcuts
        # A fresh view starts with no unsaved edits and no registered save, so
        # navigating away from a plain list view never prompts.
        self._form_dirty = False
        self._form_save = None
        for widget in self.container.winfo_children():
            widget.destroy()
        # Once the new view has been built (next idle), focus its first interactive
        # widget so every screen is keyboard-ready on load.
        self.after_idle(self._focus_first_input)

    def _focus_first_input(self):
        """Focus the first interactive widget in the current view: an entry/combo
        if there is one, otherwise a table, otherwise a button."""
        for types in ((ttk.Entry, ttk.Combobox), (ttk.Treeview,), (ttk.Button,)):
            target = self._first_descendant(self.container, types)
            if target is not None:
                target.focus_set()
                return

    def _first_descendant(self, parent, types):
        """Depth-first search for the first descendant of one of `types`."""
        for child in parent.winfo_children():
            if isinstance(child, types):
                return child
            found = self._first_descendant(child, types)
            if found is not None:
                return found
        return None

    def show_home(self):
        """Reserved for a future dashboard view. Not wired into navigation yet —
        the app currently opens on the product catalogue instead."""
        self.current_view = "home"
        self._clear_container()
        ttk.Label(self.container, text="Home", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            self.container,
            text="A dashboard will live here in the future.",
        ).pack(anchor="w", pady=(10, 0))


if __name__ == "__main__":
    App().mainloop()
