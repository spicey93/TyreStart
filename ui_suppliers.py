"""Supplier screens (mixin for App)."""
import tkinter as tk
from tkinter import ttk, messagebox

import suppliers as db
import payments as payment_db

from ui_common import make_sortable


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
                    tree.insert(
                        "",
                        "end",
                        iid=str(s["id"]),
                        values=(s["name"], s["account_number"], s["contact"], s["email"], s["phone"]),
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

        columns = ("name", "account_number", "contact", "email", "phone")
        headings = ("Name", "Account #", "Contact", "Email", "Phone")
        tree = ttk.Treeview(self.container, columns=columns, show="headings")
        for col, heading in zip(columns, headings):
            tree.heading(col, text=heading)
            tree.column(col, width=130)
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

        # Double-clicking or pressing Enter on a row opens that supplier.
        tree.bind("<Double-1>", lambda e: edit_selected())
        tree.bind("<Return>", lambda e: edit_selected())

        refresh_tree()

    def show_create_supplier(self):
        self.show_supplier_form()

    def show_supplier_form(self, supplier=None):
        """Form used for both creating (supplier=None) and editing a supplier."""
        self.current_view = "form"
        self._clear_container()
        editing = supplier is not None
        ttk.Label(
            self.container,
            text="Edit Supplier" if editing else "Create Supplier",
            font=("Segoe UI", 20, "bold"),
        ).pack(anchor="w", pady=(0, 15))

        form = ttk.Frame(self.container)
        form.pack(anchor="w")

        entries = {}
        fields = [
            ("name", "Name"),
            ("account_number", "Account #"),
            ("contact", "Contact"),
            ("email", "Email"),
            ("phone", "Phone"),
        ]
        for row, (key, label) in enumerate(fields):
            ttk.Label(form, text=label + ":").grid(row=row, column=0, sticky="w", pady=5, padx=(0, 10))
            entry = ttk.Entry(form, width=40)
            entry.grid(row=row, column=1, pady=5)
            if editing:
                entry.insert(0, supplier[key] or "")
            entries[key] = entry

        def save():
            data = {key: entry.get().strip() for key, entry in entries.items()}
            if not data["name"]:
                messagebox.showwarning("Missing name", "Please enter a supplier name.")
                return
            try:
                if editing:
                    db.update_supplier(
                        supplier["id"], data["name"], data["account_number"],
                        data["contact"], data["email"], data["phone"],
                    )
                    message = f"Supplier '{data['name']}' updated."
                else:
                    db.add_supplier(
                        data["name"], data["account_number"],
                        data["contact"], data["email"], data["phone"],
                    )
                    message = f"Supplier '{data['name']}' created."
            except db.DuplicateNameError:
                messagebox.showerror(
                    "Duplicate name",
                    f"A supplier named '{data['name']}' already exists.",
                )
                return
            messagebox.showinfo("Saved", message)
            self.show_all_suppliers()

        def delete_current():
            if not editing:
                return
            if messagebox.askyesno("Delete supplier", f"Delete '{supplier['name']}'?"):
                db.delete_supplier(supplier["id"])
                self.show_all_suppliers()

        cancel = self._discard_guard(self.show_all_suppliers)
        button_frame = ttk.Frame(self.container)
        button_frame.pack(anchor="w", pady=(20, 0))
        ttk.Button(button_frame, text="Save (Ctrl+S)", command=save).pack(side="left")
        ttk.Button(
            button_frame, text="Cancel (Esc)", command=cancel
        ).pack(side="left", padx=(8, 0))
        if editing:
            ttk.Button(
                button_frame,
                text="Delete (Ctrl+D)",
                command=delete_current,
            ).pack(side="left", padx=(8, 0))
        self._bind_form_shortcuts(
            save=save, cancel=cancel,
            delete=delete_current if editing else None,
        )

        # Account section: balance + payment actions (only for an existing supplier).
        if editing:
            account = ttk.LabelFrame(self.container, text="Account", padding=10)
            account.pack(anchor="w", fill="x", pady=(20, 0))
            balance = payment_db.supplier_balance(supplier["id"])
            ttk.Label(
                account,
                text=f"Balance owed: {balance:,.2f}",
                font=("Segoe UI", 12, "bold"),
            ).pack(anchor="w")
            acc_btns = ttk.Frame(account)
            acc_btns.pack(anchor="w", pady=(8, 0))
            ttk.Button(
                acc_btns, text="Make Payment",
                command=lambda: self.show_payment_form(supplier["id"]),
            ).pack(side="left")
            ttk.Button(
                acc_btns, text="View Payments",
                command=lambda: self.show_payments(supplier["id"]),
            ).pack(side="left", padx=(8, 0))
            ttk.Button(
                acc_btns, text="View Purchases",
                command=lambda: self.show_purchases(prefill=supplier["name"]),
            ).pack(side="left", padx=(8, 0))
