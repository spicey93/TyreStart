"""Central database for the app.

A single SQLite file (app.db) holds every table — currently Suppliers and
Products. Each entity keeps its own data-access module (suppliers.py,
products.py); they all share the one connection defined here.
"""

import sqlite3
from pathlib import Path

from core import dbconfig

# The one database file the whole app stores everything on (SQLite default).
DB_PATH = Path(__file__).resolve().parent.parent / "app.db"

# Bump whenever any create_table() schema changes, so the Postgres startup sweep
# (see init_db) runs once more to apply it; otherwise it's skipped for speed.
SCHEMA_BUILD = 1


# Tests set this True to force the local SQLite backend (against a throwaway
# DB_PATH) regardless of any configured Supabase connection — so the suite never
# touches the shared database.
USE_SQLITE_OVERRIDE = False


def backend():
    """'postgres' when Supabase connection details are configured, else 'sqlite'."""
    if USE_SQLITE_OVERRIDE:
        return "sqlite"
    return "postgres" if dbconfig.is_configured() else "sqlite"


def get_connection():
    """Open a connection to the central database with row access by column name.

    Returns a Postgres-backed connection (via the pgcompat shim) when Supabase is
    configured under Configuration → Database, otherwise the local SQLite file.
    """
    if backend() == "postgres":
        from core import pgcompat
        return pgcompat.connect(dbconfig.get(dbconfig.POOLER_CONNECTION_STRING))
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")  # enforce referential integrity
    return conn


def init_db():
    """Create every table in the central database. Safe to call on each startup."""
    # Imported here (not at module top) to avoid an import cycle, since the
    # entity modules import get_connection from this module.
    from core import dbmaint
    from core import suppliers
    from core import products
    from core import nominals
    from core import accounts
    from core import journal
    from core import purchases
    from core import payments
    from core import services
    from core import customers
    from core import sales
    from core import receipts
    from core import pricing
    from core import lookups
    from core import taxcodes
    from core import vat
    from core import settings
    from core import vehicles

    dbmaint.create_table()

    # The full create-table/migration sweep is idempotent but chatty — ~60 network
    # round-trips on Postgres (~3s). Once it has run for the current SCHEMA_BUILD we
    # record a marker and skip it on later startups. Bump SCHEMA_BUILD below whenever
    # a create_table() changes so the sweep runs once more. On SQLite the sweep is
    # local and instant, so it always runs (the marker is Postgres-only).
    if backend() == "postgres" and dbmaint.get_meta("pg_build") == str(SCHEMA_BUILD):
        return

    # On Postgres, create the objects the translated SQL relies on (the nocase
    # collation) before any table DDL that uses COLLATE NOCASE.
    if backend() == "postgres":
        from core import pgcompat
        pgcompat.ensure_prerequisites(dbconfig.get(dbconfig.POOLER_CONNECTION_STRING))

    suppliers.create_table()
    products.create_table()
    nominals.create_table()
    accounts.create_table()
    journal.create_table()
    purchases.create_table()
    payments.create_table()
    services.create_table()
    customers.create_table()
    vehicles.create_table()  # before sales: a sale may carry a vehicle_id FK
    sales.create_table()
    receipts.create_table()
    pricing.create_table()
    lookups.create_table()
    taxcodes.create_table()
    vat.create_table()
    settings.create_table()

    # Run any pending data migrations now that every table/column exists.
    from core import migrations
    migrations.run_pending()

    if backend() == "postgres":
        dbmaint.set_meta("pg_build", SCHEMA_BUILD)
