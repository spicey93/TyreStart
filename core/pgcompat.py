"""PostgreSQL (Supabase) compatibility layer.

The whole app is written against SQLite's dialect via ``database.get_connection()``.
To share data between machines it can instead talk to a Supabase Postgres database.
Rather than rewrite every ``core/*`` module, this layer presents a small
sqlite3-shaped wrapper over psycopg (v3) and translates each statement from the
SQLite dialect to Postgres on the way through:

* ``?`` placeholders            -> ``%s``
* ``... AUTOINCREMENT`` PK       -> ``SERIAL PRIMARY KEY``
* ``REAL``                       -> ``DOUBLE PRECISION``
* ``LIKE`` (always case-insens.) -> ``ILIKE`` (and any trailing ``COLLATE NOCASE`` dropped)
* other ``COLLATE NOCASE``       -> kept, backed by an ICU case-insensitive collation
* ``PRAGMA foreign_keys = ON``   -> no-op
* ``PRAGMA table_info(t)``       -> an ``information_schema`` query yielding a ``name`` column

The wrapper also: returns rows that support both ``row["col"]`` and ``row[0]``
(like ``sqlite3.Row``); emulates ``cursor.lastrowid`` via ``lastval()``; commits and
closes on ``with`` exit; and re-raises Postgres unique violations as
``sqlite3.IntegrityError`` so the modules' existing ``except`` clauses still fire.
"""
import re
import sqlite3

import psycopg


# ---------------------------------------------------------------- SQL translation

_AUTOINC = re.compile(r'INTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT', re.I)
_PRAGMA_FK = re.compile(r'PRAGMA\s+foreign_keys\s*=\s*ON', re.I)
_PRAGMA_TABLE_INFO = re.compile(
    r'PRAGMA\s+table_info\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)', re.I)
_LIKE = re.compile(r'\bLIKE\b', re.I)
_ILIKE_COLLATE = re.compile(r'(ILIKE\s+\?)\s+COLLATE\s+NOCASE', re.I)
_REAL = re.compile(r'\bREAL\b', re.I)
# Two-arg ROUND: Postgres has no ROUND(double, int) and rounds double half-to-even.
# Cast the value to NUMERIC so it exists and rounds half-up (matching SQLite and the
# Python money helpers). Lazy match stops at the real ", 0)" — COALESCE(.., 20) is safe.
_ROUND2 = re.compile(r'ROUND\((.+?),\s*0\)', re.I | re.S)


def translate(sql):
    """Translate a single SQLite-dialect statement to Postgres."""
    # Escape any literal '%' (psycopg reads '%' as a placeholder marker) before we
    # introduce our own '%s' placeholders below. App SQL keeps LIKE patterns in
    # bound params, so this is normally a no-op, but it makes inline '%' safe.
    s = sql.replace('%', '%%')
    s = _PRAGMA_FK.sub('SELECT 1', s)
    s = _PRAGMA_TABLE_INFO.sub(
        r"SELECT column_name AS name FROM information_schema.columns "
        r"WHERE table_name = '\1'", s)
    # SQLite's LIKE is case-insensitive by default -> use ILIKE everywhere, and a
    # nondeterministic collation can't be used with pattern matching, so strip a
    # COLLATE NOCASE that trails an ILIKE placeholder.
    s = _LIKE.sub('ILIKE', s)
    s = _ILIKE_COLLATE.sub(r'\1', s)
    # DDL type/identity fixes.
    s = _AUTOINC.sub('SERIAL PRIMARY KEY', s)
    s = re.sub(r'\bAUTOINCREMENT\b', '', s, flags=re.I)
    s = _REAL.sub('DOUBLE PRECISION', s)
    s = _ROUND2.sub(r'ROUND(CAST(\1 AS NUMERIC), 0)', s)
    # Parameter placeholders (our SQL never contains a literal '?' or '%').
    s = s.replace('?', '%s')
    return s


# ------------------------------------------------------------------- row factory

class Row:
    """A psycopg row that mimics ``sqlite3.Row``: indexable by column name or
    position, iterable, and convertible via ``dict(row)``."""

    __slots__ = ("_cols", "_index", "_vals")

    def __init__(self, cols, index, vals):
        self._cols, self._index, self._vals = cols, index, vals

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._vals[key]
        return self._vals[self._index[key]]

    def get(self, key, default=None):
        i = self._index.get(key)
        return self._vals[i] if i is not None else default

    def keys(self):
        return list(self._cols)

    def __iter__(self):
        return iter(self._vals)

    def __len__(self):
        return len(self._vals)


def _row_factory(cursor):
    cols = [c.name for c in cursor.description] if cursor.description else []
    index = {name: i for i, name in enumerate(cols)}
    def make(values):
        return Row(cols, index, list(values))
    return make


# --------------------------------------------------------------- cursor / connection

class _Cursor:
    """Thin wrapper adding ``lastrowid`` and sqlite-style iteration to a psycopg
    cursor."""

    def __init__(self, raw_conn, cur):
        self._raw = raw_conn
        self._cur = cur

    def fetchone(self):
        return self._cur.fetchone()

    def fetchall(self):
        return self._cur.fetchall()

    def __iter__(self):
        return iter(self._cur)

    @property
    def rowcount(self):
        return self._cur.rowcount

    @property
    def lastrowid(self):
        # The preceding INSERT advanced a SERIAL sequence in this session.
        with self._raw.cursor() as c:
            c.execute("SELECT lastval()")
            return c.fetchone()[0]


class Connection:
    """sqlite3-shaped wrapper over a psycopg connection. Use as a context manager:
    commits on clean exit, rolls back on error, and closes either way."""

    def __init__(self, dsn):
        self._raw = psycopg.connect(dsn, row_factory=_row_factory)

    def execute(self, sql, params=()):
        cur = self._raw.cursor()
        try:
            cur.execute(translate(sql), params)
        except psycopg.errors.IntegrityError as exc:
            raise sqlite3.IntegrityError(str(exc)) from exc
        return _Cursor(self._raw, cur)

    def executemany(self, sql, seq_of_params):
        cur = self._raw.cursor()
        try:
            cur.executemany(translate(sql), list(seq_of_params))
        except psycopg.errors.IntegrityError as exc:
            raise sqlite3.IntegrityError(str(exc)) from exc
        return _Cursor(self._raw, cur)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            self._raw.commit()
        else:
            self._raw.rollback()
        self._raw.close()
        return False

    def close(self):
        self._raw.close()


def connect(dsn):
    """Open a Postgres connection behind the sqlite3-shaped wrapper."""
    return Connection(dsn)


def ensure_prerequisites(dsn):
    """Create database objects the translated SQL relies on — currently the
    case-insensitive ``nocase`` collation that backs ``COLLATE NOCASE``. Idempotent."""
    with psycopg.connect(dsn) as conn:
        conn.execute(
            "CREATE COLLATION IF NOT EXISTS nocase "
            "(provider = icu, locale = 'und-u-ks-level2', deterministic = false)"
        )
        conn.commit()
