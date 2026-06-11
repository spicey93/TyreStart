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

    def first_nominal(self):
        return nominals.get_all()[0]["id"]
