"""Supplier-payment screens (mixin for App)."""
import datetime
import tkinter as tk
from tkinter import ttk
from ui import dialogs as messagebox

from core import suppliers as db
from core import purchases as purchase_db
from core import payments as payment_db
from core import nominals

from ui.common import make_sortable


class PaymentsMixin:
    def show_payments(self, supplier_id):
        self.current_view = "payments"
        self._clear_container()
        supplier = db.get_supplier(supplier_id)

        header = ttk.Frame(self.container)
        header.pack(fill="x", pady=(0, 10))
        ttk.Label(
            header, text=f"Payments — {supplier['name']}",
            font=("Consolas", 20, "bold"),
        ).pack(side="left")

        balance = payment_db.supplier_balance(supplier_id)
        ttk.Label(
            self.container, text=f"Balance owed: {balance:,.2f}",
            font=("Consolas", 12, "bold"),
        ).pack(anchor="w", pady=(0, 8))

        columns = ("date", "account", "method", "amount", "unallocated", "invoices")
        headings = ("Date", "Account", "Method", "Amount", "Unallocated", "Invoices")
        widths = (100, 170, 70, 90, 100, 220)
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
        tree.column("unallocated", anchor="e")
        make_sortable(tree)

        rows = payment_db.get_payments(supplier_id)
        for r in rows:
            tree.insert(
                "", "end", iid=str(r["id"]),
                values=(
                    r["date"] or "", f"{r['account_code']} - {r['account_name']}",
                    r["method"] or "", f"{r['amount']:,.2f}",
                    f"{r['unallocated']:,.2f}", r["invoices"] or "",
                ),
            )

        def open_selected(event=None):
            selection = tree.selection()
            if selection:
                self.show_payment_allocation(int(selection[0]))

        def delete_selected(event=None):
            selection = tree.selection()
            if not selection:
                return
            pid = int(selection[0])
            row = next((r for r in rows if r["id"] == pid), None)
            label = f"{row['date'] or ''} · {row['amount']:,.2f}" if row else str(pid)
            if messagebox.askyesno("Delete payment", f"Delete payment ({label})?"):
                payment_db.delete_payment(pid)
                self.show_payments(supplier_id)

        tree.bind("<Double-1>", open_selected)
        tree.bind("<Return>", open_selected)
        tree.bind("<Delete>", delete_selected)
        ttk.Label(
            self.container,
            text=(f"{len(rows)} payment(s)." if rows else "No payments yet."),
        ).pack(anchor="w", pady=(8, 0))
        ttk.Button(
            self.container, text="Back to Supplier",
            command=lambda: self.show_supplier_form(db.get_supplier(supplier_id)),
        ).pack(anchor="w", pady=(12, 0))

    def show_new_payment(self):
        """New Payment from the Suppliers menu — pick the supplier in the form."""
        self.show_payment_form()

    def show_payment_form(self, supplier_id=None):
        """Record a payment of a manually-entered amount. The supplier is chosen
        in the form (pre-selected when supplier_id is given). On Create, the
        payment is saved and we move to its allocation screen, where it can be
        allocated to outstanding invoices (now or later)."""
        self.current_view = "payment_form"
        self._clear_container()

        ttk.Label(
            self.container, text="New Payment",
            font=("Consolas", 20, "bold"),
        ).pack(anchor="w", pady=(0, 12))

        suppliers = db.get_all_suppliers()
        supplier_by_label = {s["name"]: s["id"] for s in suppliers}
        accounts = nominals.get_all()
        account_by_label = {nominals.label(a): a["id"] for a in accounts}

        head = ttk.LabelFrame(self.container, text="Payment Details", padding=12)
        head.pack(anchor="w", fill="x")
        supplier_var = tk.StringVar()
        account_var = tk.StringVar()
        method_var = tk.StringVar(value=payment_db.METHODS[0])
        date_var = tk.StringVar(value=datetime.date.today().strftime("%d/%m/%y"))
        amount_var = tk.StringVar()

        # Left column: Supplier / From account / Method.
        ttk.Label(head, text="Supplier:").grid(row=0, column=0, sticky="w", pady=6, padx=(0, 10))
        supplier_combo = ttk.Combobox(
            head, state="readonly", width=30, textvariable=supplier_var,
            values=list(supplier_by_label.keys()),
        )
        supplier_combo.grid(row=0, column=1, sticky="w", pady=6)

        ttk.Label(head, text="From account:").grid(row=1, column=0, sticky="w", pady=6, padx=(0, 10))
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
            values=list(payment_db.METHODS),
        )
        method_combo.grid(row=2, column=1, sticky="w", pady=6)
        method_combo.current(0)

        # Right column: Date / Amount.
        ttk.Label(head, text="Date:").grid(row=0, column=2, sticky="w", pady=6, padx=(30, 10))
        ttk.Entry(head, textvariable=date_var, width=22).grid(row=0, column=3, sticky="w", pady=6)

        ttk.Label(head, text="Amount:").grid(row=1, column=2, sticky="w", pady=6, padx=(30, 10))
        ttk.Entry(head, textvariable=amount_var, width=22).grid(row=1, column=3, sticky="w", pady=6)

        def default_method_for(sid):
            """Pre-select the supplier's preferred payment method, if it has one."""
            supplier = next((s for s in suppliers if s["id"] == sid), None)
            preferred = supplier["payment_method"] if supplier else ""
            if preferred in payment_db.METHODS:
                method_var.set(preferred)

        supplier_combo.bind(
            "<<ComboboxSelected>>",
            lambda e: default_method_for(supplier_by_label.get(supplier_var.get())),
        )

        if supplier_id is not None:
            label = next((s["name"] for s in suppliers if s["id"] == supplier_id), None)
            if label is not None:
                supplier_var.set(label)
                default_method_for(supplier_id)

        ttk.Label(
            self.container,
            text="Enter the payment amount, then allocate it to invoices on the next screen.",
            foreground="#C9A227",
        ).pack(anchor="w", pady=(15, 0))

        def create_and_allocate():
            sid = supplier_by_label.get(supplier_var.get())
            if sid is None:
                messagebox.showwarning("Supplier", "Choose a supplier first.")
                return
            account_id = account_by_label.get(account_var.get())
            if account_id is None:
                messagebox.showwarning("Account", "Choose an account to pay from.")
                return
            try:
                amount = float(amount_var.get().strip())
            except ValueError:
                messagebox.showwarning("Amount", "Enter a numeric payment amount.")
                return
            if amount <= 0:
                messagebox.showwarning("Amount", "Enter a payment amount greater than zero.")
                return
            payment_id = payment_db.create_payment(
                sid, account_id, method_var.get(), date_var.get().strip(), round(amount, 2),
            )
            self.show_payment_allocation(payment_id)

        actions = ttk.LabelFrame(self.container, text="Actions", padding=8)
        actions.pack(fill="x", pady=(20, 0))
        ttk.Button(actions, text="Create payment", command=create_and_allocate).pack(side="left")
        ttk.Button(
            actions, text="Cancel", command=self.show_all_suppliers,
        ).pack(side="left", padx=(8, 0))

    def show_payment_allocation(self, payment_id):
        """Allocate (part of) a payment to the supplier's outstanding invoices.

        Reachable straight after creating a payment or later from a payments
        list. Allocations may be partial and need not use the whole payment — the
        unallocated remainder can be allocated on a future visit."""
        self.current_view = "payment_allocation"
        self._clear_container()
        payment = payment_db.get_payment(payment_id)
        supplier = db.get_supplier(payment["supplier_id"])
        remaining = round(payment["amount"] - payment["allocated"], 2)

        ttk.Label(
            self.container, text=f"Allocate Payment — {supplier['name']}",
            font=("Consolas", 20, "bold"),
        ).pack(anchor="w", pady=(0, 8))
        ttk.Label(
            self.container,
            text=(f"Payment {payment['amount']:,.2f} · "
                  f"already allocated {payment['allocated']:,.2f} · "
                  f"unallocated {remaining:,.2f}"),
            font=("Consolas", 11),
        ).pack(anchor="w", pady=(0, 12))

        ttk.Label(
            self.container,
            text="Tick a purchase to allocate against it (click the leftmost column).",
            font=("Consolas", 12, "bold"),
        ).pack(anchor="w", pady=(0, 5))

        invoices = purchase_db.supplier_invoices(payment["supplier_id"], outstanding_only=True)
        outstanding = {inv["id"]: inv["outstanding"] for inv in invoices}
        allocated = {}  # purchase_id -> amount being allocated (only ticked rows)

        columns = ("select", "reference", "date", "total", "outstanding", "allocate")
        headings = ("✓", "Reference", "Date", "Total", "Outstanding", "Allocate")
        widths = (36, 150, 100, 100, 110, 110)
        table_frame = ttk.Frame(self.container)
        table_frame.pack(anchor="w", fill="x")
        tree = ttk.Treeview(
            table_frame, columns=columns, show="headings",
            height=min(max(len(invoices), 1), 12), selectmode="none",
        )
        for col, heading, width in zip(columns, headings, widths):
            tree.heading(col, text=heading)
            tree.column(col, width=width)
        tree.column("select", anchor="center", stretch=False)
        for col in ("total", "outstanding", "allocate"):
            tree.column(col, anchor="e")
        tree.pack(side="left", fill="x", expand=True)

        remaining_label = ttk.Label(
            self.container, text="", font=("Consolas", 10, "bold"),
        )
        remaining_label.pack(anchor="w", pady=(10, 0))

        def free_amount():
            """Payment amount still available to allocate this visit."""
            return round(remaining - sum(allocated.values()), 2)

        def refresh_row(pid):
            ticked = pid in allocated
            tree.set(pid, "select", "☑" if ticked else "☐")
            tree.set(pid, "allocate", f"{allocated[pid]:,.2f}" if ticked else "")

        def refresh_status():
            used = round(sum(allocated.values()), 2)
            remaining_label.config(
                text=f"Allocating {used:,.2f} of {remaining:,.2f} unallocated "
                     f"({free_amount():,.2f} left)."
            )

        for inv in invoices:
            tree.insert(
                "", "end", iid=str(inv["id"]),
                values=("☐", inv["reference"] or "", inv["date"] or "",
                        f"{inv['total']:,.2f}", f"{inv['outstanding']:,.2f}", ""),
            )

        if not invoices:
            ttk.Label(
                table_frame, text="No outstanding invoices for this supplier.",
            ).pack(anchor="w")

        def toggle(pid):
            if pid in allocated:
                del allocated[pid]
                refresh_row(pid)
                refresh_status()
                self.mark_form_dirty()
                return
            avail = free_amount()
            if avail <= 0:
                messagebox.showinfo(
                    "Fully allocated", "The whole payment has already been allocated."
                )
                return
            owed = outstanding[pid]
            if avail + 0.005 >= owed:
                allocated[pid] = round(owed, 2)
            else:
                part = messagebox.askyesno(
                    "Part allocate?",
                    f"Only {avail:,.2f} of the payment is left, but this purchase "
                    f"has {owed:,.2f} outstanding.\n\nPart-allocate {avail:,.2f} to it?",
                )
                if not part:
                    return
                allocated[pid] = round(avail, 2)
            refresh_row(pid)
            refresh_status()
            self.mark_form_dirty()

        def on_click(event):
            if tree.identify_region(event.x, event.y) != "cell":
                return
            if tree.identify_column(event.x) != "#1":  # only the checkbox column
                return
            row = tree.identify_row(event.y)
            if row:
                toggle(int(row))

        tree.bind("<Button-1>", on_click)

        def suggest():
            """Auto-allocate the payment across outstanding invoices, in order,
            using as much of each as the remaining payment covers."""
            allocated.clear()
            left = remaining
            for inv in invoices:
                if left <= 0.005:
                    break
                take = round(min(left, inv["outstanding"]), 2)
                if take > 0:
                    allocated[inv["id"]] = take
                    left = round(left - take, 2)
            for inv in invoices:
                refresh_row(inv["id"])
            refresh_status()
            self.mark_form_dirty()

        def save_allocations():
            allocations = [
                {"purchase_id": pid, "amount": amount}
                for pid, amount in allocated.items() if amount > 0
            ]
            payment_db.add_allocations(payment_id, allocations)
            return True

        refresh_status()

        # Save-on-leave, like the rest of the app: navigating away (or Esc) offers
        # to save the allocations — replacing the old Save/Allocate-later buttons.
        back = lambda: self.show_payments(payment["supplier_id"])
        self._register_form(save_allocations, back)

        if invoices:
            actions = ttk.LabelFrame(self.container, text="Actions", padding=8)
            actions.pack(fill="x", pady=(20, 0))
            ttk.Button(actions, text="Suggest", command=suggest).pack(side="left")

    # ------------------------------------------------------------------- Services
