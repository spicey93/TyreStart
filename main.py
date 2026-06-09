import tkinter as tk
from tkinter import ttk, messagebox

import database
import suppliers as db
import products as product_db


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


class App(tk.Tk):
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

        # Keyboard shortcuts for the main views.
        self.current_view = None
        self.bind_all("<F1>", lambda e: self.show_home())
        self.bind_all("<F2>", lambda e: self.show_all_suppliers())
        self.bind_all("<F3>", lambda e: self.show_products())
        self.bind_all(
            "<Control-n>",
            lambda e: self.show_create_supplier() if self.current_view == "suppliers" else None,
        )

        # Container that holds whichever view is currently shown.
        self.container = ttk.Frame(self, padding=20)
        self.container.pack(fill="both", expand=True)

        self.show_home()

    def _build_menu(self):
        menubar = tk.Menu(self)

        menubar.add_command(label="Home [F1]", command=self.show_home)
        menubar.add_command(label="Suppliers [F2]", command=self.show_all_suppliers)
        menubar.add_command(label="Products [F3]", command=self.show_products)

        self.config(menu=menubar)

    def _clear_container(self):
        for widget in self.container.winfo_children():
            widget.destroy()

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

    def show_all_suppliers(self):
        self.current_view = "suppliers"
        self._clear_container()

        header = ttk.Frame(self.container)
        header.pack(fill="x", pady=(0, 10))
        ttk.Label(
            header,
            text="Suppliers",
            font=("Segoe UI", 20, "bold"),
        ).pack(side="left")
        ttk.Button(
            header,
            text="+ New Supplier",
            command=self.show_create_supplier,
        ).pack(side="right")

        field_map = {
            "Name": "name",
            "Account #": "account_number",
            "Contact": "contact",
            "Email": "email",
            "Phone": "phone",
        }

        search_frame = ttk.Frame(self.container)
        search_frame.pack(fill="x", pady=(0, 10))
        # Let the search entry's column absorb any extra horizontal space.
        search_frame.columnconfigure(1, weight=1)

        search_term = tk.StringVar()
        search_field = tk.StringVar(value="Name")

        ttk.Label(search_frame, text="Search:").grid(row=0, column=0, sticky="w")
        search_entry = ttk.Entry(search_frame, textvariable=search_term)
        search_entry.grid(row=0, column=1, sticky="ew", padx=(8, 10))
        search_entry.focus_set()
        search_entry.bind("<Return>", lambda e: do_search())

        ttk.Label(search_frame, text="Filter:").grid(row=0, column=2, sticky="w")
        filter_combo = ttk.Combobox(
            search_frame,
            state="readonly",
            values=list(field_map.keys()),
            textvariable=search_field,
            width=12,
        )
        filter_combo.grid(row=0, column=3, sticky="w", padx=(8, 10))
        filter_combo.current(0)

        def get_rows():
            return db.get_all_suppliers()

        def refresh_tree():
            query = search_term.get().strip().lower()
            key = field_map[search_field.get()]
            rows = get_rows()
            tree.delete(*tree.get_children())
            for s in rows:
                value = (s[key] or "").lower()
                if not query or query in value:
                    tree.insert(
                        "",
                        "end",
                        iid=str(s["id"]),
                        values=(s["name"], s["account_number"], s["contact"], s["email"], s["phone"]),
                    )
            if not tree.get_children():
                if query:
                    status_label.config(text="No suppliers match the current search.")
                else:
                    status_label.config(text="No suppliers yet. Use Create Supplier to add one.")
            else:
                status_label.config(text="")

        def clear_search():
            search_term.set("")
            search_field.set("Name")
            filter_combo.current(0)
            refresh_tree()
            search_entry.focus_set()

        def do_search():
            """Run the search, then move keyboard focus to the first result (if any)."""
            refresh_tree()
            children = tree.get_children()
            if children:
                first = children[0]
                tree.focus_set()           # give the table keyboard focus
                tree.selection_set(first)  # highlight the first row
                tree.focus(first)          # make it the active row for arrow keys
                tree.see(first)            # scroll it into view

        ttk.Button(search_frame, text="Search", command=do_search).grid(
            row=0, column=4, padx=(0, 8)
        )
        ttk.Button(search_frame, text="Clear", command=clear_search).grid(row=0, column=5)

        columns = ("name", "account_number", "contact", "email", "phone")
        headings = ("Name", "Account #", "Contact", "Email", "Phone")
        tree = ttk.Treeview(self.container, columns=columns, show="headings")
        for col, heading in zip(columns, headings):
            tree.heading(col, text=heading)
            tree.column(col, width=130)
        tree.pack(fill="both", expand=True)

        status_label = ttk.Label(self.container, text="")
        status_label.pack(anchor="w", pady=(8, 0))

        def selected_id():
            selection = tree.selection()
            if not selection:
                messagebox.showinfo("No selection", "Please select a supplier first.")
                return None
            return int(selection[0])

        def edit_selected():
            sid = selected_id()
            if sid is not None:
                self.show_supplier_form(db.get_supplier(sid))

        # Double-clicking or pressing Enter on a row opens that supplier.
        tree.bind("<Double-1>", lambda e: edit_selected())
        tree.bind("<Return>", lambda e: edit_selected())

        refresh_tree()

    def show_create_supplier(self):
        self.show_supplier_form()

    def show_supplier_form(self, supplier=None):
        """Form used for both creating (supplier=None) and editing a supplier."""
        self.current_view = "form"
        self._clear_container()
        editing = supplier is not None
        ttk.Label(
            self.container,
            text="Edit Supplier" if editing else "Create Supplier",
            font=("Segoe UI", 20, "bold"),
        ).pack(anchor="w", pady=(0, 15))

        form = ttk.Frame(self.container)
        form.pack(anchor="w")

        entries = {}
        fields = [
            ("name", "Name"),
            ("account_number", "Account #"),
            ("contact", "Contact"),
            ("email", "Email"),
            ("phone", "Phone"),
        ]
        for row, (key, label) in enumerate(fields):
            ttk.Label(form, text=label + ":").grid(row=row, column=0, sticky="w", pady=5, padx=(0, 10))
            entry = ttk.Entry(form, width=40)
            entry.grid(row=row, column=1, pady=5)
            if editing:
                entry.insert(0, supplier[key] or "")
            entries[key] = entry

        def save():
            data = {key: entry.get().strip() for key, entry in entries.items()}
            if not data["name"]:
                messagebox.showwarning("Missing name", "Please enter a supplier name.")
                return
            try:
                if editing:
                    db.update_supplier(
                        supplier["id"], data["name"], data["account_number"],
                        data["contact"], data["email"], data["phone"],
                    )
                    message = f"Supplier '{data['name']}' updated."
                else:
                    db.add_supplier(
                        data["name"], data["account_number"],
                        data["contact"], data["email"], data["phone"],
                    )
                    message = f"Supplier '{data['name']}' created."
            except db.DuplicateNameError:
                messagebox.showerror(
                    "Duplicate name",
                    f"A supplier named '{data['name']}' already exists.",
                )
                return
            messagebox.showinfo("Saved", message)
            self.show_all_suppliers()

        def delete_current():
            if not editing:
                return
            if messagebox.askyesno("Delete supplier", f"Delete '{supplier['name']}'?"):
                db.delete_supplier(supplier["id"])
                self.show_all_suppliers()

        button_frame = ttk.Frame(self.container)
        button_frame.pack(anchor="w", pady=(20, 0))
        ttk.Button(button_frame, text="Save", command=save).pack(side="left")
        if editing:
            ttk.Button(
                button_frame,
                text="Delete",
                command=delete_current,
            ).pack(side="left", padx=(8, 0))

    def show_products(self):
        self.current_view = "products"
        self._clear_container()

        # The catalogue is large (tens of thousands of rows), so we never load
        # it all into the table — searches run in SQL and results are capped.
        RESULT_LIMIT = 200

        header = ttk.Frame(self.container)
        header.pack(fill="x", pady=(0, 10))
        ttk.Label(
            header,
            text="Products",
            font=("Segoe UI", 20, "bold"),
        ).pack(side="left")

        brands = product_db.get_brands()

        search_frame = ttk.Frame(self.container)
        search_frame.pack(fill="x", pady=(0, 10))
        search_frame.columnconfigure(1, weight=1)

        search_term = tk.StringVar()
        brand_choice = tk.StringVar()

        ttk.Label(search_frame, text="Search:").grid(row=0, column=0, sticky="w")
        search_entry = ttk.Entry(search_frame, textvariable=search_term)
        search_entry.grid(row=0, column=1, sticky="ew", padx=(8, 10))
        search_entry.focus_set()
        search_entry.bind("<Return>", lambda e: do_search())

        ttk.Label(search_frame, text="Brand:").grid(row=0, column=2, sticky="w")
        brand_combo = AutocompleteCombobox(
            search_frame,
            textvariable=brand_choice,
            width=20,
        )
        brand_combo.set_completion_list(brands)
        brand_combo.grid(row=0, column=3, sticky="w", padx=(8, 10))
        # Picking a brand (or pressing Enter in the box) re-runs the search.
        # An empty brand box means "all brands".
        brand_combo.bind("<<ComboboxSelected>>", lambda e: refresh_tree())
        brand_combo.bind("<Return>", lambda e: do_search())

        def populate(rows, total):
            tree.delete(*tree.get_children())
            for p in rows:
                tree.insert(
                    "",
                    "end",
                    iid=str(p["id"]),
                    values=(
                        p["stock_code"], p["description"], p["brand"],
                        p["rolling_resistance"], p["wet_grip"], p["noise_class"],
                        p["noise_performance"], p["vehicle_type"],
                    ),
                )
            shown = len(rows)
            if total == 0:
                status_label.config(text="No products match the current search.")
            elif shown < total:
                status_label.config(
                    text=f"Showing first {shown:,} of {total:,} matches — "
                    "narrow your search to see more."
                )
            else:
                status_label.config(text=f"Showing {shown:,} product(s).")

        def refresh_tree():
            rows, total = product_db.query_products(
                text=search_term.get().strip(),
                brand=brand_choice.get().strip(),
                limit=RESULT_LIMIT,
            )
            populate(rows, total)

        def clear_search():
            search_term.set("")
            brand_choice.set("")
            brand_combo["values"] = brands
            refresh_tree()
            search_entry.focus_set()

        def do_search():
            """Run the search, then move keyboard focus to the first result (if any)."""
            refresh_tree()
            children = tree.get_children()
            if children:
                first = children[0]
                tree.focus_set()
                tree.selection_set(first)
                tree.focus(first)
                tree.see(first)

        ttk.Button(search_frame, text="Search", command=do_search).grid(
            row=0, column=4, padx=(0, 8)
        )
        ttk.Button(search_frame, text="Clear", command=clear_search).grid(row=0, column=5)

        columns = (
            "stock_code", "description", "brand", "rolling_resistance",
            "wet_grip", "noise_class", "noise_performance", "vehicle_type",
        )
        headings = (
            "Stock Code", "Description", "Brand", "Rolling Resistance",
            "Wet Grip", "Noise Class", "Noise Performance", "Vehicle Type",
        )
        widths = (120, 240, 100, 130, 80, 90, 130, 100)

        # Tree + scrollbar live in their own frame so the scrollbar sits flush
        # against the table.
        table_frame = ttk.Frame(self.container)
        table_frame.pack(fill="both", expand=True)
        tree = ttk.Treeview(table_frame, columns=columns, show="headings")
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        tree.pack(side="left", fill="both", expand=True)
        for col, heading, width in zip(columns, headings, widths):
            tree.heading(col, text=heading)
            tree.column(col, width=width)

        status_label = ttk.Label(self.container, text="")
        status_label.pack(anchor="w", pady=(8, 0))

        def view_selected():
            selection = tree.selection()
            if not selection:
                messagebox.showinfo("No selection", "Please select a product first.")
                return
            self.show_product_detail(int(selection[0]))

        # Double-clicking or pressing Enter on a row opens that product.
        tree.bind("<Double-1>", lambda e: view_selected())
        tree.bind("<Return>", lambda e: view_selected())

        refresh_tree()

    def show_product_detail(self, product_id):
        """Read-only detail view for a single product."""
        self.current_view = "product_detail"
        self._clear_container()

        product = product_db.get_product(product_id)
        if product is None:
            messagebox.showerror("Not found", "That product no longer exists.")
            self.show_products()
            return

        ttk.Label(
            self.container,
            text=product["description"] or "Product",
            font=("Segoe UI", 20, "bold"),
        ).pack(anchor="w", pady=(0, 15))

        detail = ttk.Frame(self.container)
        detail.pack(anchor="w")
        fields = [
            ("Stock Code", "stock_code"),
            ("Brand", "brand"),
            ("Model", "model"),
            ("EAN", "ean"),
            ("Manufacturer Code", "manufacturer_code"),
            ("Width / Aspect / Rim", None),
            ("Product Type", "product_type"),
            ("Vehicle Type", "vehicle_type"),
            ("Rolling Resistance", "rolling_resistance"),
            ("Wet Grip", "wet_grip"),
            ("Noise Class", "noise_class"),
            ("Noise Performance", "noise_performance"),
            ("Vehicle Class", "vehicle_class"),
            ("Sync Status", "sync_status"),
            ("Created", "created_date"),
            ("Updated", "updated_date"),
        ]
        for row, (label, key) in enumerate(fields):
            if key is None:  # combined size line
                value = f"{product['width']} / {product['aspect_ratio']} / {product['rim']}"
            else:
                value = str(product[key] or "—")
            ttk.Label(detail, text=label + ":", font=("Segoe UI", 9, "bold")).grid(
                row=row, column=0, sticky="w", padx=(0, 12), pady=2
            )
            ttk.Label(detail, text=value).grid(row=row, column=1, sticky="w", pady=2)

        ttk.Button(
            self.container, text="Back to Products", command=self.show_products
        ).pack(anchor="w", pady=(20, 0))


if __name__ == "__main__":
    App().mainloop()
