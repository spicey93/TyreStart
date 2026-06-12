"""Vehicles: VRM lookups cached in app.db, backed by the UK Vehicle Data API.

A lookup checks our ``vehicles`` table first and only calls the API (with the key
from Configuration → API Keys) when we don't already hold that VRM. VRMs are
normalised — all whitespace removed and upper-cased — so 'LD07 LTF' and 'ld07ltf'
are the same vehicle. Successful API responses are stored (raw JSON kept) so the
next lookup is free and offline.
"""
import datetime
import json

from core import settings, ukvehicledata
from core.database import get_connection


class VehicleError(Exception):
    """A VRM lookup could not be completed (bad input, no key, etc.)."""


class NoApiKeyError(VehicleError):
    """No UK Vehicle Data API key has been configured."""


def normalize_vrm(vrm):
    """Canonical VRM: all whitespace removed and upper-cased."""
    return "".join((vrm or "").split()).upper()


def _now():
    return datetime.datetime.now().isoformat(timespec="seconds")


def create_table():
    """Create the vehicles table if needed."""
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS vehicles (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                vrm         TEXT NOT NULL UNIQUE,   -- normalised (no spaces, upper-case)
                make        TEXT,
                model       TEXT,
                build_year  TEXT,
                raw_json    TEXT,                   -- full API response, for re-display
                created_at  TEXT
            )
            """
        )


def get_by_vrm(vrm):
    """Return the stored vehicle row for a VRM (normalised), or None."""
    with get_connection() as conn:
        return conn.execute(
            "SELECT id, vrm, make, model, build_year, raw_json, created_at "
            "FROM vehicles WHERE vrm = ?", (normalize_vrm(vrm),)).fetchone()


def get_by_id(vehicle_id):
    """Return the stored vehicle row for an id, or None."""
    with get_connection() as conn:
        return conn.execute(
            "SELECT id, vrm, make, model, build_year, raw_json, created_at "
            "FROM vehicles WHERE id = ?", (vehicle_id,)).fetchone()


def list_vehicles(text=""):
    """Stored vehicles whose VRM contains ``text`` (normalised), newest first."""
    like = f"%{normalize_vrm(text)}%"
    with get_connection() as conn:
        return conn.execute(
            "SELECT id, vrm, make, model, build_year, created_at FROM vehicles "
            "WHERE vrm LIKE ? ORDER BY created_at DESC", (like,)).fetchall()


def save_vehicle(vrm, parsed, raw_json):
    """Insert/refresh a stored vehicle from a parsed lookup + its raw JSON."""
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO vehicles (vrm, make, model, build_year, raw_json, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(vrm) DO UPDATE SET make = excluded.make, model = excluded.model, "
            "build_year = excluded.build_year, raw_json = excluded.raw_json",
            (normalize_vrm(vrm), parsed.get("make"), parsed.get("model"),
             parsed.get("build_year"), raw_json, _now()),
        )


def details(row):
    """Parse a stored vehicle row's raw JSON into the display structure."""
    data = json.loads(row["raw_json"]) if row["raw_json"] else {}
    try:
        return ukvehicledata.parse(data)
    except ukvehicledata.LookupError:
        # Defensive: only success payloads are stored, but fall back to columns.
        return {"make": row["make"], "model": row["model"],
                "build_year": row["build_year"], "tyres": []}


def _split_camel(name):
    """'BuildYear' -> 'Build Year'; leave already-spaced names alone."""
    out = []
    for i, ch in enumerate(name):
        if i and ch.isupper() and not name[i - 1].isupper():
            out.append(" ")
        out.append(ch)
    return "".join(out)


def attributes(row):
    """A comprehensive, read-only list of ``(label, value)`` pairs describing the
    vehicle, taken from the stored raw API response's ``VehicleDetails``. Only
    scalar (non-empty) fields are included; keys are de-camel-cased for display.
    Falls back to the stored columns when no raw JSON is available."""
    data = json.loads(row["raw_json"]) if row["raw_json"] else {}
    details = (ukvehicledata._dig(data, "Response", "DataItems", "VehicleDetails")
               or {})
    pairs = []
    for key, value in details.items():
        if isinstance(value, (dict, list)) or value in (None, ""):
            continue
        pairs.append((_split_camel(key), str(value)))
    if not pairs:  # no raw payload — show what the columns hold
        pairs = [(label, row[col]) for label, col in
                 (("Make", "make"), ("Model", "model"), ("Build Year", "build_year"))
                 if row[col]]
    return pairs


def lookup(vrm, fetch=None):
    """Look up a VRM — our database first, otherwise the API (cached on success).

    Returns ``{vrm, source: 'cache'|'api', make, model, build_year, tyres}``.
    Raises ``NoApiKeyError`` if the API is needed but no key is set,
    ``VehicleError`` for bad input, ``ukvehicledata.LookupError`` if the API
    reports failure, or ``urllib.error.URLError`` on a network problem.
    """
    norm = normalize_vrm(vrm)
    if not norm:
        raise VehicleError("Enter a registration number (VRM).")

    row = get_by_vrm(norm)
    if row is not None:
        return {"vrm": norm, "source": "cache", **details(row)}

    api_key = (settings.get(settings.UKVD_API_KEY) or "").strip()
    if not api_key:
        raise NoApiKeyError(
            "No UK Vehicle Data API key set. Add one in Configuration → API Keys.")

    data = ukvehicledata.fetch_raw(norm, api_key, fetch=fetch)
    parsed = ukvehicledata.parse(data)
    save_vehicle(norm, parsed, json.dumps(data))
    return {"vrm": norm, "source": "api", **parsed}
