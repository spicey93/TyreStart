"""Tests for VRM normalisation, the UK Vehicle Data response parser, and the
database-first/API-fallback lookup. No live API calls — the fetcher is injected.
"""
import unittest

from core import settings, ukvehicledata, vehicles
from tests.support import DatabaseTestCase

# A trimmed copy of a real TyreData response (the shape we parse).
SAMPLE = {
    "Response": {
        "StatusCode": "Success",
        "StatusMessage": "Success",
        "DataItems": {
            "VehicleDetails": {"Make": "Mazda", "Model": "3 TS", "BuildYear": "2007"},
            "TyreDetails": {
                "RecordList": [
                    {
                        "Front": {"Tyre": {"Size": "195/65R15", "LoadIndex": "91",
                                            "SpeedIndex": "H", "Pressure": {"Psi": 32}},
                                  "Rim": {"Size": "6 x 15"}},
                        "Rear": {"Tyre": {"Size": "195/65R15", "Pressure": {"Psi": 45}}},
                    },
                    {
                        "Front": {"Tyre": {"Size": "205/55R16", "LoadIndex": "91",
                                            "SpeedIndex": "H", "Pressure": {"Psi": 32}},
                                  "Rim": {"Size": "6.5 x 16"}},
                        "Rear": {"Tyre": {"Size": "205/55R16", "Pressure": {"Psi": 33}}},
                    },
                    {
                        "Front": {"Tyre": {"Size": "205/50R17", "LoadIndex": "89",
                                            "SpeedIndex": "H", "Pressure": {"Psi": 32}},
                                  "Rim": {"Size": "6.5 x 17"}},
                        "Rear": {"Tyre": {"Size": "205/50R17", "Pressure": {"Psi": 45}}},
                    },
                ],
                "RecordCount": 3,
            },
        },
    }
}


class NormalizeTests(unittest.TestCase):
    def test_strips_whitespace_and_uppercases(self):
        self.assertEqual(vehicles.normalize_vrm("LD07 LTF"), "LD07LTF")
        self.assertEqual(vehicles.normalize_vrm("ld07ltf"), "LD07LTF")
        self.assertEqual(vehicles.normalize_vrm("  ld 07 ltf  "), "LD07LTF")
        self.assertEqual(vehicles.normalize_vrm(""), "")
        self.assertEqual(vehicles.normalize_vrm(None), "")


class ParseTests(unittest.TestCase):
    def test_parse_sample(self):
        parsed = ukvehicledata.parse(SAMPLE)
        self.assertEqual(parsed["make"], "Mazda")
        self.assertEqual(parsed["model"], "3 TS")
        self.assertEqual(parsed["build_year"], "2007")
        self.assertEqual(len(parsed["tyres"]), 3)
        self.assertEqual([t["front_size"] for t in parsed["tyres"]],
                         ["195/65R15", "205/55R16", "205/50R17"])
        first = parsed["tyres"][0]
        self.assertEqual((first["load_index"], first["speed_index"]), ("91", "H"))
        self.assertEqual((first["front_psi"], first["rear_psi"]), (32, 45))
        self.assertEqual(first["rim_size"], "6 x 15")

    def test_non_success_raises(self):
        bad = {"Response": {"StatusCode": "KeyInvalid", "StatusMessage": "Invalid API key"}}
        with self.assertRaises(ukvehicledata.LookupError):
            ukvehicledata.parse(bad)

    def test_build_url(self):
        url = ukvehicledata.build_url("LD07LTF", "ABC-123")
        self.assertIn("key_vrm=LD07LTF", url)
        self.assertIn("auth_apikey=ABC-123", url)
        self.assertTrue(url.startswith(ukvehicledata.API_URL))


class LookupTests(DatabaseTestCase):
    def _boom(self, url):
        raise AssertionError("API should not have been called")

    def test_database_first_skips_api(self):
        # Pre-store the vehicle, then look it up: must come from cache (no API).
        vehicles.save_vehicle("LD07LTF", ukvehicledata.parse(SAMPLE), __import__("json").dumps(SAMPLE))
        result = vehicles.lookup("ld07 ltf", fetch=self._boom)   # different spacing/case
        self.assertEqual(result["source"], "cache")
        self.assertEqual(result["make"], "Mazda")
        self.assertEqual(len(result["tyres"]), 3)

    def test_api_then_cached(self):
        settings.set(settings.UKVD_API_KEY, "dummy-key")
        result = vehicles.lookup("LD07 LTF", fetch=lambda url: SAMPLE)
        self.assertEqual(result["source"], "api")
        self.assertEqual(result["vrm"], "LD07LTF")
        self.assertEqual(result["make"], "Mazda")
        # Stored now → second lookup is a cache hit and never calls the API.
        again = vehicles.lookup("ld07ltf", fetch=self._boom)
        self.assertEqual(again["source"], "cache")

    def test_no_api_key_raises(self):
        with self.assertRaises(vehicles.NoApiKeyError):
            vehicles.lookup("AB12CDE", fetch=lambda url: SAMPLE)

    def test_blank_vrm_raises(self):
        with self.assertRaises(vehicles.VehicleError):
            vehicles.lookup("   ")

    def test_api_failure_propagates(self):
        settings.set(settings.UKVD_API_KEY, "dummy-key")
        bad = {"Response": {"StatusCode": "VrmNotFound", "StatusMessage": "Not found"}}
        with self.assertRaises(ukvehicledata.LookupError):
            vehicles.lookup("XX99XXX", fetch=lambda url: bad)


class SettingsTests(DatabaseTestCase):
    def test_get_set_default(self):
        self.assertEqual(settings.get("nope", "fallback"), "fallback")
        settings.set("k", "v")
        self.assertEqual(settings.get("k"), "v")
        settings.set("k", "v2")   # upsert
        self.assertEqual(settings.get("k"), "v2")


if __name__ == "__main__":
    unittest.main()
