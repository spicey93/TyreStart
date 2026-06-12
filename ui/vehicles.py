"""Vehicle screens (mixin for App).

Look up a vehicle by registration (VRM). We check our own database first and only
call the UK Vehicle Data API (using the key from Configuration → API Keys) for a
VRM we don't already hold; successful lookups are saved for next time.
"""
import tkinter as tk
from tkinter import ttk
from ui import dialogs as messagebox

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

        detail = ttk.LabelFrame(self.container, text="Vehicle", padding=12)
        detail.pack(fill="x", pady=(0, 10))
        info_var = tk.StringVar(value="Enter a registration and press Look up.")
        ttk.Label(detail, textvariable=info_var, font=("Consolas", 14, "bold")).pack(anchor="w")
        source_var = tk.StringVar(value="")
        ttk.Label(detail, textvariable=source_var, font=("Consolas", 9)).pack(anchor="w")

        ttk.Label(self.container, text="Tyre fitments",
                  font=("Consolas", 12, "bold")).pack(anchor="w", pady=(4, 4))
        columns = ("front", "rear", "load", "speed", "front_psi", "rear_psi", "rim")
        headings = ("Front Size", "Rear Size", "Load", "Speed",
                    "Front PSI", "Rear PSI", "Rim")
        widths = (120, 120, 60, 60, 90, 90, 100)
        table_frame = ttk.Frame(self.container)
        table_frame.pack(fill="both", expand=True)
        tree = ttk.Treeview(table_frame, columns=columns, show="headings")
        sb = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        tree.pack(side="left", fill="both", expand=True)
        for col, heading, width in zip(columns, headings, widths):
            tree.heading(col, text=heading)
            tree.column(col, width=width, anchor="w" if col in ("front", "rear", "rim") else "e")
        make_sortable(tree)

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
            tree.delete(*tree.get_children())
            tyres = result.get("tyres") or []
            for i, t in enumerate(tyres):
                tree.insert("", "end", iid=str(i), values=(
                    t.get("front_size") or "", t.get("rear_size") or "",
                    t.get("load_index") or "", t.get("speed_index") or "",
                    t.get("front_psi") if t.get("front_psi") is not None else "",
                    t.get("rear_psi") if t.get("rear_psi") is not None else "",
                    t.get("rim_size") or ""))
            if not tyres:
                source_var.set(source_var.get() + "  No tyre data for this vehicle.")

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
            tree.focus_set()
