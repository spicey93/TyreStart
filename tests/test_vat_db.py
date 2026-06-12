"""Tests for the VAT return: the 9 boxes computed from ledger + documents, the
journal cross-check, and the file/lock lifecycle."""
from core import accounts, journal, taxcodes, vat, sales, purchases
from tests.support import DatabaseTestCase


class TaxCodeSeedTests(DatabaseTestCase):
    def test_seeded(self):
        codes = {c["code"] for c in taxcodes.get_all()}
        self.assertEqual(codes, {"STD", "RED", "ZERO", "EXEMPT", "OUTSIDE", "RC"})

    def test_for_rate(self):
        self.assertEqual(taxcodes.for_rate(20.0), "STD")
        self.assertEqual(taxcodes.for_rate(5.0), "RED")
        self.assertEqual(taxcodes.for_rate(0.0), "ZERO")

    def test_in_box6_flags(self):
        self.assertEqual(taxcodes.get("ZERO")["in_box6"], 1)
        self.assertEqual(taxcodes.get("EXEMPT")["in_box6"], 0)
        self.assertEqual(taxcodes.get("OUTSIDE")["in_box6"], 0)


class VatBoxTests(DatabaseTestCase):
    def setUp(self):
        super().setUp()
        self.supplier = self.make_supplier()
        self.customer = self.make_customer()
        self.prod = self.make_product()
        # In-period sales invoice: 4 x £50 +20% = net 200, VAT 40.
        sales.create_sale(self.customer, "Invoice", "2026-02-10", [
            {"item_type": "product", "product_id": self.prod, "service_id": None,
             "description": "", "quantity": 4, "unit_price": 50.0, "vat_rate": 20.0}])
        # In-period purchase invoice: 10 x £20 +20% = net 200, VAT 40.
        purchases.create_purchase(self.supplier, "Invoice", "INV1", "2026-02-15", [
            {"product_id": self.prod, "quantity": 10, "cost_price": 20.0, "vat_rate": 20.0}])
        # Out-of-period sale (should be excluded).
        sales.create_sale(self.customer, "Invoice", "2026-05-01", [
            {"item_type": "product", "product_id": self.prod, "service_id": None,
             "description": "", "quantity": 1, "unit_price": 99.0, "vat_rate": 20.0}])

    def test_nine_boxes(self):
        boxes = vat.compute_boxes("2026-01-01", "2026-03-31")
        self.assertEqual(boxes["box1"], 4000)   # output VAT 40.00
        self.assertEqual(boxes["box4"], 4000)   # input VAT 40.00
        self.assertEqual(boxes["box3"], 4000)
        self.assertEqual(boxes["box5"], 0)      # 4000 - 4000
        self.assertEqual(boxes["box6"], 20000)  # net sales 200.00 (out-of-period excluded)
        self.assertEqual(boxes["box7"], 20000)  # net purchases 200.00
        self.assertEqual(boxes["box2"], 0)
        self.assertEqual(boxes["box8"], 0)
        self.assertEqual(boxes["box9"], 0)

    def test_box1_ties_to_ledger(self):
        # Box 1 ties to the Output VAT control account (credit-normal), capped at
        # the period end (which excludes the out-of-period sale).
        boxes = vat.compute_boxes("2026-01-01", "2026-03-31")
        ledger = -journal.account_balance_pence(
            accounts.system_id("vat_output"), end_date="2026-03-31")
        self.assertEqual(boxes["box1"], ledger)

    def test_cash_scheme_not_implemented(self):
        with self.assertRaises(NotImplementedError):
            vat.compute_boxes("2026-01-01", "2026-03-31", scheme="cash")


class VatLifecycleTests(DatabaseTestCase):
    def setUp(self):
        super().setUp()
        self.customer = self.make_customer()
        self.prod = self.make_product()
        sales.create_sale(self.customer, "Invoice", "2026-02-10", [
            {"item_type": "product", "product_id": self.prod, "service_id": None,
             "description": "", "quantity": 4, "unit_price": 50.0, "vat_rate": 20.0}])

    def test_compute_and_save_then_file_locks_journals(self):
        period = vat.create_period("2026-01-01", "2026-03-31")
        boxes = vat.compute_and_save(period)
        self.assertEqual(boxes["box1"], 4000)
        saved = vat.get_return(period)
        self.assertEqual(saved["box1"], 4000)
        self.assertIsNone(saved["filed_at"])

        vat.mark_filed(period)
        self.assertEqual(vat.get_period(period)["status"], "filed")
        # Every journal dated in the period is now locked.
        with self.subTest("journals locked"):
            from core.database import get_connection
            with get_connection() as conn:
                unlocked = conn.execute(
                    "SELECT COUNT(*) FROM journal "
                    "WHERE date BETWEEN '2026-01-01' AND '2026-03-31' AND locked = 0"
                ).fetchone()[0]
            self.assertEqual(unlocked, 0)

    def test_cannot_recompute_filed_period(self):
        period = vat.create_period("2026-01-01", "2026-03-31")
        vat.compute_and_save(period)
        vat.mark_filed(period)
        with self.assertRaises(ValueError):
            vat.compute_and_save(period)

    def test_correction_after_filing_lands_in_open_period(self):
        # File Q1, then edit the Q1 invoice; the correction must NOT change the
        # filed period's figures — it posts to the open period instead.
        period = vat.create_period("2026-01-01", "2026-03-31")
        vat.compute_and_save(period)
        vat.mark_filed(period)
        filed_box1 = vat.compute_boxes("2026-01-01", "2026-03-31")["box1"]
        self.assertEqual(filed_box1, 4000)
        sale = self.first_invoice_id()
        # Edit the (filed) invoice quantity 4 -> 5.
        sales.update_sale(sale, self.customer, "Invoice", "2026-02-10", [
            {"item_type": "product", "product_id": self.prod, "service_id": None,
             "description": "", "quantity": 5, "unit_price": 50.0, "vat_rate": 20.0}])
        # GL still balances, and the filed period's output VAT is unchanged.
        debits, credits = journal.trial_balance_totals()
        self.assertEqual(debits, credits)
        self.assertEqual(vat.compute_boxes("2026-01-01", "2026-03-31")["box1"], 4000)

    def test_cannot_delete_in_filed_period(self):
        period = vat.create_period("2026-01-01", "2026-03-31")
        vat.compute_and_save(period)
        vat.mark_filed(period)
        sale = self.first_invoice_id()
        with self.assertRaises(journal.LockedPeriodError):
            sales.delete_sale(sale)

    def first_invoice_id(self):
        from core.database import get_connection
        with get_connection() as conn:
            return conn.execute(
                "SELECT id FROM sales WHERE status = 'Invoice' ORDER BY id LIMIT 1"
            ).fetchone()[0]
