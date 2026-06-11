"""Pure money calculations: the single source of truth for line and document
totals (net / VAT / gross).

Money is computed in **whole pence** internally so VAT is rounded once per line,
half-up, to the penny (HMRC VAT Notice 700 §17.5) and document totals sum exactly
with no floating-point drift. The persisted ``*_pence`` columns hold the same
integers, and the general ledger posts these exact pence — so on-screen totals,
stored aggregates and the ledger all tie to the penny.

This module has no database or UI dependencies, so the identical rule is used by
every form's live totals (ui_sales, ui_purchases, ui_allocation), by the SQL
aggregates (the ``_LINE_*`` fragments in sales.py / purchases.py mirror it), and
by the posting service. The pounds-based ``line_amounts`` / ``document_totals``
keep their original signatures so existing callers are unaffected; the
``*_pence`` variants are the primitives the ledger uses.
"""
from collections import namedtuple
from decimal import Decimal, ROUND_HALF_UP

# Default VAT rate (percent) when a line carries none. Mirrors the SQL
# COALESCE(vat_rate, 20) in sales.py and sales.DEFAULT_VAT_RATE.
DEFAULT_VAT_RATE = 20.0

LineAmounts = namedtuple("LineAmounts", ("net", "vat", "gross"))
Totals = namedtuple("Totals", ("net", "vat", "gross"))


def to_pence(value):
    """Convert a pounds value (float/int/str/Decimal) to whole pence (int), half-up.

    Uses ``Decimal(str(value))`` so a clean 2-dp price like 14.99 converts to
    exactly 1499 with no binary-float artefact.
    """
    if value is None or value == "":
        return 0
    pence = (Decimal(str(value)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return int(pence)


def from_pence(pence):
    """Convert whole pence (int) to a pounds float, exact to the penny (for display)."""
    return (pence or 0) / 100.0


def format_pence(pence):
    """Format whole pence as a thousands-separated pounds string, e.g. '1,234.56'."""
    return f"{from_pence(pence):,.2f}"


def vat_pence(net_pence, vat_rate=DEFAULT_VAT_RATE):
    """VAT on a net pence amount at a percentage rate, rounded half-up to whole pence."""
    rate = DEFAULT_VAT_RATE if vat_rate is None else vat_rate
    vat = (Decimal(int(net_pence)) * Decimal(str(rate)) / 100).quantize(
        Decimal("1"), rounding=ROUND_HALF_UP)
    return int(vat)


def line_amounts_pence(quantity, unit_price_pence, vat_rate=DEFAULT_VAT_RATE):
    """Net/VAT/gross for one line, all in whole pence. VAT rounded per line, half-up."""
    net = int(quantity or 0) * int(unit_price_pence or 0)
    vat = vat_pence(net, vat_rate)
    return LineAmounts(net, vat, net + vat)


def document_totals_pence(lines, price_key="unit_price_pence"):
    """Sum net/VAT/gross across line dicts in whole pence (ints).

    ``price_key`` selects the unit-price field, e.g. 'unit_price_pence' for sales
    or 'cost_price_pence' for purchases. Each line needs 'quantity', the price key
    and (optionally) 'vat_rate'.
    """
    net = vat = gross = 0
    for ln in lines:
        amt = line_amounts_pence(ln["quantity"], ln[price_key], ln.get("vat_rate"))
        net += amt.net
        vat += amt.vat
        gross += amt.gross
    return Totals(net, vat, gross)


def line_amounts(quantity, unit_price, vat_rate=DEFAULT_VAT_RATE):
    """Net, VAT and gross for one line in **pounds** (penny-accurate floats).

    ``unit_price`` is a pounds amount; ``vat_rate`` is a percentage (20 == 20%),
    None falls back to DEFAULT_VAT_RATE. Computed in whole pence (per-line VAT
    rounding) then returned as pounds so it ties to the stored/ledger figures.
    Returns a (net, vat, gross) namedtuple.
    """
    amt = line_amounts_pence(quantity, to_pence(unit_price), vat_rate)
    return LineAmounts(from_pence(amt.net), from_pence(amt.vat), from_pence(amt.gross))


def document_totals(lines, price_key="unit_price"):
    """Sum net/VAT/gross across pounds line dicts, returning a pounds namedtuple.

    ``price_key`` selects the pounds unit-price field: 'unit_price' for sales,
    'cost_price' for purchases/allocation. Each line needs 'quantity', the chosen
    price key and (optionally) 'vat_rate'. Penny-accurate (computed in pence).
    """
    net = vat = gross = 0
    for ln in lines:
        amt = line_amounts_pence(ln["quantity"], to_pence(ln[price_key]), ln.get("vat_rate"))
        net += amt.net
        vat += amt.vat
        gross += amt.gross
    return Totals(from_pence(net), from_pence(vat), from_pence(gross))
