"""Tests for stock level and average cost (both feed pricing and availability).

Stock = invoiced purchases - sold (Order/Invoice sales). Average cost is the
quantity-weighted unit cost across *invoiced* purchases only.
"""
from core import products, purchases, sales as sale_db
from tests.support import DatabaseTestCase


class AverageCostTests(DatabaseTestCase):
    def setUp(self):
        super().setUp()
        self.supplier = self.make_supplier()
        self.product = self.make_product()

    def _invoice(self, quantity, cost):
        purchases.create_purchase(
            self.supplier, "Invoice", "INV", "2026-01-01",
            [{"product_id": self.product, "quantity": quantity, "cost_price": cost, "vat_rate": 20}])

    def _order(self, quantity, cost):
        purchases.create_purchase(
            self.supplier, "Order", "ORD", "2026-01-01",
            [{"product_id": self.product, "quantity": quantity, "cost_price": cost, "vat_rate": 20}])

    def test_no_purchases_is_zero(self):
        self.assertEqual(products.average_cost(self.product), 0.0)

    def test_single_invoice(self):
        self._invoice(10, 5.0)
        self.assertEqual(products.average_cost(self.product), 5.0)

    def test_quantity_weighted_across_invoices(self):
        self._invoice(10, 5.0)    # spend 50
        self._invoice(30, 9.0)    # spend 270  -> (50+270)/40 = 8.0
        self.assertEqual(products.average_cost(self.product), 8.0)

    def test_orders_are_ignored(self):
        self._invoice(10, 5.0)
        self._order(10, 100.0)    # an Order must not move the average
        self.assertEqual(products.average_cost(self.product), 5.0)


class StockLevelTests(DatabaseTestCase):
    def setUp(self):
        super().setUp()
        self.supplier = self.make_supplier()
        self.customer = self.make_customer()
        self.product = self.make_product()

    def _stock(self):
        rows, _ = products.query_products()
        return next(r["stock"] for r in rows if r["id"] == self.product)

    def _purchase(self, status, quantity):
        purchases.create_purchase(
            self.supplier, status, "REF", "2026-01-01",
            [{"product_id": self.product, "quantity": quantity, "cost_price": 5.0, "vat_rate": 20}])

    def _sale(self, status, quantity):
        sale_db.create_sale(
            self.customer, status, "2026-01-01",
            [{"item_type": "product", "product_id": self.product,
              "quantity": quantity, "unit_price": 10.0, "vat_rate": 20}])

    def test_invoiced_purchase_adds_stock(self):
        self._purchase("Invoice", 10)
        self.assertEqual(self._stock(), 10)

    def test_purchase_order_does_not_add_stock(self):
        self._purchase("Order", 10)
        self.assertEqual(self._stock(), 0)

    def test_sale_order_reduces_stock(self):
        self._purchase("Invoice", 10)
        self._sale("Order", 3)
        self.assertEqual(self._stock(), 7)

    def test_sale_quote_does_not_reduce_stock(self):
        self._purchase("Invoice", 10)
        self._sale("Quote", 3)        # a Quote is provisional
        self.assertEqual(self._stock(), 10)

    def test_sale_invoice_reduces_stock(self):
        self._purchase("Invoice", 10)
        self._sale("Invoice", 4)
        self.assertEqual(self._stock(), 6)
