# Project Structure (Reorganized)

Clean, organized project layout with all files in appropriate directories.

---

## Directory Tree

```
Climate_Risk_Assessment/
│
├── 📄 CLAUDE.md                    (Project documentation & setup)
├── 📄 README.md                    (Project overview)
├── 📄 .gitignore                   (Git configuration)
├── 📄 requirements.txt             (Python dependencies)
├── 📄 PROJECT_STRUCTURE.md         (This file)
│
├── 📁 docs/                        ⭐ Documentation & Guides
│   ├── reference-principles.md     (Design principles)
│   ├── implementation-plan.md      (Detailed tech plan)
│   ├── task-breakdown.md           (34 tasks breakdown)
│   ├── DATABASE_USAGE_GUIDE.md     (SQL query examples)
│   ├── DATABASE_TOOLS_SUMMARY.md   (Database tools comparison)
│   └── QUICK_REFERENCE.txt         (Quick command reference)
│
├── 📁 tasks/                       ⭐ Task Completion Records
│   ├── TASK_1_COMPLETION.md        (Python project setup)
│   ├── TASK_2_COMPLETION.md        (Virtual environment & deps)
│   └── TASK_3_COMPLETION.md        (SQLite schema setup)
│
├── 📁 tools/                       ⭐ Utility & Testing Scripts
│   ├── query.py                    (Quick SQL query runner)
│   ├── db_inspector.py             (Interactive DB explorer)
│   ├── run_example_queries.py      (Pre-built example queries)
│   ├── verify_database.py          (Database verification)
│   └── test_imports.py             (Dependency test)
│
├── 📁 src/                         ⭐ Application Source Code
│   ├── __init__.py
│   ├── main.py                     (Application entry point - TODO)
│   │
│   ├── database/                   (Database management)
│   │   ├── __init__.py
│   │   ├── db.py                   (SQLite setup & connection)
│   │   └── migrations.py           (Schema versioning)
│   │
│   ├── data_ingestion/             (External data fetching)
│   │   ├── __init__.py
│   │   ├── property_loader.py      (Task 8 - TODO)
│   │   ├── wildfire_ingestion.py   (Task 10 - TODO)
│   │   ├── weather_ingestion.py    (Task 11 - TODO)
│   │   ├── flood_ingestion.py      (Task 12 - TODO)
│   │   └── data_normalizer.py      (Task 13 - TODO)
│   │
│   ├── risk_scoring/               (Risk algorithms)
│   │   ├── __init__.py
│   │   ├── wildfire_scorer.py      (Task 15 - TODO)
│   │   ├── flood_scorer.py         (Task 16 - TODO)
│   │   ├── aggregator.py           (Task 17 - TODO)
│   │   └── scoring_engine.py       (Task 19 - TODO)
│   │
│   ├── continuous_monitoring/      (Monitoring system)
│   │   ├── __init__.py
│   │   ├── monitor.py              (Task 23 - TODO)
│   │   ├── scheduler.py            (Task 24 - TODO)
│   │   └── change_detector.py      (Task 22 - TODO)
│   │
│   ├── alerts/                     (Alert system)
│   │   ├── __init__.py
│   │   ├── alert_engine.py         (Task 20 - TODO)
│   │   ├── notification.py         (Task 21 - TODO)
│   │   └── alert_config.py         (Thresholds)
│   │
│   ├── portfolio/                  (Portfolio analysis)
│   │   ├── __init__.py
│   │   ├── aggregator.py           (Task 25 - TODO)
│   │   ├── hotspot_detector.py     (Task 26 - TODO)
│   │   └── reporter.py             (Task 27 - TODO)
│   │
│   ├── config/                     (Configuration)
│   │   ├── __init__.py
│   │   ├── settings.py             (Task 5 - Config manager)
│   │   └── logging_config.py       (Task 6 - Logging)
│   │
│   └── utils/                      (Utility functions)
│       ├── __init__.py
│       ├── geo_utils.py            (Task 4 - Geospatial)
│       ├── time_utils.py           (Task 4 - Time handling)
│       └── validation.py           (Task 4 - Validation)
│
├── 📁 data/                        ⭐ Data & Database
│   ├── climate_risk.db             (SQLite database - 84 KB)
│   ├── schema.sql                  (Schema reference)
│   └── sample_properties.csv       (Sample data backup)
│
├── 📁 config/                      ⭐ Configuration Files
│   ├── settings.json               (Main settings - TODO)
│   ├── logging_config.json         (Logging config - TODO)
│   ├── api_config.json             (API endpoints - TODO)
│   └── risk_thresholds.json        (Risk settings - TODO)
│
├── 📁 logs/                        (Application logs - created at runtime)
│
├── 📁 reports/                     (Generated reports - created at runtime)
│
├── 📁 scripts/                     (Utility scripts)
│
├── 📁 tests/                       (Test suite)
│   ├── __init__.py
│   ├── fixtures/                   (Test data)
│   ├── test_*.py                   (Test files - Tasks 28-30)
│
├── 📁 .claude/                     (Claude Code settings)
│   └── settings.json               (Project-specific settings)

```

---

## What's Where

### 📦 Root Level (4 files)
**Purpose:** Core project files  
**Keep here:** Configuration files, project metadata

```
CLAUDE.md              - Project vision & setup
README.md              - Quick start guide
.gitignore             - Git patterns
requirements.txt       - Python dependencies
```

### 📚 docs/ (6 files)
**Purpose:** All documentation and guides  
**Use:** Read when you need to understand the project

```
reference-principles.md      - 12 design principles
implementation-plan.md       - Detailed technical plan
task-breakdown.md            - 34 small tasks
DATABASE_USAGE_GUIDE.md      - SQL examples (30+ queries)
DATABASE_TOOLS_SUMMARY.md    - Database tools comparison
QUICK_REFERENCE.txt          - Quick commands
```

### 📋 tasks/ (3 files)
**Purpose:** Track completion of major phases  
**Use:** Reference when you complete a task

```
TASK_1_COMPLETION.md   - Project initialization (✓ Done)
TASK_2_COMPLETION.md   - Virtual environment setup (✓ Done)
TASK_3_COMPLETION.md   - Database schema creation (✓ Done)
```

### 🛠️ tools/ (5 files)
**Purpose:** Standalone utility scripts  
**Use:** Run when you need to inspect database or test setup

```
query.py                  - Run SQL queries from command line
db_inspector.py           - Interactive database explorer
run_example_queries.py    - Run 8 pre-built queries
verify_database.py        - Verify database structure
test_imports.py           - Test Python dependencies
```

### 💻 src/ (Main Application)
**Purpose:** Application source code  
**Organized by:**
- **database/** — SQLite setup & connections
- **data_ingestion/** — Fetch external hazard data (APIs)
- **risk_scoring/** — Calculate wildfire & flood risk
- **continuous_monitoring/** — 5-minute monitoring loop
- **alerts/** — Generate & send alerts
- **portfolio/** — Aggregate & analyze portfolio
- **config/** — Settings & logging
- **utils/** — Helper functions (geo, time, validation)

### 📊 data/
**Purpose:** Database and data files  
**Contains:**
- `climate_risk.db` — SQLite database (84 KB)
- `schema.sql` — Schema reference
- Sample property CSV files

### ⚙️ config/
**Purpose:** Configuration files (JSON)  
**Will contain:**
- `settings.json` — Main configuration
- `logging_config.json` — Logging setup
- `api_config.json` — API endpoints
- `risk_thresholds.json` — Risk settings

### 📝 logs/
**Purpose:** Application logs  
**Created at runtime:** `app.log`, `alerts.log`, etc.

### 📈 reports/
**Purpose:** Generated reports  
**Created at runtime:** Portfolio reports, analysis files

---

## File Organization by Category

### Configuration Files (Root Level)
```
CLAUDE.md              ← Project documentation
README.md              ← Quick start
.gitignore             ← Git configuration
requirements.txt       ← Python dependencies
```

### Documentation (docs/)
```
reference-principles.md        ← Design principles
implementation-plan.md         ← Technical plan
task-breakdown.md              ← 34 tasks
DATABASE_USAGE_GUIDE.md        ← SQL queries
DATABASE_TOOLS_SUMMARY.md      ← Tools info
QUICK_REFERENCE.txt            ← Commands
```

### Tools (tools/)
```
query.py                       ← Quick queries
db_inspector.py                ← Interactive explorer
run_example_queries.py         ← Examples
verify_database.py             ← Verification
test_imports.py                ← Dependency test
```

### Source Code (src/)
```
database/                      ← DB management
data_ingestion/                ← API data fetch
risk_scoring/                  ← Risk algorithms
continuous_monitoring/         ← Monitoring loop
alerts/                        ← Alert system
portfolio/                     ← Portfolio analysis
config/                        ← Settings
utils/                         ← Utilities
```

### Data (data/)
```
climate_risk.db                ← SQLite database
schema.sql                     ← Schema reference
sample_properties.csv          ← Sample data
```

---

## Task Progress

### ✅ Completed (3/34)
- Task 1: Project Structure
- Task 2: Virtual Environment
- Task 3: Database Schema

### ⏭️ Next (Task 4)
- Task 4: Utility Functions (Geospatial & Time)

### 📋 Future (Tasks 5-34)
- Tasks 5-6: Configuration & Logging
- Tasks 7-9: Load Properties
- Tasks 10-14: Data Ingestion APIs
- Tasks 15-19: Risk Scoring
- Tasks 20-24: Alerts & Monitoring
- Tasks 25-27: Portfolio
- Tasks 28-34: Testing & Documentation

---

## Quick Access

### To Run Database Tools
```bash
cd tools/
python query.py "SELECT * FROM schema_version"
python db_inspector.py
python run_example_queries.py
```

### To Read Documentation
```bash
docs/QUICK_REFERENCE.txt          ← Start here
docs/DATABASE_TOOLS_SUMMARY.md    ← Tools comparison
docs/DATABASE_USAGE_GUIDE.md      ← SQL examples
docs/reference-principles.md      ← Design principles
```

### To Check Task Completion
```bash
tasks/TASK_1_COMPLETION.md
tasks/TASK_2_COMPLETION.md
tasks/TASK_3_COMPLETION.md
```

---

## Before Each Task

1. **Read task description** in `docs/task-breakdown.md`
2. **Check dependencies** from task list
3. **Review relevant docs** in `docs/` folder
4. **Use tools/** to verify setup
5. **Update task record** when complete

---

## Summary

| Location | Purpose | Files | Status |
|----------|---------|-------|--------|
| Root | Core config | 4 | ✓ Clean |
| docs/ | Documentation | 6 | ✓ Complete |
| tasks/ | Task records | 3 | ✓ Up to date |
| tools/ | Utilities | 5 | ✓ Ready |
| src/ | Source code | Multiple | 🔨 In progress |
| data/ | Database | 3 | ✓ Ready |
| config/ | Settings | Empty | → Task 5 |
| logs/ | Logs | Empty | → Runtime |
| reports/ | Reports | Empty | → Runtime |

✓ **Project is well-organized and ready for development!**

---

Last updated: 2026-07-19
