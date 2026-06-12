"""Tests for opening balances: the entry balances to Capital Introduced, the
trial balance/balance sheet stay balanced, re-saving replaces the prior entry,
and opening figures combine correctly with posted transactions."""
from core import accounts, journal, opening, reports, payments, purchases, nominals
from tests.support import DatabaseTestCase

P = 100  # pounds -> pence


class OpeningBalanceTests(DatabaseTestCase):
    def ids(self):
        return {tag: accounts.system_id(tag)
                for tag in ("bank", "stock", "creditors", "debtors", "capital")}

    def test_balances_to_capital(self):
        a = self.ids()
        capital = opening.set_opening_balances("2026-01-01", {
            a["bank"]: 5000 * P, a["stock"]: 2000 * P, a["creditors"]: 1500 * P})
        # Net assets 7000 - 1500 = 5500 → Capital Introduced.
        self.assertEqual(capital, 5500 * P)
        d, c = journal.trial_balance_totals()
        self.assertEqual(d, c)
        # Capital account holds 5500 (credit-normal → negate net-debit).
        self.assertEqual(-journal.account_balance_pence(a["capital"]), 5500 * P)

    def test_balance_sheet_balances(self):
        a = self.ids()
        opening.set_opening_balances("2026-01-01", {
            a["bank"]: 5000 * P, a["stock"]: 2000 * P, a["creditors"]: 1500 * P})
        bs = reports.balance_sheet("2026-12-31")
        self.assertEqual(bs["total_assets"], bs["total_liabilities_equity"])
        self.assertEqual(bs["total_assets"], 7000 * P)        # bank + stock
        self.assertEqual(bs["total_liabilities"], 1500 * P)   # creditors
        self.assertEqual(bs["total_equity"], 5500 * P)        # capital

    def test_capital_from_bank_only(self):
        a = self.ids()
        capital = opening.set_opening_balances("2026-01-01", {a["bank"]: 5000 * P})
        self.assertEqual(capital, 5000 * P)
        self.assertEqual(journal.account_balance_pence(a["bank"]), 5000 * P)

    def test_get_round_trips(self):
        a = self.ids()
        opening.set_opening_balances("2026-01-01",
                                     {a["bank"]: 5000 * P, a["creditors"]: 1500 * P})
        got = opening.get_opening()
        self.assertEqual(got["date"], "2026-01-01")
        self.assertEqual(got["balances"][a["bank"]], 5000 * P)
        self.assertEqual(got["balances"][a["creditors"]], 1500 * P)
        self.assertEqual(got["balances"][a["capital"]], 3500 * P)   # 5000 - 1500

    def test_resave_replaces(self):
        a = self.ids()
        opening.set_opening_balances("2026-01-01", {a["bank"]: 5000 * P})
        opening.set_opening_balances("2026-01-01", {a["bank"]: 8000 * P})
        # Only the latest figure stands; GL still balances.
        self.assertEqual(journal.account_balance_pence(a["bank"]), 8000 * P)
        self.assertEqual(-journal.account_balance_pence(a["capital"]), 8000 * P)
        d, c = journal.trial_balance_totals()
        self.assertEqual(d, c)

    def test_opening_plus_payment(self):
        # Opening bank £5,000, then pay a supplier £150 → bank £4,850 (not negative).
        a = self.ids()
        opening.set_opening_balances("2026-01-01", {a["bank"]: 5000 * P})
        supplier = self.make_supplier()
        prod = self.make_product()
        purchases.create_purchase(supplier, "Invoice", "INV1", "2026-02-01", [
            {"product_id": prod, "quantity": 1, "cost_price": 125.0, "vat_rate": 20.0}])
        bank_nominal = next(n["id"] for n in nominals.get_all() if n["code"] == "2004")
        payments.create_payment(supplier, bank_nominal, "BACS", "2026-02-05", 150.0)
        self.assertEqual(journal.account_balance_pence(a["bank"]), 4850 * P)
        bs = reports.balance_sheet("2026-12-31")
        self.assertEqual(bs["total_assets"], bs["total_liabilities_equity"])
