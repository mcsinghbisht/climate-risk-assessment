"""
Pytest test suite for RiskScoringEngine (Task 19)

Run with: pytest tests/test_scoring_engine_pytest.py -v

Uses a temporary SQLite database (properties + hazard_data + risk_assessments
schema) populated with real Task 7-generated properties and hand-built
hazard_data rows - exercising the real WildFireScorer/FloodScorer/
RiskAggregator/RiskDAO stack, not mocks, so this proves the actual wiring
between all five components works end-to-end.
"""

import pytest

import src.database.db as db_module
from src.risk_scoring.scoring_engine import RiskScoringEngine
from src.data_ingestion.property_generator import generate_properties


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """Temporary SQLite database with properties, hazard_data, risk_assessments."""
    db_path = tmp_path / "test_climate_risk.db"
    monkeypatch.setattr(db_module, "DB_PATH", db_path)

    conn = db_module.get_db_connection()
    schema = db_module.get_schema()
    conn.execute(schema["properties"])
    conn.execute(schema["hazard_data"])
    conn.execute(schema["risk_assessments"])
    conn.commit()
    conn.close()

    return db_path


def load_properties(count=5):
    """Insert the first N real Task 7-generated properties into the temp DB."""
    properties = generate_properties()[:count]
    conn = db_module.get_db_connection()
    for p in properties:
        conn.execute(
            """
            INSERT INTO properties (
                property_id, address, latitude, longitude, state, county,
                zip_code, construction_type, elevation_m,
                is_in_wildland_urban_interface, is_in_floodplain,
                soil_type, drainage_class
            ) VALUES (
                :property_id, :address, :latitude, :longitude, :state, :county,
                :zip_code, :construction_type, :elevation_m,
                :is_in_wildland_urban_interface, :is_in_floodplain,
                :soil_type, :drainage_class
            )
            """,
            p,
        )
    conn.commit()
    conn.close()
    return properties


@pytest.fixture
def engine(temp_db):
    return RiskScoringEngine()


class TestScoreAllProperties:
    def test_scores_all_properties_in_portfolio(self, temp_db, engine):
        load_properties(5)
        summary = engine.score_all_properties()
        assert summary["properties_scored"] == 5

    def test_empty_portfolio_completes_cleanly(self, temp_db, engine):
        summary = engine.score_all_properties()
        assert summary["properties_scored"] == 0
        assert summary["average_risk"] == 0.0
        assert summary["errors"] == []

    def test_persists_one_assessment_per_property(self, temp_db, engine):
        load_properties(5)
        engine.score_all_properties()

        conn = db_module.get_db_connection()
        cursor = conn.execute("SELECT COUNT(DISTINCT property_id) FROM risk_assessments")
        assert cursor.fetchone()[0] == 5
        conn.close()

    def test_average_risk_is_mean_of_overall_scores(self, temp_db, engine):
        load_properties(5)
        summary = engine.score_all_properties()

        conn = db_module.get_db_connection()
        cursor = conn.execute("SELECT overall_risk_score FROM risk_assessments")
        scores = [row[0] for row in cursor.fetchall()]
        conn.close()

        expected_avg = round(sum(scores) / len(scores), 2)
        assert summary["average_risk"] == expected_avg

    def test_floodplain_property_scores_higher_than_non_floodplain(self, temp_db, engine):
        conn = db_module.get_db_connection()
        conn.execute(
            "INSERT INTO properties (property_id, address, latitude, longitude, "
            "is_in_floodplain) VALUES (1, 'Floodplain Property', 30.0, -90.0, 1)"
        )
        conn.execute(
            "INSERT INTO properties (property_id, address, latitude, longitude, "
            "is_in_floodplain) VALUES (2, 'Non-Floodplain Property', 40.0, -100.0, 0)"
        )
        conn.commit()
        conn.close()

        engine.score_all_properties()

        conn = db_module.get_db_connection()
        floodplain_score = conn.execute(
            "SELECT overall_risk_score FROM risk_assessments WHERE property_id = 1"
        ).fetchone()[0]
        non_floodplain_score = conn.execute(
            "SELECT overall_risk_score FROM risk_assessments WHERE property_id = 2"
        ).fetchone()[0]
        conn.close()

        assert floodplain_score > non_floodplain_score

    def test_high_risk_count_reflects_actual_risk_levels(self, temp_db, engine):
        load_properties(5)
        summary = engine.score_all_properties()

        conn = db_module.get_db_connection()
        actual_high = conn.execute(
            "SELECT COUNT(*) FROM risk_assessments WHERE risk_level = 'high'"
        ).fetchone()[0]
        actual_critical = conn.execute(
            "SELECT COUNT(*) FROM risk_assessments WHERE risk_level = 'critical'"
        ).fetchone()[0]
        conn.close()

        assert summary["high_risk_count"] == actual_high
        assert summary["critical_count"] == actual_critical

    def test_wildfire_hazard_data_increases_nearby_property_score(self, temp_db, engine):
        conn = db_module.get_db_connection()
        conn.execute(
            "INSERT INTO properties (property_id, address, latitude, longitude, "
            "is_in_floodplain) VALUES (1, 'Near Fire', 33.75, -116.72, 0)"
        )
        conn.execute(
            "INSERT INTO hazard_data (hazard_type, source, latitude, longitude, "
            "value, confidence, observation_timestamp) VALUES "
            "('wildfire', 'NASA_FIRMS', 33.70, -116.70, 200.0, 0.9, datetime('now'))"
        )
        conn.commit()
        conn.close()

        engine.score_all_properties()

        conn = db_module.get_db_connection()
        score = conn.execute(
            "SELECT wildfire_risk_score FROM risk_assessments WHERE property_id = 1"
        ).fetchone()[0]
        conn.close()

        assert score > 0

    def test_result_has_all_expected_summary_keys(self, temp_db, engine):
        load_properties(3)
        summary = engine.score_all_properties()
        for key in ["properties_scored", "average_risk", "high_risk_count",
                    "critical_count", "errors"]:
            assert key in summary


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
