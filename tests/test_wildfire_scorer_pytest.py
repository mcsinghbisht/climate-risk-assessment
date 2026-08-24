"""
Pytest test suite for WildFireScorer (Task 15)

Run with: pytest tests/test_wildfire_scorer_pytest.py -v
"""

import json

import pytest

from src.risk_scoring.wildfire_scorer import WildFireScorer

PROPERTY = {"property_id": 1, "latitude": 33.75, "longitude": -116.72}

# Wind direction 162 (from SSE) blows toward bearing ~342 (NNW), which is
# the direction from this fire to PROPERTY - i.e. PROPERTY is downwind.
NEARBY_FIRE = {
    "hazard_type": "wildfire", "source": "NASA_FIRMS",
    "latitude": 33.70, "longitude": -116.70, "value": 250.0,
    "confidence": 0.9, "observation_timestamp": "2026-07-22T10:00:00Z", "raw_data": "{}",
}
FAR_FIRE = {
    "hazard_type": "wildfire", "source": "NASA_FIRMS",
    "latitude": 30.0, "longitude": -120.0, "value": 100.0,
    "confidence": 0.9, "observation_timestamp": "2026-07-22T10:00:00Z", "raw_data": "{}",
}


def make_weather(temperature=25.0, humidity=50.0, wind_speed=5.0, wind_direction=162,
                  latitude=33.75, longitude=-116.72):
    return {
        "hazard_type": "weather", "source": "OPENWEATHER",
        "latitude": latitude, "longitude": longitude, "value": temperature,
        "confidence": 1.0, "observation_timestamp": "2026-07-22T10:00:00Z",
        "raw_data": json.dumps({
            "temperature": temperature, "humidity": humidity,
            "wind_speed": wind_speed, "wind_direction": wind_direction,
        }),
    }


@pytest.fixture
def scorer():
    return WildFireScorer()


class TestOverallScore:
    def test_score_is_within_0_100(self, scorer):
        result = scorer.calculate_risk_for_property(
            PROPERTY, [NEARBY_FIRE, make_weather(wind_speed=15.0)]
        )
        assert 0 <= result["score"] <= 100

    def test_no_hazard_data_returns_zero(self, scorer):
        result = scorer.calculate_risk_for_property(PROPERTY, [])
        assert result["score"] == 0.0

    def test_result_has_factors_and_explanation(self, scorer):
        result = scorer.calculate_risk_for_property(PROPERTY, [NEARBY_FIRE, make_weather()])
        assert "factors" in result
        assert "explanation" in result
        assert isinstance(result["explanation"], str) and len(result["explanation"]) > 0

    def test_nearby_downwind_intense_hot_dry_fire_scores_high(self, scorer):
        hazard_data = [NEARBY_FIRE, make_weather(temperature=38.0, humidity=12.0, wind_speed=15.0)]
        result = scorer.calculate_risk_for_property(PROPERTY, hazard_data)
        assert result["score"] > 70

    def test_far_fire_scores_low(self, scorer):
        # ~450km+ away, well beyond the 50km proximity_max_km
        result = scorer.calculate_risk_for_property(PROPERTY, [FAR_FIRE])
        assert result["score"] == 0.0

    def test_nearby_fire_with_no_weather_still_scores(self, scorer):
        result = scorer.calculate_risk_for_property(PROPERTY, [NEARBY_FIRE])
        assert result["score"] > 0  # proximity + intensity alone still contribute
        assert result["factors"]["wind_score"] == 0.0
        assert result["factors"]["environment_score"] == 0.0


class TestProximityScoring:
    def test_closer_fire_scores_higher_than_farther_fire(self, scorer):
        close = {**NEARBY_FIRE, "latitude": 33.751, "longitude": -116.721}  # ~100m away
        far_but_in_range = {**NEARBY_FIRE, "latitude": 33.5, "longitude": -116.9}  # ~35km away

        close_score, _, close_dist = scorer._score_proximity(33.75, -116.72, [close])
        far_score, _, far_dist = scorer._score_proximity(33.75, -116.72, [far_but_in_range])

        assert close_dist < far_dist
        assert close_score > far_score

    def test_no_fires_returns_zero(self, scorer):
        score, nearest, distance = scorer._score_proximity(33.75, -116.72, [])
        assert score == 0.0
        assert nearest is None
        assert distance is None

    def test_selects_nearest_of_multiple_fires(self, scorer):
        near = {**NEARBY_FIRE, "latitude": 33.751, "longitude": -116.721}
        far = {**NEARBY_FIRE, "latitude": 33.5, "longitude": -116.9}
        score, nearest, distance = scorer._score_proximity(33.75, -116.72, [far, near])
        assert nearest is near


class TestWindEscalationScoring:
    def test_downwind_strong_wind_scores_positive(self, scorer):
        score = scorer._score_wind_escalation(
            33.70, -116.70, 33.75, -116.72, wind_speed=15.0, wind_direction=162
        )
        assert score > 0

    def test_upwind_scores_zero_even_with_strong_wind(self, scorer):
        # wind_direction=342 blows toward bearing 162 (SSE), away from the
        # property which is at bearing 342 (NNW) from the fire.
        score = scorer._score_wind_escalation(
            33.70, -116.70, 33.75, -116.72, wind_speed=15.0, wind_direction=342
        )
        assert score == 0.0

    def test_below_threshold_wind_scores_zero(self, scorer):
        score = scorer._score_wind_escalation(
            33.70, -116.70, 33.75, -116.72, wind_speed=1.0, wind_direction=162
        )
        assert score == 0.0

    def test_missing_wind_data_scores_zero(self, scorer):
        score = scorer._score_wind_escalation(33.70, -116.70, 33.75, -116.72, None, None)
        assert score == 0.0

    def test_score_capped_at_100(self, scorer):
        score = scorer._score_wind_escalation(
            33.70, -116.70, 33.75, -116.72, wind_speed=1000.0, wind_direction=162
        )
        assert score == 100.0


class TestIntensityScoring:
    def test_higher_frp_scores_higher(self, scorer):
        assert scorer._score_intensity(400.0) > scorer._score_intensity(50.0)

    def test_zero_frp_scores_zero(self, scorer):
        assert scorer._score_intensity(0.0) == 0.0

    def test_none_frp_scores_zero(self, scorer):
        assert scorer._score_intensity(None) == 0.0

    def test_score_capped_at_100(self, scorer):
        assert scorer._score_intensity(10000.0) == 100.0


class TestEnvironmentScoring:
    def test_low_humidity_high_temp_scores_high(self, scorer):
        score = scorer._score_environment(temperature=40.0, humidity=5.0)
        assert score > 70

    def test_high_humidity_low_temp_scores_low(self, scorer):
        score = scorer._score_environment(temperature=10.0, humidity=90.0)
        assert score < 30

    def test_no_data_scores_zero(self, scorer):
        assert scorer._score_environment(None, None) == 0.0

    def test_partial_data_still_scores(self, scorer):
        score = scorer._score_environment(temperature=None, humidity=10.0)
        assert score > 0


class TestNearestWeatherSelection:
    def test_uses_closest_weather_station_when_multiple(self, scorer):
        far_weather = make_weather(humidity=90.0, latitude=40.0, longitude=-120.0)
        near_weather = make_weather(humidity=5.0, latitude=33.751, longitude=-116.721)

        result = scorer.calculate_risk_for_property(
            PROPERTY, [NEARBY_FIRE, far_weather, near_weather]
        )
        # near_weather's low humidity (5.0) should dominate, not far_weather's 90.0
        assert result["factors"]["humidity"] == 5.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
