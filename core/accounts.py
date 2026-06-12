"""Chart of accounts: the real general-ledger account list.

Each account has a type (asset/liability/equity/income/expense), a normal side
(debit for assets & expenses, credit for the rest), and an optional ``system_tag``
that lets the posting service find the account it needs without hard-coding ids or
codes — e.g. ``accounts.system_id("sales")``. The two VAT control accounts carry a
``vat_control`` of 'output'/'input' so the VAT return can read them.

This is the authoritative chart. The legacy 4-row ``nominal_accounts`` table is
kept as the bank/cash dropdown source for the payment/receipt forms; its rows map
to chart accounts by ``code`` (see ``id_for_nominal``) and it will be retired once
the UI selects chart accounts directly.
"""

from core.database import get_connection

ACCOUNT_TYPES = ("asset", "liability", "equity", "income", "expense")
_DEBIT_NORMAL = ("asset", "expense")

# Seeded on first run if the table is empty.
# (code, name, account_type, system_tag, is_bank, vat_control)
DEFAULT_ACCOUNTS = [
    # Income
    ("4000", "Tyre & Product Sales", "income", "sales", 0, None),
    ("4001", "Fitting & Services Income", "income", "sales_services", 0, None),
    # Cost of sales / stock
    ("5000", "Cost of Goods Sold", "expense", "cogs", 0, None),
    ("1001", "Stock / Inventory", "asset", "stock", 0, None),
    # Control accounts
    ("1100", "Debtors Control", "asset", "debtors", 0, None),
    ("2100", "Creditors Control", "liability", "creditors", 0, None),
    # VAT control
    ("2200", "VAT on Sales (Output)", "liability", "vat_output", 0, "output"),
    ("2201", "VAT on Purchases (Input)", "asset", "vat_input", 0, "input"),
    # Bank / cash (selectable as a payment/receipt account)
    ("1200", "Cash", "asset", "cash", 1, None),
    ("1240", "Card Clearing", "asset", "card_clearing", 1, None),
    ("2004", "Bank Account", "asset", "bank", 1, None),
    # Equity
    ("3000", "Capital / Owner's Equity", "equity", "capital", 0, None),
    ("3100", "Drawings", "equity", "drawings", 0, None),
    ("3200", "Retained Earnings", "equity", "retained_earnings", 0, None),
    # Overheads (P&L expenses; no system tag — user-facing nominal codes)
    ("6000", "Rent & Rates", "expense", None, 0, None),
    ("6010", "Utilities", "expense", None, 0, None),
    ("6020", "Motor & Vehicle", "expense", None, 0, None),
    ("6030", "Insurance", "expense", None, 0, None),
    ("6040", "Wages & Salaries", "expense", None, 0, None),
    ("6050", "Telephone & Internet", "expense", None, 0, None),
    ("6060", "Advertising", "expense", None, 0, None),
    ("6070", "Bank Charges", "expense", None, 0, None),
    ("6090", "Sundry Expenses", "expense", None, 0, None),
]


def normal_side(account_type):
    """'debit' for assets & expenses, 'credit' for liabilities/equity/income."""
    return "debit" if account_type in _DEBIT_NORMAL else "credit"


def create_table():
    """Create the accounts table and seed the default chart if empty."""
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS accounts (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                code         TEXT NOT NULL UNIQUE,
                name         TEXT NOT NULL,
                account_type TEXT NOT NULL,
                normal_side  TEXT NOT NULL,
                is_bank      INTEGER NOT NULL DEFAULT 0,
                vat_control  TEXT,               -- NULL | 'output' | 'input'
                system_tag   TEXT UNIQUE,         -- machine key for posting; NULL for user accounts
                active       INTEGER NOT NULL DEFAULT 1,
                external_id  TEXT                 -- integration stub (Xero/QBO id), unused for now
            )
            """
        )
        already = conn.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]
        if not already:
            conn.executemany(
                "INSERT INTO accounts "
                "(code, name, account_type, normal_side, is_bank, vat_control, system_tag) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                [(code, name, atype, normal_side(atype), is_bank, vat_control, tag)
                 for code, name, atype, tag, is_bank, vat_control in DEFAULT_ACCOUNTS],
            )


class DuplicateCodeError(Exception):
    """Raised when an account code collides with an existing one."""


def create_account(code, name, account_type):
    """Add a user account (no system tag). Returns its id.

    Raises ValueError for an unknown type and DuplicateCodeError for a clash.
    """
    if account_type not in ACCOUNT_TYPES:
        raise ValueError(f"Unknown account type {account_type!r}")
    import sqlite3
    with get_connection() as conn:
        try:
            cur = conn.execute(
                "INSERT INTO accounts (code, name, account_type, normal_side, is_bank) "
                "VALUES (?, ?, ?, ?, 0)",
                (code, name, account_type, normal_side(account_type)),
            )
        except sqlite3.IntegrityError as exc:
            raise DuplicateCodeError(code) from exc
        return cur.lastrowid


def update_account(account_id, name):
    """Rename an account (its code/type are fixed once created)."""
    with get_connection() as conn:
        conn.execute("UPDATE accounts SET name = ? WHERE id = ?", (name, account_id))


def get_all(active_only=True):
    """All accounts ordered by code (active only by default)."""
    where = "WHERE active = 1" if active_only else ""
    with get_connection() as conn:
        return conn.execute(
            f"SELECT id, code, name, account_type, normal_side, is_bank, vat_control, "
            f"system_tag, active FROM accounts {where} ORDER BY code"
        ).fetchall()


def by_type(account_type):
    """Active accounts of one type, ordered by code."""
    with get_connection() as conn:
        return conn.execute(
            "SELECT id, code, name, account_type, normal_side FROM accounts "
            "WHERE account_type = ? AND active = 1 ORDER BY code",
            (account_type,),
        ).fetchall()


def get(account_id):
    """A single account row by id, or None."""
    with get_connection() as conn:
        return conn.execute(
            "SELECT id, code, name, account_type, normal_side, is_bank, vat_control, "
            "system_tag, active FROM accounts WHERE id = ?",
            (account_id,),
        ).fetchone()


def get_by_tag(system_tag):
    """A single account row by its system tag, or None."""
    with get_connection() as conn:
        return conn.execute(
            "SELECT id, code, name, account_type, normal_side, vat_control, system_tag "
            "FROM accounts WHERE system_tag = ?",
            (system_tag,),
        ).fetchone()


def system_id(system_tag):
    """Return the account id for a system tag. Raises KeyError if not seeded."""
    row = get_by_tag(system_tag)
    if row is None:
        raise KeyError(f"No system account tagged {system_tag!r}")
    return row["id"]


def id_for_code(code):
    """Return the account id for a code, or None."""
    with get_connection() as conn:
        row = conn.execute("SELECT id FROM accounts WHERE code = ?", (code,)).fetchone()
    return row["id"] if row else None


def id_for_nominal(nominal_account_id):
    """Map a legacy nominal_accounts row to its chart account id (by code), or None."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT a.id FROM nominal_accounts n JOIN accounts a ON a.code = n.code "
            "WHERE n.id = ?",
            (nominal_account_id,),
        ).fetchone()
    return row["id"] if row else None


def label(account):
    """Format an account row as 'code - name' for display."""
    return f"{account['code']} - {account['name']}"
