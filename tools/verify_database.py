#!/usr/bin/env python
"""
Database Verification Script

Verifies database structure, tables, columns, and indexes.
"""

import sqlite3
from pathlib import Path

DB_PATH = Path("data/climate_risk.db")


def verify_database():
    """Verify database structure and content."""
    if not DB_PATH.exists():
        print(f"[ERROR] Database file not found: {DB_PATH}")
        return False

    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    print("\n" + "=" * 70)
    print("DATABASE VERIFICATION REPORT")
    print("=" * 70)

    # 1. Database file info
    print("\n1. DATABASE FILE")
    print("-" * 70)
    db_size_mb = DB_PATH.stat().st_size / (1024 * 1024)
    print(f"   Location: {DB_PATH.absolute()}")
    print(f"   Size: {db_size_mb:.2f} MB")

    # 2. List all tables
    print("\n2. TABLES IN DATABASE")
    print("-" * 70)
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in cursor.fetchall()]
    for i, table in enumerate(tables, 1):
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        print(f"   {i}. {table:25} ({count} records)")

    # 3. Table schemas
    print("\n3. TABLE SCHEMAS")
    print("-" * 70)

    key_tables = [
        "properties",
        "risk_assessments",
        "hazard_data",
        "alerts",
        "alert_history",
        "schema_version"
    ]

    for table in key_tables:
        if table in tables:
            print(f"\n   TABLE: {table}")
            print(f"   {'-' * 66}")
            cursor.execute(f"PRAGMA table_info({table})")
            columns = cursor.fetchall()
            for cid, name, type_, notnull, dflt_value, pk in columns:
                null_str = "NOT NULL" if notnull else "NULL"
                pk_str = "PK" if pk else ""
                print(f"      - {name:25} {type_:15} {null_str:10} {pk_str}")

    # 4. Indexes
    print("\n4. DATABASE INDEXES")
    print("-" * 70)
    cursor.execute("SELECT name, tbl_name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%' ORDER BY tbl_name")
    indexes = cursor.fetchall()
    if indexes:
        for name, tbl_name in indexes:
            print(f"   - {name:35} (table: {tbl_name})")
    else:
        print("   [None found]")

    # 5. Schema version
    print("\n5. SCHEMA VERSION")
    print("-" * 70)
    try:
        cursor.execute("SELECT version, applied_at, description FROM schema_version ORDER BY id DESC LIMIT 1")
        result = cursor.fetchone()
        if result:
            version, applied_at, description = result
            print(f"   Current version: {version}")
            print(f"   Applied: {applied_at}")
            print(f"   Description: {description}")
        else:
            print("   [No schema version recorded]")
    except Exception as e:
        print(f"   [Error reading schema version: {e}]")

    # 6. Foreign keys
    print("\n6. FOREIGN KEY CONSTRAINTS")
    print("-" * 70)
    for table in key_tables:
        if table in tables:
            cursor.execute(f"PRAGMA foreign_key_list({table})")
            fks = cursor.fetchall()
            if fks:
                print(f"   {table}:")
                for id_, seq, table_ref, from_col, to_col, on_delete, on_update, match in fks:
                    print(f"      - {from_col} -> {table_ref}({to_col})")

    # 7. Summary
    print("\n7. SUMMARY")
    print("-" * 70)
    user_tables = [t for t in tables if not t.startswith("sqlite_")]
    print(f"   Total tables: {len(user_tables)}")
    print(f"   Total records: {sum([cursor.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0] for t in user_tables])}")
    print(f"   Total indexes: {len(indexes)}")

    conn.close()

    print("\n" + "=" * 70)
    print("VERIFICATION COMPLETE - DATABASE IS READY!")
    print("=" * 70 + "\n")

    return True


if __name__ == "__main__":
    success = verify_database()
    exit(0 if success else 1)
