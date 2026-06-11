"""Tests for purchase credit notes: they reduce stock and the supplier balance,
and carry a manual number plus an optional linked invoice number."""
from core import purchases, products, payments
from tests.support import DatabaseTestCase


def line(product_id, quantity, cost_price=50.0, vat_rate=20.0):
    return {"product_id": product_id, "quantity": quantity,
            "cost_price": cost_price, "vat_rate": vat_rate}


class CreditNoteTests(DatabaseTestCase):
    def setUp(self):
        super().setUp()
        self.supplier = self.make_supplier()
        self.product = self.make_product()
        # Invoice 10 in at 50.00 net + 20% VAT -> gross 600.00, stock 10.
        self.invoice = purchases.create_purchase(
            self.supplier, "Invoice", "INV-1", "01/06/26",
            [line(self.product, 10)])

    def test_credit_note_reduces_stock(self):
        self.assertEqual(products.product_stock(self.product), 10)
        purchases.create_purchase(self.supplier, "Credit Note", "CN-1", "02/06/26",
                                  [line(self.product, 3)])
        self.assertEqual(products.product_stock(self.product), 7)

    def test_credit_note_reduces_supplier_balance(self):
        self.assertEqual(payments.supplier_balance(self.supplier), 600.0)
        purchases.create_purchase(self.supplier, "Credit Note", "CN-1", "02/06/26",
                                  [line(self.product, 3)])
        self.assertEqual(payments.supplier_balance(self.supplier), 420.0)  # 7 * 60

    def test_credit_note_auto_numbers_and_stores_links_and_refs(self):
        a = purchases.create_purchase(
            self.supplier, "Credit Note", "", "02/06/26",
            [line(self.product, 3)], 0, "INV-1", "CR-1", "RET-1")
        b = purchases.create_purchase(
            self.supplier, "Credit Note", "", "03/06/26", [line(self.product, 1)])
        self.assertEqual(purchases.get_purchase(a)["reference"], "CN0001")
        self.assertEqual(purchases.get_purchase(b)["reference"], "CN0002")
        row = purchases.get_purchase(a)
        self.assertEqual(row["po_reference"], "INV-1")        # the invoice it credits
        self.assertEqual(row["credit_reference"], "CR-1")
        self.assertEqual(row["return_reference"], "RET-1")

    def test_credit_notes_do_not_advance_po_numbering(self):
        purchases.create_purchase(self.supplier, "Credit Note", "", "02/06/26",
                                  [line(self.product, 1)])
        po = purchases.create_purchase(self.supplier, "Order", "", "03/06/26",
                                       [line(self.product, 1)])
        self.assertEqual(purchases.get_purchase(po)["reference"], "PO0001")
