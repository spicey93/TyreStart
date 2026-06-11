"""Service screens (mixin for App)."""
import tkinter as tk
from tkinter import ttk
from ui import dialogs as messagebox

from core import services as service_db

from ui.common import make_sortable


class ServicesMixin:
    def show_services(self):
        self.current_view = "services"
        self._clear_container()

        header = ttk.Frame(self.container)
        header.pack(fill="x", pady=(0, 10))
        ttk.Label(
            header, text="Services", font=("Consolas", 20, "bold")
        ).pack(side="left")

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

        columns = ("service_code", "service_name", "cost", "retail_price")
        headings = ("Service Code", "Service Name", "Cost", "Retail Price")
        widths = (160, 300, 110, 110)
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
        tree.column("cost", anchor="e")
        tree.column("retail_price", anchor="e")
        make_sortable(tree)

        status_label = ttk.Label(self.container, text="")
        status_label.pack(anchor="w", pady=(8, 0))

        def refresh():
            rows = service_db.list_services(text=search_term.get().strip())
            tree.delete(*tree.get_children())
            for r in rows:
                tree.insert(
                    "", "end", iid=str(r["id"]),
                    values=(
                        r["service_code"] or "", r["service_name"],
                        f"{(r['cost'] or 0):,.2f}", f"{(r['retail_price'] or 0):,.2f}",
                    ),
                )
            status_label.config(
                text=f"{len(rows)} service(s)." if rows
                else "No services yet. Use Services → New Service to add one."
            )

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
                messagebox.showinfo("No selection", "Please select a service first.")
                return
            service_id = int(selection[0])
            action = self.ask_product_action("service")
            if action == "view":
                self.show_service_form(service_db.get_service(service_id))
            elif action == "sale":
                self.show_sale_form(prefill_service=service_db.get_service(service_id))

        def delete_selected(event=None):
            selection = tree.selection()
            if not selection:
                return
            service = service_db.get_service(int(selection[0]))
            if service and messagebox.askyesno(
                "Delete service", f"Delete '{service['service_name']}'?"
            ):
                service_db.delete_service(service["id"])
                refresh()

        tree.bind("<Double-1>", lambda e: open_selected())
        tree.bind("<Return>", lambda e: open_selected())
        tree.bind("<Delete>", delete_selected)

        ttk.Label(
            self.container,
            text="Double-click or Enter for options (view / create sale) · Delete key to remove.",
            foreground="#C9A227",
        ).pack(anchor="w", pady=(4, 0))

        refresh()

    def show_service_form(self, service=None):
        """Create/edit a service (code, name, cost, retail price)."""
        self.current_view = "service_form"
        self._clear_container()
        editing = service is not None
        ttk.Label(
            self.container,
            text="Edit Service" if editing else "New Service",
            font=("Consolas", 20, "bold"),
        ).pack(anchor="w", pady=(0, 15))

        form = ttk.LabelFrame(self.container, text="Service Details", padding=12)
        form.pack(anchor="w", fill="x")
        fields = [
            ("service_code", "Service Code"),
            ("service_name", "Service Name"),
            ("cost", "Cost"),
            ("retail_price", "Retail Price"),
        ]
        entries = {}
        for row, (key, label) in enumerate(fields):
            ttk.Label(form, text=label + ":").grid(row=row, column=0, sticky="w", pady=5, padx=(0, 10))
            entry = ttk.Entry(form, width=40)
            entry.grid(row=row, column=1, pady=5)
            if editing:
                value = service[key]
                if key in ("cost", "retail_price"):
                    entry.insert(0, f"{(value or 0):.2f}")
                else:
                    entry.insert(0, value or "")
            entries[key] = entry

        def save():
            data = {key: entry.get().strip() for key, entry in entries.items()}
            if not data["service_name"]:
                messagebox.showwarning("Missing name", "Please enter a service name.")
                return None
            try:
                cost = float(data["cost"]) if data["cost"] else 0.0
                retail = float(data["retail_price"]) if data["retail_price"] else 0.0
            except ValueError:
                messagebox.showwarning("Invalid", "Cost and Retail Price must be numbers.")
                return None
            try:
                if editing:
                    service_db.update_service(
                        service["id"], data["service_code"], data["service_name"], cost, retail
                    )
                    return service["id"]
                return service_db.create_service(
                    data["service_code"], data["service_name"], cost, retail
                )
            except service_db.DuplicateCodeError:
                messagebox.showerror(
                    "Duplicate code",
                    f"A service with code '{data['service_code']}' already exists.",
                )
                return None

        self._register_form(save=save, back=self.show_services)

    # ------------------------------------------------------------------ Customers
