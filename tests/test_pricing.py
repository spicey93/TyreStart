"""Tests for the pricing-rule logic (the path that computes retail prices)."""
import unittest

from core import pricing
from tests.support import DatabaseTestCase


def rule(**kw):
    """A pricing-rule dict with sensible defaults; override fields via kwargs."""
    base = dict(id=1, name="r", uplift_type="markup", uplift_percent=0.0,
                fixed_uplift=0.0, round_up=0, cond_cost_gt=None,
                pricing_key=None, product_group=None)
    base.update(kw)
    return base


class ApplyFormulaTests(unittest.TestCase):
    def test_markup_percent(self):
        self.assertEqual(
            pricing.apply_formula(100.0, rule(uplift_type="markup", uplift_percent=20)), 120.0)

    def test_margin_percent(self):
        # margin: C / (1 - pct/100) -> 100 / 0.8 = 125
        self.assertEqual(
            pricing.apply_formula(100.0, rule(uplift_type="margin", uplift_percent=20)), 125.0)

    def test_margin_100_or_more_treated_as_markup(self):
        self.assertEqual(
            pricing.apply_formula(100.0, rule(uplift_type="margin", uplift_percent=100)), 200.0)

    def test_fixed_uplift(self):
        self.assertEqual(pricing.apply_formula(100.0, rule(fixed_uplift=15)), 115.0)

    def test_round_up_ceils_to_whole_pound(self):
        self.assertEqual(pricing.apply_formula(100.0, rule(fixed_uplift=0.5, round_up=1)), 101.0)

    def test_combined_percent_fixed_round(self):
        # 50 * 1.10 = 55, + 5 = 60, ceil = 60
        self.assertEqual(
            pricing.apply_formula(50.0, rule(uplift_percent=10, fixed_uplift=5, round_up=1)), 60.0)

    def test_none_cost_treated_as_zero(self):
        self.assertEqual(pricing.apply_formula(None, rule(fixed_uplift=10)), 10.0)


class MatchingTests(unittest.TestCase):
    def test_no_conditions_matches_anything(self):
        self.assertTrue(pricing._matches(rule(), 5.0, "", ""))

    def test_cost_gt_is_strict(self):
        r = rule(cond_cost_gt=50)
        self.assertTrue(pricing._matches(r, 60.0, "", ""))
        self.assertFalse(pricing._matches(r, 50.0, "", ""))  # strictly greater
        self.assertFalse(pricing._matches(r, 40.0, "", ""))

    def test_pricing_key_case_insensitive(self):
        r = rule(pricing_key="Alpha")
        self.assertTrue(pricing._matches(r, 0.0, "alpha", ""))
        self.assertFalse(pricing._matches(r, 0.0, "beta", ""))

    def test_product_group(self):
        r = rule(product_group="Tyres")
        self.assertTrue(pricing._matches(r, 0.0, "", "tyres"))
        self.assertFalse(pricing._matches(r, 0.0, "", "oil"))


class SpecificityTests(unittest.TestCase):
    def test_counts_set_conditions(self):
        self.assertEqual(pricing._specificity(rule()), 0)
        self.assertEqual(pricing._specificity(rule(cond_cost_gt=10)), 1)
        self.assertEqual(
            pricing._specificity(rule(cond_cost_gt=10, pricing_key="A", product_group="G")), 3)


class BestRuleTests(unittest.TestCase):
    def test_most_specific_wins(self):
        generic = rule(id=1, uplift_percent=10)
        specific = rule(id=2, uplift_percent=50, pricing_key="A")
        self.assertEqual(pricing.best_rule(100.0, "A", "", rules=[generic, specific])["id"], 2)

    def test_tie_broken_by_earliest_created(self):
        later = rule(id=5, pricing_key="A")
        earlier = rule(id=2, pricing_key="A")
        self.assertEqual(pricing.best_rule(0.0, "A", "", rules=[later, earlier])["id"], 2)

    def test_no_match_returns_none(self):
        self.assertIsNone(pricing.best_rule(0.0, "X", "", rules=[rule(pricing_key="A")]))


class PriceFromRulesTests(unittest.TestCase):
    def test_computes_price_for_matching_rule(self):
        rules = [rule(id=1, uplift_type="markup", uplift_percent=20)]
        self.assertEqual(pricing.price_from_rules(100.0, "", "", rules), 120.0)

    def test_none_when_no_rule_matches(self):
        self.assertIsNone(pricing.price_from_rules(50.0, "B", "", [rule(pricing_key="A")]))


class PricingDbRoundTripTests(DatabaseTestCase):
    def test_create_list_and_select_most_specific(self):
        pricing.create_rule("Generic", uplift_type="markup", uplift_percent=10)
        pricing.create_rule("VIP", uplift_type="markup", uplift_percent=50, pricing_key="VIP")
        rules = pricing.list_rules()
        self.assertEqual(len(rules), 2)
        # A VIP product picks the more specific rule; a plain one falls to generic.
        self.assertEqual(pricing.price_from_rules(100.0, "VIP", "", rules), 150.0)
        self.assertEqual(pricing.price_from_rules(100.0, "", "", rules), 110.0)


if __name__ == "__main__":
    unittest.main()
