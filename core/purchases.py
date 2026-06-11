"""Purchases data-access layer.

A purchase is an 'Order', an 'Invoice' or a 'Credit Note', belongs to a supplier,
and has a date, a reference and one or more product lines (quantity + cost price).
Invoices bring stock in and add to the supplier balance; Credit Notes (supplier
returns/corrections) take stock out and reduce the balance; Orders do neither
until received. Stored in the central app.db alongside the other entities.
"""

import datetime

from core.database import get_connection

STATUSES = ("Order", "Invoice", "Credit Note")

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
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                supplier_id  INTEGER NOT NULL REFERENCES suppliers(id),
                status       TEXT NOT NULL,
                reference    TEXT,
                po_reference TEXT,        -- Invoice: source PO no.; Credit Note: invoice no.
                credit_reference TEXT,    -- credit note only: supplier's credit reference
                return_reference TEXT,    -- credit note only: goods-return reference
                date         TEXT,
                reconciled   INTEGER NOT NULL DEFAULT 0,
                received     INTEGER NOT NULL DEFAULT 0,  -- a PO that's been received
                created_at   TEXT
            )
            """
        )
        # Migrate databases created before these columns existed.
        pcols = {row["name"] for row in conn.execute("PRAGMA table_info(purchases)")}
        if "reconciled" not in pcols:
            conn.execute(
                "ALTER TABLE purchases ADD COLUMN reconciled INTEGER NOT NULL DEFAULT 0"
            )
        if "po_reference" not in pcols:
            conn.execute("ALTER TABLE purchases ADD COLUMN po_reference TEXT")
        if "received" not in pcols:
            conn.execute(
                "ALTER TABLE purchases ADD COLUMN received INTEGER NOT NULL DEFAULT 0"
            )
        # Credit-note-only free-text references (the supplier's credit ref / return ref).
        if "credit_reference" not in pcols:
            conn.execute("ALTER TABLE purchases ADD COLUMN credit_reference TEXT")
        if "return_reference" not in pcols:
            conn.execute("ALTER TABLE purchases ADD COLUMN return_reference TEXT")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS purchase_items (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                purchase_id INTEGER NOT NULL REFERENCES purchases(id) ON DELETE CASCADE,
                product_id  INTEGER NOT NULL REFERENCES products(id),
                quantity    INTEGER NOT NULL,
                received    INTEGER NOT NULL DEFAULT 0,  -- qty received against a PO line
                cost_price  REAL NOT NULL,
                vat_rate    REAL NOT NULL DEFAULT 20
            )
            """
        )
        # Migrate purchase_items created before these columns existed.
        cols = {row["name"] for row in conn.execute("PRAGMA table_info(purchase_items)")}
        if "vat_rate" not in cols:
            conn.execute(
                "ALTER TABLE purchase_items ADD COLUMN vat_rate REAL NOT NULL DEFAULT 20"
            )
        if "received" not in cols:
            conn.execute(
                "ALTER TABLE purchase_items ADD COLUMN received INTEGER NOT NULL DEFAULT 0"
            )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_purchase_items_purchase "
            "ON purchase_items(purchase_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_purchase_items_product "
            "ON purchase_items(product_id)"
        )


PO_PREFIX = "PO"
# Statuses whose reference is auto-generated, with their number prefix.
_REF_PREFIX = {"Order": "PO", "Credit Note": "CN"}


def _insert_items(conn, purchase_id, items):
    conn.executemany(
        "INSERT INTO purchase_items "
        "(purchase_id, product_id, quantity, received, cost_price, vat_rate) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        [
            (purchase_id, it["product_id"], it["quantity"], it.get("received", 0),
             it["cost_price"], it.get("vat_rate", DEFAULT_VAT_RATE))
            for it in items
        ],
    )


def next_reference(status, conn=None):
    """Next sequential auto number for a status (PO0001 for Orders, CN0001 for
    Credit Notes), or '' for statuses that use a manual reference."""
    prefix = _REF_PREFIX.get(status)
    if not prefix:
        return ""

    def compute(c):
        highest = 0
        for row in c.execute(
            "SELECT reference AS r FROM purchases WHERE status = ? AND reference LIKE ?",
            (status, prefix + "%"),
        ):
            digits = (row["r"] or "")[len(prefix):]
            if digits.isdigit():
                highest = max(highest, int(digits))
        return f"{prefix}{highest + 1:04d}"

    if conn is not None:
        return compute(conn)
    with get_connection() as conn:
        return compute(conn)


def next_po_number(conn=None):
    """The next sequential purchase-order number, e.g. 'PO0001'."""
    return next_reference("Order", conn)


def create_purchase(supplier_id, status, reference, date, items, reconciled=0,
                    po_reference="", credit_reference="", return_reference=""):
    """Insert a purchase with its line items. Returns the new purchase id.

    Orders and Credit Notes with no reference are given the next auto number
    (PO… / CN…); Invoices keep the manually entered reference. `po_reference` links
    an invoice to its PO number, or a credit note to the invoice number it credits.
    """
    with get_connection() as conn:
        if not reference:
            reference = next_reference(status, conn)
        cursor = conn.execute(
            "INSERT INTO purchases "
            "(supplier_id, status, reference, po_reference, credit_reference, "
            " return_reference, date, reconciled, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (supplier_id, status, reference, po_reference, credit_reference,
             return_reference, date, int(reconciled), _now()),
        )
        purchase_id = cursor.lastrowid
        _insert_items(conn, purchase_id, items)
        return purchase_id


def update_purchase(purchase_id, supplier_id, status, reference, date, items,
                    reconciled=0, po_reference="", credit_reference="",
                    return_reference=""):
    """Update a purchase, replacing all of its line items."""
    with get_connection() as conn:
        conn.execute(
            "UPDATE purchases SET supplier_id = ?, status = ?, reference = ?, "
            "po_reference = ?, credit_reference = ?, return_reference = ?, "
            "date = ?, reconciled = ? WHERE id = ?",
            (supplier_id, status, reference, po_reference, credit_reference,
             return_reference, date, int(reconciled), purchase_id),
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
            "SELECT pu.id, pu.supplier_id, pu.status, pu.reference, pu.po_reference, "
            "pu.credit_reference, pu.return_reference, pu.date, pu.reconciled, "
            "pu.received, s.name AS supplier_name "
            "FROM purchases pu JOIN suppliers s ON s.id = pu.supplier_id "
            "WHERE pu.id = ?",
            (purchase_id,),
        ).fetchone()


def get_purchase_items(purchase_id):
    """Return the line items for a purchase, with product description/stock code."""
    with get_connection() as conn:
        return conn.execute(
            "SELECT pi.id, pi.product_id, pi.quantity, pi.received, pi.cost_price, "
            "pi.vat_rate, pr.description, pr.stock_code "
            "FROM purchase_items pi JOIN products pr ON pr.id = pi.product_id "
            "WHERE pi.purchase_id = ? ORDER BY pi.id",
            (purchase_id,),
        ).fetchall()


def receive_purchase(po_id, received_by_item, date):
    """Record a delivery against a purchase order and raise the linked invoice.

    `received_by_item` maps a purchase_items.id to the quantity received. The PO's
    line `received` figures and its `received` flag are updated, then an Invoice is
    created (linked via `po_reference` = the PO's number) containing the received
    quantities at the PO's costs. Returns the new invoice's id, or None if nothing
    was received.
    """
    with get_connection() as conn:
        for item_id, qty in received_by_item.items():
            conn.execute(
                "UPDATE purchase_items SET received = ? WHERE id = ? AND purchase_id = ?",
                (int(qty), item_id, po_id),
            )
        conn.execute("UPDATE purchases SET received = 1 WHERE id = ?", (po_id,))
        po = conn.execute(
            "SELECT supplier_id, reference FROM purchases WHERE id = ?", (po_id,)
        ).fetchone()

    items = [
        {"product_id": it["product_id"], "quantity": it["received"],
         "cost_price": it["cost_price"], "vat_rate": it["vat_rate"]}
        for it in get_purchase_items(po_id) if it["received"] > 0
    ]
    if not items:
        return None
    # Invoice number (reference) is entered later by the user; link via po_reference.
    return create_purchase(po["supplier_id"], "Invoice", "", date, items,
                           po_reference=po["reference"])


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
    """All purchases for a supplier (any status), newest first, with gross total,
    amount allocated against it, and its reconciled flag (for list filters)."""
    with get_connection() as conn:
        return conn.execute(
            "SELECT pu.id, pu.reference, pu.status, pu.date, pu.reconciled, "
            f"COALESCE((SELECT SUM({_PI_GROSS}) FROM purchase_items pi "
            "          WHERE pi.purchase_id = pu.id), 0) AS total, "
            "COALESCE((SELECT SUM(pa.amount) FROM payment_allocations pa "
            "          WHERE pa.purchase_id = pu.id), 0) AS allocated "
            "FROM purchases pu WHERE pu.supplier_id = ? ORDER BY pu.id DESC",
            (supplier_id,),
        ).fetchall()


def set_reconciled(purchase_id, reconciled):
    """Mark a purchase reconciled (or not)."""
    with get_connection() as conn:
        conn.execute(
            "UPDATE purchases SET reconciled = ? WHERE id = ?",
            (int(reconciled), purchase_id),
        )
