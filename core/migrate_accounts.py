"""One-shot migration: bring the chart of accounts up to the current comprehensive
default set.

Early databases seeded a small 23-account chart; this expands it to the full UK
chart. If the general ledger is still empty (nothing references any account) the
chart is rebuilt from scratch. If the ledger is already in use, the system
accounts (those the posting service uses) are corrected in place — keeping their
ids so posted journals stay valid — and the new accounts are added, leaving any
user extras untouched.
"""

from core import accounts
from core.database import get_connection


def run():
    with get_connection() as conn:
        in_use = conn.execute("SELECT COUNT(*) FROM journal_lines").fetchone()[0] > 0
        if not in_use:
            # Nothing is posted yet — safe to rebuild from the current defaults.
            conn.execute("DELETE FROM accounts")
        else:
            # Correct the posting accounts' codes/names without changing their ids.
            for code, name, _atype, tag, _is_bank, _vc in accounts.DEFAULT_ACCOUNTS:
                if tag:
                    conn.execute(
                        "UPDATE accounts SET code = ?, name = ? WHERE system_tag = ?",
                        (code, name, tag))
    # Ensure every default account exists (INSERT OR IGNORE top-up).
    accounts.create_table()
