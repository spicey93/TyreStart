"""Financial-report screens (mixin for App): Trial Balance, Profit & Loss,
Balance Sheet and the VAT Return."""
import tkinter as tk
from tkinter import ttk
from ui import dialogs as messagebox

from core import reports as report_db
from core import vat as vat_db
from core import money, daterange

from ui.common import make_sortable

_TITLE = ("Consolas", 20, "bold")
_SECTION = ("Consolas", 12, "bold")
_MONO = ("Consolas", 11)


def _iso(date):
    return date.strftime("%Y-%m-%d") if date else None


class ReportsMixin:
    # ---------------------------------------------------------------- helpers
    def _report_header(self, title):
        header = ttk.Frame(self.container)
        header.pack(fill="x", pady=(0, 10))
        ttk.Label(header, text=title, font=_TITLE).pack(side="left")
        return header

    def _plain_tree(self, columns, headings, widths, right_cols=()):
        frame = ttk.Frame(self.container)
        frame.pack(fill="both", expand=True)
        tree = ttk.Treeview(frame, columns=columns, show="headings")
        sb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        tree.pack(side="left", fill="both", expand=True)
        for col, heading, width in zip(columns, headings, widths):
            tree.heading(col, text=heading)
            tree.column(col, width=width, anchor="e" if col in right_cols else "w")
        tree.tag_configure("section", font=_SECTION)
        tree.tag_configure("total", font=_SECTION)
        return tree

    # ---------------------------------------------------------- Trial Balance
    def show_trial_balance(self):
        self.current_view = "trial_balance"
        self._clear_container()
        self._report_header("Trial Balance")

        bar = ttk.Frame(self.container)
        bar.pack(fill="x", pady=(0, 10))
        date_frame, get_range = self._make_date_filter(bar, lambda: refresh())
        date_frame.grid(row=0, column=0, sticky="w")

        tree = self._plain_tree(
            ("code", "name", "debit", "credit"),
            ("Code", "Account", "Debit", "Credit"),
            (80, 320, 130, 130), right_cols=("debit", "credit"))
        status = ttk.Label(self.container, text="", font=_MONO)
        status.pack(anchor="e", pady=(8, 0))

        def refresh():
            _, end = get_range()
            tb = report_db.trial_balance(as_at=_iso(end))
            tree.delete(*tree.get_children())
            for r in tb["rows"]:
                tree.insert("", "end", values=(
                    r["code"], r["name"],
                    money.format_pence(r["debit"]) if r["debit"] else "",
                    money.format_pence(r["credit"]) if r["credit"] else ""))
            tree.insert("", "end", tags=("total",), values=(
                "", "TOTAL", money.format_pence(tb["total_debit"]),
                money.format_pence(tb["total_credit"])))
            balanced = tb["total_debit"] == tb["total_credit"]
            status.config(text="Balanced ✓" if balanced else "NOT BALANCED ✗")

        refresh()

    # --------------------------------------------------------- Profit & Loss
    def show_profit_and_loss(self):
        self.current_view = "profit_and_loss"
        self._clear_container()
        self._report_header("Profit & Loss")

        bar = ttk.Frame(self.container)
        bar.pack(fill="x", pady=(0, 10))
        date_frame, get_range = self._make_date_filter(bar, lambda: refresh())
        date_frame.grid(row=0, column=0, sticky="w")

        tree = self._plain_tree(
            ("name", "amount"), ("", "Amount"), (420, 150), right_cols=("amount",))

        def refresh():
            start, end = get_range()
            pl = report_db.profit_and_loss(_iso(start), _iso(end))
            tree.delete(*tree.get_children())
            tree.insert("", "end", tags=("section",), values=("INCOME", ""))
            for r in pl["income"]:
                tree.insert("", "end", values=(f"  {r['name']}", money.format_pence(r["amount"])))
            tree.insert("", "end", tags=("total",),
                        values=("Total income", money.format_pence(pl["total_income"])))
            tree.insert("", "end", values=("", ""))
            tree.insert("", "end", tags=("section",), values=("EXPENSES", ""))
            for r in pl["expenses"]:
                tree.insert("", "end", values=(f"  {r['name']}", money.format_pence(r["amount"])))
            tree.insert("", "end", tags=("total",),
                        values=("Total expenses", money.format_pence(pl["total_expense"])))
            tree.insert("", "end", values=("", ""))
            tree.insert("", "end", tags=("total",),
                        values=("NET PROFIT", money.format_pence(pl["net_profit"])))

        refresh()

    # --------------------------------------------------------- Balance Sheet
    def show_balance_sheet(self):
        self.current_view = "balance_sheet"
        self._clear_container()
        self._report_header("Balance Sheet")

        bar = ttk.Frame(self.container)
        bar.pack(fill="x", pady=(0, 10))
        date_frame, get_range = self._make_date_filter(bar, lambda: refresh())
        date_frame.grid(row=0, column=0, sticky="w")

        tree = self._plain_tree(
            ("name", "amount"), ("", "Amount"), (420, 150), right_cols=("amount",))
        status = ttk.Label(self.container, text="", font=_MONO)
        status.pack(anchor="e", pady=(8, 0))

        def section(title, rows, total_label, total):
            tree.insert("", "end", tags=("section",), values=(title, ""))
            for r in rows:
                tree.insert("", "end", values=(f"  {r['name']}", money.format_pence(r["amount"])))
            tree.insert("", "end", tags=("total",),
                        values=(total_label, money.format_pence(total)))
            tree.insert("", "end", values=("", ""))

        def refresh():
            _, end = get_range()
            bs = report_db.balance_sheet(as_at=_iso(end))
            tree.delete(*tree.get_children())
            section("ASSETS", bs["assets"], "Total assets", bs["total_assets"])
            section("LIABILITIES", bs["liabilities"], "Total liabilities", bs["total_liabilities"])
            equity_rows = list(bs["equity"]) + [
                {"name": "Retained profit", "amount": bs["retained_profit"]}]
            section("EQUITY", equity_rows, "Total equity", bs["total_equity"])
            tree.insert("", "end", tags=("total",), values=(
                "LIABILITIES + EQUITY", money.format_pence(bs["total_liabilities_equity"])))
            balanced = bs["total_assets"] == bs["total_liabilities_equity"]
            status.config(text="Balanced ✓" if balanced else "NOT BALANCED ✗")

        refresh()

    # ------------------------------------------------------------ VAT Return
    def show_vat_return(self):
        self.current_view = "vat_return"
        self._clear_container()
        self._report_header("VAT Return")

        # Period selection / creation.
        bar = ttk.LabelFrame(self.container, text="VAT period", padding=10)
        bar.pack(fill="x", pady=(0, 10))
        periods = vat_db.get_periods()
        period_labels = {self._period_label(p): p["id"] for p in periods}
        period_var = tk.StringVar()
        ttk.Label(bar, text="Period:").grid(row=0, column=0, sticky="w")
        period_combo = ttk.Combobox(bar, state="readonly", width=34, textvariable=period_var,
                                    values=list(period_labels))
        period_combo.grid(row=0, column=1, padx=(6, 16))
        if period_labels:
            period_combo.current(0)

        ttk.Label(bar, text="New: start").grid(row=0, column=2, sticky="w")
        start_entry = ttk.Entry(bar, width=12)
        start_entry.grid(row=0, column=3, padx=(6, 6))
        ttk.Label(bar, text="end").grid(row=0, column=4, sticky="w")
        end_entry = ttk.Entry(bar, width=12)
        end_entry.grid(row=0, column=5, padx=(6, 6))

        # 9-box display.
        boxes_frame = ttk.LabelFrame(self.container, text="Return (figures in £)", padding=12)
        boxes_frame.pack(fill="x", pady=(0, 10))
        box_labels = {}
        descriptions = [
            ("box1", "Box 1  VAT due on sales"),
            ("box2", "Box 2  VAT due on acquisitions"),
            ("box3", "Box 3  Total VAT due"),
            ("box4", "Box 4  VAT reclaimed on purchases"),
            ("box5", "Box 5  Net VAT to pay / reclaim"),
            ("box6", "Box 6  Total sales ex VAT"),
            ("box7", "Box 7  Total purchases ex VAT"),
            ("box8", "Box 8  EC goods supplied"),
            ("box9", "Box 9  EC goods acquired"),
        ]
        for i, (key, text) in enumerate(descriptions):
            ttk.Label(boxes_frame, text=text, font=_MONO).grid(
                row=i, column=0, sticky="w", pady=2, padx=(0, 16))
            val = ttk.Label(boxes_frame, text="—", font=_SECTION)
            val.grid(row=i, column=1, sticky="e", pady=2)
            box_labels[key] = val
        status = ttk.Label(self.container, text="", font=_MONO)
        status.pack(anchor="w")

        ttk.Label(self.container, font=("Consolas", 9),
                  text="Figures are computed from the ledger. File with HMRC via your "
                       "accounting software (Xero/QuickBooks) or a bridging tool, then "
                       "mark the period filed to lock it.").pack(anchor="w", pady=(8, 8))

        def show_boxes(boxes, filed):
            for key, label in box_labels.items():
                label.config(text=money.format_pence(boxes[key]))

        def selected_period_id():
            return period_labels.get(period_var.get())

        def add_period():
            s, e = daterange.to_iso(start_entry.get().strip()), daterange.to_iso(end_entry.get().strip())
            if not (daterange.parse(s) and daterange.parse(e)):
                messagebox.showwarning("Dates", "Enter a valid start and end date (DD/MM/YY).")
                return
            try:
                vat_db.create_period(s, e)
            except Exception:
                messagebox.showerror("Period", "That period already exists.")
                return
            self.show_vat_return()

        def compute():
            pid = selected_period_id()
            if pid is None:
                messagebox.showinfo("No period", "Create or select a VAT period first.")
                return
            try:
                boxes = vat_db.compute_and_save(pid)
            except ValueError as exc:
                # Filed period: show the stored figures read-only.
                saved = vat_db.get_return(pid)
                if saved:
                    show_boxes({k: saved[k] for k in box_labels}, filed=True)
                    status.config(text=str(exc))
                return
            show_boxes(boxes, filed=False)
            status.config(text="Computed. Review, then Mark as Filed once submitted to HMRC.")

        def mark_filed():
            pid = selected_period_id()
            if pid is None:
                return
            if not messagebox.askyesno(
                "Mark filed",
                "Mark this VAT period as filed? This locks every journal in the period "
                "so it can no longer be edited (corrections post to the open period)."):
                return
            vat_db.compute_and_save(pid)
            vat_db.mark_filed(pid)
            self.show_vat_return()

        ttk.Button(bar, text="Add period", command=add_period).grid(row=0, column=6, padx=(6, 0))
        actions = ttk.Frame(self.container)
        actions.pack(anchor="w")
        ttk.Button(actions, text="Compute", command=compute).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="Mark as Filed", command=mark_filed).pack(side="left")

        # Pre-fill from the selected period if it already has a saved return.
        def on_period(_event=None):
            pid = selected_period_id()
            saved = vat_db.get_return(pid) if pid else None
            if saved:
                show_boxes({k: saved[k] for k in box_labels}, filed=bool(saved["filed_at"]))
                status.config(text=("Filed " + saved["filed_at"][:10]) if saved["filed_at"]
                              else "Saved (not filed).")
            else:
                for label in box_labels.values():
                    label.config(text="—")
                status.config(text="")
        period_combo.bind("<<ComboboxSelected>>", on_period)
        on_period()

    def _period_label(self, period):
        return (f"{daterange.format_stored(period['start'])} – "
                f"{daterange.format_stored(period['end'])}  [{period['status']}]")
