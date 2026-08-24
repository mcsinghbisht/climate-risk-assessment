"""
Pytest test suite for the property loader (Task 8)

Run with: pytest tests/test_property_loader_pytest.py -v

Note: these tests operate on a temporary SQLite database (not
data/climate_risk.db) so they never interfere with the real dataset.
"""

import sqlite3
import pytest

import src.database.db as db_module
from src.data_ingestion.property_loader import upsert_property, load_all_properties
from src.data_ingestion.property_generator import generate_properties, save_to_json


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """Create a fresh temporary database with the properties schema."""
    db_path = tmp_path / "test_climate_risk.db"
    monkeypatch.setattr(db_module, "DB_PATH", db_path)

    conn = db_module.get_db_connection()
    conn.execute(db_module.get_schema()["properties"])
    conn.commit()
    conn.close()

    return db_path


class TestUpsertProperty:
    """Tests for the upsert_property() function directly."""

    def test_insert_new_property(self, temp_db):
        conn = db_module.get_db_connection()
        prop = generate_properties()[0]
        upsert_property(conn, prop)
        conn.commit()

        cursor = conn.execute("SELECT COUNT(*) FROM properties")
        assert cursor.fetchone()[0] == 1
        conn.close()

    def test_upsert_same_property_id_does_not_duplicate(self, temp_db):
        conn = db_module.get_db_connection()
        prop = generate_properties()[0]

        upsert_property(conn, prop)
        upsert_property(conn, prop)  # same property_id again
        conn.commit()

        cursor = conn.execute("SELECT COUNT(*) FROM properties")
        assert cursor.fetchone()[0] == 1
        conn.close()

    def test_upsert_updates_changed_fields(self, temp_db):
        conn = db_module.get_db_connection()
        prop = generate_properties()[0]
        upsert_property(conn, prop)
        conn.commit()

        updated_prop = dict(prop)
        updated_prop["state"] = "ZZ"
        upsert_property(conn, updated_prop)
        conn.commit()

        cursor = conn.execute(
            "SELECT state FROM properties WHERE property_id = ?", (prop["property_id"],)
        )
        assert cursor.fetchone()[0] == "ZZ"
        conn.close()

    def test_created_at_preserved_across_upsert(self, temp_db):
        conn = db_module.get_db_connection()
        prop = generate_properties()[0]

        upsert_property(conn, prop)
        conn.commit()
        cursor = conn.execute(
            "SELECT created_at FROM properties WHERE property_id = ?", (prop["property_id"],)
        )
        first_created_at = cursor.fetchone()[0]

        upsert_property(conn, prop)  # re-run
        conn.commit()
        cursor = conn.execute(
            "SELECT created_at FROM properties WHERE property_id = ?", (prop["property_id"],)
        )
        second_created_at = cursor.fetchone()[0]

        assert first_created_at == second_created_at
        conn.close()


class TestLoadAllProperties:
    """Tests for the full load_all_properties() pipeline."""

    def test_loads_all_100_properties(self, temp_db, tmp_path):
        json_path = tmp_path / "props.json"
        save_to_json(generate_properties(), json_path)

        summary = load_all_properties(json_path)

        assert summary["total"] == 100
        assert summary["loaded"] == 100
        assert summary["failed"] == 0
        assert summary["errors"] == []

    def test_database_contains_100_rows_after_load(self, temp_db, tmp_path):
        json_path = tmp_path / "props.json"
        save_to_json(generate_properties(), json_path)
        load_all_properties(json_path)

        conn = db_module.get_db_connection()
        cursor = conn.execute("SELECT COUNT(*) FROM properties")
        assert cursor.fetchone()[0] == 100
        conn.close()

    def test_invalid_property_is_skipped_not_fatal(self, temp_db, tmp_path):
        properties = generate_properties()
        properties[0] = {**properties[0], "latitude": 999}  # invalid coordinate

        json_path = tmp_path / "props.json"
        save_to_json(properties, json_path)

        summary = load_all_properties(json_path)

        assert summary["total"] == 100
        assert summary["loaded"] == 99
        assert summary["failed"] == 1
        assert len(summary["errors"]) == 1

    def test_rerun_is_idempotent(self, temp_db, tmp_path):
        json_path = tmp_path / "props.json"
        save_to_json(generate_properties(), json_path)

        load_all_properties(json_path)
        load_all_properties(json_path)

        conn = db_module.get_db_connection()
        cursor = conn.execute("SELECT COUNT(*) FROM properties")
        assert cursor.fetchone()[0] == 100
        conn.close()

    def test_missing_file_raises_file_not_found(self, temp_db, tmp_path):
        missing_path = tmp_path / "does_not_exist.json"
        with pytest.raises(FileNotFoundError):
            load_all_properties(missing_path)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
