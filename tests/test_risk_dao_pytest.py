"""
Pytest test suite for RiskDAO (Task 18)

Run with: pytest tests/test_risk_dao_pytest.py -v

Uses a temporary SQLite database (properties + risk_assessments schema)
so these tests never touch or depend on data/climate_risk.db.
"""

import time

import pytest

import src.database.db as db_module
from src.database.risk_dao import RiskDAO


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """Temporary SQLite database with properties + risk_assessments schema."""
    db_path = tmp_path / "test_climate_risk.db"
    monkeypatch.setattr(db_module, "DB_PATH", db_path)

    conn = db_module.get_db_connection()
    schema = db_module.get_schema()
    conn.execute(schema["properties"])
    conn.execute(schema["risk_assessments"])
    conn.execute(
        "INSERT INTO properties (property_id, address, latitude, longitude) "
        "VALUES (1, 'Test Property', 33.75, -116.72)"
    )
    conn.commit()
    conn.close()

    return db_path


def make_assessment(property_id=1, overall_score=44.5, risk_level="medium",
                     wildfire_score=77.09, flood_score=12.0,
                     wildfire_explanation=None, flood_explanation=None):
    return {
        "property_id": property_id,
        "wildfire_risk_score": wildfire_score,
        "wildfire_factors": {"proximity_score": 88.28, "distance_km": 5.86},
        "flood_risk_score": flood_score,
        "flood_factors": {"rainfall_score": 0.0},
        "overall_risk_score": overall_score,
        "risk_level": risk_level,
        "wildfire_explanation": wildfire_explanation,
        "flood_explanation": flood_explanation,
    }


@pytest.fixture
def dao(temp_db):
    return RiskDAO()


class TestSaveAssessment:
    def test_returns_new_assessment_id(self, dao):
        assessment_id = dao.save_assessment(make_assessment())
        assert assessment_id is not None
        assert assessment_id > 0

    def test_second_save_creates_new_row_not_upsert(self, dao):
        first_id = dao.save_assessment(make_assessment(overall_score=44.5))
        second_id = dao.save_assessment(make_assessment(overall_score=60.0))
        assert first_id != second_id

        history = dao.get_assessment_history(1, days=30)
        assert len(history) == 2

    def test_explanation_folded_into_factors_json(self, dao):
        dao.save_assessment(make_assessment(
            wildfire_explanation="Nearest active fire is 5.86 km away.",
            flood_explanation="No significant recent rainfall detected.",
        ))
        latest = dao.get_latest_assessment(1)
        assert latest["wildfire_factors"]["explanation"] == "Nearest active fire is 5.86 km away."
        assert latest["flood_factors"]["explanation"] == "No significant recent rainfall detected."

    def test_factors_without_explanation_still_saved_correctly(self, dao):
        dao.save_assessment(make_assessment())  # no explanation passed
        latest = dao.get_latest_assessment(1)
        assert latest["wildfire_factors"]["proximity_score"] == 88.28
        assert "explanation" not in latest["wildfire_factors"]

    def test_alerts_triggered_defaults_to_none(self, dao):
        dao.save_assessment(make_assessment())
        latest = dao.get_latest_assessment(1)
        assert latest["alerts_triggered"] is None

    def test_alerts_triggered_can_be_provided(self, dao):
        alerts = [{"risk_type": "wildfire", "message": "Risk crossed threshold"}]
        dao.save_assessment(make_assessment(), alerts_triggered=alerts)
        latest = dao.get_latest_assessment(1)
        assert latest["alerts_triggered"] == alerts


class TestGetLatestAssessment:
    def test_returns_none_when_no_assessments_exist(self, dao):
        assert dao.get_latest_assessment(1) is None

    def test_returns_the_correct_scores(self, dao):
        dao.save_assessment(make_assessment(wildfire_score=77.09, flood_score=12.0))
        latest = dao.get_latest_assessment(1)
        assert latest["wildfire_risk_score"] == 77.09
        assert latest["flood_risk_score"] == 12.0

    def test_returns_most_recent_of_multiple(self, dao):
        dao.save_assessment(make_assessment(overall_score=30.0))
        dao.save_assessment(make_assessment(overall_score=70.0))
        latest = dao.get_latest_assessment(1)
        assert latest["overall_risk_score"] == 70.0

    def test_returns_none_for_property_with_no_data(self, dao):
        dao.save_assessment(make_assessment(property_id=1))
        assert dao.get_latest_assessment(999) is None


class TestGetAssessmentHistory:
    def test_empty_history_for_unknown_property(self, dao):
        assert dao.get_assessment_history(1) == []

    def test_returns_all_within_window_newest_first(self, dao):
        dao.save_assessment(make_assessment(overall_score=30.0))
        dao.save_assessment(make_assessment(overall_score=50.0))
        dao.save_assessment(make_assessment(overall_score=70.0))

        history = dao.get_assessment_history(1, days=30)

        assert len(history) == 3
        assert history[0]["overall_risk_score"] == 70.0  # newest first
        assert history[-1]["overall_risk_score"] == 30.0

    def test_only_returns_requested_property(self, dao):
        conn = db_module.get_db_connection()
        conn.execute(
            "INSERT INTO properties (property_id, address, latitude, longitude) "
            "VALUES (2, 'Second Property', 30.0, -90.0)"
        )
        conn.commit()
        conn.close()

        dao.save_assessment(make_assessment(property_id=1))
        dao.save_assessment(make_assessment(property_id=2))

        history = dao.get_assessment_history(1, days=30)
        assert len(history) == 1
        assert history[0]["property_id"] == 1


class TestGetAllLatestAssessments:
    def test_empty_when_no_assessments(self, dao):
        assert dao.get_all_latest_assessments() == []

    def test_one_row_per_property_not_per_snapshot(self, dao):
        conn = db_module.get_db_connection()
        conn.execute(
            "INSERT INTO properties (property_id, address, latitude, longitude) "
            "VALUES (2, 'Second Property', 30.0, -90.0)"
        )
        conn.commit()
        conn.close()

        # Property 1 gets 3 historical snapshots; property 2 gets 1
        dao.save_assessment(make_assessment(property_id=1, overall_score=10.0))
        dao.save_assessment(make_assessment(property_id=1, overall_score=20.0))
        dao.save_assessment(make_assessment(property_id=1, overall_score=30.0))
        dao.save_assessment(make_assessment(property_id=2, overall_score=99.0))

        all_latest = dao.get_all_latest_assessments()

        assert len(all_latest) == 2  # one per property, not 4
        by_property = {a["property_id"]: a for a in all_latest}
        assert by_property[1]["overall_risk_score"] == 30.0  # the newest for property 1
        assert by_property[2]["overall_risk_score"] == 99.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
