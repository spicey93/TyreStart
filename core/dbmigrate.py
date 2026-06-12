"""One-time copy of the local SQLite database into Supabase (Postgres).

Reads every row from the local ``app.db`` and inserts it into the configured
Supabase database (schema must already exist — run ``database.init_db()`` first).
Tables are loaded parent-before-child (topologically by foreign key) and each
table's id sequence is reset afterwards so new inserts don't collide.

Safe to invoke: a target table that already holds rows is **skipped** (so a partial
re-run won't duplicate data). Reading is direct sqlite3; writing goes through the
pgcompat wrapper, so identifiers/placeholders are translated the same way the app's
queries are.
"""
import sqlite3

from core import database, dbconfig, pgcompat

BATCH = 2000


def _sqlite_conn():
    conn = sqlite3.connect(database.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _tables(sconn):
    return [r["name"] for r in sconn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]


def _columns(sconn, table):
    return [r["name"] for r in sconn.execute(f'PRAGMA table_info("{table}")')]


def _order_by_fk(sconn, tables):
    """Topologically sort tables so a table's foreign-key parents load first."""
    deps = {t: set() for t in tables}
    for t in tables:
        for r in sconn.execute(f'PRAGMA foreign_key_list("{t}")'):
            parent = r["table"]
            if parent in deps and parent != t:
                deps[t].add(parent)
    ordered, seen = [], set()
    while len(ordered) < len(tables):
        progressed = False
        for t in tables:
            if t not in seen and deps[t] <= seen:
                ordered.append(t)
                seen.add(t)
                progressed = True
        if not progressed:  # a cycle — append the rest in any order
            for t in tables:
                if t not in seen:
                    ordered.append(t)
                    seen.add(t)
            break
    return ordered


def _pg_tables(pconn):
    return {r["name"] for r in pconn.execute(
        "SELECT table_name AS name FROM information_schema.tables "
        "WHERE table_schema = 'public'")}


def _pg_columns(pconn, table):
    return {r["name"] for r in pconn.execute(
        "SELECT column_name AS name FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = ?", (table,))}


def copy_to_postgres(progress=lambda msg: None):
    """Copy all local data into the configured Supabase database. Returns a dict of
    ``{table: rows_copied}``. Tables already containing rows are skipped."""
    if database.backend() != "postgres":
        raise RuntimeError("Supabase is not configured (Configuration → Database).")
    dsn = dbconfig.get(dbconfig.POOLER_CONNECTION_STRING)

    sconn = _sqlite_conn()
    try:
        with pgcompat.connect(dsn) as probe:
            pg_tables = _pg_tables(probe)
        tables = [t for t in _tables(sconn) if t in pg_tables]
        skipped_missing = [t for t in _tables(sconn) if t not in pg_tables]
        for t in skipped_missing:
            progress(f"!  {t}: no matching table in Supabase — skipped")

        copied = {}
        for table in _order_by_fk(sconn, tables):
            with pgcompat.connect(dsn) as probe:
                pg_cols = _pg_columns(probe, table)
            # Only columns present in both schemas (the local DB can carry legacy
            # columns the fresh Supabase schema no longer has, and vice versa).
            cols = [c for c in _columns(sconn, table) if c in pg_cols]
            col_sql = ", ".join(f'"{c}"' for c in cols)
            rows = sconn.execute(f'SELECT {col_sql} FROM "{table}"').fetchall()
            if not rows:
                copied[table] = 0
                progress(f"-  {table}: empty")
                continue

            with pgcompat.connect(dsn) as pconn:
                existing = pconn.execute(
                    f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
                if existing:
                    copied[table] = 0
                    progress(f"=  {table}: target already has {existing} rows — skipped")
                    continue

                placeholders = ", ".join("?" for _ in cols)
                insert = f'INSERT INTO "{table}" ({col_sql}) VALUES ({placeholders})'
                total = len(rows)
                for start in range(0, total, BATCH):
                    chunk = [tuple(r) for r in rows[start:start + BATCH]]
                    pconn.executemany(insert, chunk)
                    progress(f"   {table}: {min(start + BATCH, total)}/{total}")
                # Reset the id sequence so future inserts don't collide.
                if "id" in cols:
                    pconn.execute(
                        f"SELECT setval(pg_get_serial_sequence('\"{table}\"', 'id'), "
                        f'(SELECT MAX(id) FROM "{table}"))')
                copied[table] = total
                progress(f"OK {table}: {total} rows")
        return copied
    finally:
        sconn.close()
