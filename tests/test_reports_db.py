"""Tests for the financial statements: trial balance nets to zero, P&L net equals
the change in equity, and the balance sheet balances (assets = liab + equity)."""
from core import reports, sales, purchases, receipts, payments
from tests.support import DatabaseTestCase


class ReportsTestCase(DatabaseTestCase):
    def setUp(self):
        super().setUp()
        self.supplier = self.make_supplier()
        self.customer = self.make_customer()
        self.prod = self.make_product()
        self.nominal = self.first_nominal()
        # Buy 10 @ £30 +20% (stock); sell 4 @ £50 +20%; receive £120; pay £180.
        purchases.create_purchase(self.supplier, "Invoice", "PINV", "2026-01-05", [
            {"product_id": self.prod, "quantity": 10, "cost_price": 30.0, "vat_rate": 20.0}])
        self.sale = sales.create_sale(self.customer, "Invoice", "2026-02-01", [
            {"item_type": "product", "product_id": self.prod, "service_id": None,
             "description": "", "quantity": 4, "unit_price": 50.0, "vat_rate": 20.0}])
        receipts.create_receipt(self.customer, self.nominal, "BACS", "2026-02-10",
                                [{"sale_id": self.sale, "amount": 120.0}])


class TrialBalanceTests(ReportsTestCase):
    def test_debits_equal_credits(self):
        tb = reports.trial_balance()
        self.assertEqual(tb["total_debit"], tb["total_credit"])
        self.assertGreater(tb["total_debit"], 0)


class ProfitAndLossTests(ReportsTestCase):
    def test_net_profit_is_sales_less_cogs(self):
        pl = reports.profit_and_loss("2026-01-01", "2026-12-31")
        # Revenue 4 x £50 = 200.00; COGS 4 x £30 = 120.00; net profit 80.00.
        self.assertEqual(pl["total_income"], 20000)
        self.assertEqual(pl["total_expense"], 12000)
        self.assertEqual(pl["net_profit"], 8000)

    def test_period_excludes_outside_dates(self):
        pl = reports.profit_and_loss("2026-03-01", "2026-12-31")
        self.assertEqual(pl["net_profit"], 0)   # the sale is dated 2026-02-01


class BalanceSheetTests(ReportsTestCase):
    def test_balances(self):
        bs = reports.balance_sheet("2026-12-31")
        self.assertEqual(bs["total_assets"], bs["total_liabilities_equity"])

    def test_retained_profit_equals_pl(self):
        bs = reports.balance_sheet("2026-12-31")
        pl = reports.profit_and_loss(None, "2026-12-31")
        self.assertEqual(bs["retained_profit"], pl["net_profit"])

    def test_balances_after_supplier_payment(self):
        payments.create_payment(self.supplier, self.nominal, "BACS", "2026-02-15", 180.0,
                                [{"purchase_id": 1, "amount": 180.0}])
        bs = reports.balance_sheet("2026-12-31")
        self.assertEqual(bs["total_assets"], bs["total_liabilities_equity"])
