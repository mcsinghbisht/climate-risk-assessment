"""
Pytest test suite for NASA FIRMS wildfire ingestion (Task 10)

Run with: pytest tests/test_wildfire_ingestion_pytest.py -v

Uses canned CSV responses and a monkeypatched requests.get() so these tests
are deterministic, offline, and independent of any real API key - no live
network calls are made.
"""

import pytest

import src.database.db as db_module
import src.data_ingestion.wildfire_ingestion as wf_module
from src.data_ingestion.wildfire_ingestion import WildFireIngester

# A realistic FIRMS VIIRS area-API CSV response (2 valid rows)
SAMPLE_CSV = (
    "latitude,longitude,bright_ti4,scan,track,acq_date,acq_time,satellite,"
    "instrument,confidence,version,bright_ti5,frp,daynight\n"
    "36.3569,-114.91347,307.46,0.78,0.78,2026-07-20,0833,N,VIIRS,n,2.0NRT,288.16,8.53,N\n"
    "34.0522,-118.2437,320.10,0.50,0.50,2026-07-20,1245,N,VIIRS,h,2.0NRT,290.00,55.20,D\n"
)

INVALID_KEY_RESPONSE = "Invalid MAP_KEY"


class FakeResponse:
    """Minimal stand-in for requests.Response."""

    def __init__(self, text, status_code=200):
        self.text = text
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise wf_module.requests.exceptions.HTTPError(f"HTTP {self.status_code}")


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
    """A WildFireIngester with deterministic, test-controlled attributes."""
    ing = WildFireIngester()
    ing.enabled = True
    ing.api_key = "TEST_KEY"
    ing.default_days = 3
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


class TestParseCsvResponse:
    """Tests for _parse_csv_response() - pure parsing logic, no network."""

    def test_parses_valid_rows(self, ingester):
        fires = ingester._parse_csv_response(SAMPLE_CSV)
        assert len(fires) == 2

    def test_normalized_fields_present(self, ingester):
        fires = ingester._parse_csv_response(SAMPLE_CSV)
        fire = fires[0]
        for field in ["hazard_type", "source", "latitude", "longitude",
                       "value", "confidence", "observation_timestamp", "raw_data"]:
            assert field in fire

    def test_hazard_type_and_source_are_correct(self, ingester):
        fires = ingester._parse_csv_response(SAMPLE_CSV)
        assert fires[0]["hazard_type"] == "wildfire"
        assert fires[0]["source"] == "NASA_FIRMS"

    def test_frp_parsed_as_float(self, ingester):
        fires = ingester._parse_csv_response(SAMPLE_CSV)
        assert fires[0]["value"] == 8.53
        assert fires[1]["value"] == 55.20

    def test_confidence_letter_codes_mapped_correctly(self, ingester):
        fires = ingester._parse_csv_response(SAMPLE_CSV)
        assert fires[0]["confidence"] == 0.6  # 'n' -> nominal
        assert fires[1]["confidence"] == 0.9  # 'h' -> high

    def test_unknown_confidence_code_defaults_to_0_5(self, ingester):
        csv_text = SAMPLE_CSV.replace(",n,2.0NRT,", ",x,2.0NRT,")
        fires = ingester._parse_csv_response(csv_text)
        assert fires[0]["confidence"] == 0.5

    def test_invalid_coordinates_are_skipped(self, ingester):
        bad_row = SAMPLE_CSV + "999,-114.9,300,0.5,0.5,2026-07-20,0900,N,VIIRS,n,2.0NRT,280,5.0,N\n"
        fires = ingester._parse_csv_response(bad_row)
        assert len(fires) == 2  # the 999-latitude row is dropped

    def test_error_response_returns_empty_list(self, ingester):
        fires = ingester._parse_csv_response(INVALID_KEY_RESPONSE)
        assert fires == []

    def test_observation_timestamp_combines_date_and_time(self, ingester):
        fires = ingester._parse_csv_response(SAMPLE_CSV)
        assert fires[0]["observation_timestamp"].startswith("2026-07-20T08:33:00")


class TestFetchActiveFires:
    """Tests for fetch_active_fires() - HTTP call orchestration, mocked."""

    def test_disabled_source_returns_empty_without_request(self, ingester, monkeypatch):
        ingester.enabled = False
        fake = FakeRequests()
        monkeypatch.setattr(wf_module, "requests", fake)

        result = ingester.fetch_active_fires(32, 42, -124, -114)

        assert result == []
        assert fake.calls == 0

    def test_missing_api_key_returns_empty_without_request(self, ingester, monkeypatch):
        ingester.api_key = None
        fake = FakeRequests()
        monkeypatch.setattr(wf_module, "requests", fake)

        result = ingester.fetch_active_fires(32, 42, -124, -114)

        assert result == []
        assert fake.calls == 0

    def test_successful_fetch_returns_parsed_fires(self, ingester, monkeypatch):
        fake = FakeRequests(response=FakeResponse(SAMPLE_CSV))
        monkeypatch.setattr(wf_module, "requests", fake)

        result = ingester.fetch_active_fires(32, 42, -124, -114, days=3)

        assert len(result) == 2
        assert fake.calls == 1

    def test_bounding_box_order_is_west_south_east_north(self, ingester, monkeypatch):
        fake = FakeRequests(response=FakeResponse(SAMPLE_CSV))
        monkeypatch.setattr(wf_module, "requests", fake)

        ingester.fetch_active_fires(lat_min=32, lat_max=42, lon_min=-124, lon_max=-114, days=3)

        # URL segment should contain "-124,32,-114,42" (west,south,east,north)
        assert "-124,32,-114,42" in fake.last_url

    def test_day_range_above_max_is_clamped(self, ingester, monkeypatch):
        fake = FakeRequests(response=FakeResponse(SAMPLE_CSV))
        monkeypatch.setattr(wf_module, "requests", fake)

        ingester.fetch_active_fires(32, 42, -124, -114, days=10)

        assert fake.last_url.endswith("/5")

    def test_day_range_below_min_is_clamped(self, ingester, monkeypatch):
        fake = FakeRequests(response=FakeResponse(SAMPLE_CSV))
        monkeypatch.setattr(wf_module, "requests", fake)

        ingester.fetch_active_fires(32, 42, -124, -114, days=0)

        assert fake.last_url.endswith("/1")

    def test_network_exception_returns_empty_list(self, ingester, monkeypatch):
        fake = FakeRequests(exception=ConnectionError("network down"))
        monkeypatch.setattr(wf_module, "requests", fake)

        result = ingester.fetch_active_fires(32, 42, -124, -114)

        assert result == []


class TestStoreFires:
    """Tests for store_fires() against a temporary database."""

    def test_stores_all_fires_and_returns_count(self, ingester, temp_db):
        fires = ingester._parse_csv_response(SAMPLE_CSV)
        stored = ingester.store_fires(fires)
        assert stored == 2

    def test_database_row_count_matches(self, ingester, temp_db):
        fires = ingester._parse_csv_response(SAMPLE_CSV)
        ingester.store_fires(fires)

        conn = db_module.get_db_connection()
        cursor = conn.execute("SELECT COUNT(*) FROM hazard_data")
        assert cursor.fetchone()[0] == 2
        conn.close()

    def test_empty_list_stores_nothing(self, ingester, temp_db):
        stored = ingester.store_fires([])
        assert stored == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
