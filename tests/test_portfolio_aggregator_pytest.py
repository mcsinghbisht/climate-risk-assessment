"""
Pytest test suite for PortfolioAggregator (Task 25)

Run with: pytest tests/test_portfolio_aggregator_pytest.py -v

Uses a temporary SQLite database (properties + risk_assessments schema)
populated with hand-built rows - exercises the real PropertyDAO/RiskDAO
stack, not mocks.
"""

import pytest

import src.database.db as db_module
from src.portfolio.aggregator import PortfolioAggregator


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test_climate_risk.db"
    monkeypatch.setattr(db_module, "DB_PATH", db_path)

    conn = db_module.get_db_connection()
    schema = db_module.get_schema()
    conn.execute(schema["properties"])
    conn.execute(schema["risk_assessments"])
    conn.commit()
    conn.close()

    return db_path


def add_property(property_id, state=None, county=None, lat=33.0, lon=-116.0):
    conn = db_module.get_db_connection()
    conn.execute(
        "INSERT INTO properties (property_id, address, latitude, longitude, state, county) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (property_id, f"Property {property_id}", lat, lon, state, county),
    )
    conn.commit()
    conn.close()


def add_assessment(property_id, overall_score, risk_level, timestamp=None):
    from src.database import RiskDAO
    assessment = {
        "property_id": property_id,
        "wildfire_risk_score": overall_score,
        "wildfire_factors": {},
        "flood_risk_score": 0.0,
        "flood_factors": {},
        "overall_risk_score": overall_score,
        "risk_level": risk_level,
        "wildfire_explanation": "test",
        "flood_explanation": "test",
    }
    assessment_id = RiskDAO().save_assessment(assessment)
    if timestamp:
        conn = db_module.get_db_connection()
        conn.execute(
            "UPDATE risk_assessments SET assessment_timestamp = ? WHERE assessment_id = ?",
            (timestamp, assessment_id),
        )
        conn.commit()
        conn.close()
    return assessment_id


@pytest.fixture
def aggregator(temp_db):
    return PortfolioAggregator()


class TestEmptyPortfolio:
    def test_no_properties_completes_cleanly(self, aggregator):
        metrics = aggregator.get_portfolio_metrics()
        assert metrics["total_properties"] == 0
        assert metrics["assessed_properties"] == 0
        assert metrics["score_stats"] == {"average": 0.0, "median": 0.0, "min": 0.0, "max": 0.0}
        assert metrics["latest_assessment_timestamp"] is None

    def test_properties_with_no_assessments_excluded_from_stats(self, aggregator):
        add_property(1)
        add_property(2)
        metrics = aggregator.get_portfolio_metrics()
        assert metrics["total_properties"] == 2
        assert metrics["assessed_properties"] == 0
        assert metrics["risk_level_distribution"]["low"]["count"] == 0


class TestRiskLevelDistribution:
    def test_counts_and_percentages_correct(self, aggregator):
        for i in range(1, 5):
            add_property(i)
        add_assessment(1, 10.0, "low")
        add_assessment(2, 30.0, "medium")
        add_assessment(3, 75.0, "high")
        add_assessment(4, 90.0, "critical")

        dist = aggregator.get_portfolio_metrics()["risk_level_distribution"]
        assert dist["low"] == {"count": 1, "percentage": 25.0}
        assert dist["medium"] == {"count": 1, "percentage": 25.0}
        assert dist["high"] == {"count": 1, "percentage": 25.0}
        assert dist["critical"] == {"count": 1, "percentage": 25.0}

    def test_all_four_levels_always_present_even_if_zero(self, aggregator):
        add_property(1)
        add_assessment(1, 10.0, "low")
        dist = aggregator.get_portfolio_metrics()["risk_level_distribution"]
        assert set(dist.keys()) == {"low", "medium", "high", "critical"}
        assert dist["critical"]["count"] == 0

    def test_only_latest_assessment_per_property_counted(self, aggregator):
        add_property(1)
        add_assessment(1, 10.0, "low")
        add_assessment(1, 90.0, "critical")  # supersedes the low assessment

        dist = aggregator.get_portfolio_metrics()["risk_level_distribution"]
        assert dist["low"]["count"] == 0
        assert dist["critical"]["count"] == 1


class TestGeographicDistribution:
    def test_grouped_by_state_and_county(self, aggregator):
        add_property(1, state="CA", county="Riverside")
        add_property(2, state="CA", county="Ventura")
        add_property(3, state="TX", county="Harris")
        add_assessment(1, 50.0, "medium")
        add_assessment(2, 50.0, "medium")
        add_assessment(3, 50.0, "medium")

        geo = aggregator.get_portfolio_metrics()["geographic_distribution"]
        assert geo["by_state"] == {"CA": 2, "TX": 1}
        assert geo["by_county"] == {"Riverside": 1, "Ventura": 1, "Harris": 1}

    def test_missing_state_and_county_not_counted(self, aggregator):
        add_property(1, state=None, county=None)
        add_assessment(1, 50.0, "medium")
        geo = aggregator.get_portfolio_metrics()["geographic_distribution"]
        assert geo["by_state"] == {}
        assert geo["by_county"] == {}

    def test_unassessed_property_not_counted_in_geography(self, aggregator):
        add_property(1, state="CA", county="Riverside")  # no assessment
        add_property(2, state="CA", county="Ventura")
        add_assessment(2, 50.0, "medium")
        geo = aggregator.get_portfolio_metrics()["geographic_distribution"]
        assert geo["by_state"] == {"CA": 1}


class TestScoreStats:
    def test_average_median_min_max_correct(self, aggregator):
        for i, score in enumerate([10.0, 20.0, 30.0, 100.0], start=1):
            add_property(i)
            add_assessment(i, score, "low")

        stats = aggregator.get_portfolio_metrics()["score_stats"]
        assert stats["average"] == 40.0
        assert stats["median"] == 25.0
        assert stats["min"] == 10.0
        assert stats["max"] == 100.0

    def test_single_assessment_stats(self, aggregator):
        add_property(1)
        add_assessment(1, 55.5, "medium")
        stats = aggregator.get_portfolio_metrics()["score_stats"]
        assert stats == {"average": 55.5, "median": 55.5, "min": 55.5, "max": 55.5}


class TestLatestAssessmentTimestamp:
    def test_returns_most_recent_timestamp_across_portfolio(self, aggregator):
        add_property(1)
        add_property(2)
        add_assessment(1, 10.0, "low", timestamp="2026-01-01T00:00:00+00:00")
        add_assessment(2, 20.0, "low", timestamp="2026-06-15T12:00:00+00:00")

        latest = aggregator.get_portfolio_metrics()["latest_assessment_timestamp"]
        assert latest == "2026-06-15T12:00:00+00:00"


class TestResultShape:
    def test_result_has_all_expected_top_level_keys(self, aggregator):
        metrics = aggregator.get_portfolio_metrics()
        for key in ["total_properties", "assessed_properties", "risk_level_distribution",
                    "geographic_distribution", "score_stats", "latest_assessment_timestamp"]:
            assert key in metrics


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
