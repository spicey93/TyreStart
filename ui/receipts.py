"""Customer-receipt screens (mixin for App)."""
import datetime
import tkinter as tk
from tkinter import ttk, messagebox

from core import nominals
from core import customers as customer_db
from core import sales as sale_db
from core import receipts as receipt_db

from ui.common import make_sortable


class ReceiptsMixin:
    def show_receipts(self, customer_id):
        self.current_view = "receipts"
        self._clear_container()
        customer = customer_db.get_customer(customer_id)

        header = ttk.Frame(self.container)
        header.pack(fill="x", pady=(0, 10))
        ttk.Label(
            header, text=f"Receipts — {customer['name']}",
            font=("Segoe UI", 20, "bold"),
        ).pack(side="left")
        ttk.Button(
            header, text="Record Receipt",
            command=lambda: self.show_receipt_form(customer_id),
        ).pack(side="right")

        balance = receipt_db.customer_balance(customer_id)
        ttk.Label(
            self.container, text=f"Balance owed by customer: {balance:,.2f}",
            font=("Segoe UI", 12, "bold"),
        ).pack(anchor="w", pady=(0, 8))

        columns = ("date", "account", "method", "amount", "sales")
        headings = ("Date", "Account", "Method", "Amount", "Sales")
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

        rows = receipt_db.get_receipts(customer_id)
        for r in rows:
            tree.insert(
                "", "end",
                values=(
                    r["date"] or "", f"{r['account_code']} - {r['account_name']}",
                    r["method"] or "", f"{r['amount']:,.2f}", r["sales"] or "",
                ),
            )
        ttk.Label(
            self.container,
            text=f"{len(rows)} receipt(s)." if rows else "No receipts yet.",
        ).pack(anchor="w", pady=(8, 0))
        ttk.Button(
            self.container, text="Back to Customer",
            command=lambda: self.show_customer_form(customer_db.get_customer(customer_id)),
        ).pack(anchor="w", pady=(12, 0))

    def show_receipt_form(self, customer_id):
        self.current_view = "receipt_form"
        self._clear_container()
        customer = customer_db.get_customer(customer_id)

        ttk.Label(
            self.container, text=f"Record Receipt — {customer['name']}",
            font=("Segoe UI", 20, "bold"),
        ).pack(anchor="w", pady=(0, 12))

        accounts = nominals.get_all()
        account_by_label = {nominals.label(a): a["id"] for a in accounts}

        head = ttk.Frame(self.container)
        head.pack(anchor="w")
        account_var = tk.StringVar()
        method_var = tk.StringVar(value=receipt_db.METHODS[0])
        date_var = tk.StringVar(value=datetime.date.today().strftime("%d/%m/%y"))

        ttk.Label(head, text="To account:").grid(row=0, column=0, sticky="w", pady=4, padx=(0, 10))
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
            values=list(receipt_db.METHODS),
        )
        method_combo.grid(row=1, column=1, sticky="w", pady=4)
        method_combo.current(0)

        ttk.Label(head, text="Date:").grid(row=2, column=0, sticky="w", pady=4, padx=(0, 10))
        ttk.Entry(head, textvariable=date_var, width=20).grid(row=2, column=1, sticky="w", pady=4)

        ttk.Label(
            self.container, text="Allocate to sales", font=("Segoe UI", 12, "bold"),
        ).pack(anchor="w", pady=(15, 5))

        sales_list = sale_db.customer_sales(customer_id, outstanding_only=True)
        alloc_vars = {}
        outstanding_by_id = {}

        if not sales_list:
            ttk.Label(
                self.container, text="No outstanding sales for this customer.",
            ).pack(anchor="w")
        else:
            grid = ttk.Frame(self.container)
            grid.pack(anchor="w")
            for col, text in enumerate(["Reference", "Date", "Total", "Outstanding", "Receive"]):
                ttk.Label(grid, text=text, font=("Segoe UI", 9, "bold")).grid(
                    row=0, column=col, sticky="w", padx=(0, 12), pady=(0, 4)
                )
            for i, s in enumerate(sales_list, start=1):
                outstanding_by_id[s["id"]] = s["outstanding"]
                ttk.Label(grid, text=s["reference"] or "").grid(row=i, column=0, sticky="w", padx=(0, 12))
                ttk.Label(grid, text=s["date"] or "").grid(row=i, column=1, sticky="w", padx=(0, 12))
                ttk.Label(grid, text=f"{s['total']:,.2f}").grid(row=i, column=2, sticky="e", padx=(0, 12))
                ttk.Label(grid, text=f"{s['outstanding']:,.2f}").grid(row=i, column=3, sticky="e", padx=(0, 12))
                var = tk.StringVar()
                ttk.Entry(grid, textvariable=var, width=10).grid(row=i, column=4, sticky="w")
                alloc_vars[s["id"]] = var

        total_label = ttk.Label(
            self.container, text="Receipt total: 0.00", font=("Segoe UI", 10, "bold")
        )
        total_label.pack(anchor="w", pady=(10, 0))

        def recompute(*_):
            running = 0.0
            for var in alloc_vars.values():
                try:
                    running += float(var.get() or 0)
                except ValueError:
                    pass
            total_label.config(text=f"Receipt total: {running:,.2f}")

        for var in alloc_vars.values():
            var.trace_add("write", recompute)

        def save():
            allocations = []
            for sale_id, var in alloc_vars.items():
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
                if amount - outstanding_by_id[sale_id] > 0.005:
                    messagebox.showwarning(
                        "Too much", "An allocation exceeds the sale's outstanding amount."
                    )
                    return
                allocations.append({"sale_id": sale_id, "amount": round(amount, 2)})
            if not allocations:
                messagebox.showwarning(
                    "Nothing to receive", "Enter an amount against at least one sale."
                )
                return
            account_id = account_by_label.get(account_var.get())
            if account_id is None:
                messagebox.showwarning("Account", "Choose an account to receive into.")
                return
            receipt_db.create_receipt(
                customer_id, account_id, method_var.get(),
                date_var.get().strip(), allocations,
            )
            messagebox.showinfo("Saved", "Receipt recorded.")
            self.show_receipts(customer_id)

        cancel = self._discard_guard(lambda: self.show_receipts(customer_id))
        btns = ttk.Frame(self.container)
        btns.pack(anchor="w", pady=(15, 0))
        ttk.Button(btns, text="Save Receipt (Ctrl+S)", command=save).pack(side="left")
        ttk.Button(btns, text="Cancel (Esc)", command=cancel).pack(side="left", padx=(8, 0))
        self._bind_form_shortcuts(save=save, cancel=cancel)
