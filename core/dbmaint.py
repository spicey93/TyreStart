"""Database maintenance helpers: backups and a schema version stamp.

Used by the one-shot migrations (and the UI "Backup database" command) so that
every schema change is reversible (a timestamped copy is taken first) and
idempotent (each migration runs only once, guarded by ``schema_version``).

Kept tiny and dependency-free (stdlib only) like the rest of ``core``.
"""

import datetime
import shutil

from core.database import DB_PATH, get_connection


def create_table():
    """Create the schema_meta key/value table if needed."""
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_meta (
                key   TEXT PRIMARY KEY,
                value TEXT
            )
            """
        )


def backup_db(suffix=None):
    """Copy the live database file beside itself as ``app.db.bak-<timestamp>``.

    Returns the backup path (or None if the database file does not exist yet, as
    in tests that run against a fresh temp DB). ``suffix`` lets a caller tag the
    reason, e.g. ``backup_db("pre-money")`` → ``app.db.bak-20260611-2216-pre-money``.
    """
    if not DB_PATH.exists():
        return None
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    tag = f"-{suffix}" if suffix else ""
    dest = DB_PATH.parent / f"{DB_PATH.name}.bak-{stamp}{tag}"
    shutil.copy2(DB_PATH, dest)
    return dest


def get_meta(key):
    """Return a schema_meta value by key, or None."""
    create_table()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT value FROM schema_meta WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def set_meta(key, value):
    """Upsert a schema_meta key/value."""
    create_table()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO schema_meta (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, str(value)),
        )


def schema_version():
    """Return the integer schema version (0 if never set)."""
    create_table()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT value FROM schema_meta WHERE key = 'schema_version'"
        ).fetchone()
    return int(row["value"]) if row and row["value"] is not None else 0


def set_schema_version(version):
    """Record the schema version (upsert)."""
    create_table()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO schema_meta (key, value) VALUES ('schema_version', ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (str(int(version)),),
        )
