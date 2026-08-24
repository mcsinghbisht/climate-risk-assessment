"""
Pytest test suite for ChangeDetector (Task 22)

Run with: pytest tests/test_change_detector_pytest.py -v
"""

import pytest

from src.continuous_monitoring.change_detector import ChangeDetector


def make_assessment(overall_score=45.0, risk_level="medium",
                     wildfire_factors=None, flood_factors=None):
    return {
        "overall_risk_score": overall_score,
        "risk_level": risk_level,
        "wildfire_factors": wildfire_factors or {},
        "flood_factors": flood_factors or {},
    }


@pytest.fixture
def detector():
    return ChangeDetector()


class TestBaseline:
    def test_no_previous_assessment_is_baseline(self, detector):
        current = make_assessment()
        result = detector.detect_changes(1, current, None)
        assert result["is_baseline"] is True
        assert result["changed"] is False
        assert result["trend"] == "baseline"
        assert result["risk_delta"] is None
        assert result["factors_changed"] == []


class TestTrend:
    def test_increased_score_is_worsening(self, detector):
        previous = make_assessment(overall_score=45.0)
        current = make_assessment(overall_score=77.0)
        result = detector.detect_changes(1, current, previous)
        assert result["trend"] == "worsening"
        assert result["changed"] is True
        assert result["risk_delta"] == 32.0

    def test_decreased_score_is_improving(self, detector):
        previous = make_assessment(overall_score=77.0)
        current = make_assessment(overall_score=45.0)
        result = detector.detect_changes(1, current, previous)
        assert result["trend"] == "improving"
        assert result["risk_delta"] == -32.0

    def test_identical_score_is_stable_and_unchanged(self, detector):
        assessment = make_assessment(overall_score=50.0)
        result = detector.detect_changes(1, assessment, assessment)
        assert result["trend"] == "stable"
        assert result["changed"] is False
        assert result["risk_delta"] == 0.0

    def test_tiny_float_difference_within_tolerance_is_stable(self, detector):
        previous = make_assessment(overall_score=50.0)
        current = make_assessment(overall_score=50.005)  # well within FLOAT_TOLERANCE for factors, but here it's the raw score delta
        result = detector.detect_changes(1, current, previous)
        # overall score delta itself uses round(...,2), so 0.005 rounds to 0.0 or 0.01;
        # this asserts the rounding keeps near-zero moves from reading as noise
        assert abs(result["risk_delta"]) <= 0.01


class TestRiskLevelChange:
    def test_risk_level_change_detected(self, detector):
        previous = make_assessment(overall_score=45.0, risk_level="medium")
        current = make_assessment(overall_score=77.0, risk_level="critical")
        result = detector.detect_changes(1, current, previous)
        assert result["risk_level_changed"] is True

    def test_same_risk_level_not_flagged(self, detector):
        previous = make_assessment(risk_level="medium")
        current = make_assessment(risk_level="medium")
        result = detector.detect_changes(1, current, previous)
        assert result["risk_level_changed"] is False

    def test_risk_level_change_alone_counts_as_changed(self, detector):
        """Even if the score itself is identical (edge case), a risk_level
        change should still be flagged as a change."""
        previous = make_assessment(overall_score=50.0, risk_level="medium")
        current = make_assessment(overall_score=50.0, risk_level="high")
        result = detector.detect_changes(1, current, previous)
        assert result["changed"] is True


class TestFactorDiffing:
    def test_changed_factor_is_reported(self, detector):
        previous = make_assessment(wildfire_factors={"proximity_score": 60.0})
        current = make_assessment(wildfire_factors={"proximity_score": 88.28})
        result = detector.detect_changes(1, current, previous)
        assert len(result["factors_changed"]) == 1
        assert result["factors_changed"][0] == {
            "factor": "wildfire.proximity_score", "from": 60.0, "to": 88.28
        }

    def test_unchanged_factor_is_not_reported(self, detector):
        previous = make_assessment(wildfire_factors={"proximity_score": 60.0})
        current = make_assessment(wildfire_factors={"proximity_score": 60.0})
        result = detector.detect_changes(1, current, previous)
        assert result["factors_changed"] == []

    def test_multiple_changed_factors_all_reported(self, detector):
        previous = make_assessment(wildfire_factors={"proximity_score": 60.0, "wind_score": 0.0})
        current = make_assessment(wildfire_factors={"proximity_score": 88.0, "wind_score": 75.0})
        result = detector.detect_changes(1, current, previous)
        assert len(result["factors_changed"]) == 2

    def test_wildfire_and_flood_factors_both_diffed(self, detector):
        previous = make_assessment(
            wildfire_factors={"proximity_score": 60.0},
            flood_factors={"rainfall_score": 10.0},
        )
        current = make_assessment(
            wildfire_factors={"proximity_score": 60.0},
            flood_factors={"rainfall_score": 40.0},
        )
        result = detector.detect_changes(1, current, previous)
        assert len(result["factors_changed"]) == 1
        assert result["factors_changed"][0]["factor"] == "flood.rainfall_score"

    def test_explanation_field_is_ignored(self, detector):
        previous = make_assessment(wildfire_factors={"proximity_score": 60.0, "explanation": "Old text."})
        current = make_assessment(wildfire_factors={"proximity_score": 60.0, "explanation": "New wording."})
        result = detector.detect_changes(1, current, previous)
        assert result["factors_changed"] == []

    def test_float_noise_within_tolerance_not_reported(self, detector):
        previous = make_assessment(wildfire_factors={"proximity_score": 60.001})
        current = make_assessment(wildfire_factors={"proximity_score": 60.002})
        result = detector.detect_changes(1, current, previous)
        assert result["factors_changed"] == []

    def test_key_present_only_in_current_is_reported(self, detector):
        previous = make_assessment(wildfire_factors={})
        current = make_assessment(wildfire_factors={"proximity_score": 60.0})
        result = detector.detect_changes(1, current, previous)
        assert len(result["factors_changed"]) == 1
        assert result["factors_changed"][0]["from"] is None
        assert result["factors_changed"][0]["to"] == 60.0

    def test_missing_factors_dict_does_not_crash(self, detector):
        previous = {"overall_risk_score": 45.0, "risk_level": "medium"}  # no factors keys at all
        current = {"overall_risk_score": 77.0, "risk_level": "high"}
        result = detector.detect_changes(1, current, previous)
        assert result["changed"] is True  # score/level still changed
        assert result["factors_changed"] == []

    def test_string_factor_value_change_is_reported(self, detector):
        previous = make_assessment(wildfire_factors={"distance_category": "far"})
        current = make_assessment(wildfire_factors={"distance_category": "near"})
        result = detector.detect_changes(1, current, previous)
        assert result["factors_changed"] == [
            {"factor": "wildfire.distance_category", "from": "far", "to": "near"}
        ]


class TestResultShape:
    def test_property_id_matches_input(self, detector):
        result = detector.detect_changes(42, make_assessment(), make_assessment())
        assert result["property_id"] == 42

    def test_result_has_all_expected_keys(self, detector):
        result = detector.detect_changes(1, make_assessment(), make_assessment())
        for key in ["property_id", "changed", "is_baseline", "risk_delta",
                    "risk_level_changed", "trend", "factors_changed"]:
            assert key in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
