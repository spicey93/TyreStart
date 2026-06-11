"""Tests for the money-balance logic: purchase totals, customer/supplier
balances, outstanding amounts, and that a receipt/payment totals its allocations.
"""
from core import (purchases, payments, receipts, sales as sale_db, money)
from tests.support import DatabaseTestCase


def sale_line(quantity, unit_price, vat_rate=20.0):
    return {"item_type": "product", "quantity": quantity,
            "unit_price": unit_price, "vat_rate": vat_rate}


def cost_line(product_id, quantity, cost_price, vat_rate=20.0):
    return {"product_id": product_id, "quantity": quantity,
            "cost_price": cost_price, "vat_rate": vat_rate}


class PurchaseTotalsTests(DatabaseTestCase):
    def test_sql_totals_match_money_module(self):
        supplier = self.make_supplier()
        product = self.make_product()
        items = [cost_line(product, 10, 5.0, 20.0), cost_line(product, 1, 50.0, 0.0)]  # 100 / 10 / 110
        pid = purchases.create_purchase(supplier, "Invoice", "INV1", "2026-01-01", items)
        sql = purchases.purchase_totals(pid)
        stored = [dict(it) for it in purchases.get_purchase_items(pid)]
        py = money.document_totals(stored, "cost_price")
        self.assertAlmostEqual(sql["net"], py.net)
        self.assertAlmostEqual(sql["vat"], py.vat)
        self.assertAlmostEqual(sql["gross"], py.gross)
        self.assertEqual((py.net, py.vat, py.gross), (100.0, 10.0, 110.0))


class CustomerBalanceTests(DatabaseTestCase):
    def setUp(self):
        super().setUp()
        self.customer = self.make_customer()
        self.nominal = self.first_nominal()
        # An Order for gross 24.00 (2 x 10 net = 20, + 20% VAT = 4).
        self.sale = sale_db.create_sale(
            self.customer, "Order", "2026-01-01", [sale_line(2, 10.0)])

    def test_balance_is_owed_minus_receipts(self):
        self.assertEqual(receipts.customer_balance(self.customer), 24.0)
        receipts.create_receipt(self.customer, self.nominal, "Cash", "2026-01-02",
                                [{"sale_id": self.sale, "amount": 10.0}])
        self.assertEqual(receipts.customer_balance(self.customer), 14.0)

    def test_quote_is_not_owed(self):
        sale_db.create_sale(self.customer, "Quote", "2026-01-01", [sale_line(5, 100.0)])
        self.assertEqual(receipts.customer_balance(self.customer), 24.0)  # quote excluded

    def test_outstanding_per_sale(self):
        receipts.create_receipt(self.customer, self.nominal, "Cash", "2026-01-02",
                                [{"sale_id": self.sale, "amount": 10.0}])
        rows = sale_db.customer_sales(self.customer)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["outstanding"], 14.0)

    def test_receipt_amount_is_sum_of_allocations(self):
        sale2 = sale_db.create_sale(self.customer, "Order", "2026-01-01", [sale_line(1, 100.0)])
        rid = receipts.create_receipt(
            self.customer, self.nominal, "BACS", "2026-01-02",
            [{"sale_id": self.sale, "amount": 10.0}, {"sale_id": sale2, "amount": 5.0}])
        receipt = next(r for r in receipts.get_receipts(self.customer) if r["id"] == rid)
        self.assertEqual(receipt["amount"], 15.0)


class SupplierBalanceTests(DatabaseTestCase):
    def setUp(self):
        super().setUp()
        self.supplier = self.make_supplier()
        self.product = self.make_product()
        self.nominal = self.first_nominal()
        # An Invoice for gross 110.00 (10 x 5 net = 50 + 20% = 60; 1 x 50 @ 0% = 50).
        self.purchase = purchases.create_purchase(
            self.supplier, "Invoice", "INV1", "2026-01-01",
            [cost_line(self.product, 10, 5.0, 20.0), cost_line(self.product, 1, 50.0, 0.0)])

    def test_balance_is_invoiced_minus_payments(self):
        self.assertEqual(payments.supplier_balance(self.supplier), 110.0)
        payments.create_payment(self.supplier, self.nominal, "BACS", "2026-01-02",
                                [{"purchase_id": self.purchase, "amount": 40.0}])
        self.assertEqual(payments.supplier_balance(self.supplier), 70.0)

    def test_order_is_not_invoiced(self):
        purchases.create_purchase(self.supplier, "Order", "ORD", "2026-01-01",
                                  [cost_line(self.product, 5, 100.0, 20.0)])
        self.assertEqual(payments.supplier_balance(self.supplier), 110.0)  # order excluded

    def test_outstanding_per_invoice(self):
        payments.create_payment(self.supplier, self.nominal, "BACS", "2026-01-02",
                                [{"purchase_id": self.purchase, "amount": 40.0}])
        rows = purchases.supplier_invoices(self.supplier)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["outstanding"], 70.0)

    def test_outstanding_only_filters_settled(self):
        payments.create_payment(self.supplier, self.nominal, "BACS", "2026-01-02",
                                [{"purchase_id": self.purchase, "amount": 110.0}])  # fully paid
        self.assertEqual(purchases.supplier_invoices(self.supplier, outstanding_only=True), [])
