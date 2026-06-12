"""Tests for sales credit notes: SCN numbering, stock return, customer balance
reduction, ledger postings (mirror of an invoice), and VAT Box 1/6 reduction."""
from core import accounts, journal, products, receipts, sales, vat
from tests.support import DatabaseTestCase


class SalesCreditNoteTests(DatabaseTestCase):
    def setUp(self):
        super().setUp()
        self.customer = self.make_customer()
        self.prod = self.make_product()
        # Stock the product: buy 10 @ £30 (avg cost 3000p).
        from core import purchases
        purchases.create_purchase(
            self.make_supplier(), "Invoice", "PINV", "2026-01-01",
            [{"product_id": self.prod, "quantity": 10, "cost_price": 30.0, "vat_rate": 20.0}])

    def _line(self, qty=2, price=50.0, rate=20.0):
        return {"item_type": "product", "product_id": self.prod, "service_id": None,
                "description": "", "quantity": qty, "unit_price": price, "vat_rate": rate}

    def test_credit_note_is_a_status_with_scn_number(self):
        self.assertIn("Credit Note", sales.STATUSES)
        cn = sales.create_sale(self.customer, "Credit Note", "2026-02-01", [self._line()],
                               ref_invoice="INV0001")
        row = sales.get_sale(cn)
        self.assertEqual(row["status"], "Credit Note")
        self.assertTrue(row["credit_no"].startswith("SCN"))
        self.assertEqual(row["ref_invoice"], "INV0001")

    def test_credit_note_returns_stock(self):
        before = products.product_stock(self.prod)   # 10 purchased
        # Sell 4 (stock 6), then credit-note 1 back (stock 7).
        sales.create_sale(self.customer, "Invoice", "2026-02-01", [self._line(qty=4)])
        self.assertEqual(products.product_stock(self.prod), before - 4)
        sales.create_sale(self.customer, "Credit Note", "2026-02-05", [self._line(qty=1)])
        self.assertEqual(products.product_stock(self.prod), before - 4 + 1)

    def test_credit_note_reduces_customer_balance(self):
        sales.create_sale(self.customer, "Invoice", "2026-02-01", [self._line(qty=2)])  # gross 120
        self.assertEqual(receipts.customer_balance(self.customer), 120.0)
        sales.create_sale(self.customer, "Credit Note", "2026-02-05", [self._line(qty=1)])  # gross 60
        self.assertEqual(receipts.customer_balance(self.customer), 60.0)

    def test_credit_note_postings_mirror_invoice(self):
        sales.create_sale(self.customer, "Invoice", "2026-02-01", [self._line(qty=2)])
        # Invoice: debtors +12000, sales -10000, vat_output -2000, cogs +6000, stock -6000.
        sales.create_sale(self.customer, "Credit Note", "2026-02-05", [self._line(qty=1)])
        # Credit note for 1 unit: debtors -6000, sales +5000, vat_output +1000,
        # stock +3000 (back in), cogs -3000.
        def bal(tag):
            return journal.account_balance_pence(accounts.system_id(tag))
        self.assertEqual(bal("debtors"), 12000 - 6000)
        self.assertEqual(bal("sales"), -10000 + 5000)
        self.assertEqual(bal("vat_output"), -2000 + 1000)
        self.assertEqual(bal("cogs"), 6000 - 3000)
        self.assertEqual(bal("stock"), 30000 - 6000 + 3000)  # 30000 purchased
        d, c = journal.trial_balance_totals()
        self.assertEqual(d, c)

    def test_credit_note_reduces_vat_boxes(self):
        sales.create_sale(self.customer, "Invoice", "2026-02-01", [self._line(qty=2)])
        sales.create_sale(self.customer, "Credit Note", "2026-02-05", [self._line(qty=1)])
        boxes = vat.compute_boxes("2026-01-01", "2026-03-31")
        # Output VAT: 2000 - 1000 = 1000; net sales: 10000 - 5000 = 5000.
        self.assertEqual(boxes["box1"], 1000)
        self.assertEqual(boxes["box6"], 5000)
