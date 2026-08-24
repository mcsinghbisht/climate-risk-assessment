"""
Pytest test suite for utility functions

Run with: pytest tests/test_utils_pytest.py -v
"""

import pytest
from src.utils import (
    calculate_distance,
    is_valid_coordinate,
    validate_coordinate,
    validate_risk_score,
    get_utc_now,
)


class TestGeospatial:
    """Geospatial function tests."""

    def test_distance_calculation(self):
        """Test Haversine distance calculation."""
        dist = calculate_distance(33.7521, -116.7277, 33.9425, -116.7953)
        assert 20 < dist < 25, f"Expected ~22km, got {dist}"

    def test_valid_coordinates(self):
        """Test valid coordinate detection."""
        assert is_valid_coordinate(33.75, -116.72) == True
        assert is_valid_coordinate(0, 0) == True
        assert is_valid_coordinate(90, 180) == True
        assert is_valid_coordinate(-90, -180) == True

    def test_invalid_latitude(self):
        """Test rejection of invalid latitude."""
        assert is_valid_coordinate(91, 0) == False
        assert is_valid_coordinate(-91, 0) == False

    def test_invalid_longitude(self):
        """Test rejection of invalid longitude."""
        assert is_valid_coordinate(0, 181) == False
        assert is_valid_coordinate(0, -181) == False

    def test_nan_coordinates(self):
        """Test rejection of NaN coordinates."""
        assert is_valid_coordinate(float('nan'), 0) == False
        assert is_valid_coordinate(0, float('nan')) == False


class TestValidation:
    """Data validation tests."""

    def test_valid_coordinate(self):
        """Test valid coordinate validation."""
        is_valid, errors = validate_coordinate(33.75, -116.72)
        assert is_valid == True
        assert len(errors) == 0

    def test_invalid_coordinate(self):
        """Test invalid coordinate validation."""
        is_valid, errors = validate_coordinate(91, 0)
        assert is_valid == False
        assert len(errors) > 0

    def test_valid_risk_score(self):
        """Test valid risk score."""
        for score in [0, 50, 100]:
            is_valid, errors = validate_risk_score(score)
            assert is_valid == True, f"Score {score} should be valid"
            assert len(errors) == 0

    def test_invalid_risk_score_high(self):
        """Test rejection of score > 100."""
        is_valid, errors = validate_risk_score(150)
        assert is_valid == False
        assert len(errors) > 0

    def test_invalid_risk_score_low(self):
        """Test rejection of score < 0."""
        is_valid, errors = validate_risk_score(-10)
        assert is_valid == False
        assert len(errors) > 0

    def test_invalid_risk_score_none(self):
        """Test rejection of None score."""
        is_valid, errors = validate_risk_score(None)
        assert is_valid == False
        assert len(errors) > 0


class TestTime:
    """Time function tests."""

    def test_utc_now(self):
        """Test UTC timestamp."""
        now = get_utc_now()
        assert now.tzinfo is not None, "Should have timezone info"
        assert str(now.tzinfo) == "UTC", "Should be UTC timezone"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
