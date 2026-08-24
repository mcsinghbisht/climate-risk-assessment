"""
Alert Notification System

Formats and sends alerts (from AlertEngine, Task 20) to configured channels.
Reuses the `alerts` logger already wired up in Task 6's logging framework
(console + logs/alerts.log, both at INFO level, no propagation to the root
logger's app.log) rather than building new output plumbing - alert output
is exactly what that logger was built for.

Designed to be easy to extend: additional channels (email, SMS, Slack) can
be added as new private _send_to_* methods and registered in send_alert(),
without changing the public interface.
"""

import logging
from typing import Dict, List

logger = logging.getLogger("alerts")


class Notifier:
    """Formats and dispatches alerts to configured notification channels."""

    def send_alert(self, alert: Dict) -> None:
        """
        Send a single alert to all configured channels (currently console +
        logs/alerts.log, via the shared 'alerts' logger from Task 6).

        Args:
            alert: An alert dict. Tolerant of both AlertEngine's actual
                   output shape (risk_type, risk_score, alert_level,
                   message, triggered_at) and the simpler illustrative
                   shape from the original task spec (alert_id, message,
                   timestamp) - missing fields are handled gracefully
                   rather than raising.
        """
        formatted = self._format_alert(alert)
        level = (alert.get("alert_level") or "warning").lower()

        if level == "critical":
            logger.critical(formatted)
        else:
            logger.warning(formatted)

    def send_alerts(self, alerts: List[Dict]) -> int:
        """
        Send multiple alerts in one call.

        Args:
            alerts: List of alert dicts

        Returns:
            Number of alerts sent
        """
        for alert in alerts:
            self.send_alert(alert)
        return len(alerts)

    @staticmethod
    def _format_alert(alert: Dict) -> str:
        """Format an alert dict into a single readable log line."""
        property_id = alert.get("property_id", "unknown")
        risk_type = alert.get("risk_type", "unknown")
        message = alert.get("message", "No message provided")
        alert_id = alert.get("alert_id")

        prefix = f"[{alert_id}] " if alert_id else ""
        return f"{prefix}Property {property_id} ({risk_type}): {message}"


if __name__ == "__main__":
    from src.config import setup_logging

    setup_logging()

    print("=" * 60)
    print("Alert Notification System Test")
    print("=" * 60)
    print()

    notifier = Notifier()

    # Exact shape from the original task spec's illustrative example
    print("1. Sending a simple/legacy-shaped alert...")
    legacy_alert = {
        "alert_id": "TEST_001",
        "property_id": 1,
        "risk_type": "wildfire",
        "message": "Wildfire risk increased to 75",
        "timestamp": "2026-07-17T14:30:00Z",
    }
    notifier.send_alert(legacy_alert)
    print("Alert sent (see console output above and logs/alerts.log)")

    # Real shape, as produced by AlertEngine (Task 20)
    print()
    print("2. Sending real AlertEngine-shaped alerts...")
    from src.alerts.alert_engine import AlertEngine

    engine = AlertEngine()
    real_alerts = engine.evaluate_property(
        property_id=42,
        current_risk={"wildfire": 80, "flood": 10},
        previous_risk={"wildfire": 20, "flood": 10},
    )
    sent_count = notifier.send_alerts(real_alerts)
    print(f"Sent {sent_count} real alert(s) (see console output above and logs/alerts.log)")

    print()
    print("=" * 60)
    print(f"Check logs/alerts.log for {1 + sent_count} total entries")
    print("=" * 60)
