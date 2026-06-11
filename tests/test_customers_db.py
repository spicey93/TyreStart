"""Tests for the customer fields (address/postcode) and the legacy migration."""
from core import customers
from core.database import get_connection
from tests.support import DatabaseTestCase


class CustomerFieldsTests(DatabaseTestCase):
    def test_address_and_postcode_round_trip(self):
        cid = customers.add_customer(
            "Acme", address="1 High St", postcode="AB1 2CD", email="a@b.c", phone="123")
        c = customers.get_customer(cid)
        self.assertEqual(c["address"], "1 High St")
        self.assertEqual(c["postcode"], "AB1 2CD")

        customers.update_customer(cid, "Acme", "C00001", "2 Low St", "ZZ9 9ZZ", "x@y.z", "999")
        c = customers.get_customer(cid)
        self.assertEqual(c["address"], "2 Low St")
        self.assertEqual(c["postcode"], "ZZ9 9ZZ")

    def test_migration_adds_columns_to_legacy_table(self):
        # Simulate a pre-change database: a customers table with the old `contact`
        # column and no address/postcode, holding one row.
        with get_connection() as conn:
            conn.execute("DROP TABLE customers")
            conn.execute(
                "CREATE TABLE customers (id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "name TEXT NOT NULL, account_number TEXT, contact TEXT, "
                "email TEXT, phone TEXT)"
            )
            conn.execute("INSERT INTO customers (name, contact) VALUES ('Legacy', 'Bob')")

        customers.create_table()  # runs the migration

        with get_connection() as conn:
            cols = {r["name"] for r in conn.execute("PRAGMA table_info(customers)")}
        self.assertIn("address", cols)
        self.assertIn("postcode", cols)

        # The legacy row is still readable through the new SELECT (new cols NULL).
        row = customers.get_customer(1)
        self.assertEqual(row["name"], "Legacy")
        self.assertIsNone(row["address"])
        self.assertIsNone(row["postcode"])
