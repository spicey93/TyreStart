"""General ledger: the append-only journal and its balanced lines.

Every posting is a balanced set of debit/credit lines in whole pence (debits ==
credits, enforced here). Journals are never edited in place: to change a posted
document we post a *reversal* (debits and credits swapped, ``reversal_of`` set)
and then a fresh journal, so history is preserved and auditable.

The posting *rules* (which accounts a sale, purchase, receipt or payment touches)
live in core.posting; this module is the storage + invariant layer it builds on.
"""

import datetime

from core.database import get_connection


class UnbalancedJournalError(Exception):
    """Raised when a journal's debits and credits do not match."""


def _now():
    return datetime.datetime.now().isoformat(timespec="seconds")


def create_table():
    """Create the journal and journal_lines tables (and indexes) if needed."""
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS journal (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                date        TEXT NOT NULL,            -- ISO accounting/effective date
                memo        TEXT,
                source_type TEXT,                     -- sale|purchase|sales_credit|receipt|payment|opening|manual|...
                source_id   INTEGER,
                reversal_of INTEGER REFERENCES journal(id),
                posted_at   TEXT NOT NULL,
                locked      INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS journal_lines (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                journal_id   INTEGER NOT NULL REFERENCES journal(id) ON DELETE CASCADE,
                account_id   INTEGER NOT NULL REFERENCES accounts(id),
                debit_pence  INTEGER NOT NULL DEFAULT 0,
                credit_pence INTEGER NOT NULL DEFAULT 0,
                tax_code     TEXT,                     -- set by posting once tax codes exist
                net_pence    INTEGER,                  -- taxable net this line relates to (VAT analysis)
                CHECK (debit_pence >= 0 AND credit_pence >= 0),
                CHECK (NOT (debit_pence > 0 AND credit_pence > 0))
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_jl_journal ON journal_lines(journal_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_jl_account ON journal_lines(account_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_j_source ON journal(source_type, source_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_j_date ON journal(date)")


def post(conn, date, source_type, source_id, lines, memo=None, reversal_of=None):
    """Insert one balanced journal and its lines on ``conn`` (no commit).

    ``lines`` is a list of dicts with 'account_id' and one of 'debit'/'credit'
    (whole pence), plus optional 'tax_code'/'net_pence'. Zero lines are dropped.
    Returns the new journal id, or None if there was nothing to post. Raises
    UnbalancedJournalError if debits != credits.
    """
    lines = [ln for ln in lines if ln.get("debit") or ln.get("credit")]
    if not lines:
        return None
    total_debit = sum(ln.get("debit", 0) for ln in lines)
    total_credit = sum(ln.get("credit", 0) for ln in lines)
    if total_debit != total_credit:
        raise UnbalancedJournalError(
            f"{source_type}#{source_id}: debits {total_debit} != credits {total_credit}")
    cur = conn.execute(
        "INSERT INTO journal (date, memo, source_type, source_id, reversal_of, posted_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (date, memo, source_type, source_id, reversal_of, _now()),
    )
    journal_id = cur.lastrowid
    conn.executemany(
        "INSERT INTO journal_lines "
        "(journal_id, account_id, debit_pence, credit_pence, tax_code, net_pence) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        [(journal_id, ln["account_id"], ln.get("debit", 0), ln.get("credit", 0),
          ln.get("tax_code"), ln.get("net_pence")) for ln in lines],
    )
    return journal_id


def live_journal_ids(conn, source_type, source_id):
    """Ids of a document's journals that are still in force (not a reversal, and
    not themselves reversed by a later journal)."""
    return [r["id"] for r in conn.execute(
        "SELECT j.id FROM journal j "
        "WHERE j.source_type = ? AND j.source_id = ? AND j.reversal_of IS NULL "
        "AND NOT EXISTS (SELECT 1 FROM journal r WHERE r.reversal_of = j.id)",
        (source_type, source_id),
    )]


def reverse_live(conn, source_type, source_id, redirect_date=None):
    """Post a reversing journal for each live journal of a document.

    Used before re-posting (an edit) or on delete. A reversal swaps debits and
    credits and points at the original via ``reversal_of``. It is dated the same
    as the original, unless the original is in a locked (VAT-filed) period, in
    which case ``redirect_date`` (the open-period date) is used so a filed period
    is never rewritten. Returns the list of reversed journal ids.
    """
    reversed_ids = []
    for jid in live_journal_ids(conn, source_type, source_id):
        orig = conn.execute(
            "SELECT date, locked FROM journal WHERE id = ?", (jid,)).fetchone()
        rdate = orig["date"]
        if orig["locked"] and redirect_date:
            rdate = redirect_date
        lines = conn.execute(
            "SELECT account_id, debit_pence, credit_pence, tax_code, net_pence "
            "FROM journal_lines WHERE journal_id = ?", (jid,)).fetchall()
        swapped = [{
            "account_id": ln["account_id"],
            "debit": ln["credit_pence"],
            "credit": ln["debit_pence"],
            "tax_code": ln["tax_code"],
            "net_pence": (-ln["net_pence"] if ln["net_pence"] is not None else None),
        } for ln in lines]
        post(conn, rdate, source_type, source_id, swapped,
             memo=f"Reversal of journal #{jid}", reversal_of=jid)
        reversed_ids.append(jid)
    return reversed_ids


def get_lines(journal_id):
    """All lines of a journal (for inspection/tests)."""
    with get_connection() as conn:
        return conn.execute(
            "SELECT account_id, debit_pence, credit_pence, tax_code, net_pence "
            "FROM journal_lines WHERE journal_id = ? ORDER BY id", (journal_id,)).fetchall()


def journals_for(source_type, source_id):
    """All journals (live, reversed and reversals) for a document, oldest first."""
    with get_connection() as conn:
        return conn.execute(
            "SELECT id, date, memo, reversal_of, locked FROM journal "
            "WHERE source_type = ? AND source_id = ? ORDER BY id",
            (source_type, source_id)).fetchall()


def account_balance_pence(account_id, end_date=None, conn=None):
    """Net debit balance (debit - credit) of an account in whole pence.

    Positive for a debit-normal account that is 'up'. ``end_date`` (ISO) caps the
    balance at a date inclusive.
    """
    clause, params = "", [account_id]
    if end_date:
        clause = "AND jr.date <= ?"
        params.append(end_date)
    sql = ("SELECT COALESCE(SUM(jl.debit_pence - jl.credit_pence), 0) "
           "FROM journal_lines jl JOIN journal jr ON jr.id = jl.journal_id "
           f"WHERE jl.account_id = ? {clause}")
    if conn is not None:
        return conn.execute(sql, params).fetchone()[0]
    with get_connection() as c:
        return c.execute(sql, params).fetchone()[0]


def trial_balance_totals():
    """Return (total_debits, total_credits) across all lines, in pence (must match)."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(debit_pence), 0) AS d, COALESCE(SUM(credit_pence), 0) AS c "
            "FROM journal_lines").fetchone()
        return row["d"], row["c"]
