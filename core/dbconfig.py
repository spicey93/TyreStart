"""Local database-connection configuration (Supabase).

The app stores its data in SQLite (app.db) by default. To share data between
machines it can instead point at a Supabase (PostgreSQL) database. The connection
details for that — project URL, keys, password and the pooler connection string —
are **deliberately kept in a local JSON file next to app.db, NOT in the database
itself**: they're the bootstrap needed to reach the remote database, so they can't
live inside it. The file is git-ignored (it holds secrets).

This module only stores/loads those details. Actually opening the Postgres
connection and migrating the data is wired up separately once the details are in.
"""
import json
from pathlib import Path

# Sits beside app.db; see core.database.DB_PATH.
CONFIG_PATH = Path(__file__).resolve().parent.parent / "db_config.json"

# Known keys (also the order shown on the Configuration → Database screen).
PROJECT_URL = "project_url"
ANON_KEY = "anon_key"
DB_PASSWORD = "db_password"
POOLER_CONNECTION_STRING = "pooler_connection_string"

FIELDS = (PROJECT_URL, ANON_KEY, DB_PASSWORD, POOLER_CONNECTION_STRING)


def load():
    """Return all stored connection details as a dict (missing keys -> "")."""
    data = {}
    if CONFIG_PATH.exists():
        try:
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8")) or {}
        except (json.JSONDecodeError, OSError):
            data = {}
    return {field: (data.get(field) or "") for field in FIELDS}


def get(field, default=""):
    """Return a single stored value, or ``default`` if unset/empty."""
    if field not in FIELDS:
        raise ValueError(f"unknown db config field: {field!r}")
    return load().get(field) or default


def save(values):
    """Persist the connection details from a {field: value} mapping. Unknown keys
    are ignored; values are trimmed. Returns the written dict."""
    out = {field: (values.get(field) or "").strip() for field in FIELDS}
    CONFIG_PATH.write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out


def is_configured():
    """True once a pooler connection string has been entered (enough to connect)."""
    return bool(get(POOLER_CONNECTION_STRING))
