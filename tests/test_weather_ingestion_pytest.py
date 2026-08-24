"""
Pytest test suite for OpenWeatherMap weather ingestion (Task 11)

Run with: pytest tests/test_weather_ingestion_pytest.py -v

Uses a canned JSON response and a monkeypatched requests.get() so these
tests are deterministic, offline, and independent of any real API key -
no live network calls are made.
"""

import pytest

import src.database.db as db_module
import src.data_ingestion.weather_ingestion as weather_module
from src.data_ingestion.weather_ingestion import WeatherIngester

# A realistic OpenWeatherMap /data/2.5/weather response (metric units)
SAMPLE_RESPONSE = {
    "coord": {"lon": -116.7277, "lat": 33.7521},
    "weather": [{"id": 800, "main": "Clear", "description": "clear sky"}],
    "main": {
        "temp": 28.5,
        "feels_like": 27.9,
        "temp_min": 26.0,
        "temp_max": 31.0,
        "humidity": 22,
    },
    "wind": {"speed": 5.7, "deg": 270},
    "dt": 1753180800,  # a fixed unix timestamp
    "name": "Idyllwild",
}


class FakeResponse:
    """Minimal stand-in for requests.Response."""

    def __init__(self, json_data=None, status_code=200, text=""):
        self._json_data = json_data
        self.status_code = status_code
        self.text = text or str(json_data)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise weather_module.requests.exceptions.HTTPError(
                f"{self.status_code} Client Error: Unauthorized for url: "
                f"https://api.openweathermap.org/data/2.5/weather?appid=SECRET_KEY_VALUE"
            )

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
    """A WeatherIngester with deterministic, test-controlled attributes."""
    ing = WeatherIngester()
    ing.enabled = True
    ing.api_key = "SECRET_KEY_VALUE"
    ing.units = "metric"
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


class TestParseWeatherResponse:
    """Tests for _parse_weather_response() - pure parsing logic, no network."""

    def test_parses_valid_response(self, ingester):
        weather = ingester._parse_weather_response(SAMPLE_RESPONSE, 33.7521, -116.7277)
        assert weather is not None

    def test_normalized_fields_present(self, ingester):
        weather = ingester._parse_weather_response(SAMPLE_RESPONSE, 33.7521, -116.7277)
        for field in ["hazard_type", "source", "latitude", "longitude", "value",
                      "confidence", "observation_timestamp", "raw_data",
                      "temperature", "humidity", "wind_speed", "wind_direction"]:
            assert field in weather

    def test_hazard_type_and_source_are_correct(self, ingester):
        weather = ingester._parse_weather_response(SAMPLE_RESPONSE, 33.7521, -116.7277)
        assert weather["hazard_type"] == "weather"
        assert weather["source"] == "OPENWEATHER"

    def test_temperature_humidity_wind_parsed_correctly(self, ingester):
        weather = ingester._parse_weather_response(SAMPLE_RESPONSE, 33.7521, -116.7277)
        assert weather["temperature"] == 28.5
        assert weather["humidity"] == 22
        assert weather["wind_speed"] == 5.7
        assert weather["wind_direction"] == 270

    def test_value_field_mirrors_temperature(self, ingester):
        weather = ingester._parse_weather_response(SAMPLE_RESPONSE, 33.7521, -116.7277)
        assert weather["value"] == weather["temperature"]

    def test_missing_wind_defaults_to_zero(self, ingester):
        response_no_wind = {k: v for k, v in SAMPLE_RESPONSE.items() if k != "wind"}
        weather = ingester._parse_weather_response(response_no_wind, 33.7521, -116.7277)
        assert weather["wind_speed"] == 0.0
        assert weather["wind_direction"] == 0.0

    def test_malformed_response_returns_none(self, ingester):
        weather = ingester._parse_weather_response({"unexpected": "shape"}, 33.7521, -116.7277)
        assert weather is None

    def test_observation_timestamp_from_dt_field(self, ingester):
        weather = ingester._parse_weather_response(SAMPLE_RESPONSE, 33.7521, -116.7277)
        assert weather["observation_timestamp"].startswith("2025-07-22")


class TestFetchWeather:
    """Tests for fetch_weather() - HTTP call orchestration, mocked."""

    def test_disabled_source_returns_none_without_request(self, ingester, monkeypatch):
        ingester.enabled = False
        fake = FakeRequests()
        monkeypatch.setattr(weather_module, "requests", fake)

        result = ingester.fetch_weather(33.7521, -116.7277)

        assert result is None
        assert fake.calls == 0

    def test_missing_api_key_returns_none_without_request(self, ingester, monkeypatch):
        ingester.api_key = None
        fake = FakeRequests()
        monkeypatch.setattr(weather_module, "requests", fake)

        result = ingester.fetch_weather(33.7521, -116.7277)

        assert result is None
        assert fake.calls == 0

    def test_invalid_coordinates_return_none_without_request(self, ingester, monkeypatch):
        fake = FakeRequests()
        monkeypatch.setattr(weather_module, "requests", fake)

        result = ingester.fetch_weather(999, -116.7277)

        assert result is None
        assert fake.calls == 0

    def test_successful_fetch_returns_parsed_weather(self, ingester, monkeypatch):
        fake = FakeRequests(response=FakeResponse(json_data=SAMPLE_RESPONSE))
        monkeypatch.setattr(weather_module, "requests", fake)

        result = ingester.fetch_weather(33.7521, -116.7277)

        assert result is not None
        assert result["temperature"] == 28.5
        assert fake.calls == 1

    def test_network_exception_returns_none(self, ingester, monkeypatch):
        fake = FakeRequests(exception=ConnectionError("network down"))
        monkeypatch.setattr(weather_module, "requests", fake)

        result = ingester.fetch_weather(33.7521, -116.7277)

        assert result is None

    def test_api_key_is_redacted_from_error_logs(self, ingester, monkeypatch, caplog):
        """
        Regression test: an OpenWeatherMap error response includes the full
        request URL (with API key) in its exception text. The key must
        never appear in logged output.
        """
        error_response = FakeResponse(status_code=401)
        fake = FakeRequests(response=error_response)
        monkeypatch.setattr(weather_module, "requests", fake)

        with caplog.at_level("ERROR"):
            result = ingester.fetch_weather(33.7521, -116.7277)

        assert result is None
        assert ingester.api_key not in caplog.text
        assert "***" in caplog.text

    def test_401_error_does_not_raise(self, ingester, monkeypatch):
        error_response = FakeResponse(status_code=401)
        fake = FakeRequests(response=error_response)
        monkeypatch.setattr(weather_module, "requests", fake)

        result = ingester.fetch_weather(33.7521, -116.7277)

        assert result is None


class TestStoreWeather:
    """Tests for store_weather() against a temporary database."""

    def test_stores_weather_and_returns_true(self, ingester, temp_db):
        weather = ingester._parse_weather_response(SAMPLE_RESPONSE, 33.7521, -116.7277)
        stored = ingester.store_weather(weather)
        assert stored is True

    def test_database_row_count_matches(self, ingester, temp_db):
        weather = ingester._parse_weather_response(SAMPLE_RESPONSE, 33.7521, -116.7277)
        ingester.store_weather(weather)

        conn = db_module.get_db_connection()
        cursor = conn.execute("SELECT COUNT(*) FROM hazard_data WHERE source='OPENWEATHER'")
        assert cursor.fetchone()[0] == 1
        conn.close()

    def test_none_weather_stores_nothing(self, ingester, temp_db):
        stored = ingester.store_weather(None)
        assert stored is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
