"""Suppliers data-access layer.

All supplier SQL lives here. Uses the shared connection from the central
database (database.py), so suppliers are stored in app.db alongside products.
"""

import sqlite3

from core.database import get_connection

# Account status options (label only for now — no behavioural enforcement).
STATUSES = ("Open", "Cash Only", "On Hold", "Closed")

# The extra account fields added after the original name/contact set. Each is an
# optional column with a sensible empty/zero default; kept in one place so the
# table, INSERT, UPDATE and SELECT all stay in step.
_EXTRA_COLUMNS = (
    ("status", "TEXT", "Open"),
    ("address", "TEXT", ""),
    ("postcode", "TEXT", ""),
    ("credit_limit", "REAL", 0.0),
    ("vat_code", "TEXT", ""),
    ("vat_number", "TEXT", ""),
    ("payment_method", "TEXT", ""),
)

# Every selectable column, in a stable order, for SELECTs.
_ALL_COLUMNS = ("id", "name", "account_number", "contact", "email", "phone",
                *[c for c, _, _ in _EXTRA_COLUMNS])
_SELECT = ", ".join(_ALL_COLUMNS)


class DuplicateNameError(Exception):
    """Raised when a supplier name collides with an existing one."""


def create_table():
    """Create the suppliers table (and migrate older databases) if needed."""
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS suppliers (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                name           TEXT NOT NULL,
                account_number TEXT,
                contact        TEXT,
                email          TEXT,
                phone          TEXT
            )
            """
        )

        # Migrate older databases by adding any missing columns.
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(suppliers)")}
        if "account_number" not in columns:
            conn.execute("ALTER TABLE suppliers ADD COLUMN account_number TEXT")
        for name, sql_type, default in _EXTRA_COLUMNS:
            if name not in columns:
                default_sql = repr(default) if isinstance(default, str) else default
                conn.execute(
                    f"ALTER TABLE suppliers ADD COLUMN {name} {sql_type} "
                    f"DEFAULT {default_sql}"
                )

        # Enforce unique supplier names, case-insensitively. Works for both
        # fresh and migrated databases.
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_suppliers_name "
            "ON suppliers(name COLLATE NOCASE)"
        )


def add_supplier(name, account_number="", contact="", email="", phone="", *,
                 status="Open", address="", postcode="", credit_limit=0.0,
                 vat_code="", vat_number="", payment_method=""):
    """Insert a supplier and return its new id.

    Raises DuplicateNameError if the name already exists.
    """
    with get_connection() as conn:
        try:
            cursor = conn.execute(
                "INSERT INTO suppliers "
                "(name, account_number, contact, email, phone, status, address, "
                " postcode, credit_limit, vat_code, vat_number, payment_method) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (name, account_number, contact, email, phone, status, address,
                 postcode, credit_limit, vat_code, vat_number, payment_method),
            )
        except sqlite3.IntegrityError as exc:
            raise DuplicateNameError(name) from exc
        return cursor.lastrowid


def update_supplier(supplier_id, name, account_number="", contact="", email="",
                    phone="", *, status="Open", address="", postcode="",
                    credit_limit=0.0, vat_code="", vat_number="", payment_method=""):
    """Update an existing supplier.

    Raises DuplicateNameError if the new name collides with another supplier.
    """
    with get_connection() as conn:
        try:
            conn.execute(
                "UPDATE suppliers SET name = ?, account_number = ?, contact = ?, "
                "email = ?, phone = ?, status = ?, address = ?, postcode = ?, "
                "credit_limit = ?, vat_code = ?, vat_number = ?, payment_method = ? "
                "WHERE id = ?",
                (name, account_number, contact, email, phone, status, address,
                 postcode, credit_limit, vat_code, vat_number, payment_method,
                 supplier_id),
            )
        except sqlite3.IntegrityError as exc:
            raise DuplicateNameError(name) from exc


def get_supplier(supplier_id):
    """Return a single supplier Row by id, or None if not found."""
    with get_connection() as conn:
        return conn.execute(
            f"SELECT {_SELECT} FROM suppliers WHERE id = ?",
            (supplier_id,),
        ).fetchone()


def get_all_suppliers():
    """Return all suppliers as a list of sqlite3.Row (access by column name)."""
    with get_connection() as conn:
        return conn.execute(
            f"SELECT {_SELECT} FROM suppliers ORDER BY name COLLATE NOCASE"
        ).fetchall()


def delete_supplier(supplier_id):
    """Delete a supplier by id."""
    with get_connection() as conn:
        conn.execute("DELETE FROM suppliers WHERE id = ?", (supplier_id,))
