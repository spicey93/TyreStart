"""Tests for the dev-branch additions: date-period filters, the extra supplier
account fields, and the purchase reconciled/paid data used by list filters."""
import datetime
import unittest

from core import daterange, suppliers, purchases, payments
from tests.support import DatabaseTestCase


def cost_line(product_id, quantity, cost_price, vat_rate=20.0):
    return {"product_id": product_id, "quantity": quantity,
            "cost_price": cost_price, "vat_rate": vat_rate}


class DateRangeTests(unittest.TestCase):
    TODAY = datetime.date(2026, 6, 11)  # a Thursday

    def test_parse_accepts_two_and_four_digit_years(self):
        self.assertEqual(daterange.parse("09/06/26"), datetime.date(2026, 6, 9))
        self.assertEqual(daterange.parse("09/06/2026"), datetime.date(2026, 6, 9))
        self.assertIsNone(daterange.parse(""))
        self.assertIsNone(daterange.parse("not a date"))

    def test_period_ranges(self):
        pr = lambda p: daterange.period_range(p, today=self.TODAY)
        self.assertEqual(pr("All"), (None, None))
        self.assertEqual(pr("Custom"), (None, None))
        self.assertEqual(pr("Today"), (self.TODAY, self.TODAY))
        self.assertEqual(pr("Yesterday"),
                         (datetime.date(2026, 6, 10), datetime.date(2026, 6, 10)))
        self.assertEqual(pr("This week"),
                         (datetime.date(2026, 6, 8), datetime.date(2026, 6, 14)))
        self.assertEqual(pr("Last week"),
                         (datetime.date(2026, 6, 1), datetime.date(2026, 6, 7)))
        self.assertEqual(pr("This month"),
                         (datetime.date(2026, 6, 1), datetime.date(2026, 6, 30)))
        self.assertEqual(pr("Last month"),
                         (datetime.date(2026, 5, 1), datetime.date(2026, 5, 31)))
        self.assertEqual(pr("This year"),
                         (datetime.date(2026, 1, 1), datetime.date(2026, 12, 31)))
        self.assertEqual(pr("Last year"),
                         (datetime.date(2025, 1, 1), datetime.date(2025, 12, 31)))

    def test_in_range_inclusive_with_open_bounds(self):
        start, end = datetime.date(2026, 6, 1), datetime.date(2026, 6, 30)
        self.assertTrue(daterange.in_range("15/06/26", start, end))
        self.assertTrue(daterange.in_range("01/06/26", start, end))   # inclusive
        self.assertTrue(daterange.in_range("30/06/26", start, end))   # inclusive
        self.assertFalse(daterange.in_range("31/05/26", start, end))
        self.assertFalse(daterange.in_range("01/07/26", start, end))
        # Open bounds don't restrict that side.
        self.assertTrue(daterange.in_range("01/01/00", None, end))
        self.assertTrue(daterange.in_range("31/12/40", start, None))
        # Unparseable dates only pass when both bounds are open.
        self.assertFalse(daterange.in_range("", start, end))
        self.assertTrue(daterange.in_range("", None, None))


class SupplierFieldTests(DatabaseTestCase):
    def test_extra_fields_round_trip(self):
        sid = suppliers.add_supplier(
            "Acme", account_number="A100", status="On Hold", address="1 High St",
            postcode="AB1 2CD", credit_limit=1500.0, vat_code="T1",
            vat_number="GB123", payment_method="BACS")
        s = suppliers.get_supplier(sid)
        self.assertEqual(s["status"], "On Hold")
        self.assertEqual(s["address"], "1 High St")
        self.assertEqual(s["postcode"], "AB1 2CD")
        self.assertEqual(s["credit_limit"], 1500.0)
        self.assertEqual(s["vat_code"], "T1")
        self.assertEqual(s["vat_number"], "GB123")
        self.assertEqual(s["payment_method"], "BACS")

    def test_defaults_when_omitted(self):
        s = suppliers.get_supplier(suppliers.add_supplier("Plain"))
        self.assertEqual(s["status"], "Open")
        self.assertEqual(s["credit_limit"], 0.0)
        self.assertEqual(s["payment_method"], "")

    def test_update_changes_fields(self):
        sid = suppliers.add_supplier("Beta")
        suppliers.update_supplier(sid, "Beta", status="Closed", credit_limit=200.0,
                                  payment_method="Cash")
        s = suppliers.get_supplier(sid)
        self.assertEqual(s["status"], "Closed")
        self.assertEqual(s["credit_limit"], 200.0)
        self.assertEqual(s["payment_method"], "Cash")


class PurchaseReconciledPaidTests(DatabaseTestCase):
    def setUp(self):
        super().setUp()
        self.supplier = self.make_supplier()
        self.product = self.make_product()
        self.nominal = self.first_nominal()

    def test_reconciled_flag_persists(self):
        pid = purchases.create_purchase(
            self.supplier, "Invoice", "INV1", "2026-01-01",
            [cost_line(self.product, 1, 100.0, 0.0)], reconciled=1)
        self.assertEqual(purchases.get_purchase(pid)["reconciled"], 1)
        purchases.set_reconciled(pid, 0)
        self.assertEqual(purchases.get_purchase(pid)["reconciled"], 0)

    def test_supplier_purchases_reports_allocated_for_paid(self):
        pid = purchases.create_purchase(
            self.supplier, "Invoice", "INV1", "2026-06-15",
            [cost_line(self.product, 1, 100.0, 0.0)])  # gross 100
        payments.create_payment(self.supplier, self.nominal, "BACS", "2026-06-16",
                                40.0, [{"purchase_id": pid, "amount": 40.0}])
        row = next(r for r in purchases.supplier_purchases(self.supplier) if r["id"] == pid)
        self.assertEqual(row["total"], 100.0)
        self.assertEqual(row["allocated"], 40.0)
        self.assertEqual(row["reconciled"], 0)
        # Fully allocate it; now allocated covers the total (the "Paid" filter test).
        payments.create_payment(self.supplier, self.nominal, "BACS", "2026-06-17",
                                60.0, [{"purchase_id": pid, "amount": 60.0}])
        row = next(r for r in purchases.supplier_purchases(self.supplier) if r["id"] == pid)
        self.assertEqual(row["allocated"], 100.0)


if __name__ == "__main__":
    unittest.main()
