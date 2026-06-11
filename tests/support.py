"""Test support: a base case that runs against a throwaway SQLite database.

Never touches the real app.db. It points database.DB_PATH at a fresh temp file
for the duration of each test (get_connection reads DB_PATH at call time, so all
data-access modules follow), creates every table, then removes the file.
"""
import gc
import os
import tempfile
import unittest
from pathlib import Path

from core import database
from core import suppliers, customers, products, nominals
from core import sales, purchases, payments, receipts, services


class DatabaseTestCase(unittest.TestCase):
    def setUp(self):
        self._orig_db_path = database.DB_PATH
        fd, name = tempfile.mkstemp(suffix=".db", prefix="test_app_")
        os.close(fd)
        self._tmp_db = Path(name)
        database.DB_PATH = self._tmp_db
        database.init_db()

    def tearDown(self):
        database.DB_PATH = self._orig_db_path
        gc.collect()  # let lingering sqlite connections close so the file unlocks
        try:
            self._tmp_db.unlink()
        except OSError:
            pass  # Windows may still hold the handle; the OS cleans temp later

    # --- fixture factories (each returns the new row id) ---
    def make_supplier(self, name="Supplier"):
        return suppliers.add_supplier(name)

    def make_customer(self, name="Customer"):
        return customers.add_customer(name)

    def make_product(self, description="205/55R16 Test Tyre"):
        return products.create_product(description)

    def make_service(self, name="Fitting", code=None, cost=5.0, retail=10.0):
        return services.create_service(code, name, cost, retail)

    def first_nominal(self):
        return nominals.get_all()[0]["id"]

    # --- document fixtures (sensible defaults; override as needed) ---
    def make_sale_invoice(self, customer_id=None, items=None, date="01/01/26",
                          status="Invoice"):
        """Create a sale (default: one 4×£50 +20% product line) and return its id."""
        if customer_id is None:
            customer_id = self.make_customer()
        if items is None:
            pid = self.make_product()
            items = [{"item_type": "product", "product_id": pid, "service_id": None,
                      "description": "", "quantity": 4, "unit_price": 50.0,
                      "vat_rate": 20.0}]
        return sales.create_sale(customer_id, status, date, items)

    def make_purchase_invoice(self, supplier_id=None, items=None, date="01/01/26",
                              reference="INV1", status="Invoice"):
        """Create a purchase (default: one 4×£30 +20% product line) and return its id."""
        if supplier_id is None:
            supplier_id = self.make_supplier()
        if items is None:
            pid = self.make_product()
            items = [{"product_id": pid, "quantity": 4, "received": 0,
                      "cost_price": 30.0, "vat_rate": 20.0}]
        return purchases.create_purchase(supplier_id, status, reference, date, items)

    def make_payment(self, supplier_id, amount, account_id=None, date="01/01/26",
                     allocations=None):
        """Record a supplier payment and return its id."""
        if account_id is None:
            account_id = self.first_nominal()
        return payments.create_payment(supplier_id, account_id, "BACS", date,
                                        amount, allocations)

    def make_receipt(self, customer_id, allocations, account_id=None, date="01/01/26"):
        """Record a customer receipt (amount = sum of allocations) and return its id."""
        if account_id is None:
            account_id = self.first_nominal()
        return receipts.create_receipt(customer_id, account_id, "BACS", date,
                                       allocations)
