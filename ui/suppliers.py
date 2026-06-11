"""Supplier screens (mixin for App)."""
import tkinter as tk
from tkinter import ttk, messagebox

from core import suppliers as db
from core import payments as payment_db
from core import purchases as purchase_db

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
                    balance = payment_db.supplier_balance(s["id"])
                    tree.insert(
                        "",
                        "end",
                        iid=str(s["id"]),
                        values=(
                            s["name"], s["account_number"], s["contact"],
                            s["email"], s["phone"], f"{balance:,.2f}",
                        ),
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

        columns = ("name", "account_number", "contact", "email", "phone", "balance")
        headings = ("Name", "Account #", "Contact", "Email", "Phone", "Balance")
        tree = ttk.Treeview(self.container, columns=columns, show="headings")
        for col, heading in zip(columns, headings):
            tree.heading(col, text=heading)
            tree.column(col, width=130)
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

        ttk.Label(
            self.container,
            text="Double-click or Enter to edit · Delete key to remove the selected supplier.",
            foreground="#666666",
        ).pack(anchor="w", pady=(6, 0))

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
            font=("Segoe UI", 20, "bold"),
        ).pack(anchor="w", pady=(0, 15))

        notebook = ttk.Notebook(self.container)
        notebook.pack(fill="both", expand=True)

        # --- Details tab (the editable fields) ---
        details = ttk.Frame(notebook, padding=12)
        notebook.add(details, text="Details")

        entries = {}
        fields = [
            ("name", "Name"),
            ("account_number", "Account #"),
            ("contact", "Contact"),
            ("email", "Email"),
            ("phone", "Phone"),
        ]
        for row, (key, label) in enumerate(fields):
            ttk.Label(details, text=label + ":").grid(row=row, column=0, sticky="w", pady=5, padx=(0, 10))
            entry = ttk.Entry(details, width=40)
            entry.grid(row=row, column=1, pady=5)
            if editing:
                entry.insert(0, supplier[key] or "")
            entries[key] = entry

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
                if editing:
                    db.update_supplier(
                        supplier["id"], data["name"], data["account_number"],
                        data["contact"], data["email"], data["phone"],
                    )
                    return supplier["id"]
                return db.add_supplier(
                    data["name"], data["account_number"],
                    data["contact"], data["email"], data["phone"],
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

    def _build_supplier_payments_tab(self, notebook, supplier_id):
        """Searchable list of the supplier's payments. Double-click (or Enter) a
        payment to open its allocation screen, Delete to remove it; new payments
        are made via the Suppliers → New Payment menu."""
        tab = ttk.Frame(notebook, padding=12)
        notebook.add(tab, text="Payments")
        rows = payment_db.get_payments(supplier_id)

        def cells(r):
            return {
                "date": r["date"] or "",
                "account": f"{r['account_code']} - {r['account_name']}",
                "method": r["method"] or "",
                "amount": f"{r['amount']:,.2f}",
                "unallocated": f"{r['unallocated']:,.2f}",
                "invoices": r["invoices"] or "",
            }

        def delete_payment(pid):
            row = next((r for r in rows if r["id"] == pid), None)
            label = f"{row['date'] or ''} · {row['amount']:,.2f}" if row else str(pid)
            if messagebox.askyesno("Delete payment", f"Delete payment ({label})?"):
                payment_db.delete_payment(pid)
                # Rebuild the form so the Payments tab reflects the deletion.
                self._form_dirty = False
                self.show_supplier_form(db.get_supplier(supplier_id))

        self._searchable_table(
            tab,
            columns=("date", "account", "method", "amount", "unallocated", "invoices"),
            headings=("Date", "Account", "Method", "Amount", "Unallocated", "Invoices"),
            rows=rows, cells=cells,
            widths=(90, 150, 60, 80, 90, 180),
            right_cols=("amount", "unallocated"),
            field_labels=[("All", None), ("Date", "date"), ("Account", "account"),
                          ("Method", "method"), ("Invoices", "invoices")],
            empty_text="No payments yet.",
            iid=lambda r: str(r["id"]),
            on_open=self.show_payment_allocation,
            on_delete=delete_payment,
        )
        ttk.Label(
            tab, text="Double-click to allocate · Delete to remove.",
            foreground="#666666",
        ).pack(anchor="w", pady=(4, 0))

    def _build_supplier_purchases_tab(self, notebook, supplier_id):
        """Searchable, read-only list of the supplier's purchases (orders/invoices)."""
        tab = ttk.Frame(notebook, padding=12)
        notebook.add(tab, text="Purchases")
        rows = purchase_db.supplier_purchases(supplier_id)

        def cells(r):
            return {
                "reference": r["reference"] or "",
                "status": r["status"],
                "date": r["date"] or "",
                "total": f"{r['total']:,.2f}",
            }

        self._searchable_table(
            tab,
            columns=("reference", "status", "date", "total"),
            headings=("Reference", "Status", "Date", "Total"),
            rows=rows, cells=cells,
            widths=(150, 90, 110, 110),
            right_cols=("total",),
            field_labels=[("All", None), ("Reference", "reference"),
                          ("Status", "status"), ("Date", "date")],
            empty_text="No purchases yet.",
        )
