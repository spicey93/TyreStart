"""Application settings (a small key/value store in app.db).

Holds configuration the user enters in the app rather than in code — currently
third-party API keys (Configuration → API Keys). Stdlib/sqlite only.
"""
from core.database import get_connection

# Known setting keys.
UKVD_API_KEY = "uk_vehicle_data_api_key"


def create_table():
    """Create the app_settings table if needed."""
    with get_connection() as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS app_settings (key TEXT PRIMARY KEY, value TEXT)"
        )


def get(key, default=None):
    """Return a setting's value, or ``default`` if unset/empty."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT value FROM app_settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row and row["value"] is not None else default


def set(key, value):
    """Upsert a setting."""
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO app_settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
