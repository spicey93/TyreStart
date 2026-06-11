"""Pricing-rule screens (mixin for App)."""
import tkinter as tk
from tkinter import ttk, messagebox

from core import pricing as pricing_db

from ui.common import make_sortable


class PricingMixin:
    # --------------------------------------------------------------- Pricing Rules

    @staticmethod
    def _format_rule_formula(r):
        parts = []
        if r["uplift_percent"]:
            parts.append(f"{r['uplift_percent']:g}% {r['uplift_type']}")
        if r["fixed_uplift"]:
            parts.append(f"+{r['fixed_uplift']:g} fixed")
        text = ", ".join(parts) if parts else "no uplift"
        if r["round_up"]:
            text += " (round up)"
        return text

    @staticmethod
    def _format_rule_conditions(r):
        conds = []
        if r["cond_cost_gt"] is not None:
            conds.append(f"cost > {r['cond_cost_gt']:g}")
        if r["pricing_key"]:
            conds.append(f"key = {r['pricing_key']}")
        if r["product_group"]:
            conds.append(f"group = {r['product_group']}")
        return ", ".join(conds) if conds else "any product"

    def show_pricing_rules(self):
        """List pricing rules with add/delete. Rules auto-apply across products."""
        self.current_view = "pricing_rules"
        self._clear_container()

        header = ttk.Frame(self.container)
        header.pack(fill="x", pady=(0, 10))
        ttk.Label(header, text="Pricing Rules", font=("Segoe UI", 20, "bold")).pack(side="left")
        ttk.Button(header, text="New Rule", command=self.show_pricing_rule_form).pack(side="right")

        ttk.Label(
            self.container,
            text="Rules turn a product's average cost into a retail price. Where "
            "several rules match, the most specific one (most conditions) wins.",
            foreground="gray",
        ).pack(anchor="w", pady=(0, 10))

        columns = ("name", "formula", "conditions")
        headings = ("Name", "Formula", "Conditions")
        widths = (200, 320, 300)
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

        status_label = ttk.Label(self.container, text="")
        status_label.pack(anchor="w", pady=(8, 0))

        def refresh():
            tree.delete(*tree.get_children())
            rules = pricing_db.list_rules()
            for r in rules:
                tree.insert(
                    "", "end", iid=str(r["id"]),
                    values=(r["name"], self._format_rule_formula(r),
                            self._format_rule_conditions(r)),
                )
            status_label.config(
                text=f"{len(rules)} rule(s)." if rules
                else "No pricing rules yet. Use New Rule to add one."
            )

        def delete_selected():
            selection = tree.selection()
            if not selection:
                messagebox.showinfo("No selection", "Please select a rule first.")
                return
            if messagebox.askyesno("Delete rule", "Delete this pricing rule?"):
                pricing_db.delete_rule(int(selection[0]))
                refresh()

        tree.bind("<Delete>", lambda e: delete_selected())
        ttk.Label(
            self.container,
            text="Select a rule and press Delete to remove it.",
            foreground="#666666",
        ).pack(anchor="w", pady=(10, 0))
        refresh()

    def show_pricing_rule_form(self):
        """Create a pricing rule (name, variables, and matching conditions)."""
        self.current_view = "pricing_rule_form"
        self._clear_container()
        ttk.Label(
            self.container, text="New Pricing Rule", font=("Segoe UI", 20, "bold")
        ).pack(anchor="w", pady=(0, 15))

        name_var = tk.StringVar()
        type_var = tk.StringVar(value="markup")
        pct_var = tk.StringVar()
        fixed_var = tk.StringVar()
        round_var = tk.BooleanVar(value=False)
        cost_gt_var = tk.StringVar()
        key_var = tk.StringVar()
        group_var = tk.StringVar()

        form = ttk.Frame(self.container)
        form.pack(anchor="w")

        ttk.Label(form, text="Name:").grid(row=0, column=0, sticky="w", pady=5, padx=(0, 10))
        ttk.Entry(form, textvariable=name_var, width=38).grid(
            row=0, column=1, columnspan=2, sticky="w", pady=5
        )

        # --- Variables ---
        ttk.Label(form, text="Variables", font=("Segoe UI", 11, "bold")).grid(
            row=1, column=0, columnspan=3, sticky="w", pady=(12, 4)
        )
        ttk.Label(form, text="Percentage uplift:").grid(row=2, column=0, sticky="w", pady=5, padx=(0, 10))
        ttk.Entry(form, textvariable=pct_var, width=12).grid(row=2, column=1, sticky="w", pady=5)
        ttk.Combobox(
            form, state="readonly", width=10, textvariable=type_var,
            values=list(pricing_db.PERCENT_TYPES),
        ).grid(row=2, column=2, sticky="w", pady=5)

        ttk.Label(form, text="Fixed uplift:").grid(row=3, column=0, sticky="w", pady=5, padx=(0, 10))
        ttk.Entry(form, textvariable=fixed_var, width=12).grid(row=3, column=1, sticky="w", pady=5)

        ttk.Checkbutton(
            form, text="Round up to the nearest whole number", variable=round_var
        ).grid(row=4, column=1, columnspan=2, sticky="w", pady=5)

        # --- Conditions ---
        ttk.Label(form, text="Conditions", font=("Segoe UI", 11, "bold")).grid(
            row=5, column=0, columnspan=3, sticky="w", pady=(12, 4)
        )
        ttk.Label(form, text="(leave blank for no condition)", foreground="gray").grid(
            row=6, column=0, columnspan=3, sticky="w"
        )
        ttk.Label(form, text="Unit cost greater than:").grid(row=7, column=0, sticky="w", pady=5, padx=(0, 10))
        ttk.Entry(form, textvariable=cost_gt_var, width=12).grid(row=7, column=1, sticky="w", pady=5)
        ttk.Label(form, text="Pricing key:").grid(row=8, column=0, sticky="w", pady=5, padx=(0, 10))
        ttk.Entry(form, textvariable=key_var, width=20).grid(row=8, column=1, columnspan=2, sticky="w", pady=5)
        ttk.Label(form, text="Product group:").grid(row=9, column=0, sticky="w", pady=5, padx=(0, 10))
        ttk.Entry(form, textvariable=group_var, width=20).grid(row=9, column=1, columnspan=2, sticky="w", pady=5)

        def save():
            name = name_var.get().strip()
            if not name:
                messagebox.showwarning("Missing name", "Please enter a rule name.")
                return
            try:
                pct = float(pct_var.get()) if pct_var.get().strip() else 0.0
                fixed = float(fixed_var.get()) if fixed_var.get().strip() else 0.0
                cost_gt = float(cost_gt_var.get()) if cost_gt_var.get().strip() else None
            except ValueError:
                messagebox.showwarning(
                    "Invalid", "Percentage, fixed uplift and unit cost must be numbers."
                )
                return
            return pricing_db.create_rule(
                name=name, uplift_type=type_var.get(), uplift_percent=pct,
                fixed_uplift=fixed, round_up=round_var.get(), cond_cost_gt=cost_gt,
                pricing_key=key_var.get().strip(), product_group=group_var.get().strip(),
            )

        self._register_form(save=save, back=self.show_pricing_rules)

    # ------------------------------------------------------------------ Purchases
