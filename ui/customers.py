"""Customer screens (mixin for App)."""
import tkinter as tk
from tkinter import ttk
from ui import dialogs as messagebox

from core import customers as customer_db
from core import receipts as receipt_db
from core import sales as sale_db

from ui.common import make_sortable


class CustomersMixin:
    def show_customers(self):
        self.current_view = "customers"
        self._clear_container()

        header = ttk.Frame(self.container)
        header.pack(fill="x", pady=(0, 10))
        ttk.Label(header, text="Customers", font=("Consolas", 20, "bold")).pack(side="left")

        bar = ttk.Frame(self.container)
        bar.pack(fill="x", pady=(0, 10))
        bar.columnconfigure(1, weight=1)
        search_term = tk.StringVar()
        ttk.Label(bar, text="Search:").grid(row=0, column=0, sticky="w")
        search_entry = ttk.Entry(bar, textvariable=search_term)
        search_entry.grid(row=0, column=1, sticky="ew", padx=(8, 10))
        search_entry.focus_set()
        search_entry.bind("<Return>", lambda e: do_search())
        ttk.Button(bar, text="Search", command=lambda: do_search()).grid(row=0, column=2, padx=(0, 8))
        ttk.Button(bar, text="Clear", command=lambda: clear()).grid(row=0, column=3)

        columns = ("name", "account_number", "postcode", "email", "phone")
        headings = ("Name", "Account #", "Postcode", "Email", "Phone")
        table_frame = ttk.Frame(self.container)
        table_frame.pack(fill="both", expand=True)
        tree = ttk.Treeview(table_frame, columns=columns, show="headings")
        sb = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        tree.pack(side="left", fill="both", expand=True)
        for col, heading in zip(columns, headings):
            tree.heading(col, text=heading)
            tree.column(col, width=140)
        make_sortable(tree)

        status_label = ttk.Label(self.container, text="")
        status_label.pack(anchor="w", pady=(8, 0))

        def refresh():
            query = search_term.get().strip().lower()
            tree.delete(*tree.get_children())
            for c in customer_db.get_all_customers():
                if not query or query in (c["name"] or "").lower():
                    tree.insert(
                        "", "end", iid=str(c["id"]),
                        values=(c["name"], c["account_number"], c["postcode"], c["email"], c["phone"]),
                    )
            if not tree.get_children():
                status_label.config(
                    text="No customers match the search." if query
                    else "No customers yet. Use Customers → New Customer to add one."
                )
            else:
                status_label.config(text="")

        def clear():
            search_term.set("")
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
                messagebox.showinfo("No selection", "Please select a customer first.")
                return
            self.show_customer_form(customer_db.get_customer(int(selection[0])))

        def delete_selected(event=None):
            selection = tree.selection()
            if not selection:
                return
            customer = customer_db.get_customer(int(selection[0]))
            if customer and messagebox.askyesno(
                "Delete customer", f"Delete '{customer['name']}'?"
            ):
                customer_db.delete_customer(customer["id"])
                refresh()

        tree.bind("<Double-1>", lambda e: open_selected())
        tree.bind("<Return>", lambda e: open_selected())
        tree.bind("<Delete>", delete_selected)

        ttk.Label(
            self.container,
            text="Double-click or Enter to edit · Delete key to remove the selected customer.",
            foreground="#C9A227",
        ).pack(anchor="w", pady=(4, 0))

        refresh()

    def show_customer_form(self, customer=None):
        """Create/edit a customer."""
        self.current_view = "customer_form"
        self._clear_container()
        editing = customer is not None
        ttk.Label(
            self.container,
            text="Edit Customer" if editing else "New Customer",
            font=("Consolas", 20, "bold"),
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
            ("address", "Address"),
            ("postcode", "Postcode"),
            ("email", "Email"),
            ("phone", "Phone"),
        ]
        for row, (key, label) in enumerate(fields):
            ttk.Label(details, text=label + ":").grid(row=row, column=0, sticky="w", pady=5, padx=(0, 10))
            entry = ttk.Entry(details, width=40)
            entry.grid(row=row, column=1, pady=5)
            if editing:
                entry.insert(0, customer[key] or "")
            elif key == "account_number":
                # Autogenerated on save for new customers.
                entry.insert(0, "(auto-generated)")
                entry.configure(state="readonly")
            entries[key] = entry

        if editing:
            balance = receipt_db.customer_balance(customer["id"])
            ttk.Label(
                details,
                text=f"Balance owed by customer: {balance:,.2f}",
                font=("Consolas", 12, "bold"),
            ).grid(row=len(fields), column=0, columnspan=2, sticky="w", pady=(14, 0))

            # --- Receipts & Sales tabs (read-only; existing customer only) ---
            self._build_customer_receipts_tab(notebook, customer["id"])
            self._build_customer_sales_tab(notebook, customer["id"])

        def save():
            data = {key: entry.get().strip() for key, entry in entries.items()}
            if not data["name"]:
                messagebox.showwarning("Missing name", "Please enter a customer name.")
                return None
            if not editing:
                data["account_number"] = ""  # let the data layer generate it
            try:
                if editing:
                    customer_db.update_customer(
                        customer["id"], data["name"], data["account_number"],
                        data["address"], data["postcode"], data["email"], data["phone"],
                    )
                    return customer["id"]
                return customer_db.add_customer(
                    data["name"], data["account_number"],
                    data["address"], data["postcode"], data["email"], data["phone"],
                )
            except customer_db.DuplicateNameError:
                messagebox.showerror(
                    "Duplicate name", f"A customer named '{data['name']}' already exists."
                )
                return None

        self._register_form(save=save, back=self.show_customers)
        # Ctrl+1/Ctrl+2/… switch tabs (added after _register_form resets the list).
        self._bind_tab_shortcuts(notebook)

    def _build_customer_receipts_tab(self, notebook, customer_id):
        """Searchable, read-only list of the customer's receipts (new receipts are
        recorded via the Customers → New Receipt menu)."""
        tab = ttk.Frame(notebook, padding=12)
        notebook.add(tab, text="Receipts")
        rows = receipt_db.get_receipts(customer_id)

        def cells(r):
            return {
                "date": r["date"] or "",
                "account": f"{r['account_code']} - {r['account_name']}",
                "method": r["method"] or "",
                "amount": f"{r['amount']:,.2f}",
                "sales": r["sales"] or "",
            }

        self._searchable_table(
            tab,
            columns=("date", "account", "method", "amount", "sales"),
            headings=("Date", "Account", "Method", "Amount", "Sales"),
            rows=rows, cells=cells,
            widths=(90, 160, 70, 90, 200),
            right_cols=("amount",),
            field_labels=[("All", None), ("Date", "date"), ("Account", "account"),
                          ("Method", "method"), ("Sales", "sales")],
            empty_text="No receipts yet.",
        )

    def _build_customer_sales_tab(self, notebook, customer_id):
        """Searchable, read-only list of the customer's sales (quotes/orders/invoices)."""
        tab = ttk.Frame(notebook, padding=12)
        notebook.add(tab, text="Sales")
        rows = sale_db.list_for_customer(customer_id)

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
            empty_text="No sales yet.",
        )

    # ---------------------------------------------------------------------- Sales
