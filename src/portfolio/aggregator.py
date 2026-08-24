"""
Portfolio-Level Metrics Aggregator

Computes portfolio-wide statistics from the individual property risk
assessments already stored by RiskDAO (Task 18) - risk-level distribution,
geographic concentration, score statistics, and assessment freshness. This
is the foundation the project's "portfolio-level risk visibility and
accumulation tracking" goal depends on: everything up through Task 24
answers "what is this one property's risk?"; this answers "what does the
whole portfolio look like?"

Deliberately read-only and side-effect-free: get_portfolio_metrics() just
computes and returns numbers from what's already in the database. It does
not raise alerts or write anything - portfolio-level alerting (e.g. ">10%
of properties in high/critical") is a separate concern (Task 26), built on
top of these same numbers rather than mixed into this class.
"""

import logging
import statistics
from typing import Dict, List, Optional

from src.database import PropertyDAO, RiskDAO

logger = logging.getLogger(__name__)

RISK_LEVELS = ("low", "medium", "high", "critical")


class PortfolioAggregator:
    """Computes portfolio-wide risk metrics from the latest assessment of every property."""

    def __init__(self):
        self.property_dao = PropertyDAO()
        self.risk_dao = RiskDAO()

    def get_portfolio_metrics(self) -> Dict:
        """
        Compute portfolio-wide risk metrics.

        Returns:
            {
                "total_properties": int,
                "assessed_properties": int,
                "risk_level_distribution": {
                    "low": {"count": int, "percentage": float},
                    "medium": {...}, "high": {...}, "critical": {...},
                },
                "geographic_distribution": {
                    "by_state": {"CA": 12, ...},
                    "by_county": {"Riverside": 5, ...},
                },
                "score_stats": {
                    "average": float, "median": float,
                    "min": float, "max": float,
                },
                "latest_assessment_timestamp": Optional[str],
            }

        Properties with no assessment yet are counted in total_properties
        but excluded from risk_level_distribution, geographic_distribution,
        and score_stats (which are all about assessed risk) - reported
        separately via assessed_properties so the gap is visible rather
        than silently treated as "0 risk."
        """
        properties = self.property_dao.get_all_properties()
        assessments = self.risk_dao.get_all_latest_assessments()

        properties_by_id = {p["property_id"]: p for p in properties}
        assessed_properties = [
            a for a in assessments if a["property_id"] in properties_by_id
        ]

        metrics = {
            "total_properties": len(properties),
            "assessed_properties": len(assessed_properties),
            "risk_level_distribution": self._risk_level_distribution(assessed_properties),
            "geographic_distribution": self._geographic_distribution(assessed_properties, properties_by_id),
            "score_stats": self._score_stats(assessed_properties),
            "latest_assessment_timestamp": self._latest_timestamp(assessed_properties),
        }

        logger.info(
            "Portfolio metrics: %d/%d properties assessed, avg score=%.2f",
            metrics["assessed_properties"], metrics["total_properties"],
            metrics["score_stats"]["average"],
        )
        return metrics

    @staticmethod
    def _risk_level_distribution(assessments: List[Dict]) -> Dict:
        total = len(assessments)
        counts = {level: 0 for level in RISK_LEVELS}
        for a in assessments:
            level = a.get("risk_level")
            if level in counts:
                counts[level] += 1

        return {
            level: {
                "count": count,
                "percentage": round((count / total * 100), 2) if total else 0.0,
            }
            for level, count in counts.items()
        }

    @staticmethod
    def _geographic_distribution(assessments: List[Dict], properties_by_id: Dict) -> Dict:
        by_state: Dict[str, int] = {}
        by_county: Dict[str, int] = {}

        for a in assessments:
            prop = properties_by_id.get(a["property_id"], {})
            state = prop.get("state")
            county = prop.get("county")
            if state:
                by_state[state] = by_state.get(state, 0) + 1
            if county:
                by_county[county] = by_county.get(county, 0) + 1

        return {"by_state": by_state, "by_county": by_county}

    @staticmethod
    def _score_stats(assessments: List[Dict]) -> Dict:
        scores = [
            a["overall_risk_score"] for a in assessments
            if a.get("overall_risk_score") is not None
        ]
        if not scores:
            return {"average": 0.0, "median": 0.0, "min": 0.0, "max": 0.0}

        return {
            "average": round(sum(scores) / len(scores), 2),
            "median": round(statistics.median(scores), 2),
            "min": round(min(scores), 2),
            "max": round(max(scores), 2),
        }

    @staticmethod
    def _latest_timestamp(assessments: List[Dict]) -> Optional[str]:
        timestamps = [a["assessment_timestamp"] for a in assessments if a.get("assessment_timestamp")]
        return max(timestamps) if timestamps else None


if __name__ == "__main__":
    print("=" * 60)
    print("Portfolio Aggregator Test")
    print("=" * 60)
    print()

    aggregator = PortfolioAggregator()
    metrics = aggregator.get_portfolio_metrics()

    print(f"Total properties:     {metrics['total_properties']}")
    print(f"Assessed properties:  {metrics['assessed_properties']}")
    print()

    print("Risk level distribution:")
    for level, data in metrics["risk_level_distribution"].items():
        print(f"  {level:10s}: {data['count']:4d} ({data['percentage']:.1f}%)")
    print()

    print("Geographic distribution (by state):")
    for state, count in sorted(metrics["geographic_distribution"]["by_state"].items()):
        print(f"  {state}: {count}")
    print()

    print("Score stats:")
    for k, v in metrics["score_stats"].items():
        print(f"  {k}: {v}")
    print()

    print(f"Latest assessment: {metrics['latest_assessment_timestamp']}")

    print()
    print("=" * 60)
