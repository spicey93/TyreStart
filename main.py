"""Main application window: composes the per-entity screen mixins.

Each screen group lives in its own ui_*.py module as a mixin; this module
wires them onto one App window alongside the shared navigation, menu, and
form-shortcut infrastructure.
"""
import tkinter as tk
from tkinter import ttk, messagebox

from core import database

from ui.suppliers import SuppliersMixin
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
        self.bind_all("<F1>", lambda e: self.show_home())
        self.bind_all("<F2>", lambda e: self._open_section("suppliers"))
        self.bind_all("<F3>", lambda e: self._open_section("products"))
        self.bind_all("<F4>", lambda e: self._open_section("purchases"))
        self.bind_all("<F5>", lambda e: self._open_section("services"))
        self.bind_all("<F6>", lambda e: self._open_section("customers"))
        self.bind_all("<F7>", lambda e: self._open_section("sales"))

        # Container that holds whichever view is currently shown.
        self.container = ttk.Frame(self, padding=20)
        self.container.pack(fill="both", expand=True)

        self.show_home()

    # Section key -> (menubar x-offset, [(item label, command), ...]).
    def _sections(self):
        return {
            "suppliers": (60, [("All Suppliers", self.show_all_suppliers),
                               ("New Supplier", self.show_create_supplier)]),
            "products": (150, [("All Products", self.show_products),
                               ("New Product", self.show_product_form),
                               ("Pricing Rules", self.show_pricing_rules)]),
            "purchases": (245, [("All Purchases", self.show_purchases),
                                ("New Purchase", self.show_purchase_form)]),
            "services": (340, [("All Services", self.show_services),
                               ("New Service", self.show_service_form)]),
            "customers": (425, [("All Customers", self.show_customers),
                                ("New Customer", self.show_customer_form)]),
            "sales": (520, [("All Sales", self.show_sales),
                            ("New Sale", self.show_sale_form)]),
        }

    def _build_menu(self):
        menubar = tk.Menu(self)
        menubar.add_command(label="Home [F1]", command=self.show_home)
        # Each section is a single command that opens our own keyboard-driven
        # dropdown (not a native cascade), so F-keys can switch between open menus.
        labels = {
            "suppliers": "Suppliers [F2]", "products": "Products [F3]",
            "purchases": "Purchases [F4]", "services": "Services [F5]",
            "customers": "Customers [F6]", "sales": "Sales [F7]",
        }
        for key, label in labels.items():
            menubar.add_command(label=label, command=lambda k=key: self._open_section(k))
        self.config(menu=menubar)

    def _open_section(self, key):
        """Open (or switch to) a section's dropdown as an in-window overlay.

        It's a placed Frame inside the main window (not a separate window), so it
        reliably takes keyboard focus and — because it stays in Tk's event loop —
        pressing another F-key while it's open switches straight to that section
        with no Escape needed.
        """
        x_offset, items = self._sections()[key]
        self._section_commands = [command for _, command in items]

        frame = getattr(self, "_section_popup", None)
        if frame is None or not frame.winfo_exists():
            frame = tk.Frame(self, background="#999999")  # 1px border around the list
            listbox = tk.Listbox(
                frame, activestyle="none", exportselection=False, relief="flat",
                highlightthickness=0, font=("Segoe UI", 10), bd=0,
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
        frame.place(x=x_offset, y=0)  # just under the (native) menubar
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
            self._section_commands[index]()

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

    def _bind_form_shortcuts(self, save=None, cancel=None, delete=None):
        """Keyboard shortcuts for a form view: Ctrl+S save, Ctrl+D delete, Esc
        cancel. Pass only the actions the form supports (e.g. omit delete when
        creating). Also starts unsaved-changes tracking so cancel can prompt.
        Cleared automatically on the next view switch."""
        self._unbind_form_shortcuts()
        self._form_shortcuts = []
        self._form_dirty = False

        def bind(sequence, action):
            def handler(_event):
                action()
                return "break"  # don't let the keystroke fall through to widgets
            self._form_shortcuts.append((sequence, self.bind(sequence, handler)))

        # Track edits so cancel can ask before discarding. Typing or changing a
        # dropdown marks the form dirty; line-item changes call mark_form_dirty().
        def on_key(event):
            if event.keysym not in self._NAV_KEYS and not event.keysym.startswith("F"):
                self._form_dirty = True
        self._form_shortcuts.append(("<Key>", self.bind("<Key>", on_key, add="+")))
        self._form_shortcuts.append((
            "<<ComboboxSelected>>",
            self.bind("<<ComboboxSelected>>", lambda e: self.mark_form_dirty(), add="+"),
        ))

        if save:
            bind("<Control-s>", save)
        if delete:
            bind("<Control-d>", delete)
        if cancel:
            bind("<Escape>", cancel)

    def mark_form_dirty(self):
        """Flag the current form as having unsaved changes (e.g. a line added)."""
        self._form_dirty = True

    def _confirm_discard(self):
        """True if it's safe to leave the form: no edits, or the user confirms."""
        if getattr(self, "_form_dirty", False):
            return messagebox.askyesno(
                "Unsaved changes", "You have unsaved changes. Discard them?"
            )
        return True

    def _discard_guard(self, navigate):
        """Wrap a navigation action so it first confirms discarding unsaved edits."""
        def go():
            if self._confirm_discard():
                navigate()
        return go

    def _unbind_form_shortcuts(self):
        for sequence, funcid in getattr(self, "_form_shortcuts", []):
            self.unbind(sequence, funcid)
        self._form_shortcuts = []

    def _clear_container(self):
        self._close_section()  # dismiss any open section dropdown on view switch
        self._unbind_form_shortcuts()  # drop the previous form's shortcuts
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
        self.current_view = "home"
        self._clear_container()
        ttk.Label(
            self.container,
            text="Home",
            font=("Segoe UI", 20, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            self.container,
            text="Welcome! Use the menu bar to manage suppliers and browse products.",
        ).pack(anchor="w", pady=(10, 0))


if __name__ == "__main__":
    App().mainloop()
