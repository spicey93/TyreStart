"""Payments data-access layer.

A payment is made to a supplier, drawn from a nominal account, with a method
(Cash/Card/BACS) and date. Each payment is allocated to one or more of the
supplier's invoices (payment.amount = sum of its allocations). Stored in app.db.
"""

import datetime

from core import daterange, money
from core.database import get_connection

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
                amount             REAL NOT NULL,            -- pounds (display mirror)
                amount_pence       INTEGER NOT NULL DEFAULT 0,
                created_at         TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS payment_allocations (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                payment_id   INTEGER NOT NULL REFERENCES payments(id) ON DELETE CASCADE,
                purchase_id  INTEGER NOT NULL REFERENCES purchases(id),
                amount       REAL NOT NULL,
                amount_pence INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        # Migrate rows created before the pence columns existed (back-filled by
        # core.migrate_money from the REAL amount).
        pcols = {row["name"] for row in conn.execute("PRAGMA table_info(payments)")}
        if "amount_pence" not in pcols:
            conn.execute("ALTER TABLE payments ADD COLUMN amount_pence INTEGER NOT NULL DEFAULT 0")
        acols = {row["name"] for row in conn.execute("PRAGMA table_info(payment_allocations)")}
        if "amount_pence" not in acols:
            conn.execute(
                "ALTER TABLE payment_allocations ADD COLUMN amount_pence INTEGER NOT NULL DEFAULT 0"
            )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_alloc_payment ON payment_allocations(payment_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_alloc_purchase ON payment_allocations(purchase_id)"
        )


def create_payment(supplier_id, nominal_account_id, method, date, amount, allocations=None):
    """Record a payment for `amount`. Returns the new payment id.

    The payment amount is entered manually and is independent of any
    allocations: a payment may be created with no allocations and allocated to
    invoices later (see `add_allocations`). `allocations`, when given, is a list
    of {"purchase_id", "amount"} applied immediately.
    """
    amount_pence = money.to_pence(amount)
    amount = money.from_pence(amount_pence)
    date = daterange.to_iso(date)
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO payments "
            "(supplier_id, nominal_account_id, method, date, amount, amount_pence, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (supplier_id, nominal_account_id, method, date, amount, amount_pence, _now()),
        )
        payment_id = cursor.lastrowid
        if allocations:
            conn.executemany(
                "INSERT INTO payment_allocations (payment_id, purchase_id, amount, amount_pence) "
                "VALUES (?, ?, ?, ?)",
                [(payment_id, a["purchase_id"], money.from_pence(money.to_pence(a["amount"])),
                  money.to_pence(a["amount"])) for a in allocations],
            )
        return payment_id


def add_allocations(payment_id, allocations):
    """Allocate part (or all) of an existing payment to invoices.

    `allocations` is a list of {"purchase_id", "amount"}; each call appends new
    allocation rows, so a payment can be allocated over several visits.
    """
    if not allocations:
        return
    with get_connection() as conn:
        conn.executemany(
            "INSERT INTO payment_allocations (payment_id, purchase_id, amount, amount_pence) "
            "VALUES (?, ?, ?, ?)",
            [(payment_id, a["purchase_id"], money.from_pence(money.to_pence(a["amount"])),
              money.to_pence(a["amount"])) for a in allocations],
        )


def delete_payment(payment_id):
    """Delete a payment and (via ON DELETE CASCADE) its allocations."""
    with get_connection() as conn:
        conn.execute("DELETE FROM payments WHERE id = ?", (payment_id,))


def get_payment(payment_id):
    """A single payment with its account label and the amount allocated so far."""
    with get_connection() as conn:
        return conn.execute(
            "SELECT p.id, p.supplier_id, p.nominal_account_id, p.date, p.method, "
            "p.amount, n.code AS account_code, n.name AS account_name, "
            "COALESCE((SELECT SUM(pa.amount) FROM payment_allocations pa "
            "          WHERE pa.payment_id = p.id), 0) AS allocated "
            "FROM payments p JOIN nominal_accounts n ON n.id = p.nominal_account_id "
            "WHERE p.id = ?",
            (payment_id,),
        ).fetchone()


def get_payments(supplier_id):
    """Return a supplier's payments, with account label, allocated invoices, and
    the amount still unallocated."""
    with get_connection() as conn:
        return conn.execute(
            "SELECT p.id, p.date, p.method, p.amount, "
            "n.code AS account_code, n.name AS account_name, "
            "(SELECT GROUP_CONCAT(pu.reference, ', ') FROM payment_allocations pa "
            "   JOIN purchases pu ON pu.id = pa.purchase_id "
            "   WHERE pa.payment_id = p.id) AS invoices, "
            "p.amount - COALESCE((SELECT SUM(pa.amount) FROM payment_allocations pa "
            "   WHERE pa.payment_id = p.id), 0) AS unallocated "
            "FROM payments p JOIN nominal_accounts n ON n.id = p.nominal_account_id "
            "WHERE p.supplier_id = ? ORDER BY p.id DESC",
            (supplier_id,),
        ).fetchall()


def supplier_balance(supplier_id):
    """Supplier balance (pounds) = invoices - credit notes - payments (all gross)."""
    with get_connection() as conn:
        # Invoices add to the balance; Credit Notes reduce it (signed per status).
        # Line gross is computed in whole pence (VAT rounded per line, half-up).
        net_invoiced = conn.execute(
            "SELECT COALESCE(SUM(CASE pu.status WHEN 'Invoice' THEN 1 "
            "WHEN 'Credit Note' THEN -1 ELSE 0 END * (pi.quantity * pi.cost_price_pence + "
            "CAST(ROUND(pi.quantity * pi.cost_price_pence * "
            "COALESCE(pi.vat_rate, 20) / 100.0, 0) AS INTEGER))), 0) "
            "FROM purchase_items pi JOIN purchases pu ON pu.id = pi.purchase_id "
            "WHERE pu.supplier_id = ?",
            (supplier_id,),
        ).fetchone()[0]
        paid = conn.execute(
            "SELECT COALESCE(SUM(amount_pence), 0) FROM payments WHERE supplier_id = ?",
            (supplier_id,),
        ).fetchone()[0]
    return money.from_pence(net_invoiced - paid)
