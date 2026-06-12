"""Services data-access layer.

A service has a (unique) code, a name, a cost and a retail price. Stored in the
central app.db alongside the other entities.
"""

import sqlite3

from core import money
from core.database import get_connection


class DuplicateCodeError(Exception):
    """Raised when a service code collides with an existing one."""


def create_table():
    """Create the services table (with a unique code index) if needed."""
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS services (
                id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                service_code       TEXT,
                service_name       TEXT NOT NULL,
                cost               REAL,
                retail_price       REAL,
                cost_pence         INTEGER NOT NULL DEFAULT 0,
                retail_price_pence INTEGER NOT NULL DEFAULT 0,
                tagged_item_key    TEXT
            )
            """
        )
        # Migrate services created before the pence columns existed.
        cols = {row["name"] for row in conn.execute("PRAGMA table_info(services)")}
        if "cost_pence" not in cols:
            conn.execute("ALTER TABLE services ADD COLUMN cost_pence INTEGER NOT NULL DEFAULT 0")
        if "retail_price_pence" not in cols:
            conn.execute(
                "ALTER TABLE services ADD COLUMN retail_price_pence INTEGER NOT NULL DEFAULT 0"
            )
        # `tagged_item_key` (a product group) auto-adds this service to a sale when a
        # product of that group is sold.
        if "tagged_item_key" not in cols:
            conn.execute("ALTER TABLE services ADD COLUMN tagged_item_key TEXT")
        # Blank codes are stored as NULL so multiple uncoded services don't clash
        # (SQLite treats NULLs as distinct in a unique index).
        conn.execute("UPDATE services SET service_code = NULL WHERE service_code = ''")
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_services_code "
            "ON services(service_code COLLATE NOCASE)"
        )


def create_service(service_code, service_name, cost, retail_price, tagged_item_key=""):
    """Insert a service and return its new id.

    `tagged_item_key` (a product group, or blank) auto-adds it to a sale when a
    product of that group is sold.
    Raises DuplicateCodeError if the (non-blank) code already exists.
    """
    code = service_code or None
    with get_connection() as conn:
        try:
            cursor = conn.execute(
                "INSERT INTO services "
                "(service_code, service_name, cost, retail_price, cost_pence, "
                " retail_price_pence, tagged_item_key) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (code, service_name, cost, retail_price,
                 money.to_pence(cost), money.to_pence(retail_price),
                 tagged_item_key or None),
            )
        except sqlite3.IntegrityError as exc:
            raise DuplicateCodeError(service_code) from exc
        return cursor.lastrowid


def update_service(service_id, service_code, service_name, cost, retail_price,
                   tagged_item_key=""):
    """Update an existing service.

    Raises DuplicateCodeError if the new code collides with another service.
    """
    code = service_code or None
    with get_connection() as conn:
        try:
            conn.execute(
                "UPDATE services SET service_code = ?, service_name = ?, cost = ?, "
                "retail_price = ?, cost_pence = ?, retail_price_pence = ?, "
                "tagged_item_key = ? WHERE id = ?",
                (code, service_name, cost, retail_price,
                 money.to_pence(cost), money.to_pence(retail_price),
                 tagged_item_key or None, service_id),
            )
        except sqlite3.IntegrityError as exc:
            raise DuplicateCodeError(service_code) from exc


def get_service(service_id):
    """Return a single service row by id, or None."""
    with get_connection() as conn:
        return conn.execute(
            "SELECT id, service_code, service_name, cost, retail_price, tagged_item_key "
            "FROM services WHERE id = ?",
            (service_id,),
        ).fetchone()


def services_for_group(product_group):
    """Services whose Tagged Item Key matches `product_group` (case-insensitive) —
    i.e. those to auto-add when a product of that group is sold. Blank group
    returns nothing."""
    if not (product_group or "").strip():
        return []
    with get_connection() as conn:
        return conn.execute(
            "SELECT id, service_code, service_name, cost, retail_price "
            "FROM services WHERE tagged_item_key = ? COLLATE NOCASE "
            "ORDER BY service_name COLLATE NOCASE",
            (product_group.strip(),),
        ).fetchall()


def list_services(text="", prefix=False):
    """Return services whose code or name matches `text`, ordered by name.

    With `prefix=True`, match the code/name by prefix (e.g. 'fit' matches
    'Fitting') rather than anywhere in the string — used by the Enquiry screen.
    """
    like = f"{text}%" if prefix else f"%{text}%"
    with get_connection() as conn:
        return conn.execute(
            "SELECT id, service_code, service_name, cost, retail_price FROM services "
            "WHERE service_code LIKE ? COLLATE NOCASE OR service_name LIKE ? COLLATE NOCASE "
            "ORDER BY service_name COLLATE NOCASE",
            (like, like),
        ).fetchall()


def delete_service(service_id):
    """Delete a service by id."""
    with get_connection() as conn:
        conn.execute("DELETE FROM services WHERE id = ?", (service_id,))
