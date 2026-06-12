# Stock System

A single-user desktop application for a tyre business: manage suppliers,
products, purchases, sales, customers, receipts, payments and pricing rules, on
top of a real double-entry general ledger that produces UK VAT returns, a Profit
& Loss and a Balance Sheet.

Built with Python's standard library only — `tkinter` for the UI and `sqlite3`
for storage. There are no third-party dependencies.

## Bookkeeping & accounting

Sales invoices, purchase invoices, credit notes, receipts and payments
automatically post a balanced double-entry journal (in whole pence) as they are
saved, against a proper chart of accounts (Sales, COGS, Stock, Debtors/Creditors
control, Output/Input VAT, Bank/Cash, equity and overheads). From that ledger the
app produces:

- a **VAT Return** (the 9 boxes, accrual basis) with a period file/lock lifecycle;
- a **Profit & Loss** and **Balance Sheet**;
- a **Trial Balance** and a browsable **Chart of Accounts**.

Posting is immutable — editing a document reverses and re-posts; once a VAT period
is marked filed its journals are locked and corrections fall into the open period.
Filing to HMRC (Making Tax Digital) is done outside the app via Xero/QuickBooks or
a bridging tool; the data model is kept integration-ready (named tax codes,
external-id fields).

## Requirements

- **Python 3.12+** with `tkinter` (included in the standard Windows/macOS
  installers; on some Linux distros install `python3-tk`).
- No `pip install` step — the app uses only the standard library.

## Running the app

From the repository root:

```sh
python main.py
```

All data is stored in a single SQLite file, `app.db`, in the repository root.
It is created automatically on first run and is **not** tracked in git.

## Running the tests

```sh
python -m unittest discover -s tests -t .
```

Tests never touch the real `app.db`: the `DatabaseTestCase` harness
(`tests/support.py`) points the database at a fresh temporary file per test.

## Project layout

```
main.py            Entry point. Composes the UI mixins into one App window.
core/              Data access and domain logic (no UI dependencies).
  database.py        Central SQLite connection + table creation + migrations.
  money.py           Pure line/document totals in whole pence (net / VAT / gross).
  accounts.py        Chart of accounts (general-ledger account list).
  journal.py         Append-only double-entry ledger (balanced, immutable).
  posting.py         Posts a balanced journal from each source document.
  vat.py taxcodes.py VAT return (9 boxes) + named tax codes.
  reports.py         Trial balance, profit & loss, balance sheet.
  dbmaint.py migrations.py migrate_money.py migrate_dates.py   Backups + migrations.
  pricing.py         Pricing-rule formulas and rule selection.
  suppliers.py products.py purchases.py payments.py
  nominals.py services.py customers.py sales.py receipts.py
ui/                Tkinter screens, one module per entity.
  common.py          Shared widgets (autocomplete combobox, sortable tables).
  reports.py accounts.py   Reports [F9] and Chart of Accounts [F8] screens.
  <entity>.py        Screen mixins added to App (suppliers, products, …).
tests/             Unit tests (standard-library unittest).
DESIGN.md          UI design/style guide for new screens.
```

### Architecture notes

- **`core/` has no UI imports.** It is the layer a future API/service would call
  directly; the money and pricing rules live here as pure, tested functions.
- **The UI is split into mixins.** `App` (in `main.py`) inherits from one mixin
  per entity (`ui/sales.py` → `SalesMixin`, etc.) plus shared navigation and
  form-shortcut infrastructure.
- **Money is calculated in one place.** `core/money.py` is the single source of
  truth for line and document totals, computed in whole pence so VAT rounds once
  per line and totals tie exactly to the ledger; the persisted SQL aggregates are
  kept in step with it (covered by tests).
- **The ledger is derived, posted and authoritative.** Source documents post a
  balanced journal via `core/posting.py`; reports and the VAT return read the
  journal, so the figures always reconcile to the subledger balances. Schema and
  data migrations are versioned and back up `app.db` before they run.
