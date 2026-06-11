"""Tests for sale numbering and totals (run against a throwaway database)."""
from core import customers
from core import sales as sale_db
from core import money
from tests.support import DatabaseTestCase


def product_line(quantity=1, unit_price=10.0, vat_rate=20.0):
    return {"item_type": "product", "quantity": quantity,
            "unit_price": unit_price, "vat_rate": vat_rate}


class SaleNumberingTests(DatabaseTestCase):
    def setUp(self):
        super().setUp()
        self.customer = customers.add_customer("Test Customer")

    def _ref(self, sale_id):
        return sale_db.get_sale(sale_id)["reference"]

    def test_sequence_is_independent_per_status(self):
        q1 = sale_db.create_sale(self.customer, "Quote", "2026-01-01", [product_line()])
        q2 = sale_db.create_sale(self.customer, "Quote", "2026-01-01", [product_line()])
        o1 = sale_db.create_sale(self.customer, "Order", "2026-01-01", [product_line()])
        self.assertEqual(self._ref(q1), "Q0001")
        self.assertEqual(self._ref(q2), "Q0002")
        self.assertEqual(self._ref(o1), "O0001")  # Order sequence starts fresh

    def test_promotion_keeps_prior_number_and_takes_next(self):
        sale_db.create_sale(self.customer, "Order", "2026-01-01", [product_line()])    # O0001
        quote = sale_db.create_sale(self.customer, "Quote", "2026-01-01", [product_line()])  # Q0001
        sale_db.update_sale(quote, self.customer, "Order", "2026-01-01", [product_line()])
        row = sale_db.get_sale(quote)
        self.assertEqual(row["quote_no"], "Q0001")  # number earned as a Quote is kept
        self.assertEqual(row["order_no"], "O0002")  # next free Order number
        self.assertEqual(row["reference"], "O0002")  # reference mirrors current status
        self.assertEqual(row["status"], "Order")


class SaleTotalsTests(DatabaseTestCase):
    def setUp(self):
        super().setUp()
        self.customer = customers.add_customer("Test Customer")

    def test_sql_totals_match_money_module(self):
        items = [product_line(2, 10.0, 20.0), product_line(1, 50.0, 0.0)]  # 70 / 4 / 74
        sale_id = sale_db.create_sale(self.customer, "Invoice", "2026-01-01", items)
        sql = sale_db.sale_totals(sale_id)
        stored = [dict(it) for it in sale_db.get_sale_items(sale_id)]
        py = money.document_totals(stored, "unit_price")
        self.assertAlmostEqual(sql["net"], py.net)
        self.assertAlmostEqual(sql["vat"], py.vat)
        self.assertAlmostEqual(sql["gross"], py.gross)
        self.assertEqual((py.net, py.vat, py.gross), (70.0, 4.0, 74.0))
