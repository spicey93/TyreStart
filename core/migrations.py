"""Schema/data migration runner.

Called once at the end of database.init_db(), after every table has been created
(so new columns exist). Each migration is guarded by the integer schema version in
schema_meta, so it runs exactly once on an existing database and is a no-op on
every subsequent startup. A timestamped backup is taken before any migration runs
against a database that actually holds data.
"""

from core import dbmaint
from core.database import get_connection

# Bump as migrations are added below.
LATEST = 2

# Tables whose presence of rows means "this is a real database worth backing up".
_DATA_TABLES = ("sale_items", "purchase_items", "payments", "receipts")


def _has_data(conn):
    for table in _DATA_TABLES:
        try:
            if conn.execute(f"SELECT 1 FROM {table} LIMIT 1").fetchone():
                return True
        except Exception:
            pass
    return False


def run_pending():
    """Run any migrations newer than the stored schema version."""
    current = dbmaint.schema_version()
    if current >= LATEST:
        return

    with get_connection() as conn:
        backup_needed = _has_data(conn)
    if backup_needed:
        dbmaint.backup_db(f"pre-v{LATEST}")

    if current < 1:
        from core import migrate_money
        migrate_money.run()
        dbmaint.set_schema_version(1)

    if current < 2:
        from core import migrate_dates
        migrate_dates.run()
        dbmaint.set_schema_version(2)
