import datetime
import tkinter as tk
from tkinter import ttk, messagebox

import database
import suppliers as db
import products as product_db
import purchases as purchase_db
import payments as payment_db
import nominals
import services as service_db

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
        # F-keys open the matching menu dropdown; navigate it with arrows + Enter.
        self.bind_all("<F1>", lambda e: self.show_home())
        self.bind_all("<F2>", lambda e: self._post_section_menu(self._suppliers_menu, 60))
        self.bind_all("<F3>", lambda e: self._post_section_menu(self._products_menu, 150))
        self.bind_all("<F4>", lambda e: self._post_section_menu(self._purchases_menu, 245))
        self.bind_all("<F5>", lambda e: self._post_section_menu(self._services_menu, 340))

        # Container that holds whichever view is currently shown.
        self.container = ttk.Frame(self, padding=20)
        self.container.pack(fill="both", expand=True)

        self.show_home()

    def _build_menu(self):
        menubar = tk.Menu(self)

        menubar.add_command(label="Home [F1]", command=self.show_home)

        # Cascades are stored on self so the F-keys can post them for keyboard use.
        self._suppliers_menu = tk.Menu(menubar, tearoff=0)
        self._suppliers_menu.add_command(label="All Suppliers", command=self.show_all_suppliers)
        self._suppliers_menu.add_command(label="New Supplier", command=self.show_create_supplier)
        menubar.add_cascade(label="Suppliers [F2]", menu=self._suppliers_menu)

        self._products_menu = tk.Menu(menubar, tearoff=0)
        self._products_menu.add_command(label="All Products", command=self.show_products)
        self._products_menu.add_command(label="New Product", command=self.show_product_form)
        menubar.add_cascade(label="Products [F3]", menu=self._products_menu)

        self._purchases_menu = tk.Menu(menubar, tearoff=0)
        self._purchases_menu.add_command(label="All Purchases", command=self.show_purchases)
        self._purchases_menu.add_command(label="New Purchase", command=self.show_purchase_form)
        menubar.add_cascade(label="Purchases [F4]", menu=self._purchases_menu)

        self._services_menu = tk.Menu(menubar, tearoff=0)
        self._services_menu.add_command(label="All Services", command=self.show_services)
        self._services_menu.add_command(label="New Service", command=self.show_service_form)
        menubar.add_cascade(label="Services [F5]", menu=self._services_menu)

        self.config(menu=menubar)

    def _clear_container(self):
        for widget in self.container.winfo_children():
            widget.destroy()

    def _post_section_menu(self, menu, x_offset):
        """Open a menubar dropdown so it can be driven with arrow keys + Enter."""
        try:
            menu.tk_popup(self.winfo_rootx() + x_offset, self.winfo_rooty() + 2)
        finally:
            menu.grab_release()

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

        # Account section: balance + payment actions (only for an existing supplier).
        if editing:
            account = ttk.LabelFrame(self.container, text="Account", padding=10)
            account.pack(anchor="w", fill="x", pady=(20, 0))
            balance = payment_db.supplier_balance(supplier["id"])
            ttk.Label(
                account,
                text=f"Balance owed: {balance:,.2f}",
                font=("Segoe UI", 12, "bold"),
            ).pack(anchor="w")
            acc_btns = ttk.Frame(account)
            acc_btns.pack(anchor="w", pady=(8, 0))
            ttk.Button(
                acc_btns, text="Make Payment",
                command=lambda: self.show_payment_form(supplier["id"]),
            ).pack(side="left")
            ttk.Button(
                acc_btns, text="View Payments",
                command=lambda: self.show_payments(supplier["id"]),
            ).pack(side="left", padx=(8, 0))
            ttk.Button(
                acc_btns, text="View Purchases",
                command=lambda: self.show_purchases(prefill=supplier["name"]),
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
        instock_choice = tk.StringVar(value="Yes")

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

        ttk.Label(search_frame, text="In stock:").grid(row=0, column=4, sticky="w")
        instock_combo = ttk.Combobox(
            search_frame, state="readonly", width=6, textvariable=instock_choice,
            values=["Yes", "No", "All"],
        )
        instock_combo.grid(row=0, column=5, sticky="w", padx=(8, 10))
        instock_combo.current(0)
        instock_combo.bind("<<ComboboxSelected>>", lambda e: refresh_tree())

        SEARCH_BTN_COL, CLEAR_BTN_COL = 6, 7

        def populate(rows, total):
            tree.delete(*tree.get_children())
            for p in rows:
                tree.insert(
                    "",
                    "end",
                    iid=str(p["id"]),
                    values=(
                        p["stock_code"], p["description"], p["brand"], p["stock"],
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
            text = search_term.get().strip()
            brand = brand_choice.get().strip()
            # Don't show anything until the user applies a filter.
            if not text and not brand:
                tree.delete(*tree.get_children())
                status_label.config(
                    text="Enter a search term or choose a brand to see products."
                )
                return
            rows, total = product_db.query_products(
                text=text, brand=brand, in_stock=instock_choice.get().lower(),
                limit=RESULT_LIMIT,
            )
            populate(rows, total)

        def clear_search():
            search_term.set("")
            brand_choice.set("")
            brand_combo["values"] = brands
            instock_choice.set("Yes")
            instock_combo.current(0)
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
            row=0, column=SEARCH_BTN_COL, padx=(0, 8)
        )
        ttk.Button(search_frame, text="Clear", command=clear_search).grid(
            row=0, column=CLEAR_BTN_COL
        )

        columns = (
            "stock_code", "description", "brand", "stock", "rolling_resistance",
            "wet_grip", "noise_class", "noise_performance", "vehicle_type",
        )
        headings = (
            "Stock Code", "Description", "Brand", "Stock", "Rolling Resistance",
            "Wet Grip", "Noise Class", "Noise Performance", "Vehicle Type",
        )
        widths = (120, 230, 100, 60, 120, 80, 90, 120, 90)

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
            ("Stock", "__stock__"),
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
            elif key == "__stock__":
                value = str(product_db.product_stock(product["id"]))
            else:
                value = str(product[key] or "—")
            ttk.Label(detail, text=label + ":", font=("Segoe UI", 9, "bold")).grid(
                row=row, column=0, sticky="w", padx=(0, 12), pady=2
            )
            ttk.Label(detail, text=value).grid(row=row, column=1, sticky="w", pady=2)

        ttk.Button(
            self.container, text="Back to Products", command=self.show_products
        ).pack(anchor="w", pady=(20, 0))

    def show_product_form(self):
        """Create a new product (stock code is derived automatically)."""
        self.current_view = "product_form"
        self._clear_container()
        ttk.Label(
            self.container, text="New Product", font=("Segoe UI", 20, "bold")
        ).pack(anchor="w", pady=(0, 15))

        form = ttk.Frame(self.container)
        form.pack(anchor="w")
        fields = [
            ("description", "Description"),
            ("brand", "Brand"),
            ("model", "Model"),
            ("ean", "EAN"),
            ("manufacturer_code", "Manufacturer Code"),
            ("product_type", "Product Type"),
            ("vehicle_type", "Vehicle Type"),
            ("rolling_resistance", "Rolling Resistance"),
            ("wet_grip", "Wet Grip"),
            ("noise_class", "Noise Class"),
            ("noise_performance", "Noise Performance"),
            ("vehicle_class", "Vehicle Class"),
        ]
        entries = {}
        for row, (key, label) in enumerate(fields):
            ttk.Label(form, text=label + ":").grid(row=row, column=0, sticky="w", pady=4, padx=(0, 10))
            entry = ttk.Entry(form, width=40)
            entry.grid(row=row, column=1, pady=4)
            entries[key] = entry

        ttk.Label(
            self.container,
            text="Stock Code is generated automatically from the size, brand and "
            "manufacturer code.",
            foreground="gray",
        ).pack(anchor="w", pady=(10, 0))

        def save():
            data = {key: entry.get().strip() for key, entry in entries.items()}
            if not data["description"]:
                messagebox.showwarning("Missing description", "Please enter a description.")
                return
            product_db.create_product(**data)
            messagebox.showinfo("Saved", "Product created.")
            self.show_products()

        btns = ttk.Frame(self.container)
        btns.pack(anchor="w", pady=(15, 0))
        ttk.Button(btns, text="Save", command=save).pack(side="left")
        ttk.Button(btns, text="Cancel", command=self.show_products).pack(side="left", padx=(8, 0))

    # ------------------------------------------------------------------ Purchases

    def show_purchases(self, prefill=""):
        self.current_view = "purchases"
        self._clear_container()

        header = ttk.Frame(self.container)
        header.pack(fill="x", pady=(0, 10))
        ttk.Label(
            header, text="Purchases", font=("Segoe UI", 20, "bold")
        ).pack(side="left")

        bar = ttk.Frame(self.container)
        bar.pack(fill="x", pady=(0, 10))
        bar.columnconfigure(1, weight=1)

        search_term = tk.StringVar(value=prefill)
        status_choice = tk.StringVar(value="All")

        ttk.Label(bar, text="Search:").grid(row=0, column=0, sticky="w")
        search_entry = ttk.Entry(bar, textvariable=search_term)
        search_entry.grid(row=0, column=1, sticky="ew", padx=(8, 10))
        search_entry.focus_set()
        search_entry.bind("<Return>", lambda e: refresh())

        ttk.Label(bar, text="Status:").grid(row=0, column=2, sticky="w")
        status_combo = ttk.Combobox(
            bar, state="readonly", width=10, textvariable=status_choice,
            values=["All", "Order", "Invoice"],
        )
        status_combo.grid(row=0, column=3, sticky="w", padx=(8, 10))
        status_combo.current(0)
        status_combo.bind("<<ComboboxSelected>>", lambda e: refresh())
        ttk.Button(bar, text="Search", command=lambda: refresh()).grid(row=0, column=4, padx=(0, 8))
        ttk.Button(bar, text="Clear", command=lambda: clear()).grid(row=0, column=5)

        columns = ("reference", "supplier", "status", "date", "total")
        headings = ("Reference", "Supplier", "Status", "Date", "Total")
        widths = (170, 230, 90, 110, 110)
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
        tree.column("total", anchor="e")

        status_label = ttk.Label(self.container, text="")
        status_label.pack(anchor="w", pady=(8, 0))

        def refresh():
            status = status_choice.get()
            rows = purchase_db.list_purchases(
                text=search_term.get().strip(),
                status="" if status == "All" else status,
            )
            tree.delete(*tree.get_children())
            for r in rows:
                tree.insert(
                    "", "end", iid=str(r["id"]),
                    values=(
                        r["reference"] or "", r["supplier_name"], r["status"],
                        r["date"] or "", f"{r['total']:,.2f}",
                    ),
                )
            status_label.config(
                text=f"{len(rows)} purchase(s)." if rows else "No purchases found."
            )

        def clear():
            search_term.set("")
            status_choice.set("All")
            status_combo.current(0)
            refresh()
            search_entry.focus_set()

        def open_selected():
            selection = tree.selection()
            if not selection:
                messagebox.showinfo("No selection", "Please select a purchase first.")
                return
            self.show_purchase_form(purchase_db.get_purchase(int(selection[0])))

        tree.bind("<Double-1>", lambda e: open_selected())
        tree.bind("<Return>", lambda e: open_selected())
        refresh()

    def show_purchase_form(self, purchase=None):
        """Create/edit a purchase, including its product line items."""
        self.current_view = "purchase_form"
        self._clear_container()
        editing = purchase is not None

        ttk.Label(
            self.container,
            text="Edit Purchase" if editing else "New Purchase",
            font=("Segoe UI", 20, "bold"),
        ).pack(anchor="w", pady=(0, 12))

        # --- Header fields ---
        head = ttk.Frame(self.container)
        head.pack(anchor="w")
        supplier_by_name = {s["name"]: s["id"] for s in db.get_all_suppliers()}

        supplier_var = tk.StringVar()
        status_var = tk.StringVar(value="Order")
        reference_var = tk.StringVar()
        date_var = tk.StringVar(value=datetime.date.today().strftime("%d/%m/%y"))

        ttk.Label(head, text="Supplier:").grid(row=0, column=0, sticky="w", pady=4, padx=(0, 10))
        supplier_combo = AutocompleteCombobox(head, textvariable=supplier_var, width=37)
        supplier_combo.set_completion_list(list(supplier_by_name.keys()))
        supplier_combo.grid(row=0, column=1, sticky="w", pady=4)

        ttk.Label(head, text="Status:").grid(row=1, column=0, sticky="w", pady=4, padx=(0, 10))
        ttk.Combobox(
            head, state="readonly", width=15, textvariable=status_var,
            values=list(purchase_db.STATUSES),
        ).grid(row=1, column=1, sticky="w", pady=4)

        ttk.Label(head, text="Reference:").grid(row=2, column=0, sticky="w", pady=4, padx=(0, 10))
        ttk.Entry(head, textvariable=reference_var, width=40).grid(row=2, column=1, sticky="w", pady=4)

        ttk.Label(head, text="Date:").grid(row=3, column=0, sticky="w", pady=4, padx=(0, 10))
        ttk.Entry(head, textvariable=date_var, width=20).grid(row=3, column=1, sticky="w", pady=4)

        # --- Line items: added via the Product Allocation window ---
        prod_header = ttk.Frame(self.container)
        prod_header.pack(fill="x", pady=(15, 5))
        ttk.Label(
            prod_header, text="Products", font=("Segoe UI", 12, "bold")
        ).pack(side="left")
        ttk.Button(
            prod_header, text="Add Product",
            command=lambda: self.open_product_allocation(receive_basket),
        ).pack(side="left", padx=(12, 0))

        lines = []  # dicts: product_id, label, quantity, cost_price

        def receive_basket(items):
            """Called by the Product Allocation window when its basket is submitted."""
            lines.extend(items)
            refresh_lines()

        lt_frame = ttk.Frame(self.container)
        lt_frame.pack(fill="both", expand=True, pady=(8, 0))
        lines_tree = ttk.Treeview(
            lt_frame, columns=("product", "qty", "cost", "vat", "total"),
            show="headings", height=6,
        )
        for col, heading, width, anchor in [
            ("product", "Product", 300, "w"), ("qty", "Qty", 50, "e"),
            ("cost", "Cost", 90, "e"), ("vat", "VAT", 60, "e"),
            ("total", "Line Total", 100, "e"),
        ]:
            lines_tree.heading(col, text=heading)
            lines_tree.column(col, width=width, anchor=anchor)
        ls = ttk.Scrollbar(lt_frame, orient="vertical", command=lines_tree.yview)
        lines_tree.configure(yscrollcommand=ls.set)
        ls.pack(side="right", fill="y")
        lines_tree.pack(side="left", fill="both", expand=True)

        bottom = ttk.Frame(self.container)
        bottom.pack(fill="x", pady=(6, 0))
        ttk.Button(bottom, text="Remove line", command=lambda: remove_line()).pack(side="left")
        total_label = ttk.Label(
            bottom, text="Net 0.00   VAT 0.00   Gross 0.00", font=("Segoe UI", 10, "bold")
        )
        total_label.pack(side="right")

        def remove_line():
            selection = lines_tree.selection()
            if not selection:
                return
            del lines[int(selection[0])]
            refresh_lines()

        def refresh_lines():
            lines_tree.delete(*lines_tree.get_children())
            net_total = vat_total = gross_total = 0.0
            for index, ln in enumerate(lines):
                net = ln["quantity"] * ln["cost_price"]
                vat = net * ln["vat_rate"] / 100.0
                gross = net + vat
                net_total += net
                vat_total += vat
                gross_total += gross
                lines_tree.insert(
                    "", "end", iid=str(index),
                    values=(ln["label"], ln["quantity"], f"{ln['cost_price']:.2f}",
                            f"{ln['vat_rate']:.0f}%", f"{gross:,.2f}"),
                )
            total_label.config(
                text=f"Net {net_total:,.2f}   VAT {vat_total:,.2f}   Gross {gross_total:,.2f}"
            )

        def edit_cell(event):
            """Double-click the Qty or Cost cell to edit it inline."""
            if lines_tree.identify("region", event.x, event.y) != "cell":
                return
            column = lines_tree.identify_column(event.x)  # '#1'..'#5'
            rowid = lines_tree.identify_row(event.y)
            if not rowid or column not in ("#2", "#3"):  # only Qty (#2) / Cost (#3)
                return
            key = "quantity" if column == "#2" else "cost_price"
            index = int(rowid)
            bbox = lines_tree.bbox(rowid, column)
            if not bbox:
                return
            x, y, w, h = bbox
            editor = ttk.Entry(lines_tree)
            editor.place(x=x, y=y, width=w, height=h)
            editor.insert(0, str(lines[index][key]))
            editor.select_range(0, "end")
            editor.focus_set()

            def commit(_=None):
                raw = editor.get().strip()
                try:
                    if key == "quantity":
                        value = int(raw)
                        if value <= 0:
                            raise ValueError
                    else:
                        value = float(raw)
                        if value < 0:
                            raise ValueError
                except ValueError:
                    editor.destroy()
                    return
                lines[index][key] = value
                editor.destroy()
                refresh_lines()

            editor.bind("<Return>", commit)
            editor.bind("<FocusOut>", commit)
            editor.bind("<Escape>", lambda e: editor.destroy())

        lines_tree.bind("<Double-1>", edit_cell)

        def save():
            supplier_name = supplier_var.get().strip()
            supplier_id = supplier_by_name.get(supplier_name)
            if supplier_id is None:  # case-insensitive fallback
                for name, sid in supplier_by_name.items():
                    if name.lower() == supplier_name.lower():
                        supplier_id = sid
                        break
            if supplier_id is None:
                messagebox.showwarning("Supplier", "Please choose a valid supplier.")
                return
            if not lines:
                messagebox.showwarning("No products", "Add at least one product line.")
                return
            items = [
                {"product_id": ln["product_id"], "quantity": ln["quantity"],
                 "cost_price": ln["cost_price"], "vat_rate": ln["vat_rate"]}
                for ln in lines
            ]
            args = (supplier_id, status_var.get(), reference_var.get().strip(),
                    date_var.get().strip(), items)
            if editing:
                purchase_db.update_purchase(purchase["id"], *args)
            else:
                purchase_db.create_purchase(*args)
            messagebox.showinfo("Saved", "Purchase saved.")
            self.show_purchases()

        def delete_current():
            if not editing:
                return
            if messagebox.askyesno("Delete purchase", "Delete this purchase?"):
                try:
                    purchase_db.delete_purchase(purchase["id"])
                except Exception as exc:  # e.g. an invoice with payments allocated
                    messagebox.showerror("Cannot delete", str(exc))
                    return
                self.show_purchases()

        btns = ttk.Frame(self.container)
        btns.pack(anchor="w", pady=(12, 0))
        ttk.Button(btns, text="Save", command=save).pack(side="left")
        ttk.Button(btns, text="Cancel", command=self.show_purchases).pack(side="left", padx=(8, 0))
        if editing:
            ttk.Button(btns, text="Delete", command=delete_current).pack(side="left", padx=(8, 0))

        # Prefill when editing (after the line widgets exist).
        if editing:
            supplier_var.set(purchase["supplier_name"])
            status_var.set(purchase["status"])
            reference_var.set(purchase["reference"] or "")
            date_var.set(purchase["date"] or "")
            for it in purchase_db.get_purchase_items(purchase["id"]):
                lines.append({
                    "product_id": it["product_id"],
                    "label": f"{it['stock_code']} — {it['description']}",
                    "quantity": it["quantity"],
                    "cost_price": it["cost_price"],
                    "vat_rate": it["vat_rate"],
                })
            refresh_lines()

    # ------------------------------------------------------- Product Allocation

    def open_product_allocation(self, on_submit):
        """Modal window to search products, build a basket, and submit it to a
        purchase. `on_submit` receives a list of line dicts
        (product_id, label, quantity, cost_price)."""
        win = tk.Toplevel(self)
        win.title("Product Allocation")
        win.geometry("920x620")
        win.transient(self)

        basket = []  # dicts: product_id, label, quantity, cost_price
        result_map = {}  # iid -> product Row

        # --- Search controls ---
        search = ttk.Frame(win, padding=10)
        search.pack(fill="x")
        stock_var = tk.StringVar()
        brand_var = tk.StringVar()
        model_var = tk.StringVar()

        ttk.Label(search, text="Stock Code:").grid(row=0, column=0, sticky="w")
        stock_entry = ttk.Entry(search, textvariable=stock_var, width=20)
        stock_entry.grid(row=0, column=1, padx=(6, 12))
        # Enter searches; if the box is empty and the basket has items, it submits.
        stock_entry.bind("<Return>", lambda e: on_stock_return())

        ttk.Label(search, text="Brand:").grid(row=0, column=2, sticky="w")
        brand_combo = AutocompleteCombobox(search, textvariable=brand_var, width=18)
        brand_combo.set_completion_list(product_db.get_brands())
        brand_combo.grid(row=0, column=3, padx=(6, 12))
        brand_combo.bind("<Return>", lambda e: do_search())
        # Narrow the model list to the chosen brand (and size).
        brand_combo.bind("<<ComboboxSelected>>", lambda e: refresh_models())

        ttk.Label(search, text="Model:").grid(row=0, column=4, sticky="w")
        model_combo = AutocompleteCombobox(search, textvariable=model_var, width=18)
        model_combo.set_completion_list(product_db.get_models())
        model_combo.grid(row=0, column=5, padx=(6, 12))
        model_combo.bind("<Return>", lambda e: do_search())

        ttk.Button(search, text="Search", command=lambda: do_search()).grid(row=0, column=6, padx=(0, 6))
        ttk.Button(search, text="Clear", command=lambda: clear()).grid(row=0, column=7)

        # --- Results ---
        res_frame = ttk.Frame(win, padding=(10, 0))
        res_frame.pack(fill="both", expand=True)
        rcols = ("stock_code", "description", "brand", "model")
        results = ttk.Treeview(res_frame, columns=rcols, show="headings", height=10)
        for col, heading, width in zip(
            rcols, ("Stock Code", "Description", "Brand", "Model"), (140, 320, 120, 150)
        ):
            results.heading(col, text=heading)
            results.column(col, width=width)
        rsb = ttk.Scrollbar(res_frame, orient="vertical", command=results.yview)
        results.configure(yscrollcommand=rsb.set)
        rsb.pack(side="right", fill="y")
        results.pack(side="left", fill="both", expand=True)

        res_status = ttk.Label(win, text="Search by stock code, brand or model.", padding=(10, 4))
        res_status.pack(anchor="w")

        # --- Basket ---
        ttk.Label(
            win, text="Basket", font=("Segoe UI", 12, "bold")
        ).pack(anchor="w", padx=10)
        bframe = ttk.Frame(win, padding=(10, 0))
        bframe.pack(fill="both", expand=True)
        basket_tree = ttk.Treeview(
            bframe, columns=("product", "qty", "cost", "vat", "total"),
            show="headings", height=5,
        )
        for col, heading, width, anchor in [
            ("product", "Product", 300, "w"), ("qty", "Qty", 50, "e"),
            ("cost", "Unit Cost", 90, "e"), ("vat", "VAT", 60, "e"),
            ("total", "Line Total", 100, "e"),
        ]:
            basket_tree.heading(col, text=heading)
            basket_tree.column(col, width=width, anchor=anchor)
        bsb = ttk.Scrollbar(bframe, orient="vertical", command=basket_tree.yview)
        basket_tree.configure(yscrollcommand=bsb.set)
        bsb.pack(side="right", fill="y")
        basket_tree.pack(side="left", fill="both", expand=True)

        foot = ttk.Frame(win, padding=10)
        foot.pack(fill="x")
        ttk.Button(foot, text="Remove", command=lambda: remove_basket()).pack(side="left")
        total_lbl = ttk.Label(
            foot, text="Net 0.00   VAT 0.00   Gross 0.00", font=("Segoe UI", 10, "bold")
        )
        total_lbl.pack(side="left", padx=(12, 0))
        ttk.Button(foot, text="Submit to Purchase", command=lambda: submit()).pack(side="right")
        ttk.Button(foot, text="Cancel", command=win.destroy).pack(side="right", padx=(0, 8))

        def size_prefix():
            # Leading digits of the stock-code box, e.g. "2055516V" -> "2055516".
            digits = ""
            for ch in stock_var.get().strip():
                if ch.isdigit():
                    digits += ch
                else:
                    break
            return digits if len(digits) >= 3 else ""

        def refresh_models():
            # Keep the model list to just this brand + size, so it stays manageable.
            model_combo.set_completion_list(
                product_db.get_models(
                    brand=brand_var.get().strip(), size_prefix=size_prefix()
                )
            )

        def on_stock_return():
            # Empty box + items already in the basket = submit; otherwise search.
            if not stock_var.get().strip() and basket:
                submit()
            else:
                do_search()

        def do_search():
            refresh_models()
            results.delete(*results.get_children())
            result_map.clear()
            rows, total = product_db.search_products_adv(
                stock_code=stock_var.get().strip(),
                brand=brand_var.get().strip(),
                model=model_var.get().strip(),
                limit=200,
            )
            for r in rows:
                results.insert(
                    "", "end", iid=str(r["id"]),
                    values=(r["stock_code"], r["description"], r["brand"], r["model"]),
                )
                result_map[str(r["id"])] = r
            children = results.get_children()
            if children:
                first = children[0]
                results.focus_set()
                results.selection_set(first)
                results.focus(first)
                results.see(first)
                more = f" of {total:,}" if total > len(children) else ""
                res_status.config(text=f"Showing {len(children):,}{more} — Enter to add a row.")
            else:
                res_status.config(text="No products found.")

        def clear():
            stock_var.set("")
            brand_var.set("")
            model_var.set("")
            results.delete(*results.get_children())
            result_map.clear()
            refresh_models()
            res_status.config(text="Search by stock code, brand or model.")
            stock_entry.focus_set()

        def add_selected():
            selection = results.selection()
            if not selection:
                return
            product = result_map.get(selection[0])
            if not product:
                return
            label = f"{product['stock_code']} — {product['description']}"
            qc = self.ask_quantity_cost(win, label)
            if qc is None:
                return
            quantity, cost, vat_rate = qc
            basket.append({
                "product_id": product["id"], "label": label,
                "quantity": quantity, "cost_price": cost, "vat_rate": vat_rate,
            })
            refresh_basket()
            # Ready for the next product: clear the search and focus the stock box.
            clear()

        results.bind("<Return>", lambda e: add_selected())
        results.bind("<Double-1>", lambda e: add_selected())

        def remove_basket():
            selection = basket_tree.selection()
            if not selection:
                return
            del basket[int(selection[0])]
            refresh_basket()

        def refresh_basket():
            basket_tree.delete(*basket_tree.get_children())
            net_total = vat_total = gross_total = 0.0
            for index, it in enumerate(basket):
                net = it["quantity"] * it["cost_price"]
                vat = net * it["vat_rate"] / 100.0
                gross = net + vat
                net_total += net
                vat_total += vat
                gross_total += gross
                basket_tree.insert(
                    "", "end", iid=str(index),
                    values=(it["label"], it["quantity"], f"{it['cost_price']:.2f}",
                            f"{it['vat_rate']:.0f}%", f"{gross:,.2f}"),
                )
            total_lbl.config(
                text=f"Net {net_total:,.2f}   VAT {vat_total:,.2f}   Gross {gross_total:,.2f}"
            )

        def submit():
            if not basket:
                messagebox.showinfo("Empty basket", "Add at least one product first.", parent=win)
                return
            on_submit(list(basket))
            win.destroy()

        stock_entry.focus_set()

    def ask_quantity_cost(self, parent, product_label):
        """Modal dialog returning (quantity, net_unit_cost, vat_rate) or None."""
        dialog = tk.Toplevel(parent)
        dialog.title("Quantity & Unit Cost")
        dialog.transient(parent)
        dialog.grab_set()
        result = {"value": None}

        ttk.Label(dialog, text=product_label, wraplength=380, padding=10).pack(anchor="w")
        form = ttk.Frame(dialog, padding=(10, 0))
        form.pack(anchor="w")
        qty_var = tk.StringVar()
        cost_var = tk.StringVar()
        vat_var = tk.StringVar(value=VAT_RATE_OPTIONS[0][0])

        ttk.Label(form, text="Quantity:").grid(row=0, column=0, sticky="w", pady=4, padx=(0, 8))
        qty_entry = ttk.Entry(form, textvariable=qty_var, width=14)
        qty_entry.grid(row=0, column=1, pady=4)
        ttk.Label(form, text="Unit Cost (net):").grid(row=1, column=0, sticky="w", pady=4, padx=(0, 8))
        ttk.Entry(form, textvariable=cost_var, width=14).grid(row=1, column=1, pady=4)
        ttk.Label(form, text="VAT:").grid(row=2, column=0, sticky="w", pady=4, padx=(0, 8))
        vat_combo = ttk.Combobox(
            form, state="readonly", width=14, textvariable=vat_var,
            values=[label for label, _ in VAT_RATE_OPTIONS],
        )
        vat_combo.grid(row=2, column=1, pady=4)
        vat_combo.current(0)

        gross_label = ttk.Label(form, text="")
        gross_label.grid(row=3, column=0, columnspan=2, sticky="w", pady=(6, 0))

        rate_by_label = dict(VAT_RATE_OPTIONS)

        def preview(*_):
            try:
                gross = int(qty_var.get()) * float(cost_var.get()) * (
                    1 + rate_by_label[vat_var.get()] / 100.0
                )
                gross_label.config(text=f"Line total (inc VAT): {gross:,.2f}")
            except (ValueError, KeyError):
                gross_label.config(text="")

        qty_var.trace_add("write", preview)
        cost_var.trace_add("write", preview)
        vat_combo.bind("<<ComboboxSelected>>", preview)

        def ok():
            try:
                quantity = int(qty_var.get())
                cost = float(cost_var.get())
            except ValueError:
                messagebox.showwarning(
                    "Invalid", "Enter a whole-number quantity and a numeric unit cost.",
                    parent=dialog,
                )
                return
            if quantity <= 0:
                messagebox.showwarning("Invalid", "Quantity must be greater than zero.", parent=dialog)
                return
            result["value"] = (quantity, cost, rate_by_label[vat_var.get()])
            dialog.destroy()

        btns = ttk.Frame(dialog, padding=10)
        btns.pack(anchor="e")
        ttk.Button(btns, text="Add", command=ok).pack(side="left")
        ttk.Button(btns, text="Cancel", command=dialog.destroy).pack(side="left", padx=(8, 0))
        dialog.bind("<Return>", lambda e: ok())
        qty_entry.focus_set()
        parent.wait_window(dialog)
        return result["value"]

    # ------------------------------------------------------------------- Payments

    def show_payments(self, supplier_id):
        self.current_view = "payments"
        self._clear_container()
        supplier = db.get_supplier(supplier_id)

        header = ttk.Frame(self.container)
        header.pack(fill="x", pady=(0, 10))
        ttk.Label(
            header, text=f"Payments — {supplier['name']}",
            font=("Segoe UI", 20, "bold"),
        ).pack(side="left")
        ttk.Button(
            header, text="Make Payment",
            command=lambda: self.show_payment_form(supplier_id),
        ).pack(side="right")

        balance = payment_db.supplier_balance(supplier_id)
        ttk.Label(
            self.container, text=f"Balance owed: {balance:,.2f}",
            font=("Segoe UI", 12, "bold"),
        ).pack(anchor="w", pady=(0, 8))

        columns = ("date", "account", "method", "amount", "invoices")
        headings = ("Date", "Account", "Method", "Amount", "Invoices")
        widths = (110, 180, 80, 100, 240)
        table_frame = ttk.Frame(self.container)
        table_frame.pack(fill="both", expand=True)
        tree = ttk.Treeview(table_frame, columns=columns, show="headings")
        sb = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        tree.pack(side="left", fill="both", expand=True)
        for col, heading, width in zip(columns, headings, widths):
            tree.heading(col, text=heading)
            tree.column(col, width=width)
        tree.column("amount", anchor="e")

        rows = payment_db.get_payments(supplier_id)
        for r in rows:
            tree.insert(
                "", "end",
                values=(
                    r["date"] or "", f"{r['account_code']} - {r['account_name']}",
                    r["method"] or "", f"{r['amount']:,.2f}", r["invoices"] or "",
                ),
            )
        ttk.Label(
            self.container,
            text=f"{len(rows)} payment(s)." if rows else "No payments yet.",
        ).pack(anchor="w", pady=(8, 0))
        ttk.Button(
            self.container, text="Back to Supplier",
            command=lambda: self.show_supplier_form(db.get_supplier(supplier_id)),
        ).pack(anchor="w", pady=(12, 0))

    def show_payment_form(self, supplier_id):
        self.current_view = "payment_form"
        self._clear_container()
        supplier = db.get_supplier(supplier_id)

        ttk.Label(
            self.container, text=f"Make Payment — {supplier['name']}",
            font=("Segoe UI", 20, "bold"),
        ).pack(anchor="w", pady=(0, 12))

        accounts = nominals.get_all()
        account_by_label = {nominals.label(a): a["id"] for a in accounts}

        head = ttk.Frame(self.container)
        head.pack(anchor="w")
        account_var = tk.StringVar()
        method_var = tk.StringVar(value=payment_db.METHODS[0])
        date_var = tk.StringVar(value=datetime.date.today().strftime("%d/%m/%y"))

        ttk.Label(head, text="From account:").grid(row=0, column=0, sticky="w", pady=4, padx=(0, 10))
        account_combo = ttk.Combobox(
            head, state="readonly", width=30, textvariable=account_var,
            values=list(account_by_label.keys()),
        )
        account_combo.grid(row=0, column=1, sticky="w", pady=4)
        if account_by_label:
            account_combo.current(0)

        ttk.Label(head, text="Method:").grid(row=1, column=0, sticky="w", pady=4, padx=(0, 10))
        method_combo = ttk.Combobox(
            head, state="readonly", width=15, textvariable=method_var,
            values=list(payment_db.METHODS),
        )
        method_combo.grid(row=1, column=1, sticky="w", pady=4)
        method_combo.current(0)

        ttk.Label(head, text="Date:").grid(row=2, column=0, sticky="w", pady=4, padx=(0, 10))
        ttk.Entry(head, textvariable=date_var, width=20).grid(row=2, column=1, sticky="w", pady=4)

        ttk.Label(
            self.container, text="Allocate to invoices",
            font=("Segoe UI", 12, "bold"),
        ).pack(anchor="w", pady=(15, 5))

        invoices = purchase_db.supplier_invoices(supplier_id, outstanding_only=True)
        alloc_vars = {}            # purchase_id -> StringVar
        outstanding_by_id = {}     # purchase_id -> outstanding amount

        if not invoices:
            ttk.Label(
                self.container,
                text="No outstanding invoices for this supplier.",
            ).pack(anchor="w")
        else:
            grid = ttk.Frame(self.container)
            grid.pack(anchor="w")
            for col, text in enumerate(["Reference", "Date", "Total", "Outstanding", "Pay"]):
                ttk.Label(grid, text=text, font=("Segoe UI", 9, "bold")).grid(
                    row=0, column=col, sticky="w", padx=(0, 12), pady=(0, 4)
                )
            for i, inv in enumerate(invoices, start=1):
                outstanding_by_id[inv["id"]] = inv["outstanding"]
                ttk.Label(grid, text=inv["reference"] or "").grid(row=i, column=0, sticky="w", padx=(0, 12))
                ttk.Label(grid, text=inv["date"] or "").grid(row=i, column=1, sticky="w", padx=(0, 12))
                ttk.Label(grid, text=f"{inv['total']:,.2f}").grid(row=i, column=2, sticky="e", padx=(0, 12))
                ttk.Label(grid, text=f"{inv['outstanding']:,.2f}").grid(row=i, column=3, sticky="e", padx=(0, 12))
                var = tk.StringVar()
                ttk.Entry(grid, textvariable=var, width=10).grid(row=i, column=4, sticky="w")
                alloc_vars[inv["id"]] = var

        total_label = ttk.Label(
            self.container, text="Payment total: 0.00", font=("Segoe UI", 10, "bold")
        )
        total_label.pack(anchor="w", pady=(10, 0))

        def recompute(*_):
            running = 0.0
            for var in alloc_vars.values():
                try:
                    running += float(var.get() or 0)
                except ValueError:
                    pass
            total_label.config(text=f"Payment total: {running:,.2f}")

        for var in alloc_vars.values():
            var.trace_add("write", recompute)

        def save():
            allocations = []
            for purchase_id, var in alloc_vars.items():
                raw = var.get().strip()
                if not raw:
                    continue
                try:
                    amount = float(raw)
                except ValueError:
                    messagebox.showwarning("Invalid amount", "Enter numeric amounts only.")
                    return
                if amount <= 0:
                    continue
                if amount - outstanding_by_id[purchase_id] > 0.005:
                    messagebox.showwarning(
                        "Too much", "An allocation exceeds the invoice's outstanding amount."
                    )
                    return
                allocations.append({"purchase_id": purchase_id, "amount": round(amount, 2)})
            if not allocations:
                messagebox.showwarning(
                    "Nothing to pay", "Enter an amount against at least one invoice."
                )
                return
            account_id = account_by_label.get(account_var.get())
            if account_id is None:
                messagebox.showwarning("Account", "Choose an account to pay from.")
                return
            payment_db.create_payment(
                supplier_id, account_id, method_var.get(),
                date_var.get().strip(), allocations,
            )
            messagebox.showinfo("Saved", "Payment recorded.")
            self.show_payments(supplier_id)

        btns = ttk.Frame(self.container)
        btns.pack(anchor="w", pady=(15, 0))
        ttk.Button(btns, text="Save Payment", command=save).pack(side="left")
        ttk.Button(
            btns, text="Cancel", command=lambda: self.show_payments(supplier_id)
        ).pack(side="left", padx=(8, 0))

    # ------------------------------------------------------------------- Services

    def show_services(self):
        self.current_view = "services"
        self._clear_container()

        header = ttk.Frame(self.container)
        header.pack(fill="x", pady=(0, 10))
        ttk.Label(
            header, text="Services", font=("Segoe UI", 20, "bold")
        ).pack(side="left")

        bar = ttk.Frame(self.container)
        bar.pack(fill="x", pady=(0, 10))
        bar.columnconfigure(1, weight=1)
        search_term = tk.StringVar()
        ttk.Label(bar, text="Search:").grid(row=0, column=0, sticky="w")
        search_entry = ttk.Entry(bar, textvariable=search_term)
        search_entry.grid(row=0, column=1, sticky="ew", padx=(8, 10))
        search_entry.focus_set()
        search_entry.bind("<Return>", lambda e: do_search())
        ttk.Button(bar, text="Search", command=lambda: do_search()).grid(row=0, column=2, padx=(0, 8))
        ttk.Button(bar, text="Clear", command=lambda: clear()).grid(row=0, column=3)

        columns = ("service_code", "service_name", "cost", "retail_price")
        headings = ("Service Code", "Service Name", "Cost", "Retail Price")
        widths = (160, 300, 110, 110)
        table_frame = ttk.Frame(self.container)
        table_frame.pack(fill="both", expand=True)
        tree = ttk.Treeview(table_frame, columns=columns, show="headings")
        sb = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        tree.pack(side="left", fill="both", expand=True)
        for col, heading, width in zip(columns, headings, widths):
            tree.heading(col, text=heading)
            tree.column(col, width=width)
        tree.column("cost", anchor="e")
        tree.column("retail_price", anchor="e")

        status_label = ttk.Label(self.container, text="")
        status_label.pack(anchor="w", pady=(8, 0))

        def refresh():
            rows = service_db.list_services(text=search_term.get().strip())
            tree.delete(*tree.get_children())
            for r in rows:
                tree.insert(
                    "", "end", iid=str(r["id"]),
                    values=(
                        r["service_code"] or "", r["service_name"],
                        f"{(r['cost'] or 0):,.2f}", f"{(r['retail_price'] or 0):,.2f}",
                    ),
                )
            status_label.config(
                text=f"{len(rows)} service(s)." if rows
                else "No services yet. Use Services → New Service to add one."
            )

        def clear():
            search_term.set("")
            refresh()
            search_entry.focus_set()

        def do_search():
            refresh()
            children = tree.get_children()
            if children:
                first = children[0]
                tree.focus_set()
                tree.selection_set(first)
                tree.focus(first)
                tree.see(first)

        def open_selected():
            selection = tree.selection()
            if not selection:
                messagebox.showinfo("No selection", "Please select a service first.")
                return
            self.show_service_form(service_db.get_service(int(selection[0])))

        tree.bind("<Double-1>", lambda e: open_selected())
        tree.bind("<Return>", lambda e: open_selected())
        refresh()

    def show_service_form(self, service=None):
        """Create/edit a service (code, name, cost, retail price)."""
        self.current_view = "service_form"
        self._clear_container()
        editing = service is not None
        ttk.Label(
            self.container,
            text="Edit Service" if editing else "New Service",
            font=("Segoe UI", 20, "bold"),
        ).pack(anchor="w", pady=(0, 15))

        form = ttk.Frame(self.container)
        form.pack(anchor="w")
        fields = [
            ("service_code", "Service Code"),
            ("service_name", "Service Name"),
            ("cost", "Cost"),
            ("retail_price", "Retail Price"),
        ]
        entries = {}
        for row, (key, label) in enumerate(fields):
            ttk.Label(form, text=label + ":").grid(row=row, column=0, sticky="w", pady=5, padx=(0, 10))
            entry = ttk.Entry(form, width=40)
            entry.grid(row=row, column=1, pady=5)
            if editing:
                value = service[key]
                if key in ("cost", "retail_price"):
                    entry.insert(0, f"{(value or 0):.2f}")
                else:
                    entry.insert(0, value or "")
            entries[key] = entry

        def save():
            data = {key: entry.get().strip() for key, entry in entries.items()}
            if not data["service_name"]:
                messagebox.showwarning("Missing name", "Please enter a service name.")
                return
            try:
                cost = float(data["cost"]) if data["cost"] else 0.0
                retail = float(data["retail_price"]) if data["retail_price"] else 0.0
            except ValueError:
                messagebox.showwarning("Invalid", "Cost and Retail Price must be numbers.")
                return
            try:
                if editing:
                    service_db.update_service(
                        service["id"], data["service_code"], data["service_name"], cost, retail
                    )
                else:
                    service_db.create_service(
                        data["service_code"], data["service_name"], cost, retail
                    )
            except service_db.DuplicateCodeError:
                messagebox.showerror(
                    "Duplicate code",
                    f"A service with code '{data['service_code']}' already exists.",
                )
                return
            messagebox.showinfo("Saved", f"Service '{data['service_name']}' saved.")
            self.show_services()

        def delete_current():
            if not editing:
                return
            if messagebox.askyesno("Delete service", f"Delete '{service['service_name']}'?"):
                service_db.delete_service(service["id"])
                self.show_services()

        btns = ttk.Frame(self.container)
        btns.pack(anchor="w", pady=(20, 0))
        ttk.Button(btns, text="Save", command=save).pack(side="left")
        ttk.Button(btns, text="Cancel", command=self.show_services).pack(side="left", padx=(8, 0))
        if editing:
            ttk.Button(btns, text="Delete", command=delete_current).pack(side="left", padx=(8, 0))


if __name__ == "__main__":
    App().mainloop()
