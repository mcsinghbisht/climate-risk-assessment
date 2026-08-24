"""
Scenario-Based Integration Tests (Task 30)

Run with: pytest tests/test_integration.py -v

End-to-end tests of key workflows using mock API responses
(tests/fixtures/mock_hazard_data.json) so the full ingestion -> scoring ->
alerting -> portfolio chain can be exercised with no live network calls,
using the real ingesters/scorers/aggregators - only the HTTP layer
(`requests.get`) is faked, via the same monkeypatch-the-module pattern
already established in test_wildfire_ingestion_pytest.py etc. (Tasks 10-12).

Unlike Tasks 28/29 (unit-level gap-filling), this is deliberately
scenario-driven: each test tells a short story ("a property near an active
fire", "a floodplain property during heavy rain") end-to-end through real
components, rather than isolating one function's branches.
"""

import json
from pathlib import Path

import pytest

import src.database.db as db_module
import src.data_ingestion.wildfire_ingestion as wf_module
import src.data_ingestion.weather_ingestion as weather_module
import src.data_ingestion.flood_ingestion as flood_module
from src.data_ingestion.wildfire_ingestion import WildFireIngester
from src.data_ingestion.weather_ingestion import WeatherIngester
from src.data_ingestion.flood_ingestion import FloodIngester
from src.data_ingestion.ingestion_engine import IngestionEngine
from src.risk_scoring.scoring_engine import RiskScoringEngine
from src.continuous_monitoring.monitor import Monitor
from src.portfolio.aggregator import PortfolioAggregator
from src.portfolio.hotspot_detector import HotspotDetector
from src.utils import get_utc_now

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "mock_hazard_data.json"


def load_fixtures():
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def build_firms_csv(fixtures):
    return fixtures["firms_csv_header"] + "\n" + fixtures["firms_csv_row_active_fire"] + "\n"


def build_usgs_response(fixtures):
    """Injects a fresh dateTime so the gauge reading never reads as stale (>48h old)."""
    response = json.loads(json.dumps(fixtures["usgs_gauge_response_template"]))
    response["value"]["timeSeries"][0]["values"][0]["value"][0]["dateTime"] = get_utc_now().isoformat()
    return response


class FakeResponse:
    """Minimal stand-in for requests.Response, text or JSON."""

    def __init__(self, text=None, json_data=None, status_code=200):
        self.text = text if text is not None else ""
        self._json_data = json_data
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")

    def json(self):
        return self._json_data


class FakeRequests:
    """Stand-in for the `requests` module - always returns the same canned
    response regardless of URL, since these tests use one fixed fixture
    dataset rather than simulating per-region API variation."""

    def __init__(self, response):
        self._response = response
        self.calls = 0

    def get(self, url, timeout=None):
        self.calls += 1
        return self._response

    class exceptions:
        RequestException = Exception
        HTTPError = Exception


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test_climate_risk.db"
    monkeypatch.setattr(db_module, "DB_PATH", db_path)

    conn = db_module.get_db_connection()
    schema = db_module.get_schema()
    for table in ("properties", "hazard_data", "risk_assessments", "alerts", "alert_history"):
        conn.execute(schema[table])
    conn.commit()
    conn.close()
    return db_path


def add_property(property_id, lat, lon, is_in_floodplain=False, is_in_wui=False):
    conn = db_module.get_db_connection()
    conn.execute(
        "INSERT INTO properties (property_id, address, latitude, longitude, "
        "is_in_floodplain, is_in_wildland_urban_interface) VALUES (?, ?, ?, ?, ?, ?)",
        (property_id, f"Property {property_id}", lat, lon, is_in_floodplain, is_in_wui),
    )
    conn.commit()
    conn.close()


@pytest.fixture
def mocked_ingesters(monkeypatch):
    """
    Real ingesters (WildFireIngester/WeatherIngester/FloodIngester), forced
    enabled with fake API keys, and with each module's `requests` attribute
    monkeypatched to return the fixture-based canned responses - a fully
    offline stand-in for all three live APIs at once.
    """
    fixtures = load_fixtures()

    firms_response = FakeResponse(text=build_firms_csv(fixtures))
    weather_response = FakeResponse(json_data=fixtures["openweather_hot_dry_windy_rainy"])
    usgs_response = FakeResponse(json_data=build_usgs_response(fixtures))

    monkeypatch.setattr(wf_module, "requests", FakeRequests(firms_response))
    monkeypatch.setattr(weather_module, "requests", FakeRequests(weather_response))
    monkeypatch.setattr(flood_module, "requests", FakeRequests(usgs_response))

    wildfire = WildFireIngester()
    wildfire.enabled = True
    wildfire.api_key = "TEST_FIRMS_KEY"

    weather = WeatherIngester()
    weather.enabled = True
    weather.api_key = "TEST_OWM_KEY"

    flood = FloodIngester()
    flood.enabled = True
    # FloodIngester wraps its OWN WeatherIngester instance for precipitation -
    # a separate object from `weather` above, so it needs enabling too.
    flood._weather_ingester.enabled = True
    flood._weather_ingester.api_key = "TEST_OWM_KEY"

    return {"wildfire": wildfire, "weather": weather, "flood": flood, "fixtures": fixtures}


class TestFullMonitoringCycle:
    """test_full_monitoring_cycle: ingest -> score -> alert -> store, via
    the real production entrypoint (Monitor), with only the HTTP layer
    mocked."""

    def test_full_cycle_completes_without_errors(self, temp_db, monkeypatch):
        fixtures = load_fixtures()
        monkeypatch.setattr(wf_module, "requests", FakeRequests(FakeResponse(text=build_firms_csv(fixtures))))
        monkeypatch.setattr(weather_module, "requests",
                             FakeRequests(FakeResponse(json_data=fixtures["openweather_hot_dry_windy_rainy"])))
        monkeypatch.setattr(flood_module, "requests",
                             FakeRequests(FakeResponse(json_data=build_usgs_response(fixtures))))

        add_property(1, lat=34.05, lon=-118.0, is_in_wui=True)   # near the mock fire
        add_property(2, lat=29.95, lon=-90.07, is_in_floodplain=True)  # near the mock gauge

        monitor = Monitor()
        for ingester in (monitor.ingestion_engine._wildfire, monitor.ingestion_engine._weather,
                         monitor.ingestion_engine._flood, monitor.ingestion_engine._flood._weather_ingester):
            ingester.enabled = True
        monitor.ingestion_engine._wildfire.api_key = "TEST_FIRMS_KEY"
        monitor.ingestion_engine._weather.api_key = "TEST_OWM_KEY"
        monitor.ingestion_engine._flood._weather_ingester.api_key = "TEST_OWM_KEY"

        summary = monitor.run_monitoring_cycle()

        assert summary["errors"] == []
        assert summary["properties_scored"] == 2
        assert summary["hazard_records_ingested"] > 0

        conn = db_module.get_db_connection()
        assessments = conn.execute("SELECT * FROM risk_assessments").fetchall()
        conn.close()
        assert len(assessments) == 2


class TestPropertyScoringWithNearbyFire:
    """test_property_scoring_with_nearby_fire: ingestion + scoring for a
    property close to an active fire produces a meaningfully elevated
    wildfire score."""

    def test_nearby_fire_produces_elevated_wildfire_score(self, temp_db, mocked_ingesters):
        # ~11km north of the mock fire at (34.0, -118.0) - well within the
        # default 50km proximity_max_km, and downwind of wind_direction=180
        # (blowing from the south, toward the north).
        add_property(1, lat=34.1, lon=-118.0, is_in_wui=True)

        fires = mocked_ingesters["wildfire"].fetch_active_fires(33.5, 34.5, -118.5, -117.5)
        mocked_ingesters["wildfire"].store_fires(fires)
        weather = mocked_ingesters["weather"].fetch_weather(34.1, -118.0)
        mocked_ingesters["weather"].store_weather(weather)

        summary = RiskScoringEngine().score_all_properties()
        assert summary["properties_scored"] == 1

        conn = db_module.get_db_connection()
        row = conn.execute(
            "SELECT wildfire_risk_score FROM risk_assessments WHERE property_id = 1"
        ).fetchone()
        conn.close()

        # Close proximity + downwind strong wind + hot/dry conditions should
        # combine to a clearly-elevated score, not just barely above zero.
        assert row["wildfire_risk_score"] > 30.0


class TestFloodRiskInFloodplain:
    """test_flood_risk_in_floodplain: a floodplain property scores higher
    flood risk than an otherwise-identical non-floodplain property, given
    the same rainfall/gauge conditions."""

    def test_floodplain_property_scores_higher_than_non_floodplain(self, temp_db, mocked_ingesters):
        add_property(1, lat=29.9511, lon=-90.0715, is_in_floodplain=True)
        add_property(2, lat=29.9511, lon=-90.0715, is_in_floodplain=False)

        gauges = mocked_ingesters["flood"].fetch_river_gauges(29.0, 30.8, -91.2, -89.4)
        mocked_ingesters["flood"].store_records(gauges)
        precip = mocked_ingesters["flood"].fetch_precipitation(29.9511, -90.0715)
        mocked_ingesters["flood"].store_records([precip])

        RiskScoringEngine().score_all_properties()

        conn = db_module.get_db_connection()
        floodplain_score = conn.execute(
            "SELECT flood_risk_score FROM risk_assessments WHERE property_id = 1"
        ).fetchone()["flood_risk_score"]
        non_floodplain_score = conn.execute(
            "SELECT flood_risk_score FROM risk_assessments WHERE property_id = 2"
        ).fetchone()["flood_risk_score"]
        conn.close()

        assert floodplain_score > non_floodplain_score
        assert floodplain_score > 0


class TestPortfolioAggregation:
    """test_portfolio_aggregation: after ingesting + scoring a small mock
    portfolio, PortfolioAggregator and HotspotDetector report correctly
    against the real resulting data."""

    def test_metrics_and_hotspots_reflect_real_scored_portfolio(self, temp_db, mocked_ingesters):
        add_property(1, lat=34.1, lon=-118.0, is_in_wui=True)     # near fire -> elevated wildfire risk
        add_property(2, lat=34.11, lon=-118.01, is_in_wui=True)   # same cluster
        add_property(3, lat=29.9511, lon=-90.0715, is_in_floodplain=True)  # near gauge/rain
        add_property(4, lat=45.0, lon=-70.0)  # far from everything -> low risk

        fires = mocked_ingesters["wildfire"].fetch_active_fires(33.5, 34.5, -118.5, -117.5)
        mocked_ingesters["wildfire"].store_fires(fires)
        for lat, lon in ((34.1, -118.0), (34.11, -118.01), (29.9511, -90.0715), (45.0, -70.0)):
            weather = mocked_ingesters["weather"].fetch_weather(lat, lon)
            mocked_ingesters["weather"].store_weather(weather)
        gauges = mocked_ingesters["flood"].fetch_river_gauges(29.0, 30.8, -91.2, -89.4)
        mocked_ingesters["flood"].store_records(gauges)
        precip = mocked_ingesters["flood"].fetch_precipitation(29.9511, -90.0715)
        mocked_ingesters["flood"].store_records([precip])

        RiskScoringEngine().score_all_properties()

        metrics = PortfolioAggregator().get_portfolio_metrics()
        assert metrics["total_properties"] == 4
        assert metrics["assessed_properties"] == 4
        total_bucketed = sum(v["count"] for v in metrics["risk_level_distribution"].values())
        assert total_bucketed == 4

        hotspots = HotspotDetector().detect_hotspots(radius_km=50)
        # Properties 1 and 2 are a close, elevated-risk pair - not enough
        # alone to guarantee a hotspot (min_properties defaults to 3), but
        # detect_hotspots() should run cleanly against real scored data
        # either way.
        assert isinstance(hotspots, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
