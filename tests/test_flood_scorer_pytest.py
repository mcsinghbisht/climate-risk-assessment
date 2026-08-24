"""
Pytest test suite for FloodScorer (Task 16)

Run with: pytest tests/test_flood_scorer_pytest.py -v
"""

import json

import pytest

from src.risk_scoring.flood_scorer import FloodScorer

PROPERTY_IN_FLOODPLAIN = {
    "property_id": 1, "latitude": 29.9511, "longitude": -90.0715, "is_in_floodplain": True,
}
PROPERTY_NOT_IN_FLOODPLAIN = {
    "property_id": 2, "latitude": 29.9511, "longitude": -90.0715, "is_in_floodplain": False,
}

NEAR_GAUGE = {
    "hazard_type": "flood", "source": "USGS",
    "latitude": 29.96, "longitude": -90.08, "value": 3.2,
    "confidence": 1.0, "observation_timestamp": "2026-07-22T10:00:00Z",
    "raw_data": json.dumps({"site_name": "Near Gauge", "parameter_label": "gage_height_ft"}),
}
FAR_GAUGE = {
    "hazard_type": "flood", "source": "USGS",
    "latitude": 40.0, "longitude": -100.0, "value": 500000.0,  # huge discharge, but far away
    "confidence": 1.0, "observation_timestamp": "2026-07-22T10:00:00Z",
    "raw_data": json.dumps({"site_name": "Far Gauge", "parameter_label": "discharge_cfs"}),
}


def make_rain(value=10.0, latitude=29.9511, longitude=-90.0715):
    return {
        "hazard_type": "flood", "source": "OPENWEATHER_RAIN",
        "latitude": latitude, "longitude": longitude, "value": value,
        "confidence": 1.0, "observation_timestamp": "2026-07-22T10:00:00Z", "raw_data": "{}",
    }


def make_weather(humidity=50.0, temperature=25.0, latitude=29.9511, longitude=-90.0715):
    return {
        "hazard_type": "weather", "source": "OPENWEATHER",
        "latitude": latitude, "longitude": longitude, "value": temperature,
        "confidence": 1.0, "observation_timestamp": "2026-07-22T10:00:00Z",
        "raw_data": json.dumps({"temperature": temperature, "humidity": humidity, "wind_speed": 2.0, "wind_direction": 90}),
    }


@pytest.fixture
def scorer():
    return FloodScorer()


class TestOverallScore:
    def test_score_is_within_0_100(self, scorer):
        result = scorer.calculate_risk_for_property(
            PROPERTY_IN_FLOODPLAIN, [make_rain(60.0), NEAR_GAUGE, make_weather(humidity=90.0)]
        )
        assert 0 <= result["score"] <= 100

    def test_no_hazard_data_not_in_floodplain_returns_zero(self, scorer):
        result = scorer.calculate_risk_for_property(PROPERTY_NOT_IN_FLOODPLAIN, [])
        assert result["score"] == 0.0

    def test_result_has_factors_and_explanation(self, scorer):
        result = scorer.calculate_risk_for_property(PROPERTY_IN_FLOODPLAIN, [make_rain()])
        assert "factors" in result
        assert "explanation" in result
        assert isinstance(result["explanation"], str) and len(result["explanation"]) > 0

    def test_heavy_rain_floodplain_near_gauge_scores_high(self, scorer):
        hazard_data = [make_rain(80.0), NEAR_GAUGE, make_weather(humidity=90.0)]
        result = scorer.calculate_risk_for_property(PROPERTY_IN_FLOODPLAIN, hazard_data)
        assert result["score"] > 60

    def test_floodplain_status_scored_even_with_no_hazard_data(self, scorer):
        result = scorer.calculate_risk_for_property(PROPERTY_IN_FLOODPLAIN, [])
        assert result["score"] > 0
        assert result["factors"]["floodplain_score"] == 100.0

    def test_far_gauge_does_not_contribute_to_score(self, scorer):
        """Regression-style test mirroring Task 15's out-of-range-fire bug:
        a gauge far outside proximity_max_km must not affect the score,
        regardless of how large its discharge value is."""
        result = scorer.calculate_risk_for_property(PROPERTY_NOT_IN_FLOODPLAIN, [FAR_GAUGE])
        assert result["score"] == 0.0
        assert result["factors"]["proximity_score"] == 0.0


class TestRainfallScoring:
    def test_more_rain_scores_higher(self, scorer):
        low_score, _ = scorer._score_rainfall([make_rain(5.0)])
        high_score, _ = scorer._score_rainfall([make_rain(100.0)])
        assert high_score > low_score

    def test_no_rain_rows_scores_zero(self, scorer):
        score, total = scorer._score_rainfall([])
        assert score == 0.0
        assert total == 0.0

    def test_sums_multiple_rainfall_readings(self, scorer):
        score, total = scorer._score_rainfall([make_rain(10.0), make_rain(20.0)])
        assert total == 30.0

    def test_score_capped_at_100(self, scorer):
        score, _ = scorer._score_rainfall([make_rain(10000.0)])
        assert score == 100.0


class TestProximityToWaterScoring:
    def test_closer_gauge_scores_higher(self, scorer):
        near_score, _, near_dist = scorer._score_proximity_to_water(29.9511, -90.0715, [NEAR_GAUGE])
        far_score, _, far_dist = scorer._score_proximity_to_water(29.9511, -90.0715, [FAR_GAUGE])
        assert near_dist < far_dist
        assert near_score > far_score

    def test_no_gauges_returns_zero(self, scorer):
        score, nearest, distance = scorer._score_proximity_to_water(29.9511, -90.0715, [])
        assert score == 0.0
        assert nearest is None
        assert distance is None

    def test_gauge_beyond_max_range_scores_zero(self, scorer):
        score, nearest, distance = scorer._score_proximity_to_water(29.9511, -90.0715, [FAR_GAUGE])
        assert score == 0.0
        assert distance > scorer.proximity_max_km


class TestFloodplainScoring:
    def test_in_floodplain_scores_100(self, scorer):
        assert scorer._score_floodplain(True) == 100.0

    def test_not_in_floodplain_scores_zero(self, scorer):
        assert scorer._score_floodplain(False) == 0.0


class TestSoilSaturationScoring:
    def test_high_rainfall_high_humidity_scores_high(self, scorer):
        score = scorer._score_soil_saturation(rainfall_total_mm=100.0, humidity=95.0)
        assert score > 60

    def test_no_rainfall_no_humidity_scores_low(self, scorer):
        score = scorer._score_soil_saturation(rainfall_total_mm=0.0, humidity=10.0)
        assert score < 20

    def test_no_data_scores_zero(self, scorer):
        assert scorer._score_soil_saturation(None, None) == 0.0

    def test_partial_data_still_scores(self, scorer):
        score = scorer._score_soil_saturation(rainfall_total_mm=None, humidity=80.0)
        assert score > 0


class TestNearestWeatherSelection:
    def test_uses_closest_weather_station_for_humidity(self, scorer):
        far_weather = make_weather(humidity=10.0, latitude=40.0, longitude=-100.0)
        near_weather = make_weather(humidity=95.0, latitude=29.952, longitude=-90.072)

        result = scorer.calculate_risk_for_property(
            PROPERTY_IN_FLOODPLAIN, [far_weather, near_weather]
        )
        assert result["factors"]["humidity"] == 95.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
