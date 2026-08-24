"""
Pytest test suite for src/risk_scoring/ (Task 29)

Run with: pytest tests/test_risk_scoring.py -v
Coverage:  pytest tests/test_risk_scoring.py --cov=src/risk_scoring --cov-report=term-missing

This is a gap-filling, edge-case-focused suite, not a from-scratch one:
WildFireScorer, FloodScorer, and RiskAggregator already have thorough
per-component suites (test_wildfire_scorer_pytest.py, test_flood_scorer_pytest.py,
test_aggregator_pytest.py, all at 100% coverage as of Task 28). This file
covers what the task spec explicitly calls for - proximity, wind escalation,
rainfall, score combination, and edge cases (score=0, score=100, missing
data, invalid coordinates) - plus the two remaining real gaps found by
checking coverage first: RiskScoringEngine's high/critical-count branches
and per-property error isolation (scoring_engine.py), and the malformed-JSON
fallback in scoring_utils.py's raw_data parsers.
"""

import pytest

from src.risk_scoring.wildfire_scorer import WildFireScorer
from src.risk_scoring.flood_scorer import FloodScorer
from src.risk_scoring.aggregator import RiskAggregator
from src.risk_scoring.scoring_engine import RiskScoringEngine
from src.risk_scoring.scoring_utils import parse_weather_extras, parse_gauge_extras


# ---------------------------------------------------------------------------
# WildFireScorer
# ---------------------------------------------------------------------------

class TestWildfireScorerProximity:
    def test_closer_fire_scores_higher(self):
        scorer = WildFireScorer()
        property_data = {"property_id": 1, "latitude": 33.75, "longitude": -116.72}

        near_fire = [{
            "hazard_type": "wildfire", "source": "NASA_FIRMS",
            "latitude": 33.751, "longitude": -116.721, "value": 0,
            "confidence": 0.9, "observation_timestamp": "2026-07-22T10:00:00Z",
        }]
        far_fire = [{
            "hazard_type": "wildfire", "source": "NASA_FIRMS",
            "latitude": 34.5, "longitude": -117.5, "value": 0,
            "confidence": 0.9, "observation_timestamp": "2026-07-22T10:00:00Z",
        }]

        near_result = scorer.calculate_risk_for_property(property_data, near_fire)
        far_result = scorer.calculate_risk_for_property(property_data, far_fire)
        assert near_result["score"] > far_result["score"]

    def test_fire_beyond_proximity_max_km_scores_zero(self):
        scorer = WildFireScorer()
        property_data = {"property_id": 1, "latitude": 0.0, "longitude": 0.0}
        distant_fire = [{
            "hazard_type": "wildfire", "source": "NASA_FIRMS",
            "latitude": 10.0, "longitude": 10.0, "value": 100,
            "confidence": 0.9, "observation_timestamp": "2026-07-22T10:00:00Z",
        }]
        result = scorer.calculate_risk_for_property(property_data, distant_fire)
        assert result["score"] == 0.0
        assert result["factors"]["proximity_score"] == 0.0

    def test_nearest_of_multiple_fires_is_used(self):
        scorer = WildFireScorer()
        property_data = {"property_id": 1, "latitude": 33.75, "longitude": -116.72}
        fires = [
            {"hazard_type": "wildfire", "source": "NASA_FIRMS", "latitude": 34.5,
             "longitude": -117.5, "value": 0, "confidence": 0.9,
             "observation_timestamp": "2026-07-22T10:00:00Z"},
            {"hazard_type": "wildfire", "source": "NASA_FIRMS", "latitude": 33.751,
             "longitude": -116.721, "value": 0, "confidence": 0.9,
             "observation_timestamp": "2026-07-22T10:00:00Z"},
        ]
        result = scorer.calculate_risk_for_property(property_data, fires)
        assert result["factors"]["distance_km"] < 1.0


class TestWildfireScorerWindEscalation:
    def test_downwind_strong_wind_increases_score(self):
        scorer = WildFireScorer()
        property_data = {"property_id": 1, "latitude": 33.75, "longitude": -116.72}
        fire_lat, fire_lon = 33.751, -116.721

        no_wind = [{
            "hazard_type": "wildfire", "source": "NASA_FIRMS",
            "latitude": fire_lat, "longitude": fire_lon, "value": 0,
            "confidence": 0.9, "observation_timestamp": "2026-07-22T10:00:00Z",
        }]
        # Property is at bearing ~140 (SE) from the fire; wind "direction" is
        # where it blows FROM, so wind blowing toward the property (making it
        # downwind) comes from ~140-180=-40 -> 320 (NW).
        with_downwind = no_wind + [{
            "hazard_type": "weather", "source": "OPENWEATHER",
            "latitude": 33.75, "longitude": -116.72, "value": 20.0,
            "confidence": 1.0, "observation_timestamp": "2026-07-22T10:00:00Z",
            "raw_data": '{"temperature": 20.0, "humidity": 40.0, "wind_speed": 15.0, "wind_direction": 320}',
        }]

        result_no_wind = scorer.calculate_risk_for_property(property_data, no_wind)
        result_with_wind = scorer.calculate_risk_for_property(property_data, with_downwind)
        assert result_with_wind["factors"]["wind_score"] > 0
        assert result_no_wind["factors"]["wind_score"] == 0
        assert result_with_wind["score"] > result_no_wind["score"]

    def test_wind_below_speed_threshold_scores_zero(self):
        scorer = WildFireScorer()
        property_data = {"property_id": 1, "latitude": 33.75, "longitude": -116.72}
        hazard_data = [
            {"hazard_type": "wildfire", "source": "NASA_FIRMS", "latitude": 33.751,
             "longitude": -116.721, "value": 0, "confidence": 0.9,
             "observation_timestamp": "2026-07-22T10:00:00Z"},
            {"hazard_type": "weather", "source": "OPENWEATHER", "latitude": 33.75,
             "longitude": -116.72, "value": 20.0, "confidence": 1.0,
             "observation_timestamp": "2026-07-22T10:00:00Z",
             "raw_data": '{"temperature": 20.0, "humidity": 40.0, "wind_speed": 1.0, "wind_direction": 162}'},
        ]
        result = scorer.calculate_risk_for_property(property_data, hazard_data)
        assert result["factors"]["wind_score"] == 0.0

    def test_upwind_property_scores_zero_regardless_of_speed(self):
        scorer = WildFireScorer()
        property_data = {"property_id": 1, "latitude": 33.75, "longitude": -116.72}
        hazard_data = [
            {"hazard_type": "wildfire", "source": "NASA_FIRMS", "latitude": 33.751,
             "longitude": -116.721, "value": 0, "confidence": 0.9,
             "observation_timestamp": "2026-07-22T10:00:00Z"},
            # Property is at bearing ~140 (SE) from the fire; a wind_direction
            # of ~140 means the wind blows FROM the property's own direction,
            # i.e. away from the property - it is upwind, not downwind.
            {"hazard_type": "weather", "source": "OPENWEATHER", "latitude": 33.75,
             "longitude": -116.72, "value": 20.0, "confidence": 1.0,
             "observation_timestamp": "2026-07-22T10:00:00Z",
             "raw_data": '{"temperature": 20.0, "humidity": 40.0, "wind_speed": 15.0, "wind_direction": 140}'},
        ]
        result = scorer.calculate_risk_for_property(property_data, hazard_data)
        assert result["factors"]["wind_score"] == 0.0


# ---------------------------------------------------------------------------
# FloodScorer
# ---------------------------------------------------------------------------

class TestFloodScorerRainfall:
    def test_higher_rainfall_scores_higher(self):
        scorer = FloodScorer()
        property_data = {"property_id": 1, "latitude": 29.95, "longitude": -90.07, "is_in_floodplain": False}

        light_rain = [{
            "hazard_type": "flood", "source": "OPENWEATHER_RAIN",
            "latitude": 29.95, "longitude": -90.07, "value": 5.0,
            "confidence": 1.0, "observation_timestamp": "2026-07-22T10:00:00Z",
        }]
        heavy_rain = [{
            "hazard_type": "flood", "source": "OPENWEATHER_RAIN",
            "latitude": 29.95, "longitude": -90.07, "value": 140.0,
            "confidence": 1.0, "observation_timestamp": "2026-07-22T10:00:00Z",
        }]

        light_result = scorer.calculate_risk_for_property(property_data, light_rain)
        heavy_result = scorer.calculate_risk_for_property(property_data, heavy_rain)
        assert heavy_result["score"] > light_result["score"]

    def test_multiple_rainfall_readings_sum(self):
        scorer = FloodScorer()
        property_data = {"property_id": 1, "latitude": 29.95, "longitude": -90.07, "is_in_floodplain": False}
        readings = [
            {"hazard_type": "flood", "source": "OPENWEATHER_RAIN", "latitude": 29.95,
             "longitude": -90.07, "value": 20.0, "confidence": 1.0,
             "observation_timestamp": "2026-07-22T10:00:00Z"},
            {"hazard_type": "flood", "source": "OPENWEATHER_RAIN", "latitude": 29.95,
             "longitude": -90.07, "value": 30.0, "confidence": 1.0,
             "observation_timestamp": "2026-07-22T11:00:00Z"},
        ]
        result = scorer.calculate_risk_for_property(property_data, readings)
        assert result["factors"]["total_rainfall_mm"] == 50.0

    def test_rainfall_capped_at_configured_max(self):
        scorer = FloodScorer()
        property_data = {"property_id": 1, "latitude": 29.95, "longitude": -90.07, "is_in_floodplain": False}
        extreme_rain = [{
            "hazard_type": "flood", "source": "OPENWEATHER_RAIN",
            "latitude": 29.95, "longitude": -90.07, "value": 10000.0,
            "confidence": 1.0, "observation_timestamp": "2026-07-22T10:00:00Z",
        }]
        result = scorer.calculate_risk_for_property(property_data, extreme_rain)
        assert result["factors"]["rainfall_score"] == 100.0


# ---------------------------------------------------------------------------
# RiskAggregator
# ---------------------------------------------------------------------------

class TestAggregatorScoreCombination:
    def test_weighted_average_without_override(self):
        aggregator = RiskAggregator()
        result = aggregator.aggregate_scores(60, 40)
        assert result["overall_score"] == 50.0
        assert result["breakdown"]["single_hazard_override"] is False

    def test_single_hazard_override_raises_overall_score(self):
        aggregator = RiskAggregator()
        result = aggregator.aggregate_scores(100, 0)
        assert result["overall_score"] == 100.0
        assert result["risk_level"] == "critical"
        assert result["breakdown"]["single_hazard_override"] is True
        assert result["breakdown"]["dominant_score"] == 100

    def test_build_overall_assessment_combines_scorer_outputs(self):
        aggregator = RiskAggregator()
        wildfire_result = {"score": 40.0, "factors": {"a": 1}, "explanation": "wf"}
        flood_result = {"score": 20.0, "factors": {"b": 2}, "explanation": "fl"}
        assessment = aggregator.build_overall_assessment(
            {"property_id": 7}, wildfire_result, flood_result
        )
        assert assessment["property_id"] == 7
        assert assessment["wildfire_risk_score"] == 40.0
        assert assessment["flood_risk_score"] == 20.0
        assert assessment["wildfire_explanation"] == "wf"
        assert assessment["flood_explanation"] == "fl"


# ---------------------------------------------------------------------------
# Edge cases (explicitly required by Task 29): score=0, score=100,
# missing data, invalid coordinates
# ---------------------------------------------------------------------------

class TestEdgeCaseScoreZero:
    def test_wildfire_scorer_zero_with_no_hazard_data(self):
        scorer = WildFireScorer()
        result = scorer.calculate_risk_for_property(
            {"property_id": 1, "latitude": 33.75, "longitude": -116.72}, []
        )
        assert result["score"] == 0.0

    def test_flood_scorer_zero_with_no_hazard_data_and_not_in_floodplain(self):
        scorer = FloodScorer()
        result = scorer.calculate_risk_for_property(
            {"property_id": 1, "latitude": 29.95, "longitude": -90.07, "is_in_floodplain": False}, []
        )
        assert result["score"] == 0.0

    def test_aggregator_zero_and_zero(self):
        aggregator = RiskAggregator()
        result = aggregator.aggregate_scores(0, 0)
        assert result["overall_score"] == 0.0
        assert result["risk_level"] == "low"


class TestEdgeCaseScoreHundred:
    def test_aggregator_hundred_and_hundred(self):
        aggregator = RiskAggregator()
        result = aggregator.aggregate_scores(100, 100)
        assert result["overall_score"] == 100.0
        assert result["risk_level"] == "critical"

    def test_flood_scorer_capped_at_hundred_even_with_extreme_inputs(self):
        scorer = FloodScorer()
        hazard_data = [
            {"hazard_type": "flood", "source": "OPENWEATHER_RAIN", "latitude": 29.95,
             "longitude": -90.07, "value": 100000.0, "confidence": 1.0,
             "observation_timestamp": "2026-07-22T10:00:00Z"},
            {"hazard_type": "flood", "source": "USGS", "latitude": 29.95,
             "longitude": -90.07, "value": 50.0, "confidence": 1.0,
             "observation_timestamp": "2026-07-22T10:00:00Z"},
        ]
        result = scorer.calculate_risk_for_property(
            {"property_id": 1, "latitude": 29.95, "longitude": -90.07, "is_in_floodplain": True},
            hazard_data,
        )
        assert result["score"] <= 100.0


class TestEdgeCaseMissingData:
    def test_wildfire_scorer_missing_latitude_raises(self):
        scorer = WildFireScorer()
        with pytest.raises(KeyError):
            scorer.calculate_risk_for_property({"property_id": 1, "longitude": -116.72}, [])

    def test_flood_scorer_missing_floodplain_flag_defaults_false(self):
        scorer = FloodScorer()
        result = scorer.calculate_risk_for_property(
            {"property_id": 1, "latitude": 29.95, "longitude": -90.07}, []
        )
        assert result["factors"]["is_in_floodplain"] is False

    def test_wildfire_scorer_missing_weather_data_scores_environment_zero(self):
        scorer = WildFireScorer()
        fire_only = [{
            "hazard_type": "wildfire", "source": "NASA_FIRMS",
            "latitude": 33.751, "longitude": -116.721, "value": 100,
            "confidence": 0.9, "observation_timestamp": "2026-07-22T10:00:00Z",
        }]
        result = scorer.calculate_risk_for_property(
            {"property_id": 1, "latitude": 33.75, "longitude": -116.72}, fire_only
        )
        assert result["factors"]["environment_score"] == 0.0
        assert result["factors"]["temperature"] is None
        assert result["factors"]["humidity"] is None


class TestEdgeCaseInvalidCoordinates:
    def test_wildfire_scorer_raises_on_invalid_property_coordinates(self):
        scorer = WildFireScorer()
        fires = [{
            "hazard_type": "wildfire", "source": "NASA_FIRMS",
            "latitude": 33.75, "longitude": -116.72, "value": 100,
            "confidence": 0.9, "observation_timestamp": "2026-07-22T10:00:00Z",
        }]
        with pytest.raises(ValueError):
            scorer.calculate_risk_for_property(
                {"property_id": 1, "latitude": 999.0, "longitude": -116.72}, fires
            )

    def test_flood_scorer_raises_on_invalid_property_coordinates(self):
        scorer = FloodScorer()
        gauges = [{
            "hazard_type": "flood", "source": "USGS",
            "latitude": 29.95, "longitude": -90.07, "value": 3.0,
            "confidence": 1.0, "observation_timestamp": "2026-07-22T10:00:00Z",
        }]
        with pytest.raises(ValueError):
            scorer.calculate_risk_for_property(
                {"property_id": 1, "latitude": 29.95, "longitude": -999.0, "is_in_floodplain": False}, gauges
            )


# ---------------------------------------------------------------------------
# RiskScoringEngine - closing the branch-coverage gap found before writing
# this suite (high/critical counters, per-property error isolation)
# ---------------------------------------------------------------------------

class VariableScorer:
    """Test double standing in for either scorer: returns a fixed score per
    property_id, or raises for property_ids in raise_for - used to directly
    control which risk_level bucket / error path RiskScoringEngine hits,
    without needing real hazard data to produce specific score bands."""

    def __init__(self, score_map, raise_for=None):
        self.score_map = score_map
        self.raise_for = raise_for or set()

    def calculate_risk_for_property(self, property_data, hazard_data):
        pid = property_data["property_id"]
        if pid in self.raise_for:
            raise ValueError(f"invalid coordinates for property {pid}")
        return {"score": self.score_map.get(pid, 0.0), "factors": {}, "explanation": "test"}


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    import src.database.db as db_module

    db_path = tmp_path / "test_climate_risk.db"
    monkeypatch.setattr(db_module, "DB_PATH", db_path)

    conn = db_module.get_db_connection()
    schema = db_module.get_schema()
    conn.execute(schema["properties"])
    conn.execute(schema["hazard_data"])
    conn.execute(schema["risk_assessments"])
    conn.commit()
    conn.close()
    return db_path


def add_property(property_id, lat=33.75, lon=-116.72):
    import src.database.db as db_module
    conn = db_module.get_db_connection()
    conn.execute(
        "INSERT INTO properties (property_id, address, latitude, longitude) VALUES (?, ?, ?, ?)",
        (property_id, f"Property {property_id}", lat, lon),
    )
    conn.commit()
    conn.close()


class TestScoringEngineRiskLevelCounts:
    def test_high_and_critical_counts_reflect_actual_buckets(self, temp_db):
        for pid in (1, 2, 3):
            add_property(pid)

        engine = RiskScoringEngine()
        # property 1: dominant score 90 -> single-hazard override -> critical
        # property 2: weighted avg 65 -> "high" (medium_max=50, high_max=75)
        # property 3: weighted avg 10 -> "low"
        engine.wildfire_scorer = VariableScorer({1: 90.0, 2: 65.0, 3: 10.0})
        engine.flood_scorer = VariableScorer({1: 0.0, 2: 65.0, 3: 10.0})

        summary = engine.score_all_properties()
        assert summary["properties_scored"] == 3
        assert summary["critical_count"] == 1
        assert summary["high_risk_count"] == 1
        assert summary["errors"] == []


class TestScoringEngineErrorIsolation:
    def test_one_property_failing_does_not_stop_the_rest(self, temp_db):
        for pid in (1, 2):
            add_property(pid)

        engine = RiskScoringEngine()
        engine.wildfire_scorer = VariableScorer({2: 20.0}, raise_for={1})
        engine.flood_scorer = VariableScorer({2: 0.0}, raise_for={1})

        summary = engine.score_all_properties()
        assert summary["properties_scored"] == 1
        assert len(summary["errors"]) == 1
        assert "property_id=1" in summary["errors"][0]


# ---------------------------------------------------------------------------
# scoring_utils.py - malformed raw_data JSON fallback
# ---------------------------------------------------------------------------

class TestScoringUtilsMalformedData:
    def test_parse_weather_extras_falls_back_on_malformed_json(self):
        row = {"value": 25.0, "raw_data": "{not valid json"}
        result = parse_weather_extras(row)
        assert result["temperature"] == 25.0  # value itself still read directly
        assert result["humidity"] is None
        assert result["wind_speed"] is None

    def test_parse_weather_extras_handles_none_row(self):
        result = parse_weather_extras(None)
        assert result == {"temperature": None, "humidity": None, "wind_speed": None, "wind_direction": None}

    def test_parse_gauge_extras_falls_back_on_malformed_json(self):
        row = {"raw_data": "{not valid json"}
        result = parse_gauge_extras(row)
        assert result == {"site_name": None, "parameter_label": None}

    def test_parse_gauge_extras_handles_none_row(self):
        result = parse_gauge_extras(None)
        assert result == {"site_name": None, "parameter_label": None}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
