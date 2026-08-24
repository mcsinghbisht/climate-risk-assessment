"""
Continuous Monitoring Loop

Orchestrates a single end-to-end monitoring cycle: ingest hazard data,
score every property, detect what changed, evaluate and persist alerts,
and send notifications for anything newly due - tying together every
component built in Tasks 14, 19, 20, 21, 21b, and 22 for the first time.
Also evaluates the portfolio-level accumulation alert (Task 27 - see
docs/alert-lifecycle-design.md, "Portfolio-Level Alerts") once per cycle,
alongside the per-property loop.

This is the cycle Task 24's scheduler will run every 5 minutes. Each step
is wrapped for error isolation: one property's alert-handling failure does
not stop the rest of the portfolio from being processed, matching the same
principle already applied in IngestionEngine (Task 14) and
RiskScoringEngine (Task 19).

Known MVP simplification: after scoring, this loop re-queries each
property's assessment history and alert state individually (one property
at a time) rather than batching those reads. Correct and simple at 100
properties; the next place a batching/spatial-cell-style optimization
(mirroring Task 14's ingestion design) would be needed if portfolio size
grows substantially.
"""

import logging
from typing import Dict, List

from src.database import PropertyDAO, RiskDAO, AlertDAO
from src.data_ingestion.ingestion_engine import IngestionEngine
from src.risk_scoring.scoring_engine import RiskScoringEngine
from src.continuous_monitoring.change_detector import ChangeDetector
from src.alerts.alert_engine import AlertEngine
from src.alerts.notification import Notifier
from src.portfolio.aggregator import PortfolioAggregator
from src.utils import get_utc_now

logger = logging.getLogger(__name__)


class Monitor:
    """Orchestrates one full monitoring cycle: ingest -> score -> alert -> notify."""

    def __init__(self):
        self.property_dao = PropertyDAO()
        self.risk_dao = RiskDAO()
        self.alert_dao = AlertDAO()
        self.ingestion_engine = IngestionEngine()
        self.scoring_engine = RiskScoringEngine()
        self.change_detector = ChangeDetector()
        self.alert_engine = AlertEngine()
        self.notifier = Notifier()
        self.portfolio_aggregator = PortfolioAggregator()

    def run_monitoring_cycle(self) -> Dict:
        """
        Run one complete monitoring cycle.

        Returns:
            {
                "cycle_timestamp": str,
                "hazard_records_ingested": int,
                "properties_scored": int,
                "new_alerts": int,
                "notifications_sent": int,
                "errors": List[str],
            }
        """
        cycle_started_at = get_utc_now()
        logger.info("=== Monitoring cycle starting at %s ===", cycle_started_at.isoformat())

        errors: List[str] = []

        # --- Step 1: Ingestion (Task 14) ---
        try:
            ingestion_summary = self.ingestion_engine.run_ingestion_cycle()
            hazard_records_ingested = (
                ingestion_summary.get("fires_ingested", 0)
                + ingestion_summary.get("weather_points", 0)
                + ingestion_summary.get("precipitation_points", 0)
                + ingestion_summary.get("gauge_readings", 0)
            )
            errors.extend(f"ingestion: {e}" for e in ingestion_summary.get("errors", []))
        except Exception as e:
            logger.error("Ingestion step failed entirely: %s", e)
            hazard_records_ingested = 0
            errors.append(f"ingestion: {e}")

        # --- Step 2: Scoring (Task 19) ---
        try:
            scoring_summary = self.scoring_engine.score_all_properties()
            errors.extend(f"scoring: {e}" for e in scoring_summary.get("errors", []))
        except Exception as e:
            logger.error("Scoring step failed entirely: %s", e)
            scoring_summary = {"properties_scored": 0}
            errors.append(f"scoring: {e}")

        # --- Step 3: Change detection + alerting + notification, per property ---
        new_alert_count = 0
        notifications_sent = 0

        for property_data in self.property_dao.get_all_properties():
            property_id = property_data["property_id"]
            try:
                new_alert_count += self._process_property_alerts(property_id)
                notifications_sent += self._send_due_notifications(property_id)
            except Exception as e:
                logger.error("Alert processing failed for property_id=%s: %s", property_id, e)
                errors.append(f"alerts property_id={property_id}: {e}")

        # --- Step 4: Portfolio-level accumulation alert (Task 27) ---
        try:
            new_alert_count += self._process_portfolio_alert()
            notifications_sent += self._send_due_notifications(None)
        except Exception as e:
            logger.error("Portfolio-level alert processing failed: %s", e)
            errors.append(f"portfolio alert: {e}")

        duration = (get_utc_now() - cycle_started_at).total_seconds()
        summary = {
            "cycle_timestamp": cycle_started_at.isoformat(),
            "hazard_records_ingested": hazard_records_ingested,
            "properties_scored": scoring_summary.get("properties_scored", 0),
            "new_alerts": new_alert_count,
            "notifications_sent": notifications_sent,
            "errors": errors,
        }

        logger.info(
            "=== Monitoring cycle complete in %.1fs: %d hazard records, %d properties scored, "
            "%d new alerts, %d notifications sent, %d errors ===",
            duration, summary["hazard_records_ingested"], summary["properties_scored"],
            summary["new_alerts"], summary["notifications_sent"], len(errors),
        )
        return summary

    def _process_property_alerts(self, property_id: int) -> int:
        """
        For one property: detect changes, evaluate new alert triggers,
        persist them, and re-evaluate the lifecycle of any existing alert
        (so resolution/staleness are detected even when no new alert fires
        this cycle). Returns the number of genuinely new alerts created.
        """
        history = self.risk_dao.get_assessment_history(property_id, days=1)
        if not history:
            return 0

        current = history[0]
        previous = history[1] if len(history) > 1 else None

        change = self.change_detector.detect_changes(property_id, current, previous)
        if change["changed"]:
            logger.info(
                "Property %s changed: trend=%s, delta=%s",
                property_id, change["trend"], change["risk_delta"],
            )

        current_scores = {
            "wildfire": current.get("wildfire_risk_score"),
            "flood": current.get("flood_risk_score"),
        }
        previous_scores = None
        if previous:
            previous_scores = {
                "wildfire": previous.get("wildfire_risk_score"),
                "flood": previous.get("flood_risk_score"),
            }

        triggered_alerts = self.alert_engine.evaluate_property(property_id, current_scores, previous_scores)
        new_ids = self.alert_dao.save_new_alerts(triggered_alerts) if triggered_alerts else []

        # Re-evaluate lifecycle for both hazard types regardless of whether
        # a new trigger fired this cycle - this is what detects resolution
        # and staleness for alerts raised in an earlier cycle.
        assessment_timestamp = current.get("assessment_timestamp")
        for risk_type in ("wildfire", "flood"):
            score = current_scores.get(risk_type)
            if score is not None:
                self.alert_dao.evaluate_lifecycle(property_id, risk_type, score, assessment_timestamp)

        return len(new_ids)

    def _process_portfolio_alert(self) -> int:
        """
        Evaluate the portfolio-wide high/critical percentage against
        portfolio_threshold_percent, persist a new alert if it's newly
        crossed, and re-evaluate the lifecycle of any existing portfolio
        alert (resolution/staleness) regardless of whether a new one fired
        this cycle - same reasoning as _process_property_alerts, just keyed
        on risk_type='portfolio_high_risk_pct' with property_id=None
        instead of a specific property. Returns the number of genuinely
        new alerts created (0 or 1).
        """
        metrics = self.portfolio_aggregator.get_portfolio_metrics()
        if metrics["assessed_properties"] == 0:
            return 0

        dist = metrics["risk_level_distribution"]
        high_critical_percent = dist["high"]["percentage"] + dist["critical"]["percentage"]

        alert = self.alert_engine.evaluate_portfolio(high_critical_percent)
        new_ids = self.alert_dao.save_new_alerts([alert]) if alert else []

        self.alert_dao.evaluate_lifecycle(
            None, "portfolio_high_risk_pct", high_critical_percent, metrics["latest_assessment_timestamp"]
        )

        return len(new_ids)

    def _send_due_notifications(self, property_id) -> int:
        """Send notifications for any of this property's (or, if
        property_id=None, the portfolio's) alerts whose re-notification
        cooldown has elapsed. Returns the count sent."""
        sent = 0
        for alert in self.alert_dao.get_alerts_for_property(property_id):
            if self.alert_dao.should_notify(alert["alert_id"]):
                self.notifier.send_alert(alert)
                self.alert_dao.mark_notified(alert["alert_id"])
                sent += 1
        return sent


if __name__ == "__main__":
    from src.config import setup_logging

    setup_logging()

    print("=" * 60)
    print("Continuous Monitoring Loop - Task 23")
    print("=" * 60)
    print()

    monitor = Monitor()
    summary = monitor.run_monitoring_cycle()

    print(f"Cycle timestamp:       {summary['cycle_timestamp']}")
    print(f"Hazard records:        {summary['hazard_records_ingested']}")
    print(f"Properties scored:     {summary['properties_scored']}")
    print(f"New alerts:            {summary['new_alerts']}")
    print(f"Notifications sent:    {summary['notifications_sent']}")
    if summary["errors"]:
        print("Errors:")
        for err in summary["errors"]:
            print(f"  - {err}")

    print()
    print("=" * 60)
