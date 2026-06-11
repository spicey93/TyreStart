"""Product screens (mixin for App)."""
import tkinter as tk
from tkinter import ttk, messagebox

from core import products as product_db
from core import pricing as pricing_db

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
            font=("Segoe UI", 20, "bold"),
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
            ("pricing_key", "Pricing Key"),
            ("product_group", "Product Group"),
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
            "manufacturer code. Pricing Key and Product Group are used by pricing rules.",
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

        cancel = self._discard_guard(self.show_products)
        btns = ttk.Frame(self.container)
        btns.pack(anchor="w", pady=(15, 0))
        ttk.Button(btns, text="Save (Ctrl+S)", command=save).pack(side="left")
        ttk.Button(btns, text="Cancel (Esc)", command=cancel).pack(side="left", padx=(8, 0))
        self._bind_form_shortcuts(save=save, cancel=cancel)
