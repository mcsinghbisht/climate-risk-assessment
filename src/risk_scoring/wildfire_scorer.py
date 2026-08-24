"""
Wildfire Risk Scoring Algorithm

Calculates an explainable 0-100 wildfire risk score for a property from
nearby hazard_data rows (wildfire detections + weather observations),
combining four weighted factors:

  - Proximity to the nearest active fire (default weight 0.4)
  - Wind-driven escalation (is the fire's smoke/embers blowing toward the
    property, and how strongly?) (default weight 0.3)
  - Fire intensity (Fire Radiative Power, FRP) (default weight 0.2)
  - Environmental conditions (low humidity / high temperature) (default weight 0.1)

All weights and thresholds are configuration-driven (config/settings.json
-> risk_scoring.wildfire_weights / risk_scoring.wildfire_params) - no
hardcoded thresholds in this module.

Input format: hazard_data is a list of hazard_data-table-shaped dicts (the
same shape produced by DataNormalizer / stored by the ingesters in Tasks
10-13) - hazard_type, source, latitude, longitude, value, confidence,
observation_timestamp, raw_data. This lets the scorer be used directly
with rows pulled from the database, with no translation layer.
"""

import json
import logging
from typing import Dict, List, Optional, Tuple

from src.config import get_config
from src.utils import calculate_distance, is_downwind, get_distance_category
from src.risk_scoring.scoring_utils import parse_weather_extras as _parse_weather_extras

logger = logging.getLogger(__name__)


class WildFireScorer:
    """Calculates wildfire risk scores for properties from hazard data."""

    def __init__(self):
        config = get_config()
        self.weights: Dict = config.get_section("risk_scoring").get(
            "wildfire_weights", {"proximity": 0.4, "wind": 0.3, "intensity": 0.2, "environment": 0.1}
        )
        params: Dict = config.get_section("risk_scoring").get("wildfire_params", {})
        self.proximity_max_km: float = params.get("proximity_max_km", 50.0)
        self.wind_speed_threshold_ms: float = params.get("wind_speed_threshold_ms", 9.0)
        self.wind_max_reference_speed_ms: float = params.get("wind_max_reference_speed_ms", 20.0)
        self.historical_max_frp: float = params.get("historical_max_frp", 500.0)
        self.humidity_weight: float = params.get("humidity_weight", 0.6)
        self.temperature_weight: float = params.get("temperature_weight", 0.4)
        self.high_temp_threshold_c: float = params.get("high_temp_threshold_c", 35.0)

    # ------------------------------------------------------------------
    # Component scorers
    # ------------------------------------------------------------------

    def _score_proximity(
        self, property_lat: float, property_lon: float, fires: List[Dict]
    ) -> Tuple[float, Optional[Dict], Optional[float]]:
        """
        Score based on distance to the nearest active fire.

        Returns:
            (score 0-100, nearest_fire dict or None, distance_km or None)
        """
        if not fires:
            return 0.0, None, None

        nearest_fire = None
        nearest_distance = None
        for fire in fires:
            distance = calculate_distance(
                property_lat, property_lon, fire["latitude"], fire["longitude"]
            )
            if nearest_distance is None or distance < nearest_distance:
                nearest_distance = distance
                nearest_fire = fire

        if nearest_distance > self.proximity_max_km:
            return 0.0, nearest_fire, nearest_distance

        score = max(0.0, 100.0 * (1 - nearest_distance / self.proximity_max_km))
        return score, nearest_fire, nearest_distance

    def _score_wind_escalation(
        self, fire_lat: float, fire_lon: float, property_lat: float, property_lon: float,
        wind_speed: Optional[float], wind_direction: Optional[float],
    ) -> float:
        """
        Score wind-driven escalation risk: is the property downwind of the
        fire, and how strong is the wind pushing toward it?

        Returns 0 if there's no wind data, the property isn't downwind, or
        wind speed is below the configured threshold. Otherwise scales
        0-100 based on wind speed relative to a configured reference max.
        """
        if wind_speed is None or wind_direction is None:
            return 0.0

        if wind_speed < self.wind_speed_threshold_ms:
            return 0.0

        if not is_downwind(fire_lat, fire_lon, property_lat, property_lon, wind_direction):
            return 0.0

        return min(100.0, (wind_speed / self.wind_max_reference_speed_ms) * 100.0)

    def _score_intensity(self, frp: Optional[float]) -> float:
        """Score fire intensity (Fire Radiative Power, MW) relative to a
        configured historical maximum."""
        if not frp or frp <= 0:
            return 0.0
        return min(100.0, (frp / self.historical_max_frp) * 100.0)

    def _score_environment(self, temperature: Optional[float], humidity: Optional[float]) -> float:
        """
        Score environmental fire-danger conditions: low humidity and high
        temperature both increase risk.
        """
        if humidity is None and temperature is None:
            return 0.0

        humidity_score = max(0.0, 100.0 - humidity) if humidity is not None else 0.0
        temperature_score = (
            min(100.0, max(0.0, (temperature / self.high_temp_threshold_c) * 100.0))
            if temperature is not None else 0.0
        )

        return (humidity_score * self.humidity_weight) + (temperature_score * self.temperature_weight)

    # ------------------------------------------------------------------
    # Orchestration
    # ------------------------------------------------------------------

    def calculate_risk_for_property(self, property_data: Dict, hazard_data: List[Dict]) -> Dict:
        """
        Calculate the overall wildfire risk score for a property.

        Args:
            property_data: Property dict (must have 'latitude', 'longitude')
            hazard_data: List of hazard_data-shaped dicts (wildfire + weather
                         rows) near this property

        Returns:
            {
                "score": float 0-100,
                "factors": {proximity_score, wind_score, intensity_score,
                            environment_score, distance_km, frp,
                            wind_speed, wind_direction, temperature, humidity},
                "explanation": human-readable summary string
            }
        """
        property_lat = property_data["latitude"]
        property_lon = property_data["longitude"]

        fires = [h for h in hazard_data if h.get("hazard_type") == "wildfire"]
        weather_rows = [h for h in hazard_data if h.get("hazard_type") == "weather"]

        proximity_score, nearest_fire, distance_km = self._score_proximity(
            property_lat, property_lon, fires
        )

        # A fire beyond proximity_max_km poses no meaningful threat - its
        # intensity/wind-escalation shouldn't factor into the score just
        # because it happens to be the "nearest" one found. Only a fire
        # within range is treated as the active threat for those factors.
        fire_in_range = (
            nearest_fire if (distance_km is not None and distance_km <= self.proximity_max_km)
            else None
        )

        # Use the weather observation nearest to the property as the source
        # of wind/temperature/humidity for the wind and environment factors.
        nearest_weather = None
        if weather_rows:
            nearest_weather = min(
                weather_rows,
                key=lambda w: calculate_distance(property_lat, property_lon, w["latitude"], w["longitude"]),
            )
        weather_extras = _parse_weather_extras(nearest_weather) if nearest_weather else {
            "temperature": None, "humidity": None, "wind_speed": None, "wind_direction": None,
        }

        wind_score = 0.0
        if fire_in_range is not None:
            wind_score = self._score_wind_escalation(
                fire_in_range["latitude"], fire_in_range["longitude"],
                property_lat, property_lon,
                weather_extras["wind_speed"], weather_extras["wind_direction"],
            )

        intensity_score = self._score_intensity(fire_in_range["value"] if fire_in_range else None)
        environment_score = self._score_environment(
            weather_extras["temperature"], weather_extras["humidity"]
        )

        overall_score = (
            proximity_score * self.weights.get("proximity", 0.4)
            + wind_score * self.weights.get("wind", 0.3)
            + intensity_score * self.weights.get("intensity", 0.2)
            + environment_score * self.weights.get("environment", 0.1)
        )
        overall_score = round(min(100.0, max(0.0, overall_score)), 2)

        factors = {
            "proximity_score": round(proximity_score, 2),
            "wind_score": round(wind_score, 2),
            "intensity_score": round(intensity_score, 2),
            "environment_score": round(environment_score, 2),
            "distance_km": round(distance_km, 2) if distance_km is not None else None,
            "distance_category": get_distance_category(distance_km) if distance_km is not None else None,
            "frp": fire_in_range["value"] if fire_in_range else None,
            "wind_speed": weather_extras["wind_speed"],
            "wind_direction": weather_extras["wind_direction"],
            "temperature": weather_extras["temperature"],
            "humidity": weather_extras["humidity"],
        }

        explanation = self._build_explanation(overall_score, factors, nearest_fire is not None)

        return {"score": overall_score, "factors": factors, "explanation": explanation}

    @staticmethod
    def _build_explanation(score: float, factors: Dict, has_fire: bool) -> str:
        if not has_fire:
            return "No active wildfire detected nearby. Risk score reflects baseline conditions only."

        parts = [f"Nearest active fire is {factors['distance_km']} km away ({factors['distance_category']})."]

        if factors["wind_score"] > 0:
            parts.append(
                f"Wind ({factors['wind_speed']} m/s) is blowing toward the property, "
                f"increasing escalation risk."
            )

        if factors["frp"]:
            parts.append(f"Fire intensity (FRP): {factors['frp']} MW.")

        if factors["humidity"] is not None or factors["temperature"] is not None:
            parts.append(
                f"Conditions: {factors['temperature']}°C, {factors['humidity']}% humidity."
            )

        parts.append(f"Overall wildfire risk score: {score}/100.")
        return " ".join(parts)


if __name__ == "__main__":
    print("=" * 60)
    print("Wildfire Risk Scorer Test")
    print("=" * 60)
    print()

    scorer = WildFireScorer()

    property_data = {"property_id": 1, "latitude": 33.75, "longitude": -116.72}
    hazard_data = [
        {
            "hazard_type": "wildfire", "source": "NASA_FIRMS",
            "latitude": 33.70, "longitude": -116.70, "value": 250.0,
            "confidence": 0.9, "observation_timestamp": "2026-07-22T10:00:00Z",
            "raw_data": "{}",
        },
        {
            "hazard_type": "weather", "source": "OPENWEATHER",
            "latitude": 33.75, "longitude": -116.72, "value": 38.0,
            "confidence": 1.0, "observation_timestamp": "2026-07-22T10:00:00Z",
            "raw_data": json.dumps({
                # Fire is at bearing ~342 (NNW) from the property's perspective
                # reversed, i.e. property is NNW of the fire; wind from ~162
                # (SSE) blows toward NNW, putting the property downwind.
                "temperature": 38.0, "humidity": 12.0,
                "wind_speed": 15.0, "wind_direction": 162,
            }),
        },
    ]

    result = scorer.calculate_risk_for_property(property_data, hazard_data)
    print(f"Score: {result['score']}")
    print(f"Factors: {json.dumps(result['factors'], indent=2)}")
    print(f"Explanation: {result['explanation']}")

    print()
    print("=" * 60)
    print("No-fire baseline test")
    print("=" * 60)
    result_no_fire = scorer.calculate_risk_for_property(property_data, [])
    print(f"Score: {result_no_fire['score']}")
    print(f"Explanation: {result_no_fire['explanation']}")

    print()
    print("=" * 60)
    print("All tests complete!")
    print("=" * 60)
