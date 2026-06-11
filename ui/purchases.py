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
            self.open_purchase(purchase_db.get_purchase(int(selection[0])))

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

    def open_purchase(self, purchase):
        """Open a purchase in the right editor for its type (Order vs Invoice)."""
        if purchase["status"] == "Order":
            self.show_purchase_order_form(purchase)
        else:
            self.show_purchase_invoice_form(purchase)

    def _resolve_supplier(self, supplier_by_name, typed):
        """Map a typed supplier name to its id (case-insensitive), or None."""
        typed = typed.strip()
        if typed in supplier_by_name:
            return supplier_by_name[typed]
        for name, sid in supplier_by_name.items():
            if name.lower() == typed.lower():
                return sid
        return None

    def _purchase_lines_editor(self, parent, editable=True):
        """Build the product-lines editor (Add Product + table + totals).

        Lines are removed by pressing Delete on a row or setting its Qty to 0.
        When `editable` is False the lines are shown read-only. Returns a dict with
        `lines` (the working list) and `refresh()`.
        """
        header = ttk.Frame(parent)
        header.pack(fill="x", pady=(15, 5))
        ttk.Label(header, text="Products", font=("Consolas", 12, "bold")).pack(side="left")

        lines = []

        def receive_basket(items):
            lines.extend(items)
            refresh_lines()
            self.mark_form_dirty()

        if editable:
            ttk.Button(
                header, text="Add Product",
                command=lambda: self.open_product_allocation(receive_basket),
            ).pack(side="left", padx=(12, 0))

        lt_frame = ttk.Frame(parent)
        lt_frame.pack(fill="both", expand=True, pady=(8, 0))
        tree = ttk.Treeview(
            lt_frame, columns=("stock_code", "description", "qty", "cost", "vat", "total"),
            show="headings", height=6,
        )
        for col, heading, width, anchor in [
            ("stock_code", "Stock Code", 130, "w"), ("description", "Description", 260, "w"),
            ("qty", "Qty", 50, "e"), ("cost", "Cost", 90, "e"), ("vat", "VAT", 60, "e"),
            ("total", "Line Total", 100, "e"),
        ]:
            tree.heading(col, text=heading)
            tree.column(col, width=width, anchor=anchor)
        make_sortable(tree)
        ls = ttk.Scrollbar(lt_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=ls.set)
        ls.pack(side="right", fill="y")
        tree.pack(side="left", fill="both", expand=True)

        total_label = ttk.Label(
            parent, text="Net 0.00   VAT 0.00   Gross 0.00", font=("Consolas", 10, "bold")
        )
        total_label.pack(anchor="e", pady=(6, 0))

        def refresh_lines():
            tree.delete(*tree.get_children())
            net_total = vat_total = gross_total = 0.0
            for index, ln in enumerate(lines):
                net, vat, gross = money.line_amounts(
                    ln["quantity"], ln["cost_price"], ln["vat_rate"])
                net_total += net
                vat_total += vat
                gross_total += gross
                tree.insert(
                    "", "end", iid=str(index),
                    values=(ln["stock_code"], ln["description"], ln["quantity"],
                            f"{ln['cost_price']:.2f}", f"{ln['vat_rate']:.0f}%", f"{gross:,.2f}"))
            total_label.config(
                text=f"Net {net_total:,.2f}   VAT {vat_total:,.2f}   Gross {gross_total:,.2f}")

        def remove_at(index):
            del lines[index]
            refresh_lines()
            self.mark_form_dirty()

        def delete_selected(event=None):
            sel = tree.selection()
            if sel:
                remove_at(int(sel[0]))
            return "break"

        def edit_cell(event):
            """Double-click Qty or Cost to edit inline; Qty 0 removes the line."""
            if tree.identify("region", event.x, event.y) != "cell":
                return
            column = tree.identify_column(event.x)  # '#1'..'#6'
            rowid = tree.identify_row(event.y)
            if not rowid or column not in ("#3", "#4"):  # only Qty (#3) / Cost (#4)
                return
            key = "quantity" if column == "#3" else "cost_price"
            index = int(rowid)
            bbox = tree.bbox(rowid, column)
            if not bbox:
                return
            x, y, w, h = bbox
            editor = ttk.Entry(tree)
            editor.place(x=x, y=y, width=w, height=h)
            editor.insert(0, str(lines[index][key]))
            editor.select_range(0, "end")
            editor.focus_set()

            def commit(_=None):
                raw = editor.get().strip()
                try:
                    value = int(raw) if key == "quantity" else float(raw)
                    if value < 0:
                        raise ValueError
                except ValueError:
                    editor.destroy()
                    return
                editor.destroy()
                if key == "quantity" and value == 0:  # zero qty removes the line
                    remove_at(index)
                    return
                lines[index][key] = value
                refresh_lines()
                self.mark_form_dirty()

            editor.bind("<Return>", commit)
            editor.bind("<FocusOut>", commit)
            editor.bind("<Escape>", lambda e: editor.destroy())

        if editable:
            tree.bind("<Double-1>", edit_cell)
            tree.bind("<Delete>", delete_selected)
            ttk.Label(
                parent, style="Hint.TLabel",
                text="Double-click Qty/Cost to edit · set Qty to 0 or press Delete to remove a line.",
            ).pack(anchor="w", pady=(4, 0))

        return {"lines": lines, "refresh": refresh_lines, "tree": tree}

    def _prefill_lines(self, editor, purchase_id):
        for it in purchase_db.get_purchase_items(purchase_id):
            editor["lines"].append({
                "product_id": it["product_id"], "stock_code": it["stock_code"],
                "description": it["description"], "quantity": it["quantity"],
                "cost_price": it["cost_price"], "vat_rate": it["vat_rate"],
            })
        editor["refresh"]()

    def show_purchase_order_form(self, purchase=None):
        """Create/edit a purchase order: supplier + date + product lines, with an
        auto-generated PO number. Once received, the order is read-only."""
        self.current_view = "purchase_form"
        self._clear_container()
        editing = purchase is not None
        received = bool(editing and purchase["received"])

        ttk.Label(
            self.container, text="Edit Purchase Order" if editing else "New Purchase Order",
            font=("Consolas", 20, "bold"),
        ).pack(anchor="w", pady=(0, 12))

        head = ttk.LabelFrame(self.container, text="Purchase Order", padding=12)
        head.pack(anchor="w", fill="x")
        supplier_by_name = {s["name"]: s["id"] for s in db.get_all_suppliers()}
        supplier_var = tk.StringVar()
        date_var = tk.StringVar(value=datetime.date.today().strftime("%d/%m/%y"))

        ttk.Label(head, text="Supplier:").grid(row=0, column=0, sticky="w", pady=6, padx=(0, 10))
        supplier_combo = AutocompleteCombobox(head, textvariable=supplier_var, width=30)
        supplier_combo.set_completion_list(list(supplier_by_name.keys()))
        supplier_combo.grid(row=0, column=1, sticky="w", pady=6)
        supplier_combo.focus_set()

        ttk.Label(head, text="PO Number:").grid(row=0, column=2, sticky="w", pady=6, padx=(30, 10))
        po_number = purchase["reference"] if editing else "(auto-generated on save)"
        ttk.Label(head, text=po_number, font=("Consolas", 11, "bold")).grid(
            row=0, column=3, sticky="w", pady=6)

        ttk.Label(head, text="Date:").grid(row=1, column=0, sticky="w", pady=6, padx=(0, 10))
        ttk.Entry(head, textvariable=date_var, width=24).grid(row=1, column=1, sticky="w", pady=6)

        if received:
            ttk.Label(head, text="✓ Received — order locked", style="Hint.TLabel").grid(
                row=1, column=2, columnspan=2, sticky="w", pady=6, padx=(30, 0))

        editor = self._purchase_lines_editor(self.container, editable=not received)

        if editing and not received:
            actions = ttk.Frame(self.container)
            actions.pack(fill="x", pady=(8, 0))
            ttk.Button(actions, text="Receive / Deliver",
                       command=lambda: self._receive_purchase_order(purchase["id"])).pack(side="left")

        def save():
            if received:
                return purchase["id"]  # locked — nothing to persist
            supplier_id = self._resolve_supplier(supplier_by_name, supplier_var.get())
            if supplier_id is None:
                messagebox.showwarning("Supplier", "Please choose a valid supplier.")
                return None
            if not editor["lines"]:
                messagebox.showwarning("No products", "Add at least one product line.")
                return None
            items = [
                {"product_id": ln["product_id"], "quantity": ln["quantity"],
                 "cost_price": ln["cost_price"], "vat_rate": ln["vat_rate"]}
                for ln in editor["lines"]
            ]
            date = date_var.get().strip()
            if editing:
                purchase_db.update_purchase(
                    purchase["id"], supplier_id, "Order", purchase["reference"], date, items)
                return purchase["id"]
            return purchase_db.create_purchase(supplier_id, "Order", "", date, items)

        self._register_form(save=save, back=self.show_purchases)

        if editing:
            supplier_var.set(purchase["supplier_name"])
            date_var.set(purchase["date"] or "")
            self._prefill_lines(editor, purchase["id"])

    def _receive_purchase_order(self, po_id):
        """Modal to confirm/adjust received quantities, then raise the linked
        invoice and open it for the user to enter the supplier's invoice number."""
        items = purchase_db.get_purchase_items(po_id)
        if not items:
            messagebox.showinfo("Nothing to receive", "This order has no product lines.")
            return

        dialog = tk.Toplevel(self)
        dialog.title("Receive / Deliver")
        dialog.transient(self)
        dialog.grab_set()

        ttk.Label(
            dialog, text="Confirm the quantities received (defaults to all ordered):",
            padding=12,
        ).pack(anchor="w")
        grid = ttk.Frame(dialog, padding=(12, 0))
        grid.pack(fill="x")
        for col, text in enumerate(["Stock Code", "Description", "Ordered", "Received"]):
            ttk.Label(grid, text=text, font=("Consolas", 9, "bold")).grid(
                row=0, column=col, sticky="w", padx=(0, 12), pady=(0, 4))
        recv_vars = {}
        for i, it in enumerate(items, start=1):
            ttk.Label(grid, text=it["stock_code"]).grid(row=i, column=0, sticky="w", padx=(0, 12))
            ttk.Label(grid, text=it["description"]).grid(row=i, column=1, sticky="w", padx=(0, 12))
            ttk.Label(grid, text=str(it["quantity"])).grid(row=i, column=2, sticky="e", padx=(0, 12))
            var = tk.StringVar(value=str(it["quantity"]))  # default: all received
            ttk.Entry(grid, textvariable=var, width=8).grid(row=i, column=3, sticky="w")
            recv_vars[it["id"]] = var

        def confirm():
            received = {}
            for item_id, var in recv_vars.items():
                raw = var.get().strip()
                try:
                    qty = int(raw or 0)
                    if qty < 0:
                        raise ValueError
                except ValueError:
                    messagebox.showwarning("Invalid quantity",
                                           "Received quantities must be whole numbers.",
                                           parent=dialog)
                    return
                received[item_id] = qty
            if sum(received.values()) == 0:
                messagebox.showwarning("Nothing received",
                                       "Enter a received quantity for at least one line.",
                                       parent=dialog)
                return
            today = datetime.date.today().strftime("%d/%m/%y")
            invoice_id = purchase_db.receive_purchase(po_id, received, today)
            dialog.destroy()
            # The PO write is done; leave its form cleanly and open the new invoice.
            self._form_dirty = False
            if invoice_id is not None:
                self.show_purchase_invoice_form(purchase_db.get_purchase(invoice_id))
            else:
                self.show_purchases()

        btns = ttk.Frame(dialog, padding=12)
        btns.pack(fill="x")
        ttk.Button(btns, text="Confirm Receipt", command=confirm).pack(side="left")
        ttk.Button(btns, text="Cancel", command=dialog.destroy).pack(side="left", padx=(8, 0))

    def show_purchase_invoice_form(self, purchase=None):
        """Create/edit a purchase invoice: supplier, date, the (manually entered)
        purchase-invoice number, an optional PO number it's linked to, product
        lines and a reconciled flag."""
        self.current_view = "purchase_form"
        self._clear_container()
        editing = purchase is not None

        ttk.Label(
            self.container, text="Edit Purchase Invoice" if editing else "New Purchase Invoice",
            font=("Consolas", 20, "bold"),
        ).pack(anchor="w", pady=(0, 12))

        head = ttk.LabelFrame(self.container, text="Purchase Invoice", padding=12)
        head.pack(anchor="w", fill="x")
        supplier_by_name = {s["name"]: s["id"] for s in db.get_all_suppliers()}
        supplier_var = tk.StringVar()
        invoice_no_var = tk.StringVar()
        po_ref_var = tk.StringVar()
        date_var = tk.StringVar(value=datetime.date.today().strftime("%d/%m/%y"))
        reconciled_var = tk.BooleanVar(value=bool(editing and purchase["reconciled"]))

        # Left column: Supplier / Invoice No.
        ttk.Label(head, text="Supplier:").grid(row=0, column=0, sticky="w", pady=6, padx=(0, 10))
        supplier_combo = AutocompleteCombobox(head, textvariable=supplier_var, width=30)
        supplier_combo.set_completion_list(list(supplier_by_name.keys()))
        supplier_combo.grid(row=0, column=1, sticky="w", pady=6)

        ttk.Label(head, text="Invoice No:").grid(row=1, column=0, sticky="w", pady=6, padx=(0, 10))
        invoice_entry = ttk.Entry(head, textvariable=invoice_no_var, width=32)
        invoice_entry.grid(row=1, column=1, sticky="w", pady=6)

        # Right column: PO Number (the link) / Date.
        ttk.Label(head, text="PO Number:").grid(row=0, column=2, sticky="w", pady=6, padx=(30, 10))
        ttk.Entry(head, textvariable=po_ref_var, width=24).grid(row=0, column=3, sticky="w", pady=6)

        ttk.Label(head, text="Date:").grid(row=1, column=2, sticky="w", pady=6, padx=(30, 10))
        ttk.Entry(head, textvariable=date_var, width=24).grid(row=1, column=3, sticky="w", pady=6)

        ttk.Checkbutton(head, text="Reconciled", variable=reconciled_var,
                        command=self.mark_form_dirty).grid(
            row=2, column=2, columnspan=2, sticky="w", pady=(6, 0))

        editor = self._purchase_lines_editor(self.container, editable=True)

        def save():
            supplier_id = self._resolve_supplier(supplier_by_name, supplier_var.get())
            if supplier_id is None:
                messagebox.showwarning("Supplier", "Please choose a valid supplier.")
                return None
            invoice_no = invoice_no_var.get().strip()
            if not invoice_no:
                messagebox.showwarning("Invoice number",
                                       "Please enter the purchase invoice number.")
                return None
            if not editor["lines"]:
                messagebox.showwarning("No products", "Add at least one product line.")
                return None
            items = [
                {"product_id": ln["product_id"], "quantity": ln["quantity"],
                 "cost_price": ln["cost_price"], "vat_rate": ln["vat_rate"]}
                for ln in editor["lines"]
            ]
            args = (supplier_id, "Invoice", invoice_no, date_var.get().strip(), items,
                    int(reconciled_var.get()), po_ref_var.get().strip())
            if editing:
                purchase_db.update_purchase(purchase["id"], *args)
                return purchase["id"]
            return purchase_db.create_purchase(*args)

        self._register_form(save=save, back=self.show_purchases)

        if editing:
            supplier_var.set(purchase["supplier_name"])
            invoice_no_var.set(purchase["reference"] or "")
            po_ref_var.set(purchase["po_reference"] or "")
            date_var.set(purchase["date"] or "")
            self._prefill_lines(editor, purchase["id"])
            # Raised from a PO: the invoice number is what's still needed.
            if not purchase["reference"]:
                invoice_entry.focus_set()

    def show_credit_note(self):
        """Placeholder for the upcoming Credit Note feature."""
        self.current_view = "credit_note"
        self._clear_container()
        ttk.Label(self.container, text="New Credit Note", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            self.container,
            text="Credit notes aren't built yet — coming soon.",
        ).pack(anchor="w", pady=(10, 0))

    # ------------------------------------------------------- Product Allocation
