"""Named VAT tax codes.

A small table of HMRC-style codes (standard / reduced / zero / exempt /
outside-scope / reverse-charge) layered on top of the numeric ``vat_rate`` that
still drives the VAT arithmetic. It distinguishes cases the bare rate cannot —
zero-rated (rate 0, in Box 6) vs exempt/outside-scope (rate 0, NOT in Box 6) —
and is the natural mapping point for a future Xero/QuickBooks ``TaxType``
(``external_id``). Seeded for use by the VAT return and later UI selection.
"""

from core.database import get_connection

# (code, name, rate, kind, in_box6, reverse_charge)
DEFAULT_TAX_CODES = [
    ("STD", "Standard 20%", 20.0, "standard", 1, 0),
    ("RED", "Reduced 5%", 5.0, "reduced", 1, 0),
    ("ZERO", "Zero-rated 0%", 0.0, "zero", 1, 0),
    ("EXEMPT", "Exempt", 0.0, "exempt", 0, 0),
    ("OUTSIDE", "Outside the scope", 0.0, "outside", 0, 0),
    ("RC", "Reverse charge", 0.0, "reverse_charge", 1, 1),
]


def create_table():
    """Create the tax_codes table and seed the defaults if empty."""
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tax_codes (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                code           TEXT NOT NULL UNIQUE,
                name           TEXT NOT NULL,
                rate           REAL NOT NULL,
                kind           TEXT NOT NULL,    -- standard|reduced|zero|exempt|outside|reverse_charge
                in_box6        INTEGER NOT NULL DEFAULT 1,
                reverse_charge INTEGER NOT NULL DEFAULT 0,
                external_id    TEXT
            )
            """
        )
        already = conn.execute("SELECT COUNT(*) FROM tax_codes").fetchone()[0]
        if not already:
            conn.executemany(
                "INSERT INTO tax_codes (code, name, rate, kind, in_box6, reverse_charge) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                DEFAULT_TAX_CODES,
            )


def get_all():
    """All tax codes ordered by descending rate (Standard first)."""
    with get_connection() as conn:
        return conn.execute(
            "SELECT id, code, name, rate, kind, in_box6, reverse_charge "
            "FROM tax_codes ORDER BY rate DESC, code"
        ).fetchall()


def get(code):
    """A single tax code row by code, or None."""
    with get_connection() as conn:
        return conn.execute(
            "SELECT id, code, name, rate, kind, in_box6, reverse_charge "
            "FROM tax_codes WHERE code = ?", (code,)).fetchone()


def for_rate(rate):
    """Default tax code for a bare numeric rate (20->STD, 5->RED, 0->ZERO)."""
    return {20.0: "STD", 5.0: "RED", 0.0: "ZERO"}.get(
        float(rate) if rate is not None else 20.0, "STD")
