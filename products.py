"""Products data-access layer.

All product SQL lives here. Uses the shared connection from the central
database (database.py), so products are stored in app.db alongside suppliers.

Product rows are bulk-loaded from products.csv via import_from_csv(). During
import we parse the tyre size out of the description and build a Stock Code.
"""

import csv
import datetime
import re

from database import get_connection

# Maps a source CSV column index -> the database column it populates.
# The CSV's first column (a constant "N") and its empty trailing column are
# intentionally skipped. The two unnamed image columns are wrapped in <html>.
CSV_TO_DB = [
    (1, "sync_status"),
    (2, "image_html"),
    (3, "logo_html"),
    (4, "description"),
    (5, "ean"),
    (6, "manufacturer_code"),
    (7, "brand"),
    (8, "model"),
    (9, "product_type"),
    (10, "vehicle_type"),
    (11, "rolling_resistance"),
    (12, "wet_grip"),
    (13, "noise_class"),
    (14, "noise_performance"),
    (15, "vehicle_class"),
    (16, "created_date"),
    (17, "updated_date"),
]

# Columns we derive at import time (not present in the CSV).
DERIVED_COLUMNS = ["width", "aspect_ratio", "rim", "stock_code"]

# Tyre size embedded in the description, e.g. "325/95R24" -> (325, 95, 24).
SIZE_RE = re.compile(r"(\d{2,3})\s*/\s*(\d{2,3})\s*R\s*(\d{2})")


def parse_size(description):
    """Pull (width, aspect_ratio, rim) out of a description, or ('', '', '')."""
    match = SIZE_RE.search(description or "")
    if not match:
        return "", "", ""
    return match.group(1), match.group(2), match.group(3)


def build_stock_code(width, aspect_ratio, rim, brand, manufacturer_code):
    """Stock Code = width + aspect ratio + rim + brand(first 2 letters) + mfr code.

    Parts are concatenated with no separators. If no size was parsed, the size
    portion is simply omitted.
    """
    size = f"{width}{aspect_ratio}{rim}" if (width and aspect_ratio and rim) else ""
    brand_prefix = (brand or "")[:2].upper()
    return f"{size}{brand_prefix}{manufacturer_code or ''}"


def create_table():
    """Create the products table and its indexes if needed."""
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS products (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                sync_status       TEXT,
                image_html        TEXT,
                logo_html         TEXT,
                description       TEXT,
                ean               TEXT,
                manufacturer_code TEXT,
                brand             TEXT,
                model             TEXT,
                product_type      TEXT,
                vehicle_type      TEXT,
                rolling_resistance TEXT,
                wet_grip          TEXT,
                noise_class       TEXT,
                noise_performance TEXT,
                vehicle_class     TEXT,
                created_date      TEXT,
                updated_date      TEXT,
                width             TEXT,
                aspect_ratio      TEXT,
                rim               TEXT,
                stock_code        TEXT,
                pricing_key       TEXT,
                product_group     TEXT
            )
            """
        )

        # Migrate tables created before the derived/pricing columns existed.
        existing = {row["name"] for row in conn.execute("PRAGMA table_info(products)")}
        for column in DERIVED_COLUMNS + ["pricing_key", "product_group"]:
            if column not in existing:
                conn.execute(f"ALTER TABLE products ADD COLUMN {column} TEXT")

        conn.execute("CREATE INDEX IF NOT EXISTS idx_products_ean ON products(ean)")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_products_brand ON products(brand COLLATE NOCASE)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_products_stock_code "
            "ON products(stock_code COLLATE NOCASE)"
        )


def import_from_csv(csv_path, replace=True):
    """Bulk-load products from a CSV file. Returns the resulting row count.

    With replace=True (the default) the table is emptied first, so re-running
    gives a clean reload rather than duplicating rows. The Stock Code and size
    columns are computed from each row as it is read.
    """
    base_columns = [col for _, col in CSV_TO_DB]
    all_columns = base_columns + DERIVED_COLUMNS
    placeholders = ", ".join("?" for _ in all_columns)
    insert_sql = f"INSERT INTO products ({', '.join(all_columns)}) VALUES ({placeholders})"

    def rows_from(reader):
        for row in reader:
            if not row:
                continue  # skip blank lines
            values = [row[index].strip() for index, _ in CSV_TO_DB]
            record = dict(zip(base_columns, values))
            width, aspect_ratio, rim = parse_size(record["description"])
            stock_code = build_stock_code(
                width, aspect_ratio, rim, record["brand"], record["manufacturer_code"]
            )
            yield values + [width, aspect_ratio, rim, stock_code]

    with get_connection() as conn:
        if replace:
            conn.execute("DELETE FROM products")
        # utf-8-sig strips a leading BOM if the export added one.
        with open(csv_path, newline="", encoding="utf-8-sig") as handle:
            reader = csv.reader(handle)
            next(reader, None)  # skip the header row
            conn.executemany(insert_sql, rows_from(reader))
        return conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]


def _all_fields():
    return {col for _, col in CSV_TO_DB} | set(DERIVED_COLUMNS) | {"id"}


def count_products():
    """Total number of products."""
    with get_connection() as conn:
        return conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]


def get_products(limit=200, offset=0):
    """Return a page of products ordered by description."""
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM products ORDER BY description COLLATE NOCASE LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()


def get_brands():
    """Return the distinct non-empty brand names, sorted case-insensitively."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT DISTINCT brand FROM products WHERE brand <> '' "
            "ORDER BY brand COLLATE NOCASE"
        ).fetchall()
        return [row["brand"] for row in rows]


def get_models(brand="", size_prefix=""):
    """Distinct non-empty models, optionally narrowed by brand and/or a stock-code
    size prefix (e.g. '2055516'). Keeps the model picker a manageable size."""
    clauses = ["model <> ''"]
    params = []
    if brand:
        clauses.append("brand = ? COLLATE NOCASE")
        params.append(brand)
    if size_prefix:
        clauses.append("stock_code LIKE ?")
        params.append(size_prefix + "%")
    with get_connection() as conn:
        rows = conn.execute(
            f"SELECT DISTINCT model FROM products WHERE {' AND '.join(clauses)} "
            "ORDER BY model COLLATE NOCASE",
            params,
        ).fetchall()
        return [row["model"] for row in rows]


def create_product(description, brand="", model="", ean="", manufacturer_code="",
                   product_type="", vehicle_type="", rolling_resistance="", wet_grip="",
                   noise_class="", noise_performance="", vehicle_class="",
                   pricing_key="", product_group=""):
    """Insert a manually-created product. Stock code/size are derived. Returns id."""
    width, aspect_ratio, rim = parse_size(description)
    stock_code = build_stock_code(width, aspect_ratio, rim, brand, manufacturer_code)
    today = datetime.date.today().strftime("%d/%m/%y")
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO products (sync_status, image_html, logo_html, description, ean, "
            "manufacturer_code, brand, model, product_type, vehicle_type, "
            "rolling_resistance, wet_grip, noise_class, noise_performance, vehicle_class, "
            "created_date, updated_date, width, aspect_ratio, rim, stock_code, "
            "pricing_key, product_group) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("", "", "", description, ean, manufacturer_code, brand, model, product_type,
             vehicle_type, rolling_resistance, wet_grip, noise_class, noise_performance,
             vehicle_class, today, today, width, aspect_ratio, rim, stock_code,
             pricing_key, product_group),
        )
        return cursor.lastrowid


# Current stock = invoiced purchases - sold quantities (sale Orders and Invoices).
# Purchase Orders and sale Quotes don't count.
STOCK_EXPR = (
    "(COALESCE((SELECT SUM(pi.quantity) FROM purchase_items pi "
    "JOIN purchases pu ON pu.id = pi.purchase_id "
    "WHERE pi.product_id = products.id AND pu.status = 'Invoice'), 0) "
    "- COALESCE((SELECT SUM(si.quantity) FROM sale_items si "
    "JOIN sales sa ON sa.id = si.sale_id "
    "WHERE si.product_id = products.id AND sa.status IN ('Order', 'Invoice')), 0))"
)
STOCK_SUBQUERY = STOCK_EXPR + " AS stock"

# Average unit cost = quantity-weighted cost across invoiced purchases (0 if none).
AVG_COST_EXPR = (
    "(SELECT CASE WHEN COALESCE(SUM(pi.quantity), 0) > 0 "
    "THEN SUM(pi.quantity * pi.cost_price) / SUM(pi.quantity) ELSE 0 END "
    "FROM purchase_items pi JOIN purchases pu ON pu.id = pi.purchase_id "
    "WHERE pi.product_id = products.id AND pu.status = 'Invoice')"
)
AVG_COST_SUBQUERY = AVG_COST_EXPR + " AS avg_cost"


def average_cost(product_id):
    """Quantity-weighted average unit cost from invoiced purchases (0 if none)."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(pi.quantity), 0) AS qty, "
            "COALESCE(SUM(pi.quantity * pi.cost_price), 0) AS spend "
            "FROM purchase_items pi JOIN purchases pu ON pu.id = pi.purchase_id "
            "WHERE pi.product_id = ? AND pu.status = 'Invoice'",
            (product_id,),
        ).fetchone()
        return row["spend"] / row["qty"] if row["qty"] else 0.0


def query_products(text="", brand="", in_stock="all", limit=200):
    """Filter products by free text, brand and/or stock status.

    `text` matches the description OR the stock code (case-insensitive).
    `brand` (when given) restricts to that exact brand.
    `in_stock`: 'yes' = only stocked, 'no' = only out of stock, 'all' = no filter.
    Each row includes a `stock` column (invoiced quantity).
    Returns (rows, total_matches) so the UI can report how many were capped.
    """
    clauses, params = [], []
    if text:
        like = f"%{text}%"
        clauses.append(
            "(description LIKE ? COLLATE NOCASE OR stock_code LIKE ? COLLATE NOCASE)"
        )
        params += [like, like]
    if brand:
        clauses.append("brand = ? COLLATE NOCASE")
        params.append(brand)
    if in_stock == "yes":
        clauses.append(f"{STOCK_EXPR} > 0")
    elif in_stock == "no":
        clauses.append(f"{STOCK_EXPR} = 0")
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""

    with get_connection() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM products{where}", params
        ).fetchone()[0]
        rows = conn.execute(
            f"SELECT products.*, {STOCK_SUBQUERY}, {AVG_COST_SUBQUERY} FROM products{where} "
            "ORDER BY description COLLATE NOCASE LIMIT ?",
            params + [limit],
        ).fetchall()
        return rows, total


# A size+speed shorthand like "2055516V" = size 205/55R16, speed rating V.
SIZE_SPEED_RE = re.compile(r"^(\d{7})([A-Za-z]+)$")


def search_products_adv(stock_code="", brand="", model="", in_stock="", limit=200):
    """Search by stock code and/or exact brand/model, for the Product Allocation
    window. The stock-code box also accepts a size+speed shorthand such as
    "2055516V" (size 205/55R16 + speed rating V). `in_stock` ('yes'/'no', else no
    filter) restricts by current stock. Returns (rows, total_matches)."""
    clauses, params = [], []
    speed = ""
    code = stock_code.strip()
    match = SIZE_SPEED_RE.match(code)
    if match:  # e.g. 2055516V -> size prefix on stock_code + speed in description
        clauses.append("stock_code LIKE ?")
        params.append(match.group(1) + "%")
        speed = match.group(2).upper()
    elif code:
        clauses.append("stock_code LIKE ? COLLATE NOCASE")
        params.append(f"%{code}%")
    if brand:
        clauses.append("brand = ? COLLATE NOCASE")
        params.append(brand)
    if model:
        clauses.append("model = ? COLLATE NOCASE")
        params.append(model)
    if in_stock == "yes":
        clauses.append(f"{STOCK_EXPR} > 0")
    elif in_stock == "no":
        clauses.append(f"{STOCK_EXPR} = 0")
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""

    with get_connection() as conn:
        if speed:
            # Speed rating sits in the description after the load index (e.g. "91V");
            # filter those rows in Python. The size clause already narrows it a lot.
            rows = conn.execute(
                f"SELECT * FROM products{where} ORDER BY description COLLATE NOCASE",
                params,
            ).fetchall()
            pattern = re.compile(r"\d\s*" + re.escape(speed) + r"\b", re.IGNORECASE)
            rows = [r for r in rows if pattern.search(r["description"] or "")]
            return rows[:limit], len(rows)
        total = conn.execute(
            f"SELECT COUNT(*) FROM products{where}", params
        ).fetchone()[0]
        rows = conn.execute(
            f"SELECT * FROM products{where} ORDER BY description COLLATE NOCASE LIMIT ?",
            params + [limit],
        ).fetchall()
        return rows, total


def product_stock(product_id):
    """Current stock = invoiced purchases - sold (sale Orders and Invoices)."""
    with get_connection() as conn:
        purchased = conn.execute(
            "SELECT COALESCE(SUM(pi.quantity), 0) FROM purchase_items pi "
            "JOIN purchases pu ON pu.id = pi.purchase_id "
            "WHERE pi.product_id = ? AND pu.status = 'Invoice'",
            (product_id,),
        ).fetchone()[0]
        sold = conn.execute(
            "SELECT COALESCE(SUM(si.quantity), 0) FROM sale_items si "
            "JOIN sales sa ON sa.id = si.sale_id "
            "WHERE si.product_id = ? AND sa.status IN ('Order', 'Invoice')",
            (product_id,),
        ).fetchone()[0]
        return purchased - sold


def get_product(product_id):
    """Return a single product Row by id, or None if not found."""
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM products WHERE id = ?", (product_id,)
        ).fetchone()
