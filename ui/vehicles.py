"""Vehicle screens (mixin for App).

Look up a vehicle by registration (VRM). We check our own database first and only
call the UK Vehicle Data API (using the key from Configuration → API Keys) for a
VRM we don't already hold; successful lookups are saved for next time.

A successful lookup shows a tabbed view: **Details** (a comprehensive read-only of
the vehicle, including tyre fitments) and **History** (every sale linked to the
vehicle).
"""
import tkinter as tk
from tkinter import ttk
from ui import dialogs as messagebox

from core import daterange
from core import sales as sale_db
from core import vehicles as vehicle_db
from core import ukvehicledata

from ui.common import make_sortable


class VehiclesMixin:
    def show_vehicles(self):
        self.current_view = "vehicles"
        self._clear_container()

        header = ttk.Frame(self.container)
        header.pack(fill="x", pady=(0, 10))
        ttk.Label(header, text="Vehicles", font=("Consolas", 20, "bold")).pack(side="left")

        bar = ttk.Frame(self.container)
        bar.pack(fill="x", pady=(0, 10))
        vrm_var = tk.StringVar()
        ttk.Label(bar, text="VRM:").grid(row=0, column=0, sticky="w")
        vrm_entry = ttk.Entry(bar, textvariable=vrm_var, width=14, font=("Consolas", 14, "bold"))
        vrm_entry.grid(row=0, column=1, sticky="w", padx=(8, 10))
        vrm_entry.focus_set()
        vrm_entry.bind("<Return>", lambda e: do_lookup())
        ttk.Button(bar, text="Look up", command=lambda: do_lookup()).grid(row=0, column=2)

        # A single summary line above the tabs, then the Details / History notebook.
        info_var = tk.StringVar(value="Enter a registration and press Look up.")
        ttk.Label(self.container, textvariable=info_var,
                  font=("Consolas", 14, "bold")).pack(anchor="w", pady=(0, 2))
        source_var = tk.StringVar(value="")
        ttk.Label(self.container, textvariable=source_var,
                  font=("Consolas", 9)).pack(anchor="w", pady=(0, 8))

        notebook = ttk.Notebook(self.container)
        notebook.pack(fill="both", expand=True)
        details_tab = ttk.Frame(notebook, padding=12)
        history_tab = ttk.Frame(notebook, padding=12)
        notebook.add(details_tab, text="Details")
        notebook.add(history_tab, text="History")

        def render_details(row, result):
            for child in details_tab.winfo_children():
                child.destroy()

            # Comprehensive, read-only attribute grid from the stored API response.
            attrs = vehicle_db.attributes(row)
            grid = ttk.Frame(details_tab)
            grid.pack(anchor="w", fill="x")
            if attrs:
                half = (len(attrs) + 1) // 2  # two columns of label/value pairs
                for i, (label, value) in enumerate(attrs):
                    col = 0 if i < half else 2
                    r = i if i < half else i - half
                    ttk.Label(grid, text=f"{label}:").grid(
                        row=r, column=col, sticky="w", padx=(0, 10), pady=3)
                    ttk.Label(grid, text=str(value), font=("Consolas", 10, "bold")).grid(
                        row=r, column=col + 1, sticky="w", padx=(0, 30), pady=3)
            else:
                ttk.Label(grid, text="No further vehicle details available.").pack(anchor="w")

            # Tyre fitments.
            ttk.Label(details_tab, text="Tyre fitments",
                      font=("Consolas", 12, "bold")).pack(anchor="w", pady=(14, 4))
            columns = ("front", "rear", "load", "speed", "front_psi", "rear_psi", "rim")
            headings = ("Front Size", "Rear Size", "Load", "Speed",
                        "Front PSI", "Rear PSI", "Rim")
            widths = (120, 120, 60, 60, 90, 90, 100)
            tf = ttk.Frame(details_tab)
            tf.pack(fill="both", expand=True)
            tree = ttk.Treeview(tf, columns=columns, show="headings", height=5)
            sb = ttk.Scrollbar(tf, orient="vertical", command=tree.yview)
            tree.configure(yscrollcommand=sb.set)
            sb.pack(side="right", fill="y")
            tree.pack(side="left", fill="both", expand=True)
            for col, heading, width in zip(columns, headings, widths):
                tree.heading(col, text=heading)
                tree.column(col, width=width,
                            anchor="w" if col in ("front", "rear", "rim") else "e")
            make_sortable(tree)
            tyres = result.get("tyres") or []
            for i, t in enumerate(tyres):
                tree.insert("", "end", iid=str(i), values=(
                    t.get("front_size") or "", t.get("rear_size") or "",
                    t.get("load_index") or "", t.get("speed_index") or "",
                    t.get("front_psi") if t.get("front_psi") is not None else "",
                    t.get("rear_psi") if t.get("rear_psi") is not None else "",
                    t.get("rim_size") or ""))
            status = ttk.Label(details_tab, text="")
            status.pack(anchor="w", pady=(6, 0))
            if not tyres:
                status.config(text="No tyre data for this vehicle.")

        def render_history(row):
            for child in history_tab.winfo_children():
                child.destroy()
            rows = sale_db.list_for_vehicle(row["id"])

            def cells(r):
                return {
                    "reference": r["reference"] or "",
                    "customer": r["customer_name"],
                    "status": r["status"],
                    "date": daterange.format_stored(r["date"]),
                    "total": f"{r['total']:,.2f}",
                }

            self._searchable_table(
                history_tab,
                columns=("reference", "customer", "status", "date", "total"),
                headings=("Reference", "Customer", "Status", "Date", "Total"),
                rows=rows, cells=cells,
                widths=(150, 220, 90, 110, 110),
                right_cols=("total",),
                field_labels=[("All", None), ("Reference", "reference"),
                              ("Customer", "customer"), ("Status", "status")],
                empty_text="No sales linked to this vehicle yet.",
                iid=lambda r: str(r["id"]),
                on_open=lambda sid: self.show_sale_form(sale_db.get_sale(sid)),
            )

        def show_result(result):
            make = result.get("make") or ""
            model = result.get("model") or ""
            year = result.get("build_year")
            line = f"{result['vrm']}   {make} {model}".rstrip()
            if year:
                line += f"  ({year})"
            info_var.set(line)
            source_var.set("From the UK Vehicle Data API."
                           if result["source"] == "api" else "From your saved vehicles.")
            row = vehicle_db.get_by_vrm(result["vrm"])
            render_details(row, result)
            render_history(row)
            notebook.select(details_tab)

        def do_lookup():
            try:
                result = vehicle_db.lookup(vrm_var.get())
            except vehicle_db.NoApiKeyError as exc:
                messagebox.showwarning("API key needed", str(exc))
                return
            except ukvehicledata.LookupError as exc:
                messagebox.showwarning("Not found", f"The lookup was not successful:\n\n{exc}")
                return
            except vehicle_db.VehicleError as exc:
                messagebox.showwarning("Vehicle lookup", str(exc))
                return
            except Exception as exc:  # network/parse problems
                messagebox.showerror(
                    "Lookup failed",
                    f"Could not reach the UK Vehicle Data service.\n\n{exc}")
                return
            vrm_var.set(result["vrm"])
            show_result(result)
