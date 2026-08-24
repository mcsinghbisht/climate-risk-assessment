# Database Usage Guide

How to inspect, query, and interact with the SQLite database.

---

## Quick Start

### Option 1: Interactive Inspector (Recommended for exploration)
```bash
python db_inspector.py
```

This launches an interactive menu where you can:
- View database info
- List all tables
- View table schemas
- Run custom SQL queries
- Run pre-built example queries

### Option 2: Run Example Queries
```bash
python run_example_queries.py
```

Shows 8 common queries with results:
- List all tables
- Schema version info
- Properties by state
- Sample properties
- Hazard data sources
- Risk statistics
- Alerts summary
- Table sizes

### Option 3: Python Direct Access
```python
from src.database import get_db_connection

conn = get_db_connection()
cursor = conn.cursor()
cursor.execute("SELECT COUNT(*) FROM properties")
count = cursor.fetchone()[0]
print(f"Total properties: {count}")
conn.close()
```

---

## Database Inspector - Interactive Menu

```
1. Show database info
   - File location
   - File size
   - Existence check

2. List all tables
   - All tables with row counts
   - Quick overview

3. Show table schema
   - Column names, types
   - NOT NULL constraints
   - Primary keys
   - Row count

4. Run custom SQL query
   - Enter any SELECT/INSERT/UPDATE/DELETE
   - View formatted results

5. Run example queries
   - Pre-built common queries
   - Choose which one to execute

6. Exit
```

---

## Common SQL Queries

### Basic Information Queries

**Count total properties:**
```sql
SELECT COUNT(*) as total_properties FROM properties;
```

**Count by state:**
```sql
SELECT state, COUNT(*) as count FROM properties GROUP BY state ORDER BY count DESC;
```

**Show all tables:**
```sql
SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name;
```

**Database schema version:**
```sql
SELECT version, applied_at, description FROM schema_version;
```

### Properties Queries

**View sample properties:**
```sql
SELECT property_id, address, latitude, longitude, state 
FROM properties 
LIMIT 10;
```

**Find properties in floodplain:**
```sql
SELECT property_id, address, is_in_floodplain, is_in_wildland_urban_interface 
FROM properties 
WHERE is_in_floodplain = 1;
```

**Properties in specific state:**
```sql
SELECT property_id, address, county 
FROM properties 
WHERE state = 'CA' 
LIMIT 10;
```

**Properties with high elevation:**
```sql
SELECT property_id, address, elevation_m 
FROM properties 
WHERE elevation_m > 1000 
ORDER BY elevation_m DESC;
```

### Risk Assessment Queries

**Latest risk assessments:**
```sql
SELECT assessment_id, property_id, assessment_timestamp, overall_risk_score, risk_level 
FROM risk_assessments 
ORDER BY created_at DESC 
LIMIT 10;
```

**Risk by level:**
```sql
SELECT risk_level, COUNT(*) as count, ROUND(AVG(overall_risk_score), 2) as avg_score 
FROM risk_assessments 
GROUP BY risk_level;
```

**High-risk properties:**
```sql
SELECT ra.property_id, p.address, ra.overall_risk_score, ra.risk_level 
FROM risk_assessments ra
JOIN properties p ON ra.property_id = p.property_id
WHERE ra.overall_risk_score > 70
ORDER BY ra.overall_risk_score DESC;
```

### Hazard Data Queries

**All hazard sources:**
```sql
SELECT DISTINCT hazard_type, source FROM hazard_data;
```

**Recent hazard data:**
```sql
SELECT hazard_type, source, latitude, longitude, value, observation_timestamp 
FROM hazard_data 
ORDER BY ingested_timestamp DESC 
LIMIT 10;
```

**Hazard records by type:**
```sql
SELECT hazard_type, source, COUNT(*) as count 
FROM hazard_data 
GROUP BY hazard_type, source;
```

### Alert Queries

**All alerts:**
```sql
SELECT alert_id, property_id, risk_type, risk_score, alert_level, triggered_at 
FROM alerts 
ORDER BY triggered_at DESC;
```

**Unacknowledged alerts:**
```sql
SELECT alert_id, property_id, risk_type, risk_score 
FROM alerts 
WHERE acknowledged_at IS NULL;
```

**Alert counts by level:**
```sql
SELECT alert_level, risk_type, COUNT(*) as count 
FROM alerts 
GROUP BY alert_level, risk_type;
```

### Joins (Cross-Table Queries)

**Properties with their latest risk:**
```sql
SELECT 
    p.property_id, 
    p.address, 
    p.state,
    ra.overall_risk_score,
    ra.risk_level,
    ra.assessment_timestamp
FROM properties p
LEFT JOIN risk_assessments ra ON p.property_id = ra.property_id
ORDER BY ra.assessment_timestamp DESC
LIMIT 10;
```

**Properties with alerts:**
```sql
SELECT 
    p.property_id,
    p.address,
    a.alert_id,
    a.risk_type,
    a.risk_score,
    a.triggered_at
FROM properties p
JOIN alerts a ON p.property_id = a.property_id
ORDER BY a.triggered_at DESC;
```

---

## Python Usage Examples

### Simple Query
```python
from src.database import get_db_connection

conn = get_db_connection()
cursor = conn.cursor()

# Query
cursor.execute("SELECT COUNT(*) FROM properties")
count = cursor.fetchone()[0]
print(f"Total properties: {count}")

conn.close()
```

### Fetch Multiple Rows
```python
from src.database import get_db_connection

conn = get_db_connection()
cursor = conn.cursor()

# Fetch all properties
cursor.execute("SELECT property_id, address, state FROM properties LIMIT 5")
properties = cursor.fetchall()

for prop in properties:
    print(f"{prop['property_id']}: {prop['address']} ({prop['state']})")

conn.close()
```

### INSERT Data
```python
from src.database import get_db_connection
from datetime import datetime

conn = get_db_connection()
cursor = conn.cursor()

# Insert property
cursor.execute("""
    INSERT INTO properties 
    (address, latitude, longitude, state, county)
    VALUES (?, ?, ?, ?, ?)
""", ("123 Main St", 33.75, -116.72, "CA", "Riverside"))

conn.commit()
print(f"Inserted! New property ID: {cursor.lastrowid}")

conn.close()
```

### Conditional Update
```python
from src.database import get_db_connection

conn = get_db_connection()
cursor = conn.cursor()

# Update property
cursor.execute("""
    UPDATE properties 
    SET is_in_floodplain = 1
    WHERE property_id = 1
""")

conn.commit()
print(f"Updated {cursor.rowcount} rows")

conn.close()
```

---

## Table Descriptions

### properties
Stores property information and static hazard exposure flags.
- **Columns:** property_id, address, latitude, longitude, state, county, zip_code, construction_type, elevation_m, is_in_wildland_urban_interface, is_in_floodplain, soil_type, drainage_class
- **Rows:** Empty (load in Task 7)

### risk_assessments
Stores risk score snapshots for each property over time.
- **Columns:** assessment_id, property_id, assessment_timestamp, wildfire_risk_score, wildfire_factors (JSON), flood_risk_score, flood_factors (JSON), overall_risk_score, risk_level, alerts_triggered (JSON)
- **Rows:** Empty (generated by Task 19)

### hazard_data
Stores external hazard data ingested from APIs.
- **Columns:** hazard_id, hazard_type, source, latitude, longitude, value, confidence, observation_timestamp, ingested_timestamp, raw_data (JSON)
- **Rows:** Empty (populated by Task 14)

### alerts
Stores triggered alerts.
- **Columns:** alert_id, property_id, risk_type, risk_score, threshold_exceeded, alert_level, message, triggered_at, acknowledged_at
- **Rows:** Empty (generated by Task 20)

### alert_history
Tracks alert status changes over time.
- **Columns:** history_id, alert_id, old_status, new_status, timestamp
- **Rows:** Empty (populated by Task 22)

### schema_version
Tracks database schema versions for migrations.
- **Columns:** id, version, applied_at, description
- **Rows:** 1 (schema version 1 recorded at initialization)

---

## Tips

1. **Use `LIMIT` for safety:** Always use LIMIT when testing queries on large tables
2. **Check counts first:** `SELECT COUNT(*)` before fetching large result sets
3. **Use indexes:** Queries on indexed columns (state, timestamp, risk_level) are faster
4. **JSON queries:** Hazard data and factors stored as JSON text can be queried with JSON functions

---

## Troubleshooting

**"Database not found"**
- Run `python src/database/db.py` to initialize

**"No results found"**
- Tables are empty until data is loaded (Tasks 7-14)
- Check table with `SELECT COUNT(*) FROM table_name`

**"Column not found"**
- Use `PRAGMA table_info(table_name)` to see all columns
- Column names are case-sensitive

**Connection errors**
- Ensure virtual environment is activated
- Check database file exists at `data/climate_risk.db`

---

## Next Steps

1. Use `db_inspector.py` to explore the schema
2. Run example queries with `run_example_queries.py`
3. Write custom Python scripts to query data
4. Load sample data in Task 7 (Property Loader)
