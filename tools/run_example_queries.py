#!/usr/bin/env python
"""
Run Example Database Queries

Demonstrates how to query the database.
"""

import sqlite3
from pathlib import Path

DB_PATH = Path("data/climate_risk.db")


def get_db_connection():
    """Get database connection."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def print_query_result(title, query):
    """Execute and print query results."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)
    print(f"\nQuery: {query}\n")
    print("-" * 80)

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()

        if not rows:
            print("No results found.")
        else:
            # Get column names
            columns = [description[0] for description in cursor.description]

            # Print header
            header_parts = []
            for col in columns:
                header_parts.append(f"{col[:20]:<20}")
            print(" | ".join(header_parts))
            print("-" * (len(" | ".join(header_parts))))

            # Print rows
            for row in rows:
                row_parts = []
                for col in columns:
                    value = str(row[col])[:20]
                    row_parts.append(f"{value:<20}")
                print(" | ".join(row_parts))

            print(f"\nTotal rows: {len(rows)}")

        conn.close()

    except Exception as e:
        print(f"[ERROR] {str(e)}")


def main():
    """Run example queries."""
    print("\n" + "=" * 80)
    print("  DATABASE EXAMPLE QUERIES")
    print("=" * 80)

    # Check if database exists
    if not DB_PATH.exists():
        print(f"\n[ERROR] Database not found at {DB_PATH}")
        print("Run 'python src/database/db.py' first to initialize.")
        return

    print(f"\nDatabase: {DB_PATH.absolute()}")
    print(f"File size: {DB_PATH.stat().st_size / 1024:.1f} KB")

    # Query 1: Show all tables
    print_query_result(
        "Query 1: List All Tables",
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    )

    # Query 2: Schema version
    print_query_result(
        "Query 2: Schema Version Information",
        "SELECT version, applied_at, description FROM schema_version"
    )

    # Query 3: Properties table info
    print_query_result(
        "Query 3: Properties Table - Row Count by State",
        """
SELECT state, COUNT(*) as property_count
FROM properties
GROUP BY state
ORDER BY property_count DESC
LIMIT 10
        """
    )

    # Query 4: Properties sample
    print_query_result(
        "Query 4: Sample Properties",
        """
SELECT property_id, address, latitude, longitude, state, is_in_floodplain
FROM properties
LIMIT 5
        """
    )

    # Query 5: Hazard data
    print_query_result(
        "Query 5: Hazard Data Sources",
        """
SELECT hazard_type, source, COUNT(*) as record_count
FROM hazard_data
GROUP BY hazard_type, source
        """
    )

    # Query 6: Risk assessments
    print_query_result(
        "Query 6: Risk Assessment Statistics",
        """
SELECT
    risk_level,
    COUNT(*) as count,
    ROUND(AVG(overall_risk_score), 2) as avg_score
FROM risk_assessments
GROUP BY risk_level
        """
    )

    # Query 7: Alerts
    print_query_result(
        "Query 7: Alert Summary",
        """
SELECT alert_level, risk_type, COUNT(*) as alert_count
FROM alerts
GROUP BY alert_level, risk_type
        """
    )

    # Query 8: Database structure
    print_query_result(
        "Query 8: Table Sizes",
        """
SELECT
    name as table_name,
    (SELECT COUNT(*) FROM sqlite_master) as total_tables
FROM sqlite_master
WHERE type='table' AND name NOT LIKE 'sqlite_%'
        """
    )

    print("\n" + "=" * 80)
    print("  END OF EXAMPLES")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
