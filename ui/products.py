"""Product screens (mixin for App)."""
import tkinter as tk
from tkinter import ttk
from ui import dialogs as messagebox

from core import products as product_db
from core import pricing as pricing_db
from core import lookups as lookups_db

from ui.common import AutocompleteCombobox, make_sortable


class ProductsMixin:
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
            font=("Consolas", 20, "bold"),
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
        brand_combo.bind("<<ComboboxSelected>>", lambda e: do_search())
        brand_combo.bind("<Return>", lambda e: do_search())

        ttk.Label(search_frame, text="In stock:").grid(row=0, column=4, sticky="w")
        instock_combo = ttk.Combobox(
            search_frame, state="readonly", width=6, textvariable=instock_choice,
            values=["Yes", "No", "All"],
        )
        instock_combo.grid(row=0, column=5, sticky="w", padx=(8, 10))
        instock_combo.current(0)
        instock_combo.bind("<<ComboboxSelected>>", lambda e: do_search())

        SEARCH_BTN_COL, CLEAR_BTN_COL = 6, 7

        def populate(rows, total):
            tree.delete(*tree.get_children())
            rules = pricing_db.list_rules()  # fetched once; price computed per row
            for p in rows:
                price = pricing_db.price_from_rules(
                    p["avg_cost"], p["pricing_key"] or "", p["product_group"] or "",
                    rules=rules,
                )
                tree.insert(
                    "",
                    "end",
                    iid=str(p["id"]),
                    values=(
                        p["stock_code"], p["description"], p["brand"], p["stock"],
                        f"{price:,.2f}" if price is not None else "—",
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
            in_stock = instock_choice.get().lower()
            # Don't show anything until the user applies a filter. A stock filter
            # of Yes/No counts as a filter; only "All" with no text/brand does not.
            if not text and not brand and in_stock == "all":
                tree.delete(*tree.get_children())
                status_label.config(
                    text="Enter a search term, choose a brand, or set an In stock filter."
                )
                return
            rows, total = product_db.query_products(
                text=text, brand=brand, in_stock=in_stock,
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
            "stock_code", "description", "brand", "stock", "price",
            "rolling_resistance", "wet_grip", "noise_class", "noise_performance",
            "vehicle_type",
        )
        headings = (
            "Stock Code", "Description", "Brand", "Stock", "Price",
            "Rolling Resistance", "Wet Grip", "Noise Class", "Noise Performance",
            "Vehicle Type",
        )
        widths = (120, 230, 100, 60, 80, 120, 80, 90, 120, 90)

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
        tree.column("stock", anchor="e")
        tree.column("price", anchor="e")
        make_sortable(tree)

        status_label = ttk.Label(self.container, text="")
        status_label.pack(anchor="w", pady=(8, 0))

        def activate_selected():
            selection = tree.selection()
            if not selection:
                messagebox.showinfo("No selection", "Please select a product first.")
                return
            product_id = int(selection[0])
            action = self.ask_product_action()
            if action == "view":
                self.show_product_detail(product_id)
            elif action == "sale":
                self.show_sale_form(prefill_product=product_db.get_product(product_id))

        # Double-clicking or pressing Enter on a row asks what to do with it.
        tree.bind("<Double-1>", lambda e: activate_selected())
        tree.bind("<Return>", lambda e: activate_selected())

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
            font=("Consolas", 20, "bold"),
        ).pack(anchor="w", pady=(0, 15))

        detail = ttk.Frame(self.container)
        detail.pack(anchor="w")
        fields = [
            ("Stock Code", "stock_code"),
            ("Stock", "__stock__"),
            ("Avg Cost", "__avg_cost__"),
            ("Price", "__price__"),
            ("Pricing Key", "pricing_key"),
            ("Product Group", "product_group"),
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
            elif key == "__avg_cost__":
                value = f"{product_db.average_cost(product['id']):,.2f}"
            elif key == "__price__":
                price = pricing_db.price_for_product(product["id"])
                value = f"{price:,.2f}" if price is not None else "— (no matching rule)"
            else:
                value = str(product[key] or "—")
            ttk.Label(detail, text=label + ":", font=("Consolas", 9, "bold")).grid(
                row=row, column=0, sticky="w", padx=(0, 12), pady=2
            )
            ttk.Label(detail, text=value).grid(row=row, column=1, sticky="w", pady=2)

        ttk.Button(
            self.container, text="Back to Products", command=self.show_products
        ).pack(anchor="w", pady=(20, 0))

    # Fixed-choice dropdowns (EU tyre-label ratings). The add-able pickers
    # (brand/model/product type/vehicle type) get their values from the database.
    _RATING_AE = ["", "A", "B", "C", "D", "E"]          # rolling resistance, wet grip
    _NOISE_CLASS = ["", "A", "B", "C"]                  # wave-bar noise class
    _NOISE_DB = [""] + [str(n) for n in range(65, 81)]  # measured noise, dB

    def show_product_form(self):
        """Create a new product. Stock code/size are derived from the description.

        Two-column layout: identity/classification on the left, the EU tyre-label
        ratings on the right. Description is forced upper-case; Brand / Model /
        Product Type / Vehicle Type are dropdowns with a "+" to add a new option."""
        self.current_view = "product_form"
        self._clear_container()
        ttk.Label(
            self.container, text="New Product", font=("Consolas", 20, "bold")
        ).pack(anchor="w", pady=(0, 15))

        form = ttk.LabelFrame(self.container, text="Product Details", padding=12)
        form.pack(anchor="w", fill="x")
        form.columnconfigure(1, weight=1)
        form.columnconfigure(3, weight=1)

        variables = {}

        def field_options(category):
            """Dropdown options for an add-able field: values already in the
            catalogue, plus any the user has added, de-duplicated."""
            values = set(product_db.get_distinct_values(category))
            values |= set(lookups_db.get_values(category))
            return [""] + sorted(values, key=str.lower)

        def add_lookup(category, var, combo, label_text):
            """"+" handler: prompt for a new option, persist it, then select it."""
            new = messagebox.askstring(
                f"New {label_text}", f"Enter a new {label_text.lower()}:")
            if not new:
                return
            try:
                lookups_db.add_value(category, new)
            except lookups_db.DuplicateValueError:
                pass  # already known — just select it
            combo["values"] = field_options(category)
            var.set(new)
            self.mark_form_dirty()

        def label(text, row, col):
            pad = (30, 10) if col == 2 else (0, 10)
            ttk.Label(form, text=text + ":").grid(
                row=row, column=col, sticky="w", pady=5, padx=pad)

        def entry(key, row, col, width=24):
            var = variables[key] = tk.StringVar()
            ttk.Entry(form, textvariable=var, width=width).grid(
                row=row, column=col, sticky="w", pady=5)

        def choice(key, row, col, values, width=22):
            var = variables[key] = tk.StringVar()
            ttk.Combobox(form, textvariable=var, state="readonly",
                         values=values, width=width).grid(
                row=row, column=col, sticky="w", pady=5)

        def addable(key, label_text, row, col):
            var = variables[key] = tk.StringVar()
            cell = ttk.Frame(form)
            cell.grid(row=row, column=col, sticky="w", pady=5)
            combo = ttk.Combobox(cell, textvariable=var, state="readonly",
                                 values=field_options(key), width=20)
            combo.pack(side="left")
            ttk.Button(cell, text="+", width=2,
                       command=lambda: add_lookup(key, var, combo, label_text)
                       ).pack(side="left", padx=(4, 0))

        # Description spans both columns; forced upper-case as you type.
        desc_var = variables["description"] = tk.StringVar()

        def force_upper(*_):
            current = desc_var.get()
            upper = current.upper()
            if current != upper:
                desc_var.set(upper)
        desc_var.trace_add("write", force_upper)
        label("Description", 0, 0)
        ttk.Entry(form, textvariable=desc_var).grid(
            row=0, column=1, columnspan=3, sticky="ew", pady=5)

        # Left column: identity & classification.
        label("Brand", 1, 0);             addable("brand", "Brand", 1, 1)
        label("Model", 2, 0);             addable("model", "Model", 2, 1)
        label("Product Type", 3, 0);      addable("product_type", "Product Type", 3, 1)
        label("Vehicle Type", 4, 0);      addable("vehicle_type", "Vehicle Type", 4, 1)
        label("EAN", 5, 0);               entry("ean", 5, 1)
        label("Manufacturer Code", 6, 0); entry("manufacturer_code", 6, 1)

        # Right column: EU tyre-label ratings, then pricing classification.
        label("Rolling Resistance", 1, 2); choice("rolling_resistance", 1, 3, self._RATING_AE)
        label("Wet Grip", 2, 2);           choice("wet_grip", 2, 3, self._RATING_AE)
        label("Noise Class", 3, 2);        choice("noise_class", 3, 3, self._NOISE_CLASS)
        label("Noise Performance", 4, 2);  choice("noise_performance", 4, 3, self._NOISE_DB)
        label("Vehicle Class", 5, 2);      entry("vehicle_class", 5, 3)
        label("Pricing Key", 6, 2);        entry("pricing_key", 6, 3)
        label("Product Group", 7, 2);      entry("product_group", 7, 3)

        def save():
            data = {key: var.get().strip() for key, var in variables.items()}
            if not data["description"]:
                messagebox.showwarning("Missing description", "Please enter a description.")
                return None
            return product_db.create_product(**data)

        self._register_form(save=save, back=self.show_products)
