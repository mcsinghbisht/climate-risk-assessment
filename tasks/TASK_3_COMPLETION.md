# Task 3: Create SQLite Database Schema - COMPLETED ✓

**Completed:** 2026-07-19  
**Status:** Database is fully initialized and verified

---

## What Was Completed

### 1. SQLite Database Created
**Location:** `data/climate_risk.db`  
**Size:** 0.08 MB  
**Schema Version:** 1  
**Status:** ✓ Ready for data ingestion

---

### 2. Six Core Tables Created

| # | Table | Rows | Purpose |
|---|-------|------|---------|
| 1 | **properties** | 0 | Store property data and static hazard exposure |
| 2 | **risk_assessments** | 0 | Store risk score snapshots over time |
| 3 | **hazard_data** | 0 | Store ingested external hazard data |
| 4 | **alerts** | 0 | Store triggered alerts |
| 5 | **alert_history** | 0 | Track alert status changes |
| 6 | **schema_version** | 1 | Track database schema versions |

---

### 3. 11 Indexes Created for Performance

**Properties Table:**
- `idx_properties_state` — Fast state-level filtering
- `idx_properties_county` — Fast county-level filtering
- `idx_properties_coords` — Fast coordinate-based queries

**Risk Assessments Table:**
- `idx_risk_property` — Link risks to properties
- `idx_risk_timestamp` — Time-range queries
- `idx_risk_level` — Filter by risk level

**Hazard Data Table:**
- `idx_hazard_type` — Filter by hazard source
- `idx_hazard_coords` — Spatial queries
- `idx_hazard_timestamp` — Recent data lookups

**Alerts Table:**
- `idx_alerts_property` — Property-level alert history
- `idx_alerts_timestamp` — Recent alerts

---

## Table Structure Details

### properties (15 columns)
```
property_id             INTEGER PRIMARY KEY
address                 TEXT NOT NULL
latitude                REAL NOT NULL (validated: -90 to 90)
longitude               REAL NOT NULL (validated: -180 to 180)
state                   TEXT
county                  TEXT
zip_code                TEXT
construction_type       TEXT
elevation_m             REAL
is_in_wildland_urban_interface  BOOLEAN
is_in_floodplain        BOOLEAN
soil_type               TEXT
drainage_class          TEXT
created_at              TIMESTAMP (auto-set)
updated_at              TIMESTAMP (auto-set)
```

### risk_assessments (11 columns)
```
assessment_id           INTEGER PRIMARY KEY
property_id             INTEGER NOT NULL -> properties(property_id)
assessment_timestamp    TIMESTAMP NOT NULL
wildfire_risk_score     REAL (0-100)
wildfire_factors        TEXT (JSON)
flood_risk_score        REAL (0-100)
flood_factors           TEXT (JSON)
overall_risk_score      REAL (0-100)
risk_level              TEXT (low|medium|high|critical)
alerts_triggered        TEXT (JSON)
created_at              TIMESTAMP (auto-set)
```

### hazard_data (9 columns)
```
hazard_id               INTEGER PRIMARY KEY
hazard_type             TEXT NOT NULL
source                  TEXT NOT NULL
latitude                REAL NOT NULL
longitude               REAL NOT NULL
value                   REAL
confidence              REAL (0-1)
observation_timestamp   TIMESTAMP NOT NULL
ingested_timestamp      TIMESTAMP (auto-set)
raw_data                TEXT (JSON, full API response)
```

### alerts (10 columns)
```
alert_id                INTEGER PRIMARY KEY
property_id             INTEGER NOT NULL -> properties(property_id)
risk_type               TEXT NOT NULL
risk_score              REAL (0-100)
threshold_exceeded      REAL
alert_level             TEXT (warning|critical)
message                 TEXT
triggered_at            TIMESTAMP NOT NULL
acknowledged_at         TIMESTAMP
created_at              TIMESTAMP (auto-set)
```

### alert_history (4 columns)
```
history_id              INTEGER PRIMARY KEY
alert_id                INTEGER NOT NULL -> alerts(alert_id)
old_status              TEXT
new_status              TEXT
timestamp               TIMESTAMP (auto-set)
```

### schema_version (4 columns)
```
id                      INTEGER PRIMARY KEY
version                 INTEGER NOT NULL
applied_at              TIMESTAMP (auto-set)
description             TEXT
```

---

## Foreign Key Relationships

```
risk_assessments.property_id ──────► properties.property_id
alerts.property_id ────────────────► properties.property_id
alert_history.alert_id ───────────► alerts.alert_id
```

---

## Data Validation (Constraints)

✓ **Coordinate Validation**
- Latitude: -90 to 90
- Longitude: -180 to 180

✓ **Score Validation**
- All risk scores: 0 to 100
- Confidence: 0 to 1

✓ **Enum Validation**
- risk_level: low | medium | high | critical
- alert_level: warning | critical

---

## Files Created/Modified

| File | Purpose |
|------|---------|
| `src/database/db.py` | Main database initialization & setup (232 lines) |
| `src/database/migrations.py` | Schema versioning & migration tracking (65 lines) |
| `src/database/__init__.py` | Package exports & public API |
| `data/schema.sql` | SQL schema documentation & reference |
| `data/climate_risk.db` | SQLite database file (created, 84 KB) |
| `verify_database.py` | Database verification script (for testing) |

---

## How to Use the Database

### Connect to Database (Python)
```python
from src.database import get_db_connection

conn = get_db_connection()
cursor = conn.cursor()
cursor.execute("SELECT * FROM properties")
rows = cursor.fetchall()
conn.close()
```

### Initialize Database (if needed)
```python
from src.database import initialize_database

success, message = initialize_database()
print(message)
```

### Verify Database Setup
```bash
python verify_database.py
```

---

## Following Reference Principles

**Task 3 aligns with project principles:**

✓ **Data Quality as First-Class Concern**
- CHECK constraints validate coordinates and scores
- Foreign keys ensure referential integrity
- Timestamps on every table for audit trails

✓ **Scalability From Day One**
- Indexes on all frequently-queried columns
- Schema supports millions of records
- Proper normalization for efficiency

✓ **Transparency & Explainability**
- Clear column names and types
- JSON fields store detailed factors for scoring
- Alert history tracks all changes

✓ **Integration-First Architecture**
- Foreign keys enable cross-table joins
- Structured schema supports API serialization
- Timestamps enable audit and compliance

---

## Summary

| Aspect | Status |
|--------|--------|
| Database Created | ✓ climate_risk.db |
| Tables Created | ✓ 6 tables |
| Indexes Created | ✓ 11 indexes |
| Foreign Keys | ✓ 3 relationships |
| Validation Constraints | ✓ Coordinates, scores, enums |
| Schema Version Recorded | ✓ Version 1 |
| Database Verified | ✓ All tables ready |

---

## Next Steps

**Task 4: Create Utility Functions (Geospatial & Time)**
- Distance calculations for proximity scoring
- Coordinate validation
- Timestamp utilities for monitoring cycles

---

## Key Features Available

✓ **Persistent storage** of properties, risks, hazards, and alerts  
✓ **Time-series tracking** of risk assessments  
✓ **Foreign key integrity** ensuring data consistency  
✓ **Performance indexes** for fast queries  
✓ **Audit trail** with timestamps on all operations  
✓ **JSON storage** for complex factor data  
✓ **Validation constraints** ensuring data quality  

---

## Ready for Task 4 ✓

Database is fully initialized, indexed, and verified. Ready to proceed to **Task 4: Create Utility Functions**.

