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
                retail_price_pence INTEGER NOT NULL DEFAULT 0
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
        # Blank codes are stored as NULL so multiple uncoded services don't clash
        # (SQLite treats NULLs as distinct in a unique index).
        conn.execute("UPDATE services SET service_code = NULL WHERE service_code = ''")
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_services_code "
            "ON services(service_code COLLATE NOCASE)"
        )


def create_service(service_code, service_name, cost, retail_price):
    """Insert a service and return its new id.

    Raises DuplicateCodeError if the (non-blank) code already exists.
    """
    code = service_code or None
    with get_connection() as conn:
        try:
            cursor = conn.execute(
                "INSERT INTO services "
                "(service_code, service_name, cost, retail_price, cost_pence, retail_price_pence) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (code, service_name, cost, retail_price,
                 money.to_pence(cost), money.to_pence(retail_price)),
            )
        except sqlite3.IntegrityError as exc:
            raise DuplicateCodeError(service_code) from exc
        return cursor.lastrowid


def update_service(service_id, service_code, service_name, cost, retail_price):
    """Update an existing service.

    Raises DuplicateCodeError if the new code collides with another service.
    """
    code = service_code or None
    with get_connection() as conn:
        try:
            conn.execute(
                "UPDATE services SET service_code = ?, service_name = ?, cost = ?, "
                "retail_price = ?, cost_pence = ?, retail_price_pence = ? WHERE id = ?",
                (code, service_name, cost, retail_price,
                 money.to_pence(cost), money.to_pence(retail_price), service_id),
            )
        except sqlite3.IntegrityError as exc:
            raise DuplicateCodeError(service_code) from exc


def get_service(service_id):
    """Return a single service row by id, or None."""
    with get_connection() as conn:
        return conn.execute(
            "SELECT id, service_code, service_name, cost, retail_price "
            "FROM services WHERE id = ?",
            (service_id,),
        ).fetchone()


def list_services(text=""):
    """Return services whose code or name matches `text`, ordered by name."""
    like = f"%{text}%"
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
