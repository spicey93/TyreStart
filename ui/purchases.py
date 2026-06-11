"""Purchase screens (mixin for App)."""
import datetime
import tkinter as tk
from tkinter import ttk
from ui import dialogs as messagebox

from core import suppliers as db
from core import purchases as purchase_db
from core import money

from ui.common import AutocompleteCombobox, make_sortable


class PurchasesMixin:
    def show_purchases(self, prefill=""):
        self.current_view = "purchases"
        self._clear_container()

        header = ttk.Frame(self.container)
        header.pack(fill="x", pady=(0, 10))
        ttk.Label(
            header, text="Purchases", font=("Consolas", 20, "bold")
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
        search_entry.bind("<Return>", lambda e: do_search())

        ttk.Label(bar, text="Status:").grid(row=0, column=2, sticky="w")
        status_combo = ttk.Combobox(
            bar, state="readonly", width=10, textvariable=status_choice,
            values=["All", "Order", "Invoice"],
        )
        status_combo.grid(row=0, column=3, sticky="w", padx=(8, 10))
        status_combo.current(0)
        status_combo.bind("<<ComboboxSelected>>", lambda e: do_search())
        ttk.Button(bar, text="Search", command=lambda: do_search()).grid(row=0, column=4, padx=(0, 8))
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
        make_sortable(tree)

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

        def do_search():
            refresh()
            children = tree.get_children()
            if children:
                first = children[0]
                tree.focus_set()
                tree.selection_set(first)
                tree.focus(first)
                tree.see(first)

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

        def delete_selected(event=None):
            selection = tree.selection()
            if not selection:
                return
            if messagebox.askyesno("Delete purchase", "Delete this purchase?"):
                try:
                    purchase_db.delete_purchase(int(selection[0]))
                except Exception as exc:  # e.g. an invoice with payments allocated
                    messagebox.showerror("Cannot delete", str(exc))
                    return
                refresh()

        tree.bind("<Double-1>", lambda e: open_selected())
        tree.bind("<Return>", lambda e: open_selected())
        tree.bind("<Delete>", delete_selected)

        ttk.Label(
            self.container,
            text="Double-click or Enter to edit · Delete key to remove the selected purchase.",
            foreground="#C9A227",
        ).pack(anchor="w", pady=(4, 0))

        refresh()

    def show_purchase_form(self, purchase=None):
        """Create/edit a purchase, including its product line items."""
        self.current_view = "purchase_form"
        self._clear_container()
        editing = purchase is not None

        ttk.Label(
            self.container,
            text="Edit Purchase" if editing else "New Purchase",
            font=("Consolas", 20, "bold"),
        ).pack(anchor="w", pady=(0, 12))

        # --- Header fields (bordered panel; mirrors the Sale form's layout) ---
        head = ttk.LabelFrame(self.container, text="Purchase Details", padding=12)
        head.pack(anchor="w", fill="x")
        supplier_by_name = {s["name"]: s["id"] for s in db.get_all_suppliers()}

        supplier_var = tk.StringVar()
        status_var = tk.StringVar(value="Order")
        reference_var = tk.StringVar()
        date_var = tk.StringVar(value=datetime.date.today().strftime("%d/%m/%y"))

        # Left column: Supplier / Status.
        ttk.Label(head, text="Supplier:").grid(row=0, column=0, sticky="w", pady=6, padx=(0, 10))
        supplier_combo = AutocompleteCombobox(head, textvariable=supplier_var, width=30)
        supplier_combo.set_completion_list(list(supplier_by_name.keys()))
        supplier_combo.grid(row=0, column=1, sticky="w", pady=6)
        supplier_combo.focus_set()  # target the supplier picker on load

        ttk.Label(head, text="Status:").grid(row=1, column=0, sticky="w", pady=6, padx=(0, 10))
        ttk.Combobox(
            head, state="readonly", width=18, textvariable=status_var,
            values=list(purchase_db.STATUSES),
        ).grid(row=1, column=1, sticky="w", pady=6)

        # Right column: Reference / Date.
        ttk.Label(head, text="Reference:").grid(row=0, column=2, sticky="w", pady=6, padx=(30, 10))
        ttk.Entry(head, textvariable=reference_var, width=24).grid(row=0, column=3, sticky="w", pady=6)

        ttk.Label(head, text="Date:").grid(row=1, column=2, sticky="w", pady=6, padx=(30, 10))
        ttk.Entry(head, textvariable=date_var, width=24).grid(row=1, column=3, sticky="w", pady=6)

        # --- Line items: added via the Product Allocation window ---
        prod_header = ttk.Frame(self.container)
        prod_header.pack(fill="x", pady=(15, 5))
        ttk.Label(
            prod_header, text="Products", font=("Consolas", 12, "bold")
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
            self.mark_form_dirty()

        lt_frame = ttk.Frame(self.container)
        lt_frame.pack(fill="both", expand=True, pady=(8, 0))
        lines_tree = ttk.Treeview(
            lt_frame, columns=("stock_code", "description", "qty", "cost", "vat", "total"),
            show="headings", height=6,
        )
        for col, heading, width, anchor in [
            ("stock_code", "Stock Code", 130, "w"), ("description", "Description", 260, "w"),
            ("qty", "Qty", 50, "e"), ("cost", "Cost", 90, "e"), ("vat", "VAT", 60, "e"),
            ("total", "Line Total", 100, "e"),
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
            bottom, text="Net 0.00   VAT 0.00   Gross 0.00", font=("Consolas", 10, "bold")
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
                net, vat, gross = money.line_amounts(
                    ln["quantity"], ln["cost_price"], ln["vat_rate"]
                )
                net_total += net
                vat_total += vat
                gross_total += gross
                lines_tree.insert(
                    "", "end", iid=str(index),
                    values=(ln["stock_code"], ln["description"], ln["quantity"],
                            f"{ln['cost_price']:.2f}", f"{ln['vat_rate']:.0f}%", f"{gross:,.2f}"),
                )
            total_label.config(
                text=f"Net {net_total:,.2f}   VAT {vat_total:,.2f}   Gross {gross_total:,.2f}"
            )

        def edit_cell(event):
            """Double-click the Qty or Cost cell to edit it inline."""
            if lines_tree.identify("region", event.x, event.y) != "cell":
                return
            column = lines_tree.identify_column(event.x)  # '#1'..'#6'
            rowid = lines_tree.identify_row(event.y)
            if not rowid or column not in ("#3", "#4"):  # only Qty (#3) / Cost (#4)
                return
            key = "quantity" if column == "#3" else "cost_price"
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
                return purchase["id"]
            return purchase_db.create_purchase(*args)

        self._register_form(save=save, back=self.show_purchases)

        # Prefill when editing (after the line widgets exist).
        if editing:
            supplier_var.set(purchase["supplier_name"])
            status_var.set(purchase["status"])
            reference_var.set(purchase["reference"] or "")
            date_var.set(purchase["date"] or "")
            for it in purchase_db.get_purchase_items(purchase["id"]):
                lines.append({
                    "product_id": it["product_id"],
                    "stock_code": it["stock_code"],
                    "description": it["description"],
                    "quantity": it["quantity"],
                    "cost_price": it["cost_price"],
                    "vat_rate": it["vat_rate"],
                })
            refresh_lines()

    # ------------------------------------------------------- Product Allocation
