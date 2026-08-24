"""
Property Loader

Reads generated sample properties (data/sample_properties.json) and loads
them into the `properties` table in SQLite. Validates each record before
insertion and upserts on property_id so the loader can be re-run safely
without creating duplicates.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List

from src.config import setup_logging
from src.database import get_db_connection
from src.utils import validate_property_data, get_utc_now
from src.data_ingestion.property_generator import JSON_OUTPUT_PATH

logger = logging.getLogger(__name__)


def load_properties_from_json(path: Path = JSON_OUTPUT_PATH) -> List[Dict]:
    """
    Read property records from a JSON file.

    Args:
        path: Path to the JSON file (default: data/sample_properties.json)

    Returns:
        List of property dicts

    Raises:
        FileNotFoundError: If the JSON file does not exist
    """
    if not path.exists():
        raise FileNotFoundError(
            f"Sample properties file not found: {path}. "
            f"Run src/data_ingestion/property_generator.py first."
        )

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def upsert_property(conn, prop: Dict) -> None:
    """
    Insert a property, or update it in place if its property_id already
    exists. Preserves created_at across re-runs; always refreshes updated_at.

    Args:
        conn: SQLite connection
        prop: Validated property dict
    """
    now = get_utc_now().isoformat()

    conn.execute(
        """
        INSERT INTO properties (
            property_id, address, latitude, longitude, state, county,
            zip_code, construction_type, elevation_m,
            is_in_wildland_urban_interface, is_in_floodplain,
            soil_type, drainage_class, created_at, updated_at
        ) VALUES (
            :property_id, :address, :latitude, :longitude, :state, :county,
            :zip_code, :construction_type, :elevation_m,
            :is_in_wildland_urban_interface, :is_in_floodplain,
            :soil_type, :drainage_class, :created_at, :updated_at
        )
        ON CONFLICT(property_id) DO UPDATE SET
            address = excluded.address,
            latitude = excluded.latitude,
            longitude = excluded.longitude,
            state = excluded.state,
            county = excluded.county,
            zip_code = excluded.zip_code,
            construction_type = excluded.construction_type,
            elevation_m = excluded.elevation_m,
            is_in_wildland_urban_interface = excluded.is_in_wildland_urban_interface,
            is_in_floodplain = excluded.is_in_floodplain,
            soil_type = excluded.soil_type,
            drainage_class = excluded.drainage_class,
            updated_at = excluded.updated_at
        """,
        {**prop, "created_at": now, "updated_at": now},
    )


def load_all_properties(json_path: Path = JSON_OUTPUT_PATH) -> Dict:
    """
    Load all properties from the JSON file into the database.

    Validates every record before insertion; invalid records are skipped
    and logged rather than aborting the whole load.

    Args:
        json_path: Path to the JSON file to load

    Returns:
        Summary dict: {loaded, failed, total, errors}
    """
    properties = load_properties_from_json(json_path)
    logger.info("Loaded %d property records from %s", len(properties), json_path)

    conn = get_db_connection()
    loaded = 0
    failed = 0
    errors = []

    try:
        for prop in properties:
            is_valid, validation_errors = validate_property_data(prop)
            if not is_valid:
                failed += 1
                msg = f"property_id={prop.get('property_id')}: {validation_errors}"
                errors.append(msg)
                logger.warning("Skipping invalid property: %s", msg)
                continue

            try:
                upsert_property(conn, prop)
                loaded += 1
            except Exception as e:
                failed += 1
                msg = f"property_id={prop.get('property_id')}: {e}"
                errors.append(msg)
                logger.error("Failed to insert property: %s", msg)

        conn.commit()
    finally:
        conn.close()

    summary = {
        "total": len(properties),
        "loaded": loaded,
        "failed": failed,
        "errors": errors,
    }
    logger.info("Property load complete: %d loaded, %d failed (of %d total)",
                loaded, failed, len(properties))
    return summary


if __name__ == "__main__":
    setup_logging()

    print("=" * 60)
    print("Property Loader - Task 8")
    print("=" * 60)
    print()

    summary = load_all_properties()

    print(f"Total records read:  {summary['total']}")
    print(f"Successfully loaded: {summary['loaded']}")
    print(f"Failed/skipped:      {summary['failed']}")

    if summary["errors"]:
        print()
        print("Errors:")
        for err in summary["errors"]:
            print(f"  - {err}")

    print()
    print("=" * 60)
    if summary["failed"] == 0:
        print("SUCCESS: All properties loaded!")
    else:
        print("COMPLETED WITH ERRORS - see above")
    print("=" * 60)
