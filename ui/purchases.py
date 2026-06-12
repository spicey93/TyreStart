"""Purchase screens (mixin for App)."""
import datetime
import tkinter as tk
from tkinter import ttk
from ui import dialogs as messagebox

from core import suppliers as db
from core import purchases as purchase_db
from core import products as product_db
from core import money
from core import daterange

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
            bar, state="readonly", width=12, textvariable=status_choice,
            values=["All", "Order", "Invoice", "Credit Note"],
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
                        daterange.format_stored(r["date"]), f"{r['total']:,.2f}",
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

        refresh()

    def open_purchase(self, purchase):
        """Open a purchase in the right editor for its type."""
        if purchase["status"] == "Order":
            self.show_purchase_order_form(purchase)
        elif purchase["status"] == "Credit Note":
            self.show_credit_note_form(purchase)
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
        """Build the product-lines table + totals (the table only — the Add Product
        button lives in the form's Actions panel and calls the returned `add`).

        Lines are removed by pressing Delete on a row or setting its Qty to 0.
        When `editable` is False the lines are shown read-only. Returns a dict with
        `lines` (the working list), `refresh()` and `add()` (opens the picker).
        """
        ttk.Label(parent, text="Products", font=("Consolas", 12, "bold")).pack(
            anchor="w", pady=(15, 5))

        lines = []

        def receive_basket(items):
            lines.extend(items)
            refresh_lines()
            self.mark_form_dirty()

        def add_product():
            self.open_product_allocation(receive_basket)

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

        return {"lines": lines, "refresh": refresh_lines, "tree": tree, "add": add_product}

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

        actions = ttk.LabelFrame(self.container, text="Actions", padding=8)
        if not received:
            actions.pack(fill="x", pady=(12, 0))
        editor = self._purchase_lines_editor(self.container, editable=not received)
        if not received:
            ttk.Button(actions, text="Add Product", command=editor["add"]).pack(side="left")
            if editing:
                ttk.Button(actions, text="Receive / Deliver",
                           command=lambda: self._receive_purchase_order(purchase["id"])).pack(
                    side="left", padx=(8, 0))

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
            date_var.set(daterange.format_stored(purchase["date"]))
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
        """Create/edit a purchase invoice (manually entered invoice number, optional
        linked PO number)."""
        self._purchase_document_form(
            purchase, "Invoice", panel_title="Purchase Invoice",
            new_title="New Purchase Invoice", edit_title="Edit Purchase Invoice",
            number_label="Invoice No", link_label="PO Number")

    def show_credit_note_form(self, purchase=None, from_invoice=None):
        """Create/edit a purchase credit note.

        Two entry points: from the menu it opens **blank** — add products from
        stock to return; or from a purchase invoice's *Create Credit Note* button
        it's **seeded** with that invoice's lines (`from_invoice`) so you set a
        Returned qty per line and it's linked to that invoice. The Returned qty
        drives the net total, the stock-out and the supplier-balance reduction.
        The number is auto-generated; Credit Ref / Return Ref are free text."""
        self.current_view = "purchase_form"
        self._clear_container()
        editing = purchase is not None

        ttk.Label(
            self.container, text="Edit Credit Note" if editing else "New Credit Note",
            font=("Consolas", 20, "bold"),
        ).pack(anchor="w", pady=(0, 12))

        head = ttk.LabelFrame(self.container, text="Credit Note", padding=12)
        head.pack(anchor="w", fill="x")
        supplier_by_name = {s["name"]: s["id"] for s in db.get_all_suppliers()}
        supplier_var = tk.StringVar()
        credit_ref_var = tk.StringVar()
        return_ref_var = tk.StringVar()
        date_var = tk.StringVar(value=datetime.date.today().strftime("%d/%m/%y"))

        # The invoice this note credits (if any) — set when seeded or editing.
        if from_invoice is not None:
            linked_ref = from_invoice["reference"] or ""
        elif editing:
            linked_ref = purchase["po_reference"] or ""
        else:
            linked_ref = ""

        # Left column: Supplier / Date.
        ttk.Label(head, text="Supplier:").grid(row=0, column=0, sticky="w", pady=6, padx=(0, 10))
        supplier_combo = AutocompleteCombobox(head, textvariable=supplier_var, width=30)
        supplier_combo.set_completion_list(list(supplier_by_name.keys()))
        supplier_combo.grid(row=0, column=1, sticky="w", pady=6)

        ttk.Label(head, text="Date:").grid(row=1, column=0, sticky="w", pady=6, padx=(0, 10))
        ttk.Entry(head, textvariable=date_var, width=20).grid(row=1, column=1, sticky="w", pady=6)

        ttk.Label(head, text="Invoice:").grid(row=2, column=0, sticky="w", pady=6, padx=(0, 10))
        ttk.Label(head, text=linked_ref or "—", font=("Consolas", 11, "bold")).grid(
            row=2, column=1, sticky="w", pady=6)

        # Right column: CN number (auto) / Credit Ref / Return Ref.
        ttk.Label(head, text="Credit Note No:").grid(row=0, column=2, sticky="w", pady=6, padx=(30, 10))
        cn_number = purchase["reference"] if editing else "(auto-generated on save)"
        ttk.Label(head, text=cn_number, font=("Consolas", 11, "bold")).grid(
            row=0, column=3, sticky="w", pady=6)

        ttk.Label(head, text="Credit Ref:").grid(row=1, column=2, sticky="w", pady=6, padx=(30, 10))
        ttk.Entry(head, textvariable=credit_ref_var, width=24).grid(row=1, column=3, sticky="w", pady=6)

        ttk.Label(head, text="Return Ref:").grid(row=2, column=2, sticky="w", pady=6, padx=(30, 10))
        ttk.Entry(head, textvariable=return_ref_var, width=24).grid(row=2, column=3, sticky="w", pady=6)

        # --- Actions (above the lines, like the other purchase forms) ---
        actions = ttk.LabelFrame(self.container, text="Actions", padding=8)
        actions.pack(fill="x", pady=(12, 0))

        # --- Credit lines ---
        ttk.Label(self.container, text="Lines to return", font=("Consolas", 12, "bold")).pack(
            anchor="w", pady=(15, 5))

        lines = []

        def receive_basket(items):
            for it in items:  # products added from stock to return
                lines.append({
                    "product_id": it["product_id"], "stock_code": it["stock_code"],
                    "description": it["description"], "invoiced": None,
                    "returned": it["quantity"], "cost_price": it["cost_price"],
                    "vat_rate": it["vat_rate"],
                })
            refresh_grid()
            self.mark_form_dirty()

        ttk.Button(
            actions, text="Add Product",
            command=lambda: self.open_product_allocation(
                receive_basket, price_label="Unit Cost (net)",
                price_fn=lambda p: product_db.average_cost(p["id"])),
        ).pack(side="left")

        lt_frame = ttk.Frame(self.container)
        lt_frame.pack(fill="both", expand=True, pady=(4, 0))
        columns = ("stock_code", "description", "invoiced", "returned", "cost", "net")
        headings = ("Stock Code", "Description", "Invoiced", "Returned", "Unit Cost", "Net Total")
        widths = (120, 240, 70, 70, 80, 100)
        tree = ttk.Treeview(lt_frame, columns=columns, show="headings", height=7)
        for col, heading, width in zip(columns, headings, widths):
            tree.heading(col, text=heading)
            tree.column(col, width=width,
                        anchor=("e" if col in ("invoiced", "returned", "cost", "net") else "w"))
        make_sortable(tree)
        ls = ttk.Scrollbar(lt_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=ls.set)
        ls.pack(side="right", fill="y")
        tree.pack(side="left", fill="both", expand=True)

        total_label = ttk.Label(self.container, text="Net 0.00   VAT 0.00   Gross 0.00",
                                font=("Consolas", 10, "bold"))
        total_label.pack(anchor="e", pady=(6, 0))

        def refresh_grid():
            tree.delete(*tree.get_children())
            net_total = vat_total = gross_total = 0.0
            for i, ln in enumerate(lines):
                net, vat, gross = money.line_amounts(ln["returned"], ln["cost_price"], ln["vat_rate"])
                net_total += net
                vat_total += vat
                gross_total += gross
                tree.insert("", "end", iid=str(i), values=(
                    ln["stock_code"], ln["description"],
                    "" if ln["invoiced"] is None else ln["invoiced"], ln["returned"],
                    f"{ln['cost_price']:.2f}", f"{net:,.2f}"))
            total_label.config(
                text=f"Net {net_total:,.2f}   VAT {vat_total:,.2f}   Gross {gross_total:,.2f}")

        def edit_returned(event):
            if tree.identify("region", event.x, event.y) != "cell":
                return
            if tree.identify_column(event.x) != "#4":  # Returned only
                return
            rowid = tree.identify_row(event.y)
            if not rowid:
                return
            index = int(rowid)
            bbox = tree.bbox(rowid, "#4")
            if not bbox:
                return
            x, y, w, h = bbox
            editor = ttk.Entry(tree)
            editor.place(x=x, y=y, width=w, height=h)
            editor.insert(0, str(lines[index]["returned"]))
            editor.select_range(0, "end")
            editor.focus_set()

            def commit(_=None):
                raw = editor.get().strip()
                try:
                    value = int(raw)
                    if value < 0:
                        raise ValueError
                except ValueError:
                    editor.destroy()
                    return
                editor.destroy()
                lines[index]["returned"] = value
                refresh_grid()
                self.mark_form_dirty()

            editor.bind("<Return>", commit)
            editor.bind("<FocusOut>", commit)
            editor.bind("<Escape>", lambda e: editor.destroy())

        def delete_selected(event=None):
            sel = tree.selection()
            if sel:
                del lines[int(sel[0])]
                refresh_grid()
                self.mark_form_dirty()
            return "break"

        tree.bind("<Double-1>", edit_returned)
        tree.bind("<Delete>", delete_selected)

        def save():
            supplier_id = self._resolve_supplier(supplier_by_name, supplier_var.get())
            if supplier_id is None:
                messagebox.showwarning("Supplier", "Please choose a valid supplier.")
                return None
            items = [
                {"product_id": ln["product_id"], "quantity": ln["returned"],
                 "cost_price": ln["cost_price"], "vat_rate": ln["vat_rate"]}
                for ln in lines if ln["returned"] > 0
            ]
            if not items:
                messagebox.showwarning("Nothing to return",
                                       "Add a product and/or set a Returned quantity.")
                return None
            reference = purchase["reference"] if editing else ""
            args = (supplier_id, "Credit Note", reference, date_var.get().strip(), items,
                    int(editing and purchase["reconciled"]), linked_ref,
                    credit_ref_var.get().strip(), return_ref_var.get().strip())
            if editing:
                purchase_db.update_purchase(purchase["id"], *args)
                return purchase["id"]
            return purchase_db.create_purchase(*args)

        self._register_form(save=save, back=self.show_purchases)

        if from_invoice is not None:  # seeded from an invoice: pull its lines
            supplier_var.set(from_invoice["supplier_name"])
            for it in purchase_db.get_purchase_items(from_invoice["id"]):
                lines.append({
                    "product_id": it["product_id"], "stock_code": it["stock_code"],
                    "description": it["description"], "invoiced": it["quantity"],
                    "returned": it["quantity"], "cost_price": it["cost_price"],
                    "vat_rate": it["vat_rate"]})
            refresh_grid()
            self.mark_form_dirty()
        elif editing:
            supplier_var.set(purchase["supplier_name"])
            credit_ref_var.set(purchase["credit_reference"] or "")
            return_ref_var.set(purchase["return_reference"] or "")
            date_var.set(daterange.format_stored(purchase["date"]))
            # Look up the credited invoice's quantities for the Invoiced column.
            invoiced_by_product = {}
            if linked_ref:
                for inv in purchase_db.supplier_invoices(purchase["supplier_id"]):
                    if (inv["reference"] or "") == linked_ref:
                        invoiced_by_product = {
                            it["product_id"]: it["quantity"]
                            for it in purchase_db.get_purchase_items(inv["id"])}
                        break
            for it in purchase_db.get_purchase_items(purchase["id"]):
                lines.append({
                    "product_id": it["product_id"], "stock_code": it["stock_code"],
                    "description": it["description"],
                    "invoiced": invoiced_by_product.get(it["product_id"]),
                    "returned": it["quantity"], "cost_price": it["cost_price"],
                    "vat_rate": it["vat_rate"]})
            refresh_grid()

    def _purchase_document_form(self, purchase, status, *, panel_title, new_title,
                                edit_title, number_label, link_label):
        """Shared editor for the invoice-style purchase documents (Purchase Invoice
        and Credit Note). Both carry a manually-entered document number
        (`reference`), an optional linked document number (`po_reference`), a date,
        product lines and a reconciled flag — only the wording and status differ."""
        self.current_view = "purchase_form"
        self._clear_container()
        editing = purchase is not None

        ttk.Label(
            self.container, text=edit_title if editing else new_title,
            font=("Consolas", 20, "bold"),
        ).pack(anchor="w", pady=(0, 12))

        head = ttk.LabelFrame(self.container, text=panel_title, padding=12)
        head.pack(anchor="w", fill="x")
        supplier_by_name = {s["name"]: s["id"] for s in db.get_all_suppliers()}
        supplier_var = tk.StringVar()
        number_var = tk.StringVar()
        link_var = tk.StringVar()
        date_var = tk.StringVar(value=datetime.date.today().strftime("%d/%m/%y"))
        reconciled_var = tk.BooleanVar(value=bool(editing and purchase["reconciled"]))

        # Left column: Supplier / document number.
        ttk.Label(head, text="Supplier:").grid(row=0, column=0, sticky="w", pady=6, padx=(0, 10))
        supplier_combo = AutocompleteCombobox(head, textvariable=supplier_var, width=30)
        supplier_combo.set_completion_list(list(supplier_by_name.keys()))
        supplier_combo.grid(row=0, column=1, sticky="w", pady=6)

        ttk.Label(head, text=number_label + ":").grid(row=1, column=0, sticky="w", pady=6, padx=(0, 10))
        number_entry = ttk.Entry(head, textvariable=number_var, width=32)
        number_entry.grid(row=1, column=1, sticky="w", pady=6)

        # Right column: linked document number / date.
        ttk.Label(head, text=link_label + ":").grid(row=0, column=2, sticky="w", pady=6, padx=(30, 10))
        ttk.Entry(head, textvariable=link_var, width=24).grid(row=0, column=3, sticky="w", pady=6)

        ttk.Label(head, text="Date:").grid(row=1, column=2, sticky="w", pady=6, padx=(30, 10))
        ttk.Entry(head, textvariable=date_var, width=24).grid(row=1, column=3, sticky="w", pady=6)

        ttk.Checkbutton(head, text="Reconciled", variable=reconciled_var,
                        command=self.mark_form_dirty).grid(
            row=2, column=2, columnspan=2, sticky="w", pady=(6, 0))

        actions = ttk.LabelFrame(self.container, text="Actions", padding=8)
        actions.pack(fill="x", pady=(12, 0))
        editor = self._purchase_lines_editor(self.container, editable=True)
        ttk.Button(actions, text="Add Product", command=editor["add"]).pack(side="left")
        # From a saved invoice you can raise a credit note seeded with its lines.
        if editing and status == "Invoice":
            ttk.Button(
                actions, text="Create Credit Note",
                command=lambda: (setattr(self, "_form_dirty", False),
                                 self.show_credit_note_form(from_invoice=purchase))[-1],
            ).pack(side="left", padx=(8, 0))

        def save():
            supplier_id = self._resolve_supplier(supplier_by_name, supplier_var.get())
            if supplier_id is None:
                messagebox.showwarning("Supplier", "Please choose a valid supplier.")
                return None
            number = number_var.get().strip()
            if not number:
                messagebox.showwarning(number_label, f"Please enter the {number_label}.")
                return None
            if not editor["lines"]:
                messagebox.showwarning("No products", "Add at least one product line.")
                return None
            items = [
                {"product_id": ln["product_id"], "quantity": ln["quantity"],
                 "cost_price": ln["cost_price"], "vat_rate": ln["vat_rate"]}
                for ln in editor["lines"]
            ]
            args = (supplier_id, status, number, date_var.get().strip(), items,
                    int(reconciled_var.get()), link_var.get().strip())
            if editing:
                purchase_db.update_purchase(purchase["id"], *args)
                return purchase["id"]
            return purchase_db.create_purchase(*args)

        self._register_form(save=save, back=self.show_purchases)

        if editing:
            supplier_var.set(purchase["supplier_name"])
            number_var.set(purchase["reference"] or "")
            link_var.set(purchase["po_reference"] or "")
            date_var.set(daterange.format_stored(purchase["date"]))
            self._prefill_lines(editor, purchase["id"])
            # Raised from a PO (blank number): the document number is what's needed.
            if not purchase["reference"]:
                number_entry.focus_set()

    # ------------------------------------------------------- Product Allocation
