"""Products data-access layer.

All product SQL lives here. Uses the shared connection from the central
database (database.py), so products are stored in app.db alongside suppliers.

Product rows are bulk-loaded from products.csv via import_from_csv(). During
import we parse the tyre size out of the description and build a Stock Code.
"""

import csv
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
                stock_code        TEXT
            )
            """
        )

        # Migrate tables created before the derived columns existed.
        existing = {row["name"] for row in conn.execute("PRAGMA table_info(products)")}
        for column in DERIVED_COLUMNS:
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


def query_products(text="", brand="", limit=200):
    """Filter products by free text and/or an exact brand.

    `text` matches the description OR the stock code (case-insensitive).
    `brand` (when given) restricts to that exact brand.
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
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""

    with get_connection() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM products{where}", params
        ).fetchone()[0]
        rows = conn.execute(
            f"SELECT * FROM products{where} ORDER BY description COLLATE NOCASE LIMIT ?",
            params + [limit],
        ).fetchall()
        return rows, total


def get_product(product_id):
    """Return a single product Row by id, or None if not found."""
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM products WHERE id = ?", (product_id,)
        ).fetchone()
