"""
Validation Utility Functions

Provides data validation for risk assessment:
- Property data validation
- Coordinate validation
- Risk score validation
- Hazard data validation
- Alert message validation
"""

from typing import Tuple, List, Dict, Any

try:
    from src.utils.geo_utils import is_valid_coordinate
except ImportError:
    from geo_utils import is_valid_coordinate


def validate_coordinate(lat: float, lon: float) -> Tuple[bool, List[str]]:
    """
    Validate a coordinate pair with detailed error messages.

    Args:
        lat: Latitude in degrees
        lon: Longitude in degrees

    Returns:
        Tuple of (is_valid: bool, errors: List[str])
    """
    errors = []

    if lat is None or lon is None:
        errors.append("Latitude and longitude cannot be None")
        return False, errors

    try:
        lat_float = float(lat)
        lon_float = float(lon)
    except (TypeError, ValueError):
        errors.append(f"Coordinates must be numeric: lat={lat}, lon={lon}")
        return False, errors

    if lat_float < -90 or lat_float > 90:
        errors.append(f"Latitude must be between -90 and 90, got {lat_float}")

    if lon_float < -180 or lon_float > 180:
        errors.append(f"Longitude must be between -180 and 180, got {lon_float}")

    return len(errors) == 0, errors


def validate_property_data(property_dict: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Validate complete property data structure.

    Args:
        property_dict: Property data dictionary

    Returns:
        Tuple of (is_valid: bool, errors: List[str])
    """
    errors = []

    if not isinstance(property_dict, dict):
        errors.append("Property data must be a dictionary")
        return False, errors

    # Required fields
    required_fields = ['address', 'latitude', 'longitude']
    for field in required_fields:
        if field not in property_dict:
            errors.append(f"Missing required field: {field}")
        elif property_dict[field] is None:
            errors.append(f"Required field cannot be None: {field}")

    if 'latitude' in property_dict and 'longitude' in property_dict:
        is_valid, coord_errors = validate_coordinate(
            property_dict['latitude'],
            property_dict['longitude']
        )
        if not is_valid:
            errors.extend(coord_errors)

    # Validate optional numeric fields
    numeric_fields = {
        'elevation_m': (None, None),  # No range limit
        'property_id': (1, None),  # Must be positive
    }

    for field, (min_val, max_val) in numeric_fields.items():
        if field in property_dict and property_dict[field] is not None:
            try:
                value = float(property_dict[field])
                if min_val is not None and value < min_val:
                    errors.append(f"{field} must be >= {min_val}, got {value}")
                if max_val is not None and value > max_val:
                    errors.append(f"{field} must be <= {max_val}, got {value}")
            except (TypeError, ValueError):
                errors.append(f"{field} must be numeric, got {property_dict[field]}")

    # Validate boolean fields
    boolean_fields = ['is_in_wildland_urban_interface', 'is_in_floodplain']
    for field in boolean_fields:
        if field in property_dict and property_dict[field] is not None:
            if not isinstance(property_dict[field], (bool, int)):
                errors.append(f"{field} must be boolean, got {property_dict[field]}")

    # Validate string fields
    string_fields = ['address', 'state', 'county', 'construction_type', 'soil_type']
    for field in string_fields:
        if field in property_dict and property_dict[field] is not None:
            if not isinstance(property_dict[field], str):
                errors.append(f"{field} must be string, got {type(property_dict[field])}")

    return len(errors) == 0, errors


def validate_risk_score(risk_score: float, risk_type: str = "overall") -> Tuple[bool, List[str]]:
    """
    Validate a risk score value.

    Args:
        risk_score: Risk score value (should be 0-100)
        risk_type: Type of risk score (wildfire, flood, overall)

    Returns:
        Tuple of (is_valid: bool, errors: List[str])
    """
    errors = []

    if risk_score is None:
        errors.append(f"{risk_type} risk score cannot be None")
        return False, errors

    try:
        score_float = float(risk_score)
    except (TypeError, ValueError):
        errors.append(f"{risk_type} risk score must be numeric, got {risk_score}")
        return False, errors

    if score_float < 0 or score_float > 100:
        errors.append(f"{risk_type} risk score must be between 0-100, got {score_float}")

    return len(errors) == 0, errors


def validate_risk_assessment(assessment_dict: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Validate risk assessment data structure.

    Args:
        assessment_dict: Risk assessment dictionary

    Returns:
        Tuple of (is_valid: bool, errors: List[str])
    """
    errors = []

    if not isinstance(assessment_dict, dict):
        errors.append("Risk assessment must be a dictionary")
        return False, errors

    # Required fields
    required_fields = ['property_id', 'assessment_timestamp']
    for field in required_fields:
        if field not in assessment_dict:
            errors.append(f"Missing required field: {field}")

    # Validate scores
    if 'wildfire_risk_score' in assessment_dict and assessment_dict['wildfire_risk_score'] is not None:
        is_valid, score_errors = validate_risk_score(
            assessment_dict['wildfire_risk_score'], 'wildfire')
        if not is_valid:
            errors.extend(score_errors)

    if 'flood_risk_score' in assessment_dict and assessment_dict['flood_risk_score'] is not None:
        is_valid, score_errors = validate_risk_score(
            assessment_dict['flood_risk_score'], 'flood')
        if not is_valid:
            errors.extend(score_errors)

    if 'overall_risk_score' in assessment_dict and assessment_dict['overall_risk_score'] is not None:
        is_valid, score_errors = validate_risk_score(
            assessment_dict['overall_risk_score'], 'overall')
        if not is_valid:
            errors.extend(score_errors)

    # Validate risk level
    if 'risk_level' in assessment_dict and assessment_dict['risk_level'] is not None:
        valid_levels = ['low', 'medium', 'high', 'critical']
        if assessment_dict['risk_level'] not in valid_levels:
            errors.append(f"risk_level must be one of {valid_levels}, got {assessment_dict['risk_level']}")

    return len(errors) == 0, errors


def validate_hazard_data(hazard_dict: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Validate hazard data from external sources.

    Args:
        hazard_dict: Hazard data dictionary

    Returns:
        Tuple of (is_valid: bool, errors: List[str])
    """
    errors = []

    if not isinstance(hazard_dict, dict):
        errors.append("Hazard data must be a dictionary")
        return False, errors

    # Required fields
    required_fields = ['hazard_type', 'source', 'latitude', 'longitude', 'observation_timestamp']
    for field in required_fields:
        if field not in hazard_dict:
            errors.append(f"Missing required field: {field}")

    # Validate coordinates
    if 'latitude' in hazard_dict and 'longitude' in hazard_dict:
        is_valid, coord_errors = validate_coordinate(
            hazard_dict['latitude'],
            hazard_dict['longitude']
        )
        if not is_valid:
            errors.extend(coord_errors)

    # Validate hazard type
    if 'hazard_type' in hazard_dict:
        valid_types = ['wildfire', 'flood', 'weather', 'other']
        if hazard_dict['hazard_type'] not in valid_types:
            errors.append(f"hazard_type must be one of {valid_types}, got {hazard_dict['hazard_type']}")

    # Validate confidence (if present)
    if 'confidence' in hazard_dict and hazard_dict['confidence'] is not None:
        try:
            conf = float(hazard_dict['confidence'])
            if conf < 0 or conf > 1:
                errors.append(f"confidence must be between 0-1, got {conf}")
        except (TypeError, ValueError):
            errors.append(f"confidence must be numeric, got {hazard_dict['confidence']}")

    # Validate value (if present)
    if 'value' in hazard_dict and hazard_dict['value'] is not None:
        try:
            float(hazard_dict['value'])
        except (TypeError, ValueError):
            errors.append(f"value must be numeric, got {hazard_dict['value']}")

    return len(errors) == 0, errors


def validate_alert(alert_dict: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Validate alert data structure.

    Args:
        alert_dict: Alert dictionary

    Returns:
        Tuple of (is_valid: bool, errors: List[str])
    """
    errors = []

    if not isinstance(alert_dict, dict):
        errors.append("Alert must be a dictionary")
        return False, errors

    # Required fields
    required_fields = ['property_id', 'risk_type', 'triggered_at']
    for field in required_fields:
        if field not in alert_dict:
            errors.append(f"Missing required field: {field}")

    # Validate risk type
    if 'risk_type' in alert_dict:
        valid_types = ['wildfire', 'flood', 'portfolio']
        if alert_dict['risk_type'] not in valid_types:
            errors.append(f"risk_type must be one of {valid_types}, got {alert_dict['risk_type']}")

    # Validate alert level
    if 'alert_level' in alert_dict and alert_dict['alert_level'] is not None:
        valid_levels = ['warning', 'critical']
        if alert_dict['alert_level'] not in valid_levels:
            errors.append(f"alert_level must be one of {valid_levels}, got {alert_dict['alert_level']}")

    # Validate risk score (if present)
    if 'risk_score' in alert_dict and alert_dict['risk_score'] is not None:
        is_valid, score_errors = validate_risk_score(alert_dict['risk_score'])
        if not is_valid:
            errors.extend(score_errors)

    return len(errors) == 0, errors


if __name__ == "__main__":
    # Test functions
    print("=" * 60)
    print("Validation Utilities Test")
    print("=" * 60)

    # Test 1: Coordinate validation
    print("\n1. Coordinate Validation")
    print("-" * 60)
    test_coords = [
        (33.75, -116.72, "Valid"),
        (91, 0, "Invalid: lat > 90"),
        (0, 181, "Invalid: lon > 180"),
    ]

    for lat, lon, desc in test_coords:
        is_valid, errors = validate_coordinate(lat, lon)
        status = "[VALID]" if is_valid else "[INVALID]"
        print(f"{status} {desc}")
        if errors:
            for error in errors:
                print(f"        → {error}")

    # Test 2: Property validation
    print("\n2. Property Data Validation")
    print("-" * 60)
    valid_property = {
        'address': '123 Main St',
        'latitude': 33.75,
        'longitude': -116.72,
        'state': 'CA',
        'construction_type': 'wood'
    }
    is_valid, errors = validate_property_data(valid_property)
    print(f"Valid property: {is_valid}")

    invalid_property = {'address': '123 Main St'}  # Missing coordinates
    is_valid, errors = validate_property_data(invalid_property)
    print(f"Invalid property: {is_valid}")
    for error in errors:
        print(f"  → {error}")

    # Test 3: Risk score validation
    print("\n3. Risk Score Validation")
    print("-" * 60)
    test_scores = [50, 100, 101, -1, None]
    for score in test_scores:
        is_valid, errors = validate_risk_score(score)
        status = "[VALID]" if is_valid else "[INVALID]"
        print(f"{status} Score: {score}")
        if errors:
            print(f"        → {errors[0]}")

    print("\n" + "=" * 60)
    print("All tests complete!")
    print("=" * 60)
