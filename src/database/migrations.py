"""
Database Schema Migrations

Manages schema versioning and migrations for the SQLite database.
"""

from src.database.db import get_db_connection, SCHEMA_VERSION


class MigrationManager:
    """Manages database schema migrations and versioning."""

    def __init__(self):
        """Initialize migration manager."""
        self.current_version = SCHEMA_VERSION

    def get_current_version(self):
        """
        Get the current schema version from database.

        Returns:
            int: Current schema version, or None if not initialized
        """
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT version FROM schema_version ORDER BY id DESC LIMIT 1"
            )
            result = cursor.fetchone()
            conn.close()
            return result[0] if result else None
        except Exception:
            return None

    def is_up_to_date(self):
        """
        Check if database schema is up to date.

        Returns:
            bool: True if current version matches target version
        """
        db_version = self.get_current_version()
        return db_version == self.current_version

    def needs_migration(self):
        """
        Check if database needs migration.

        Returns:
            bool: True if database version is behind target version
        """
        db_version = self.get_current_version()
        if db_version is None:
            return False  # New database
        return db_version < self.current_version

    def record_migration(self, version, description):
        """
        Record a migration in the database.

        Args:
            version (int): Schema version number
            description (str): Description of the migration

        Returns:
            bool: True if successful
        """
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO schema_version (version, description)
                   VALUES (?, ?)""",
                (version, description)
            )
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error recording migration: {e}")
            return False


if __name__ == "__main__":
    manager = MigrationManager()
    current = manager.get_current_version()
    print(f"Current schema version in database: {current}")
    print(f"Target schema version: {manager.current_version}")
    print(f"Up to date: {manager.is_up_to_date()}")
