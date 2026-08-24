"""
Risk Score Aggregator

Combines WildFireScorer and FloodScorer output into a single overall risk
score and risk level classification, using the weights and thresholds
already configured in config/settings.json (risk_scoring.overall_weights,
risk_scoring.risk_levels) since Task 5.

Single-hazard override: a pure weighted average can dilute a genuinely
extreme single-hazard score (e.g. wildfire=100, flood=0 -> 50 under a 50/50
average), understating risk for properties facing one severe peril rather
than two moderate ones. If either individual score is >=
critical_single_hazard_threshold (default 85), the overall_score is raised
to at least that dominant score and risk_level is forced to "critical" -
this was a deliberate design decision (not the original MVP formula),
revisited after reviewing Task 17's initial output.
"""

import logging
from typing import Dict, Optional

from src.config import get_config

logger = logging.getLogger(__name__)

DEFAULT_OVERALL_WEIGHTS = {"wildfire": 0.5, "flood": 0.5}
DEFAULT_RISK_LEVELS = {"low_max": 25, "medium_max": 50, "high_max": 75}
DEFAULT_CRITICAL_SINGLE_HAZARD_THRESHOLD = 85


class RiskAggregator:
    """Combines wildfire and flood risk scores into an overall assessment."""

    def __init__(self):
        config = get_config()
        risk_scoring = config.get_section("risk_scoring")
        self.weights: Dict = risk_scoring.get("overall_weights", DEFAULT_OVERALL_WEIGHTS)
        self.risk_levels: Dict = risk_scoring.get("risk_levels", DEFAULT_RISK_LEVELS)
        self.critical_single_hazard_threshold: float = risk_scoring.get(
            "critical_single_hazard_threshold", DEFAULT_CRITICAL_SINGLE_HAZARD_THRESHOLD
        )

    def classify_risk_level(self, score: float) -> str:
        """
        Classify a 0-100 score into low/medium/high/critical using the
        configured risk_levels thresholds.

        Args:
            score: Overall risk score (0-100)

        Returns:
            One of "low", "medium", "high", "critical"
        """
        if score <= self.risk_levels.get("low_max", 25):
            return "low"
        elif score <= self.risk_levels.get("medium_max", 50):
            return "medium"
        elif score <= self.risk_levels.get("high_max", 75):
            return "high"
        else:
            return "critical"

    def aggregate_scores(self, wildfire_score: float, flood_score: float) -> Dict:
        """
        Combine a wildfire score and a flood score into an overall score
        and risk level.

        A single-hazard override applies when either score is >=
        critical_single_hazard_threshold: overall_score is raised to at
        least that dominant score, and risk_level is forced to "critical" -
        an extreme single peril is never diluted into a lower band just
        because the other peril happens to be calm.

        Args:
            wildfire_score: Wildfire risk score (0-100)
            flood_score: Flood risk score (0-100)

        Returns:
            {
                "overall_score": float 0-100,
                "risk_level": "low"/"medium"/"high"/"critical",
                "breakdown": {wildfire_score, wildfire_weight, wildfire_contribution,
                              flood_score, flood_weight, flood_contribution,
                              single_hazard_override, dominant_score}
            }
        """
        wildfire_weight = self.weights.get("wildfire", 0.5)
        flood_weight = self.weights.get("flood", 0.5)

        wildfire_contribution = wildfire_score * wildfire_weight
        flood_contribution = flood_score * flood_weight
        weighted_average = wildfire_contribution + flood_contribution

        dominant_score = max(wildfire_score, flood_score)
        single_hazard_override = dominant_score >= self.critical_single_hazard_threshold

        if single_hazard_override:
            overall_score = max(weighted_average, dominant_score)
            risk_level = "critical"
        else:
            overall_score = weighted_average
            risk_level = self.classify_risk_level(overall_score)

        overall_score = round(min(100.0, max(0.0, overall_score)), 2)

        breakdown = {
            "wildfire_score": wildfire_score,
            "wildfire_weight": wildfire_weight,
            "wildfire_contribution": round(wildfire_contribution, 2),
            "flood_score": flood_score,
            "flood_weight": flood_weight,
            "flood_contribution": round(flood_contribution, 2),
            "single_hazard_override": single_hazard_override,
            "dominant_score": dominant_score if single_hazard_override else None,
        }

        return {"overall_score": overall_score, "risk_level": risk_level, "breakdown": breakdown}

    def build_overall_assessment(
        self, property_data: Dict, wildfire_result: Dict, flood_result: Dict
    ) -> Dict:
        """
        Convenience method combining full scorer outputs (score + factors +
        explanation from each of WildFireScorer/FloodScorer) into a single
        dict shaped to match the risk_assessments table schema (Task 3),
        ready for storage (Task 18) or for building an LLM agent context.

        Args:
            property_data: Property dict (must have 'property_id')
            wildfire_result: Output of WildFireScorer.calculate_risk_for_property()
            flood_result: Output of FloodScorer.calculate_risk_for_property()

        Returns:
            {
                "property_id", "wildfire_risk_score", "wildfire_factors",
                "flood_risk_score", "flood_factors", "overall_risk_score",
                "risk_level", "wildfire_explanation", "flood_explanation"
            }
        """
        aggregated = self.aggregate_scores(wildfire_result["score"], flood_result["score"])

        return {
            "property_id": property_data.get("property_id"),
            "wildfire_risk_score": wildfire_result["score"],
            "wildfire_factors": wildfire_result["factors"],
            "flood_risk_score": flood_result["score"],
            "flood_factors": flood_result["factors"],
            "overall_risk_score": aggregated["overall_score"],
            "risk_level": aggregated["risk_level"],
            "wildfire_explanation": wildfire_result["explanation"],
            "flood_explanation": flood_result["explanation"],
        }


if __name__ == "__main__":
    print("=" * 60)
    print("Risk Aggregator Test")
    print("=" * 60)
    print()

    aggregator = RiskAggregator()

    test_cases = [
        (60, 40, "Moderate wildfire, low flood"),
        (85, 90, "High wildfire, high flood"),
        (0, 0, "No risk"),
        (100, 0, "Extreme wildfire only"),
    ]

    for wildfire_score, flood_score, label in test_cases:
        result = aggregator.aggregate_scores(wildfire_score, flood_score)
        print(f"{label}: wildfire={wildfire_score}, flood={flood_score}")
        print(f"  -> overall={result['overall_score']}, risk_level={result['risk_level']}")
        print(f"  -> breakdown: {result['breakdown']}")
        print()

    print("=" * 60)
    print("All tests complete!")
    print("=" * 60)
