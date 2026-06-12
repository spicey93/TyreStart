"""Opening balances: the business's starting position, posted as one balanced
'opening' journal so the books reflect reality from day one.

The user enters what they have (assets) and what they owe (liabilities); the
difference is the owner's **Capital Introduced**, which is posted automatically so
the entry always balances. Re-saving replaces the previous opening entry (a
reversal is posted for the audit trail, then the new figures).

Amounts are 'natural': a positive number is the account's normal-side balance
(e.g. Bank 5000 → a £5,000 asset; Creditors 1500 → a £1,500 liability).
"""
from core import accounts, daterange, journal
from core.database import get_connection

SOURCE = "opening"
SOURCE_ID = 0
CAPITAL_TAG = "capital"
TYPES = ("asset", "liability", "equity")


def editable_accounts():
    """Balance-sheet accounts the user sets opening balances for. Capital is the
    auto-balancing figure, so it is excluded. Ordered by type then code."""
    capital = accounts.system_id(CAPITAL_TAG)
    out = []
    for account_type in TYPES:
        for account in accounts.by_type(account_type):
            if account["id"] != capital:
                out.append(account)
    return out


def get_opening():
    """The current opening entry: ``{'date': iso|None, 'balances': {account_id:
    pence}}`` (balances natural, positive = normal-side)."""
    with get_connection() as conn:
        date = None
        balances = {}
        for jid in journal.live_journal_ids(conn, SOURCE, SOURCE_ID):
            row = conn.execute("SELECT date FROM journal WHERE id = ?", (jid,)).fetchone()
            date = row["date"]
            for ln in conn.execute(
                "SELECT jl.account_id, jl.debit_pence, jl.credit_pence, a.normal_side "
                "FROM journal_lines jl JOIN accounts a ON a.id = jl.account_id "
                "WHERE jl.journal_id = ?", (jid,)
            ):
                natural = (ln["debit_pence"] - ln["credit_pence"]) if ln["normal_side"] == "debit" \
                    else (ln["credit_pence"] - ln["debit_pence"])
                balances[ln["account_id"]] = balances.get(ln["account_id"], 0) + natural
    return {"date": date, "balances": balances}


def set_opening_balances(date, amounts_pence):
    """Post (replacing any prior) the opening journal from natural amounts
    ``{account_id: pence}``. The remainder balances to Capital Introduced.
    Returns the Capital figure (natural pence; positive = capital introduced).
    """
    date = daterange.to_iso(date)
    capital = accounts.system_id(CAPITAL_TAG)
    with get_connection() as conn:
        journal.reverse_live(conn, SOURCE, SOURCE_ID)

        sides = {a["id"]: a["normal_side"] for a in accounts.get_all(active_only=False)}
        net_debit = 0
        lines = []
        for account_id, pence in amounts_pence.items():
            if account_id == capital or not pence:
                continue
            nd = pence if sides.get(account_id) == "debit" else -pence
            net_debit += nd
            if nd > 0:
                lines.append({"account_id": account_id, "debit": nd})
            else:
                lines.append({"account_id": account_id, "credit": -nd})

        # Capital balances the entry: its net-debit is the negative of the rest.
        cap_nd = -net_debit
        if cap_nd > 0:
            lines.append({"account_id": capital, "debit": cap_nd})
        elif cap_nd < 0:
            lines.append({"account_id": capital, "credit": -cap_nd})

        journal.post(conn, date, SOURCE, SOURCE_ID, lines, memo="Opening balances")
    return net_debit
