"""
Pytest test suite for Notifier (Task 21)

Run with: pytest tests/test_notification_pytest.py -v
"""

import logging

import pytest

from src.config import setup_logging
from src.alerts.notification import Notifier
from src.alerts.alert_engine import AlertEngine

# The propagate=False behavior these tests rely on only takes effect once
# Task 6's dictConfig is actually applied - call it explicitly here so this
# test file doesn't depend on some other test module happening to have
# called setup_logging() first in the same pytest session.
setup_logging()


@pytest.fixture
def notifier():
    return Notifier()


LEGACY_ALERT = {
    "alert_id": "TEST_001",
    "property_id": 1,
    "risk_type": "wildfire",
    "message": "Wildfire risk increased to 75",
    "timestamp": "2026-07-17T14:30:00Z",
}


class TestSendAlert:
    def test_critical_alert_logged_at_critical_level(self, notifier, caplog):
        alert = {**LEGACY_ALERT, "alert_level": "critical"}
        with caplog.at_level(logging.CRITICAL, logger="alerts"):
            notifier.send_alert(alert)
        assert any(r.levelno == logging.CRITICAL for r in caplog.records)

    def test_warning_alert_logged_at_warning_level(self, notifier, caplog):
        alert = {**LEGACY_ALERT, "alert_level": "warning"}
        with caplog.at_level(logging.WARNING, logger="alerts"):
            notifier.send_alert(alert)
        assert any(r.levelno == logging.WARNING for r in caplog.records)

    def test_missing_alert_level_defaults_to_warning(self, notifier, caplog):
        """LEGACY_ALERT has no 'alert_level' key at all - the illustrative
        shape from the original task spec."""
        with caplog.at_level(logging.WARNING, logger="alerts"):
            notifier.send_alert(LEGACY_ALERT)
        assert any(r.levelno == logging.WARNING for r in caplog.records)

    def test_message_contains_property_id_and_risk_type(self, notifier, caplog):
        with caplog.at_level(logging.WARNING, logger="alerts"):
            notifier.send_alert(LEGACY_ALERT)
        logged_text = caplog.text
        assert "Property 1" in logged_text
        assert "wildfire" in logged_text

    def test_alert_id_included_when_present(self, notifier, caplog):
        with caplog.at_level(logging.WARNING, logger="alerts"):
            notifier.send_alert(LEGACY_ALERT)
        assert "TEST_001" in caplog.text

    def test_missing_alert_id_does_not_crash(self, notifier, caplog):
        alert_without_id = {"property_id": 2, "risk_type": "flood", "message": "Test"}
        with caplog.at_level(logging.WARNING, logger="alerts"):
            notifier.send_alert(alert_without_id)  # should not raise
        assert "Property 2" in caplog.text

    def test_alerts_logger_does_not_propagate_to_root(self):
        """
        The 'alerts' logger must have propagate=False (Task 6 config) so
        alert messages never leak into the root logger's handlers/app.log.

        Asserts the actual logger attribute directly rather than using
        pytest's caplog fixture: caplog's cross-logger capture semantics
        do not reliably respect propagate=False (confirmed empirically -
        caplog attached to "root" still captured a record logged only to
        "alerts" with propagate=False), so it is not a trustworthy way to
        test this specific property. Checking the real, already-configured
        logger object directly is the correct and more precise test.
        """
        alerts_logger = logging.getLogger("alerts")
        assert alerts_logger.propagate is False


class TestSendAlerts:
    def test_sends_all_alerts_and_returns_count(self, notifier, caplog):
        alerts = [LEGACY_ALERT, {**LEGACY_ALERT, "property_id": 2}]
        with caplog.at_level(logging.WARNING, logger="alerts"):
            count = notifier.send_alerts(alerts)
        assert count == 2
        assert len(caplog.records) == 2

    def test_empty_list_sends_nothing(self, notifier, caplog):
        with caplog.at_level(logging.WARNING, logger="alerts"):
            count = notifier.send_alerts([])
        assert count == 0
        assert len(caplog.records) == 0


class TestIntegrationWithAlertEngine:
    """Confirms Notifier correctly handles AlertEngine's real output shape,
    not just the illustrative legacy shape."""

    def test_real_alert_engine_output_is_handled_correctly(self, notifier, caplog):
        engine = AlertEngine()
        alerts = engine.evaluate_property(
            property_id=42,
            current_risk={"wildfire": 80, "flood": 10},
            previous_risk={"wildfire": 20, "flood": 10},
        )
        assert len(alerts) == 2  # absolute + increase, both triggered

        with caplog.at_level(logging.WARNING, logger="alerts"):
            count = notifier.send_alerts(alerts)

        assert count == 2
        levels = {r.levelno for r in caplog.records}
        assert logging.CRITICAL in levels  # absolute threshold alert
        assert logging.WARNING in levels   # increase alert


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
