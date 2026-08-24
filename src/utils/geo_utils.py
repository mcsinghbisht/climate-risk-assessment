"""
Geospatial Utility Functions

Provides geospatial calculations for risk assessment:
- Distance calculations between coordinates
- Coordinate validation
- Bearing/direction calculations
- Proximity checks
- Grid-cell assignment (for geographic-cell-based data ingestion, see
  docs/scaling-design.md)
"""

import math
from typing import Tuple


# Earth's radius in kilometers
EARTH_RADIUS_KM = 6371.0


def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate distance between two coordinates using Haversine formula.

    Args:
        lat1: Latitude of first point (degrees)
        lon1: Longitude of first point (degrees)
        lat2: Latitude of second point (degrees)
        lon2: Longitude of second point (degrees)

    Returns:
        Distance in kilometers (float)

    Raises:
        ValueError: If coordinates are invalid
    """
    if not (is_valid_coordinate(lat1, lon1) and is_valid_coordinate(lat2, lon2)):
        raise ValueError("Invalid coordinates provided")

    # Convert degrees to radians
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)

    # Haversine formula
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad

    a = (math.sin(dlat / 2) ** 2 +
         math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2)
    c = 2 * math.asin(math.sqrt(a))

    distance = EARTH_RADIUS_KM * c
    return distance


def is_valid_coordinate(lat: float, lon: float) -> bool:
    """
    Validate that a coordinate pair is within valid ranges.

    Args:
        lat: Latitude in degrees (-90 to 90)
        lon: Longitude in degrees (-180 to 180)

    Returns:
        True if coordinates are valid, False otherwise
    """
    try:
        lat_float = float(lat)
        lon_float = float(lon)

        # Check valid ranges
        if not (-90 <= lat_float <= 90):
            return False
        if not (-180 <= lon_float <= 180):
            return False

        # Check for NaN or Inf
        if math.isnan(lat_float) or math.isnan(lon_float):
            return False
        if math.isinf(lat_float) or math.isinf(lon_float):
            return False

        return True
    except (TypeError, ValueError):
        return False


def get_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate bearing (direction) from point 1 to point 2.

    Args:
        lat1: Latitude of first point (degrees)
        lon1: Longitude of first point (degrees)
        lat2: Latitude of second point (degrees)
        lon2: Longitude of second point (degrees)

    Returns:
        Bearing in degrees (0-360), where 0 is North, 90 is East, etc.

    Raises:
        ValueError: If coordinates are invalid
    """
    if not (is_valid_coordinate(lat1, lon1) and is_valid_coordinate(lat2, lon2)):
        raise ValueError("Invalid coordinates provided")

    # Convert to radians
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)

    # Calculate bearing
    dlon = lon2_rad - lon1_rad
    x = math.sin(dlon) * math.cos(lat2_rad)
    y = (math.cos(lat1_rad) * math.sin(lat2_rad) -
         math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(dlon))

    bearing_rad = math.atan2(x, y)
    bearing_deg = math.degrees(bearing_rad)

    # Normalize to 0-360 range
    bearing_deg = (bearing_deg + 360) % 360

    return bearing_deg


def is_downwind(fire_lat: float, fire_lon: float, property_lat: float,
                property_lon: float, wind_direction: float) -> bool:
    """
    Check if property is downwind from fire (fire is upwind).

    Args:
        fire_lat: Fire location latitude
        fire_lon: Fire location longitude
        property_lat: Property location latitude
        property_lon: Property location longitude
        wind_direction: Wind direction in degrees (0=N, 90=E, 180=S, 270=W)

    Returns:
        True if property is downwind (fire is upwind), False otherwise

    Raises:
        ValueError: If coordinates are invalid
    """
    bearing_to_property = get_bearing(fire_lat, fire_lon, property_lat, property_lon)

    # Wind direction indicates where wind comes FROM
    # Property is downwind if it's in the direction wind is blowing TO
    # That's opposite of wind direction (wind_direction + 180 degrees)
    wind_blowing_to = (wind_direction + 180) % 360

    # Check if property bearing is within ~45 degrees of wind direction
    angle_diff = abs(bearing_to_property - wind_blowing_to)
    if angle_diff > 180:
        angle_diff = 360 - angle_diff

    return angle_diff <= 45  # Within 45 degrees of downwind direction


def get_distance_category(distance_km: float) -> str:
    """
    Categorize distance for risk assessment.

    Args:
        distance_km: Distance in kilometers

    Returns:
        Category: "immediate" (<5km), "near" (5-20km), "moderate" (20-50km),
                 "far" (>50km)
    """
    if distance_km < 5:
        return "immediate"
    elif distance_km < 20:
        return "near"
    elif distance_km < 50:
        return "moderate"
    else:
        return "far"


def haversine_distance(lat1: float, lon1: float, lat2: float,
                       lon2: float) -> float:
    """
    Alias for calculate_distance using Haversine formula.
    Provided for clarity in risk scoring context.

    Args:
        lat1: Latitude of first point (degrees)
        lon1: Longitude of first point (degrees)
        lat2: Latitude of second point (degrees)
        lon2: Longitude of second point (degrees)

    Returns:
        Distance in kilometers (float)
    """
    return calculate_distance(lat1, lon1, lat2, lon2)


def assign_grid_cell(lat: float, lon: float, cell_size_degrees: float = 0.5) -> Tuple[float, float]:
    """
    Assign a coordinate to its containing grid cell, identified by centroid.

    Used for geographic-cell-based data ingestion (see docs/scaling-design.md):
    properties sharing a cell share hazard data, so hazard-data API calls scale
    with geographic footprint rather than property count.

    Args:
        lat: Latitude in degrees
        lon: Longitude in degrees
        cell_size_degrees: Size of each square grid cell, in degrees
                           (default 0.5deg, ~55km)

    Returns:
        (cell_lat, cell_lon) - the centroid of the cell containing (lat, lon).
        Two coordinates in the same cell always return the identical centroid,
        so it can be used directly as a grouping key.

    Raises:
        ValueError: If coordinates are invalid or cell_size_degrees <= 0
    """
    if not is_valid_coordinate(lat, lon):
        raise ValueError(f"Invalid coordinates: ({lat}, {lon})")
    if cell_size_degrees <= 0:
        raise ValueError(f"cell_size_degrees must be positive, got {cell_size_degrees}")

    cell_lat = (math.floor(lat / cell_size_degrees) + 0.5) * cell_size_degrees
    cell_lon = (math.floor(lon / cell_size_degrees) + 0.5) * cell_size_degrees

    # Round to avoid floating-point noise producing near-duplicate cell keys
    return (round(cell_lat, 6), round(cell_lon, 6))


if __name__ == "__main__":
    # Test functions
    print("=" * 60)
    print("Geospatial Utilities Test")
    print("=" * 60)

    # Test 1: Distance calculation
    print("\n1. Distance Calculation (Haversine)")
    print("-" * 60)
    lat1, lon1 = 33.7521, -116.7277  # Idyllwild, CA
    lat2, lon2 = 33.9425, -116.7953  # San Bernardino, CA
    dist = calculate_distance(lat1, lon1, lat2, lon2)
    print(f"Idyllwild to San Bernardino: {dist:.1f} km")

    # Test 2: Coordinate validation
    print("\n2. Coordinate Validation")
    print("-" * 60)
    test_coords = [
        (33.75, -116.72, "Valid: Idyllwild"),
        (90, 0, "Valid: North Pole"),
        (-90, 0, "Valid: South Pole"),
        (91, 0, "Invalid: Latitude > 90"),
        (0, 181, "Invalid: Longitude > 180"),
        (float('nan'), 0, "Invalid: NaN latitude"),
    ]

    for lat, lon, desc in test_coords:
        valid = is_valid_coordinate(lat, lon)
        status = "[OK]" if valid else "[INVALID]"
        print(f"{status} {desc}")

    # Test 3: Bearing calculation
    print("\n3. Bearing Calculation")
    print("-" * 60)
    bearing = get_bearing(lat1, lon1, lat2, lon2)
    print(f"Bearing from Idyllwild to San Bernardino: {bearing:.1f}°")

    # Test 4: Downwind check
    print("\n4. Downwind Check")
    print("-" * 60)
    wind_dir = 270  # Wind from West (blowing East)
    downwind = is_downwind(lat1, lon1, lat2, lon2, wind_dir)
    print(f"Wind direction: {wind_dir}° (from West)")
    print(f"Is San Bernardino downwind from Idyllwild: {downwind}")

    # Test 5: Distance category
    print("\n5. Distance Categories")
    print("-" * 60)
    test_distances = [2, 10, 30, 60]
    for d in test_distances:
        category = get_distance_category(d)
        print(f"{d:3d} km → {category}")

    # Test 6: Grid cell assignment
    print("\n6. Grid Cell Assignment")
    print("-" * 60)
    points = [
        (33.7521, -116.7277, "Idyllwild"),
        (33.9425, -116.7953, "San Bernardino"),
        (29.9511, -90.0715, "New Orleans"),
    ]
    for lat, lon, name in points:
        cell = assign_grid_cell(lat, lon, cell_size_degrees=0.5)
        print(f"{name:20} ({lat}, {lon}) -> cell {cell}")
    # Two nearby points should share a cell
    cell1 = assign_grid_cell(33.7521, -116.7277, 0.5)
    cell2 = assign_grid_cell(33.9425, -116.7953, 0.5)
    print(f"Idyllwild and San Bernardino share a cell: {cell1 == cell2}")

    print("\n" + "=" * 60)
    print("All tests complete!")
    print("=" * 60)
