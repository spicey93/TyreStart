"""Tests for ISO date storage: daterange parse/format/normalise helpers, the
one-shot date migration, and that the data layer stores ISO on write."""
import datetime
import unittest

from core import daterange, migrate_dates
from core.database import get_connection
from tests.support import DatabaseTestCase


class DateRangeHelperTests(unittest.TestCase):
    def test_parse_accepts_iso_and_legacy(self):
        self.assertEqual(daterange.parse("2026-06-11"), datetime.date(2026, 6, 11))
        self.assertEqual(daterange.parse("11/06/26"), datetime.date(2026, 6, 11))
        self.assertEqual(daterange.parse("11/06/2026"), datetime.date(2026, 6, 11))
        self.assertIsNone(daterange.parse(""))
        self.assertIsNone(daterange.parse("not a date"))

    def test_to_iso_normalises(self):
        self.assertEqual(daterange.to_iso("11/06/26"), "2026-06-11")
        self.assertEqual(daterange.to_iso("2026-06-11"), "2026-06-11")   # idempotent
        self.assertEqual(daterange.to_iso(datetime.date(2026, 6, 11)), "2026-06-11")
        self.assertEqual(daterange.to_iso(""), "")
        self.assertEqual(daterange.to_iso("garbage"), "garbage")          # passes through

    def test_format_stored_shows_ddmmyy(self):
        self.assertEqual(daterange.format_stored("2026-06-11"), "11/06/26")
        self.assertEqual(daterange.format_stored("11/06/26"), "11/06/26")
        self.assertEqual(daterange.format_stored(""), "")

    def test_in_range_sql(self):
        clause, params = daterange.in_range_sql(
            datetime.date(2026, 1, 1), datetime.date(2026, 3, 31), "jr.date")
        self.assertEqual(clause, "jr.date >= ? AND jr.date <= ?")
        self.assertEqual(params, ["2026-01-01", "2026-03-31"])
        clause, params = daterange.in_range_sql(None, None)
        self.assertEqual(clause, "1=1")
        self.assertEqual(params, [])


class WriteStoresIsoTests(DatabaseTestCase):
    def test_create_sale_stores_iso(self):
        from core import sales
        customer = self.make_customer()
        sale = self.make_sale_invoice(customer_id=customer, date="11/06/26")
        with get_connection() as conn:
            stored = conn.execute("SELECT date FROM sales WHERE id = ?", (sale,)).fetchone()[0]
        self.assertEqual(stored, "2026-06-11")

    def test_create_payment_stores_iso(self):
        from core import payments
        supplier = self.make_supplier()
        pid = self.make_payment(supplier, 10.0, date="01/02/26")
        with get_connection() as conn:
            stored = conn.execute("SELECT date FROM payments WHERE id = ?", (pid,)).fetchone()[0]
        self.assertEqual(stored, "2026-02-01")


class DateMigrationTests(DatabaseTestCase):
    def test_migrate_dates_converts_legacy(self):
        from core import purchases
        supplier = self.make_supplier()
        prod = self.make_product()
        purchase = purchases.create_purchase(
            supplier, "Invoice", "INV1", "2026-01-01",
            [{"product_id": prod, "quantity": 1, "cost_price": 5.0, "vat_rate": 20.0}])
        # Force a legacy DD/MM/YY value as if pre-migration.
        with get_connection() as conn:
            conn.execute("UPDATE purchases SET date = '15/03/25' WHERE id = ?", (purchase,))
        migrate_dates.run()
        with get_connection() as conn:
            stored = conn.execute(
                "SELECT date FROM purchases WHERE id = ?", (purchase,)).fetchone()[0]
        self.assertEqual(stored, "2025-03-15")
        # Idempotent: running again leaves ISO unchanged.
        migrate_dates.run()
        with get_connection() as conn:
            stored = conn.execute(
                "SELECT date FROM purchases WHERE id = ?", (purchase,)).fetchone()[0]
        self.assertEqual(stored, "2025-03-15")


if __name__ == "__main__":
    unittest.main()
