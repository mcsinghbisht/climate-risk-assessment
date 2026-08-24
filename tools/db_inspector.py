#!/usr/bin/env python
"""
Database Inspector Tool

Interactive tool to inspect database, run queries, and view results.
Usage: python db_inspector.py
"""

import sqlite3
from pathlib import Path
import json
from datetime import datetime

DB_PATH = Path("data/climate_risk.db")


def get_db_connection():
    """Get database connection."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def print_header(text):
    """Print a formatted header."""
    print("\n" + "=" * 80)
    print(f"  {text}")
    print("=" * 80 + "\n")


def print_separator():
    """Print a separator line."""
    print("-" * 80)


def format_row(row):
    """Format a database row for display."""
    if row is None:
        return "None"
    return str(row)


def show_database_info():
    """Show database file information."""
    if not DB_PATH.exists():
        print(f"[ERROR] Database not found at {DB_PATH}")
        return

    size_mb = DB_PATH.stat().st_size / (1024 * 1024)
    print_header("DATABASE INFORMATION")
    print(f"Path:     {DB_PATH.absolute()}")
    print(f"Size:     {size_mb:.3f} MB")
    print(f"Exists:   Yes")


def show_tables():
    """List all tables in database."""
    conn = get_db_connection()
    cursor = conn.cursor()

    print_header("DATABASE TABLES")
    cursor.execute(
        "SELECT name, type FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    tables = cursor.fetchall()

    if not tables:
        print("No tables found.")
        conn.close()
        return

    print(f"{'Table Name':<30} {'Type':<10} {'Row Count':<10}")
    print_separator()

    for name, table_type in tables:
        if not name.startswith("sqlite_"):
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {name}")
                count = cursor.fetchone()[0]
                print(f"{name:<30} {table_type:<10} {count:<10}")
            except Exception as e:
                print(f"{name:<30} {table_type:<10} [Error: {str(e)}]")

    conn.close()


def show_table_schema(table_name):
    """Show schema for a specific table."""
    conn = get_db_connection()
    cursor = conn.cursor()

    print_header(f"TABLE SCHEMA: {table_name}")

    try:
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = cursor.fetchall()

        if not columns:
            print(f"Table '{table_name}' not found.")
            conn.close()
            return

        print(f"{'Column':<30} {'Type':<15} {'Null':<8} {'PK':<4}")
        print_separator()

        for cid, name, type_, notnull, dflt_value, pk in columns:
            null_str = "NO" if notnull else "YES"
            pk_str = "YES" if pk else "NO"
            print(f"{name:<30} {type_:<15} {null_str:<8} {pk_str:<4}")

        # Show row count
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cursor.fetchone()[0]
        print_separator()
        print(f"Total rows in table: {count}")

    except Exception as e:
        print(f"Error: {str(e)}")

    conn.close()


def run_query(query):
    """Execute a SQL query and display results."""
    if not query.strip():
        print("No query provided.")
        return

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Execute query
        cursor.execute(query)

        # Check if it's a SELECT query
        if query.strip().upper().startswith("SELECT"):
            # Fetch results
            rows = cursor.fetchall()

            if not rows:
                print("No results found.")
            else:
                # Get column names
                columns = [description[0] for description in cursor.description]

                # Print header
                header = " | ".join(f"{col:<20}" for col in columns)
                print(header)
                print("-" * len(header))

                # Print rows
                for row in rows:
                    row_str = " | ".join(
                        f"{str(row[col]):<20}" for col in columns
                    )
                    print(row_str)

                print(f"\nTotal rows: {len(rows)}")

        else:
            # Non-SELECT query (INSERT, UPDATE, DELETE, etc.)
            conn.commit()
            print(f"Query executed successfully. Rows affected: {cursor.rowcount}")

    except Exception as e:
        print(f"Error executing query: {str(e)}")

    conn.close()


def show_menu():
    """Display interactive menu."""
    while True:
        print("\n" + "=" * 80)
        print("  DATABASE INSPECTOR - MAIN MENU")
        print("=" * 80)
        print("\n1. Show database info")
        print("2. List all tables")
        print("3. Show table schema")
        print("4. Run custom SQL query")
        print("5. Run example queries")
        print("6. Exit")
        print()

        choice = input("Select option (1-6): ").strip()

        if choice == "1":
            show_database_info()

        elif choice == "2":
            show_tables()

        elif choice == "3":
            table_name = input("Enter table name: ").strip()
            if table_name:
                show_table_schema(table_name)

        elif choice == "4":
            print("\nEnter SQL query (or 'exit' to return to menu):")
            query = input(">>> ").strip()
            if query.lower() != "exit" and query:
                print_header(f"QUERY RESULTS")
                print(f"Query: {query}\n")
                run_query(query)

        elif choice == "5":
            show_example_queries()

        elif choice == "6":
            print("\nGoodbye!")
            break

        else:
            print("Invalid option. Please try again.")


def show_example_queries():
    """Show example queries to run."""
    print_header("EXAMPLE QUERIES")

    examples = {
        "1": {
            "description": "Show all tables and row counts",
            "query": "SELECT name, (SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=sqlite_master.name) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';"
        },
        "2": {
            "description": "Count properties by state",
            "query": "SELECT state, COUNT(*) as count FROM properties GROUP BY state ORDER BY count DESC LIMIT 10;"
        },
        "3": {
            "description": "Show all properties",
            "query": "SELECT property_id, address, latitude, longitude, state FROM properties LIMIT 10;"
        },
        "4": {
            "description": "Show properties in floodplain",
            "query": "SELECT property_id, address, is_in_floodplain, is_in_wildland_urban_interface FROM properties WHERE is_in_floodplain = 1 LIMIT 10;"
        },
        "5": {
            "description": "Show latest risk assessments",
            "query": "SELECT ra.assessment_id, ra.property_id, ra.assessment_timestamp, ra.overall_risk_score, ra.risk_level FROM risk_assessments ra ORDER BY ra.created_at DESC LIMIT 10;"
        },
        "6": {
            "description": "Show all hazard data",
            "query": "SELECT hazard_id, hazard_type, source, value, observation_timestamp FROM hazard_data ORDER BY ingested_timestamp DESC LIMIT 10;"
        },
        "7": {
            "description": "Show all alerts",
            "query": "SELECT alert_id, property_id, risk_type, risk_score, alert_level, triggered_at FROM alerts ORDER BY triggered_at DESC LIMIT 10;"
        },
        "8": {
            "description": "Show schema version",
            "query": "SELECT version, applied_at, description FROM schema_version;"
        }
    }

    for num, example in examples.items():
        print(f"\n{num}. {example['description']}")
        print(f"   Query: {example['query']}")

    print("\n" + "-" * 80)
    choice = input("\nRun example (enter number 1-8 or 'skip'): ").strip()

    if choice in examples:
        print_header(f"EXAMPLE {choice}: {examples[choice]['description']}")
        print(f"Query: {examples[choice]['query']}\n")
        run_query(examples[choice]["query"])
    elif choice.lower() != "skip":
        print("Invalid choice.")


if __name__ == "__main__":
    # Check if database exists
    if not DB_PATH.exists():
        print(f"[ERROR] Database not found at {DB_PATH}")
        print("Run 'python src/database/db.py' to initialize the database first.")
        exit(1)

    print("\n" + "=" * 80)
    print("  CLIMATE RISK ASSESSMENT - DATABASE INSPECTOR")
    print("=" * 80)
    print(f"  Database: {DB_PATH.absolute()}\n")

    # Show initial info
    show_database_info()
    show_tables()

    # Start interactive menu
    show_menu()
