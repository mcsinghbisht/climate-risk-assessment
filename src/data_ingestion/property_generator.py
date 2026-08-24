"""
Sample Property Generator

Generates 100 realistic property records for the MVP, distributed across
high wildfire-risk states, high flood-risk states, and mixed/other states,
so the risk-scoring engine has meaningful variety to work with.

This is synthetic data for development and testing only - not real
property records.
"""

import json
import csv
import random
from pathlib import Path
from typing import List, Dict

PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
JSON_OUTPUT_PATH = DATA_DIR / "sample_properties.json"
CSV_OUTPUT_PATH = DATA_DIR / "sample_properties.csv"

DEFAULT_SEED = 42

# Each state config drives realistic coordinate generation and risk-relevant
# attribute weighting. category is used only to bias construction/floodplain/
# WUI distributions - it is not stored on the property record itself.
STATE_CONFIGS = [
    {
        "state": "CA", "count": 20, "category": "wildfire",
        "counties": ["Riverside", "San Bernardino", "Los Angeles", "Ventura", "San Diego"],
        "cities": ["Idyllwild", "Big Bear Lake", "Julian", "Lake Arrowhead", "Ojai"],
        "center": (34.0, -117.5), "spread": 2.2,
        "elevation_range": (300, 2200),
    },
    {
        "state": "AZ", "count": 15, "category": "wildfire",
        "counties": ["Coconino", "Yavapai", "Gila", "Cochise"],
        "cities": ["Flagstaff", "Prescott", "Payson", "Sedona", "Show Low"],
        "center": (34.5, -111.5), "spread": 1.8,
        "elevation_range": (900, 2300),
    },
    {
        "state": "CO", "count": 10, "category": "wildfire",
        "counties": ["Boulder", "El Paso", "Larimer", "Douglas"],
        "cities": ["Boulder", "Estes Park", "Woodland Park", "Evergreen"],
        "center": (39.5, -105.3), "spread": 1.2,
        "elevation_range": (1500, 2900),
    },
    {
        "state": "LA", "count": 15, "category": "flood",
        "counties": ["Orleans", "Jefferson", "St. Tammany", "Lafourche"],
        "cities": ["New Orleans", "Metairie", "Slidell", "Houma"],
        "center": (29.9, -90.3), "spread": 0.9,
        "elevation_range": (0, 15),
    },
    {
        "state": "TX", "count": 12, "category": "flood",
        "counties": ["Harris", "Galveston", "Jefferson", "Brazoria"],
        "cities": ["Houston", "Galveston", "Beaumont", "Pearland"],
        "center": (29.7, -95.3), "spread": 1.1,
        "elevation_range": (0, 40),
    },
    {
        "state": "FL", "count": 13, "category": "flood",
        "counties": ["Miami-Dade", "Broward", "Pinellas", "Lee"],
        "cities": ["Miami", "Fort Lauderdale", "St. Petersburg", "Fort Myers"],
        "center": (26.5, -80.9), "spread": 1.3,
        "elevation_range": (0, 12),
    },
    {
        "state": "OR", "count": 5, "category": "mixed",
        "counties": ["Deschutes", "Jackson"],
        "cities": ["Bend", "Ashland"],
        "center": (43.9, -121.6), "spread": 1.0,
        "elevation_range": (300, 1400),
    },
    {
        "state": "WA", "count": 4, "category": "mixed",
        "counties": ["Chelan", "King"],
        "cities": ["Wenatchee", "North Bend"],
        "center": (47.5, -120.9), "spread": 1.0,
        "elevation_range": (100, 1200),
    },
    {
        "state": "NC", "count": 3, "category": "mixed",
        "counties": ["Buncombe", "New Hanover"],
        "cities": ["Asheville", "Wilmington"],
        "center": (35.5, -79.5), "spread": 1.5,
        "elevation_range": (0, 700),
    },
    {
        "state": "NM", "count": 3, "category": "mixed",
        "counties": ["Santa Fe", "Los Alamos"],
        "cities": ["Santa Fe", "Los Alamos"],
        "center": (35.8, -106.0), "spread": 0.8,
        "elevation_range": (1700, 2400),
    },
]

STREET_NAMES = [
    "Pine Ridge", "Maple", "Oak Hollow", "Sunset", "River Bend", "Cedar",
    "Meadow", "Highland", "Willow Creek", "Canyon View", "Lakeshore",
    "Timber", "Bayou", "Magnolia", "Foothill", "Summit", "Aspen",
    "Redwood", "Cypress", "Ridgeline",
]
STREET_TYPES = ["Road", "Drive", "Lane", "Way", "Court", "Avenue", "Street", "Trail"]

CONSTRUCTION_TYPES = ["wood", "masonry", "mixed"]
SOIL_TYPES = ["sandy_loam", "clay", "silty_clay", "loam", "sandy", "peat"]
DRAINAGE_CLASSES = ["well_drained", "moderately_drained", "poorly_drained", "somewhat_poorly_drained"]


def _weighted_choice(rng: random.Random, options: List[str], weights: List[float]) -> str:
    return rng.choices(options, weights=weights, k=1)[0]


def _generate_one_property(rng: random.Random, property_id: int, cfg: dict) -> Dict:
    lat = round(cfg["center"][0] + rng.uniform(-cfg["spread"], cfg["spread"]), 6)
    lon = round(cfg["center"][1] + rng.uniform(-cfg["spread"], cfg["spread"]), 6)

    street_number = rng.randint(100, 9999)
    street = f"{rng.choice(STREET_NAMES)} {rng.choice(STREET_TYPES)}"
    city = rng.choice(cfg["cities"])
    county = rng.choice(cfg["counties"])
    zip_code = f"{rng.randint(10000, 99999)}"
    address = f"{street_number} {street}, {city}, {cfg['state']} {zip_code}"

    elevation_m = round(rng.uniform(*cfg["elevation_range"]), 1)

    # Construction type: wood is more common in wildfire zones, masonry more
    # common in flood zones (broadly realistic regional pattern for the MVP).
    if cfg["category"] == "wildfire":
        construction_type = _weighted_choice(rng, CONSTRUCTION_TYPES, [0.6, 0.2, 0.2])
    elif cfg["category"] == "flood":
        construction_type = _weighted_choice(rng, CONSTRUCTION_TYPES, [0.25, 0.5, 0.25])
    else:
        construction_type = _weighted_choice(rng, CONSTRUCTION_TYPES, [0.4, 0.35, 0.25])

    # WUI flag: much more likely for wildfire-zone properties.
    if cfg["category"] == "wildfire":
        is_in_wui = rng.random() < 0.55
    elif cfg["category"] == "mixed":
        is_in_wui = rng.random() < 0.25
    else:
        is_in_wui = rng.random() < 0.05

    # Floodplain flag: much more likely for flood-zone properties.
    if cfg["category"] == "flood":
        is_in_floodplain = rng.random() < 0.45
    elif cfg["category"] == "mixed":
        is_in_floodplain = rng.random() < 0.15
    else:
        is_in_floodplain = rng.random() < 0.05

    soil_type = rng.choice(SOIL_TYPES)
    drainage_class = rng.choice(DRAINAGE_CLASSES)

    return {
        "property_id": property_id,
        "address": address,
        "latitude": lat,
        "longitude": lon,
        "state": cfg["state"],
        "county": county,
        "zip_code": zip_code,
        "construction_type": construction_type,
        "elevation_m": elevation_m,
        "is_in_wildland_urban_interface": is_in_wui,
        "is_in_floodplain": is_in_floodplain,
        "soil_type": soil_type,
        "drainage_class": drainage_class,
    }


def generate_properties(seed: int = DEFAULT_SEED) -> List[Dict]:
    """
    Generate the full set of sample properties across all configured states.

    Args:
        seed: Random seed for reproducible generation (default: 42)

    Returns:
        List of property dicts, ordered by property_id (1..N)
    """
    rng = random.Random(seed)
    properties = []
    property_id = 1

    for cfg in STATE_CONFIGS:
        for _ in range(cfg["count"]):
            properties.append(_generate_one_property(rng, property_id, cfg))
            property_id += 1

    return properties


def save_to_json(properties: List[Dict], path: Path = JSON_OUTPUT_PATH) -> None:
    """Write properties to a JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(properties, f, indent=2)


def save_to_csv(properties: List[Dict], path: Path = CSV_OUTPUT_PATH) -> None:
    """Write properties to a CSV file (backup format)."""
    if not properties:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(properties[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(properties)


if __name__ == "__main__":
    print("=" * 60)
    print("Sample Property Generator - Task 7")
    print("=" * 60)
    print()

    properties = generate_properties()
    print(f"Generated {len(properties)} properties")

    save_to_json(properties)
    print(f"[OK] Saved JSON: {JSON_OUTPUT_PATH}")

    save_to_csv(properties)
    print(f"[OK] Saved CSV:  {CSV_OUTPUT_PATH}")

    print()
    print("Distribution by state:")
    print("-" * 60)
    counts = {}
    for p in properties:
        counts[p["state"]] = counts.get(p["state"], 0) + 1
    for state, count in sorted(counts.items()):
        print(f"  {state}: {count}")

    wui_count = sum(1 for p in properties if p["is_in_wildland_urban_interface"])
    flood_count = sum(1 for p in properties if p["is_in_floodplain"])
    print()
    print(f"Properties in WUI: {wui_count}")
    print(f"Properties in floodplain: {flood_count}")

    print()
    print("Sample property:")
    print("-" * 60)
    print(json.dumps(properties[0], indent=2))

    print()
    print("=" * 60)
    print("Generation complete!")
    print("=" * 60)
