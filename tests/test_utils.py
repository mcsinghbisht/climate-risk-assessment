"""
Pytest test suite for src/utils/ (Task 28)

Run with: pytest tests/test_utils.py -v
Coverage:  pytest tests/test_utils.py --cov=src/utils --cov-report=term-missing

Direct, focused unit tests for every function in geo_utils.py, time_utils.py,
and validation.py. Many of these already have indirect coverage through
other suites (e.g. calculate_distance via the wildfire scorer tests,
is_within_hours via AlertDAO tests) - this file is the dedicated,
exhaustive pass over the utilities themselves, covering branches those
call sites don't happen to exercise.
"""

import math
from datetime import datetime, timedelta, timezone

import pytest

from src.utils.geo_utils import (
    calculate_distance,
    is_valid_coordinate,
    get_bearing,
    is_downwind,
    get_distance_category,
    haversine_distance,
    assign_grid_cell,
)
from src.utils.time_utils import (
    get_utc_now,
    get_utc_timestamp_str,
    hours_ago,
    minutes_ago,
    days_ago,
    seconds_ago,
    time_since,
    is_older_than,
    is_within_hours,
    get_monitoring_cycle_time,
    get_last_cycle_time,
    next_cycle_in,
    format_timestamp,
    parse_iso_timestamp,
    get_date_range,
    is_business_hours,
)
from src.utils.validation import (
    validate_coordinate,
    validate_property_data,
    validate_risk_score,
    validate_risk_assessment,
    validate_hazard_data,
    validate_alert,
)


# ---------------------------------------------------------------------------
# geo_utils.py
# ---------------------------------------------------------------------------

class TestCalculateDistance:
    def test_known_distance_idyllwild_to_san_bernardino(self):
        dist = calculate_distance(33.7521, -116.7277, 33.9425, -116.7953)
        assert 20 < dist < 25

    def test_same_point_is_zero(self):
        assert calculate_distance(33.75, -116.72, 33.75, -116.72) == 0.0

    def test_distance_is_symmetric(self):
        d1 = calculate_distance(33.75, -116.72, 34.05, -118.24)
        d2 = calculate_distance(34.05, -118.24, 33.75, -116.72)
        assert d1 == pytest.approx(d2, abs=1e-9)

    def test_antipodal_points_half_earth_circumference(self):
        dist = calculate_distance(0, 0, 0, 180)
        assert dist == pytest.approx(math.pi * 6371.0, rel=1e-3)

    def test_raises_on_invalid_first_point(self):
        with pytest.raises(ValueError):
            calculate_distance(91, 0, 33.75, -116.72)

    def test_raises_on_invalid_second_point(self):
        with pytest.raises(ValueError):
            calculate_distance(33.75, -116.72, 0, 181)


class TestIsValidCoordinate:
    def test_valid_coordinates(self):
        assert is_valid_coordinate(33.75, -116.72) is True
        assert is_valid_coordinate(0, 0) is True

    def test_boundary_values_are_valid(self):
        assert is_valid_coordinate(90, 180) is True
        assert is_valid_coordinate(-90, -180) is True

    def test_latitude_out_of_range(self):
        assert is_valid_coordinate(90.1, 0) is False
        assert is_valid_coordinate(-90.1, 0) is False

    def test_longitude_out_of_range(self):
        assert is_valid_coordinate(0, 180.1) is False
        assert is_valid_coordinate(0, -180.1) is False

    def test_nan_is_invalid(self):
        assert is_valid_coordinate(float("nan"), 0) is False
        assert is_valid_coordinate(0, float("nan")) is False

    def test_infinity_is_invalid(self):
        assert is_valid_coordinate(float("inf"), 0) is False
        assert is_valid_coordinate(0, float("-inf")) is False

    def test_non_numeric_is_invalid(self):
        assert is_valid_coordinate("not a number", 0) is False
        assert is_valid_coordinate(None, 0) is False

    def test_numeric_strings_are_valid(self):
        assert is_valid_coordinate("33.75", "-116.72") is True


class TestGetBearing:
    def test_due_north_is_zero(self):
        bearing = get_bearing(0, 0, 1, 0)
        assert bearing == pytest.approx(0, abs=0.01)

    def test_due_east_is_ninety(self):
        bearing = get_bearing(0, 0, 0, 1)
        assert bearing == pytest.approx(90, abs=0.01)

    def test_due_south_is_180(self):
        bearing = get_bearing(1, 0, 0, 0)
        assert bearing == pytest.approx(180, abs=0.01)

    def test_due_west_is_270(self):
        bearing = get_bearing(0, 1, 0, 0)
        assert bearing == pytest.approx(270, abs=0.01)

    def test_result_always_in_0_360_range(self):
        bearing = get_bearing(33.75, -116.72, 33.94, -116.79)
        assert 0 <= bearing < 360

    def test_raises_on_invalid_coordinates(self):
        with pytest.raises(ValueError):
            get_bearing(91, 0, 0, 0)


class TestIsDownwind:
    def test_property_directly_downwind_is_true(self):
        # property due east of fire; wind blowing from the west (270) -> blows east
        assert is_downwind(0, 0, 0, 1, wind_direction=270) is True

    def test_property_directly_upwind_is_false(self):
        # property due west of fire; wind blowing from the west means it blows AWAY from the property
        assert is_downwind(0, 0, 0, -1, wind_direction=270) is False

    def test_property_perpendicular_to_wind_is_false(self):
        # property due north of fire; wind blowing east-to-west (blowing FROM east)
        assert is_downwind(0, 0, 1, 0, wind_direction=90) is False

    def test_raises_on_invalid_coordinates(self):
        with pytest.raises(ValueError):
            is_downwind(91, 0, 0, 0, wind_direction=90)


class TestGetDistanceCategory:
    def test_immediate_below_5km(self):
        assert get_distance_category(0) == "immediate"
        assert get_distance_category(4.99) == "immediate"

    def test_near_5_to_20km(self):
        assert get_distance_category(5) == "near"
        assert get_distance_category(19.99) == "near"

    def test_moderate_20_to_50km(self):
        assert get_distance_category(20) == "moderate"
        assert get_distance_category(49.99) == "moderate"

    def test_far_50km_and_above(self):
        assert get_distance_category(50) == "far"
        assert get_distance_category(1000) == "far"


class TestHaversineDistance:
    def test_matches_calculate_distance(self):
        args = (33.7521, -116.7277, 33.9425, -116.7953)
        assert haversine_distance(*args) == calculate_distance(*args)


class TestAssignGridCell:
    def test_same_cell_for_nearby_points(self):
        cell1 = assign_grid_cell(33.7521, -116.7277, cell_size_degrees=0.5)
        cell2 = assign_grid_cell(33.9, -116.9, cell_size_degrees=0.5)
        assert cell1 == cell2

    def test_different_cells_for_distant_points(self):
        cell1 = assign_grid_cell(33.75, -116.72, cell_size_degrees=0.5)
        cell2 = assign_grid_cell(29.95, -90.07, cell_size_degrees=0.5)
        assert cell1 != cell2

    def test_returns_centroid_not_input_coordinate(self):
        cell = assign_grid_cell(33.7521, -116.7277, cell_size_degrees=0.5)
        assert cell != (33.7521, -116.7277)

    def test_deterministic_for_same_input(self):
        cell1 = assign_grid_cell(33.7521, -116.7277, cell_size_degrees=0.5)
        cell2 = assign_grid_cell(33.7521, -116.7277, cell_size_degrees=0.5)
        assert cell1 == cell2

    def test_raises_on_invalid_coordinates(self):
        with pytest.raises(ValueError):
            assign_grid_cell(91, 0)

    def test_raises_on_non_positive_cell_size(self):
        with pytest.raises(ValueError):
            assign_grid_cell(33.75, -116.72, cell_size_degrees=0)
        with pytest.raises(ValueError):
            assign_grid_cell(33.75, -116.72, cell_size_degrees=-1)


# ---------------------------------------------------------------------------
# time_utils.py
# ---------------------------------------------------------------------------

class TestGetUtcNow:
    def test_has_utc_timezone(self):
        now = get_utc_now()
        assert now.tzinfo is not None
        assert now.utcoffset() == timedelta(0)


class TestGetUtcTimestampStr:
    def test_uses_z_suffix_not_offset(self):
        ts = get_utc_timestamp_str()
        assert ts.endswith("Z")
        assert "+00:00" not in ts

    def test_parses_back_to_a_valid_timestamp(self):
        ts = get_utc_timestamp_str()
        parsed = parse_iso_timestamp(ts)
        assert parsed.tzinfo is not None


class TestRelativeTimeFunctions:
    def test_hours_ago(self):
        result = hours_ago(2)
        expected = get_utc_now() - timedelta(hours=2)
        assert abs((result - expected).total_seconds()) < 1

    def test_minutes_ago(self):
        result = minutes_ago(30)
        expected = get_utc_now() - timedelta(minutes=30)
        assert abs((result - expected).total_seconds()) < 1

    def test_days_ago(self):
        result = days_ago(3)
        expected = get_utc_now() - timedelta(days=3)
        assert abs((result - expected).total_seconds()) < 1

    def test_seconds_ago(self):
        result = seconds_ago(45)
        expected = get_utc_now() - timedelta(seconds=45)
        assert abs((result - expected).total_seconds()) < 1

    def test_zero_hours_ago_is_essentially_now(self):
        result = hours_ago(0)
        assert abs((get_utc_now() - result).total_seconds()) < 1


class TestTimeSince:
    def test_elapsed_seconds_approximately_correct(self):
        past = minutes_ago(5)
        elapsed = time_since(past)
        assert 295 < elapsed < 305

    def test_handles_naive_datetime(self):
        naive_past = get_utc_now().replace(tzinfo=None) - timedelta(minutes=5)
        elapsed = time_since(naive_past)
        assert 295 < elapsed < 305


class TestIsOlderThanAndIsWithinHours:
    def test_recent_timestamp_not_older_than(self):
        recent = minutes_ago(10)
        assert is_older_than(recent, hours=1) is False

    def test_old_timestamp_is_older_than(self):
        old = days_ago(3)
        assert is_older_than(old, hours=24) is True

    def test_is_within_hours_is_inverse_of_is_older_than(self):
        recent = minutes_ago(10)
        old = days_ago(3)
        assert is_within_hours(recent, hours=1) is True
        assert is_within_hours(old, hours=1) is False

    def test_handles_naive_datetime(self):
        naive_recent = get_utc_now().replace(tzinfo=None) - timedelta(minutes=10)
        assert is_older_than(naive_recent, hours=1) is False


class TestMonitoringCycleFunctions:
    def test_cycle_time_is_rounded_to_interval(self):
        cycle_time = get_monitoring_cycle_time(interval_minutes=5)
        assert cycle_time.minute % 5 == 0
        assert cycle_time.second == 0
        assert cycle_time.microsecond == 0

    def test_last_cycle_is_one_interval_before_current(self):
        current = get_monitoring_cycle_time(interval_minutes=5)
        last = get_last_cycle_time(interval_minutes=5)
        assert (current - last) == timedelta(minutes=5)

    def test_next_cycle_in_is_non_negative_and_within_interval(self):
        seconds = next_cycle_in(interval_minutes=5)
        assert 0 <= seconds <= 300


class TestFormatTimestamp:
    def test_default_format(self):
        ts = datetime(2026, 7, 20, 14, 30, 0, tzinfo=timezone.utc)
        assert format_timestamp(ts) == "2026-07-20 14:30:00"

    def test_custom_format(self):
        ts = datetime(2026, 7, 20, 14, 30, 0, tzinfo=timezone.utc)
        assert format_timestamp(ts, "%Y-%m-%d") == "2026-07-20"

    def test_handles_naive_datetime(self):
        ts = datetime(2026, 7, 20, 14, 30, 0)
        assert format_timestamp(ts) == "2026-07-20 14:30:00"


class TestParseIsoTimestamp:
    def test_parses_z_suffix(self):
        dt = parse_iso_timestamp("2026-07-20T14:30:00Z")
        assert dt.year == 2026 and dt.month == 7 and dt.day == 20
        assert dt.tzinfo is not None

    def test_parses_explicit_offset(self):
        dt = parse_iso_timestamp("2026-07-20T14:30:00+00:00")
        assert dt.hour == 14

    def test_parses_naive_string_as_utc(self):
        dt = parse_iso_timestamp("2026-07-20T14:30:00")
        assert dt.tzinfo is not None

    def test_raises_on_invalid_format(self):
        with pytest.raises(ValueError):
            parse_iso_timestamp("not-a-timestamp")

    def test_round_trips_with_get_utc_timestamp_str(self):
        original = get_utc_now()
        parsed = parse_iso_timestamp(original.isoformat())
        assert abs((original - parsed).total_seconds()) < 1


class TestGetDateRange:
    def test_default_seven_days(self):
        start, end = get_date_range()
        assert (end - start) == pytest.approx(timedelta(days=7), abs=timedelta(seconds=1))

    def test_custom_days(self):
        start, end = get_date_range(days=30)
        assert (end - start) == pytest.approx(timedelta(days=30), abs=timedelta(seconds=1))

    def test_start_before_end(self):
        start, end = get_date_range(1)
        assert start < end


class TestIsBusinessHours:
    def test_9am_utc_is_business_hours(self):
        ts = datetime(2026, 7, 20, 9, 0, 0, tzinfo=timezone.utc)
        assert is_business_hours(ts) is True

    def test_4_59pm_utc_is_business_hours(self):
        ts = datetime(2026, 7, 20, 16, 59, 0, tzinfo=timezone.utc)
        assert is_business_hours(ts) is True

    def test_5pm_utc_is_not_business_hours(self):
        ts = datetime(2026, 7, 20, 17, 0, 0, tzinfo=timezone.utc)
        assert is_business_hours(ts) is False

    def test_8_59am_utc_is_not_business_hours(self):
        ts = datetime(2026, 7, 20, 8, 59, 0, tzinfo=timezone.utc)
        assert is_business_hours(ts) is False

    def test_midnight_is_not_business_hours(self):
        ts = datetime(2026, 7, 20, 0, 0, 0, tzinfo=timezone.utc)
        assert is_business_hours(ts) is False

    def test_handles_naive_datetime(self):
        ts = datetime(2026, 7, 20, 12, 0, 0)
        assert is_business_hours(ts) is True

    def test_defaults_to_now_when_no_argument(self):
        result = is_business_hours()
        assert isinstance(result, bool)


# ---------------------------------------------------------------------------
# validation.py
# ---------------------------------------------------------------------------

class TestValidateCoordinate:
    def test_valid_returns_no_errors(self):
        is_valid, errors = validate_coordinate(33.75, -116.72)
        assert is_valid is True
        assert errors == []

    def test_none_values_rejected(self):
        is_valid, errors = validate_coordinate(None, -116.72)
        assert is_valid is False
        assert "cannot be None" in errors[0]

    def test_non_numeric_rejected(self):
        is_valid, errors = validate_coordinate("abc", "def")
        assert is_valid is False
        assert "numeric" in errors[0]

    def test_latitude_out_of_range_reported(self):
        is_valid, errors = validate_coordinate(91, 0)
        assert is_valid is False
        assert any("Latitude" in e for e in errors)

    def test_longitude_out_of_range_reported(self):
        is_valid, errors = validate_coordinate(0, 181)
        assert is_valid is False
        assert any("Longitude" in e for e in errors)

    def test_both_out_of_range_reports_both_errors(self):
        is_valid, errors = validate_coordinate(91, 181)
        assert is_valid is False
        assert len(errors) == 2


class TestValidatePropertyData:
    def test_valid_property_passes(self):
        prop = {"address": "123 Main St", "latitude": 33.75, "longitude": -116.72}
        is_valid, errors = validate_property_data(prop)
        assert is_valid is True
        assert errors == []

    def test_non_dict_rejected(self):
        is_valid, errors = validate_property_data("not a dict")
        assert is_valid is False

    def test_missing_required_field_reported(self):
        is_valid, errors = validate_property_data({"address": "123 Main St"})
        assert is_valid is False
        assert any("longitude" in e for e in errors)

    def test_none_required_field_reported(self):
        prop = {"address": None, "latitude": 33.75, "longitude": -116.72}
        is_valid, errors = validate_property_data(prop)
        assert is_valid is False

    def test_invalid_coordinates_propagate_as_errors(self):
        prop = {"address": "123 Main St", "latitude": 91, "longitude": -116.72}
        is_valid, errors = validate_property_data(prop)
        assert is_valid is False
        assert any("Latitude" in e for e in errors)

    def test_negative_property_id_rejected(self):
        prop = {"address": "x", "latitude": 33.75, "longitude": -116.72, "property_id": -1}
        is_valid, errors = validate_property_data(prop)
        assert is_valid is False

    def test_non_numeric_elevation_rejected(self):
        prop = {"address": "x", "latitude": 33.75, "longitude": -116.72, "elevation_m": "high"}
        is_valid, errors = validate_property_data(prop)
        assert is_valid is False

    def test_invalid_boolean_field_rejected(self):
        prop = {"address": "x", "latitude": 33.75, "longitude": -116.72, "is_in_floodplain": "yes"}
        is_valid, errors = validate_property_data(prop)
        assert is_valid is False

    def test_boolean_field_accepts_int(self):
        prop = {"address": "x", "latitude": 33.75, "longitude": -116.72, "is_in_floodplain": 1}
        is_valid, errors = validate_property_data(prop)
        assert is_valid is True

    def test_invalid_string_field_rejected(self):
        prop = {"address": "x", "latitude": 33.75, "longitude": -116.72, "state": 123}
        is_valid, errors = validate_property_data(prop)
        assert is_valid is False


class TestValidateRiskScore:
    def test_valid_scores(self):
        for score in (0, 50, 100):
            is_valid, errors = validate_risk_score(score)
            assert is_valid is True
            assert errors == []

    def test_none_rejected(self):
        is_valid, errors = validate_risk_score(None)
        assert is_valid is False
        assert "cannot be None" in errors[0]

    def test_above_100_rejected(self):
        is_valid, errors = validate_risk_score(150)
        assert is_valid is False

    def test_below_zero_rejected(self):
        is_valid, errors = validate_risk_score(-1)
        assert is_valid is False

    def test_non_numeric_rejected(self):
        is_valid, errors = validate_risk_score("high")
        assert is_valid is False
        assert "numeric" in errors[0]

    def test_risk_type_included_in_error_message(self):
        is_valid, errors = validate_risk_score(None, risk_type="wildfire")
        assert "wildfire" in errors[0]


class TestValidateRiskAssessment:
    def test_valid_assessment_passes(self):
        assessment = {
            "property_id": 1, "assessment_timestamp": "2026-07-20T00:00:00Z",
            "wildfire_risk_score": 50.0, "flood_risk_score": 10.0,
            "overall_risk_score": 40.0, "risk_level": "medium",
        }
        is_valid, errors = validate_risk_assessment(assessment)
        assert is_valid is True

    def test_non_dict_rejected(self):
        is_valid, errors = validate_risk_assessment([1, 2, 3])
        assert is_valid is False

    def test_missing_required_fields_reported(self):
        is_valid, errors = validate_risk_assessment({})
        assert is_valid is False
        assert len(errors) == 2

    def test_invalid_wildfire_score_reported(self):
        assessment = {"property_id": 1, "assessment_timestamp": "x", "wildfire_risk_score": 150}
        is_valid, errors = validate_risk_assessment(assessment)
        assert is_valid is False

    def test_invalid_flood_score_reported(self):
        assessment = {"property_id": 1, "assessment_timestamp": "x", "flood_risk_score": -5}
        is_valid, errors = validate_risk_assessment(assessment)
        assert is_valid is False

    def test_invalid_overall_score_reported(self):
        assessment = {"property_id": 1, "assessment_timestamp": "x", "overall_risk_score": 200}
        is_valid, errors = validate_risk_assessment(assessment)
        assert is_valid is False

    def test_invalid_risk_level_reported(self):
        assessment = {"property_id": 1, "assessment_timestamp": "x", "risk_level": "extreme"}
        is_valid, errors = validate_risk_assessment(assessment)
        assert is_valid is False

    def test_valid_risk_levels_accepted(self):
        for level in ("low", "medium", "high", "critical"):
            assessment = {"property_id": 1, "assessment_timestamp": "x", "risk_level": level}
            is_valid, errors = validate_risk_assessment(assessment)
            assert is_valid is True


class TestValidateHazardData:
    def test_valid_hazard_passes(self):
        hazard = {
            "hazard_type": "wildfire", "source": "NASA_FIRMS",
            "latitude": 33.75, "longitude": -116.72,
            "observation_timestamp": "2026-07-20T00:00:00Z",
            "confidence": 0.9, "value": 200.0,
        }
        is_valid, errors = validate_hazard_data(hazard)
        assert is_valid is True

    def test_non_dict_rejected(self):
        is_valid, errors = validate_hazard_data("nope")
        assert is_valid is False

    def test_missing_required_fields_reported(self):
        is_valid, errors = validate_hazard_data({})
        assert is_valid is False
        assert len(errors) == 5

    def test_invalid_coordinates_reported(self):
        hazard = {
            "hazard_type": "wildfire", "source": "x", "latitude": 91, "longitude": 0,
            "observation_timestamp": "x",
        }
        is_valid, errors = validate_hazard_data(hazard)
        assert is_valid is False

    def test_invalid_hazard_type_reported(self):
        hazard = {
            "hazard_type": "meteor", "source": "x", "latitude": 0, "longitude": 0,
            "observation_timestamp": "x",
        }
        is_valid, errors = validate_hazard_data(hazard)
        assert is_valid is False

    def test_confidence_out_of_range_reported(self):
        hazard = {
            "hazard_type": "wildfire", "source": "x", "latitude": 0, "longitude": 0,
            "observation_timestamp": "x", "confidence": 1.5,
        }
        is_valid, errors = validate_hazard_data(hazard)
        assert is_valid is False

    def test_non_numeric_confidence_reported(self):
        hazard = {
            "hazard_type": "wildfire", "source": "x", "latitude": 0, "longitude": 0,
            "observation_timestamp": "x", "confidence": "high",
        }
        is_valid, errors = validate_hazard_data(hazard)
        assert is_valid is False

    def test_non_numeric_value_reported(self):
        hazard = {
            "hazard_type": "wildfire", "source": "x", "latitude": 0, "longitude": 0,
            "observation_timestamp": "x", "value": "lots",
        }
        is_valid, errors = validate_hazard_data(hazard)
        assert is_valid is False


class TestValidateAlert:
    def test_valid_alert_passes(self):
        alert = {
            "property_id": 1, "risk_type": "wildfire", "triggered_at": "2026-07-20T00:00:00Z",
            "alert_level": "critical", "risk_score": 85.0,
        }
        is_valid, errors = validate_alert(alert)
        assert is_valid is True

    def test_non_dict_rejected(self):
        is_valid, errors = validate_alert(123)
        assert is_valid is False

    def test_missing_required_fields_reported(self):
        is_valid, errors = validate_alert({})
        assert is_valid is False
        assert len(errors) == 3

    def test_invalid_risk_type_reported(self):
        alert = {"property_id": 1, "risk_type": "meteor", "triggered_at": "x"}
        is_valid, errors = validate_alert(alert)
        assert is_valid is False

    def test_invalid_alert_level_reported(self):
        alert = {"property_id": 1, "risk_type": "wildfire", "triggered_at": "x", "alert_level": "urgent"}
        is_valid, errors = validate_alert(alert)
        assert is_valid is False

    def test_invalid_risk_score_reported(self):
        alert = {"property_id": 1, "risk_type": "wildfire", "triggered_at": "x", "risk_score": 500}
        is_valid, errors = validate_alert(alert)
        assert is_valid is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
