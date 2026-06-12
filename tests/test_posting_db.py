"""Tests for the general-ledger posting service: exact debit/credit lines per
document type, the debits==credits invariant, COGS at average cost, edit/delete
reversals, and that the GL control accounts reconcile to the subledger balances.
"""
from core import accounts, journal, sales, purchases, payments, receipts
from tests.support import DatabaseTestCase


class PostingTestCase(DatabaseTestCase):
    def bal(self, tag):
        """Net debit balance (pence) of a system account."""
        return journal.account_balance_pence(accounts.system_id(tag))

    def assert_balanced(self):
        debits, credits = journal.trial_balance_totals()
        self.assertEqual(debits, credits, "trial balance does not balance")

    def stocked_product(self, qty=4, cost=30.0):
        """A product with `qty` invoiced at `cost` (so it has an average cost)."""
        supplier = self.make_supplier()
        prod = self.make_product()
        purchases.create_purchase(
            supplier, "Invoice", "PINV", "2026-01-01",
            [{"product_id": prod, "quantity": qty, "cost_price": cost, "vat_rate": 20.0}])
        return prod


class SaleInvoiceTests(PostingTestCase):
    def test_sale_invoice_exact_lines(self):
        prod = self.stocked_product(qty=4, cost=30.0)   # avg cost 3000p
        customer = self.make_customer()
        sales.create_sale(customer, "Invoice", "2026-02-01", [
            {"item_type": "product", "product_id": prod, "service_id": None,
             "description": "", "quantity": 2, "unit_price": 50.0, "vat_rate": 20.0}])
        # Sale: net 10000, vat 2000, gross 12000; COGS 2*3000 = 6000.
        self.assertEqual(self.bal("debtors"), 12000)
        self.assertEqual(self.bal("sales"), -10000)
        self.assertEqual(self.bal("vat_output"), -2000)
        self.assertEqual(self.bal("cogs"), 6000)
        # Stock: +12000 from the purchase, -6000 from COGS.
        self.assertEqual(self.bal("stock"), 6000)
        self.assert_balanced()

    def test_service_line_has_no_cogs(self):
        customer = self.make_customer()
        svc = self.make_service()
        sales.create_sale(customer, "Invoice", "2026-02-01", [
            {"item_type": "service", "product_id": None, "service_id": svc,
             "description": "Fitting", "quantity": 1, "unit_price": 20.0, "vat_rate": 20.0}])
        self.assertEqual(self.bal("sales_services"), -2000)
        self.assertEqual(self.bal("vat_output"), -400)
        self.assertEqual(self.bal("cogs"), 0)
        self.assertEqual(self.bal("stock"), 0)
        self.assert_balanced()

    def test_quote_and_order_do_not_post(self):
        customer = self.make_customer()
        item = [{"item_type": "product", "product_id": None, "service_id": None,
                 "description": "", "quantity": 1, "unit_price": 100.0, "vat_rate": 20.0}]
        sales.create_sale(customer, "Quote", "2026-02-01", item)
        sales.create_sale(customer, "Order", "2026-02-01", item)
        self.assertEqual(self.bal("debtors"), 0)
        self.assertEqual(journal.trial_balance_totals(), (0, 0))


class PurchaseTests(PostingTestCase):
    def test_purchase_invoice_exact_lines(self):
        supplier = self.make_supplier()
        prod = self.make_product()
        purchases.create_purchase(supplier, "Invoice", "INV1", "2026-01-01", [
            {"product_id": prod, "quantity": 4, "cost_price": 30.0, "vat_rate": 20.0}])
        # net 12000, vat 2400, gross 14400.
        self.assertEqual(self.bal("stock"), 12000)
        self.assertEqual(self.bal("vat_input"), 2400)
        self.assertEqual(self.bal("creditors"), -14400)
        self.assert_balanced()

    def test_purchase_credit_note_reverses_signs(self):
        supplier = self.make_supplier()
        prod = self.make_product()
        purchases.create_purchase(supplier, "Credit Note", "", "2026-01-05", [
            {"product_id": prod, "quantity": 1, "cost_price": 30.0, "vat_rate": 20.0}])
        # net 3000, vat 600, gross 3600 — creditors debited (reduced), stock/vat credited.
        self.assertEqual(self.bal("creditors"), 3600)
        self.assertEqual(self.bal("stock"), -3000)
        self.assertEqual(self.bal("vat_input"), -600)
        self.assert_balanced()

    def test_order_does_not_post(self):
        supplier = self.make_supplier()
        prod = self.make_product()
        purchases.create_purchase(supplier, "Order", "PO1", "2026-01-01", [
            {"product_id": prod, "quantity": 4, "cost_price": 30.0, "vat_rate": 20.0}])
        self.assertEqual(journal.trial_balance_totals(), (0, 0))


class ReceiptPaymentTests(PostingTestCase):
    def test_receipt_posts_bank_and_debtors(self):
        prod = self.stocked_product()
        customer = self.make_customer()
        sale = sales.create_sale(customer, "Invoice", "2026-02-01", [
            {"item_type": "product", "product_id": prod, "service_id": None,
             "description": "", "quantity": 2, "unit_price": 50.0, "vat_rate": 20.0}])
        nominal = self.first_nominal()
        receipts.create_receipt(customer, nominal, "BACS", "2026-02-05",
                                [{"sale_id": sale, "amount": 120.0}])
        bank = accounts.id_for_nominal(nominal)
        self.assertEqual(journal.account_balance_pence(bank), 12000)
        self.assertEqual(self.bal("debtors"), 0)   # 12000 invoiced - 12000 received
        self.assert_balanced()

    def test_payment_posts_creditors_and_bank(self):
        supplier = self.make_supplier()
        prod = self.make_product()
        pur = purchases.create_purchase(supplier, "Invoice", "INV1", "2026-01-01", [
            {"product_id": prod, "quantity": 4, "cost_price": 30.0, "vat_rate": 20.0}])
        nominal = self.first_nominal()
        payments.create_payment(supplier, nominal, "BACS", "2026-01-10", 144.0,
                                [{"purchase_id": pur, "amount": 144.0}])
        bank = accounts.id_for_nominal(nominal)
        self.assertEqual(self.bal("creditors"), 0)        # 14400 owed - 14400 paid
        self.assertEqual(journal.account_balance_pence(bank), -14400)
        self.assert_balanced()


class ReversalTests(PostingTestCase):
    def test_edit_reverses_and_reposts(self):
        prod = self.stocked_product(qty=10, cost=30.0)
        customer = self.make_customer()
        sale = sales.create_sale(customer, "Invoice", "2026-02-01", [
            {"item_type": "product", "product_id": prod, "service_id": None,
             "description": "", "quantity": 2, "unit_price": 50.0, "vat_rate": 20.0}])
        self.assertEqual(self.bal("debtors"), 12000)
        # Edit: change quantity to 3.
        sales.update_sale(sale, customer, "Invoice", "2026-02-01", [
            {"item_type": "product", "product_id": prod, "service_id": None,
             "description": "", "quantity": 3, "unit_price": 50.0, "vat_rate": 20.0}])
        self.assertEqual(self.bal("debtors"), 18000)   # 3 * 60.00
        self.assertEqual(self.bal("sales"), -15000)
        self.assert_balanced()
        # There should now be three sale journals: original, its reversal, and the repost.
        self.assertEqual(len(journal.journals_for("sale", sale)), 3)

    def test_demote_invoice_to_order_reverses(self):
        prod = self.stocked_product()
        customer = self.make_customer()
        sale = sales.create_sale(customer, "Invoice", "2026-02-01", [
            {"item_type": "product", "product_id": prod, "service_id": None,
             "description": "", "quantity": 2, "unit_price": 50.0, "vat_rate": 20.0}])
        sales.update_sale(sale, customer, "Order", "2026-02-01", [
            {"item_type": "product", "product_id": prod, "service_id": None,
             "description": "", "quantity": 2, "unit_price": 50.0, "vat_rate": 20.0}])
        self.assertEqual(self.bal("debtors"), 0)
        self.assert_balanced()

    def test_delete_reverses_but_keeps_audit(self):
        supplier = self.make_supplier()
        prod = self.make_product()
        pur = purchases.create_purchase(supplier, "Invoice", "INV1", "2026-01-01", [
            {"product_id": prod, "quantity": 4, "cost_price": 30.0, "vat_rate": 20.0}])
        self.assertEqual(self.bal("creditors"), -14400)
        purchases.delete_purchase(pur)
        self.assertEqual(self.bal("creditors"), 0)
        self.assert_balanced()
        # Journals remain for audit (original + reversal).
        self.assertEqual(len(journal.journals_for("purchase", pur)), 2)


class ReconciliationTests(PostingTestCase):
    def test_gl_debtors_matches_customer_balance(self):
        prod = self.stocked_product()
        customer = self.make_customer()
        sale = sales.create_sale(customer, "Invoice", "2026-02-01", [
            {"item_type": "product", "product_id": prod, "service_id": None,
             "description": "", "quantity": 2, "unit_price": 50.0, "vat_rate": 20.0}])
        receipts.create_receipt(customer, self.first_nominal(), "BACS", "2026-02-05",
                                [{"sale_id": sale, "amount": 30.0}])
        # GL debtors (pence) == customer_balance (pounds) for invoiced docs.
        self.assertEqual(self.bal("debtors"), round(receipts.customer_balance(customer) * 100))

    def test_gl_creditors_matches_supplier_balance(self):
        supplier = self.make_supplier()
        prod = self.make_product()
        pur = purchases.create_purchase(supplier, "Invoice", "INV1", "2026-01-01", [
            {"product_id": prod, "quantity": 4, "cost_price": 30.0, "vat_rate": 20.0}])
        payments.create_payment(supplier, self.first_nominal(), "BACS", "2026-01-10", 44.40,
                                [{"purchase_id": pur, "amount": 44.40}])
        # creditors is credit-normal, so negate the net-debit balance to compare.
        self.assertEqual(-self.bal("creditors"), round(payments.supplier_balance(supplier) * 100))
