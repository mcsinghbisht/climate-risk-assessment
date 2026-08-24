# Database Tools & Query Options

Three ways to check the database and run SQL queries.

---

## 🎯 Quick Comparison

| Tool | Use Case | Complexity | Best For |
|------|----------|-----------|----------|
| **query.py** | Simple queries | ⭐ Easiest | Quick lookups, one-liners |
| **db_inspector.py** | Exploring database | ⭐⭐ Medium | Browsing schema, testing queries |
| **Python API** | Programmatic access | ⭐⭐⭐ Advanced | Building applications |

---

## Option 1: Quick Query Runner (Easiest) 🚀

### Command-Line Query
```bash
# Activate venv first
.\venv\Scripts\Activate.ps1

# Run a query
python query.py "SELECT COUNT(*) FROM properties"
python query.py "SELECT name FROM sqlite_master WHERE type='table'"
python query.py "SELECT version FROM schema_version"
```

### Interactive Mode
```bash
python query.py
# Then type queries at the prompt:
SQL> SELECT COUNT(*) FROM properties
SQL> SELECT * FROM schema_version
SQL> exit
```

### Examples
```bash
# Count rows in each table
python query.py "SELECT 'properties' as table_name, COUNT(*) FROM properties UNION ALL SELECT 'alerts', COUNT(*) FROM alerts"

# Show database info
python query.py "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"

# Show schema version
python query.py "SELECT * FROM schema_version"

# Get table info
python query.py "PRAGMA table_info(properties)"

# Show indexes
python query.py "SELECT name, tbl_name FROM sqlite_master WHERE type='index'"
```

---

## Option 2: Database Inspector (Best for Exploration) 🔍

### Launch Interactive Menu
```bash
# Activate venv first
.\venv\Scripts\Activate.ps1

# Run inspector
python db_inspector.py
```

### Menu Options
```
1. Show database info
   - File location
   - File size
   - Database version

2. List all tables
   - All tables
   - Row counts

3. Show table schema
   - Column names & types
   - Constraints
   - Row count
   (Enter table name when prompted)

4. Run custom SQL query
   - Type any SQL query
   - View formatted results

5. Run example queries
   - 8 pre-built queries
   - Choose which to run

6. Exit
```

### Built-in Example Queries
- Show all tables and row counts
- Count properties by state
- Show sample properties
- Show properties in floodplain
- Show latest risk assessments
- Show all hazard data
- Show all alerts
- Show schema version

---

## Option 3: Python Direct Access (Most Powerful) ⚙️

### Basic Connection
```python
from src.database import get_db_connection

conn = get_db_connection()
cursor = conn.cursor()

# Run query
cursor.execute("SELECT COUNT(*) FROM properties")
result = cursor.fetchone()[0]
print(f"Total properties: {result}")

conn.close()
```

### Fetch Multiple Rows
```python
from src.database import get_db_connection

conn = get_db_connection()
cursor = conn.cursor()

cursor.execute("SELECT property_id, address, state FROM properties LIMIT 5")
for row in cursor.fetchall():
    print(f"{row['property_id']}: {row['address']} ({row['state']})")

conn.close()
```

### Insert Data
```python
from src.database import get_db_connection
from datetime import datetime

conn = get_db_connection()
cursor = conn.cursor()

cursor.execute("""
    INSERT INTO properties (address, latitude, longitude, state)
    VALUES (?, ?, ?, ?)
""", ("123 Main St", 33.75, -116.72, "CA"))

conn.commit()
property_id = cursor.lastrowid
print(f"New property ID: {property_id}")

conn.close()
```

### Query with Parameters (Prevent SQL Injection)
```python
from src.database import get_db_connection

conn = get_db_connection()
cursor = conn.cursor()

state_code = "CA"
cursor.execute("SELECT COUNT(*) FROM properties WHERE state = ?", (state_code,))
count = cursor.fetchone()[0]
print(f"Properties in {state_code}: {count}")

conn.close()
```

---

## Current Database Status

### Tables Created ✓
- **properties** (0 rows) - Ready for load
- **risk_assessments** (0 rows) - Ready for scores
- **hazard_data** (0 rows) - Ready for API data
- **alerts** (0 rows) - Ready for alerts
- **alert_history** (0 rows) - Ready for tracking
- **schema_version** (1 row) - Version 1 recorded

### Indexes Created ✓
- 11 performance indexes across all tables

### Database File
- Location: `data/climate_risk.db`
- Size: 84 KB
- Status: Ready

---

## Common Queries Reference

### Count All Tables
```sql
SELECT 'properties' as tbl, COUNT(*) FROM properties
UNION ALL SELECT 'risk_assessments', COUNT(*) FROM risk_assessments
UNION ALL SELECT 'hazard_data', COUNT(*) FROM hazard_data
UNION ALL SELECT 'alerts', COUNT(*) FROM alerts
UNION ALL SELECT 'alert_history', COUNT(*) FROM alert_history
UNION ALL SELECT 'schema_version', COUNT(*) FROM schema_version
```

### Show All Tables
```sql
SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name
```

### Show Table Structure
```sql
PRAGMA table_info(properties)
PRAGMA table_info(risk_assessments)
PRAGMA table_info(hazard_data)
PRAGMA table_info(alerts)
```

### Show All Indexes
```sql
SELECT name, tbl_name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%'
```

### Show Foreign Keys
```sql
PRAGMA foreign_key_list(risk_assessments)
PRAGMA foreign_key_list(alerts)
```

### Schema Version
```sql
SELECT * FROM schema_version
```

---

## Workflow

### Step 1: Verify Database
```bash
python run_example_queries.py
```
Shows all tables and their status.

### Step 2: Quick Lookups
```bash
python query.py "SELECT COUNT(*) FROM properties"
```

### Step 3: Explore Schema
```bash
python db_inspector.py
# Choose option 2 to list tables
# Choose option 3 to show schema for a specific table
```

### Step 4: Run Complex Queries
```bash
# Use query.py for ad-hoc queries
python query.py "SELECT state, COUNT(*) FROM properties GROUP BY state"

# Use db_inspector.py for interactive exploration
python db_inspector.py
# Choose option 4 to run custom SQL
```

### Step 5: Programmatic Access
```python
# Use Python API in your code
from src.database import get_db_connection
# ... your code ...
```

---

## Tips & Best Practices

1. **Always activate venv first**
   ```bash
   .\venv\Scripts\Activate.ps1
   ```

2. **Use LIMIT for safety**
   ```sql
   SELECT * FROM properties LIMIT 10  -- Safe
   SELECT * FROM properties            -- Could be slow
   ```

3. **Check counts before fetching**
   ```sql
   SELECT COUNT(*) FROM table_name  -- Quick check first
   ```

4. **Use indexes for speed**
   - Queries on indexed columns are fast
   - Indexed: state, county, coordinates, timestamp, risk_level

5. **Format large results**
   ```bash
   python query.py "SELECT * FROM table LIMIT 100"  # Readable output
   ```

---

## Troubleshooting

### "Database not found"
```bash
python src/database/db.py  # Reinitialize
```

### "No results found"
- Table is probably empty (expected for Tasks 1-6)
- Check: `python query.py "SELECT COUNT(*) FROM table_name"`

### "Column not found"
- Check schema: `python query.py "PRAGMA table_info(table_name)"`

### Connection timeout
- Make sure venv is activated
- Check database file exists: `data/climate_risk.db`

---

## Next Steps

1. **Use `query.py`** for quick lookups
   ```bash
   python query.py "SELECT * FROM schema_version"
   ```

2. **Use `db_inspector.py`** to explore tables
   ```bash
   python db_inspector.py
   ```

3. **Use `run_example_queries.py`** to see data examples
   ```bash
   python run_example_queries.py
   ```

4. **Read `DATABASE_USAGE_GUIDE.md`** for detailed query examples

5. **Task 7**: Load 100 sample properties into database

---

## Summary

You have **3 powerful tools** to work with the database:

| Tool | Command | Purpose |
|------|---------|---------|
| **query.py** | `python query.py "SQL"` | Single queries |
| **db_inspector.py** | `python db_inspector.py` | Interactive exploration |
| **Python API** | `from src.database import ...` | Programmatic access |

Choose based on your need:
- **Quick answer?** → `query.py`
- **Exploring?** → `db_inspector.py`
- **Building code?** → Python API

All three access the same database! ✓
