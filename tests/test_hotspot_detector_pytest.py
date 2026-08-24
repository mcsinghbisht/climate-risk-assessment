"""
Pytest test suite for HotspotDetector (Task 26)

Run with: pytest tests/test_hotspot_detector_pytest.py -v

Uses a temporary SQLite database populated with hand-built property
coordinates and assessments - exercises the real PropertyDAO/RiskDAO/
calculate_distance stack, not mocks. Coordinates are chosen with exact,
easily-reasoned-about distances (points along the same line of longitude,
~1 degree latitude apart is ~111km) rather than real addresses.
"""

import pytest

import src.database.db as db_module
from src.portfolio.hotspot_detector import HotspotDetector


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


def add_property(property_id, lat, lon):
    conn = db_module.get_db_connection()
    conn.execute(
        "INSERT INTO properties (property_id, address, latitude, longitude) VALUES (?, ?, ?, ?)",
        (property_id, f"Property {property_id}", lat, lon),
    )
    conn.commit()
    conn.close()


def add_assessment(property_id, overall_score, risk_level="high"):
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


@pytest.fixture
def detector(temp_db):
    return HotspotDetector()


class TestEmptyOrSparsePortfolio:
    def test_no_properties_returns_no_hotspots(self, detector):
        assert detector.detect_hotspots() == []

    def test_fewer_than_min_properties_returns_no_hotspots(self, detector):
        # min_properties defaults to 3; only 2 assessed
        add_property(1, 34.0, -118.0)
        add_property(2, 34.0, -118.0)
        add_assessment(1, 90.0)
        add_assessment(2, 90.0)
        assert detector.detect_hotspots() == []

    def test_unassessed_properties_ignored(self, detector):
        add_property(1, 34.0, -118.0)
        add_property(2, 34.0, -118.0)
        add_property(3, 34.0, -118.0)  # no assessment
        add_assessment(1, 90.0)
        add_assessment(2, 90.0)
        assert detector.detect_hotspots() == []  # only 2 assessed, below min_properties


class TestClusterDetection:
    def test_tight_high_risk_cluster_detected(self, detector):
        # All at the same point -> distance 0, trivially within any radius
        for pid in (1, 2, 3):
            add_property(pid, 34.0, -118.0)
            add_assessment(pid, 80.0)

        hotspots = detector.detect_hotspots(radius_km=50)
        assert len(hotspots) == 1
        assert hotspots[0]["property_count"] == 3
        assert hotspots[0]["avg_risk"] == 80.0
        assert {p["property_id"] for p in hotspots[0]["properties"]} == {1, 2, 3}

    def test_low_risk_cluster_not_flagged(self, detector):
        for pid in (1, 2, 3):
            add_property(pid, 34.0, -118.0)
            add_assessment(pid, 10.0, risk_level="low")
        assert detector.detect_hotspots(radius_km=50) == []

    def test_far_apart_properties_not_clustered(self, detector):
        # ~1 degree latitude apart is ~111km - well beyond a 50km radius
        add_property(1, 34.0, -118.0)
        add_property(2, 35.0, -118.0)
        add_property(3, 36.0, -118.0)
        for pid in (1, 2, 3):
            add_assessment(pid, 90.0)
        assert detector.detect_hotspots(radius_km=50) == []

    def test_custom_radius_overrides_default(self, detector):
        # ~1 degree latitude apart is ~111km - not within 50km, but within 150km
        add_property(1, 34.0, -118.0)
        add_property(2, 35.0, -118.0)
        add_property(3, 36.0, -118.0)
        for pid in (1, 2, 3):
            add_assessment(pid, 90.0)

        assert detector.detect_hotspots(radius_km=50) == []
        hotspots = detector.detect_hotspots(radius_km=150)
        assert len(hotspots) == 1
        assert hotspots[0]["property_count"] == 3

    def test_avg_risk_computed_correctly(self, detector):
        for pid, score in [(1, 60.0), (2, 70.0), (3, 80.0)]:
            add_property(pid, 34.0, -118.0)
            add_assessment(pid, score)
        hotspots = detector.detect_hotspots(radius_km=50)
        assert hotspots[0]["avg_risk"] == 70.0

    def test_isolated_property_excluded_from_nearby_cluster(self, detector):
        for pid in (1, 2, 3):
            add_property(pid, 34.0, -118.0)
            add_assessment(pid, 90.0)
        # far away, low risk - should not appear in the hotspot's members
        add_property(4, 40.0, -118.0)
        add_assessment(4, 90.0)

        hotspots = detector.detect_hotspots(radius_km=50)
        assert len(hotspots) == 1
        assert {p["property_id"] for p in hotspots[0]["properties"]} == {1, 2, 3}


class TestNonMaxSuppression:
    def test_dense_cluster_reported_once_not_per_property(self, detector):
        # 5 co-located high-risk properties should yield exactly 1 hotspot,
        # not one candidate per property (every property is tried as a center)
        for pid in range(1, 6):
            add_property(pid, 34.0, -118.0)
            add_assessment(pid, 85.0)
        hotspots = detector.detect_hotspots(radius_km=50)
        assert len(hotspots) == 1
        assert hotspots[0]["property_count"] == 5

    def test_two_separate_clusters_both_reported(self, detector):
        for pid in (1, 2, 3):
            add_property(pid, 34.0, -118.0)
            add_assessment(pid, 90.0)
        for pid in (4, 5, 6):
            add_property(pid, 40.0, -118.0)  # ~666km from the first cluster
            add_assessment(pid, 90.0)

        hotspots = detector.detect_hotspots(radius_km=50)
        assert len(hotspots) == 2

    def test_hotspots_sorted_by_avg_risk_descending(self, detector):
        for pid in (1, 2, 3):
            add_property(pid, 34.0, -118.0)
            add_assessment(pid, 55.0)  # just above threshold (50)
        for pid in (4, 5, 6):
            add_property(pid, 40.0, -118.0)
            add_assessment(pid, 95.0)

        hotspots = detector.detect_hotspots(radius_km=50)
        assert len(hotspots) == 2
        assert hotspots[0]["avg_risk"] > hotspots[1]["avg_risk"]


class TestResultShape:
    def test_hotspot_has_all_expected_keys(self, detector):
        for pid in (1, 2, 3):
            add_property(pid, 34.0, -118.0)
            add_assessment(pid, 90.0)
        hotspots = detector.detect_hotspots(radius_km=50)
        for key in ["center_lat", "center_lon", "property_count", "avg_risk", "properties"]:
            assert key in hotspots[0]

    def test_property_entries_include_risk_score(self, detector):
        for pid, score in [(1, 60.0), (2, 70.0), (3, 80.0)]:
            add_property(pid, 34.0, -118.0)
            add_assessment(pid, score)
        hotspots = detector.detect_hotspots(radius_km=50)
        for entry in hotspots[0]["properties"]:
            assert "property_id" in entry
            assert "risk_score" in entry


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
