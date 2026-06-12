"""Posting service: derive a balanced general-ledger journal from a source
document (sale, purchase, receipt, payment) and write it in the document's own
save transaction, so the document and its ledger entry commit atomically.

Each ``post_*`` first reverses any journal the document already had (so an edit
re-posts cleanly and a delete just reverses), then posts the journal for the
document's current state. Posting on save keeps the ledger always in step with
the subledgers; nothing needs a separate "post" step.

Tax points (when a journal is raised):
- Sales post on status 'Invoice' (the VAT tax point); Quotes/Orders do not post.
- Purchases post on 'Invoice' and 'Credit Note'.
- Receipts and payments post when recorded.

All amounts are whole pence and tie to core.money / the *_pence columns.
"""

from core import accounts, daterange, journal, money


def _redirect_for(conn, source_type, source_id):
    """Date to use when a document's existing journals are locked (filed): today,
    so the reversal and re-post land in the open period instead of rewriting a
    filed one. Returns None when nothing is locked (use the document's own date).
    """
    if journal.has_locked_live(conn, source_type, source_id):
        return daterange.iso_today()
    return None


def _avg_cost_pence(conn, product_id):
    """Quantity-weighted average cost (whole pence) from invoiced purchases."""
    row = conn.execute(
        "SELECT COALESCE(SUM(pi.quantity), 0) AS qty, "
        "COALESCE(SUM(pi.quantity * pi.cost_price_pence), 0) AS spend "
        "FROM purchase_items pi JOIN purchases pu ON pu.id = pi.purchase_id "
        "WHERE pi.product_id = ? AND pu.status = 'Invoice'",
        (product_id,),
    ).fetchone()
    return round(row["spend"] / row["qty"]) if row["qty"] else 0


def remove(conn, source_type, source_id):
    """Reverse all of a document's live journals (used on delete).

    Refuses if the document is in a filed (locked) VAT period — a credit note
    should be raised instead of deleting history.
    """
    if journal.has_locked_live(conn, source_type, source_id):
        raise journal.LockedPeriodError(
            "This document is in a filed VAT period and cannot be deleted; "
            "raise a credit note instead.")
    journal.reverse_live(conn, source_type, source_id)


def post_sale(conn, sale_id):
    """(Re)post the journal for a sale. Posts on 'Invoice' and 'Credit Note'.

    Invoice: DR Debtors (gross); CR Sales / Services Income (net by line type);
    CR Output VAT (vat); plus per product line DR COGS / CR Stock at average cost.
    Credit Note (customer return/adjustment) is the mirror image: it reduces
    debtors, sales and output VAT, and returns the goods to stock.
    """
    redirect = _redirect_for(conn, "sale", sale_id)
    journal.reverse_live(conn, "sale", sale_id, redirect_date=redirect)
    sale = conn.execute(
        "SELECT status, date FROM sales WHERE id = ?", (sale_id,)).fetchone()
    if not sale or sale["status"] not in ("Invoice", "Credit Note"):
        return

    product_net = service_net = vat_total = cogs_total = 0
    for ln in conn.execute(
        "SELECT item_type, product_id, quantity, unit_price_pence, vat_rate "
        "FROM sale_items WHERE sale_id = ?", (sale_id,)
    ):
        amt = money.line_amounts_pence(ln["quantity"], ln["unit_price_pence"], ln["vat_rate"])
        vat_total += amt.vat
        if ln["item_type"] == "service":
            service_net += amt.net
        else:
            product_net += amt.net
            if ln["product_id"]:
                cogs_total += ln["quantity"] * _avg_cost_pence(conn, ln["product_id"])

    gross = product_net + service_net + vat_total
    debtors = accounts.system_id("debtors")
    sales_acc = accounts.system_id("sales")
    services_acc = accounts.system_id("sales_services")
    vat_out = accounts.system_id("vat_output")
    cogs = accounts.system_id("cogs")
    stock = accounts.system_id("stock")

    if sale["status"] == "Invoice":
        lines = [
            {"account_id": debtors, "debit": gross},
            {"account_id": sales_acc, "credit": product_net},
            {"account_id": services_acc, "credit": service_net},
            {"account_id": vat_out, "credit": vat_total},
            {"account_id": cogs, "debit": cogs_total},
            {"account_id": stock, "credit": cogs_total},
        ]
        memo = "Sales invoice"
    else:  # Credit Note — mirror image; goods back into stock.
        lines = [
            {"account_id": sales_acc, "debit": product_net},
            {"account_id": services_acc, "debit": service_net},
            {"account_id": vat_out, "debit": vat_total},
            {"account_id": debtors, "credit": gross},
            {"account_id": stock, "debit": cogs_total},
            {"account_id": cogs, "credit": cogs_total},
        ]
        memo = "Sales credit note"
    journal.post(conn, redirect or sale["date"], "sale", sale_id, lines, memo=memo)


def post_purchase(conn, purchase_id):
    """(Re)post the journal for a purchase. Posts on 'Invoice' and 'Credit Note'.

    Invoice: DR Stock (net), DR Input VAT (vat), CR Creditors (gross).
    Credit Note: the reverse (DR Creditors, CR Stock, CR Input VAT).
    """
    redirect = _redirect_for(conn, "purchase", purchase_id)
    journal.reverse_live(conn, "purchase", purchase_id, redirect_date=redirect)
    pu = conn.execute(
        "SELECT status, date FROM purchases WHERE id = ?", (purchase_id,)).fetchone()
    if not pu or pu["status"] not in ("Invoice", "Credit Note"):
        return

    net = vat = 0
    for ln in conn.execute(
        "SELECT quantity, cost_price_pence, vat_rate FROM purchase_items WHERE purchase_id = ?",
        (purchase_id,)
    ):
        amt = money.line_amounts_pence(ln["quantity"], ln["cost_price_pence"], ln["vat_rate"])
        net += amt.net
        vat += amt.vat
    gross = net + vat

    stock = accounts.system_id("stock")
    vat_input = accounts.system_id("vat_input")
    creditors = accounts.system_id("creditors")
    if pu["status"] == "Invoice":
        lines = [
            {"account_id": stock, "debit": net},
            {"account_id": vat_input, "debit": vat},
            {"account_id": creditors, "credit": gross},
        ]
        memo = "Purchase invoice"
    else:  # Credit Note
        lines = [
            {"account_id": creditors, "debit": gross},
            {"account_id": stock, "credit": net},
            {"account_id": vat_input, "credit": vat},
        ]
        memo = "Purchase credit note"
    journal.post(conn, redirect or pu["date"], "purchase", purchase_id, lines, memo=memo)


def post_receipt(conn, receipt_id):
    """(Re)post the journal for a customer receipt: DR Bank/Cash, CR Debtors."""
    redirect = _redirect_for(conn, "receipt", receipt_id)
    journal.reverse_live(conn, "receipt", receipt_id, redirect_date=redirect)
    r = conn.execute(
        "SELECT amount_pence, date, nominal_account_id FROM receipts WHERE id = ?",
        (receipt_id,)).fetchone()
    if not r or not r["amount_pence"]:
        return
    bank = accounts.id_for_nominal(r["nominal_account_id"])
    lines = [
        {"account_id": bank, "debit": r["amount_pence"]},
        {"account_id": accounts.system_id("debtors"), "credit": r["amount_pence"]},
    ]
    journal.post(conn, redirect or r["date"], "receipt", receipt_id, lines, memo="Customer receipt")


def post_payment(conn, payment_id):
    """(Re)post the journal for a supplier payment: DR Creditors, CR Bank/Cash."""
    redirect = _redirect_for(conn, "payment", payment_id)
    journal.reverse_live(conn, "payment", payment_id, redirect_date=redirect)
    p = conn.execute(
        "SELECT amount_pence, date, nominal_account_id FROM payments WHERE id = ?",
        (payment_id,)).fetchone()
    if not p or not p["amount_pence"]:
        return
    bank = accounts.id_for_nominal(p["nominal_account_id"])
    lines = [
        {"account_id": accounts.system_id("creditors"), "debit": p["amount_pence"]},
        {"account_id": bank, "credit": p["amount_pence"]},
    ]
    journal.post(conn, redirect or p["date"], "payment", payment_id, lines, memo="Supplier payment")
