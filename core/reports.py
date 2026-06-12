"""Financial statements computed from the general ledger (journal_lines).

Pure SQL over the posted journals and the chart of accounts, all in whole pence:
- trial_balance(as_at): every account's debit/credit balance; debits == credits.
- profit_and_loss(start, end): income less expenses over a period -> net profit.
- balance_sheet(as_at): assets, liabilities and equity, where equity includes
  retained profit (cumulative income - expenses to date) so it balances.

Balances are always derived, never stored (consistent with the rest of the app).
"""

from core.database import get_connection

# Net debit (debit - credit) per account of a type, optionally within [start, end].
# The CASE lets a NULL bound mean "open" and keeps accounts with no postings.
_TYPE_ROWS = (
    "SELECT a.id, a.code, a.name, "
    "COALESCE(SUM(CASE WHEN (? IS NULL OR jr.date >= ?) AND (? IS NULL OR jr.date <= ?) "
    "  THEN jl.debit_pence - jl.credit_pence ELSE 0 END), 0) AS dc "
    "FROM accounts a "
    "LEFT JOIN journal_lines jl ON jl.account_id = a.id "
    "LEFT JOIN journal jr ON jr.id = jl.journal_id "
    "WHERE a.account_type = ? "
    "GROUP BY a.id ORDER BY a.code"
)


def _type_rows(conn, account_type, start=None, end=None):
    return conn.execute(_TYPE_ROWS, (start, start, end, end, account_type)).fetchall()


def trial_balance(as_at=None):
    """Every account's balance as at ``as_at`` (ISO), split into debit/credit
    columns. Returns {'rows': [...], 'total_debit', 'total_credit'} in pence.
    Total debit must equal total credit.
    """
    rows, total_debit, total_credit = [], 0, 0
    with get_connection() as conn:
        for atype in ("asset", "liability", "equity", "income", "expense"):
            for r in _type_rows(conn, atype, None, as_at):
                dc = r["dc"]
                if dc == 0:
                    continue
                debit = dc if dc > 0 else 0
                credit = -dc if dc < 0 else 0
                total_debit += debit
                total_credit += credit
                rows.append({"code": r["code"], "name": r["name"],
                             "type": atype, "debit": debit, "credit": credit})
    return {"rows": rows, "total_debit": total_debit, "total_credit": total_credit}


def profit_and_loss(start=None, end=None):
    """Income and expenses over [start, end] (ISO) and the net profit, in pence."""
    with get_connection() as conn:
        income = [{"code": r["code"], "name": r["name"], "amount": -r["dc"]}
                  for r in _type_rows(conn, "income", start, end) if r["dc"]]
        expenses = [{"code": r["code"], "name": r["name"], "amount": r["dc"]}
                    for r in _type_rows(conn, "expense", start, end) if r["dc"]]
    total_income = sum(r["amount"] for r in income)
    total_expense = sum(r["amount"] for r in expenses)
    return {"income": income, "expenses": expenses,
            "total_income": total_income, "total_expense": total_expense,
            "net_profit": total_income - total_expense}


def _retained_profit(conn, as_at=None):
    """Cumulative income - expenses up to ``as_at`` (pence)."""
    income = sum(-r["dc"] for r in _type_rows(conn, "income", None, as_at))
    expense = sum(r["dc"] for r in _type_rows(conn, "expense", None, as_at))
    return income - expense


def balance_sheet(as_at=None):
    """Assets, liabilities and equity as at ``as_at`` (ISO), in pence.

    Equity includes retained profit (cumulative P&L to date) so that
    total assets == total liabilities + total equity.
    """
    with get_connection() as conn:
        assets = [{"code": r["code"], "name": r["name"], "amount": r["dc"]}
                  for r in _type_rows(conn, "asset", None, as_at) if r["dc"]]
        liabilities = [{"code": r["code"], "name": r["name"], "amount": -r["dc"]}
                       for r in _type_rows(conn, "liability", None, as_at) if r["dc"]]
        equity = [{"code": r["code"], "name": r["name"], "amount": -r["dc"]}
                  for r in _type_rows(conn, "equity", None, as_at) if r["dc"]]
        retained = _retained_profit(conn, as_at)

    total_assets = sum(r["amount"] for r in assets)
    total_liabilities = sum(r["amount"] for r in liabilities)
    equity_named = sum(r["amount"] for r in equity)
    total_equity = equity_named + retained
    return {
        "assets": assets,
        "liabilities": liabilities,
        "equity": equity,
        "retained_profit": retained,
        "total_assets": total_assets,
        "total_liabilities": total_liabilities,
        "total_equity": total_equity,
        "total_liabilities_equity": total_liabilities + total_equity,
    }
