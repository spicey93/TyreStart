# Design & Style Guide

Conventions established while building the Suppliers app. **Follow these for all new
screens and features** so the app stays consistent. When a new pattern is needed,
add it here.

## Toolkit & theming
- **Tkinter with `ttk` (themed) widgets** for everything user-facing — `ttk.Frame`,
  `ttk.Label`, `ttk.Entry`, `ttk.Button`, `ttk.Treeview`, `ttk.Combobox`.
  Use classic `tk` only where `ttk` has no equivalent (e.g. `tk.Menu`, `tk.StringVar`).
- **Font:** `("Consolas", ...)` — a monospace face for the retro terminal look. Page
  titles are `("Consolas", 20, "bold")`.
- **Retro high-contrast theme.** The palette and all ttk styling live in `ui/theme.py`
  (a black page, bright yellow text, yellow inverted chunky buttons — high contrast).
  Whatever widget currently has keyboard focus is outlined in **crisp white**
  (`theme.FOCUS`) against the soft-grey default border — entries, comboboxes, buttons
  and tables alike — so it's always obvious where you are. `theme.apply(self)`
  runs once in `App.__init__`, before any view is built. **Never hardcode hex colors per
  widget** — pull a named color from `theme` (e.g. `theme.FG`, `theme.FG_MUTED`,
  `theme.BORDER`) or use a named ttk style. Hint/secondary text uses `theme.FG_MUTED`.

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
- **Custom in-window menu bar, not a native `tk.Menu`.** `_build_menu` builds a themed
  `tk.Frame` of clickable labels packed at the top of the window (on Windows a native
  menubar is OS-drawn and ignores the theme's colors). Each label highlights amber on
  hover and carries its F-key in the text.
- `Home` is a flat command (`Home [F1]` — the shortcut goes in the label text).
- Each **section** (Suppliers / Products / Purchases / Services / Customers / Sales) is a
  menubar label tagged with its F-key (`Suppliers [F2]`). Clicking it — or pressing its
  F-key — opens a custom dropdown, which places itself directly under that label.
- **Custom dropdown, not a native menu.** `_open_section(key)` shows an in-window overlay
  (a placed `tk.Frame` + `Listbox`) under the menubar, highlights the first item, and
  focuses it; navigate with **arrows + Enter** (Escape closes). It's an in-window overlay
  (not a `Toplevel`/`tk_popup`) for two reasons: native popups run a **modal loop** that
  swallows the next F-key (forcing an Escape to switch), and `overrideredirect` windows
  take keyboard focus unreliably on Windows. Because the overlay stays in Tk's event loop,
  **pressing another F-key while one is open switches straight to it** (`bind_all` fires
  from the focused listbox). `_clear_container` closes any open overlay on view switch.
- The single source of truth for section items is `_sections()` → `{key: [(label,
  command), …]}`. No per-item accelerators, no separate `Ctrl+N`.
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
- **`messagebox` is our themed `ui/dialogs.py`, not `tkinter.messagebox`.** Native
  message boxes are OS-drawn and ignore the theme, so each screen does
  `from ui import dialogs as messagebox`; the module mirrors the standard API
  (`showinfo`/`showwarning`/`showerror`/`askyesno`/`askyesnocancel`) and return values.

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
  Pass `search_first=True` for a large/secondary list: the table loads empty and lists
  rows only once a term is entered, and the tab opens focused in the search box (instead
  of highlighting the first row).
- **Date-filtered lists** use `self._make_date_filter(parent, on_change)` → `(frame,
  get_range)`: a Period dropdown (presets in `core/daterange.PERIODS`) plus Start/End
  boxes. Choosing a preset fills the boxes; editing a box switches to *Custom*.
  `get_range()` returns parsed `(start, end)` dates; filter rows with
  `daterange.in_range(row_date, start, end)`. Dates are `DD/MM/YY` text — parse via
  `daterange.parse`. The supplier Payments/Purchases tabs pair this with extra
  readonly filter combos (`_filter_combo`) for Method / Fully Allocated / Reconciled /
  Paid.

## Highlighting (focus & hover)
- The focused widget always gets a **crisp white outline** (entries, combos, tables,
  buttons — see `theme.FOCUS`). A table's selected row is **bright yellow when that
  table has focus** and **dim amber when it doesn't** (`SELECT_BG` vs `SELECT_DIM`), so
  it's clear both where you are and which table is live.
- **Every table highlights the row under the mouse** with a faint amber wash
  (`theme.ROW_HOVER`), wired centrally in `make_sortable` — no per-table code needed.

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
- A **lines `Treeview`** (`iid` = list index) and a running **Total** label; keep the
  working list in a Python `list` and rebuild the tree on change. Remove a line by
  **pressing Delete on it or setting its Qty to 0** (no Remove-line button). The purchase
  forms share one builder, `self._purchase_lines_editor(parent, editable=...)`.
- Persist the parent + replace all child rows in one data-layer call
  (`create_purchase`/`update_purchase`).

## Purchase documents (orders, invoices, credit notes)
- The Purchases menu has **All Purchases · New Purchase Order · New Purchase Invoice ·
  New Credit Note**. Each document type has its own form; `open_purchase(row)` routes an
  existing purchase to the right one by `status` (Order / Invoice / Credit Note).
- Each purchase form has an **Actions panel** — a bordered `ttk.LabelFrame(text="Actions")`
  packed directly under the Details panel and above the lines table — holding that
  document's buttons (**Add Product** always; plus **Receive / Deliver** on an editable PO,
  or **Create Credit Note** on a saved invoice). The lines editor no longer renders its own
  Add Product button; it exposes an `add` callback the Actions panel wires up. Keep
  document-level actions here rather than loose at the bottom of the page.
- **Credit Notes** (supplier returns/corrections) have **two entry points**: *New Credit
  Note* from the menu opens a **blank** note where you **Add Product** from stock to return;
  or a saved invoice's **Create Credit Note** button (`show_credit_note_form(from_invoice=…)`)
  **seeds** the note with the invoice's lines and links it (`po_reference` = invoice number).
  The number is auto-generated (`CN0001`, via `next_reference`); there are free-text
  `credit_reference` / `return_reference` fields. Each line shows Stock Code / Description /
  Invoiced (blank for stock-added lines) / **Returned** (editable) / Unit Cost / Net Total —
  the single **Returned** qty drives the net total, the **stock-out** and the **balance
  reduction** (we deliberately don't separate "credited" money from "returned" goods).
  A credit note subtracts its quantities from stock (`STOCK_EXPR` / `product_stock` sign by
  status) and its gross from the supplier balance (`supplier_balance` =
  invoices − credit notes − payments). It isn't payment-allocatable and doesn't affect
  average cost (invoice-based). Products added from stock default their unit cost to the
  product's average cost. (A separate physical *Return Note* could be added later if
  returns-awaiting-credit ever needs tracking; today one document does both.)
- **Purchase Orders** capture supplier + date only and get an **auto PO number**
  (`PO0001`, via `purchases.next_po_number`) stored in `reference`; status isn't shown.
- **Receiving**: an Order's *Receive / Deliver* button opens a modal defaulting every
  line to its full ordered qty (editable down). Confirming records `received` per line,
  marks the PO `received` (locking it read-only), and **raises a linked Purchase Invoice**
  for the received quantities — `purchases.receive_purchase(po_id, {item_id: qty}, date)`.
  Stock comes in via that invoice (orders don't move stock), matching `product_stock`.
- **Purchase Invoices** keep a **manually entered** invoice number (`reference`, the
  supplier's number) plus an optional **PO Number** (`po_reference`) that links back to the
  order. A raised invoice opens with the PO number pre-filled and the invoice-number box
  focused for entry.

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
- **The app opens windowed.** `F11` toggles full screen; `Ctrl+Q` quits (both confirm
  via `_quit`).
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
