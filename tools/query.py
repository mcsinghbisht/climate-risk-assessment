#!/usr/bin/env python
"""
Quick Query Runner

Run SQL queries from command line.
Usage: python query.py "SELECT * FROM properties LIMIT 5"
"""

import sqlite3
import sys
from pathlib import Path

DB_PATH = Path("data/climate_risk.db")


def run_query(sql_query):
    """Execute and display query results."""
    if not DB_PATH.exists():
        print(f"[ERROR] Database not found at {DB_PATH}")
        return False

    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Execute query
        cursor.execute(sql_query)

        # Check if SELECT query
        if sql_query.strip().upper().startswith("SELECT"):
            rows = cursor.fetchall()

            if not rows:
                print("No results found.")
            else:
                # Get column names
                columns = [description[0] for description in cursor.description]

                # Print header
                print("\n" + "=" * 100)
                header_parts = [f"{col:<25}" for col in columns]
                print(" | ".join(header_parts))
                print("-" * 100)

                # Print rows
                for row in rows:
                    row_parts = [f"{str(row[col])[:25]:<25}" for col in columns]
                    print(" | ".join(row_parts))

                print("-" * 100)
                print(f"Total rows: {len(rows)}\n")
        else:
            # Non-SELECT
            conn.commit()
            print(f"Query executed. Rows affected: {cursor.rowcount}")

        conn.close()
        return True

    except Exception as e:
        print(f"[ERROR] {str(e)}")
        return False


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("""
Quick Query Runner
==================

Usage: python query.py "SELECT * FROM table"

Examples:
  python query.py "SELECT COUNT(*) FROM properties"
  python query.py "SELECT * FROM schema_version"
  python query.py "SELECT name FROM sqlite_master WHERE type='table'"
  python query.py "SELECT * FROM properties LIMIT 5"

Interactive Mode (no arguments):
  python query.py
  (then enter SQL queries)
        """)

        # Interactive mode
        print("\nEntering interactive mode. Type 'exit' to quit.\n")
        while True:
            try:
                query = input("SQL> ").strip()
                if query.lower() == "exit":
                    print("Goodbye!")
                    break
                if query:
                    run_query(query)
            except KeyboardInterrupt:
                print("\nGoodbye!")
                break
    else:
        # Command-line mode
        query = " ".join(sys.argv[1:])
        run_query(query)
