"""Unit tests for the pure money calculations (no DB / UI needed)."""
import unittest

import money


class LineAmountsTests(unittest.TestCase):
    def test_standard_rate(self):
        net, vat, gross = money.line_amounts(2, 10.0, 20.0)
        self.assertEqual((net, vat, gross), (20.0, 4.0, 24.0))

    def test_reduced_rate(self):
        self.assertEqual(money.line_amounts(1, 100.0, 5.0), (100.0, 5.0, 105.0))

    def test_zero_rate(self):
        self.assertEqual(money.line_amounts(3, 10.0, 0.0), (30.0, 0.0, 30.0))

    def test_zero_quantity_is_all_zero(self):
        self.assertEqual(money.line_amounts(0, 10.0, 20.0), (0.0, 0.0, 0.0))

    def test_missing_rate_defaults_to_20(self):
        # No vat_rate argument -> DEFAULT_VAT_RATE (20%).
        self.assertEqual(money.line_amounts(1, 100.0), (100.0, 20.0, 120.0))

    def test_none_rate_defaults_to_20(self):
        # Mirrors the SQL COALESCE(vat_rate, 20) used by the persisted aggregates.
        self.assertEqual(money.line_amounts(1, 100.0, None), (100.0, 20.0, 120.0))

    def test_namedtuple_fields(self):
        amt = money.line_amounts(2, 5.0, 20.0)
        self.assertEqual(amt.net, 10.0)
        self.assertEqual(amt.vat, 2.0)
        self.assertEqual(amt.gross, 12.0)


class DocumentTotalsTests(unittest.TestCase):
    def test_empty_document_is_zero(self):
        self.assertEqual(money.document_totals([]), (0.0, 0.0, 0.0))

    def test_sales_lines_use_unit_price(self):
        lines = [
            {"quantity": 2, "unit_price": 10.0, "vat_rate": 20.0},   # 20 / 4 / 24
            {"quantity": 1, "unit_price": 50.0, "vat_rate": 0.0},    # 50 / 0 / 50
        ]
        self.assertEqual(money.document_totals(lines), (70.0, 4.0, 74.0))

    def test_purchase_lines_use_cost_price(self):
        lines = [
            {"quantity": 3, "cost_price": 10.0, "vat_rate": 20.0},   # 30 / 6 / 36
            {"quantity": 2, "cost_price": 5.0, "vat_rate": 5.0},     # 10 / 0.5 / 10.5
        ]
        self.assertEqual(
            money.document_totals(lines, price_key="cost_price"), (40.0, 6.5, 46.5)
        )

    def test_line_missing_rate_defaults_to_20(self):
        lines = [{"quantity": 1, "unit_price": 100.0}]  # no vat_rate
        self.assertEqual(money.document_totals(lines), (100.0, 20.0, 120.0))


if __name__ == "__main__":
    unittest.main()
