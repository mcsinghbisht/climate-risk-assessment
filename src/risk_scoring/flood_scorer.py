"""
Flood Risk Scoring Algorithm

Calculates an explainable 0-100 flood risk score for a property from nearby
hazard_data rows (precipitation + river gauge readings) plus the property's
own static floodplain flag, combining four weighted factors:

  - Rainfall accumulation (default weight 0.5)
  - Proximity to water (nearest river/stream gauge) (default weight 0.2)
  - Floodplain status (static property attribute, not hazard_data) (default weight 0.2)
  - Soil saturation proxy (rainfall + humidity) (default weight 0.1)

All weights and thresholds are configuration-driven (config/settings.json
-> risk_scoring.flood_weights / risk_scoring.flood_params) - no hardcoded
thresholds in this module. Mirrors WildFireScorer's design (Task 15) so the
output shape - {score, factors, explanation} - is identical across both
scorers, which matters for the future LLM agent context (see Task 15
completion notes).

Key design difference from WildFireScorer: floodplain status is read
directly from `property_data` (it's a static attribute generated in Task 7,
not something fetched from an external API), not from `hazard_data`.

Known simplification: proximity-to-water uses only distance to the nearest
gauge, not the gauge's current reading severity - a gauge station existing
nearby is treated as a proxy for "there is a water body nearby," independent
of whether that water body is currently high or low. This matches the
documented MVP design (docs/implementation-plan.md Section 5) rather than
inventing a fifth weighted factor.
"""

import logging
from typing import Dict, List, Optional, Tuple

from src.config import get_config
from src.utils import calculate_distance, get_distance_category
from src.risk_scoring.scoring_utils import parse_weather_extras, parse_gauge_extras

logger = logging.getLogger(__name__)


class FloodScorer:
    """Calculates flood risk scores for properties from hazard data."""

    def __init__(self):
        config = get_config()
        self.weights: Dict = config.get_section("risk_scoring").get(
            "flood_weights", {"rainfall": 0.5, "proximity": 0.2, "floodplain": 0.2, "saturation": 0.1}
        )
        params: Dict = config.get_section("risk_scoring").get("flood_params", {})
        self.proximity_max_km: float = params.get("proximity_max_km", 20.0)
        self.rainfall_max_accumulation_mm: float = params.get("rainfall_max_accumulation_mm", 150.0)
        self.saturation_rainfall_weight: float = params.get("soil_saturation_rainfall_weight", 0.7)
        self.saturation_humidity_weight: float = params.get("soil_saturation_humidity_weight", 0.3)

    # ------------------------------------------------------------------
    # Component scorers
    # ------------------------------------------------------------------

    def _score_rainfall(self, precipitation_rows: List[Dict]) -> Tuple[float, float]:
        """
        Score based on total recent rainfall accumulation.

        Sums the `value` (mm/hour) of every precipitation reading passed in
        as a proxy for accumulation - callers control the time window by
        controlling which hazard_data rows they include.

        Returns:
            (score 0-100, total_rainfall_mm)
        """
        if not precipitation_rows:
            return 0.0, 0.0

        total_mm = sum(r["value"] for r in precipitation_rows)
        score = min(100.0, (total_mm / self.rainfall_max_accumulation_mm) * 100.0)
        return score, total_mm

    def _score_proximity_to_water(
        self, property_lat: float, property_lon: float, gauge_rows: List[Dict]
    ) -> Tuple[float, Optional[Dict], Optional[float]]:
        """
        Score based on distance to the nearest river/stream gauge station,
        used as a proxy for proximity to a water body.

        Returns:
            (score 0-100, nearest_gauge dict or None, distance_km or None)
        """
        if not gauge_rows:
            return 0.0, None, None

        nearest_gauge = None
        nearest_distance = None
        for gauge in gauge_rows:
            distance = calculate_distance(
                property_lat, property_lon, gauge["latitude"], gauge["longitude"]
            )
            if nearest_distance is None or distance < nearest_distance:
                nearest_distance = distance
                nearest_gauge = gauge

        if nearest_distance > self.proximity_max_km:
            return 0.0, nearest_gauge, nearest_distance

        score = max(0.0, 100.0 * (1 - nearest_distance / self.proximity_max_km))
        return score, nearest_gauge, nearest_distance

    def _score_floodplain(self, is_in_floodplain: bool) -> float:
        """Score based on the property's static FEMA floodplain flag (Task 7)."""
        return 100.0 if is_in_floodplain else 0.0

    def _score_soil_saturation(self, rainfall_total_mm: Optional[float], humidity: Optional[float]) -> float:
        """
        Score soil saturation as a proxy from recent rainfall and humidity -
        no direct soil-moisture data source exists yet, so this combines the
        two available signals that correlate with saturated ground.
        """
        if rainfall_total_mm is None and humidity is None:
            return 0.0

        rainfall_component = min(100.0, ((rainfall_total_mm or 0.0) / self.rainfall_max_accumulation_mm) * 100.0)
        humidity_component = humidity if humidity is not None else 0.0

        return (rainfall_component * self.saturation_rainfall_weight) + (
            humidity_component * self.saturation_humidity_weight
        )

    # ------------------------------------------------------------------
    # Orchestration
    # ------------------------------------------------------------------

    def calculate_risk_for_property(self, property_data: Dict, hazard_data: List[Dict]) -> Dict:
        """
        Calculate the overall flood risk score for a property.

        Args:
            property_data: Property dict (must have 'latitude', 'longitude',
                            'is_in_floodplain')
            hazard_data: List of hazard_data-shaped dicts (precipitation +
                         gauge + weather rows) near this property

        Returns:
            {
                "score": float 0-100,
                "factors": {rainfall_score, proximity_score, floodplain_score,
                            saturation_score, total_rainfall_mm, distance_km,
                            distance_category, gauge_site_name, is_in_floodplain,
                            humidity},
                "explanation": human-readable summary string
            }
        """
        property_lat = property_data["latitude"]
        property_lon = property_data["longitude"]
        is_in_floodplain = bool(property_data.get("is_in_floodplain", False))

        precipitation_rows = [
            h for h in hazard_data
            if h.get("hazard_type") == "flood" and h.get("source") == "OPENWEATHER_RAIN"
        ]
        gauge_rows = [
            h for h in hazard_data
            if h.get("hazard_type") == "flood" and h.get("source") == "USGS"
        ]
        weather_rows = [h for h in hazard_data if h.get("hazard_type") == "weather"]

        rainfall_score, total_rainfall_mm = self._score_rainfall(precipitation_rows)
        proximity_score, nearest_gauge, distance_km = self._score_proximity_to_water(
            property_lat, property_lon, gauge_rows
        )
        floodplain_score = self._score_floodplain(is_in_floodplain)

        nearest_weather = None
        if weather_rows:
            nearest_weather = min(
                weather_rows,
                key=lambda w: calculate_distance(property_lat, property_lon, w["latitude"], w["longitude"]),
            )
        humidity = parse_weather_extras(nearest_weather)["humidity"]
        saturation_score = self._score_soil_saturation(total_rainfall_mm, humidity)

        overall_score = (
            rainfall_score * self.weights.get("rainfall", 0.5)
            + proximity_score * self.weights.get("proximity", 0.2)
            + floodplain_score * self.weights.get("floodplain", 0.2)
            + saturation_score * self.weights.get("saturation", 0.1)
        )
        overall_score = round(min(100.0, max(0.0, overall_score)), 2)

        gauge_extras = parse_gauge_extras(nearest_gauge)

        factors = {
            "rainfall_score": round(rainfall_score, 2),
            "proximity_score": round(proximity_score, 2),
            "floodplain_score": round(floodplain_score, 2),
            "saturation_score": round(saturation_score, 2),
            "total_rainfall_mm": round(total_rainfall_mm, 2),
            "distance_km": round(distance_km, 2) if distance_km is not None else None,
            "distance_category": get_distance_category(distance_km) if distance_km is not None else None,
            "gauge_site_name": gauge_extras["site_name"],
            "is_in_floodplain": is_in_floodplain,
            "humidity": humidity,
        }

        explanation = self._build_explanation(overall_score, factors)

        return {"score": overall_score, "factors": factors, "explanation": explanation}

    @staticmethod
    def _build_explanation(score: float, factors: Dict) -> str:
        parts = []

        if factors["total_rainfall_mm"] > 0:
            parts.append(f"Recent rainfall accumulation: {factors['total_rainfall_mm']} mm.")
        else:
            parts.append("No significant recent rainfall detected.")

        if factors["distance_km"] is not None and factors["proximity_score"] > 0:
            site = f" ({factors['gauge_site_name']})" if factors["gauge_site_name"] else ""
            parts.append(f"Nearest water gauge{site} is {factors['distance_km']} km away ({factors['distance_category']}).")

        if factors["is_in_floodplain"]:
            parts.append("Property is located within a designated FEMA floodplain.")
        else:
            parts.append("Property is not in a designated floodplain.")

        if factors["humidity"] is not None:
            parts.append(f"Humidity: {factors['humidity']}%.")

        parts.append(f"Overall flood risk score: {score}/100.")
        return " ".join(parts)


if __name__ == "__main__":
    import json

    print("=" * 60)
    print("Flood Risk Scorer Test")
    print("=" * 60)
    print()

    scorer = FloodScorer()

    property_data = {
        "property_id": 1, "latitude": 29.9511, "longitude": -90.0715,
        "is_in_floodplain": True,
    }
    hazard_data = [
        {
            "hazard_type": "flood", "source": "OPENWEATHER_RAIN",
            "latitude": 29.9511, "longitude": -90.0715, "value": 45.0,
            "confidence": 1.0, "observation_timestamp": "2026-07-22T10:00:00Z",
            "raw_data": "{}",
        },
        {
            "hazard_type": "flood", "source": "USGS",
            "latitude": 29.96, "longitude": -90.08, "value": 3.2,
            "confidence": 1.0, "observation_timestamp": "2026-07-22T10:00:00Z",
            "raw_data": json.dumps({"site_name": "New Orleans Gauge", "parameter_label": "gage_height_ft"}),
        },
        {
            "hazard_type": "weather", "source": "OPENWEATHER",
            "latitude": 29.9511, "longitude": -90.0715, "value": 27.0,
            "confidence": 1.0, "observation_timestamp": "2026-07-22T10:00:00Z",
            "raw_data": json.dumps({"temperature": 27.0, "humidity": 88.0, "wind_speed": 3.0, "wind_direction": 90}),
        },
    ]

    result = scorer.calculate_risk_for_property(property_data, hazard_data)
    print(f"Score: {result['score']}")
    print(f"Factors: {json.dumps(result['factors'], indent=2)}")
    print(f"Explanation: {result['explanation']}")

    print()
    print("=" * 60)
    print("No-hazard baseline test (not in floodplain)")
    print("=" * 60)
    baseline_property = {**property_data, "is_in_floodplain": False}
    result_baseline = scorer.calculate_risk_for_property(baseline_property, [])
    print(f"Score: {result_baseline['score']}")
    print(f"Explanation: {result_baseline['explanation']}")

    print()
    print("=" * 60)
    print("All tests complete!")
    print("=" * 60)
