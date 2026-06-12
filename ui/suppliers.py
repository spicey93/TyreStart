"""Supplier screens (mixin for App)."""
import tkinter as tk
from tkinter import ttk
from ui import dialogs as messagebox

from core import suppliers as db
from core import payments as payment_db
from core import purchases as purchase_db
from core import daterange

from ui import theme
from ui.common import make_sortable


class SuppliersMixin:
    def show_all_suppliers(self):
        self.current_view = "suppliers"
        self._clear_container()

        header = ttk.Frame(self.container)
        header.pack(fill="x", pady=(0, 10))
        ttk.Label(
            header,
            text="Suppliers",
            font=("Consolas", 20, "bold"),
        ).pack(side="left")

        # Two dedicated search boxes — Account # and Name — instead of one box
        # plus a field dropdown. Either (or neither) may be filled; an empty box
        # doesn't restrict, so searching works with no filters applied.
        search_frame = ttk.Frame(self.container)
        search_frame.pack(fill="x", pady=(0, 10))

        acc_term = tk.StringVar()
        name_term = tk.StringVar()

        ttk.Label(search_frame, text="Account #:").grid(row=0, column=0, sticky="w")
        acc_entry = ttk.Entry(search_frame, textvariable=acc_term, width=18)
        acc_entry.grid(row=0, column=1, sticky="w", padx=(8, 16))
        acc_entry.focus_set()
        acc_entry.bind("<Return>", lambda e: do_search())

        ttk.Label(search_frame, text="Name:").grid(row=0, column=2, sticky="w")
        name_entry = ttk.Entry(search_frame, textvariable=name_term, width=28)
        name_entry.grid(row=0, column=3, sticky="w", padx=(8, 16))
        name_entry.bind("<Return>", lambda e: do_search())

        def refresh_tree():
            acc = acc_term.get().strip().lower()
            name = name_term.get().strip().lower()
            tree.delete(*tree.get_children())
            for s in db.get_all_suppliers():
                if acc and acc not in (s["account_number"] or "").lower():
                    continue
                if name and name not in (s["name"] or "").lower():
                    continue
                balance = payment_db.supplier_balance(s["id"])
                tree.insert(
                    "", "end", iid=str(s["id"]),
                    values=(
                        s["name"], s["account_number"], s["status"] or "",
                        s["phone"], f"{(s['credit_limit'] or 0):,.2f}",
                        f"{balance:,.2f}",
                    ),
                )
            if not tree.get_children():
                if acc or name:
                    status_label.config(text="No suppliers match the current search.")
                else:
                    status_label.config(text="No suppliers yet. Use Create Supplier to add one.")
            else:
                status_label.config(text="")

        def clear_search():
            acc_term.set("")
            name_term.set("")
            refresh_tree()
            acc_entry.focus_set()

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

        columns = ("name", "account_number", "status", "phone", "credit_limit", "balance")
        headings = ("Name", "Account #", "Status", "Phone", "Credit Limit", "Balance")
        tree = ttk.Treeview(self.container, columns=columns, show="headings")
        for col, heading in zip(columns, headings):
            tree.heading(col, text=heading)
            tree.column(col, width=130)
        tree.column("credit_limit", anchor="e", width=100)
        tree.column("balance", anchor="e", width=100)
        make_sortable(tree)
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

        def delete_selected(event=None):
            selection = tree.selection()
            if not selection:
                return
            sid = int(selection[0])
            supplier = db.get_supplier(sid)
            if supplier and messagebox.askyesno(
                "Delete supplier", f"Delete '{supplier['name']}'?"
            ):
                db.delete_supplier(sid)
                refresh_tree()

        # Double-clicking or pressing Enter on a row opens that supplier;
        # Delete removes the selected one (deletion lives here, not on the form).
        tree.bind("<Double-1>", lambda e: edit_selected())
        tree.bind("<Return>", lambda e: edit_selected())
        tree.bind("<Delete>", delete_selected)

        refresh_tree()

    def show_create_supplier(self):
        self.show_supplier_form()

    def show_supplier_form(self, supplier=None):
        """Create (supplier=None) or edit a supplier.

        Editing shows Details / Payments / Purchases tabs. There are no
        Save/Cancel/Delete buttons: edits are saved when leaving the page (you're
        asked first), Esc leaves back to the list, and deletion lives on the list.
        """
        self.current_view = "form"
        self._clear_container()
        editing = supplier is not None
        ttk.Label(
            self.container,
            text="Edit Supplier" if editing else "Create Supplier",
            font=("Consolas", 20, "bold"),
        ).pack(anchor="w", pady=(0, 15))

        notebook = ttk.Notebook(self.container)
        notebook.pack(fill="both", expand=True)

        # --- Details tab (the editable fields) ---
        details = ttk.Frame(notebook, padding=12)
        notebook.add(details, text="Details")

        entries = {}

        def add_field(key, label, row, col, fmt=None):
            """A label + entry on the details grid. `col` 0 = left pair, 1 = right."""
            ttk.Label(details, text=label + ":").grid(
                row=row, column=col * 2, sticky="w", pady=5, padx=(24 if col else 0, 10))
            entry = ttk.Entry(details, width=28)
            entry.grid(row=row, column=col * 2 + 1, sticky="w", pady=5)
            if editing and supplier[key] is not None:
                entry.insert(0, fmt(supplier[key]) if fmt else supplier[key])
            entries[key] = entry
            return entry

        # Left column: the original contact details.
        add_field("name", "Name", 0, 0)
        add_field("account_number", "Account #", 1, 0)
        add_field("contact", "Contact", 2, 0)
        add_field("email", "Email", 3, 0)
        add_field("phone", "Phone", 4, 0)

        # Right column: account / accounting fields. Status and Payment method are
        # dropdowns; the rest are entries.
        status_var = tk.StringVar(value=(supplier["status"] if editing and supplier["status"] else "Open"))
        ttk.Label(details, text="Status:").grid(row=0, column=2, sticky="w", pady=5, padx=(24, 10))
        ttk.Combobox(details, state="readonly", width=26, textvariable=status_var,
                     values=list(db.STATUSES)).grid(row=0, column=3, sticky="w", pady=5)

        add_field("address", "Address", 1, 1)
        add_field("postcode", "Postcode", 2, 1)
        add_field("credit_limit", "Credit Limit", 3, 1, fmt=lambda v: f"{(v or 0):.2f}")
        add_field("vat_code", "VAT Code", 4, 1)
        add_field("vat_number", "VAT Number", 5, 1)

        method_var = tk.StringVar(value=(supplier["payment_method"] if editing and supplier["payment_method"] else ""))
        ttk.Label(details, text="Payment Method:").grid(row=6, column=2, sticky="w", pady=5, padx=(24, 10))
        ttk.Combobox(details, state="readonly", width=26, textvariable=method_var,
                     values=("", *payment_db.METHODS)).grid(row=6, column=3, sticky="w", pady=5)
        ttk.Label(details, text="(used as the default when adding a payment)",
                  style="Hint.TLabel").grid(row=7, column=2, columnspan=2, sticky="w")

        if editing:
            # --- Payments & Purchases tabs (existing supplier only) ---
            self._build_supplier_payments_tab(notebook, supplier["id"])
            self._build_supplier_purchases_tab(notebook, supplier["id"])

        def save():
            """Persist the Details fields. Returns the supplier id on success, or
            None if validation/uniqueness fails (so the caller can stay put)."""
            data = {key: entry.get().strip() for key, entry in entries.items()}
            if not data["name"]:
                messagebox.showwarning("Missing name", "Please enter a supplier name.")
                return None
            try:
                credit = float(data["credit_limit"]) if data["credit_limit"] else 0.0
            except ValueError:
                messagebox.showwarning("Invalid credit limit", "Credit limit must be a number.")
                return None
            extra = dict(
                status=status_var.get(), address=data["address"],
                postcode=data["postcode"], credit_limit=credit,
                vat_code=data["vat_code"], vat_number=data["vat_number"],
                payment_method=method_var.get(),
            )
            try:
                if editing:
                    db.update_supplier(
                        supplier["id"], data["name"], data["account_number"],
                        data["contact"], data["email"], data["phone"], **extra,
                    )
                    return supplier["id"]
                return db.add_supplier(
                    data["name"], data["account_number"],
                    data["contact"], data["email"], data["phone"], **extra,
                )
            except db.DuplicateNameError:
                messagebox.showerror(
                    "Duplicate name",
                    f"A supplier named '{data['name']}' already exists.",
                )
                return None

        self._register_form(save=save, back=self.show_all_suppliers)
        # Ctrl+1/Ctrl+2/… switch tabs (added after _register_form resets the list).
        self._bind_tab_shortcuts(notebook)

    @staticmethod
    def _filter_combo(bar, label, column, values):
        """A labelled readonly filter combobox on `bar`'s row 0. Returns its var."""
        ttk.Label(bar, text=label).grid(row=0, column=column, sticky="w", padx=(10, 6))
        var = tk.StringVar(value=values[0])
        combo = ttk.Combobox(bar, state="readonly", width=max(6, len(max(values, key=len))),
                             textvariable=var, values=list(values))
        combo.grid(row=0, column=column + 1, padx=(0, 4))
        combo.current(0)
        combo._ignore_dirty = True  # a filter, not a record field
        return var, combo

    @staticmethod
    def _filtered_table(tab, columns, headings, widths, right_cols):
        """Build a scrollable Treeview for a filtered tab; returns (tree, status)."""
        table_frame = ttk.Frame(tab)
        table_frame.pack(fill="both", expand=True)
        tree = ttk.Treeview(table_frame, columns=columns, show="headings")
        sb = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        tree.pack(side="left", fill="both", expand=True)
        for col, heading, width in zip(columns, headings, widths):
            tree.heading(col, text=heading)
            tree.column(col, width=width)
        for col in right_cols:
            tree.column(col, anchor="e")
        make_sortable(tree)
        status = ttk.Label(tab, text="")
        status.pack(anchor="w", pady=(8, 0))
        return tree, status

    def _build_supplier_payments_tab(self, notebook, supplier_id):
        """The supplier's payments, filtered by date period/range, method and
        whether they're fully allocated. Double-click to allocate, Delete to remove."""
        tab = ttk.Frame(notebook, padding=12)
        notebook.add(tab, text="Payments")
        rows = payment_db.get_payments(supplier_id)

        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 8))
        date_frame, get_range = self._make_date_filter(bar, lambda: refresh())
        date_frame.grid(row=0, column=0, sticky="w")
        method_var, method_combo = self._filter_combo(
            bar, "Method:", 1, ("All", *payment_db.METHODS))
        alloc_var, alloc_combo = self._filter_combo(
            bar, "Fully Allocated:", 3, ("All", "Yes", "No"))
        method_combo.bind("<<ComboboxSelected>>", lambda e: refresh())
        alloc_combo.bind("<<ComboboxSelected>>", lambda e: refresh())

        columns = ("date", "account", "method", "amount", "unallocated", "invoices")
        headings = ("Date", "Account", "Method", "Amount", "Unallocated", "Invoices")
        tree, status = self._filtered_table(
            tab, columns, headings, (90, 150, 60, 80, 90, 180),
            right_cols=("amount", "unallocated"))

        def refresh():
            start, end = get_range()
            method, alloc = method_var.get(), alloc_var.get()
            tree.delete(*tree.get_children())
            shown = 0
            for r in rows:
                if not daterange.in_range(r["date"] or "", start, end):
                    continue
                if method != "All" and (r["method"] or "") != method:
                    continue
                fully = r["unallocated"] <= 0.005
                if (alloc == "Yes" and not fully) or (alloc == "No" and fully):
                    continue
                tree.insert(
                    "", "end", iid=str(r["id"]),
                    values=(daterange.format_stored(r["date"]), f"{r['account_code']} - {r['account_name']}",
                            r["method"] or "", f"{r['amount']:,.2f}",
                            f"{r['unallocated']:,.2f}", r["invoices"] or ""))
                shown += 1
            status.config(text=(f"Showing {shown} of {len(rows)} payment(s)."
                                if rows else "No payments yet."))

        def open_selected(event=None):
            sel = tree.selection()
            if sel:
                self.show_payment_allocation(int(sel[0]))

        def delete_selected(event=None):
            sel = tree.selection()
            if not sel:
                return
            pid = int(sel[0])
            row = next((r for r in rows if r["id"] == pid), None)
            label = f"{daterange.format_stored(row['date'])} · {row['amount']:,.2f}" if row else str(pid)
            if messagebox.askyesno("Delete payment", f"Delete payment ({label})?"):
                payment_db.delete_payment(pid)
                self._form_dirty = False
                self.show_supplier_form(db.get_supplier(supplier_id))

        tree.bind("<Double-1>", open_selected)
        tree.bind("<Return>", open_selected)
        tree.bind("<Delete>", delete_selected)
        refresh()

    def _build_supplier_purchases_tab(self, notebook, supplier_id):
        """The supplier's purchases, filtered by date period/range, reconciled and
        paid status. Double-click (or Enter) opens the purchase."""
        tab = ttk.Frame(notebook, padding=12)
        notebook.add(tab, text="Purchases")
        rows = purchase_db.supplier_purchases(supplier_id)

        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 8))
        date_frame, get_range = self._make_date_filter(bar, lambda: refresh())
        date_frame.grid(row=0, column=0, sticky="w")
        rec_var, rec_combo = self._filter_combo(bar, "Reconciled:", 1, ("All", "Yes", "No"))
        paid_var, paid_combo = self._filter_combo(bar, "Paid:", 3, ("All", "Yes", "No"))
        rec_combo.bind("<<ComboboxSelected>>", lambda e: refresh())
        paid_combo.bind("<<ComboboxSelected>>", lambda e: refresh())

        columns = ("reference", "status", "date", "total", "paid", "reconciled")
        headings = ("Reference", "Status", "Date", "Total", "Paid", "Reconciled")
        tree, status = self._filtered_table(
            tab, columns, headings, (140, 80, 90, 100, 50, 80), right_cols=("total",))

        def is_paid(r):
            return r["total"] > 0 and r["allocated"] >= r["total"] - 0.005

        def refresh():
            start, end = get_range()
            want_rec, want_paid = rec_var.get(), paid_var.get()
            tree.delete(*tree.get_children())
            shown = 0
            for r in rows:
                if not daterange.in_range(r["date"] or "", start, end):
                    continue
                reconciled = bool(r["reconciled"])
                if (want_rec == "Yes" and not reconciled) or (want_rec == "No" and reconciled):
                    continue
                paid = is_paid(r)
                if (want_paid == "Yes" and not paid) or (want_paid == "No" and paid):
                    continue
                tree.insert(
                    "", "end", iid=str(r["id"]),
                    values=(r["reference"] or "", r["status"], daterange.format_stored(r["date"]),
                            f"{r['total']:,.2f}", "Yes" if paid else "No",
                            "Yes" if reconciled else "No"))
                shown += 1
            status.config(text=(f"Showing {shown} of {len(rows)} purchase(s)."
                                if rows else "No purchases yet."))

        def open_selected(event=None):
            sel = tree.selection()
            if sel:
                self.open_purchase(purchase_db.get_purchase(int(sel[0])))

        tree.bind("<Double-1>", open_selected)
        tree.bind("<Return>", open_selected)
        refresh()
