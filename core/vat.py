"""UK VAT return: periods, the 9 boxes, and the file/lock lifecycle.

Boxes 1 and 4 (output/input VAT) are read from the authoritative VAT control
accounts in the general ledger, so they always tie to the posted journals. Boxes
6 and 7 (net sales/purchases) are summed from the source documents by date and
status. Computation is on an **accrual** basis (by invoice/journal date); the
cash scheme is a recognised extension point but not implemented yet.

This module computes and stores the figures only. Submission to HMRC (Making Tax
Digital) is done outside the app — via Xero/QuickBooks or a bridging tool — so a
return here is "computed" then "marked filed", which locks every journal in the
period so a filed period can't be silently rewritten (corrections post to the
open period via the reversal mechanism in core.journal).
"""

import datetime

from core import accounts
from core.database import get_connection

SCHEMES = ("accrual", "cash")
BOXES = tuple(f"box{i}" for i in range(1, 10))


def _now():
    return datetime.datetime.now().isoformat(timespec="seconds")


def create_table():
    """Create the vat_periods and vat_returns tables if needed."""
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS vat_periods (
                id     INTEGER PRIMARY KEY AUTOINCREMENT,
                "start"  TEXT NOT NULL,          -- ISO inclusive
                "end"    TEXT NOT NULL,          -- ISO inclusive ("end" is a PG keyword)
                status TEXT NOT NULL DEFAULT 'open',   -- 'open' | 'filed'
                UNIQUE("start", "end")
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS vat_returns (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                period_id    INTEGER NOT NULL REFERENCES vat_periods(id),
                box1 INTEGER, box2 INTEGER, box3 INTEGER, box4 INTEGER, box5 INTEGER,
                box6 INTEGER, box7 INTEGER, box8 INTEGER, box9 INTEGER,   -- whole pence
                scheme       TEXT NOT NULL DEFAULT 'accrual',
                computed_at  TEXT,
                filed_at     TEXT,
                external_ref TEXT,
                UNIQUE(period_id)
            )
            """
        )


# --- periods ---------------------------------------------------------------

def create_period(start, end):
    """Create a VAT period (ISO start/end inclusive); returns its id."""
    with get_connection() as conn:
        cur = conn.execute(
            'INSERT INTO vat_periods ("start", "end") VALUES (?, ?)', (start, end))
        return cur.lastrowid


def get_periods():
    """All VAT periods, newest first."""
    with get_connection() as conn:
        return conn.execute(
            'SELECT id, "start", "end", status FROM vat_periods ORDER BY "start" DESC, id DESC'
        ).fetchall()


def get_period(period_id):
    """A single VAT period row, or None."""
    with get_connection() as conn:
        return conn.execute(
            'SELECT id, "start", "end", status FROM vat_periods WHERE id = ?', (period_id,)
        ).fetchone()


# --- box computation -------------------------------------------------------

def compute_boxes(start, end, scheme="accrual"):
    """Compute the 9 VAT boxes (whole pence) for an ISO [start, end] period.

    Box 1 = output VAT (from the Output VAT control account in the ledger).
    Box 4 = input VAT (from the Input VAT control account).
    Box 3 = Box 1 + Box 2; Box 5 = Box 3 - Box 4 (positive = payable to HMRC).
    Box 6/7 = net sales/purchases from invoices and credit notes in the period.
    Boxes 2, 8, 9 are 0 (no EU/NI acquisitions modelled).
    """
    if scheme != "accrual":
        raise NotImplementedError(
            "Only the accrual VAT scheme is implemented; cash scheme is a future extension.")

    with get_connection() as conn:
        def vat_account(tag, credit_minus_debit):
            sign = "jl.credit_pence - jl.debit_pence" if credit_minus_debit \
                else "jl.debit_pence - jl.credit_pence"
            return conn.execute(
                f"SELECT COALESCE(SUM({sign}), 0) "
                "FROM journal_lines jl JOIN journal jr ON jr.id = jl.journal_id "
                "WHERE jl.account_id = ? AND jr.date BETWEEN ? AND ?",
                (accounts.system_id(tag), start, end),
            ).fetchone()[0]

        box1 = vat_account("vat_output", credit_minus_debit=True)   # output VAT due
        box4 = vat_account("vat_input", credit_minus_debit=False)   # input VAT reclaimed

        def net_documents(items_table, parent_table, join_col, price_col):
            return conn.execute(
                f"SELECT COALESCE(SUM("
                f"  CASE p.status WHEN 'Invoice' THEN 1 WHEN 'Credit Note' THEN -1 ELSE 0 END "
                f"  * it.quantity * it.{price_col}), 0) "
                f"FROM {items_table} it JOIN {parent_table} p ON p.id = it.{join_col} "
                f"WHERE p.date BETWEEN ? AND ?",
                (start, end),
            ).fetchone()[0]

        box6 = net_documents("sale_items", "sales", "sale_id", "unit_price_pence")
        box7 = net_documents("purchase_items", "purchases", "purchase_id", "cost_price_pence")

    box2 = 0
    box3 = box1 + box2
    box5 = box3 - box4
    box8 = box9 = 0
    return {"box1": box1, "box2": box2, "box3": box3, "box4": box4, "box5": box5,
            "box6": box6, "box7": box7, "box8": box8, "box9": box9}


# --- return lifecycle ------------------------------------------------------

def compute_and_save(period_id, scheme="accrual"):
    """Compute the period's boxes and upsert its (recomputable) vat_returns row.

    Returns the saved boxes dict. Raises if the period is already filed.
    """
    period = get_period(period_id)
    if period is None:
        raise ValueError(f"No VAT period {period_id}")
    if period["status"] == "filed":
        raise ValueError("This VAT period is filed; its return cannot be recomputed.")

    boxes = compute_boxes(period["start"], period["end"], scheme)
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO vat_returns "
            "(period_id, box1, box2, box3, box4, box5, box6, box7, box8, box9, "
            " scheme, computed_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(period_id) DO UPDATE SET "
            "box1=excluded.box1, box2=excluded.box2, box3=excluded.box3, "
            "box4=excluded.box4, box5=excluded.box5, box6=excluded.box6, "
            "box7=excluded.box7, box8=excluded.box8, box9=excluded.box9, "
            "scheme=excluded.scheme, computed_at=excluded.computed_at",
            (period_id, boxes["box1"], boxes["box2"], boxes["box3"], boxes["box4"],
             boxes["box5"], boxes["box6"], boxes["box7"], boxes["box8"], boxes["box9"],
             scheme, _now()),
        )
    return boxes


def get_return(period_id):
    """The saved return row for a period, or None."""
    with get_connection() as conn:
        return conn.execute(
            'SELECT r.*, p."start", p."end", p.status FROM vat_returns r '
            "JOIN vat_periods p ON p.id = r.period_id WHERE r.period_id = ?",
            (period_id,)).fetchone()


def mark_filed(period_id, external_ref=None):
    """Mark a period's return filed and lock every journal dated within it.

    Locked journals are immutable; later corrections post to the open period via
    the reversal mechanism. (Submission to HMRC happens outside the app.)
    """
    period = get_period(period_id)
    if period is None:
        raise ValueError(f"No VAT period {period_id}")
    with get_connection() as conn:
        conn.execute(
            "UPDATE vat_returns SET filed_at = ?, external_ref = ? WHERE period_id = ?",
            (_now(), external_ref, period_id))
        conn.execute("UPDATE vat_periods SET status = 'filed' WHERE id = ?", (period_id,))
        conn.execute(
            "UPDATE journal SET locked = 1 WHERE date BETWEEN ? AND ?",
            (period["start"], period["end"]))
