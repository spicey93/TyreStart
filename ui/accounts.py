"""Chart of accounts screens (mixin for App)."""
import datetime
import tkinter as tk
from tkinter import ttk
from ui import dialogs as messagebox

from core import accounts as account_db
from core import opening as opening_db
from core import money, daterange

from ui.common import make_sortable


class ChartOfAccountsMixin:
    def show_chart_of_accounts(self):
        self.current_view = "chart_of_accounts"
        self._clear_container()

        header = ttk.Frame(self.container)
        header.pack(fill="x", pady=(0, 10))
        ttk.Label(header, text="Chart of Accounts",
                  font=("Consolas", 20, "bold")).pack(side="left")
        ttk.Button(header, text="New Account",
                   command=self.show_account_form).pack(side="right")

        columns = ("code", "name", "type", "side", "bank")
        headings = ("Code", "Name", "Type", "Normal Side", "Bank")
        widths = (80, 280, 110, 110, 60)
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
        make_sortable(tree)

        for a in account_db.get_all(active_only=False):
            tree.insert("", "end", iid=str(a["id"]), values=(
                a["code"], a["name"], a["account_type"].title(),
                a["normal_side"].title(), "Yes" if a["is_bank"] else ""))

        ttk.Label(self.container,
                  text="Double-click an account to rename it. System accounts keep "
                       "their code and type.").pack(anchor="w", pady=(8, 0))

        def open_selected(event=None):
            sel = tree.selection()
            if sel:
                self.show_account_form(account_db.get(int(sel[0])))

        tree.bind("<Double-1>", open_selected)
        tree.bind("<Return>", open_selected)

    def show_account_form(self, account=None):
        """Create a new account, or rename an existing one (code/type are fixed)."""
        self.current_view = "account_form"
        self._clear_container()
        editing = account is not None
        is_system = editing and account["system_tag"]
        ttk.Label(self.container, text="Edit Account" if editing else "New Account",
                  font=("Consolas", 20, "bold")).pack(anchor="w", pady=(0, 15))

        form = ttk.LabelFrame(self.container, text="Account Details", padding=12)
        form.pack(anchor="w", fill="x")

        ttk.Label(form, text="Code:").grid(row=0, column=0, sticky="w", pady=5, padx=(0, 10))
        code_entry = ttk.Entry(form, width=20)
        code_entry.grid(row=0, column=1, sticky="w", pady=5)

        ttk.Label(form, text="Name:").grid(row=1, column=0, sticky="w", pady=5, padx=(0, 10))
        name_entry = ttk.Entry(form, width=40)
        name_entry.grid(row=1, column=1, sticky="w", pady=5)

        ttk.Label(form, text="Type:").grid(row=2, column=0, sticky="w", pady=5, padx=(0, 10))
        type_var = tk.StringVar()
        type_combo = ttk.Combobox(form, state="readonly", width=18, textvariable=type_var,
                                  values=list(account_db.ACCOUNT_TYPES))
        type_combo.grid(row=2, column=1, sticky="w", pady=5)
        type_combo.current(0)

        if editing:
            code_entry.insert(0, account["code"])
            name_entry.insert(0, account["name"])
            type_var.set(account["account_type"])
            # Existing accounts keep their code and type.
            code_entry.config(state="disabled")
            type_combo.config(state="disabled")
        else:
            name_entry.focus_set()

        def save():
            code = code_entry.get().strip()
            name = name_entry.get().strip()
            if not name:
                messagebox.showwarning("Missing name", "Please enter an account name.")
                return None
            if editing:
                account_db.update_account(account["id"], name)
                return account["id"]
            if not code:
                messagebox.showwarning("Missing code", "Please enter an account code.")
                return None
            try:
                return account_db.create_account(code, name, type_var.get())
            except account_db.DuplicateCodeError:
                messagebox.showerror("Duplicate code",
                                     f"An account with code '{code}' already exists.")
                return None

        self._register_form(save=save, back=self.show_chart_of_accounts)

    # ----------------------------------------------------------- Opening balances
    def show_opening_balances(self):
        """Enter the business's starting position. The user fills in what they have
        (assets) and owe (liabilities); the difference is posted to Capital
        Introduced so it always balances. Saved when leaving the page."""
        self.current_view = "opening_balances"
        self._clear_container()
        body = self._scrollable_body()

        ttk.Label(body, text="Opening Balances",
                  font=("Consolas", 20, "bold")).pack(anchor="w", pady=(0, 12))

        existing = opening_db.get_opening()

        head = ttk.Frame(body)
        head.pack(anchor="w", fill="x")
        ttk.Label(head, text="As-at date:").grid(row=0, column=0, sticky="w", padx=(0, 10))
        date_var = tk.StringVar(
            value=daterange.format_stored(existing["date"]) if existing["date"]
            else datetime.date.today().strftime("%d/%m/%y"))
        ttk.Entry(head, textvariable=date_var, width=14).grid(row=0, column=1, sticky="w")
        ttk.Label(body, font=("Consolas", 9),
                  text="The date your figures are as at (usually when you start using the "
                       "system). Enter what you have and what you owe — the difference is "
                       "your capital.").pack(anchor="w", pady=(6, 10))

        accounts = opening_db.editable_accounts()
        amount_vars = {}
        cap_var = tk.StringVar()

        def recompute(*_):
            net = 0
            for acc in accounts:
                raw = amount_vars[acc["id"]].get().strip()
                try:
                    pence = money.to_pence(raw) if raw else 0
                except Exception:
                    pence = 0
                net += pence if acc["normal_side"] == "debit" else -pence
            cap_var.set(f"Capital Introduced (balancing figure): {money.format_pence(net)}")

        titles = (("asset", "ASSETS — what the business has"),
                  ("liability", "LIABILITIES — what the business owes"),
                  ("equity", "EQUITY (other than capital)"))
        for account_type, title in titles:
            rows = [a for a in accounts if a["account_type"] == account_type]
            if not rows:
                continue
            frame = ttk.LabelFrame(body, text=title, padding=12)
            frame.pack(anchor="w", fill="x", pady=(0, 10))
            for i, acc in enumerate(rows):
                ttk.Label(frame, text=f"{acc['code']} - {acc['name']}").grid(
                    row=i, column=0, sticky="w", pady=3, padx=(0, 14))
                var = tk.StringVar()
                pence = existing["balances"].get(acc["id"], 0)
                if pence:
                    var.set(f"{money.from_pence(pence):.2f}")
                amount_vars[acc["id"]] = var
                entry = ttk.Entry(frame, textvariable=var, width=14, justify="right")
                entry.grid(row=i, column=1, sticky="w", pady=3)
                entry.bind("<KeyRelease>", recompute)

        cap_frame = ttk.LabelFrame(body, text="Capital", padding=12)
        cap_frame.pack(anchor="w", fill="x")
        ttk.Label(cap_frame, textvariable=cap_var,
                  font=("Consolas", 12, "bold")).pack(anchor="w")
        recompute()

        def save():
            date_text = date_var.get().strip()
            if not daterange.parse(date_text):
                messagebox.showwarning("Date", "Enter a valid as-at date (DD/MM/YY).")
                return None
            amounts = {}
            for acc in accounts:
                raw = amount_vars[acc["id"]].get().strip()
                if not raw:
                    continue
                try:
                    amounts[acc["id"]] = money.to_pence(raw)
                except Exception:
                    messagebox.showwarning("Amount", f"'{raw}' is not a valid amount.")
                    return None
            opening_db.set_opening_balances(date_text, amounts)
            return True

        self._register_form(save=save, back=self.show_chart_of_accounts)
