"""
SQLite Database Setup and Management

Creates and initializes the SQLite database with all required tables
for the Climate Risk Assessment system.
"""

import sqlite3
import os
import json
from datetime import datetime
from pathlib import Path

# Database location
DB_PATH = Path(__file__).parent.parent.parent / "data" / "climate_risk.db"
SCHEMA_VERSION = 1


def get_db_connection():
    """
    Get a connection to the SQLite database.

    Returns:
        sqlite3.Connection: Database connection with row factory
    """
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def get_schema():
    """
    Get the complete database schema.

    Returns:
        dict: Dictionary with table names and their CREATE TABLE statements
    """
    schema = {
        "schema_version": """
            CREATE TABLE IF NOT EXISTS schema_version (
                id INTEGER PRIMARY KEY,
                version INTEGER NOT NULL,
                applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                description TEXT
            )
        """,

        "properties": """
            CREATE TABLE IF NOT EXISTS properties (
                property_id INTEGER PRIMARY KEY AUTOINCREMENT,
                address TEXT NOT NULL,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                state TEXT,
                county TEXT,
                zip_code TEXT,
                construction_type TEXT,
                elevation_m REAL,
                is_in_wildland_urban_interface BOOLEAN DEFAULT 0,
                is_in_floodplain BOOLEAN DEFAULT 0,
                soil_type TEXT,
                drainage_class TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                CHECK (latitude >= -90 AND latitude <= 90),
                CHECK (longitude >= -180 AND longitude <= 180)
            )
        """,

        "risk_assessments": """
            CREATE TABLE IF NOT EXISTS risk_assessments (
                assessment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                property_id INTEGER NOT NULL,
                assessment_timestamp TIMESTAMP NOT NULL,
                wildfire_risk_score REAL,
                wildfire_factors TEXT,
                flood_risk_score REAL,
                flood_factors TEXT,
                overall_risk_score REAL,
                risk_level TEXT CHECK (risk_level IN ('low', 'medium', 'high', 'critical')),
                alerts_triggered TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (property_id) REFERENCES properties(property_id),
                CHECK (wildfire_risk_score IS NULL OR (wildfire_risk_score >= 0 AND wildfire_risk_score <= 100)),
                CHECK (flood_risk_score IS NULL OR (flood_risk_score >= 0 AND flood_risk_score <= 100)),
                CHECK (overall_risk_score IS NULL OR (overall_risk_score >= 0 AND overall_risk_score <= 100))
            )
        """,

        "hazard_data": """
            CREATE TABLE IF NOT EXISTS hazard_data (
                hazard_id INTEGER PRIMARY KEY AUTOINCREMENT,
                hazard_type TEXT NOT NULL,
                source TEXT NOT NULL,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                value REAL,
                confidence REAL DEFAULT 1.0,
                observation_timestamp TIMESTAMP NOT NULL,
                ingested_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                raw_data TEXT,
                CHECK (latitude >= -90 AND latitude <= 90),
                CHECK (longitude >= -180 AND longitude <= 180),
                CHECK (confidence >= 0 AND confidence <= 1)
            )
        """,

        "alerts": """
            -- property_id is nullable: portfolio-level alerts (Task 27,
            -- risk_type='portfolio_high_risk_pct') aren't about one property.
            CREATE TABLE IF NOT EXISTS alerts (
                alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
                property_id INTEGER,
                risk_type TEXT NOT NULL,
                risk_score REAL,
                threshold_exceeded REAL,
                alert_level TEXT CHECK (alert_level IN ('warning', 'critical')),
                message TEXT,
                triggered_at TIMESTAMP NOT NULL,
                acknowledged_at TIMESTAMP,
                status TEXT CHECK (status IN ('active', 'acknowledged', 'stale', 'resolved')) DEFAULT 'active',
                resolved_at TIMESTAMP,
                last_notified_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (property_id) REFERENCES properties(property_id),
                CHECK (risk_score >= 0 AND risk_score <= 100)
            )
        """,

        "alert_history": """
            CREATE TABLE IF NOT EXISTS alert_history (
                history_id INTEGER PRIMARY KEY AUTOINCREMENT,
                alert_id INTEGER NOT NULL,
                old_status TEXT,
                new_status TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (alert_id) REFERENCES alerts(alert_id)
            )
        """
    }
    return schema


def create_indexes(conn):
    """Create indexes for common queries."""
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_properties_state ON properties(state)",
        "CREATE INDEX IF NOT EXISTS idx_properties_county ON properties(county)",
        "CREATE INDEX IF NOT EXISTS idx_properties_coords ON properties(latitude, longitude)",
        "CREATE INDEX IF NOT EXISTS idx_risk_property ON risk_assessments(property_id)",
        "CREATE INDEX IF NOT EXISTS idx_risk_timestamp ON risk_assessments(assessment_timestamp)",
        "CREATE INDEX IF NOT EXISTS idx_risk_level ON risk_assessments(risk_level)",
        "CREATE INDEX IF NOT EXISTS idx_hazard_type ON hazard_data(hazard_type, source)",
        "CREATE INDEX IF NOT EXISTS idx_hazard_coords ON hazard_data(latitude, longitude)",
        "CREATE INDEX IF NOT EXISTS idx_hazard_timestamp ON hazard_data(ingested_timestamp)",
        "CREATE INDEX IF NOT EXISTS idx_alerts_property ON alerts(property_id)",
        "CREATE INDEX IF NOT EXISTS idx_alerts_timestamp ON alerts(triggered_at)",
    ]

    cursor = conn.cursor()
    for index_sql in indexes:
        cursor.execute(index_sql)
    conn.commit()


def initialize_database():
    """
    Initialize the SQLite database with all tables and indexes.

    Returns:
        tuple: (success: bool, message: str)
    """
    try:
        # Ensure data directory exists
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)

        # Connect to database (creates file if doesn't exist)
        conn = get_db_connection()
        cursor = conn.cursor()

        # Create all tables
        schema = get_schema()
        for table_name, create_sql in schema.items():
            cursor.execute(create_sql)
            print(f"[OK] Table '{table_name}' ready")

        # Record schema version
        cursor.execute("SELECT COUNT(*) FROM schema_version")
        if cursor.fetchone()[0] == 0:
            cursor.execute(
                "INSERT INTO schema_version (version, description) VALUES (?, ?)",
                (SCHEMA_VERSION, f"Initial schema version {SCHEMA_VERSION}")
            )
            print(f"[OK] Schema version {SCHEMA_VERSION} recorded")

        # Create indexes
        create_indexes(conn)
        print("[OK] Database indexes created")

        conn.commit()
        conn.close()

        return True, f"Database initialized successfully at {DB_PATH}"

    except Exception as e:
        return False, f"Error initializing database: {str(e)}"


def drop_all_tables():
    """
    Drop all tables (for testing/cleanup only).

    Returns:
        tuple: (success: bool, message: str)
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        tables = [
            "alert_history",
            "alerts",
            "hazard_data",
            "risk_assessments",
            "properties",
            "schema_version"
        ]

        for table in tables:
            cursor.execute(f"DROP TABLE IF EXISTS {table}")
            print(f"[OK] Dropped table '{table}'")

        conn.commit()
        conn.close()

        return True, "All tables dropped successfully"

    except Exception as e:
        return False, f"Error dropping tables: {str(e)}"


def verify_database():
    """
    Verify database is properly set up.

    Returns:
        tuple: (success: bool, details: dict)
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get list of tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]

        # Get schema version
        cursor.execute("SELECT version FROM schema_version ORDER BY id DESC LIMIT 1")
        version_row = cursor.fetchone()
        version = version_row[0] if version_row else None

        # Count records in each table
        counts = {}
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            counts[table] = cursor.fetchone()[0]

        conn.close()

        details = {
            "tables": tables,
            "schema_version": version,
            "record_counts": counts,
            "db_path": str(DB_PATH),
            "db_exists": DB_PATH.exists(),
            "db_size_mb": DB_PATH.stat().st_size / (1024 * 1024) if DB_PATH.exists() else 0
        }

        return True, details

    except Exception as e:
        return False, {"error": str(e)}


if __name__ == "__main__":
    print("=" * 60)
    print("Climate Risk Assessment - Database Initialization")
    print("=" * 60)
    print()

    # Initialize database
    print("Step 1: Creating database and tables...")
    print("-" * 60)
    success, message = initialize_database()
    print(message)
    print()

    if success:
        # Verify database
        print("Step 2: Verifying database...")
        print("-" * 60)
        success, details = verify_database()

        if success:
            print(f"[OK] Database location: {details['db_path']}")
            print(f"[OK] Database size: {details['db_size_mb']:.2f} MB")
            print(f"[OK] Schema version: {details['schema_version']}")
            print(f"[OK] Tables created: {len(details['tables'])}")
            print()
            print("Tables in database:")
            for table, count in details['record_counts'].items():
                print(f"  - {table}: {count} records")
            print()
            print("=" * 60)
            print("SUCCESS: Database is ready!")
            print("=" * 60)
        else:
            print(f"[FAILED] Verification failed: {details.get('error')}")
    else:
        print(f"[FAILED] Initialization failed")
