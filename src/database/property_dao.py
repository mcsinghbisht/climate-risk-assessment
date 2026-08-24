"""
Property Data Access Object (DAO)

The single, clean interface for reading property data. All other modules
(risk scoring, portfolio aggregation, alerts, etc.) should go through
PropertyDAO instead of writing raw SQL against the `properties` table -
this keeps the database layer swappable and the query logic in one place.
"""

import sqlite3
from typing import Dict, List, Optional

from src.database.db import get_db_connection


def _row_to_dict(row: sqlite3.Row) -> Dict:
    """Convert a sqlite3.Row into a plain dict."""
    return dict(row)


class PropertyDAO:
    """Read-only data access layer for the `properties` table."""

    def get_all_properties(self) -> List[Dict]:
        """
        Get every property in the database.

        Returns:
            List of property dicts, ordered by property_id
        """
        conn = get_db_connection()
        try:
            cursor = conn.execute("SELECT * FROM properties ORDER BY property_id")
            return [_row_to_dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_property_by_id(self, property_id: int) -> Optional[Dict]:
        """
        Get a single property by its ID.

        Args:
            property_id: The property's primary key

        Returns:
            Property dict, or None if not found
        """
        conn = get_db_connection()
        try:
            cursor = conn.execute(
                "SELECT * FROM properties WHERE property_id = ?", (property_id,)
            )
            row = cursor.fetchone()
            return _row_to_dict(row) if row else None
        finally:
            conn.close()

    def get_properties_by_state(self, state: str) -> List[Dict]:
        """
        Get all properties in a given state.

        Args:
            state: Two-letter state code (e.g., "CA")

        Returns:
            List of property dicts, ordered by property_id
        """
        conn = get_db_connection()
        try:
            cursor = conn.execute(
                "SELECT * FROM properties WHERE state = ? ORDER BY property_id", (state,)
            )
            return [_row_to_dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_properties_in_floodplain(self) -> List[Dict]:
        """
        Get all properties flagged as being in a FEMA floodplain.

        Returns:
            List of property dicts, ordered by property_id
        """
        conn = get_db_connection()
        try:
            cursor = conn.execute(
                "SELECT * FROM properties WHERE is_in_floodplain = 1 ORDER BY property_id"
            )
            return [_row_to_dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_properties_in_wui(self) -> List[Dict]:
        """
        Get all properties flagged as being in the Wildland-Urban Interface.

        Returns:
            List of property dicts, ordered by property_id
        """
        conn = get_db_connection()
        try:
            cursor = conn.execute(
                "SELECT * FROM properties WHERE is_in_wildland_urban_interface = 1 "
                "ORDER BY property_id"
            )
            return [_row_to_dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def count_properties(self) -> int:
        """
        Get the total number of properties in the database.

        Returns:
            Total property count
        """
        conn = get_db_connection()
        try:
            cursor = conn.execute("SELECT COUNT(*) FROM properties")
            return cursor.fetchone()[0]
        finally:
            conn.close()


if __name__ == "__main__":
    print("=" * 60)
    print("Property DAO Test")
    print("=" * 60)
    print()

    dao = PropertyDAO()

    count = dao.count_properties()
    print(f"Total properties: {count}")

    all_props = dao.get_all_properties()
    print(f"get_all_properties() returned: {len(all_props)} records")

    first = dao.get_property_by_id(1)
    print(f"Property 1: {first['address'] if first else 'NOT FOUND'}")

    ca_props = dao.get_properties_by_state("CA")
    print(f"Properties in CA: {len(ca_props)}")

    flood_props = dao.get_properties_in_floodplain()
    print(f"Properties in floodplain: {len(flood_props)}")

    wui_props = dao.get_properties_in_wui()
    print(f"Properties in WUI: {len(wui_props)}")

    print()
    print("=" * 60)
    print("All queries executed successfully!")
    print("=" * 60)
