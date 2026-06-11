"""Purchases data-access layer.

A purchase is either an 'Order' or an 'Invoice', belongs to a supplier, and has
a date, a reference and one or more product lines (quantity + cost price).
Stored in the central app.db alongside the other entities.
"""

import datetime

from core.database import get_connection

STATUSES = ("Order", "Invoice")

# VAT: cost prices are stored NET; the rate (percent) is per line, default 20%.
DEFAULT_VAT_RATE = 20.0
VAT_RATES = (20.0, 5.0, 0.0)

# SQL fragments for line money (use unqualified columns; add a `pi.` prefix in joins).
_LINE_NET = "quantity * cost_price"
_LINE_VAT = "quantity * cost_price * COALESCE(vat_rate, 20) / 100.0"
_LINE_GROSS = "quantity * cost_price * (1 + COALESCE(vat_rate, 20) / 100.0)"
# Gross expression for a subquery where purchase_items is aliased `pi`.
_PI_GROSS = "pi.quantity * pi.cost_price * (1 + COALESCE(pi.vat_rate, 20) / 100.0)"


def _now():
    return datetime.datetime.now().isoformat(timespec="seconds")


def create_table():
    """Create the purchases and purchase_items tables if needed."""
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS purchases (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                supplier_id INTEGER NOT NULL REFERENCES suppliers(id),
                status      TEXT NOT NULL,
                reference   TEXT,
                date        TEXT,
                created_at  TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS purchase_items (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                purchase_id INTEGER NOT NULL REFERENCES purchases(id) ON DELETE CASCADE,
                product_id  INTEGER NOT NULL REFERENCES products(id),
                quantity    INTEGER NOT NULL,
                cost_price  REAL NOT NULL,
                vat_rate    REAL NOT NULL DEFAULT 20
            )
            """
        )
        # Migrate purchase_items created before VAT existed.
        cols = {row["name"] for row in conn.execute("PRAGMA table_info(purchase_items)")}
        if "vat_rate" not in cols:
            conn.execute(
                "ALTER TABLE purchase_items ADD COLUMN vat_rate REAL NOT NULL DEFAULT 20"
            )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_purchase_items_purchase "
            "ON purchase_items(purchase_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_purchase_items_product "
            "ON purchase_items(product_id)"
        )


def _insert_items(conn, purchase_id, items):
    conn.executemany(
        "INSERT INTO purchase_items (purchase_id, product_id, quantity, cost_price, vat_rate) "
        "VALUES (?, ?, ?, ?, ?)",
        [
            (purchase_id, it["product_id"], it["quantity"], it["cost_price"],
             it.get("vat_rate", DEFAULT_VAT_RATE))
            for it in items
        ],
    )


def create_purchase(supplier_id, status, reference, date, items):
    """Insert a purchase with its line items. Returns the new purchase id."""
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO purchases (supplier_id, status, reference, date, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (supplier_id, status, reference, date, _now()),
        )
        purchase_id = cursor.lastrowid
        _insert_items(conn, purchase_id, items)
        return purchase_id


def update_purchase(purchase_id, supplier_id, status, reference, date, items):
    """Update a purchase, replacing all of its line items."""
    with get_connection() as conn:
        conn.execute(
            "UPDATE purchases SET supplier_id = ?, status = ?, reference = ?, date = ? "
            "WHERE id = ?",
            (supplier_id, status, reference, date, purchase_id),
        )
        conn.execute("DELETE FROM purchase_items WHERE purchase_id = ?", (purchase_id,))
        _insert_items(conn, purchase_id, items)


def delete_purchase(purchase_id):
    """Delete a purchase (its line items cascade)."""
    with get_connection() as conn:
        conn.execute("DELETE FROM purchases WHERE id = ?", (purchase_id,))


def get_purchase(purchase_id):
    """Return the purchase row (with supplier name), or None."""
    with get_connection() as conn:
        return conn.execute(
            "SELECT pu.id, pu.supplier_id, pu.status, pu.reference, pu.date, "
            "s.name AS supplier_name "
            "FROM purchases pu JOIN suppliers s ON s.id = pu.supplier_id "
            "WHERE pu.id = ?",
            (purchase_id,),
        ).fetchone()


def get_purchase_items(purchase_id):
    """Return the line items for a purchase, with product description/stock code."""
    with get_connection() as conn:
        return conn.execute(
            "SELECT pi.id, pi.product_id, pi.quantity, pi.cost_price, pi.vat_rate, "
            "pr.description, pr.stock_code "
            "FROM purchase_items pi JOIN products pr ON pr.id = pi.product_id "
            "WHERE pi.purchase_id = ? ORDER BY pi.id",
            (purchase_id,),
        ).fetchall()


def purchase_total(purchase_id):
    """Gross total of a purchase (net + VAT)."""
    with get_connection() as conn:
        return conn.execute(
            f"SELECT COALESCE(SUM({_LINE_GROSS}), 0) FROM purchase_items "
            "WHERE purchase_id = ?",
            (purchase_id,),
        ).fetchone()[0]


def purchase_totals(purchase_id):
    """Return {'net', 'vat', 'gross'} for a purchase."""
    with get_connection() as conn:
        row = conn.execute(
            f"SELECT COALESCE(SUM({_LINE_NET}), 0) AS net, "
            f"COALESCE(SUM({_LINE_VAT}), 0) AS vat, "
            f"COALESCE(SUM({_LINE_GROSS}), 0) AS gross "
            "FROM purchase_items WHERE purchase_id = ?",
            (purchase_id,),
        ).fetchone()
        return {"net": row["net"], "vat": row["vat"], "gross": row["gross"]}


def list_purchases(text="", status=""):
    """List purchases (with supplier name and total) for the list view.

    `text` matches the reference or supplier name; `status` (if given) restricts
    to 'Order' or 'Invoice'.
    """
    like = f"%{text}%"
    with get_connection() as conn:
        return conn.execute(
            "SELECT pu.id, pu.reference, pu.status, pu.date, pu.supplier_id, "
            "s.name AS supplier_name, "
            f"COALESCE((SELECT SUM({_PI_GROSS}) FROM purchase_items pi "
            "          WHERE pi.purchase_id = pu.id), 0) AS total "
            "FROM purchases pu JOIN suppliers s ON s.id = pu.supplier_id "
            "WHERE (pu.reference LIKE ? COLLATE NOCASE OR s.name LIKE ? COLLATE NOCASE) "
            "AND (? = '' OR pu.status = ?) "
            "ORDER BY pu.id DESC",
            (like, like, status, status),
        ).fetchall()


def supplier_invoices(supplier_id, outstanding_only=False):
    """Invoices for a supplier with total, allocated and outstanding amounts.

    Returns a list of dicts so the computed `outstanding` is available directly.
    """
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT pu.id, pu.reference, pu.date, "
            f"COALESCE((SELECT SUM({_PI_GROSS}) FROM purchase_items pi "
            "          WHERE pi.purchase_id = pu.id), 0) AS total, "
            "COALESCE((SELECT SUM(pa.amount) FROM payment_allocations pa "
            "          WHERE pa.purchase_id = pu.id), 0) AS allocated "
            "FROM purchases pu "
            "WHERE pu.supplier_id = ? AND pu.status = 'Invoice' "
            "ORDER BY pu.id",
            (supplier_id,),
        ).fetchall()
    invoices = []
    for r in rows:
        outstanding = round(r["total"] - r["allocated"], 2)
        if outstanding_only and outstanding <= 0:
            continue
        invoices.append(
            {
                "id": r["id"],
                "reference": r["reference"],
                "date": r["date"],
                "total": r["total"],
                "allocated": r["allocated"],
                "outstanding": outstanding,
            }
        )
    return invoices


def supplier_purchases(supplier_id):
    """All purchases for a supplier (any status), newest first, with gross total."""
    with get_connection() as conn:
        return conn.execute(
            "SELECT pu.id, pu.reference, pu.status, pu.date, "
            f"COALESCE((SELECT SUM({_PI_GROSS}) FROM purchase_items pi "
            "          WHERE pi.purchase_id = pu.id), 0) AS total "
            "FROM purchases pu WHERE pu.supplier_id = ? ORDER BY pu.id DESC",
            (supplier_id,),
        ).fetchall()
