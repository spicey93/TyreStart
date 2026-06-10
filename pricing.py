"""Pricing rules data-access layer.

A pricing rule (formula) turns a product's unit cost into a retail price. Each
rule has a name, the variables that make up the formula (a percentage uplift —
either markup or margin — a fixed uplift, and whether to round the result up to
the nearest whole pound) and optional conditions that decide which products the
rule applies to (unit cost greater than X, a pricing key, and/or a product
group). Stored in the central app.db alongside the other entities.

Application order for a matched rule, given a cost C:
    1. percentage:  markup -> C * (1 + pct/100);  margin -> C / (1 - pct/100)
    2. fixed:       + fixed_uplift
    3. round up:    ceil to the next whole number (if enabled)

When several rules match a product the most specific one wins — that is, the
rule with the most conditions set. Ties are broken by the earliest-created rule.
"""

import math

from database import get_connection

# Percentage uplift can be interpreted as a markup on cost or a target margin.
PERCENT_TYPES = ("markup", "margin")


def create_table():
    """Create the pricing_rules table if needed."""
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS pricing_rules (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                name           TEXT NOT NULL,
                uplift_type    TEXT NOT NULL DEFAULT 'markup',
                uplift_percent REAL NOT NULL DEFAULT 0,
                fixed_uplift   REAL NOT NULL DEFAULT 0,
                round_up       INTEGER NOT NULL DEFAULT 0,
                cond_cost_gt   REAL,
                pricing_key    TEXT,
                product_group  TEXT
            )
            """
        )


def create_rule(name, uplift_type="markup", uplift_percent=0.0, fixed_uplift=0.0,
                round_up=False, cond_cost_gt=None, pricing_key="", product_group=""):
    """Insert a pricing rule and return its new id.

    `cond_cost_gt` is None when there's no cost condition; `pricing_key` and
    `product_group` are stored as NULL when blank (meaning "no condition").
    """
    if uplift_type not in PERCENT_TYPES:
        uplift_type = "markup"
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO pricing_rules (name, uplift_type, uplift_percent, "
            "fixed_uplift, round_up, cond_cost_gt, pricing_key, product_group) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (name, uplift_type, uplift_percent, fixed_uplift, 1 if round_up else 0,
             cond_cost_gt, pricing_key or None, product_group or None),
        )
        return cursor.lastrowid


def list_rules():
    """Return all pricing rules, earliest-created first."""
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM pricing_rules ORDER BY id"
        ).fetchall()


def delete_rule(rule_id):
    """Delete a pricing rule by id."""
    with get_connection() as conn:
        conn.execute("DELETE FROM pricing_rules WHERE id = ?", (rule_id,))


def apply_formula(cost, rule):
    """Apply a rule's variables to a unit cost and return the retail price."""
    price = cost or 0.0
    pct = rule["uplift_percent"] or 0.0
    if pct:
        if rule["uplift_type"] == "margin" and pct < 100:
            price = price / (1 - pct / 100.0)
        else:  # markup (and any nonsensical 100%+ margin) treated as markup
            price = price * (1 + pct / 100.0)
    price += rule["fixed_uplift"] or 0.0
    if rule["round_up"]:
        price = math.ceil(price)
    return round(price, 2)


def _matches(rule, cost, pricing_key, product_group):
    if rule["cond_cost_gt"] is not None and not (cost > rule["cond_cost_gt"]):
        return False
    if rule["pricing_key"] and (pricing_key or "").lower() != rule["pricing_key"].lower():
        return False
    if rule["product_group"] and (product_group or "").lower() != rule["product_group"].lower():
        return False
    return True


def _specificity(rule):
    """How many conditions a rule sets — more conditions = more specific."""
    return sum((
        rule["cond_cost_gt"] is not None,
        bool(rule["pricing_key"]),
        bool(rule["product_group"]),
    ))


def best_rule(cost, pricing_key="", product_group="", rules=None):
    """Return the most specific rule matching the given product attributes, or
    None. Pass `rules` (from list_rules()) to avoid re-querying in a loop."""
    if rules is None:
        rules = list_rules()
    matching = [r for r in rules if _matches(r, cost or 0.0, pricing_key, product_group)]
    if not matching:
        return None
    # Most specific first; ties broken by earliest-created (lowest id).
    matching.sort(key=lambda r: (_specificity(r), -r["id"]), reverse=True)
    return matching[0]


def price_from_rules(cost, pricing_key="", product_group="", rules=None):
    """Compute the retail price for a cost/key/group, or None if no rule matches."""
    rule = best_rule(cost, pricing_key, product_group, rules)
    return apply_formula(cost, rule) if rule is not None else None


def price_for_product(product_id, rules=None):
    """Compute the retail price for a product from its average cost and its
    pricing key / product group, or None if no rule matches."""
    import products as product_db

    product = product_db.get_product(product_id)
    if product is None:
        return None
    cost = product_db.average_cost(product_id)
    return price_from_rules(
        cost, product["pricing_key"] or "", product["product_group"] or "", rules
    )
