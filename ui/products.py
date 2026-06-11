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
            action = self.ask_product_action(allow_edit=True)
            if action == "view":
                self.show_product_detail(product_id)
            elif action == "edit":
                self.show_product_form(product_db.get_product(product_id))
            elif action == "sale":
                self.show_sale_form(prefill_product=product_db.get_product(product_id))

        # Double-clicking or pressing Enter on a row asks what to do with it.
        tree.bind("<Double-1>", lambda e: activate_selected())
        tree.bind("<Return>", lambda e: activate_selected())

        refresh_tree()

    def show_product_detail(self, product_id):
        """Read-only detail view for a single product.

        Mirrors the New Product form's layout — same two-column Product Details
        panel — but every field is a read-only input. A second Stock & Pricing
        panel shows the derived figures (stock, average cost, price) and the
        import/sync metadata."""
        self.current_view = "product_detail"
        self._clear_container()

        product = product_db.get_product(product_id)
        if product is None:
            messagebox.showerror("Not found", "That product no longer exists.")
            self.show_products()
            return

        body = self._scrollable_body()
        ttk.Label(
            body,
            text=product["description"] or "Product",
            font=("Consolas", 20, "bold"),
        ).pack(anchor="w", pady=(0, 15))

        def panel(title):
            frame = ttk.LabelFrame(body, text=title, padding=12)
            frame.pack(anchor="w", fill="x", pady=(0, 12))
            frame.columnconfigure(1, weight=1)
            frame.columnconfigure(3, weight=1)
            return frame

        def label(parent, text, row, col):
            pad = (30, 10) if col == 2 else (0, 10)
            ttk.Label(parent, text=text + ":").grid(
                row=row, column=col, sticky="w", pady=5, padx=pad)

        def ro(parent, value, row, col, width=24, span=1):
            var = tk.StringVar(value="" if value is None else str(value))
            entry = ttk.Entry(parent, textvariable=var, state="readonly", width=width)
            entry._keep_var = var  # keep a ref so the StringVar isn't GC'd (blanks the box)
            entry.grid(row=row, column=col, columnspan=span,
                       sticky="ew" if span > 1 else "w", pady=5)

        # --- Product Details: same layout as the New Product form ------------
        details = panel("Product Details")
        label(details, "Description", 0, 0)
        ro(details, product["description"], 0, 1, span=3)

        label(details, "Size (W/A/R)", 1, 0)
        size_cell = ttk.Frame(details)
        size_cell.grid(row=1, column=1, columnspan=3, sticky="w", pady=5)
        for part in ("width", "aspect_ratio", "rim"):
            v = tk.StringVar(value=product[part] or "")
            size_entry = ttk.Entry(size_cell, textvariable=v, state="readonly", width=6)
            size_entry._keep_var = v  # keep a ref so the StringVar isn't GC'd
            size_entry.pack(side="left", padx=(0, 6))

        # Left column
        label(details, "Brand", 2, 0);             ro(details, product["brand"], 2, 1)
        label(details, "Model", 3, 0);             ro(details, product["model"], 3, 1)
        label(details, "Product Type", 4, 0);      ro(details, product["product_type"], 4, 1)
        label(details, "Vehicle Type", 5, 0);      ro(details, product["vehicle_type"], 5, 1)
        label(details, "EAN", 6, 0);               ro(details, product["ean"], 6, 1)
        label(details, "Manufacturer Code", 7, 0); ro(details, product["manufacturer_code"], 7, 1)

        # Right column
        label(details, "Rolling Resistance", 2, 2); ro(details, product["rolling_resistance"], 2, 3)
        label(details, "Wet Grip", 3, 2);           ro(details, product["wet_grip"], 3, 3)
        label(details, "Noise Class", 4, 2);        ro(details, product["noise_class"], 4, 3)
        label(details, "Noise Performance", 5, 2);  ro(details, product["noise_performance"], 5, 3)
        label(details, "Vehicle Class", 6, 2);      ro(details, product["vehicle_class"], 6, 3)
        label(details, "Pricing Key", 7, 2);        ro(details, product["pricing_key"], 7, 3)
        label(details, "Product Group", 8, 2);      ro(details, product["product_group"], 8, 3)

        # --- Stock & Pricing: derived figures + import metadata --------------
        price = pricing_db.price_for_product(product["id"])
        stock = panel("Stock & Pricing")
        label(stock, "Stock Code", 0, 0); ro(stock, product["stock_code"], 0, 1)
        label(stock, "Stock", 1, 0);      ro(stock, product_db.product_stock(product["id"]), 1, 1)
        label(stock, "Avg Cost", 2, 0);   ro(stock, f"{product_db.average_cost(product['id']):,.2f}", 2, 1)
        label(stock, "Price", 3, 0)
        ro(stock, f"{price:,.2f}" if price is not None else "— (no matching rule)", 3, 1)
        label(stock, "Sync Status", 0, 2); ro(stock, product["sync_status"], 0, 3)
        label(stock, "Created", 1, 2);     ro(stock, product["created_date"], 1, 3)
        label(stock, "Updated", 2, 2);     ro(stock, product["updated_date"], 2, 3)

        actions = ttk.Frame(body)
        actions.pack(anchor="w", pady=(8, 0))
        ttk.Button(actions, text="Edit Product",
                   command=lambda: self.show_product_form(product)).pack(side="left")
        ttk.Button(actions, text="Back to Products",
                   command=self.show_products).pack(side="left", padx=(8, 0))

    # Fixed-choice dropdowns (EU tyre-label ratings + standard tyre sizes). The
    # add-able pickers (brand/model/product type/vehicle type) get their values
    # from the database instead.
    _RATING = ["", "A", "B", "C", "D", "E", "F", "G"]   # rolling resistance, wet grip
    _NOISE_CLASS = ["", "A", "B", "C"]                  # noise class (letter)
    _NOISE_DB = [""] + [str(n) for n in range(65, 81)]  # measured noise, dB
    _VEHICLE_CLASS = ["", "C1", "C2", "C3"]             # EU vehicle class
    _WIDTHS = [""] + [str(w) for w in range(125, 356, 10)]
    _ASPECTS = [""] + [str(a) for a in range(25, 86, 5)]
    _RIMS = [""] + [str(r) for r in range(10, 25)]

    def show_product_form(self, product=None):
        """Create a new product, or edit `product` when one is given. One method
        serves both: the title switches between New / Edit and the fields pre-fill
        when editing.

        Two-column layout: identity/classification on the left, the EU tyre-label
        ratings on the right. Description is forced upper-case; Brand / Model /
        Product Type / Vehicle Type / Product Group are dropdowns with a "+" to add
        a new option."""
        editing = product is not None
        self.current_view = "product_form"
        self._clear_container()
        body = self._scrollable_body()
        ttk.Label(
            body,
            text="Edit Product" if editing else "New Product",
            font=("Consolas", 20, "bold"),
        ).pack(anchor="w", pady=(0, 15))

        form = ttk.LabelFrame(body, text="Product Details", padding=12)
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

        # Size: three inline dropdowns. Left blank, they're derived from the
        # description; set, they drive the stock code directly.
        label("Size (W/A/R)", 1, 0)
        size_cell = ttk.Frame(form)
        size_cell.grid(row=1, column=1, columnspan=3, sticky="w", pady=5)
        for key, values in (("width", self._WIDTHS),
                            ("aspect_ratio", self._ASPECTS),
                            ("rim", self._RIMS)):
            var = variables[key] = tk.StringVar()
            ttk.Combobox(size_cell, textvariable=var, state="readonly",
                         values=values, width=6).pack(side="left", padx=(0, 6))

        # Left column: identity & classification.
        label("Brand", 2, 0);             addable("brand", "Brand", 2, 1)
        label("Model", 3, 0);             addable("model", "Model", 3, 1)
        label("Product Type", 4, 0);      addable("product_type", "Product Type", 4, 1)
        label("Vehicle Type", 5, 0);      addable("vehicle_type", "Vehicle Type", 5, 1)
        label("EAN", 6, 0);               entry("ean", 6, 1)
        label("Manufacturer Code", 7, 0); entry("manufacturer_code", 7, 1)

        # Right column: EU tyre-label ratings, then pricing classification.
        label("Rolling Resistance", 2, 2); choice("rolling_resistance", 2, 3, self._RATING)
        label("Wet Grip", 3, 2);           choice("wet_grip", 3, 3, self._RATING)
        label("Noise Class", 4, 2);        choice("noise_class", 4, 3, self._NOISE_CLASS)
        label("Noise Performance", 5, 2);  choice("noise_performance", 5, 3, self._NOISE_DB)
        label("Vehicle Class", 6, 2);      choice("vehicle_class", 6, 3, self._VEHICLE_CLASS)
        label("Pricing Key", 7, 2);        entry("pricing_key", 7, 3)
        label("Product Group", 8, 2);      addable("product_group", "Product Group", 8, 3)

        # When editing, pre-fill every field from the record. Setting StringVars
        # programmatically doesn't mark the form dirty, so it opens clean.
        if editing:
            for key, var in variables.items():
                var.set(product[key] or "")

        def save():
            data = {key: var.get().strip() for key, var in variables.items()}
            if not data["description"]:
                messagebox.showwarning("Missing description", "Please enter a description.")
                return None
            if editing:
                return product_db.update_product(product["id"], **data)
            return product_db.create_product(**data)

        # Cancelling/leaving returns to the product's detail when editing, else the list.
        back = ((lambda: self.show_product_detail(product["id"]))
                if editing else self.show_products)
        self._register_form(save=save, back=back)
