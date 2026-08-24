"""
Pytest test suite for PropertyDAO (Task 9)

Run with: pytest tests/test_property_dao_pytest.py -v

Uses a temporary SQLite database (populated via the Task 7/8 generator and
loader) so these tests never touch or depend on data/climate_risk.db.
"""

import pytest

import src.database.db as db_module
from src.database.property_dao import PropertyDAO
from src.data_ingestion.property_generator import generate_properties, save_to_json
from src.data_ingestion.property_loader import load_all_properties


@pytest.fixture
def dao_with_data(tmp_path, monkeypatch):
    """Create a temp DB, schema, and 100 loaded properties; return a PropertyDAO."""
    db_path = tmp_path / "test_climate_risk.db"
    monkeypatch.setattr(db_module, "DB_PATH", db_path)

    conn = db_module.get_db_connection()
    conn.execute(db_module.get_schema()["properties"])
    conn.commit()
    conn.close()

    json_path = tmp_path / "props.json"
    save_to_json(generate_properties(), json_path)
    load_all_properties(json_path)

    return PropertyDAO()


class TestPropertyDAO:
    """Tests for each PropertyDAO method against a fully loaded dataset."""

    def test_count_properties_returns_100(self, dao_with_data):
        assert dao_with_data.count_properties() == 100

    def test_get_all_properties_returns_100_dicts(self, dao_with_data):
        properties = dao_with_data.get_all_properties()
        assert len(properties) == 100
        assert all(isinstance(p, dict) for p in properties)

    def test_get_all_properties_ordered_by_id(self, dao_with_data):
        properties = dao_with_data.get_all_properties()
        ids = [p["property_id"] for p in properties]
        assert ids == sorted(ids)

    def test_get_property_by_id_returns_correct_property(self, dao_with_data):
        prop = dao_with_data.get_property_by_id(1)
        assert prop is not None
        assert prop["property_id"] == 1
        assert prop["state"] == "CA"

    def test_get_property_by_id_returns_none_for_missing_id(self, dao_with_data):
        prop = dao_with_data.get_property_by_id(9999)
        assert prop is None

    def test_get_properties_by_state_ca(self, dao_with_data):
        ca_props = dao_with_data.get_properties_by_state("CA")
        assert len(ca_props) == 20
        assert all(p["state"] == "CA" for p in ca_props)

    def test_get_properties_by_state_returns_empty_for_unknown_state(self, dao_with_data):
        props = dao_with_data.get_properties_by_state("ZZ")
        assert props == []

    def test_get_properties_in_floodplain(self, dao_with_data):
        flood_props = dao_with_data.get_properties_in_floodplain()
        assert len(flood_props) == 21
        assert all(p["is_in_floodplain"] == 1 for p in flood_props)

    def test_get_properties_in_wui(self, dao_with_data):
        wui_props = dao_with_data.get_properties_in_wui()
        assert len(wui_props) == 28
        assert all(p["is_in_wildland_urban_interface"] == 1 for p in wui_props)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
