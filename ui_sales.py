"""Sale screens and dialogs (mixin for App)."""
import datetime
import tkinter as tk
from tkinter import ttk, messagebox

import database
import products as product_db
import services as service_db
import customers as customer_db
import sales as sale_db
import pricing as pricing_db

from ui_common import make_sortable, VAT_RATE_OPTIONS


class SalesMixin:
    def show_sales(self, prefill=""):
        self.current_view = "sales"
        self._clear_container()

        header = ttk.Frame(self.container)
        header.pack(fill="x", pady=(0, 10))
        ttk.Label(header, text="Sales", font=("Segoe UI", 20, "bold")).pack(side="left")

        bar = ttk.Frame(self.container)
        bar.pack(fill="x", pady=(0, 10))
        bar.columnconfigure(1, weight=1)
        search_term = tk.StringVar(value=prefill)
        status_choice = tk.StringVar(value="All")
        ttk.Label(bar, text="Search:").grid(row=0, column=0, sticky="w")
        search_entry = ttk.Entry(bar, textvariable=search_term)
        search_entry.grid(row=0, column=1, sticky="ew", padx=(8, 10))
        search_entry.focus_set()
        search_entry.bind("<Return>", lambda e: do_search())
        ttk.Label(bar, text="Status:").grid(row=0, column=2, sticky="w")
        status_combo = ttk.Combobox(
            bar, state="readonly", width=10, textvariable=status_choice,
            values=["All", "Quote", "Order", "Invoice"],
        )
        status_combo.grid(row=0, column=3, sticky="w", padx=(8, 10))
        status_combo.current(0)
        status_combo.bind("<<ComboboxSelected>>", lambda e: do_search())
        ttk.Button(bar, text="Search", command=lambda: do_search()).grid(row=0, column=4, padx=(0, 8))
        ttk.Button(bar, text="Clear", command=lambda: clear()).grid(row=0, column=5)

        columns = ("reference", "customer", "status", "date", "total")
        headings = ("Reference", "Customer", "Status", "Date", "Total")
        widths = (170, 230, 90, 110, 110)
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
        tree.column("total", anchor="e")
        make_sortable(tree)

        status_label = ttk.Label(self.container, text="")
        status_label.pack(anchor="w", pady=(8, 0))

        def refresh():
            status = status_choice.get()
            rows = sale_db.list_sales(
                text=search_term.get().strip(), status="" if status == "All" else status
            )
            tree.delete(*tree.get_children())
            for r in rows:
                tree.insert(
                    "", "end", iid=str(r["id"]),
                    values=(r["reference"] or "", r["customer_name"], r["status"],
                            r["date"] or "", f"{r['total']:,.2f}"),
                )
            status_label.config(text=f"{len(rows)} sale(s)." if rows else "No sales found.")

        def clear():
            search_term.set("")
            status_choice.set("All")
            status_combo.current(0)
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
                messagebox.showinfo("No selection", "Please select a sale first.")
                return
            self.show_sale_form(sale_db.get_sale(int(selection[0])))

        tree.bind("<Double-1>", lambda e: open_selected())
        tree.bind("<Return>", lambda e: open_selected())
        refresh()

    def show_sale_form(self, sale=None, prefill_product=None):
        """Create/edit a sale with product and service line items.
        `prefill_product` (a product row) starts a new sale with that product
        already added — used when creating a sale straight from the product list."""
        self.current_view = "sale_form"
        self._clear_container()
        editing = sale is not None

        ttk.Label(
            self.container,
            text="Edit Sale" if editing else "New Sale",
            font=("Segoe UI", 20, "bold"),
        ).pack(anchor="w", pady=(0, 12))

        status_var = tk.StringVar(value="Quote")
        reference_var = tk.StringVar(value="(auto-generated)")
        date_var = tk.StringVar(value=datetime.date.today().strftime("%d/%m/%y"))

        # Two-column details panel: Customer/Status on the left, Reference/Date right.
        head = ttk.LabelFrame(self.container, text="Sale Details", padding=12)
        head.pack(anchor="w", fill="x")

        # Customer is chosen via + (create new) / 🔍 (search) buttons; once assigned
        # an ✕ button unassigns it and the +/search buttons return.
        customer_state = {"id": None, "name": ""}
        ttk.Label(head, text="Customer:").grid(row=0, column=0, sticky="w", pady=6, padx=(0, 10))
        cust_frame = ttk.Frame(head)
        cust_frame.grid(row=0, column=1, sticky="w", pady=6)

        def set_customer(customer_id, name):
            customer_state["id"], customer_state["name"] = customer_id, name
            render_customer()

        def clear_customer():
            customer_state["id"], customer_state["name"] = None, ""
            render_customer()

        def render_customer():
            for child in cust_frame.winfo_children():
                child.destroy()
            if customer_state["id"] is not None:
                ttk.Label(
                    cust_frame, text=customer_state["name"], font=("Segoe UI", 10, "bold")
                ).pack(side="left")
                ttk.Button(cust_frame, text="✕", width=3, command=clear_customer).pack(
                    side="left", padx=(8, 0)
                )
            else:
                ttk.Label(cust_frame, text="No customer selected", foreground="gray").pack(
                    side="left"
                )
                ttk.Button(
                    cust_frame, text="+", width=3,
                    command=lambda: self.open_new_customer_dialog(set_customer),
                ).pack(side="left", padx=(8, 0))
                ttk.Button(
                    cust_frame, text="🔍", width=3,
                    command=lambda: self.open_customer_search_dialog(set_customer),
                ).pack(side="left", padx=(4, 0))

        render_customer()

        ttk.Label(head, text="Status:").grid(row=1, column=0, sticky="w", pady=6, padx=(0, 10))
        ttk.Combobox(
            head, state="readonly", width=18, textvariable=status_var,
            values=list(sale_db.STATUSES),
        ).grid(row=1, column=1, sticky="w", pady=6)

        # Right column.
        ttk.Label(head, text="Reference:").grid(row=0, column=2, sticky="w", pady=6, padx=(30, 10))
        # Autogenerated per status (Q…/O…/INV…); not user-editable.
        ttk.Entry(head, textvariable=reference_var, width=22, state="readonly").grid(
            row=0, column=3, sticky="w", pady=6
        )

        ttk.Label(head, text="Date:").grid(row=1, column=2, sticky="w", pady=6, padx=(30, 10))
        ttk.Entry(head, textvariable=date_var, width=22).grid(row=1, column=3, sticky="w", pady=6)

        # --- Line items (products + services) ---
        items_header = ttk.Frame(self.container)
        items_header.pack(fill="x", pady=(15, 5))
        ttk.Label(items_header, text="Items", font=("Segoe UI", 12, "bold")).pack(side="left")
        ttk.Button(
            items_header, text="Add Product",
            command=lambda: self.open_product_allocation(
                receive_products, "Unit Price (net)",
                price_fn=lambda p: pricing_db.price_for_product(p["id"]),
                stock_filter=True, quick_add=True,
            ),
        ).pack(side="left", padx=(12, 0))
        ttk.Button(
            items_header, text="Add Service",
            command=lambda: self.open_service_picker(receive_service),
        ).pack(side="left", padx=(8, 0))

        lines = []  # dicts: item_type, product_id, service_id, description, quantity, unit_price, vat_rate

        def receive_products(basket):
            for it in basket:
                lines.append({
                    "item_type": "product", "product_id": it["product_id"],
                    "service_id": None,
                    "description": it.get("description") or it["label"],
                    "quantity": it["quantity"], "unit_price": it["cost_price"],
                    "vat_rate": it["vat_rate"],
                })
            refresh_lines()
            self.mark_form_dirty()

        def receive_service(line):
            lines.append(line)
            refresh_lines()
            self.mark_form_dirty()

        lt_frame = ttk.Frame(self.container)
        lt_frame.pack(fill="both", expand=True, pady=(8, 0))
        lines_tree = ttk.Treeview(
            lt_frame, columns=("item", "type", "qty", "price", "vat", "total"),
            show="headings", height=6,
        )
        for col, heading, width, anchor in [
            ("item", "Item", 280, "w"), ("type", "Type", 70, "w"),
            ("qty", "Qty", 50, "e"), ("price", "Unit Price", 90, "e"),
            ("vat", "VAT", 55, "e"), ("total", "Line Total", 100, "e"),
        ]:
            lines_tree.heading(col, text=heading)
            lines_tree.column(col, width=width, anchor=anchor)
        make_sortable(lines_tree)
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
            self.mark_form_dirty()

        def refresh_lines():
            lines_tree.delete(*lines_tree.get_children())
            net_total = vat_total = gross_total = 0.0
            for index, ln in enumerate(lines):
                net = ln["quantity"] * ln["unit_price"]
                vat = net * ln["vat_rate"] / 100.0
                gross = net + vat
                net_total += net
                vat_total += vat
                gross_total += gross
                lines_tree.insert(
                    "", "end", iid=str(index),
                    values=(ln["description"], ln["item_type"].title(), ln["quantity"],
                            f"{ln['unit_price']:.2f}", f"{ln['vat_rate']:.0f}%", f"{gross:,.2f}"),
                )
            total_label.config(
                text=f"Net {net_total:,.2f}   VAT {vat_total:,.2f}   Gross {gross_total:,.2f}"
            )

        def edit_cell(event):
            """Double-click the Qty or Unit Price cell to edit it inline."""
            if lines_tree.identify("region", event.x, event.y) != "cell":
                return
            column = lines_tree.identify_column(event.x)
            rowid = lines_tree.identify_row(event.y)
            if not rowid or column not in ("#3", "#4"):  # Qty (#3) / Unit Price (#4)
                return
            key = "quantity" if column == "#3" else "unit_price"
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

            committed = {"done": False}

            def commit(_=None):
                # Bound to both <Return> and <FocusOut>; the warning dialog steals
                # focus and would otherwise fire commit a second time.
                if committed["done"]:
                    return
                committed["done"] = True
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
                ln = lines[index]
                # Warn (but still allow) when selling more than we hold in stock.
                if key == "quantity" and ln["item_type"] == "product" and ln["product_id"]:
                    stock = product_db.product_stock(ln["product_id"])
                    if value > stock:
                        messagebox.showwarning(
                            "Insufficient stock",
                            f"Only {stock} in stock for this product, "
                            f"but {value} requested.",
                        )
                ln[key] = value
                editor.destroy()
                refresh_lines()

            editor.bind("<Return>", commit)
            editor.bind("<FocusOut>", commit)
            editor.bind("<Escape>", lambda e: editor.destroy())

        lines_tree.bind("<Double-1>", edit_cell)

        def save():
            customer_id = customer_state["id"]
            if customer_id is None:
                messagebox.showwarning("Customer", "Please choose a customer.")
                return
            if not lines:
                messagebox.showwarning("No items", "Add at least one product or service.")
                return
            args = (customer_id, status_var.get(), date_var.get().strip(), lines)
            if editing:
                sale_db.update_sale(sale["id"], *args)
            else:
                sale_db.create_sale(*args)
            messagebox.showinfo("Saved", "Sale saved.")
            self.show_sales()

        def delete_current():
            if not editing:
                return
            if messagebox.askyesno("Delete sale", "Delete this sale?"):
                try:
                    sale_db.delete_sale(sale["id"])
                except Exception as exc:  # e.g. a sale with receipts allocated
                    messagebox.showerror("Cannot delete", str(exc))
                    return
                self.show_sales()

        cancel = self._discard_guard(self.show_sales)
        btns = ttk.Frame(self.container)
        btns.pack(anchor="w", pady=(12, 0))
        ttk.Button(btns, text="Save (Ctrl+S)", command=save).pack(side="left")
        ttk.Button(btns, text="Cancel (Esc)", command=cancel).pack(side="left", padx=(8, 0))
        if editing:
            ttk.Button(btns, text="Delete (Ctrl+D)", command=delete_current).pack(side="left", padx=(8, 0))
        self._bind_form_shortcuts(
            save=save, cancel=cancel,
            delete=delete_current if editing else None,
        )

        if editing:
            set_customer(sale["customer_id"], sale["customer_name"])
            status_var.set(sale["status"])
            reference_var.set(sale["reference"] or "(auto-generated)")
            date_var.set(sale["date"] or "")
            for it in sale_db.get_sale_items(sale["id"]):
                lines.append({
                    "item_type": it["item_type"], "product_id": it["product_id"],
                    "service_id": it["service_id"], "description": it["description"],
                    "quantity": it["quantity"], "unit_price": it["unit_price"],
                    "vat_rate": it["vat_rate"],
                })
            refresh_lines()
        elif prefill_product is not None:
            # Started from the product list: add it straight away as a single line.
            # The retail price comes from the matching pricing rule (or 0 if none);
            # quantity/price are then editable inline in the items table.
            label = f"{prefill_product['stock_code']} — {prefill_product['description']}"
            price = pricing_db.price_for_product(prefill_product["id"]) or 0.0
            receive_products([{
                "product_id": prefill_product["id"], "label": label,
                "description": prefill_product["description"] or label,
                "quantity": 1, "cost_price": price, "vat_rate": VAT_RATE_OPTIONS[0][1],
            }])

    def open_new_customer_dialog(self, on_created):
        """Modal to create a customer; calls on_created(id, name) on success."""
        dialog = tk.Toplevel(self)
        dialog.title("New Customer")
        dialog.transient(self)
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding=12)
        frame.pack(fill="both", expand=True)
        entries = {}
        fields = [
            ("name", "Name"), ("contact", "Contact"), ("email", "Email"),
            ("phone", "Phone"),
        ]
        for row, (key, label) in enumerate(fields):
            ttk.Label(frame, text=label + ":").grid(row=row, column=0, sticky="w", pady=4, padx=(0, 8))
            entry = ttk.Entry(frame, width=34)
            entry.grid(row=row, column=1, pady=4)
            entries[key] = entry
        ttk.Label(
            frame, text="Account # is generated automatically.", foreground="gray"
        ).grid(row=len(fields), column=0, columnspan=2, sticky="w", pady=(6, 0))

        def save():
            data = {key: entry.get().strip() for key, entry in entries.items()}
            if not data["name"]:
                messagebox.showwarning("Missing name", "Please enter a customer name.", parent=dialog)
                return
            try:
                customer_id = customer_db.add_customer(
                    data["name"], "", data["contact"], data["email"], data["phone"],
                )
            except customer_db.DuplicateNameError:
                messagebox.showerror(
                    "Duplicate name", f"A customer named '{data['name']}' already exists.",
                    parent=dialog,
                )
                return
            on_created(customer_id, data["name"])
            dialog.destroy()

        btns = ttk.Frame(frame)
        btns.grid(row=len(fields) + 1, column=0, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(btns, text="Save", command=save).pack(side="left")
        ttk.Button(btns, text="Cancel", command=dialog.destroy).pack(side="left", padx=(8, 0))
        entries["name"].focus_set()

    def open_customer_search_dialog(self, on_selected):
        """Modal to search the customer database; calls on_selected(id, name)."""
        dialog = tk.Toplevel(self)
        dialog.title("Find Customer")
        dialog.transient(self)
        dialog.grab_set()
        dialog.geometry("540x440")

        bar = ttk.Frame(dialog, padding=10)
        bar.pack(fill="x")
        ttk.Label(bar, text="Search:").pack(side="left")
        term = tk.StringVar()
        entry = ttk.Entry(bar, textvariable=term)
        entry.pack(side="left", fill="x", expand=True, padx=(8, 0))
        entry.focus_set()

        tree_frame = ttk.Frame(dialog, padding=(10, 0))
        tree_frame.pack(fill="both", expand=True)
        cols = ("name", "account_number", "contact", "phone")
        tree = ttk.Treeview(tree_frame, columns=cols, show="headings")
        for col, heading, width in zip(
            cols, ("Name", "Account #", "Contact", "Phone"), (190, 90, 130, 110)
        ):
            tree.heading(col, text=heading)
            tree.column(col, width=width)
        sb = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        tree.pack(side="left", fill="both", expand=True)
        make_sortable(tree)

        all_customers = customer_db.get_all_customers()
        name_by_id = {c["id"]: c["name"] for c in all_customers}

        def refresh(*_):
            needle = term.get().strip().lower()
            tree.delete(*tree.get_children())
            for c in all_customers:
                hay = " ".join(
                    str(c[k] or "") for k in ("name", "account_number", "contact", "email", "phone")
                ).lower()
                if not needle or needle in hay:
                    tree.insert(
                        "", "end", iid=str(c["id"]),
                        values=(c["name"], c["account_number"] or "", c["contact"] or "",
                                c["phone"] or ""),
                    )

        def choose(*_):
            selection = tree.selection()
            if not selection:
                return
            customer_id = int(selection[0])
            on_selected(customer_id, name_by_id[customer_id])
            dialog.destroy()

        term.trace_add("write", refresh)
        # Enter in the search box drops focus to the first result.
        entry.bind("<Return>", lambda e: self._focus_first_row(tree))
        tree.bind("<Return>", choose)
        tree.bind("<Double-1>", choose)

        btns = ttk.Frame(dialog, padding=10)
        btns.pack(fill="x")
        ttk.Button(btns, text="Select", command=choose).pack(side="right")
        ttk.Button(btns, text="Cancel", command=dialog.destroy).pack(side="right", padx=(0, 8))
        refresh()

    @staticmethod
    def _focus_first_row(tree):
        children = tree.get_children()
        if children:
            tree.focus_set()
            tree.selection_set(children[0])
            tree.focus(children[0])

    def open_service_picker(self, on_add):
        """Search-driven window to add service lines (mirrors product allocation).
        Search, press Enter for a results table, then select a service to add it
        (a quantity/price/VAT dialog follows). Stays open so several can be added.
        Each addition calls on_add(line_dict)."""
        if not service_db.list_services():
            messagebox.showinfo("No services", "There are no services yet. Add some under Services.")
            return

        win = tk.Toplevel(self)
        win.title("Add Service")
        win.geometry("680x460")
        win.transient(self)
        win.grab_set()

        result_map = {}  # iid -> service Row

        search = ttk.Frame(win, padding=10)
        search.pack(fill="x")
        term_var = tk.StringVar()
        ttk.Label(search, text="Search:").pack(side="left")
        search_entry = ttk.Entry(search, textvariable=term_var, width=30)
        search_entry.pack(side="left", padx=(8, 8))
        search_entry.bind("<Return>", lambda e: do_search())
        ttk.Button(search, text="Search", command=lambda: do_search()).pack(side="left")
        ttk.Button(search, text="Clear", command=lambda: clear()).pack(side="left", padx=(6, 0))

        res_frame = ttk.Frame(win, padding=(10, 0))
        res_frame.pack(fill="both", expand=True)
        rcols = ("code", "name", "cost", "retail")
        results = ttk.Treeview(res_frame, columns=rcols, show="headings", height=12)
        for col, heading, width, anchor in [
            ("code", "Code", 120, "w"), ("name", "Service", 300, "w"),
            ("cost", "Cost", 100, "e"), ("retail", "Retail Price", 110, "e"),
        ]:
            results.heading(col, text=heading)
            results.column(col, width=width, anchor=anchor)
        make_sortable(results)
        rsb = ttk.Scrollbar(res_frame, orient="vertical", command=results.yview)
        results.configure(yscrollcommand=rsb.set)
        rsb.pack(side="right", fill="y")
        results.pack(side="left", fill="both", expand=True)

        res_status = ttk.Label(win, text="Search services by code or name.", padding=(10, 4))
        res_status.pack(anchor="w")

        foot = ttk.Frame(win, padding=10)
        foot.pack(fill="x")
        ttk.Button(foot, text="Add Selected", command=lambda: add_selected()).pack(side="left")
        ttk.Button(foot, text="Close", command=win.destroy).pack(side="right")

        def do_search():
            results.delete(*results.get_children())
            result_map.clear()
            rows = service_db.list_services(text=term_var.get().strip())
            for s in rows:
                results.insert(
                    "", "end", iid=str(s["id"]),
                    values=(s["service_code"] or "—", s["service_name"],
                            f"{(s['cost'] or 0):,.2f}", f"{(s['retail_price'] or 0):,.2f}"),
                )
                result_map[str(s["id"])] = s
            children = results.get_children()
            if children:
                self._focus_first_row(results)
                res_status.config(text=f"{len(children)} service(s) — Enter to add.")
            else:
                res_status.config(text="No services found.")

        def clear():
            term_var.set("")
            results.delete(*results.get_children())
            result_map.clear()
            res_status.config(text="Search services by code or name.")
            search_entry.focus_set()

        def add_selected():
            selection = results.selection()
            if not selection:
                return
            service = result_map.get(selection[0])
            if not service:
                return
            # Add quantity 1 at the service's retail price, then return to the sale.
            on_add({
                "item_type": "service", "product_id": None, "service_id": service["id"],
                "description": service["service_name"], "quantity": 1,
                "unit_price": service["retail_price"] or 0.0,
                "vat_rate": VAT_RATE_OPTIONS[0][1],
            })
            win.destroy()

        results.bind("<Return>", lambda e: add_selected())
        results.bind("<Double-1>", lambda e: add_selected())

        # Start empty — results appear only after a search.
        search_entry.focus_set()

    # ------------------------------------------------------------------- Receipts
