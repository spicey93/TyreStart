"""Supplier-payment screens (mixin for App)."""
import datetime
import tkinter as tk
from tkinter import ttk, messagebox

import suppliers as db
import purchases as purchase_db
import payments as payment_db
import nominals

from ui_common import make_sortable


class PaymentsMixin:
    def show_payments(self, supplier_id):
        self.current_view = "payments"
        self._clear_container()
        supplier = db.get_supplier(supplier_id)

        header = ttk.Frame(self.container)
        header.pack(fill="x", pady=(0, 10))
        ttk.Label(
            header, text=f"Payments — {supplier['name']}",
            font=("Segoe UI", 20, "bold"),
        ).pack(side="left")
        ttk.Button(
            header, text="Make Payment",
            command=lambda: self.show_payment_form(supplier_id),
        ).pack(side="right")

        balance = payment_db.supplier_balance(supplier_id)
        ttk.Label(
            self.container, text=f"Balance owed: {balance:,.2f}",
            font=("Segoe UI", 12, "bold"),
        ).pack(anchor="w", pady=(0, 8))

        columns = ("date", "account", "method", "amount", "invoices")
        headings = ("Date", "Account", "Method", "Amount", "Invoices")
        widths = (110, 180, 80, 100, 240)
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
        tree.column("amount", anchor="e")
        make_sortable(tree)

        rows = payment_db.get_payments(supplier_id)
        for r in rows:
            tree.insert(
                "", "end",
                values=(
                    r["date"] or "", f"{r['account_code']} - {r['account_name']}",
                    r["method"] or "", f"{r['amount']:,.2f}", r["invoices"] or "",
                ),
            )
        ttk.Label(
            self.container,
            text=f"{len(rows)} payment(s)." if rows else "No payments yet.",
        ).pack(anchor="w", pady=(8, 0))
        ttk.Button(
            self.container, text="Back to Supplier",
            command=lambda: self.show_supplier_form(db.get_supplier(supplier_id)),
        ).pack(anchor="w", pady=(12, 0))

    def show_payment_form(self, supplier_id):
        self.current_view = "payment_form"
        self._clear_container()
        supplier = db.get_supplier(supplier_id)

        ttk.Label(
            self.container, text=f"Make Payment — {supplier['name']}",
            font=("Segoe UI", 20, "bold"),
        ).pack(anchor="w", pady=(0, 12))

        accounts = nominals.get_all()
        account_by_label = {nominals.label(a): a["id"] for a in accounts}

        head = ttk.Frame(self.container)
        head.pack(anchor="w")
        account_var = tk.StringVar()
        method_var = tk.StringVar(value=payment_db.METHODS[0])
        date_var = tk.StringVar(value=datetime.date.today().strftime("%d/%m/%y"))

        ttk.Label(head, text="From account:").grid(row=0, column=0, sticky="w", pady=4, padx=(0, 10))
        account_combo = ttk.Combobox(
            head, state="readonly", width=30, textvariable=account_var,
            values=list(account_by_label.keys()),
        )
        account_combo.grid(row=0, column=1, sticky="w", pady=4)
        if account_by_label:
            account_combo.current(0)

        ttk.Label(head, text="Method:").grid(row=1, column=0, sticky="w", pady=4, padx=(0, 10))
        method_combo = ttk.Combobox(
            head, state="readonly", width=15, textvariable=method_var,
            values=list(payment_db.METHODS),
        )
        method_combo.grid(row=1, column=1, sticky="w", pady=4)
        method_combo.current(0)

        ttk.Label(head, text="Date:").grid(row=2, column=0, sticky="w", pady=4, padx=(0, 10))
        ttk.Entry(head, textvariable=date_var, width=20).grid(row=2, column=1, sticky="w", pady=4)

        ttk.Label(
            self.container, text="Allocate to invoices",
            font=("Segoe UI", 12, "bold"),
        ).pack(anchor="w", pady=(15, 5))

        invoices = purchase_db.supplier_invoices(supplier_id, outstanding_only=True)
        alloc_vars = {}            # purchase_id -> StringVar
        outstanding_by_id = {}     # purchase_id -> outstanding amount

        if not invoices:
            ttk.Label(
                self.container,
                text="No outstanding invoices for this supplier.",
            ).pack(anchor="w")
        else:
            grid = ttk.Frame(self.container)
            grid.pack(anchor="w")
            for col, text in enumerate(["Reference", "Date", "Total", "Outstanding", "Pay"]):
                ttk.Label(grid, text=text, font=("Segoe UI", 9, "bold")).grid(
                    row=0, column=col, sticky="w", padx=(0, 12), pady=(0, 4)
                )
            for i, inv in enumerate(invoices, start=1):
                outstanding_by_id[inv["id"]] = inv["outstanding"]
                ttk.Label(grid, text=inv["reference"] or "").grid(row=i, column=0, sticky="w", padx=(0, 12))
                ttk.Label(grid, text=inv["date"] or "").grid(row=i, column=1, sticky="w", padx=(0, 12))
                ttk.Label(grid, text=f"{inv['total']:,.2f}").grid(row=i, column=2, sticky="e", padx=(0, 12))
                ttk.Label(grid, text=f"{inv['outstanding']:,.2f}").grid(row=i, column=3, sticky="e", padx=(0, 12))
                var = tk.StringVar()
                ttk.Entry(grid, textvariable=var, width=10).grid(row=i, column=4, sticky="w")
                alloc_vars[inv["id"]] = var

        total_label = ttk.Label(
            self.container, text="Payment total: 0.00", font=("Segoe UI", 10, "bold")
        )
        total_label.pack(anchor="w", pady=(10, 0))

        def recompute(*_):
            running = 0.0
            for var in alloc_vars.values():
                try:
                    running += float(var.get() or 0)
                except ValueError:
                    pass
            total_label.config(text=f"Payment total: {running:,.2f}")

        for var in alloc_vars.values():
            var.trace_add("write", recompute)

        def save():
            allocations = []
            for purchase_id, var in alloc_vars.items():
                raw = var.get().strip()
                if not raw:
                    continue
                try:
                    amount = float(raw)
                except ValueError:
                    messagebox.showwarning("Invalid amount", "Enter numeric amounts only.")
                    return
                if amount <= 0:
                    continue
                if amount - outstanding_by_id[purchase_id] > 0.005:
                    messagebox.showwarning(
                        "Too much", "An allocation exceeds the invoice's outstanding amount."
                    )
                    return
                allocations.append({"purchase_id": purchase_id, "amount": round(amount, 2)})
            if not allocations:
                messagebox.showwarning(
                    "Nothing to pay", "Enter an amount against at least one invoice."
                )
                return
            account_id = account_by_label.get(account_var.get())
            if account_id is None:
                messagebox.showwarning("Account", "Choose an account to pay from.")
                return
            payment_db.create_payment(
                supplier_id, account_id, method_var.get(),
                date_var.get().strip(), allocations,
            )
            messagebox.showinfo("Saved", "Payment recorded.")
            self.show_payments(supplier_id)

        cancel = self._discard_guard(lambda: self.show_payments(supplier_id))
        btns = ttk.Frame(self.container)
        btns.pack(anchor="w", pady=(15, 0))
        ttk.Button(btns, text="Save Payment (Ctrl+S)", command=save).pack(side="left")
        ttk.Button(btns, text="Cancel (Esc)", command=cancel).pack(side="left", padx=(8, 0))
        self._bind_form_shortcuts(save=save, cancel=cancel)

    # ------------------------------------------------------------------- Services
