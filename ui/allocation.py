"""Shared product-allocation dialogs (used by products, purchases, sales)."""
import tkinter as tk
from tkinter import ttk
from ui import dialogs as messagebox

from core import products as product_db
from core import money

from ui.common import AutocompleteCombobox, make_sortable, VAT_RATE_OPTIONS


class AllocationMixin:
    def open_product_allocation(self, on_submit, price_label="Unit Cost (net)",
                                price_fn=None, stock_filter=False, quick_add=False):
        """Modal window to search products and submit them to a sale/purchase.
        `on_submit` receives a list of line dicts
        (product_id, label, quantity, cost_price, vat_rate). `price_label` sets
        the wording of the per-line price field (cost for purchases, price for
        sales). `price_fn`, if given, is called with a product row to pre-fill the
        price field (used on sales to suggest the pricing-rule retail price).
        `stock_filter` swaps the Model picker for an In Stock filter (default Yes) —
        used on sales; purchases keep the Model picker. `quick_add` (sales) skips
        the basket and quantity dialog: selecting a product adds qty 1 at its rule
        price and closes the window immediately."""
        win = tk.Toplevel(self)
        win.title("Add Product" if quick_add else "Product Allocation")
        win.geometry("920x460" if quick_add else "920x620")
        win.transient(self)

        basket = []  # dicts: product_id, label, quantity, cost_price (unused if quick_add)
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

        in_stock_var = tk.StringVar(value="Yes")

        ttk.Label(search, text="Brand:").grid(row=0, column=2, sticky="w")
        brand_combo = AutocompleteCombobox(search, textvariable=brand_var, width=18)
        brand_combo.set_completion_list(product_db.get_brands())
        brand_combo.grid(row=0, column=3, padx=(6, 12))
        brand_combo.bind("<Return>", lambda e: do_search())

        if stock_filter:
            # Sales: filter by stock instead of model (default to in-stock only).
            ttk.Label(search, text="In Stock:").grid(row=0, column=4, sticky="w")
            in_stock_combo = ttk.Combobox(
                search, state="readonly", width=6, textvariable=in_stock_var,
                values=["Yes", "No", "All"],
            )
            in_stock_combo.grid(row=0, column=5, padx=(6, 12))
            in_stock_combo.current(0)
            in_stock_combo.bind("<<ComboboxSelected>>", lambda e: do_search())
            model_combo = None
        else:
            # Purchases: keep the brand-narrowed model picker. Bind both the
            # dropdown selection and typing (add="+" keeps the autocomplete handler).
            brand_combo.bind("<<ComboboxSelected>>", lambda e: refresh_models())
            brand_combo.bind("<KeyRelease>", lambda e: refresh_models(), add="+")
            ttk.Label(search, text="Model:").grid(row=0, column=4, sticky="w")
            model_combo = AutocompleteCombobox(search, textvariable=model_var, width=18)
            # Disabled until a brand is chosen; refresh_models() enables it.
            model_combo.configure(state="disabled")
            model_combo.grid(row=0, column=5, padx=(6, 12))
            model_combo.bind("<Return>", lambda e: do_search())
            # Re-narrow the model list as the size (stock-code box) changes.
            stock_entry.bind("<KeyRelease>", lambda e: refresh_models())

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
        make_sortable(results)
        rsb = ttk.Scrollbar(res_frame, orient="vertical", command=results.yview)
        results.configure(yscrollcommand=rsb.set)
        rsb.pack(side="right", fill="y")
        results.pack(side="left", fill="both", expand=True)

        default_status = (
            "Search and select a product to add it to the sale."
            if quick_add else "Search by stock code, brand or model."
        )
        res_status = ttk.Label(win, text=default_status, padding=(10, 4))
        res_status.pack(anchor="w")

        basket_tree = total_lbl = None
        if quick_add:
            # No basket: a single Close button; selecting a product adds & closes.
            foot = ttk.Frame(win, padding=10)
            foot.pack(fill="x")
            ttk.Button(foot, text="Close", command=win.destroy).pack(side="right")
        else:
            # --- Basket ---
            ttk.Label(
                win, text="Basket", font=("Consolas", 12, "bold")
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
            make_sortable(basket_tree)
            bsb = ttk.Scrollbar(bframe, orient="vertical", command=basket_tree.yview)
            basket_tree.configure(yscrollcommand=bsb.set)
            bsb.pack(side="right", fill="y")
            basket_tree.pack(side="left", fill="both", expand=True)

            foot = ttk.Frame(win, padding=10)
            foot.pack(fill="x")
            ttk.Button(foot, text="Remove", command=lambda: remove_basket()).pack(side="left")
            total_lbl = ttk.Label(
                foot, text="Net 0.00   VAT 0.00   Gross 0.00", font=("Consolas", 10, "bold")
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
            # Only relevant in model mode (purchases); a no-op when the In Stock
            # filter has replaced the model picker.
            if model_combo is None:
                return
            # Model picker stays disabled until a brand is chosen; once it is, the
            # list is narrowed to that brand (and the size, if one's been typed).
            brand = brand_var.get().strip()
            if not brand:
                model_var.set("")
                model_combo.set_completion_list([])
                model_combo.configure(state="disabled")
                return
            model_combo.configure(state="normal")
            models = product_db.get_models(brand=brand, size_prefix=size_prefix())
            model_combo.set_completion_list(models)
            # Drop a stale model that the new brand/size no longer offers.
            if model_var.get().strip() and model_var.get().strip() not in models:
                model_var.set("")

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
                model="" if stock_filter else model_var.get().strip(),
                in_stock=in_stock_var.get().lower() if stock_filter else "",
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
                hint = "Enter to add to sale" if quick_add else "Enter to add a row"
                res_status.config(text=f"Showing {len(children):,}{more} — {hint}.")
            else:
                res_status.config(text="No products found.")

        def clear():
            stock_var.set("")
            brand_var.set("")
            model_var.set("")
            if stock_filter:
                in_stock_var.set("Yes")
            results.delete(*results.get_children())
            result_map.clear()
            refresh_models()
            res_status.config(text=default_status)
            stock_entry.focus_set()

        def add_selected():
            selection = results.selection()
            if not selection:
                return
            product = result_map.get(selection[0])
            if not product:
                return
            label = f"{product['stock_code']} — {product['description']}"
            if quick_add:
                # Add qty 1 at the rule price and return straight to the sale.
                on_submit([{
                    "product_id": product["id"], "label": label,
                    "stock_code": product["stock_code"],
                    "description": product["description"] or label,
                    "quantity": 1, "cost_price": price_fn(product) if price_fn else 0.0,
                    "vat_rate": VAT_RATE_OPTIONS[0][1],
                }])
                win.destroy()
                return
            default_cost = price_fn(product) if price_fn else None
            qc = self.ask_quantity_cost(win, label, price_label, default_cost=default_cost)
            if qc is None:
                return
            quantity, cost, vat_rate = qc
            basket.append({
                "product_id": product["id"], "label": label,
                "stock_code": product["stock_code"],
                "description": product["description"] or label,
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
                net, vat, gross = money.line_amounts(
                    it["quantity"], it["cost_price"], it["vat_rate"]
                )
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

    def ask_product_action(self, noun="product", allow_edit=False):
        """Ask whether to view the record, edit it, or start a sale for it.
        `noun` ("product"/"service") sets the wording; `allow_edit` adds an Edit
        button. Returns "view", "edit", "sale", or None if cancelled."""
        dialog = tk.Toplevel(self)
        dialog.title(noun.title())
        dialog.transient(self)
        dialog.grab_set()
        result = {"value": None}

        ttk.Label(
            dialog, text=f"What would you like to do with this {noun}?", padding=15
        ).pack(anchor="w")
        btns = ttk.Frame(dialog, padding=(15, 0, 15, 15))
        btns.pack(fill="x")

        def choose(value):
            result["value"] = value
            dialog.destroy()

        view_btn = ttk.Button(btns, text=f"View {noun.title()}", command=lambda: choose("view"))
        view_btn.pack(side="left")
        if allow_edit:
            ttk.Button(btns, text=f"Edit {noun.title()}",
                       command=lambda: choose("edit")).pack(side="left", padx=(8, 0))
        ttk.Button(btns, text="Create Sale", command=lambda: choose("sale")).pack(
            side="left", padx=(8, 0)
        )
        ttk.Button(btns, text="Cancel", command=dialog.destroy).pack(side="right")

        dialog.bind("<Escape>", lambda e: dialog.destroy())
        view_btn.focus_set()
        self.wait_window(dialog)
        return result["value"]

    def ask_quantity_cost(self, parent, product_label, price_label="Unit Cost (net)",
                          default_cost=None):
        """Modal dialog returning (quantity, net_unit_price, vat_rate) or None.
        `default_cost`, if given, pre-fills the price field (e.g. a pricing-rule
        retail price on sales) — still editable before adding."""
        dialog = tk.Toplevel(parent)
        dialog.title("Quantity & Unit Cost")
        dialog.transient(parent)
        dialog.grab_set()
        result = {"value": None}

        ttk.Label(dialog, text=product_label, wraplength=380, padding=10).pack(anchor="w")
        form = ttk.Frame(dialog, padding=(10, 0))
        form.pack(anchor="w")
        qty_var = tk.StringVar()
        cost_var = tk.StringVar(value=f"{default_cost:.2f}" if default_cost else "")
        vat_var = tk.StringVar(value=VAT_RATE_OPTIONS[0][0])

        ttk.Label(form, text="Quantity:").grid(row=0, column=0, sticky="w", pady=4, padx=(0, 8))
        qty_entry = ttk.Entry(form, textvariable=qty_var, width=14)
        qty_entry.grid(row=0, column=1, pady=4)
        ttk.Label(form, text=price_label + ":").grid(row=1, column=0, sticky="w", pady=4, padx=(0, 8))
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
                gross = money.line_amounts(
                    int(qty_var.get()), float(cost_var.get()), rate_by_label[vat_var.get()]
                ).gross
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
