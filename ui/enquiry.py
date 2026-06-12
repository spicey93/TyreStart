"""Enquiry screen (mixin for App).

A quick point-of-sale lookup: type a stock code or service code, and press Enter
on a result row to start a sale for that product/service. Products and services
are searched together and shown in one list.
"""
import tkinter as tk
from tkinter import ttk

from core import products as product_db
from core import services as service_db
from core import pricing as pricing_db

from ui.common import make_sortable

PRODUCT_LIMIT = 100


class EnquiryMixin:
    def show_enquiry(self):
        self.current_view = "enquiry"
        self._clear_container()

        header = ttk.Frame(self.container)
        header.pack(fill="x", pady=(0, 10))
        ttk.Label(header, text="Enquiry", font=("Consolas", 20, "bold")).pack(side="left")

        bar = ttk.Frame(self.container)
        bar.pack(fill="x", pady=(0, 10))
        bar.columnconfigure(1, weight=1)
        search_term = tk.StringVar()
        ttk.Label(bar, text="Stock / service code:").grid(row=0, column=0, sticky="w")
        search_entry = ttk.Entry(bar, textvariable=search_term)
        search_entry.grid(row=0, column=1, sticky="ew", padx=(8, 10))
        search_entry.focus_set()
        search_entry.bind("<Return>", lambda e: do_search())
        ttk.Button(bar, text="Search", command=lambda: do_search()).grid(row=0, column=2, padx=(0, 8))
        ttk.Button(bar, text="Clear", command=lambda: clear()).grid(row=0, column=3)

        columns = ("type", "code", "description", "stock", "price")
        headings = ("Type", "Code", "Description", "Stock", "Price")
        widths = (80, 150, 360, 70, 90)
        table_frame = ttk.Frame(self.container)
        table_frame.pack(fill="both", expand=True)
        tree = ttk.Treeview(table_frame, columns=columns, show="headings")
        sb = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        tree.pack(side="left", fill="both", expand=True)
        for col, heading, width in zip(columns, headings, widths):
            tree.heading(col, text=heading)
            tree.column(col, width=width, anchor="e" if col in ("stock", "price") else "w")
        make_sortable(tree)

        status = ttk.Label(self.container, text="")
        status.pack(anchor="w", pady=(8, 0))

        def refresh():
            text = search_term.get().strip()
            tree.delete(*tree.get_children())
            if not text:
                status.config(text="Enter a stock code or service code to search.")
                return
            prods, total = product_db.query_products(text=text, in_stock="all", limit=PRODUCT_LIMIT)
            rules = pricing_db.list_rules()
            for p in prods:
                price = pricing_db.price_from_rules(
                    p["avg_cost"], p["pricing_key"] or "", p["product_group"] or "", rules=rules)
                tree.insert("", "end", iid=f"p{p['id']}", values=(
                    "Product", p["stock_code"], p["description"], p["stock"],
                    f"{price:,.2f}" if price is not None else "—"))
            svcs = service_db.list_services(text=text)
            for s in svcs:
                tree.insert("", "end", iid=f"s{s['id']}", values=(
                    "Service", s["service_code"] or "", s["service_name"], "",
                    f"{(s['retail_price'] or 0):,.2f}"))
            n = len(prods) + len(svcs)
            extra = f" (first {len(prods)} of {total:,} products)" if total > len(prods) else ""
            status.config(text=(
                f"{n} result(s).{extra}  Press Enter on a row to start a sale."
                if n else "No products or services match."))

        def do_search():
            refresh()
            children = tree.get_children()
            if children:
                tree.focus_set()
                tree.selection_set(children[0])
                tree.focus(children[0])
                tree.see(children[0])

        def clear():
            search_term.set("")
            refresh()
            search_entry.focus_set()

        def start_sale(event=None):
            selection = tree.selection()
            if not selection:
                return
            iid = selection[0]
            kind, record_id = iid[0], int(iid[1:])
            if kind == "p":
                product = product_db.get_product(record_id)
                if product is not None:
                    self.show_sale_form(prefill_product=product)
            else:
                service = service_db.get_service(record_id)
                if service is not None:
                    self.show_sale_form(prefill_service=service)

        tree.bind("<Return>", start_sale)
        tree.bind("<Double-1>", start_sale)

        refresh()
