"""One-shot migration: convert the transaction ``date`` columns from the legacy
``DD/MM/YY`` text to ISO ``YYYY-MM-DD`` so SQL range/sort is chronological.

Run once (guarded by the schema version in core.migrations). Idempotent: ISO
values normalise to themselves, and any value that can't be parsed is left
untouched (and would still read via daterange.parse). ``created_at`` is already
ISO and is not touched.
"""

from core import daterange
from core.database import get_connection

_TABLES = ("sales", "purchases", "payments", "receipts")


def run():
    """Rewrite each table's ``date`` column in ISO form."""
    with get_connection() as conn:
        for table in _TABLES:
            rows = conn.execute(f"SELECT id, date FROM {table}").fetchall()
            conn.executemany(
                f"UPDATE {table} SET date = ? WHERE id = ?",
                [(daterange.to_iso(r["date"]), r["id"]) for r in rows],
            )
