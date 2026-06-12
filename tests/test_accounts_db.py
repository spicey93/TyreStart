"""Tests for the chart of accounts: seed integrity, system-tag lookups, VAT
control accounts, normal sides, and the nominal->chart mapping."""
from core import accounts, nominals
from tests.support import DatabaseTestCase


class ChartSeedTests(DatabaseTestCase):
    def test_seeded_and_unique_codes(self):
        rows = accounts.get_all()
        self.assertTrue(rows)
        codes = [r["code"] for r in rows]
        self.assertEqual(len(codes), len(set(codes)))  # unique
        # Key control/posting accounts exist.
        for code in ("4000", "5000", "1001", "1100", "2100", "2200", "2201", "2004"):
            self.assertIn(code, codes)

    def test_system_tags_resolve(self):
        for tag in ("sales", "sales_services", "cogs", "stock", "debtors",
                    "creditors", "vat_output", "vat_input", "bank", "cash",
                    "card_clearing", "capital", "retained_earnings"):
            self.assertIsInstance(accounts.system_id(tag), int)

    def test_unknown_tag_raises(self):
        with self.assertRaises(KeyError):
            accounts.system_id("does_not_exist")

    def test_exactly_two_vat_control_accounts(self):
        rows = [r for r in accounts.get_all() if r["vat_control"]]
        kinds = sorted(r["vat_control"] for r in rows)
        self.assertEqual(kinds, ["input", "output"])

    def test_normal_sides(self):
        # Assets & expenses are debit-normal; the rest credit-normal.
        self.assertEqual(accounts.get(accounts.system_id("stock"))["normal_side"], "debit")
        self.assertEqual(accounts.get(accounts.system_id("cogs"))["normal_side"], "debit")
        self.assertEqual(accounts.get(accounts.system_id("sales"))["normal_side"], "credit")
        self.assertEqual(accounts.get(accounts.system_id("creditors"))["normal_side"], "credit")
        self.assertEqual(accounts.get(accounts.system_id("capital"))["normal_side"], "credit")

    def test_input_vat_is_asset_output_vat_is_liability(self):
        self.assertEqual(accounts.get(accounts.system_id("vat_input"))["account_type"], "asset")
        self.assertEqual(accounts.get(accounts.system_id("vat_output"))["account_type"], "liability")

    def test_bank_accounts_match_legacy_nominals(self):
        bank_codes = {r["code"] for r in accounts.get_all() if r["is_bank"]}
        self.assertEqual(bank_codes, {"1200", "1240", "2004"})

    def test_id_for_nominal_maps_by_code(self):
        # Every seeded nominal maps to a chart account with the same code.
        for n in nominals.get_all():
            acc_id = accounts.id_for_nominal(n["id"])
            self.assertIsNotNone(acc_id, f"nominal {n['code']} did not map")
            self.assertEqual(accounts.get(acc_id)["code"], n["code"])

    def test_seed_is_idempotent(self):
        before = len(accounts.get_all(active_only=False))
        accounts.create_table()  # should not re-seed
        after = len(accounts.get_all(active_only=False))
        self.assertEqual(before, after)
