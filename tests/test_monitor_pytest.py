"""
Pytest test suite for Monitor (Task 23)

Run with: pytest tests/test_monitor_pytest.py -v

Ingestion and scoring are stubbed out (fakes) since they depend on live
external APIs (Tasks 11-13) and real hazard-driven scoring is already
covered by test_scoring_engine_pytest.py (Task 19). What this suite
exercises is the real orchestration: given assessments already in the
database, does run_monitoring_cycle() correctly detect changes, raise
alerts, persist them, evaluate lifecycle transitions, and notify - using
the real ChangeDetector, AlertEngine, AlertDAO, RiskDAO, and PropertyDAO,
not mocks, against a temporary SQLite database.
"""

import pytest

import src.database.db as db_module
from src.continuous_monitoring.monitor import Monitor


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """Temporary SQLite database with the full schema this cycle touches."""
    db_path = tmp_path / "test_climate_risk.db"
    monkeypatch.setattr(db_module, "DB_PATH", db_path)

    conn = db_module.get_db_connection()
    schema = db_module.get_schema()
    for table in ("properties", "hazard_data", "risk_assessments", "alerts", "alert_history"):
        conn.execute(schema[table])
    conn.commit()
    conn.close()

    return db_path


def add_property(property_id=1, lat=33.75, lon=-116.72):
    conn = db_module.get_db_connection()
    conn.execute(
        "INSERT INTO properties (property_id, address, latitude, longitude) VALUES (?, ?, ?, ?)",
        (property_id, f"Property {property_id}", lat, lon),
    )
    conn.commit()
    conn.close()


def pad_with_low_risk_properties(count=15, start_id=100):
    """
    Add extra low-risk assessed properties so a single high-risk test
    property stays under the portfolio-level accumulation threshold
    (10% by default) - keeping these tests scoped to property-level
    alerting rather than also incidentally triggering the Task 27
    portfolio alert.
    """
    for pid in range(start_id, start_id + count):
        add_property(pid)
        add_assessment(pid, wildfire_score=5.0, overall_score=5.0, risk_level="low")


def add_assessment(property_id, wildfire_score, flood_score=5.0, overall_score=None, risk_level="low"):
    from src.database import RiskDAO
    RiskDAO().save_assessment({
        "property_id": property_id,
        "wildfire_risk_score": wildfire_score,
        "wildfire_factors": {},
        "flood_risk_score": flood_score,
        "flood_factors": {},
        "overall_risk_score": overall_score if overall_score is not None else wildfire_score,
        "risk_level": risk_level,
        "wildfire_explanation": "test",
        "flood_explanation": "test",
    })


class FakeIngestionEngine:
    def __init__(self, summary=None, error=None):
        self._summary = summary or {
            "fires_ingested": 3, "weather_points": 2, "precipitation_points": 1,
            "gauge_readings": 0, "cells_processed": 1, "cells_skipped_fresh": 0, "errors": [],
        }
        self._error = error

    def run_ingestion_cycle(self):
        if self._error:
            raise self._error
        return self._summary


class FakeScoringEngine:
    def __init__(self, summary=None, error=None):
        self._summary = summary or {
            "properties_scored": 0, "average_risk": 0.0, "high_risk_count": 0,
            "critical_count": 0, "errors": [],
        }
        self._error = error

    def score_all_properties(self):
        if self._error:
            raise self._error
        return self._summary


class FakeNotifier:
    def __init__(self):
        self.sent = []

    def send_alert(self, alert):
        self.sent.append(alert)


@pytest.fixture
def monitor(temp_db):
    m = Monitor()
    m.ingestion_engine = FakeIngestionEngine()
    m.scoring_engine = FakeScoringEngine()
    m.notifier = FakeNotifier()
    return m


class TestCycleSummaryShape:
    def test_empty_portfolio_completes_cleanly(self, monitor):
        summary = monitor.run_monitoring_cycle()
        assert summary["properties_scored"] == 0
        assert summary["new_alerts"] == 0
        assert summary["notifications_sent"] == 0
        assert summary["errors"] == []

    def test_result_has_all_expected_keys(self, monitor):
        summary = monitor.run_monitoring_cycle()
        for key in ["cycle_timestamp", "hazard_records_ingested", "properties_scored",
                    "new_alerts", "notifications_sent", "errors"]:
            assert key in summary

    def test_hazard_records_ingested_sums_all_categories(self, monitor):
        # 3 + 2 + 1 + 0 from FakeIngestionEngine's default summary
        summary = monitor.run_monitoring_cycle()
        assert summary["hazard_records_ingested"] == 6

    def test_properties_scored_reflects_scoring_summary(self, temp_db):
        m = Monitor()
        m.ingestion_engine = FakeIngestionEngine()
        m.scoring_engine = FakeScoringEngine(summary={
            "properties_scored": 42, "average_risk": 10.0, "high_risk_count": 0,
            "critical_count": 0, "errors": [],
        })
        m.notifier = FakeNotifier()
        summary = m.run_monitoring_cycle()
        assert summary["properties_scored"] == 42


class TestErrorIsolation:
    def test_ingestion_failure_is_captured_not_raised(self, temp_db):
        m = Monitor()
        m.ingestion_engine = FakeIngestionEngine(error=RuntimeError("API down"))
        m.scoring_engine = FakeScoringEngine()
        m.notifier = FakeNotifier()
        summary = m.run_monitoring_cycle()
        assert summary["hazard_records_ingested"] == 0
        assert any("ingestion" in e for e in summary["errors"])

    def test_scoring_failure_is_captured_not_raised(self, temp_db):
        m = Monitor()
        m.ingestion_engine = FakeIngestionEngine()
        m.scoring_engine = FakeScoringEngine(error=RuntimeError("DB locked"))
        m.notifier = FakeNotifier()
        summary = m.run_monitoring_cycle()
        assert summary["properties_scored"] == 0
        assert any("scoring" in e for e in summary["errors"])

    def test_ingestion_internal_errors_are_surfaced(self, monitor):
        monitor.ingestion_engine = FakeIngestionEngine(summary={
            "fires_ingested": 0, "weather_points": 0, "precipitation_points": 0,
            "gauge_readings": 0, "cells_processed": 0, "cells_skipped_fresh": 0,
            "errors": ["cell (33.5, -117.0): timeout"],
        })
        summary = monitor.run_monitoring_cycle()
        assert any("ingestion" in e for e in summary["errors"])

    def test_one_property_alert_failure_does_not_stop_others(self, monitor, monkeypatch):
        add_property(1)
        add_property(2)
        add_assessment(1, wildfire_score=90.0, overall_score=90.0, risk_level="critical")
        add_assessment(2, wildfire_score=90.0, overall_score=90.0, risk_level="critical")

        original = monitor.alert_engine.evaluate_property

        def flaky_evaluate(property_id, current, previous=None):
            if property_id == 1:
                raise RuntimeError("boom")
            return original(property_id, current, previous)

        monkeypatch.setattr(monitor.alert_engine, "evaluate_property", flaky_evaluate)

        summary = monitor.run_monitoring_cycle()
        assert any("property_id=1" in e for e in summary["errors"])
        # property 2 still got processed despite property 1's failure
        assert summary["new_alerts"] >= 1


class TestAlertingIntegration:
    def test_new_alert_created_for_property_crossing_threshold(self, monitor):
        add_property(1)
        add_assessment(1, wildfire_score=85.0, overall_score=85.0, risk_level="critical")
        pad_with_low_risk_properties()

        summary = monitor.run_monitoring_cycle()
        assert summary["new_alerts"] == 1  # absolute threshold only, no previous score to compare

        from src.database import AlertDAO
        active = AlertDAO().get_active_alerts()
        assert len(active) == 1
        assert active[0]["property_id"] == 1

    def test_no_alert_for_low_risk_property(self, monitor):
        add_property(1)
        add_assessment(1, wildfire_score=10.0, overall_score=10.0, risk_level="low")

        summary = monitor.run_monitoring_cycle()
        assert summary["new_alerts"] == 0

    def test_notification_sent_for_new_alert(self, monitor):
        add_property(1)
        add_assessment(1, wildfire_score=85.0, overall_score=85.0, risk_level="critical")
        pad_with_low_risk_properties()

        summary = monitor.run_monitoring_cycle()
        assert summary["notifications_sent"] == 1
        assert len(monitor.notifier.sent) == 1

    def test_renotification_cooldown_prevents_duplicate_sends(self, monitor):
        add_property(1)
        add_assessment(1, wildfire_score=85.0, overall_score=85.0, risk_level="critical")
        pad_with_low_risk_properties()

        monitor.run_monitoring_cycle()
        assert len(monitor.notifier.sent) == 1

        # Second cycle, same ongoing condition - cooldown should suppress re-send
        monitor.run_monitoring_cycle()
        assert len(monitor.notifier.sent) == 1

    def test_alert_resolves_when_score_drops_and_stops_notifying(self, monitor):
        add_property(1)
        add_assessment(1, wildfire_score=85.0, overall_score=85.0, risk_level="critical")
        monitor.run_monitoring_cycle()

        add_assessment(1, wildfire_score=10.0, overall_score=10.0, risk_level="low")
        monitor.run_monitoring_cycle()

        from src.database import AlertDAO
        assert AlertDAO().get_active_alerts() == []

    def test_both_absolute_and_increase_alerts_created_independently(self, monitor):
        add_property(1)
        add_assessment(1, wildfire_score=20.0, overall_score=20.0, risk_level="low")
        add_assessment(1, wildfire_score=85.0, overall_score=60.0, risk_level="high")
        pad_with_low_risk_properties()

        summary = monitor.run_monitoring_cycle()
        assert summary["new_alerts"] == 2  # crosses absolute threshold (70) AND increase threshold (40)


class TestPortfolioAlertIntegration:
    def test_portfolio_alert_created_when_percentage_exceeds_threshold(self, monitor):
        # 2 of 3 assessed properties high/critical -> 66.7%, well above the 10% default
        add_property(1)
        add_property(2)
        add_property(3)
        add_assessment(1, wildfire_score=85.0, overall_score=85.0, risk_level="critical")
        add_assessment(2, wildfire_score=80.0, overall_score=80.0, risk_level="high")
        add_assessment(3, wildfire_score=5.0, overall_score=5.0, risk_level="low")

        summary = monitor.run_monitoring_cycle()
        assert summary["new_alerts"] == 3  # 2 property-level (absolute threshold) + 1 portfolio-level

        from src.database import AlertDAO
        portfolio_alerts = [a for a in AlertDAO().get_active_alerts() if a["risk_type"] == "portfolio_high_risk_pct"]
        assert len(portfolio_alerts) == 1
        assert portfolio_alerts[0]["property_id"] is None

    def test_no_portfolio_alert_when_below_threshold(self, monitor):
        add_property(1)
        add_assessment(1, wildfire_score=85.0, overall_score=85.0, risk_level="critical")
        pad_with_low_risk_properties()  # keeps the percentage under 10%

        monitor.run_monitoring_cycle()

        from src.database import AlertDAO
        portfolio_alerts = [a for a in AlertDAO().get_active_alerts() if a["risk_type"] == "portfolio_high_risk_pct"]
        assert portfolio_alerts == []

    def test_portfolio_alert_resolves_when_percentage_drops(self, monitor):
        add_property(1)
        add_property(2)
        add_assessment(1, wildfire_score=85.0, overall_score=85.0, risk_level="critical")
        add_assessment(2, wildfire_score=80.0, overall_score=80.0, risk_level="high")
        monitor.run_monitoring_cycle()

        from src.database import AlertDAO
        assert any(a["risk_type"] == "portfolio_high_risk_pct" for a in AlertDAO().get_active_alerts())

        # Both properties recover, plus enough low-risk padding that even a
        # rounding edge case can't keep the percentage above the resolution point
        add_assessment(1, wildfire_score=5.0, overall_score=5.0, risk_level="low")
        add_assessment(2, wildfire_score=5.0, overall_score=5.0, risk_level="low")
        pad_with_low_risk_properties()
        monitor.run_monitoring_cycle()

        portfolio_alerts = [a for a in AlertDAO().get_active_alerts() if a["risk_type"] == "portfolio_high_risk_pct"]
        assert portfolio_alerts == []

    def test_portfolio_notification_sent(self, monitor):
        add_property(1)
        add_property(2)
        add_assessment(1, wildfire_score=85.0, overall_score=85.0, risk_level="critical")
        add_assessment(2, wildfire_score=80.0, overall_score=80.0, risk_level="high")

        monitor.run_monitoring_cycle()
        assert any(a.get("risk_type") == "portfolio_high_risk_pct" for a in monitor.notifier.sent)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
