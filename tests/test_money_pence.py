"""Tests for the integer-pence money layer: conversion helpers, per-line VAT
rounding, that the SQL aggregates match the pure money module exactly, and that
the one-shot migration back-fills the pence columns."""
import unittest

from core import money, migrate_money, dbmaint, migrations
from core.database import get_connection
from tests.support import DatabaseTestCase


class PenceHelperTests(unittest.TestCase):
    def test_to_pence_clean_two_dp(self):
        self.assertEqual(money.to_pence(14.99), 1499)
        self.assertEqual(money.to_pence("0.01"), 1)
        self.assertEqual(money.to_pence(0), 0)
        self.assertEqual(money.to_pence(None), 0)

    def test_to_pence_half_up(self):
        # .x5 rounds up (half-up), via Decimal(str(value)).
        self.assertEqual(money.to_pence(2.675), 268)
        self.assertEqual(money.to_pence(21.7355), 2174)

    def test_round_trip(self):
        self.assertEqual(money.from_pence(money.to_pence(123.45)), 123.45)

    def test_format_pence(self):
        self.assertEqual(money.format_pence(123456), "1,234.56")
        self.assertEqual(money.format_pence(0), "0.00")

    def test_vat_pence_per_line_half_up(self):
        # 9.99 @ 20% = 199.8p -> 200p
        self.assertEqual(money.vat_pence(999, 20.0), 200)
        # 5% of 1000p = 50p exactly
        self.assertEqual(money.vat_pence(1000, 5.0), 50)
        self.assertEqual(money.vat_pence(3000, 0.0), 0)
        self.assertEqual(money.vat_pence(1000, None), 200)  # default 20%

    def test_line_amounts_pence(self):
        self.assertEqual(money.line_amounts_pence(4, 5000, 20.0), (20000, 4000, 24000))

    def test_line_amounts_pounds_is_penny_accurate(self):
        # Pounds API rounds VAT per line: 1 x 9.99 @ 20% -> vat 2.00 (not 1.998).
        net, vat, gross = money.line_amounts(1, 9.99, 20.0)
        self.assertEqual((net, vat, gross), (9.99, 2.00, 11.99))


class SqlMatchesMoneyTests(DatabaseTestCase):
    def test_sale_totals_pence_match_money_module(self):
        customer = self.make_customer()
        pid = self.make_product()
        items = [
            {"item_type": "product", "product_id": pid, "service_id": None,
             "description": "", "quantity": 3, "unit_price": 9.99, "vat_rate": 20.0},
            {"item_type": "product", "product_id": pid, "service_id": None,
             "description": "", "quantity": 1, "unit_price": 50.0, "vat_rate": 5.0},
            {"item_type": "product", "product_id": pid, "service_id": None,
             "description": "", "quantity": 2, "unit_price": 12.5, "vat_rate": 0.0},
        ]
        sale = self.make_sale_invoice(customer_id=customer, items=items)
        from core import sales
        sql = sales.sale_totals_pence(sale)
        stored = [dict(it) for it in sales.get_sale_items(sale)]
        py = money.document_totals_pence(stored, "unit_price_pence")
        self.assertEqual((sql["net"], sql["vat"], sql["gross"]), tuple(py))

    def test_purchase_totals_pence_match_money_module(self):
        from core import purchases
        supplier = self.make_supplier()
        pid = self.make_product()
        items = [
            {"product_id": pid, "quantity": 7, "cost_price": 3.33, "vat_rate": 20.0},
            {"product_id": pid, "quantity": 2, "cost_price": 5.0, "vat_rate": 5.0},
        ]
        purchase = purchases.create_purchase(supplier, "Invoice", "INV9", "2026-01-01", items)
        sql = purchases.purchase_totals_pence(purchase)
        stored = [dict(it) for it in purchases.get_purchase_items(purchase)]
        py = money.document_totals_pence(stored, "cost_price_pence")
        self.assertEqual((sql["net"], sql["vat"], sql["gross"]), tuple(py))


class MigrationTests(DatabaseTestCase):
    def test_migrate_money_backfills_pence(self):
        from core import purchases
        supplier = self.make_supplier()
        pid = self.make_product()
        purchase = purchases.create_purchase(
            supplier, "Invoice", "INV1", "2026-01-01",
            [{"product_id": pid, "quantity": 4, "cost_price": 12.34, "vat_rate": 20.0}])
        # Simulate a pre-migration row: zero out the pence column.
        with get_connection() as conn:
            conn.execute("UPDATE purchase_items SET cost_price_pence = 0")
        migrate_money.run()
        with get_connection() as conn:
            pence = conn.execute(
                "SELECT cost_price_pence FROM purchase_items").fetchone()[0]
        self.assertEqual(pence, 1234)

    def test_run_pending_is_idempotent(self):
        # After init_db the version is already current; running again does nothing.
        self.assertGreaterEqual(dbmaint.schema_version(), 1)
        migrations.run_pending()  # no error, no change
        self.assertGreaterEqual(dbmaint.schema_version(), 1)


if __name__ == "__main__":
    unittest.main()
