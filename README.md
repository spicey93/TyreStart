# Stock System

A single-user desktop application for a tyre business: manage suppliers,
products, purchases, sales, customers, receipts, payments and pricing rules,
with a simple double-entry-style ledger of nominal accounts.

Built with Python's standard library only — `tkinter` for the UI and `sqlite3`
for storage. There are no third-party dependencies.

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
  database.py        Central SQLite connection + table creation.
  money.py           Pure line/document totals (net / VAT / gross).
  pricing.py         Pricing-rule formulas and rule selection.
  suppliers.py products.py purchases.py payments.py
  nominals.py services.py customers.py sales.py receipts.py
ui/                Tkinter screens, one module per entity.
  common.py          Shared widgets (autocomplete combobox, sortable tables).
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
  truth for line and document totals, used by every form's live totals; the
  persisted SQL aggregates are kept in step with it (covered by tests).
