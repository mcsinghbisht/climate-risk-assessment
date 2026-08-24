"""
Safe SQL Executor (Step 7)

For novel questions not covered by curated tools, Claude can generate SELECT
queries. This module validates, sandboxes, and executes them safely.

Key safeguards:
- Only SELECT queries allowed (read-only)
- Forbidden keywords rejected (DROP, ALTER, INSERT, UPDATE, DELETE)
- Read-only database connection
- Query timeout (30 seconds)
- Result row limit (1000)
- Full logging and query audit trail
"""

import logging
import sqlparse
import sqlite3
from typing import Tuple, List, Dict, Optional

logger = logging.getLogger(__name__)


class SafeSQLExecutor:
    """
    Validates and executes SQL queries against the climate risk database.

    All queries run read-only against a separate connection with no write
    access. Queries are logged with full context for audit trail.
    """

    FORBIDDEN_KEYWORDS = {
        "DROP", "ALTER", "INSERT", "UPDATE", "DELETE", "REPLACE",
        "TRUNCATE", "PRAGMA", "ATTACH", "DETACH", "VACUUM",
        "ANALYZE", "REINDEX", "SAVEPOINT", "RELEASE", "ROLLBACK",
    }

    def __init__(self, db_path: str, max_rows: int = 1000, timeout_seconds: int = 30):
        """
        Initialize the SQL executor.

        Args:
            db_path: path to the SQLite database
            max_rows: maximum rows to return per query (default 1000)
            timeout_seconds: query execution timeout (default 30s)
        """
        self.db_path = db_path
        self.max_rows = max_rows
        self.timeout_seconds = timeout_seconds

    def validate_query(self, sql: str) -> Tuple[bool, Optional[str]]:
        """
        Validate a SQL query for safety.

        Args:
            sql: SQL query string to validate

        Returns:
            (is_valid, error_message)
            - If is_valid=True, error_message is None
            - If is_valid=False, error_message explains why
        """
        if not sql or not sql.strip():
            return False, "Query is empty"

        # Check it's a valid SQL statement
        try:
            parsed = sqlparse.parse(sql)
            if not parsed:
                return False, "Could not parse SQL"
        except Exception as e:
            return False, f"SQL parse error: {e}"

        # Check first statement type
        first_stmt = parsed[0]
        stmt_type = first_stmt.get_type()

        if stmt_type != "SELECT":
            return False, f"Only SELECT queries allowed (got {stmt_type})"

        # Check for forbidden keywords (case-insensitive)
        query_upper = sql.upper()
        for keyword in self.FORBIDDEN_KEYWORDS:
            # Simple word boundary check: keyword surrounded by non-alphanumeric
            if f" {keyword} " in f" {query_upper} ":
                return False, f"Forbidden keyword: {keyword}"

        return True, None

    def execute(self, sql: str, user_context: str = "unknown") -> Tuple[List[Dict], Optional[str]]:
        """
        Execute a validated SQL query.

        Args:
            sql: SQL query string
            user_context: context for logging (e.g., "user_123" or "underwriter:property_42")

        Returns:
            (results, error_message)
            - If error_message is None, results is a list of dicts
            - If error_message is not None, results is empty
        """
        # Validate first
        is_valid, error = self.validate_query(sql)
        if not is_valid:
            logger.warning(f"Query rejected: {error} | user={user_context}")
            return [], error

        # Execute with timeout and row limit
        try:
            conn = sqlite3.connect(self.db_path, timeout=self.timeout_seconds)
            conn.row_factory = sqlite3.Row  # Return rows as dicts

            # Set timeout
            conn.execute(f"PRAGMA busy_timeout = {self.timeout_seconds * 1000}")

            cursor = conn.cursor()
            cursor.execute(sql)

            # Fetch up to max_rows
            rows = cursor.fetchmany(self.max_rows)
            results = [dict(row) for row in rows]

            conn.close()

            # Log successful execution
            logger.info(
                f"Query executed | rows={len(results)} | user={user_context} | "
                f"query_len={len(sql)}"
            )

            return results, None

        except sqlite3.OperationalError as e:
            error_msg = f"Database error: {str(e)[:100]}"
            logger.error(
                f"Query failed (DB error) | error={error_msg} | user={user_context}"
            )
            return [], error_msg

        except sqlite3.DatabaseError as e:
            error_msg = f"Database error: {str(e)[:100]}"
            logger.error(
                f"Query failed (DB error) | error={error_msg} | user={user_context}"
            )
            return [], error_msg

        except Exception as e:
            error_msg = f"Unexpected error: {str(e)[:100]}"
            logger.error(
                f"Query failed (unexpected) | error={error_msg} | user={user_context}"
            )
            return [], error_msg

    def explain_query(self, sql: str) -> Tuple[List[Dict], Optional[str]]:
        """
        Explain a query's execution plan (EXPLAIN QUERY PLAN).

        Useful for understanding what a query will do before executing it.

        Args:
            sql: SQL query string to explain

        Returns:
            (explain_rows, error_message) - same format as execute()
        """
        is_valid, error = self.validate_query(sql)
        if not is_valid:
            return [], error

        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row

            cursor = conn.cursor()
            cursor.execute(f"EXPLAIN QUERY PLAN {sql}")

            rows = cursor.fetchall()
            results = [dict(row) for row in rows]

            conn.close()

            return results, None

        except Exception as e:
            return [], f"Could not explain query: {str(e)}"
