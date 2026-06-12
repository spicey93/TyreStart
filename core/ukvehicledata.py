"""UK Vehicle Data (vehicledataglobal.com) TyreData lookup client.

Stdlib-only HTTPS client for a VRM → vehicle/tyre-fit lookup. ``fetch_raw`` does
the network call (injectable, so tests never hit the live, paid API); ``parse``
turns a response into the fields we display and store. The API key is passed in
(from app settings) — never stored here.

Endpoint (GET):
    https://legacy.api.vehicledataglobal.com/api/datapackage/TyreData
        ?v=2&auth_apikey=<KEY>&key_vrm=<VRM>
"""
import json
import urllib.parse
import urllib.request

API_URL = "https://legacy.api.vehicledataglobal.com/api/datapackage/TyreData"
TIMEOUT_SECONDS = 20


class LookupError(Exception):
    """The API responded but the lookup itself was not successful."""


def build_url(vrm, api_key):
    """Build the TyreData request URL for a (normalised) VRM and API key."""
    query = urllib.parse.urlencode({"v": 2, "auth_apikey": api_key, "key_vrm": vrm})
    return f"{API_URL}?{query}"


def _http_get(url):
    with urllib.request.urlopen(url, timeout=TIMEOUT_SECONDS) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_raw(vrm, api_key, fetch=None):
    """Call the API and return the raw decoded JSON (a dict).

    Network problems raise ``urllib.error.URLError``. Pass ``fetch`` (a callable
    taking the URL and returning a decoded dict) to inject a stub in tests.
    """
    return (fetch or _http_get)(build_url(vrm, api_key))


def _dig(data, *path):
    """Safely walk nested dict keys, returning None if any step is missing."""
    for key in path:
        if not isinstance(data, dict):
            return None
        data = data.get(key)
    return data


def parse(data):
    """Extract make/model/year and the tyre-fitment list from a raw response.

    Returns ``{make, model, build_year, tyres: [{front_size, rear_size,
    load_index, speed_index, front_psi, rear_psi, rim_size}, …]}``. Raises
    ``LookupError`` if the response status is not 'Success'.
    """
    status = _dig(data, "Response", "StatusCode")
    if status != "Success":
        message = _dig(data, "Response", "StatusMessage") or status or "Lookup failed"
        raise LookupError(str(message))

    items = _dig(data, "Response", "DataItems") or {}
    vehicle = items.get("VehicleDetails") or {}

    tyres = []
    for record in (_dig(items, "TyreDetails", "RecordList") or []):
        front = _dig(record, "Front", "Tyre") or {}
        rear = _dig(record, "Rear", "Tyre") or {}
        tyres.append({
            "front_size": front.get("Size"),
            "rear_size": rear.get("Size"),
            "load_index": front.get("LoadIndex"),
            "speed_index": front.get("SpeedIndex"),
            "front_psi": _dig(front, "Pressure", "Psi"),
            "rear_psi": _dig(rear, "Pressure", "Psi"),
            "rim_size": _dig(record, "Front", "Rim", "Size"),
        })

    return {
        "make": vehicle.get("Make"),
        "model": vehicle.get("Model"),
        "build_year": vehicle.get("BuildYear"),
        "tyres": tyres,
    }
