"""User-managed option lists (lookups).

Some product fields — Brand, Model, Product Type, Vehicle Type — are picked from
a dropdown, but the user can add a new option on the fly (the "+" button next to
each picker). Those user-added options are persisted here so they survive even
before any product uses them.

A single `lookups` table holds every list, keyed by `category`. The dropdowns in
the UI show the union of these values and the distinct values already present in
the products table (see `products.get_distinct_values`).
"""

from core.database import get_connection

# The fields that have an add-able dropdown. Used to validate `category`.
CATEGORIES = ("brand", "model", "product_type", "vehicle_type", "product_group")


class DuplicateValueError(Exception):
    """Raised when adding a value that already exists for that category."""


def create_table():
    """Create the lookups table and its uniqueness index if needed."""
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS lookups (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                value    TEXT NOT NULL
            )
            """
        )
        # One row per (category, value), case-insensitively — so "BMW"/"bmw"
        # don't both get stored.
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_lookups_cat_value "
            "ON lookups(category, value COLLATE NOCASE)"
        )


def get_values(category):
    """Return the user-added values for a category, sorted case-insensitively."""
    _check(category)
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT value FROM lookups WHERE category = ? ORDER BY value COLLATE NOCASE",
            (category,),
        ).fetchall()
        return [row["value"] for row in rows]


def add_value(category, value):
    """Persist a new option for a category. Raises DuplicateValueError if it
    already exists (case-insensitively)."""
    _check(category)
    value = value.strip()
    if not value:
        raise ValueError("value must not be blank")
    import sqlite3
    try:
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO lookups (category, value) VALUES (?, ?)",
                (category, value),
            )
    except sqlite3.IntegrityError:
        raise DuplicateValueError(f"{value!r} already exists for {category}")


def _check(category):
    if category not in CATEGORIES:
        raise ValueError(f"unknown lookup category: {category!r}")
