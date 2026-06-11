"""Pure money calculations: the single source of truth for line and document
totals (net / VAT / gross).

This module has no database or UI dependencies, so the identical rule is used by
every form's live totals (ui_sales, ui_purchases, ui_allocation) and can be unit
tested on its own. It is also the natural primitive for a future API/service
layer to call.

The persisted aggregates in sales.py express the same rule as SQL (see
``_LINE_NET`` / ``_LINE_VAT`` / ``_LINE_GROSS`` there); both default a missing VAT
rate to 20% — kept in step via ``DEFAULT_VAT_RATE`` and the SQL ``COALESCE(..,20)``.
"""
from collections import namedtuple

# Default VAT rate (percent) when a line carries none. Mirrors the SQL
# COALESCE(vat_rate, 20) in sales.py and sales.DEFAULT_VAT_RATE.
DEFAULT_VAT_RATE = 20.0

LineAmounts = namedtuple("LineAmounts", ("net", "vat", "gross"))
Totals = namedtuple("Totals", ("net", "vat", "gross"))


def line_amounts(quantity, unit_price, vat_rate=DEFAULT_VAT_RATE):
    """Net, VAT and gross for one line. ``vat_rate`` is a percentage (20 == 20%);
    None falls back to DEFAULT_VAT_RATE. Returns a (net, vat, gross) namedtuple."""
    net = (quantity or 0) * (unit_price or 0.0)
    rate = DEFAULT_VAT_RATE if vat_rate is None else vat_rate
    vat = net * rate / 100.0
    return LineAmounts(net, vat, net + vat)


def document_totals(lines, price_key="unit_price"):
    """Sum net/VAT/gross across line dicts, returning a (net, vat, gross) namedtuple.

    ``price_key`` selects the unit-price field on each line dict: 'unit_price'
    for sales, 'cost_price' for purchases/allocation. Each line is expected to
    have 'quantity', the chosen price key, and (optionally) 'vat_rate'.
    """
    net = vat = gross = 0.0
    for ln in lines:
        amt = line_amounts(ln["quantity"], ln[price_key], ln.get("vat_rate"))
        net += amt.net
        vat += amt.vat
        gross += amt.gross
    return Totals(net, vat, gross)
