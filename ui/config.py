"""Configuration screens (mixin for App): API keys and other app settings."""
import tkinter as tk
from tkinter import ttk

from core import settings
from core import dbconfig

from ui.common import make_sortable  # noqa: F401 (kept for parity / future lists)


class ConfigMixin:
    def show_api_keys(self):
        """Edit third-party API keys. Saved when you leave the page (you're asked
        first), like the other forms."""
        self.current_view = "api_keys"
        self._clear_container()
        ttk.Label(self.container, text="API Keys",
                  font=("Consolas", 20, "bold")).pack(anchor="w", pady=(0, 15))

        form = ttk.LabelFrame(self.container, text="API Keys", padding=12)
        form.pack(anchor="w", fill="x")
        form.columnconfigure(1, weight=1)

        ttk.Label(form, text="UK Vehicle Data:").grid(
            row=0, column=0, sticky="w", pady=6, padx=(0, 10))
        ukvd_var = tk.StringVar(value=settings.get(settings.UKVD_API_KEY) or "")
        ukvd_entry = ttk.Entry(form, textvariable=ukvd_var, width=52)
        # API keys can be case-sensitive — don't force this field to upper case.
        ukvd_entry._allow_mixed_case = True
        ukvd_entry.grid(row=0, column=1, sticky="ew", pady=6)
        ukvd_entry.focus_set()

        ttk.Label(
            self.container, font=("Consolas", 9),
            text="Used for VRM lookups on the Vehicles screen. Stored locally in app.db.",
        ).pack(anchor="w", pady=(8, 0))

        def save():
            settings.set(settings.UKVD_API_KEY, ukvd_var.get().strip())
            return True

        self._register_form(save=save, back=self.show_enquiry)

    def show_database_config(self):
        """Enter the Supabase connection details used to share data between
        machines. Saved (to a local file, not the database) when you leave the
        page. Linking the app to this database is a separate, later step."""
        self.current_view = "database_config"
        self._clear_container()
        ttk.Label(self.container, text="Database",
                  font=("Consolas", 20, "bold")).pack(anchor="w", pady=(0, 15))

        form = ttk.LabelFrame(self.container, text="Supabase Connection", padding=12)
        form.pack(anchor="w", fill="x")
        form.columnconfigure(1, weight=1)

        current = dbconfig.load()
        # (field key, label, mask-on-screen?) — secrets are shown as •••• .
        rows = [
            (dbconfig.PROJECT_URL, "Project URL", False),
            (dbconfig.ANON_KEY, "Anon Key", False),
            (dbconfig.DB_PASSWORD, "Database Password", True),
            (dbconfig.POOLER_CONNECTION_STRING, "Session Pooler Connection String", True),
        ]
        vars_by_field = {}
        first_entry = None
        for row, (field, label, secret) in enumerate(rows):
            ttk.Label(form, text=label + ":").grid(
                row=row, column=0, sticky="w", pady=6, padx=(0, 10))
            var = tk.StringVar(value=current.get(field, ""))
            entry = ttk.Entry(form, textvariable=var, width=64,
                              show="•" if secret else "")
            # Connection details are case-sensitive — never force upper case.
            entry._allow_mixed_case = True
            entry.grid(row=row, column=1, sticky="ew", pady=6)
            vars_by_field[field] = var
            if first_entry is None:
                first_entry = entry
        if first_entry is not None:
            first_entry.focus_set()

        ttk.Label(
            self.container, font=("Consolas", 9),
            text=("Used to share data between computers via Supabase. Stored locally "
                  "in db_config.json (kept out of version control), not in the "
                  "database. Linking the app to this database is the next step."),
        ).pack(anchor="w", pady=(8, 0))

        def save():
            dbconfig.save({field: var.get() for field, var in vars_by_field.items()})
            return True

        self._register_form(save=save, back=self.show_enquiry)
