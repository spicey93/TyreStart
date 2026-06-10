"""Receipts data-access layer (money received from customers).

The sales-side mirror of payments.py. A receipt is received from a customer,
deposited into a nominal account, with a method (Cash/Card/BACS) and date, and
is allocated to one or more of the customer's sales. Stored in app.db.
"""

import datetime

from database import get_connection

METHODS = ("Cash", "Card", "BACS")


def _now():
    return datetime.datetime.now().isoformat(timespec="seconds")


def create_table():
    """Create the receipts and receipt_allocations tables if needed."""
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS receipts (
                id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id        INTEGER NOT NULL REFERENCES customers(id),
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
            CREATE TABLE IF NOT EXISTS receipt_allocations (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                receipt_id INTEGER NOT NULL REFERENCES receipts(id) ON DELETE CASCADE,
                sale_id    INTEGER NOT NULL REFERENCES sales(id),
                amount     REAL NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_recalloc_receipt ON receipt_allocations(receipt_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_recalloc_sale ON receipt_allocations(sale_id)"
        )


def create_receipt(customer_id, nominal_account_id, method, date, allocations):
    """Record a receipt and its sale allocations. Returns the new receipt id.

    `allocations` is a list of {"sale_id", "amount"}; the receipt's total amount
    is the sum of the allocated amounts.
    """
    amount = round(sum(a["amount"] for a in allocations), 2)
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO receipts "
            "(customer_id, nominal_account_id, method, date, amount, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (customer_id, nominal_account_id, method, date, amount, _now()),
        )
        receipt_id = cursor.lastrowid
        conn.executemany(
            "INSERT INTO receipt_allocations (receipt_id, sale_id, amount) "
            "VALUES (?, ?, ?)",
            [(receipt_id, a["sale_id"], a["amount"]) for a in allocations],
        )
        return receipt_id


def get_receipts(customer_id):
    """Return a customer's receipts, with account label and allocated sales."""
    with get_connection() as conn:
        return conn.execute(
            "SELECT r.id, r.date, r.method, r.amount, "
            "n.code AS account_code, n.name AS account_name, "
            "(SELECT GROUP_CONCAT(sa.reference, ', ') FROM receipt_allocations ra "
            "   JOIN sales sa ON sa.id = ra.sale_id "
            "   WHERE ra.receipt_id = r.id) AS sales "
            "FROM receipts r JOIN nominal_accounts n ON n.id = r.nominal_account_id "
            "WHERE r.customer_id = ? ORDER BY r.id DESC",
            (customer_id,),
        ).fetchall()


def customer_balance(customer_id):
    """Customer balance = sum of owed (Order/Invoice) totals (gross) - receipts."""
    with get_connection() as conn:
        sold = conn.execute(
            "SELECT COALESCE(SUM(si.quantity * si.unit_price * "
            "(1 + COALESCE(si.vat_rate, 20) / 100.0)), 0) "
            "FROM sale_items si JOIN sales sa ON sa.id = si.sale_id "
            "WHERE sa.customer_id = ? AND sa.status IN ('Order', 'Invoice')",
            (customer_id,),
        ).fetchone()[0]
        received = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM receipts WHERE customer_id = ?",
            (customer_id,),
        ).fetchone()[0]
    return round(sold - received, 2)
