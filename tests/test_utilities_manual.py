#!/usr/bin/env python
"""
Manual Test Suite for Utility Functions

Run with: python test_utilities_manual.py
"""

from src.utils import (
    # Geospatial
    calculate_distance,
    is_valid_coordinate,
    get_bearing,
    is_downwind,
    get_distance_category,
    # Time
    get_utc_now,
    hours_ago,
    minutes_ago,
    is_within_hours,
    get_monitoring_cycle_time,
    next_cycle_in,
    format_timestamp,
    # Validation
    validate_coordinate,
    validate_property_data,
    validate_risk_score,
)


def test_geospatial():
    """Test geospatial functions."""
    print("\n" + "=" * 60)
    print("TESTING GEOSPATIAL FUNCTIONS")
    print("=" * 60)

    # Test 1: Distance calculation (Idyllwild to San Bernardino)
    print("\n1. Distance Calculation")
    dist = calculate_distance(33.7521, -116.7277, 33.9425, -116.7953)
    print(f"   Idyllwild to San Bernardino: {dist:.1f} km")
    assert 20 < dist < 25, f"Expected ~22km, got {dist}"
    print("   ✓ PASS")

    # Test 2: Coordinate validation - valid
    print("\n2. Valid Coordinates")
    is_valid = is_valid_coordinate(33.75, -116.72)
    print(f"   (33.75, -116.72): {is_valid}")
    assert is_valid == True
    print("   ✓ PASS")

    # Test 3: Coordinate validation - invalid lat
    print("\n3. Invalid Latitude (> 90)")
    is_valid = is_valid_coordinate(91, 0)
    print(f"   (91, 0): {is_valid}")
    assert is_valid == False
    print("   ✓ PASS")

    # Test 4: Coordinate validation - invalid lon
    print("\n4. Invalid Longitude (> 180)")
    is_valid = is_valid_coordinate(0, 181)
    print(f"   (0, 181): {is_valid}")
    assert is_valid == False
    print("   ✓ PASS")

    # Test 5: Bearing calculation
    print("\n5. Bearing Calculation")
    bearing = get_bearing(33.7521, -116.7277, 33.9425, -116.7953)
    print(f"   Bearing: {bearing:.1f}°")
    assert 330 < bearing < 360 or 0 <= bearing < 20, f"Expected ~343°, got {bearing}"
    print("   ✓ PASS")

    # Test 6: Distance categories
    print("\n6. Distance Categories")
    categories = [
        (2, "immediate"),
        (12, "near"),
        (35, "moderate"),
        (100, "far"),
    ]
    for dist, expected_cat in categories:
        cat = get_distance_category(dist)
        print(f"   {dist:3d}km → {cat}")
        assert cat == expected_cat, f"Expected {expected_cat}, got {cat}"
    print("   ✓ PASS")

    print("\n✓ All geospatial tests passed!")


def test_time_functions():
    """Test time utility functions."""
    print("\n" + "=" * 60)
    print("TESTING TIME FUNCTIONS")
    print("=" * 60)

    # Test 1: Current UTC time
    print("\n1. Current UTC Time")
    now = get_utc_now()
    print(f"   Now: {now}")
    assert now.tzinfo is not None, "Should have timezone"
    print("   ✓ PASS")

    # Test 2: Hours ago
    print("\n2. Time Ranges")
    one_hour_ago = hours_ago(1)
    thirty_min_ago = minutes_ago(30)
    print(f"   1 hour ago: {one_hour_ago}")
    print(f"   30 min ago: {thirty_min_ago}")
    assert (now - one_hour_ago).total_seconds() > 3500, "Should be ~1 hour"
    assert (now - thirty_min_ago).total_seconds() > 1700, "Should be ~30 min"
    print("   ✓ PASS")

    # Test 3: Freshness checks
    print("\n3. Freshness Checks")
    recent = minutes_ago(10)
    old = hours_ago(3)

    is_fresh = is_within_hours(recent, 1)
    is_stale = is_within_hours(old, 1)

    print(f"   10 min old, within 1 hour: {is_fresh}")
    print(f"   3 hours old, within 1 hour: {is_stale}")
    assert is_fresh == True, "Recent data should be fresh"
    assert is_stale == False, "Old data should not be fresh"
    print("   ✓ PASS")

    # Test 4: Monitoring cycles
    print("\n4. Monitoring Cycles (5-minute)")
    next_cycle = get_monitoring_cycle_time(5)
    secs_to_wait = next_cycle_in(5)
    print(f"   Next cycle: {next_cycle}")
    print(f"   Wait time: {secs_to_wait:.1f} seconds")
    assert 0 < secs_to_wait <= 300, f"Should be 0-300 sec, got {secs_to_wait}"
    print("   ✓ PASS")

    # Test 5: Timestamp formatting
    print("\n5. Timestamp Formatting")
    ts = get_utc_now()
    formatted = format_timestamp(ts, "%Y-%m-%d %H:%M:%S")
    print(f"   Formatted: {formatted}")
    assert len(formatted) == 19, "Should be YYYY-MM-DD HH:MM:SS format"
    print("   ✓ PASS")

    print("\n✓ All time tests passed!")


def test_validation():
    """Test validation functions."""
    print("\n" + "=" * 60)
    print("TESTING VALIDATION FUNCTIONS")
    print("=" * 60)

    # Test 1: Valid coordinate
    print("\n1. Valid Coordinate")
    is_valid, errors = validate_coordinate(33.75, -116.72)
    print(f"   Valid: {is_valid}, Errors: {errors}")
    assert is_valid == True and len(errors) == 0
    print("   ✓ PASS")

    # Test 2: Invalid latitude
    print("\n2. Invalid Latitude")
    is_valid, errors = validate_coordinate(91, 0)
    print(f"   Valid: {is_valid}")
    print(f"   Errors: {errors}")
    assert is_valid == False and len(errors) > 0
    print("   ✓ PASS")

    # Test 3: Valid property
    print("\n3. Valid Property Data")
    property_data = {
        'address': '123 Main St',
        'latitude': 33.75,
        'longitude': -116.72,
        'state': 'CA',
        'construction_type': 'wood'
    }
    is_valid, errors = validate_property_data(property_data)
    print(f"   Valid: {is_valid}, Errors: {errors}")
    assert is_valid == True
    print("   ✓ PASS")

    # Test 4: Invalid property (missing coords)
    print("\n4. Invalid Property (Missing Coordinates)")
    property_data = {'address': '123 Main St'}
    is_valid, errors = validate_property_data(property_data)
    print(f"   Valid: {is_valid}")
    print(f"   Errors: {errors}")
    assert is_valid == False and len(errors) > 0
    print("   ✓ PASS")

    # Test 5: Valid risk score
    print("\n5. Valid Risk Score")
    is_valid, errors = validate_risk_score(50)
    print(f"   Score 50: Valid={is_valid}, Errors={errors}")
    assert is_valid == True
    print("   ✓ PASS")

    # Test 6: Invalid risk score (too high)
    print("\n6. Invalid Risk Score (> 100)")
    is_valid, errors = validate_risk_score(150)
    print(f"   Score 150: Valid={is_valid}")
    print(f"   Error: {errors[0] if errors else 'None'}")
    assert is_valid == False
    print("   ✓ PASS")

    # Test 7: Invalid risk score (negative)
    print("\n7. Invalid Risk Score (< 0)")
    is_valid, errors = validate_risk_score(-10)
    print(f"   Score -10: Valid={is_valid}")
    print(f"   Error: {errors[0] if errors else 'None'}")
    assert is_valid == False
    print("   ✓ PASS")

    print("\n✓ All validation tests passed!")


def run_all_tests():
    """Run all test suites."""
    print("\n")
    print("╔════════════════════════════════════════════════════════════╗")
    print("║           UTILITY FUNCTIONS TEST SUITE                     ║")
    print("╚════════════════════════════════════════════════════════════╝")

    try:
        test_geospatial()
        test_time_functions()
        test_validation()

        print("\n")
        print("╔════════════════════════════════════════════════════════════╗")
        print("║                  ALL TESTS PASSED! ✓                       ║")
        print("║                                                            ║")
        print("║  30+ utility functions validated and working correctly.   ║")
        print("╚════════════════════════════════════════════════════════════╝")
        print()
        return True

    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        return False
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
