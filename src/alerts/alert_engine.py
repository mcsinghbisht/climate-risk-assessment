"""
Alert Threshold Engine

Evaluates a property's current (and optionally previous) wildfire/flood risk
scores against configured thresholds, producing structured alert records
matching the `alerts` table schema (Task 3). Two independent trigger
conditions per hazard type:

  - Absolute threshold: current score alone exceeds a critical threshold
  - Sudden increase: score jumped by more than N points since the last
    assessment

Both wildfire and flood are evaluated independently - a property can
trigger a wildfire alert, a flood alert, both, or neither. All thresholds
are configuration-driven (config/settings.json -> alerts.*), unused since
Task 5 until now.
"""

import logging
from typing import Dict, List, Optional

from src.config import get_config
from src.utils import get_utc_now

logger = logging.getLogger(__name__)

DEFAULT_ALERTS_CONFIG = {
    "wildfire_threshold": 70,
    "wildfire_increase_threshold": 40,
    "flood_threshold": 65,
    "flood_increase_threshold": 30,
    "portfolio_threshold_percent": 10,
}

PORTFOLIO_RISK_TYPE = "portfolio_high_risk_pct"


class AlertEngine:
    """Evaluates risk scores against configured alert thresholds."""

    def __init__(self):
        config = get_config()
        alerts_cfg = config.get_section("alerts")
        self.wildfire_threshold: float = alerts_cfg.get(
            "wildfire_threshold", DEFAULT_ALERTS_CONFIG["wildfire_threshold"]
        )
        self.wildfire_increase_threshold: float = alerts_cfg.get(
            "wildfire_increase_threshold", DEFAULT_ALERTS_CONFIG["wildfire_increase_threshold"]
        )
        self.flood_threshold: float = alerts_cfg.get(
            "flood_threshold", DEFAULT_ALERTS_CONFIG["flood_threshold"]
        )
        self.flood_increase_threshold: float = alerts_cfg.get(
            "flood_increase_threshold", DEFAULT_ALERTS_CONFIG["flood_increase_threshold"]
        )
        self.portfolio_threshold_percent: float = alerts_cfg.get(
            "portfolio_threshold_percent", DEFAULT_ALERTS_CONFIG["portfolio_threshold_percent"]
        )

    def evaluate_property(
        self, property_id: int, current_risk: Dict, previous_risk: Optional[Dict] = None
    ) -> List[Dict]:
        """
        Evaluate a property's current (and optionally previous) risk scores
        against configured thresholds.

        Args:
            property_id: The property's ID
            current_risk: {"wildfire": score, "flood": score} - current scores
            previous_risk: {"wildfire": score, "flood": score} - previous
                           assessment's scores, or None if this is the
                           property's first-ever assessment (increase checks
                           are skipped in that case, not treated as an error)

        Returns:
            List of alert dicts (matching the `alerts` table schema), or []
            if nothing crossed a threshold. A single hazard type can produce
            up to two alerts (one for absolute threshold, one for a sudden
            increase) if both conditions are independently met.
        """
        alerts = []
        alerts.extend(self._evaluate_hazard(
            property_id, "wildfire",
            current_risk.get("wildfire"),
            previous_risk.get("wildfire") if previous_risk else None,
            self.wildfire_threshold, self.wildfire_increase_threshold,
        ))
        alerts.extend(self._evaluate_hazard(
            property_id, "flood",
            current_risk.get("flood"),
            previous_risk.get("flood") if previous_risk else None,
            self.flood_threshold, self.flood_increase_threshold,
        ))
        return alerts

    def evaluate_portfolio(self, high_critical_percent: float) -> Optional[Dict]:
        """
        Evaluate the portfolio-wide percentage of assessed properties in
        high/critical risk against portfolio_threshold_percent (Task 27 -
        see docs/alert-lifecycle-design.md, "Portfolio-Level Alerts").

        Unlike evaluate_property(), there is no "sudden increase" check
        here and only one alert can result - a portfolio accumulation
        breach is inherently the more severe signal regardless of how far
        past the threshold it is, so it's always alert_level='critical'.

        Args:
            high_critical_percent: Percentage (0-100) of assessed
                properties currently in the 'high' or 'critical' risk
                level, e.g. from PortfolioAggregator.get_portfolio_metrics().

        Returns:
            An alert dict (property_id=None, risk_type='portfolio_high_risk_pct'),
            matching the alerts table schema, or None if the threshold
            isn't crossed.
        """
        if high_critical_percent <= self.portfolio_threshold_percent:
            return None

        return {
            "property_id": None,
            "risk_type": PORTFOLIO_RISK_TYPE,
            "risk_score": high_critical_percent,
            "threshold_exceeded": self.portfolio_threshold_percent,
            "alert_level": "critical",
            "message": (
                f"{high_critical_percent:.1f}% of assessed properties are in high/critical "
                f"risk, exceeding the {self.portfolio_threshold_percent}% portfolio accumulation threshold."
            ),
            "triggered_at": get_utc_now().isoformat(),
        }

    def _evaluate_hazard(
        self, property_id: int, risk_type: str,
        current_score: Optional[float], previous_score: Optional[float],
        threshold: float, increase_threshold: float,
    ) -> List[Dict]:
        """Evaluate one hazard type's absolute and increase thresholds."""
        if current_score is None:
            return []

        triggered_at = get_utc_now().isoformat()
        alerts = []

        if current_score > threshold:
            alerts.append({
                "property_id": property_id,
                "risk_type": risk_type,
                "risk_score": current_score,
                "threshold_exceeded": threshold,
                "alert_level": "critical",
                "message": (
                    f"{risk_type.capitalize()} risk score {current_score} exceeds "
                    f"the critical threshold of {threshold}."
                ),
                "triggered_at": triggered_at,
            })

        if previous_score is not None:
            increase = current_score - previous_score
            if increase > increase_threshold:
                alerts.append({
                    "property_id": property_id,
                    "risk_type": risk_type,
                    "risk_score": current_score,
                    "threshold_exceeded": increase_threshold,
                    "alert_level": "warning",
                    "message": (
                        f"{risk_type.capitalize()} risk score increased by {increase:.1f} "
                        f"points (from {previous_score} to {current_score}), exceeding the "
                        f"{increase_threshold}-point increase threshold."
                    ),
                    "triggered_at": triggered_at,
                })

        return alerts


if __name__ == "__main__":
    print("=" * 60)
    print("Alert Engine Test")
    print("=" * 60)
    print()

    engine = AlertEngine()
    print(f"Wildfire threshold: {engine.wildfire_threshold} "
          f"(increase: {engine.wildfire_increase_threshold})")
    print(f"Flood threshold:    {engine.flood_threshold} "
          f"(increase: {engine.flood_increase_threshold})")
    print()

    test_cases = [
        (1, {"wildfire": 75, "flood": 30}, {"wildfire": 60, "flood": 30}, "Absolute wildfire threshold crossed"),
        (2, {"wildfire": 50, "flood": 60}, {"wildfire": 15, "flood": 60}, "35-point wildfire increase"),
        (3, {"wildfire": 20, "flood": 20}, {"wildfire": 10, "flood": 10}, "No thresholds crossed"),
        (4, {"wildfire": 80, "flood": 70}, None, "First-ever assessment (no previous)"),
    ]

    for property_id, current, previous, label in test_cases:
        alerts = engine.evaluate_property(property_id, current, previous)
        print(f"Property {property_id} ({label}): {len(alerts)} alert(s)")
        for alert in alerts:
            print(f"  [{alert['alert_level'].upper()}] {alert['message']}")
        print()

    print("=" * 60)
    print("All tests complete!")
    print("=" * 60)
