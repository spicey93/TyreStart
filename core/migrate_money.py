"""One-shot migration: back-fill the integer-pence money columns from the legacy
REAL (pounds) columns.

Run once (guarded by the schema version in core.migrations). Idempotent: re-running
recomputes the same pence from the REAL columns. Conversion uses money.to_pence
(Decimal-based) rather than SQL ``ROUND(x*100)`` so the migrated values match
exactly what the create_*/update_* paths now write for the same pounds amount —
including the rare ``.x5`` boundary where a binary float and a decimal disagree.
"""

from core import money
from core.database import get_connection

# (table, source REAL column, destination pence column)
_SINGLE = [
    ("sale_items", "unit_price", "unit_price_pence"),
    ("purchase_items", "cost_price", "cost_price_pence"),
    ("payments", "amount", "amount_pence"),
    ("payment_allocations", "amount", "amount_pence"),
    ("receipts", "amount", "amount_pence"),
    ("receipt_allocations", "amount", "amount_pence"),
]


def run():
    """Populate every ``*_pence`` column from its REAL pounds source."""
    with get_connection() as conn:
        for table, src, dst in _SINGLE:
            rows = conn.execute(f"SELECT id, {src} AS v FROM {table}").fetchall()
            conn.executemany(
                f"UPDATE {table} SET {dst} = ? WHERE id = ?",
                [(money.to_pence(r["v"]), r["id"]) for r in rows],
            )
        # services carries two money columns.
        rows = conn.execute("SELECT id, cost, retail_price FROM services").fetchall()
        conn.executemany(
            "UPDATE services SET cost_pence = ?, retail_price_pence = ? WHERE id = ?",
            [(money.to_pence(r["cost"]), money.to_pence(r["retail_price"]), r["id"])
             for r in rows],
        )
