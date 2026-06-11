"""Nominal accounts data-access layer.

A small chart of accounts used when recording payments (the account the money
is withdrawn from, e.g. "2004 - Bank Account"). Stored in the central app.db.
"""

from core.database import get_connection

# Seeded on first run if the table is empty. (code, name)
DEFAULT_ACCOUNTS = [
    ("1200", "Cash"),
    ("1240", "Card Clearing"),
    ("2004", "Bank Account"),
    ("2100", "Creditors Control"),
]


def create_table():
    """Create the nominal_accounts table and seed defaults if empty."""
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS nominal_accounts (
                id   INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL,
                name TEXT NOT NULL
            )
            """
        )
        already = conn.execute("SELECT COUNT(*) FROM nominal_accounts").fetchone()[0]
        if not already:
            conn.executemany(
                "INSERT INTO nominal_accounts (code, name) VALUES (?, ?)",
                DEFAULT_ACCOUNTS,
            )


def get_all():
    """Return all nominal accounts ordered by code."""
    with get_connection() as conn:
        return conn.execute(
            "SELECT id, code, name FROM nominal_accounts ORDER BY code"
        ).fetchall()


def label(account):
    """Format a nominal-account row as 'code - name' for display."""
    return f"{account['code']} - {account['name']}"
