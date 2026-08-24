"""
Risk Scoring Orchestrator

Runs the complete risk scoring pipeline across the entire property
portfolio in one call: fetch properties + hazard data, score each property
for wildfire and flood risk, aggregate into an overall assessment, and
persist a snapshot - bringing together every component built in Tasks 9,
15-18 for the first time as a single working system.

Known MVP simplification: fetches the entire hazard_data table once per
run and passes the same full list to every property's scorers (each
scorer internally finds the nearest relevant hazard and applies its own
proximity_max_km cutoff, so out-of-range data naturally scores 0 - see
Tasks 15/16). This is correct and simple at 100 properties / a few hundred
hazard rows. At production scale this would need a spatial pre-filter
(e.g. querying only hazard_data within each property's grid cell, mirroring
Task 14's ingestion-side design) rather than scanning the full table per
run - not needed yet, but the next place this pattern would need to grow.
"""

import logging
from typing import Dict, List

from src.database import get_db_connection, PropertyDAO, RiskDAO
from src.risk_scoring.wildfire_scorer import WildFireScorer
from src.risk_scoring.flood_scorer import FloodScorer
from src.risk_scoring.aggregator import RiskAggregator

logger = logging.getLogger(__name__)


class RiskScoringEngine:
    """Orchestrates wildfire + flood scoring and storage across the portfolio."""

    def __init__(self):
        self.property_dao = PropertyDAO()
        self.wildfire_scorer = WildFireScorer()
        self.flood_scorer = FloodScorer()
        self.aggregator = RiskAggregator()
        self.risk_dao = RiskDAO()

    @staticmethod
    def _fetch_all_hazard_data() -> List[Dict]:
        """Fetch every row currently in hazard_data as a list of dicts."""
        conn = get_db_connection()
        try:
            cursor = conn.execute("SELECT * FROM hazard_data")
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def score_all_properties(self) -> Dict:
        """
        Score every property in the portfolio for wildfire and flood risk,
        aggregate into an overall assessment, and persist a snapshot for each.

        Each property is scored independently and wrapped in its own
        try/except - one property failing to score does not stop the rest
        of the portfolio from being scored (same error-isolation principle
        as Task 14's IngestionEngine).

        Returns:
            {
                "properties_scored": int,
                "average_risk": float,
                "high_risk_count": int,
                "critical_count": int,
                "errors": List[str],
            }
        """
        properties = self.property_dao.get_all_properties()
        hazard_data = self._fetch_all_hazard_data()

        logger.info(
            "Starting risk scoring cycle: %d properties, %d hazard_data rows available",
            len(properties), len(hazard_data),
        )

        overall_scores: List[float] = []
        high_risk_count = 0
        critical_count = 0
        errors: List[str] = []

        for property_data in properties:
            property_id = property_data.get("property_id")
            try:
                wildfire_result = self.wildfire_scorer.calculate_risk_for_property(
                    property_data, hazard_data
                )
                flood_result = self.flood_scorer.calculate_risk_for_property(
                    property_data, hazard_data
                )
                assessment = self.aggregator.build_overall_assessment(
                    property_data, wildfire_result, flood_result
                )
                self.risk_dao.save_assessment(assessment)

                overall_scores.append(assessment["overall_risk_score"])
                if assessment["risk_level"] == "high":
                    high_risk_count += 1
                elif assessment["risk_level"] == "critical":
                    critical_count += 1
            except Exception as e:
                logger.error("Failed to score property_id=%s: %s", property_id, e)
                errors.append(f"property_id={property_id}: {e}")

        average_risk = round(sum(overall_scores) / len(overall_scores), 2) if overall_scores else 0.0

        summary = {
            "properties_scored": len(overall_scores),
            "average_risk": average_risk,
            "high_risk_count": high_risk_count,
            "critical_count": critical_count,
            "errors": errors,
        }

        logger.info(
            "Risk scoring cycle complete: %d scored, avg=%.2f, high=%d, critical=%d, %d errors",
            summary["properties_scored"], summary["average_risk"],
            summary["high_risk_count"], summary["critical_count"], len(summary["errors"]),
        )
        return summary


if __name__ == "__main__":
    from src.config import setup_logging

    setup_logging()

    print("=" * 60)
    print("Risk Scoring Orchestrator - Task 19")
    print("=" * 60)
    print()

    engine = RiskScoringEngine()
    summary = engine.score_all_properties()

    print(f"Properties scored: {summary['properties_scored']}")
    print(f"Average risk:       {summary['average_risk']}")
    print(f"High risk count:    {summary['high_risk_count']}")
    print(f"Critical count:     {summary['critical_count']}")
    if summary["errors"]:
        print("Errors:")
        for err in summary["errors"]:
            print(f"  - {err}")

    print()
    print("=" * 60)
