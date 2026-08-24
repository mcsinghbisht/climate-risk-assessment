"""
Database Module - SQLite Database Management

Provides database initialization, connections, and migrations.
"""

from src.database.db import (
    get_db_connection,
    initialize_database,
    verify_database,
    drop_all_tables,
    DB_PATH,
    SCHEMA_VERSION,
)
from src.database.migrations import MigrationManager
from src.database.property_dao import PropertyDAO
from src.database.risk_dao import RiskDAO
from src.database.alert_dao import AlertDAO

__all__ = [
    "get_db_connection",
    "initialize_database",
    "verify_database",
    "drop_all_tables",
    "MigrationManager",
    "PropertyDAO",
    "RiskDAO",
    "AlertDAO",
    "DB_PATH",
    "SCHEMA_VERSION",
]
