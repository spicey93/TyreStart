"""Suppliers data-access layer.

All supplier SQL lives here. Uses the shared connection from the central
database (database.py), so suppliers are stored in app.db alongside products.
"""

import sqlite3

from core.database import get_connection


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

        # Migrate databases created before account_number existed.
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(suppliers)")}
        if "account_number" not in columns:
            conn.execute("ALTER TABLE suppliers ADD COLUMN account_number TEXT")

        # Enforce unique supplier names, case-insensitively. Works for both
        # fresh and migrated databases.
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_suppliers_name "
            "ON suppliers(name COLLATE NOCASE)"
        )


def add_supplier(name, account_number="", contact="", email="", phone=""):
    """Insert a supplier and return its new id.

    Raises DuplicateNameError if the name already exists.
    """
    with get_connection() as conn:
        try:
            cursor = conn.execute(
                "INSERT INTO suppliers (name, account_number, contact, email, phone) "
                "VALUES (?, ?, ?, ?, ?)",
                (name, account_number, contact, email, phone),
            )
        except sqlite3.IntegrityError as exc:
            raise DuplicateNameError(name) from exc
        return cursor.lastrowid


def update_supplier(supplier_id, name, account_number="", contact="", email="", phone=""):
    """Update an existing supplier.

    Raises DuplicateNameError if the new name collides with another supplier.
    """
    with get_connection() as conn:
        try:
            conn.execute(
                "UPDATE suppliers "
                "SET name = ?, account_number = ?, contact = ?, email = ?, phone = ? "
                "WHERE id = ?",
                (name, account_number, contact, email, phone, supplier_id),
            )
        except sqlite3.IntegrityError as exc:
            raise DuplicateNameError(name) from exc


def get_supplier(supplier_id):
    """Return a single supplier Row by id, or None if not found."""
    with get_connection() as conn:
        return conn.execute(
            "SELECT id, name, account_number, contact, email, phone "
            "FROM suppliers WHERE id = ?",
            (supplier_id,),
        ).fetchone()


def get_all_suppliers():
    """Return all suppliers as a list of sqlite3.Row (access by column name)."""
    with get_connection() as conn:
        return conn.execute(
            "SELECT id, name, account_number, contact, email, phone "
            "FROM suppliers ORDER BY name COLLATE NOCASE"
        ).fetchall()


def delete_supplier(supplier_id):
    """Delete a supplier by id."""
    with get_connection() as conn:
        conn.execute("DELETE FROM suppliers WHERE id = ?", (supplier_id,))
