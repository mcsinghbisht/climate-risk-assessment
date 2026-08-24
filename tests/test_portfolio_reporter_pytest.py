"""
Pytest test suite for PortfolioReporter (Task 27)

Run with: pytest tests/test_portfolio_reporter_pytest.py -v

Uses a temporary SQLite database and a temporary reports directory -
exercises the real PortfolioAggregator/HotspotDetector/AlertDAO stack,
not mocks.
"""

import pytest

import src.database.db as db_module
from src.database import AlertDAO
from src.portfolio.reporter import PortfolioReporter
from src.utils import get_utc_now


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test_climate_risk.db"
    monkeypatch.setattr(db_module, "DB_PATH", db_path)

    conn = db_module.get_db_connection()
    schema = db_module.get_schema()
    for table in ("properties", "hazard_data", "risk_assessments", "alerts", "alert_history"):
        conn.execute(schema[table])
    conn.commit()
    conn.close()

    return db_path


def add_property(property_id, lat=34.0, lon=-118.0, state=None, county=None):
    conn = db_module.get_db_connection()
    conn.execute(
        "INSERT INTO properties (property_id, address, latitude, longitude, state, county) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (property_id, f"Property {property_id}", lat, lon, state, county),
    )
    conn.commit()
    conn.close()


def add_assessment(property_id, overall_score, risk_level="low"):
    from src.database import RiskDAO
    RiskDAO().save_assessment({
        "property_id": property_id,
        "wildfire_risk_score": overall_score,
        "wildfire_factors": {},
        "flood_risk_score": 0.0,
        "flood_factors": {},
        "overall_risk_score": overall_score,
        "risk_level": risk_level,
        "wildfire_explanation": "test",
        "flood_explanation": "test",
    })


def add_property_alert(property_id, risk_type="wildfire", alert_level="critical"):
    AlertDAO().save_new_alerts([{
        "property_id": property_id, "risk_type": risk_type, "risk_score": 85.0,
        "threshold_exceeded": 70, "alert_level": alert_level, "message": "Test alert",
        "triggered_at": get_utc_now().isoformat(),
    }])


def add_portfolio_alert():
    AlertDAO().save_new_alerts([{
        "property_id": None, "risk_type": "portfolio_high_risk_pct", "risk_score": 25.0,
        "threshold_exceeded": 10, "alert_level": "critical",
        "message": "25.0% of assessed properties are in high/critical risk.",
        "triggered_at": get_utc_now().isoformat(),
    }])


@pytest.fixture
def reporter(temp_db, tmp_path):
    return PortfolioReporter(reports_dir=tmp_path / "reports")


class TestEmptyPortfolio:
    def test_generates_without_crashing(self, reporter):
        report = reporter.generate_summary_report(write_to_file=False)
        assert "PORTFOLIO SUMMARY REPORT" in report
        assert "No hotspots detected." in report
        assert "No active alerts." in report

    def test_zero_assessed_shown_correctly(self, reporter):
        add_property(1)
        report = reporter.generate_summary_report(write_to_file=False)
        assert "Assessed properties:   0" in report
        assert "Latest assessment:     N/A" in report


class TestMetricsSection:
    def test_risk_level_distribution_present(self, reporter):
        add_property(1)
        add_assessment(1, 90.0, "critical")
        report = reporter.generate_summary_report(write_to_file=False)
        assert "Critical" in report
        assert "1" in report

    def test_geographic_distribution_present(self, reporter):
        add_property(1, state="CA")
        add_assessment(1, 50.0, "medium")
        report = reporter.generate_summary_report(write_to_file=False)
        assert "CA: 1" in report

    def test_no_geographic_section_when_no_states(self, reporter):
        add_property(1, state=None)
        add_assessment(1, 50.0, "medium")
        report = reporter.generate_summary_report(write_to_file=False)
        assert "Geographic distribution" not in report


class TestHotspotsSection:
    def test_hotspot_listed_when_present(self, reporter):
        for pid in (1, 2, 3):
            add_property(pid, lat=34.0, lon=-118.0)
            add_assessment(pid, 90.0, "critical")
        report = reporter.generate_summary_report(write_to_file=False)
        assert "3 properties, avg risk 90.0" in report

    def test_no_hotspots_message_when_none_found(self, reporter):
        add_property(1)
        add_assessment(1, 10.0, "low")
        report = reporter.generate_summary_report(write_to_file=False)
        assert "No hotspots detected." in report


class TestAlertsSection:
    def test_property_alert_listed(self, reporter):
        add_property(1)
        add_property_alert(1)
        report = reporter.generate_summary_report(write_to_file=False)
        assert "property_id=1" in report
        assert "1 critical, 0 warning" in report

    def test_portfolio_alert_listed_separately(self, reporter):
        add_portfolio_alert()
        report = reporter.generate_summary_report(write_to_file=False)
        assert "Portfolio-level:" in report
        assert "25.0% of assessed properties" in report

    def test_both_alert_scopes_shown_together(self, reporter):
        add_property(1)
        add_property_alert(1)
        add_portfolio_alert()
        report = reporter.generate_summary_report(write_to_file=False)
        assert "Portfolio-level:" in report
        assert "Property-level (1 active):" in report

    def test_resolved_alerts_not_shown(self, reporter):
        add_property(1)
        add_property_alert(1)
        dao = AlertDAO()
        alert_id = dao.get_active_alerts()[0]["alert_id"]
        dao.evaluate_lifecycle(1, "wildfire", current_score=10.0, latest_assessment_timestamp=get_utc_now().isoformat())
        report = reporter.generate_summary_report(write_to_file=False)
        assert "No active alerts." in report


class TestFileOutput:
    def test_writes_file_when_requested(self, reporter, tmp_path):
        report = reporter.generate_summary_report(write_to_file=True)
        files = list((tmp_path / "reports").glob("portfolio_*.txt"))
        assert len(files) == 1
        assert files[0].read_text(encoding="utf-8") == report

    def test_does_not_write_file_when_not_requested(self, reporter, tmp_path):
        reporter.generate_summary_report(write_to_file=False)
        assert not (tmp_path / "reports").exists() or list((tmp_path / "reports").glob("*.txt")) == []

    def test_second_report_same_day_overwrites(self, reporter, tmp_path):
        reporter.generate_summary_report(write_to_file=True)
        add_property(1)
        add_assessment(1, 90.0, "critical")
        reporter.generate_summary_report(write_to_file=True)

        files = list((tmp_path / "reports").glob("portfolio_*.txt"))
        assert len(files) == 1
        assert "Assessed properties:   1" in files[0].read_text(encoding="utf-8")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
