"""Payments data-access layer.

A payment is made to a supplier, drawn from a nominal account, with a method
(Cash/Card/BACS) and date. Each payment is allocated to one or more of the
supplier's invoices (payment.amount = sum of its allocations). Stored in app.db.
"""

import datetime

from database import get_connection

METHODS = ("Cash", "Card", "BACS")


def _now():
    return datetime.datetime.now().isoformat(timespec="seconds")


def create_table():
    """Create the payments and payment_allocations tables if needed."""
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS payments (
                id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                supplier_id        INTEGER NOT NULL REFERENCES suppliers(id),
                nominal_account_id INTEGER NOT NULL REFERENCES nominal_accounts(id),
                method             TEXT,
                date               TEXT,
                amount             REAL NOT NULL,
                created_at         TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS payment_allocations (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                payment_id  INTEGER NOT NULL REFERENCES payments(id) ON DELETE CASCADE,
                purchase_id INTEGER NOT NULL REFERENCES purchases(id),
                amount      REAL NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_alloc_payment ON payment_allocations(payment_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_alloc_purchase ON payment_allocations(purchase_id)"
        )


def create_payment(supplier_id, nominal_account_id, method, date, allocations):
    """Record a payment and its invoice allocations. Returns the new payment id.

    `allocations` is a list of {"purchase_id", "amount"}; the payment's total
    amount is the sum of the allocated amounts.
    """
    amount = round(sum(a["amount"] for a in allocations), 2)
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO payments "
            "(supplier_id, nominal_account_id, method, date, amount, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (supplier_id, nominal_account_id, method, date, amount, _now()),
        )
        payment_id = cursor.lastrowid
        conn.executemany(
            "INSERT INTO payment_allocations (payment_id, purchase_id, amount) "
            "VALUES (?, ?, ?)",
            [(payment_id, a["purchase_id"], a["amount"]) for a in allocations],
        )
        return payment_id


def get_payments(supplier_id):
    """Return a supplier's payments, with account label and allocated invoices."""
    with get_connection() as conn:
        return conn.execute(
            "SELECT p.id, p.date, p.method, p.amount, "
            "n.code AS account_code, n.name AS account_name, "
            "(SELECT GROUP_CONCAT(pu.reference, ', ') FROM payment_allocations pa "
            "   JOIN purchases pu ON pu.id = pa.purchase_id "
            "   WHERE pa.payment_id = p.id) AS invoices "
            "FROM payments p JOIN nominal_accounts n ON n.id = p.nominal_account_id "
            "WHERE p.supplier_id = ? ORDER BY p.id DESC",
            (supplier_id,),
        ).fetchall()


def supplier_balance(supplier_id):
    """Supplier balance = sum of invoice totals - sum of payments."""
    with get_connection() as conn:
        invoiced = conn.execute(
            "SELECT COALESCE(SUM(pi.quantity * pi.cost_price * "
            "(1 + COALESCE(pi.vat_rate, 20) / 100.0)), 0) "
            "FROM purchase_items pi JOIN purchases pu ON pu.id = pi.purchase_id "
            "WHERE pu.supplier_id = ? AND pu.status = 'Invoice'",
            (supplier_id,),
        ).fetchone()[0]
        paid = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM payments WHERE supplier_id = ?",
            (supplier_id,),
        ).fetchone()[0]
    return round(invoiced - paid, 2)
