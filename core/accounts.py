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

# A comprehensive UK chart of accounts (Sage-50-style nominal ranges) so little
# else needs adding. Topped up on every startup by code (INSERT OR IGNORE), so a
# renamed account is preserved and new codes added here arrive on the next run.
# System accounts (a system_tag) are what the posting service posts to and keep
# stable codes; the bank/cash/creditors codes (1200/1240/2004/2100) match the
# legacy nominal_accounts so payments/receipts map to the ledger by code.
#
# Ranges: 0xxx fixed assets · 1xxx current assets · 2xxx liabilities ·
# 3xxx capital & reserves · 4xxx income · 5xxx cost of sales · 6xxx direct costs ·
# 7xxx-8xxx overheads · 9xxx control/suspense.
# (code, name, account_type, system_tag, is_bank, vat_control)
DEFAULT_ACCOUNTS = [
    # --- Fixed assets (0xxx) ---
    ("0010", "Freehold Property", "asset", None, 0, None),
    ("0011", "Leasehold Property", "asset", None, 0, None),
    ("0020", "Plant and Machinery", "asset", None, 0, None),
    ("0021", "Plant and Machinery Depreciation", "asset", None, 0, None),
    ("0030", "Office Equipment", "asset", None, 0, None),
    ("0031", "Office Equipment Depreciation", "asset", None, 0, None),
    ("0040", "Furniture and Fixtures", "asset", None, 0, None),
    ("0041", "Furniture and Fixtures Depreciation", "asset", None, 0, None),
    ("0050", "Motor Vehicles", "asset", None, 0, None),
    ("0051", "Motor Vehicles Depreciation", "asset", None, 0, None),

    # --- Current assets (1xxx) ---
    ("1001", "Stock / Inventory", "asset", "stock", 0, None),
    ("1002", "Work in Progress", "asset", None, 0, None),
    ("1100", "Debtors Control Account", "asset", "debtors", 0, None),
    ("1101", "Sundry Debtors", "asset", None, 0, None),
    ("1103", "Prepayments", "asset", None, 0, None),
    ("1200", "Cash", "asset", "cash", 1, None),
    ("1230", "Petty Cash", "asset", None, 0, None),
    ("1240", "Card Clearing", "asset", "card_clearing", 1, None),
    ("1250", "Credit Card Receipts", "asset", None, 0, None),
    ("2004", "Bank Account", "asset", "bank", 1, None),

    # --- Current liabilities (2xxx) ---
    ("2100", "Creditors Control Account", "liability", "creditors", 0, None),
    ("2101", "Sundry Creditors", "liability", None, 0, None),
    ("2109", "Accruals", "liability", None, 0, None),
    ("2200", "VAT on Sales (Output Tax)", "liability", "vat_output", 0, "output"),
    ("2201", "VAT on Purchases (Input Tax)", "asset", "vat_input", 0, "input"),
    ("2202", "VAT Liability (due to HMRC)", "liability", None, 0, None),
    ("2210", "PAYE", "liability", None, 0, None),
    ("2211", "National Insurance", "liability", None, 0, None),
    ("2220", "Net Wages", "liability", None, 0, None),
    ("2230", "Pension Fund", "liability", None, 0, None),

    # --- Long-term liabilities (23xx) ---
    ("2300", "Loans", "liability", None, 0, None),
    ("2310", "Hire Purchase", "liability", None, 0, None),
    ("2320", "Corporation Tax", "liability", None, 0, None),
    ("2330", "Mortgages", "liability", None, 0, None),

    # --- Capital & reserves (3xxx) ---
    ("3000", "Capital Introduced / Share Capital", "equity", "capital", 0, None),
    ("3050", "Drawings", "equity", "drawings", 0, None),
    ("3100", "Reserves", "equity", None, 0, None),
    ("3200", "Retained Earnings", "equity", "retained_earnings", 0, None),

    # --- Sales / income (4xxx) ---
    ("4000", "Tyre & Product Sales", "income", "sales", 0, None),
    ("4001", "Part-Worn Tyre Sales", "income", None, 0, None),
    ("4002", "Wheel & Accessory Sales", "income", None, 0, None),
    ("4009", "Discounts Allowed", "income", None, 0, None),
    ("4100", "Fitting & Services Income", "income", "sales_services", 0, None),
    ("4101", "MOT Income", "income", None, 0, None),
    ("4102", "Wheel Alignment & Balancing", "income", None, 0, None),
    ("4103", "Puncture Repairs", "income", None, 0, None),
    ("4200", "Sale of Assets", "income", None, 0, None),
    ("4900", "Miscellaneous Income", "income", None, 0, None),
    ("4904", "Rent Income", "income", None, 0, None),
    ("4906", "Insurance Claims", "income", None, 0, None),

    # --- Cost of sales (5xxx) ---
    ("5000", "Cost of Goods Sold", "expense", "cogs", 0, None),
    ("5001", "Tyres & Stock Purchased", "expense", None, 0, None),
    ("5002", "Carriage Inwards", "expense", None, 0, None),
    ("5003", "Packaging", "expense", None, 0, None),
    ("5009", "Discounts Taken", "expense", None, 0, None),
    ("5100", "Sub-Contractor Costs", "expense", None, 0, None),

    # --- Direct costs (6xxx) ---
    ("6000", "Productive Labour", "expense", None, 0, None),
    ("6100", "Sales Commissions", "expense", None, 0, None),
    ("6200", "Advertising", "expense", None, 0, None),
    ("6201", "Marketing & Promotion", "expense", None, 0, None),

    # --- Overheads: wages (70xx) ---
    ("7000", "Gross Wages", "expense", None, 0, None),
    ("7003", "Staff Salaries", "expense", None, 0, None),
    ("7006", "Employers National Insurance", "expense", None, 0, None),
    ("7007", "Employers Pension Contributions", "expense", None, 0, None),

    # --- Overheads: premises (71xx-72xx) ---
    ("7100", "Rent", "expense", None, 0, None),
    ("7102", "Water Rates", "expense", None, 0, None),
    ("7103", "Business Rates", "expense", None, 0, None),
    ("7104", "Premises Insurance", "expense", None, 0, None),
    ("7200", "Electricity", "expense", None, 0, None),
    ("7201", "Gas", "expense", None, 0, None),
    ("7204", "Heating & Lighting", "expense", None, 0, None),

    # --- Overheads: motor & travel (73xx-74xx) ---
    ("7300", "Fuel & Oil", "expense", None, 0, None),
    ("7301", "Vehicle Repairs & Servicing", "expense", None, 0, None),
    ("7302", "Road Fund Licences", "expense", None, 0, None),
    ("7303", "Vehicle Insurance", "expense", None, 0, None),
    ("7304", "Vehicle Hire", "expense", None, 0, None),
    ("7400", "Travelling", "expense", None, 0, None),
    ("7402", "Hotels & Accommodation", "expense", None, 0, None),
    ("7403", "Entertainment", "expense", None, 0, None),
    ("7406", "Subsistence", "expense", None, 0, None),

    # --- Overheads: office (75xx) ---
    ("7500", "Printing", "expense", None, 0, None),
    ("7501", "Postage & Carriage", "expense", None, 0, None),
    ("7502", "Telephone", "expense", None, 0, None),
    ("7503", "Internet & Broadband", "expense", None, 0, None),
    ("7504", "Office Stationery", "expense", None, 0, None),
    ("7505", "Books & Publications", "expense", None, 0, None),

    # --- Overheads: professional (76xx) ---
    ("7600", "Legal Fees", "expense", None, 0, None),
    ("7601", "Audit & Accountancy Fees", "expense", None, 0, None),
    ("7602", "Consultancy Fees", "expense", None, 0, None),
    ("7603", "Professional Fees", "expense", None, 0, None),

    # --- Overheads: equipment & premises upkeep (77xx-78xx) ---
    ("7700", "Equipment Hire", "expense", None, 0, None),
    ("7701", "Equipment Maintenance", "expense", None, 0, None),
    ("7800", "Repairs & Renewals", "expense", None, 0, None),
    ("7801", "Cleaning", "expense", None, 0, None),
    ("7803", "Premises Expenses", "expense", None, 0, None),

    # --- Overheads: finance (79xx) ---
    ("7900", "Bank Interest Paid", "expense", None, 0, None),
    ("7901", "Bank Charges", "expense", None, 0, None),
    ("7902", "Credit Card Charges", "expense", None, 0, None),
    ("7903", "Loan Interest", "expense", None, 0, None),
    ("7904", "Hire Purchase Interest", "expense", None, 0, None),

    # --- Other overheads (80xx-82xx) ---
    ("8000", "Depreciation", "expense", None, 0, None),
    ("8100", "Bad Debt Write Off", "expense", None, 0, None),
    ("8102", "Bad Debt Provision", "expense", None, 0, None),
    ("8200", "Donations", "expense", None, 0, None),
    ("8201", "Subscriptions", "expense", None, 0, None),
    ("8203", "Training Costs", "expense", None, 0, None),
    ("8204", "Insurance (General)", "expense", None, 0, None),
    ("8205", "Sundry Expenses", "expense", None, 0, None),

    # --- Control / suspense (9xxx) ---
    ("9998", "Suspense Account", "asset", None, 0, None),
    ("9999", "Mispostings Account", "asset", None, 0, None),
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
        # Top up by code: insert any default not already present (INSERT OR IGNORE
        # skips existing codes/tags), so the full chart is ensured without
        # disturbing accounts the user has renamed or added.
        conn.executemany(
            "INSERT OR IGNORE INTO accounts "
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
