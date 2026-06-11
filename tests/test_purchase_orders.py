"""Tests for purchase orders: auto PO numbering and the receive -> invoice flow."""
from core import purchases
from tests.support import DatabaseTestCase


def line(product_id, quantity, cost_price=50.0, vat_rate=20.0):
    return {"product_id": product_id, "quantity": quantity,
            "cost_price": cost_price, "vat_rate": vat_rate}


class PoNumberingTests(DatabaseTestCase):
    def setUp(self):
        super().setUp()
        self.supplier = self.make_supplier()
        self.product = self.make_product()

    def test_orders_auto_number_sequentially(self):
        a = purchases.create_purchase(self.supplier, "Order", "", "01/06/26",
                                      [line(self.product, 1)])
        b = purchases.create_purchase(self.supplier, "Order", "", "01/06/26",
                                      [line(self.product, 1)])
        self.assertEqual(purchases.get_purchase(a)["reference"], "PO0001")
        self.assertEqual(purchases.get_purchase(b)["reference"], "PO0002")

    def test_invoice_keeps_manual_reference(self):
        inv = purchases.create_purchase(self.supplier, "Invoice", "SUP-INV-7",
                                        "01/06/26", [line(self.product, 1)])
        self.assertEqual(purchases.get_purchase(inv)["reference"], "SUP-INV-7")
        # An invoice's manual ref must not advance the PO sequence.
        po = purchases.create_purchase(self.supplier, "Order", "", "01/06/26",
                                       [line(self.product, 1)])
        self.assertEqual(purchases.get_purchase(po)["reference"], "PO0001")


class ReceiveTests(DatabaseTestCase):
    def setUp(self):
        super().setUp()
        self.supplier = self.make_supplier()
        self.p1 = self.make_product("Tyre A")
        self.p2 = self.make_product("Tyre B")
        self.po = purchases.create_purchase(
            self.supplier, "Order", "", "01/06/26",
            [line(self.p1, 4), line(self.p2, 2)])

    def test_receive_raises_linked_invoice_with_received_quantities(self):
        items = purchases.get_purchase_items(self.po)
        received = {items[0]["id"]: 4, items[1]["id"]: 1}  # partial on the 2nd line
        inv = purchases.receive_purchase(self.po, received, "02/06/26")

        inv_row = purchases.get_purchase(inv)
        self.assertEqual(inv_row["status"], "Invoice")
        self.assertEqual(inv_row["po_reference"], "PO0001")
        self.assertEqual(inv_row["reference"], "")  # supplier invoice no. entered later
        self.assertEqual(sorted(it["quantity"] for it in purchases.get_purchase_items(inv)),
                         [1, 4])

    def test_receive_marks_po_and_records_line_quantities(self):
        items = purchases.get_purchase_items(self.po)
        purchases.receive_purchase(self.po, {items[0]["id"]: 4, items[1]["id"]: 1}, "02/06/26")
        self.assertEqual(purchases.get_purchase(self.po)["received"], 1)
        self.assertEqual(sorted(it["received"] for it in purchases.get_purchase_items(self.po)),
                         [1, 4])

    def test_receiving_nothing_raises_no_invoice(self):
        items = purchases.get_purchase_items(self.po)
        result = purchases.receive_purchase(
            self.po, {items[0]["id"]: 0, items[1]["id"]: 0}, "02/06/26")
        self.assertIsNone(result)
