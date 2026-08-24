"""
Pytest test suite for USGS/OpenWeatherMap flood ingestion (Task 12)

Run with: pytest tests/test_flood_ingestion_pytest.py -v

Uses canned USGS WaterML-JSON responses and monkeypatched requests.get()/
WeatherIngester so these tests are deterministic, offline, and independent
of any real API key or network access.
"""

import json
from datetime import datetime, timedelta, timezone

import pytest

import src.database.db as db_module
import src.data_ingestion.flood_ingestion as flood_module
from src.data_ingestion.flood_ingestion import FloodIngester, MAX_GAUGE_READING_AGE_HOURS


def _iso(dt: datetime) -> str:
    """Format a UTC-aware datetime with its true (+00:00) offset - dt's
    digits must match the labeled offset, or the reconstructed instant
    will be wrong when parsed back (this bit us once already: labeling
    UTC digits with a fake -05:00 suffix silently shifted every timestamp
    by 5 hours, masking staleness in the tests below)."""
    return dt.strftime("%Y-%m-%dT%H:%M:%S.000+00:00")


def make_usgs_response(current_dt: datetime, stale_dt: datetime) -> dict:
    """Build a canned USGS WaterML-as-JSON response with one current and one stale site."""
    return {
        "value": {
            "timeSeries": [
                {
                    "sourceInfo": {
                        "siteName": "CURRENT RIVER GAUGE",
                        "geoLocation": {"geogLocation": {"latitude": "29.95", "longitude": "-90.07"}},
                    },
                    "variable": {"variableCode": [{"value": "00065"}]},
                    "values": [{"value": [{"value": "3.21", "qualifiers": ["P"], "dateTime": _iso(current_dt)}]}],
                },
                {
                    "sourceInfo": {
                        "siteName": "STALE RIVER GAUGE",
                        "geoLocation": {"geogLocation": {"latitude": "30.10", "longitude": "-89.90"}},
                    },
                    "variable": {"variableCode": [{"value": "00060"}]},
                    "values": [{"value": [{"value": "-509", "qualifiers": ["A"], "dateTime": _iso(stale_dt)}]}],
                },
            ]
        }
    }


class FakeResponse:
    """Minimal stand-in for requests.Response."""

    def __init__(self, json_data=None, status_code=200, text=""):
        self._json_data = json_data
        self.status_code = status_code
        self.text = text or str(json_data)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise flood_module.requests.exceptions.HTTPError(f"HTTP {self.status_code}")

    def json(self):
        if self._json_data is None:
            raise ValueError("No JSON")
        return self._json_data


class FakeRequests:
    """Stand-in for the requests module, records the last URL requested."""

    def __init__(self, response=None, exception=None):
        self._response = response
        self._exception = exception
        self.last_url = None
        self.calls = 0

    def get(self, url, timeout=None):
        self.calls += 1
        self.last_url = url
        if self._exception:
            raise self._exception
        return self._response

    class exceptions:
        RequestException = Exception
        HTTPError = Exception


@pytest.fixture
def ingester():
    """A FloodIngester with deterministic, test-controlled attributes."""
    ing = FloodIngester()
    ing.enabled = True
    return ing


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """Temporary SQLite database with the hazard_data schema."""
    db_path = tmp_path / "test_climate_risk.db"
    monkeypatch.setattr(db_module, "DB_PATH", db_path)

    conn = db_module.get_db_connection()
    conn.execute(db_module.get_schema()["hazard_data"])
    conn.commit()
    conn.close()

    return db_path


class TestParseGaugeResponse:
    """Tests for _parse_gauge_response() - pure parsing/staleness logic, no network."""

    def test_current_reading_is_kept(self, ingester):
        now = datetime.now(timezone.utc)
        data = make_usgs_response(current_dt=now - timedelta(hours=1), stale_dt=now - timedelta(days=1000))

        records = ingester._parse_gauge_response(data)

        assert len(records) == 1
        assert records[0]["raw_data"].find("CURRENT RIVER GAUGE") != -1

    def test_stale_reading_is_filtered_out(self, ingester):
        now = datetime.now(timezone.utc)
        # both stale: neither should survive
        data = make_usgs_response(
            current_dt=now - timedelta(hours=MAX_GAUGE_READING_AGE_HOURS + 1),
            stale_dt=now - timedelta(days=1000),
        )

        records = ingester._parse_gauge_response(data)

        assert len(records) == 0

    def test_normalized_fields_present(self, ingester):
        now = datetime.now(timezone.utc)
        data = make_usgs_response(current_dt=now, stale_dt=now - timedelta(days=1000))

        records = ingester._parse_gauge_response(data)
        record = records[0]
        for field in ["hazard_type", "source", "latitude", "longitude", "value",
                      "confidence", "observation_timestamp", "raw_data"]:
            assert field in record

    def test_hazard_type_and_source_are_correct(self, ingester):
        now = datetime.now(timezone.utc)
        data = make_usgs_response(current_dt=now, stale_dt=now - timedelta(days=1000))

        records = ingester._parse_gauge_response(data)
        assert records[0]["hazard_type"] == "flood"
        assert records[0]["source"] == "USGS"

    def test_missing_time_series_returns_empty_list(self, ingester):
        records = ingester._parse_gauge_response({"unexpected": "shape"})
        assert records == []

    def test_invalid_coordinates_are_skipped(self, ingester):
        now = datetime.now(timezone.utc)
        data = make_usgs_response(current_dt=now, stale_dt=now - timedelta(days=1000))
        data["value"]["timeSeries"][0]["sourceInfo"]["geoLocation"]["geogLocation"]["latitude"] = "999"

        records = ingester._parse_gauge_response(data)

        # first entry: invalid coordinates -> skipped; second entry: stale -> skipped
        assert len(records) == 0


class TestFetchRiverGauges:
    """Tests for fetch_river_gauges() - HTTP orchestration + bbox constraint, mocked."""

    def test_disabled_source_returns_empty_without_request(self, ingester, monkeypatch):
        ingester.enabled = False
        fake = FakeRequests()
        monkeypatch.setattr(flood_module, "requests", fake)

        result = ingester.fetch_river_gauges(29.0, 30.8, -91.2, -89.4)

        assert result == []
        assert fake.calls == 0

    def test_bbox_too_large_returns_empty_without_request(self, ingester, monkeypatch):
        fake = FakeRequests()
        monkeypatch.setattr(flood_module, "requests", fake)

        # lat_range=10, lon_range=10 -> product=100 > 25
        result = ingester.fetch_river_gauges(20, 30, -100, -90)

        assert result == []
        assert fake.calls == 0

    def test_bounding_box_order_is_west_south_east_north(self, ingester, monkeypatch):
        now = datetime.now(timezone.utc)
        data = make_usgs_response(current_dt=now, stale_dt=now - timedelta(days=1000))
        fake = FakeRequests(response=FakeResponse(json_data=data))
        monkeypatch.setattr(flood_module, "requests", fake)

        ingester.fetch_river_gauges(lat_min=29.0, lat_max=30.8, lon_min=-91.2, lon_max=-89.4)

        assert "bBox=-91.2,29.0,-89.4,30.8" in fake.last_url

    def test_successful_fetch_returns_parsed_records(self, ingester, monkeypatch):
        now = datetime.now(timezone.utc)
        data = make_usgs_response(current_dt=now, stale_dt=now - timedelta(days=1000))
        fake = FakeRequests(response=FakeResponse(json_data=data))
        monkeypatch.setattr(flood_module, "requests", fake)

        result = ingester.fetch_river_gauges(29.0, 30.8, -91.2, -89.4)

        assert len(result) == 1

    def test_network_exception_returns_empty_list(self, ingester, monkeypatch):
        fake = FakeRequests(exception=ConnectionError("network down"))
        monkeypatch.setattr(flood_module, "requests", fake)

        result = ingester.fetch_river_gauges(29.0, 30.8, -91.2, -89.4)

        assert result == []


class TestFetchPrecipitation:
    """Tests for fetch_precipitation() - delegates to WeatherIngester, mocked."""

    def test_returns_none_when_weather_fetch_fails(self, ingester, monkeypatch):
        monkeypatch.setattr(ingester._weather_ingester, "fetch_weather", lambda lat, lon: None)

        result = ingester.fetch_precipitation(29.95, -90.07)

        assert result is None

    def test_extracts_rainfall_when_present(self, ingester, monkeypatch):
        fake_weather = {
            "observation_timestamp": "2026-07-22T12:00:00+00:00",
            "raw_data": json.dumps({"raw_response": {"rain": {"1h": 4.2}}}),
        }
        monkeypatch.setattr(ingester._weather_ingester, "fetch_weather", lambda lat, lon: fake_weather)

        result = ingester.fetch_precipitation(29.95, -90.07)

        assert result["value"] == 4.2
        assert result["hazard_type"] == "flood"
        assert result["source"] == "OPENWEATHER_RAIN"

    def test_defaults_to_zero_when_no_rain_field(self, ingester, monkeypatch):
        fake_weather = {
            "observation_timestamp": "2026-07-22T12:00:00+00:00",
            "raw_data": json.dumps({"raw_response": {}}),  # no 'rain' key - dry conditions
        }
        monkeypatch.setattr(ingester._weather_ingester, "fetch_weather", lambda lat, lon: fake_weather)

        result = ingester.fetch_precipitation(29.95, -90.07)

        assert result["value"] == 0.0


class TestStoreRecords:
    """Tests for store_records() against a temporary database."""

    def test_stores_all_records_and_returns_count(self, ingester, temp_db):
        now = datetime.now(timezone.utc)
        data = make_usgs_response(current_dt=now, stale_dt=now - timedelta(days=1000))
        records = ingester._parse_gauge_response(data)

        stored = ingester.store_records(records)

        assert stored == 1

    def test_database_row_count_matches(self, ingester, temp_db):
        now = datetime.now(timezone.utc)
        data = make_usgs_response(current_dt=now, stale_dt=now - timedelta(days=1000))
        records = ingester._parse_gauge_response(data)
        ingester.store_records(records)

        conn = db_module.get_db_connection()
        cursor = conn.execute("SELECT COUNT(*) FROM hazard_data WHERE source='USGS'")
        assert cursor.fetchone()[0] == 1
        conn.close()

    def test_empty_list_stores_nothing(self, ingester, temp_db):
        stored = ingester.store_records([])
        assert stored == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
