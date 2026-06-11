# Design & Style Guide

Conventions established while building the Suppliers app. **Follow these for all new
screens and features** so the app stays consistent. When a new pattern is needed,
add it here.

## Toolkit & theming
- **Tkinter with `ttk` (themed) widgets** for everything user-facing — `ttk.Frame`,
  `ttk.Label`, `ttk.Entry`, `ttk.Button`, `ttk.Treeview`, `ttk.Combobox`.
  Use classic `tk` only where `ttk` has no equivalent (e.g. `tk.Menu`, `tk.StringVar`).
- **Font:** `("Segoe UI", ...)`. Page titles are `("Segoe UI", 20, "bold")`.
- No custom colors yet — we rely on the default ttk theme. If we introduce a palette
  later, centralize it (don't hardcode colors per widget).

## App structure
- One window: a single `App(tk.Tk)` subclass.
- **One content area** (`self.container`, a `ttk.Frame(padding=20)`). Each screen is a
  `show_<name>()` method that calls `self._clear_container()` and rebuilds the view.
  Don't open secondary windows for primary navigation. **Exception:** a focused,
  self-contained sub-task may use a modal `tk.Toplevel` (e.g. the **Product Allocation**
  window for building a basket, and its quantity/cost dialog). Modal dialogs use
  `transient(parent)` + `grab_set()` + `parent.wait_window(dialog)` and return a value;
  a non-modal builder window hands its result back via an `on_submit(items)` callback.
- Track the active screen in `self.current_view` (used to scope shortcuts).
- **One central database** (`app.db`) holds every table. `database.py` owns the file
  path and the shared `get_connection()`; `database.init_db()` creates all tables at
  startup.
- **One data-access module per entity** (`suppliers.py`, `products.py`, `purchases.py`,
  `payments.py`, `nominals.py`, `services.py`, `customers.py`, `sales.py`, `receipts.py`). Each imports `get_connection` from `database.py`,
  exposes a `create_table()`, and keeps **all of that entity's SQL**. The UI calls
  functions like `db.get_all_suppliers()` and never writes SQL inline. The data layer
  raises domain errors (e.g. `DuplicateNameError`) instead of leaking `sqlite3` errors.
- **Foreign keys are ON** (`get_connection()` sets `PRAGMA foreign_keys = ON`). Money is
  stored as `REAL` and formatted to 2dp on display (`f"{x:,.2f}"`); dates as `DD/MM/YY`
  text, defaulted to today on new records.
- **VAT**: cost prices are stored **net**; each purchase line carries a `vat_rate`
  (percent, default 20). Line gross = `qty*cost*(1+rate/100)`. Totals are reported as
  **Net / VAT / Gross**; supplier balances and invoice outstanding use **gross** (what you
  owe). Standard rates live in `purchases.VAT_RATES` (20/5/0); the UI labels them in
  `VAT_RATE_OPTIONS`.
- **Never run blanket `DELETE`/`DROP` against `app.db` for tests or cleanup.** Verify the
  data layer against a throwaway DB (`database.DB_PATH = Path('._tmp.db')` *before*
  `init_db()`), or create rows and delete only the ids you created. UI build harnesses
  must be read-only.
- **Derived totals/balances are computed in SQL, never stored**: a purchase total is
  `SUM(qty*cost)` over its lines; **product stock = invoiced purchase qty − sold qty**
  (sales with status `Sale`; purchase Orders and sale Quotes don't count); a supplier
  balance is `Σ invoices − Σ payments`. Keep these as functions in the owning module
  (e.g. `products.STOCK_EXPR` / `product_stock`) so every screen agrees.
- **Mixed line items**: a sale line is a product OR a service — `sale_items` has
  `item_type` ('product'/'service') plus nullable `product_id`/`service_id`, a snapshot
  `description`, and net `unit_price` + `vat_rate`. The purchase line-item dialog/window
  is reused for the product side (`open_product_allocation(on_submit, price_label=...)`);
  services are added one at a time via `open_service_picker` (defaults price to the
  service's retail price). Status (Quote/Sale) mirrors purchases' Order/Invoice.
- **Bulk imports** (e.g. a CSV catalogue) live in the entity module as an
  `import_from_csv(path, replace=True)` function — replace-on-reload so re-running is
  idempotent. Map source columns explicitly (skip junk/constant columns).

## Navigation & menu bar
- `Home` is a flat command (`Home [F1]` — top-level items don't render `accelerator=`,
  so the shortcut goes in the label text).
- Each **section** (Suppliers / Products / Purchases / Services / Customers / Sales) is a
  menubar **command** (not a native cascade) labelled with its F-key (`Suppliers [F2]`).
  Clicking it — or pressing its F-key — opens a custom dropdown.
- **Custom dropdown, not a native menu.** `_open_section(key)` shows an in-window overlay
  (a placed `tk.Frame` + `Listbox`) under the menubar, highlights the first item, and
  focuses it; navigate with **arrows + Enter** (Escape closes). It's an in-window overlay
  (not a `Toplevel`/`tk_popup`) for two reasons: native popups run a **modal loop** that
  swallows the next F-key (forcing an Escape to switch), and `overrideredirect` windows
  take keyboard focus unreliably on Windows. Because the overlay stays in Tk's event loop,
  **pressing another F-key while one is open switches straight to it** (`bind_all` fires
  from the focused listbox). `_clear_container` closes any open overlay on view switch.
- The single source of truth for section items is `_sections()` → `{key: (x_offset,
  [(label, command), …])}`. No per-item accelerators, no separate `Ctrl+N`.
- **No "+ New" buttons in page headers** — creation lives in the menu dropdown.

## Page header pattern
Every list/detail screen starts with a header row: **title on the left, primary action
button on the right**, in a `ttk.Frame(fill="x")`.

```python
header = ttk.Frame(self.container)
header.pack(fill="x", pady=(0, 10))
ttk.Label(header, text="Suppliers", font=("Segoe UI", 20, "bold")).pack(side="left")
ttk.Button(header, text="+ New Supplier", command=self.show_create_supplier).pack(side="right")
```
- Primary "create" buttons read **`+ New <Thing>`**.

## Forms (create / edit share one view)
- One method handles both create and edit (`show_supplier_form(supplier=None)`); the
  title switches between `Create <Thing>` / `Edit <Thing>` and fields pre-fill when editing.
- **Header/detail fields go in a bordered `ttk.LabelFrame(text="<Thing> Details", padding=12)`**
  packed `anchor="w", fill="x"` — e.g. *Sale Details*, *Purchase Details*, *Payment
  Details*, *Receipt Details*, *Product Details*, *Service Details*. Documents with four-ish
  header fields use a **two-column** grid inside it: the primary picker + status on the left
  (columns 0/1), reference/date (and amount) on the right (columns 2/3, label `padx=(30, 10)`),
  rows on `pady=6`. Tabbed entity forms (suppliers, customers) keep their fields on the
  notebook's `Details` tab, which is itself the bordered container.
- Layout: `ttk.Label` + `ttk.Entry` pairs on a grid — label in column 0
  (`sticky="w"`, `padx=(0, 10)`), entry in column 1, `pady=5`.
- **Save** button below the form, `anchor="w"`, `pady=(20, 0)`.
- Validation & feedback via `messagebox`: `showwarning` for missing required input,
  `showerror` for conflicts (e.g. duplicate name), `showinfo` on success. After a
  successful save, return to the list view.

## Tabbed forms
- Entity edit forms (suppliers, customers) use a `ttk.Notebook`. After
  `_register_form`, call `self._bind_tab_shortcuts(notebook)`: it binds
  **Ctrl+1 / Ctrl+2 / …** to the tabs, **appends the shortcut to each tab label**
  (e.g. `Details (Ctrl+1)`), and on every tab change **focuses the first item** of the
  shown tab — the first row of its table if it has one, else its first entry.
- **List-style tabs get a search/filter bar** built with `self._searchable_table(parent,
  columns, headings, rows, cells, …)` (a `Search:` entry + `Filter:` column combo + the
  Treeview). Pass `iid=`/`on_open=`/`on_delete=` to make rows actionable. Its search
  widgets are tagged `_ignore_dirty` so typing in them never marks the edit form dirty.

## Tables (lists)
- `ttk.Treeview(show="headings")`. **Set each row's `iid` to the record's DB id** so
  selections map straight back to the database.
- Below the table, a single **status `ttk.Label`** for empty / "no matches" messages
  (don't use a popup for an empty list).
- Destructive actions **confirm first** (`messagebox.askyesno`) before deleting.

## Large datasets (tens of thousands of rows)
- **Never load the whole table into the Treeview.** Search/filter in SQL and **cap the
  results** (`LIMIT`, e.g. 200). Default the view to the first page.
- The status label reports the cap honestly: *"Showing first 200 of 6,160 matches —
  narrow your search to see more."* (Never silently truncate.)
- Give the table a vertical `ttk.Scrollbar` (wrap tree + scrollbar in their own frame).
- Records that aren't user-editable get a **read-only detail view** (a labelled grid +
  a `Back to <List>` button) instead of the create/edit form.

## Derived data
- Computed fields (e.g. a Stock Code parsed/assembled from other columns) are produced
  **once at import time** and stored in their own column, so lists can show and search
  them without recomputing. Keep the parsing/formatting logic in the entity module.
- *Live* derived figures that change with other data (stock, balances, invoice totals)
  are computed **on read in SQL** (see App structure), not stored.

## Forms with line items (parent + children)
For a record that owns a list of sub-rows (e.g. a Purchase with product lines):
- Header fields at the top (entity picker, status, reference, date) on a grid.
- An **add-line strip**: a product **search box** (`query_products`, capped) → results
  `Combobox` → quantity + cost entries → **Add**. Don't load a huge table into a combobox.
- A **lines `Treeview`** (`iid` = list index) with a **Remove line** button and a running
  **Total** label; keep the working list in a Python `list` and rebuild the tree on change.
- Persist the parent + replace all child rows in one data-layer call
  (`create_purchase`/`update_purchase`).

## Pickers
- **Small/medium option set from the DB** (suppliers, nominal accounts): an
  `AutocompleteCombobox` (or readonly `Combobox`) keyed by a display label → map the label
  back to the row id on save.
- **Huge table** (products, 80k+): never a combobox — use a search box + capped results.
- **Dependent dropdowns**: narrow a large option list by its parents to keep it usable —
  e.g. the model picker is scoped to the chosen brand + size (`get_models(brand, size)`),
  refreshed when the brand changes or a search runs.

## Search shorthands & filters
- Products support a **size+speed stock-code shorthand**: `2055516V` = size 205/55R16
  (matched as a `stock_code` prefix) + speed rating `V` (matched in the description). See
  `products.search_products_adv` / `SIZE_SPEED_RE`.
- Lists that track stock offer an **In stock** filter (`Yes`/`No`/`All`, default `Yes`)
  via `query_products(in_stock=...)`.

## Inline cell editing & fast entry
- **Double-click a Treeview cell to edit it** (e.g. Qty/Cost on purchase lines): overlay
  a `ttk.Entry` at `tree.bbox(rowid, column)`, commit on `<Return>`/`<FocusOut>`, cancel
  on `<Escape>`, then rebuild the row. Restrict to the editable columns by `identify_column`.
- **Rapid repeat entry** (Product Allocation): after adding to the basket, clear the search
  inputs and refocus the search box; pressing **Enter on an empty search with a non-empty
  basket submits** — so a whole basket can be built without the mouse.

## Account / balance section
A record with money movements shows an **Account** `ttk.LabelFrame` on its edit screen:
the **Balance** plus allocation actions. This is symmetric across the two sides:
- **Supplier** (purchases side): balance = `Σ invoices − Σ payments`; buttons **Make
  Payment** / **View Payments** / **View Purchases**; payments draw *from* a nominal
  account and allocate to outstanding **invoices**.
- **Customer** (sales side): balance = `Σ Sales − Σ receipts` (Quotes excluded); buttons
  **Record Receipt** / **View Receipts** / **View Sales**; receipts deposit *to* a nominal
  account and allocate to outstanding **sales**.
Allocation uses a small grid (reference/date/total/outstanding + an amount entry per row);
the total is the sum of allocations, shown live via `StringVar.trace_add`. An invoice/sale
with allocations against it can't be deleted (FK), surfaced as a friendly error.

## Search / filter bar
- A `ttk.Frame(fill="x")` on a grid above the table: `Search:` label, entry, `Filter:`
  combobox, then **Search** and **Clear** buttons.
- The **search entry expands to fill horizontal space**; keep trailing controls flush
  right: `search_frame.columnconfigure(<entry_col>, weight=1)` and grid the entry
  `sticky="ew"` (no fixed `width`).
- **Long option lists** (e.g. a Brand picker with 100+ values) use the
  `AutocompleteCombobox` widget (in main.py): editable, autocompletes and narrows its
  dropdown as you type. An empty box means "no filter / all". Free-text search and the
  dropdown filter **combine** (text AND brand) in one SQL query.

## Keyboard behavior (first-class, not an afterthought)
- **Every view auto-focuses its first interactive widget on load.** `_clear_container()`
  schedules `self.after_idle(self._focus_first_input)`, which (once the new view is built)
  focuses the first entry/combobox, else the first table, else the first button. So no
  screen needs its own `focus_set()` — it's universal. Toplevel dialogs are separate and
  still set their own initial focus.
- **Enter activates the focused button** app-wide: `bind_class("TButton", "<Return>", ...)`.
- Global navigation shortcuts via `bind_all` (e.g. `F1` Home, `F2` Suppliers, `F3`
  Products, `F4` Purchases).
- **`Ctrl+N` is context-aware**: `_new_for_current_view()` opens the right create form
  for the current list (`suppliers`→supplier, `products`→product, `purchases`→purchase),
  keyed off `self.current_view`.
- **Dates** are `DD/MM/YY` text (`datetime.date.today().strftime("%d/%m/%y")`), defaulted
  to today on new records. Because this isn't sortable as text, **order lists by `id`**,
  not by the date column.
- **Search → results flow:** Enter in the search box runs the search and, if there are
  matches, moves focus to the table and selects the first row (so arrow keys navigate).
  **Enter on a table row opens that record** (same as double-click).
- When an action can't proceed (e.g. nothing selected), tell the user via `messagebox`
  rather than failing silently.

## Naming & wording
- Buttons: `Search`, `Clear`, `Edit`, `Delete`, `Save`.
- Uniqueness checks are **case-insensitive** (e.g. supplier name, service code) via a
  `UNIQUE INDEX ... COLLATE NOCASE` + a domain error (`DuplicateNameError` /
  `DuplicateCodeError`) caught in the form. For an optional unique field, store blanks as
  `NULL` so multiple un-coded rows don't clash (SQLite treats NULLs as distinct).
