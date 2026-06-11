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

    def show_new_receipt(self):
        """New Receipt from the Customers menu — pick the customer in the form."""
        self.show_receipt_form()

    def show_receipt_form(self, customer_id=None):
        """Record a receipt. The customer is chosen in the form; their outstanding
        sales load on selection (pre-selected when customer_id is given). No
        Save/Cancel buttons — leaving the page offers to save."""
        self.current_view = "receipt_form"
        self._clear_container()

        ttk.Label(
            self.container, text="New Receipt",
            font=("Segoe UI", 20, "bold"),
        ).pack(anchor="w", pady=(0, 12))

        customers = customer_db.get_all_customers()
        customer_by_label = {c["name"]: c["id"] for c in customers}
        accounts = nominals.get_all()
        account_by_label = {nominals.label(a): a["id"] for a in accounts}

        head = ttk.LabelFrame(self.container, text="Receipt Details", padding=12)
        head.pack(anchor="w", fill="x")
        customer_var = tk.StringVar()
        account_var = tk.StringVar()
        method_var = tk.StringVar(value=receipt_db.METHODS[0])
        date_var = tk.StringVar(value=datetime.date.today().strftime("%d/%m/%y"))

        # Left column: Customer / To account / Method.
        ttk.Label(head, text="Customer:").grid(row=0, column=0, sticky="w", pady=6, padx=(0, 10))
        customer_combo = ttk.Combobox(
            head, state="readonly", width=30, textvariable=customer_var,
            values=list(customer_by_label.keys()),
        )
        customer_combo.grid(row=0, column=1, sticky="w", pady=6)

        ttk.Label(head, text="To account:").grid(row=1, column=0, sticky="w", pady=6, padx=(0, 10))
        account_combo = ttk.Combobox(
            head, state="readonly", width=30, textvariable=account_var,
            values=list(account_by_label.keys()),
        )
        account_combo.grid(row=1, column=1, sticky="w", pady=6)
        if account_by_label:
            account_combo.current(0)

        ttk.Label(head, text="Method:").grid(row=2, column=0, sticky="w", pady=6, padx=(0, 10))
        method_combo = ttk.Combobox(
            head, state="readonly", width=18, textvariable=method_var,
            values=list(receipt_db.METHODS),
        )
        method_combo.grid(row=2, column=1, sticky="w", pady=6)
        method_combo.current(0)

        # Right column: Date.
        ttk.Label(head, text="Date:").grid(row=0, column=2, sticky="w", pady=6, padx=(30, 10))
        ttk.Entry(head, textvariable=date_var, width=22).grid(row=0, column=3, sticky="w", pady=6)

        ttk.Label(
            self.container, text="Allocate to sales", font=("Segoe UI", 12, "bold"),
        ).pack(anchor="w", pady=(15, 5))

        # The sale rows are rebuilt into this frame whenever the customer changes.
        alloc_frame = ttk.Frame(self.container)
        alloc_frame.pack(anchor="w", fill="x")
        total_label = ttk.Label(
            self.container, text="Receipt total: 0.00", font=("Segoe UI", 10, "bold")
        )
        total_label.pack(anchor="w", pady=(10, 0))

        state = {"customer_id": None, "alloc_vars": {}, "outstanding": {}}

        def recompute(*_):
            running = 0.0
            for var in state["alloc_vars"].values():
                try:
                    running += float(var.get() or 0)
                except ValueError:
                    pass
            total_label.config(text=f"Receipt total: {running:,.2f}")

        def load_sales():
            for widget in alloc_frame.winfo_children():
                widget.destroy()
            state["alloc_vars"] = {}
            state["outstanding"] = {}
            cid = state["customer_id"]
            if cid is None:
                ttk.Label(alloc_frame, text="Select a customer to see outstanding sales.").pack(anchor="w")
                recompute()
                return
            sales_list = sale_db.customer_sales(cid, outstanding_only=True)
            if not sales_list:
                ttk.Label(alloc_frame, text="No outstanding sales for this customer.").pack(anchor="w")
                recompute()
                return
            for col, text in enumerate(["Reference", "Date", "Total", "Outstanding", "Receive"]):
                ttk.Label(alloc_frame, text=text, font=("Segoe UI", 9, "bold")).grid(
                    row=0, column=col, sticky="w", padx=(0, 12), pady=(0, 4)
                )
            for i, s in enumerate(sales_list, start=1):
                state["outstanding"][s["id"]] = s["outstanding"]
                ttk.Label(alloc_frame, text=s["reference"] or "").grid(row=i, column=0, sticky="w", padx=(0, 12))
                ttk.Label(alloc_frame, text=s["date"] or "").grid(row=i, column=1, sticky="w", padx=(0, 12))
                ttk.Label(alloc_frame, text=f"{s['total']:,.2f}").grid(row=i, column=2, sticky="e", padx=(0, 12))
                ttk.Label(alloc_frame, text=f"{s['outstanding']:,.2f}").grid(row=i, column=3, sticky="e", padx=(0, 12))
                var = tk.StringVar()
                var.trace_add("write", recompute)
                ttk.Entry(alloc_frame, textvariable=var, width=10).grid(row=i, column=4, sticky="w")
                state["alloc_vars"][s["id"]] = var
            recompute()

        def on_customer(*_):
            state["customer_id"] = customer_by_label.get(customer_var.get())
            load_sales()

        customer_combo.bind("<<ComboboxSelected>>", on_customer)

        if customer_id is not None:
            label = next((c["name"] for c in customers if c["id"] == customer_id), None)
            if label is not None:
                customer_var.set(label)
                state["customer_id"] = customer_id
        load_sales()

        def save():
            if state["customer_id"] is None:
                messagebox.showwarning("Customer", "Choose a customer first.")
                return None
            allocations = []
            for sale_id, var in state["alloc_vars"].items():
                raw = var.get().strip()
                if not raw:
                    continue
                try:
                    amount = float(raw)
                except ValueError:
                    messagebox.showwarning("Invalid amount", "Enter numeric amounts only.")
                    return None
                if amount <= 0:
                    continue
                if amount - state["outstanding"][sale_id] > 0.005:
                    messagebox.showwarning(
                        "Too much", "An allocation exceeds the sale's outstanding amount."
                    )
                    return None
                allocations.append({"sale_id": sale_id, "amount": round(amount, 2)})
            if not allocations:
                messagebox.showwarning(
                    "Nothing to receive", "Enter an amount against at least one sale."
                )
                return None
            account_id = account_by_label.get(account_var.get())
            if account_id is None:
                messagebox.showwarning("Account", "Choose an account to receive into.")
                return None
            return receipt_db.create_receipt(
                state["customer_id"], account_id, method_var.get(),
                date_var.get().strip(), allocations,
            )

        self._register_form(save=save, back=self.show_customers)
