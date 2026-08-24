"""
Pytest test suite for the sample property generator (Task 7)

Run with: pytest tests/test_property_generator_pytest.py -v
"""

import json
import pytest

from src.data_ingestion.property_generator import (
    generate_properties,
    JSON_OUTPUT_PATH,
    CSV_OUTPUT_PATH,
)
from src.utils import validate_property_data

REQUIRED_FIELDS = [
    "property_id", "address", "latitude", "longitude", "state", "county",
    "zip_code", "construction_type", "elevation_m",
    "is_in_wildland_urban_interface", "is_in_floodplain",
    "soil_type", "drainage_class",
]

WILDFIRE_STATES = {"CA", "AZ", "CO"}
FLOOD_STATES = {"LA", "TX", "FL"}


class TestPropertyGeneration:
    """Tests for generate_properties()."""

    def test_generates_exactly_100_properties(self):
        properties = generate_properties()
        assert len(properties) == 100

    def test_property_ids_are_sequential_and_unique(self):
        properties = generate_properties()
        ids = [p["property_id"] for p in properties]
        assert ids == list(range(1, 101))

    def test_all_required_fields_present(self):
        properties = generate_properties()
        for p in properties:
            for field in REQUIRED_FIELDS:
                assert field in p, f"Missing field {field} in property {p.get('property_id')}"

    def test_wildfire_states_present(self):
        properties = generate_properties()
        states = {p["state"] for p in properties}
        assert WILDFIRE_STATES.issubset(states)

    def test_flood_states_present(self):
        properties = generate_properties()
        states = {p["state"] for p in properties}
        assert FLOOD_STATES.issubset(states)

    def test_coordinates_are_valid(self):
        properties = generate_properties()
        for p in properties:
            assert -90 <= p["latitude"] <= 90
            assert -180 <= p["longitude"] <= 180

    def test_construction_type_is_valid(self):
        properties = generate_properties()
        valid = {"wood", "masonry", "mixed"}
        for p in properties:
            assert p["construction_type"] in valid

    def test_generation_is_reproducible_with_same_seed(self):
        props1 = generate_properties(seed=42)
        props2 = generate_properties(seed=42)
        assert props1 == props2

    def test_different_seeds_produce_different_data(self):
        props1 = generate_properties(seed=1)
        props2 = generate_properties(seed=2)
        assert props1 != props2

    def test_each_property_passes_shared_validation(self):
        """Cross-check generator output against Task 4's validate_property_data()."""
        properties = generate_properties()
        for p in properties:
            is_valid, errors = validate_property_data(p)
            assert is_valid, f"Property {p['property_id']} failed validation: {errors}"


class TestOutputFiles:
    """Tests for the generated JSON/CSV artifacts on disk."""

    def test_json_file_exists(self):
        assert JSON_OUTPUT_PATH.exists()

    def test_csv_file_exists(self):
        assert CSV_OUTPUT_PATH.exists()

    def test_json_file_is_valid_and_has_100_records(self):
        data = json.loads(JSON_OUTPUT_PATH.read_text(encoding="utf-8"))
        assert len(data) == 100

    def test_csv_file_has_header_and_100_rows(self):
        lines = CSV_OUTPUT_PATH.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 101  # header + 100 rows


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
