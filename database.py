"""Central database for the app.

A single SQLite file (app.db) holds every table — currently Suppliers and
Products. Each entity keeps its own data-access module (suppliers.py,
products.py); they all share the one connection defined here.
"""

import sqlite3
from pathlib import Path

# The one database file the whole app stores everything on.
DB_PATH = Path(__file__).with_name("app.db")


def get_connection():
    """Open a connection to the central database with row access by column name."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")  # enforce referential integrity
    return conn


def init_db():
    """Create every table in the central database. Safe to call on each startup."""
    # Imported here (not at module top) to avoid an import cycle, since the
    # entity modules import get_connection from this module.
    import suppliers
    import products
    import nominals
    import purchases
    import payments

    suppliers.create_table()
    products.create_table()
    nominals.create_table()
    purchases.create_table()
    payments.create_table()
