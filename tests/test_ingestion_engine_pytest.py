"""
Pytest test suite for IngestionEngine (Task 14)

Run with: pytest tests/test_ingestion_engine_pytest.py -v

Fully offline: PropertyDAO and all three ingesters are replaced with
in-test fakes, so these tests never touch the network or a real API key.
Uses a temporary SQLite database for the freshness-check queries.
"""

from datetime import timedelta

import pytest

import src.database.db as db_module
from src.data_ingestion.ingestion_engine import IngestionEngine
from src.utils import get_utc_now


def _insert_records(records):
    """Test-double helper: actually insert into hazard_data (like the real
    store_* methods do), so freshness-check tests see real rows."""
    if not records:
        return 0
    conn = db_module.get_db_connection()
    try:
        for r in records:
            conn.execute(
                """
                INSERT INTO hazard_data (
                    hazard_type, source, latitude, longitude, value,
                    confidence, observation_timestamp, ingested_timestamp, raw_data
                ) VALUES (
                    :hazard_type, :source, :latitude, :longitude, :value,
                    :confidence, :observation_timestamp, :ingested_timestamp, :raw_data
                )
                """,
                {**r, "ingested_timestamp": get_utc_now().isoformat()},
            )
        conn.commit()
    finally:
        conn.close()
    return len(records)


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


class FakePropertyDAO:
    """Stand-in for PropertyDAO with a small, fixed portfolio."""

    def __init__(self, properties):
        self._properties = properties

    def get_all_properties(self):
        return self._properties

    def count_properties(self):
        return len(self._properties)


class FakeWildFireIngester:
    def __init__(self, fires_to_return=None, raise_error=False):
        self.fires_to_return = fires_to_return or []
        self.raise_error = raise_error
        self.fetch_calls = []
        self.store_calls = []

    def fetch_active_fires(self, lat_min, lat_max, lon_min, lon_max):
        if self.raise_error:
            raise RuntimeError("simulated NASA FIRMS failure")
        self.fetch_calls.append((lat_min, lat_max, lon_min, lon_max))
        return self.fires_to_return

    def store_fires(self, fires):
        self.store_calls.append(fires)
        return _insert_records(fires)


class FakeWeatherIngester:
    def __init__(self, weather_to_return=None):
        self.weather_to_return = weather_to_return
        self.fetch_calls = []

    def fetch_weather(self, lat, lon):
        self.fetch_calls.append((lat, lon))
        return self.weather_to_return

    def store_weather(self, weather):
        if weather is None:
            return False
        _insert_records([weather])
        return True


class FakeFloodIngester:
    def __init__(self, gauges_to_return=None, precip_to_return=None):
        self.gauges_to_return = gauges_to_return or []
        self.precip_to_return = precip_to_return
        self.gauge_calls = []
        self.precip_calls = []

    def fetch_river_gauges(self, lat_min, lat_max, lon_min, lon_max):
        self.gauge_calls.append((lat_min, lat_max, lon_min, lon_max))
        return self.gauges_to_return

    def fetch_precipitation(self, lat, lon):
        self.precip_calls.append((lat, lon))
        return self.precip_to_return

    def store_records(self, records):
        return _insert_records(records)


def make_engine(temp_db, properties, monkeypatch, fires=None, gauges=None,
                 weather=None, precip=None, wildfire_error=False):
    """Build an IngestionEngine with all external dependencies faked."""
    engine = IngestionEngine.__new__(IngestionEngine)  # bypass __init__'s real ingesters
    engine.cell_size_degrees = 0.5
    engine.freshness_minutes = 4
    engine.bbox_buffer_degrees = 0.5
    engine._property_dao = FakePropertyDAO(properties)
    engine._wildfire = FakeWildFireIngester(fires, raise_error=wildfire_error)
    engine._weather = FakeWeatherIngester(weather)
    engine._flood = FakeFloodIngester(gauges, precip)

    from src.data_ingestion.rate_limiter import RateLimiter
    engine._rate_limiters = {
        "NASA_FIRMS": RateLimiter(6000),  # effectively no wait in tests
        "OPENWEATHER": RateLimiter(6000),
        "OPENWEATHER_RAIN": RateLimiter(6000),
        "USGS": RateLimiter(6000),
    }
    return engine


SAMPLE_FIRE = {
    "hazard_type": "wildfire", "source": "NASA_FIRMS",
    "latitude": 33.75, "longitude": -116.75, "value": 10.0,
    "confidence": 0.6, "observation_timestamp": get_utc_now().isoformat(),
    "raw_data": "{}",
}
SAMPLE_GAUGE = {
    # Coordinates deliberately match ONE_PROPERTY's grid cell (33.75, -116.75)
    # so freshness-check tests using ONE_PROPERTY find this row within its bbox.
    "hazard_type": "flood", "source": "USGS",
    "latitude": 33.75, "longitude": -116.75, "value": 3.0,
    "confidence": 1.0, "observation_timestamp": get_utc_now().isoformat(),
    "raw_data": "{}",
}
SAMPLE_WEATHER = {
    "hazard_type": "weather", "source": "OPENWEATHER",
    "latitude": 33.75, "longitude": -116.75, "value": 25.0,
    "confidence": 1.0, "observation_timestamp": get_utc_now().isoformat(),
    "raw_data": "{}", "temperature": 25.0,
}
SAMPLE_PRECIP = {
    "hazard_type": "flood", "source": "OPENWEATHER_RAIN",
    "latitude": 33.75, "longitude": -116.75, "value": 2.0,
    "confidence": 1.0, "observation_timestamp": get_utc_now().isoformat(),
    "raw_data": "{}",
}

ONE_PROPERTY = [{"property_id": 1, "latitude": 33.7521, "longitude": -116.7277}]
TWO_NEARBY_PROPERTIES = [
    {"property_id": 1, "latitude": 33.7521, "longitude": -116.7277},
    {"property_id": 2, "latitude": 33.9425, "longitude": -116.7953},
]
TWO_FAR_PROPERTIES = [
    {"property_id": 1, "latitude": 33.7521, "longitude": -116.7277},
    {"property_id": 2, "latitude": 29.9511, "longitude": -90.0715},
]


class TestGridCellGrouping:
    """Tests for _get_portfolio_cells() - the geographic clustering step."""

    def test_nearby_properties_share_one_cell(self, temp_db, monkeypatch):
        engine = make_engine(temp_db, TWO_NEARBY_PROPERTIES, monkeypatch)
        cells = engine._get_portfolio_cells()
        assert len(cells) == 1

    def test_far_properties_produce_separate_cells(self, temp_db, monkeypatch):
        engine = make_engine(temp_db, TWO_FAR_PROPERTIES, monkeypatch)
        cells = engine._get_portfolio_cells()
        assert len(cells) == 2

    def test_cell_count_never_exceeds_property_count(self, temp_db, monkeypatch):
        engine = make_engine(temp_db, TWO_NEARBY_PROPERTIES, monkeypatch)
        cells = engine._get_portfolio_cells()
        assert len(cells) <= len(TWO_NEARBY_PROPERTIES)


class TestFreshnessCheck:
    """Tests for _is_cell_fresh()."""

    def test_no_existing_data_is_not_fresh(self, temp_db, monkeypatch):
        engine = make_engine(temp_db, ONE_PROPERTY, monkeypatch)
        assert engine._is_cell_fresh("NASA_FIRMS", 33, 34, -117, -116) is False

    def test_recent_data_is_fresh(self, temp_db, monkeypatch):
        engine = make_engine(temp_db, ONE_PROPERTY, monkeypatch)
        conn = db_module.get_db_connection()
        conn.execute(
            "INSERT INTO hazard_data (hazard_type, source, latitude, longitude, "
            "value, confidence, observation_timestamp, ingested_timestamp) "
            "VALUES ('wildfire', 'NASA_FIRMS', 33.5, -116.5, 1.0, 0.5, ?, ?)",
            (get_utc_now().isoformat(), get_utc_now().isoformat()),
        )
        conn.commit()
        conn.close()

        assert engine._is_cell_fresh("NASA_FIRMS", 33, 34, -117, -116) is True

    def test_old_data_is_not_fresh(self, temp_db, monkeypatch):
        engine = make_engine(temp_db, ONE_PROPERTY, monkeypatch)
        old_ts = (get_utc_now() - timedelta(minutes=10)).isoformat()
        conn = db_module.get_db_connection()
        conn.execute(
            "INSERT INTO hazard_data (hazard_type, source, latitude, longitude, "
            "value, confidence, observation_timestamp, ingested_timestamp) "
            "VALUES ('wildfire', 'NASA_FIRMS', 33.5, -116.5, 1.0, 0.5, ?, ?)",
            (old_ts, old_ts),
        )
        conn.commit()
        conn.close()

        assert engine._is_cell_fresh("NASA_FIRMS", 33, 34, -117, -116) is False

    def test_different_source_does_not_count_as_fresh(self, temp_db, monkeypatch):
        engine = make_engine(temp_db, ONE_PROPERTY, monkeypatch)
        conn = db_module.get_db_connection()
        conn.execute(
            "INSERT INTO hazard_data (hazard_type, source, latitude, longitude, "
            "value, confidence, observation_timestamp, ingested_timestamp) "
            "VALUES ('weather', 'OPENWEATHER', 33.5, -116.5, 1.0, 1.0, ?, ?)",
            (get_utc_now().isoformat(), get_utc_now().isoformat()),
        )
        conn.commit()
        conn.close()

        assert engine._is_cell_fresh("NASA_FIRMS", 33, 34, -117, -116) is False


class TestRunIngestionCycle:
    """Tests for the full orchestrated cycle."""

    def test_counts_all_four_sources(self, temp_db, monkeypatch):
        engine = make_engine(
            temp_db, ONE_PROPERTY, monkeypatch,
            fires=[SAMPLE_FIRE], gauges=[SAMPLE_GAUGE],
            weather=SAMPLE_WEATHER, precip=SAMPLE_PRECIP,
        )
        summary = engine.run_ingestion_cycle()

        assert summary["fires_ingested"] == 1
        assert summary["gauge_readings"] == 1
        assert summary["weather_points"] == 1
        assert summary["precipitation_points"] == 1
        assert summary["cells_processed"] == 1
        assert summary["errors"] == []

    def test_second_run_is_fully_skipped_as_fresh(self, temp_db, monkeypatch):
        engine = make_engine(
            temp_db, ONE_PROPERTY, monkeypatch,
            fires=[SAMPLE_FIRE], gauges=[SAMPLE_GAUGE],
            weather=SAMPLE_WEATHER, precip=SAMPLE_PRECIP,
        )
        engine.run_ingestion_cycle()
        second_summary = engine.run_ingestion_cycle()

        assert second_summary["cells_processed"] == 0
        assert second_summary["cells_skipped_fresh"] == 4  # all 4 sources skipped

    def test_wildfire_failure_does_not_block_other_sources(self, temp_db, monkeypatch):
        engine = make_engine(
            temp_db, ONE_PROPERTY, monkeypatch,
            gauges=[SAMPLE_GAUGE], weather=SAMPLE_WEATHER, precip=SAMPLE_PRECIP,
            wildfire_error=True,
        )
        summary = engine.run_ingestion_cycle()

        assert summary["fires_ingested"] == 0
        assert len(summary["errors"]) == 1
        assert "wildfire" in summary["errors"][0]
        # other sources still succeeded despite wildfire failing
        assert summary["gauge_readings"] == 1
        assert summary["weather_points"] == 1
        assert summary["precipitation_points"] == 1

    def test_no_weather_data_available_does_not_error(self, temp_db, monkeypatch):
        engine = make_engine(
            temp_db, ONE_PROPERTY, monkeypatch,
            fires=[SAMPLE_FIRE], gauges=[SAMPLE_GAUGE],
            weather=None, precip=None,
        )
        summary = engine.run_ingestion_cycle()

        assert summary["weather_points"] == 0
        assert summary["precipitation_points"] == 0
        assert summary["errors"] == []

    def test_empty_portfolio_completes_cleanly(self, temp_db, monkeypatch):
        engine = make_engine(temp_db, [], monkeypatch)
        summary = engine.run_ingestion_cycle()

        assert summary["cells_processed"] == 0
        assert summary["errors"] == []

    def test_rate_limiter_invoked_per_source_call(self, temp_db, monkeypatch):
        engine = make_engine(
            temp_db, ONE_PROPERTY, monkeypatch,
            fires=[SAMPLE_FIRE], gauges=[SAMPLE_GAUGE],
            weather=SAMPLE_WEATHER, precip=SAMPLE_PRECIP,
        )
        calls = {"count": 0}
        original = engine._rate_limiters["NASA_FIRMS"].wait_if_needed

        def spy():
            calls["count"] += 1
            return original()

        engine._rate_limiters["NASA_FIRMS"].wait_if_needed = spy
        engine.run_ingestion_cycle()

        assert calls["count"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
