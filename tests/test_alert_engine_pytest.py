"""
Pytest test suite for AlertEngine (Task 20)

Run with: pytest tests/test_alert_engine_pytest.py -v
"""

import pytest

from src.alerts.alert_engine import AlertEngine


@pytest.fixture
def engine():
    return AlertEngine()


class TestAbsoluteThreshold:
    def test_wildfire_above_threshold_triggers_critical_alert(self, engine):
        alerts = engine.evaluate_property(
            1, current_risk={"wildfire": 75, "flood": 30}, previous_risk={"wildfire": 60, "flood": 30}
        )
        assert len(alerts) == 1
        assert alerts[0]["risk_type"] == "wildfire"
        assert alerts[0]["alert_level"] == "critical"

    def test_wildfire_exactly_at_threshold_does_not_trigger(self, engine):
        """Strict '>' comparison, matching the pattern used elsewhere
        (e.g. RiskAggregator.classify_risk_level's '<=' boundaries)."""
        alerts = engine.evaluate_property(
            1, current_risk={"wildfire": 70, "flood": 30}, previous_risk={"wildfire": 70, "flood": 30}
        )
        assert alerts == []

    def test_flood_above_threshold_triggers_critical_alert(self, engine):
        alerts = engine.evaluate_property(
            1, current_risk={"wildfire": 10, "flood": 66}, previous_risk={"wildfire": 10, "flood": 66}
        )
        assert len(alerts) == 1
        assert alerts[0]["risk_type"] == "flood"
        assert alerts[0]["alert_level"] == "critical"

    def test_both_hazards_crossing_threshold_produce_two_alerts(self, engine):
        alerts = engine.evaluate_property(
            1, current_risk={"wildfire": 80, "flood": 70}, previous_risk={"wildfire": 80, "flood": 70}
        )
        assert len(alerts) == 2
        risk_types = {a["risk_type"] for a in alerts}
        assert risk_types == {"wildfire", "flood"}


class TestIncreaseThreshold:
    def test_large_wildfire_increase_triggers_warning_alert(self, engine):
        """The corrected spec example: 15 -> 60 is a 45-point jump,
        exceeding wildfire_increase_threshold=40."""
        alerts = engine.evaluate_property(
            2, current_risk={"wildfire": 60, "flood": 60}, previous_risk={"wildfire": 15, "flood": 60}
        )
        assert len(alerts) == 1
        assert alerts[0]["risk_type"] == "wildfire"
        assert alerts[0]["alert_level"] == "warning"

    def test_35_point_increase_does_not_cross_40_point_threshold(self, engine):
        """
        Regression test documenting a real discrepancy found while
        implementing this task: the original task-breakdown.md spec's
        illustrative example used a 35-point jump (15->50) and asserted it
        would trigger an alert - but wildfire_increase_threshold is
        configured to 40 (config/settings.json, set in Task 5), so a
        35-point jump correctly does NOT cross it. The doc's example was
        corrected to a 45-point jump; this test locks in the correct,
        config-driven behavior for the original (now-incorrect) example.
        """
        alerts = engine.evaluate_property(
            2, current_risk={"wildfire": 50, "flood": 60}, previous_risk={"wildfire": 15, "flood": 60}
        )
        assert alerts == []

    def test_increase_exactly_at_threshold_does_not_trigger(self, engine):
        alerts = engine.evaluate_property(
            1, current_risk={"wildfire": 50, "flood": 30}, previous_risk={"wildfire": 10, "flood": 30}
        )
        assert alerts == []  # exactly 40-point increase, strict '>' required

    def test_increase_one_point_above_threshold_triggers(self, engine):
        alerts = engine.evaluate_property(
            1, current_risk={"wildfire": 51, "flood": 30}, previous_risk={"wildfire": 10, "flood": 30}
        )
        assert len(alerts) == 1
        assert alerts[0]["alert_level"] == "warning"


class TestNoAlertScenarios:
    def test_no_thresholds_crossed_returns_empty_list(self, engine):
        alerts = engine.evaluate_property(
            1, current_risk={"wildfire": 20, "flood": 20}, previous_risk={"wildfire": 10, "flood": 10}
        )
        assert alerts == []

    def test_no_previous_risk_only_checks_absolute_threshold(self, engine):
        """First-ever assessment for a property - no crash, increase check
        is simply skipped rather than treated as an error."""
        alerts = engine.evaluate_property(
            1, current_risk={"wildfire": 80, "flood": 10}, previous_risk=None
        )
        assert len(alerts) == 1
        assert alerts[0]["risk_type"] == "wildfire"

    def test_no_previous_risk_and_no_absolute_breach_returns_empty(self, engine):
        alerts = engine.evaluate_property(
            1, current_risk={"wildfire": 20, "flood": 10}, previous_risk=None
        )
        assert alerts == []


class TestBothTriggersOnSameHazard:
    def test_absolute_and_increase_both_triggered_produce_two_alerts(self, engine):
        """A score that both exceeds the absolute threshold AND jumped more
        than the increase threshold produces two distinct alerts for the
        same hazard type - they represent different reasons to escalate."""
        alerts = engine.evaluate_property(
            1, current_risk={"wildfire": 90, "flood": 10}, previous_risk={"wildfire": 20, "flood": 10}
        )
        wildfire_alerts = [a for a in alerts if a["risk_type"] == "wildfire"]
        assert len(wildfire_alerts) == 2
        levels = {a["alert_level"] for a in wildfire_alerts}
        assert levels == {"critical", "warning"}


class TestAlertShape:
    def test_alert_has_all_expected_fields(self, engine):
        alerts = engine.evaluate_property(
            1, current_risk={"wildfire": 80, "flood": 10}, previous_risk=None
        )
        alert = alerts[0]
        for field in ["property_id", "risk_type", "risk_score", "threshold_exceeded",
                      "alert_level", "message", "triggered_at"]:
            assert field in alert

    def test_property_id_matches_input(self, engine):
        alerts = engine.evaluate_property(
            42, current_risk={"wildfire": 80, "flood": 10}, previous_risk=None
        )
        assert alerts[0]["property_id"] == 42


class TestEvaluatePortfolio:
    """Task 27: portfolio-level accumulation alert."""

    def test_above_threshold_triggers_critical_alert(self, engine):
        alert = engine.evaluate_portfolio(15.0)  # default threshold is 10%
        assert alert is not None
        assert alert["alert_level"] == "critical"
        assert alert["property_id"] is None
        assert alert["risk_type"] == "portfolio_high_risk_pct"
        assert alert["risk_score"] == 15.0

    def test_at_threshold_does_not_trigger(self, engine):
        assert engine.evaluate_portfolio(10.0) is None  # strict '>' comparison

    def test_below_threshold_returns_none(self, engine):
        assert engine.evaluate_portfolio(5.0) is None

    def test_message_includes_percentage_and_threshold(self, engine):
        alert = engine.evaluate_portfolio(23.4)
        assert "23.4%" in alert["message"]
        assert "10%" in alert["message"]

    def test_alert_has_all_expected_fields(self, engine):
        alert = engine.evaluate_portfolio(50.0)
        for field in ["property_id", "risk_type", "risk_score", "threshold_exceeded",
                      "alert_level", "message", "triggered_at"]:
            assert field in alert


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
