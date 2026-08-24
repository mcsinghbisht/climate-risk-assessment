"""
Utility Module - Geospatial, Time, and Validation Functions

Provides core utility functions for the risk assessment system.
"""

# Geospatial utilities
from src.utils.geo_utils import (
    calculate_distance,
    is_valid_coordinate,
    get_bearing,
    is_downwind,
    get_distance_category,
    haversine_distance,
    assign_grid_cell,
    EARTH_RADIUS_KM,
)

# Time utilities
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

# Validation utilities
from src.utils.validation import (
    validate_coordinate,
    validate_property_data,
    validate_risk_score,
    validate_risk_assessment,
    validate_hazard_data,
    validate_alert,
)

__all__ = [
    # Geospatial
    "calculate_distance",
    "is_valid_coordinate",
    "get_bearing",
    "is_downwind",
    "get_distance_category",
    "haversine_distance",
    "assign_grid_cell",
    "EARTH_RADIUS_KM",
    # Time
    "get_utc_now",
    "get_utc_timestamp_str",
    "hours_ago",
    "minutes_ago",
    "days_ago",
    "seconds_ago",
    "time_since",
    "is_older_than",
    "is_within_hours",
    "get_monitoring_cycle_time",
    "get_last_cycle_time",
    "next_cycle_in",
    "format_timestamp",
    "parse_iso_timestamp",
    "get_date_range",
    "is_business_hours",
    # Validation
    "validate_coordinate",
    "validate_property_data",
    "validate_risk_score",
    "validate_risk_assessment",
    "validate_hazard_data",
    "validate_alert",
]
