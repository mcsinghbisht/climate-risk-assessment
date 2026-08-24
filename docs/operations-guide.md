# Operations Guide

A practical, operator-facing guide: how to install, configure, run, monitor,
and troubleshoot the Climate Risk Assessment system. If you want to know
*what a function returns*, see [api-reference.md](api-reference.md) instead
- this document is about running the system, not calling its code directly.

**Table of Contents**
1. [Installation & Setup](#1-installation--setup)
2. [Configuration Walkthrough](#2-configuration-walkthrough)
3. [Running the Monitoring Loop](#3-running-the-monitoring-loop)
4. [Monitoring Health](#4-monitoring-health)
5. [Troubleshooting](#5-troubleshooting)
6. [Data Backup Procedures](#6-data-backup-procedures)

---

## 1. Installation & Setup

### Prerequisites
- Python 3.10+ (developed and tested on 3.14)
- Free API keys for two of the three data sources (see below) - USGS Water
  Services requires no key at all

### Step 1: Install dependencies
```bash
pip install -r requirements.txt
```

### Step 2: Register free API keys
Two of the three hazard data sources require a free API key; USGS does not.

| Source | Used for | Register at |
|---|---|---|
| NASA FIRMS | Active wildfire detections | https://firms.modaps.eosdis.nasa.gov/api/map_key/ |
| OpenWeatherMap | Weather + precipitation | https://openweathermap.org/appid |
| USGS Water Services | River gauge levels | No key required |

Copy `.env.example` to `.env` and fill in both keys:
```bash
cp .env.example .env
```
```ini
NASA_FIRMS_API_KEY=your_key_here
OPENWEATHER_API_KEY=your_key_here
```

**`.env` is gitignored and must never be committed.** If a key is ever
accidentally exposed (e.g. pasted into a chat log or committed), rotate it
immediately at the registration link above - this project's own error
logging deliberately redacts API keys from log output (`str(e).replace(self.api_key, "***")`
in `wildfire_ingestion.py`/`weather_ingestion.py`) precisely because a real
key was accidentally exposed once during development and had to be rotated.

### Step 3: Initialize the database
```bash
python -m src.database.db
```
This creates `data/climate_risk.db` with all tables and indexes, and
verifies the result. Safe to re-run - table creation uses `CREATE TABLE IF
NOT EXISTS`, so it's a no-op against an already-initialized database.

### Step 4: Generate and load sample properties
The project ships with a synthetic 100-property portfolio (not real
property records - see `src/data_ingestion/property_generator.py`'s
docstring) for development and demonstration.
```bash
python -m src.data_ingestion.property_generator   # writes data/sample_properties.json + .csv
python -m src.data_ingestion.property_loader      # loads them into the properties table
```
The loader validates each record (`validate_property_data()`) and upserts
on `property_id`, so it's also safe to re-run.

### Step 5: Verify the setup
```bash
python -c "
from src.database import PropertyDAO
print(f'{PropertyDAO().count_properties()} properties loaded')
"
```
Expect `100 properties loaded`.

---

## 2. Configuration Walkthrough

Everything tunable lives in `config/settings.json` - no thresholds are
hardcoded in source. Access it via `get_config()` (`src/config/settings.py`),
never by reading the JSON file directly in application code.

### `risk_scoring` - scoring weights and thresholds
- `wildfire_weights` / `flood_weights` - how each scorer's four factors
  combine (each set sums to 1.0)
- `overall_weights` - wildfire vs. flood weight in the combined score
  (0.5/0.5 by default)
- `risk_levels` - score bucket boundaries (`low_max`, `medium_max`,
  `high_max`; anything above `high_max` is `critical`)
- `critical_single_hazard_threshold` (default 85) - a single hazard scoring
  at or above this forces `risk_level="critical"` regardless of the other
  hazard, so an extreme single peril is never diluted by averaging (see
  [implementation-plan.md](implementation-plan.md))
- `wildfire_params` / `flood_params` - the physical thresholds each scorer's
  factors are calibrated against (e.g. `proximity_max_km`, `wind_speed_threshold_ms`)

### `alerts` - thresholds and lifecycle timing
- `wildfire_threshold` / `flood_threshold` - absolute score that triggers a
  `critical` property-level alert
- `wildfire_increase_threshold` / `flood_increase_threshold` - point jump
  since the last assessment that triggers a `warning` alert
- `portfolio_threshold_percent` (default 10) - percentage of the portfolio
  in high/critical risk that triggers the portfolio-level alert
- `renotify_interval_minutes` (default 60) - minimum gap between repeat
  notifications for an ongoing, unacknowledged alert
- `resolution_hysteresis` / `portfolio_resolution_hysteresis_percent` - how
  far a score/percentage must fall below its trigger point to count as
  resolved (prevents flapping open/closed right at the threshold)
- `stale_after_hours` (default 6) - an alert whose property hasn't been
  reassessed within this window is marked `stale`, not left falsely `active`
- `alert_check_interval_minutes` (default 5) - how often the scheduler runs
  a full monitoring cycle

Full lifecycle design: [alert-lifecycle-design.md](alert-lifecycle-design.md).

### `data_sources` - per-provider settings
Each source (`nasa_firms`, `openweather`, `usgs_water`) has its own
`enabled` flag, `base_url`, and `calls_per_minute` (rate limit, enforced by
`RateLimiter`). **Setting `enabled: false` silently disables that source** -
`fetch_active_fires()`/`fetch_weather()`/`fetch_river_gauges()` all return
an empty result rather than raising, so a disabled source shows up as "0
records ingested," not an error (see Troubleshooting below).

### `ingestion` - scaling behavior
- `grid_cell_size_degrees` (default 0.5, ~55km) - properties sharing a grid
  cell share hazard-data API calls, so call volume scales with geographic
  footprint, not portfolio size (see [scaling-design.md](scaling-design.md))
- `freshness_minutes` (default 4) - a cell/source already has a fresh-enough
  reading, skip re-fetching it this cycle

### `portfolio` - hotspot detection
- `hotspot_radius_km` (default 50), `hotspot_min_properties` (default 3),
  `hotspot_risk_threshold` (default 50) - together define what counts as a
  geographic risk cluster (see [Task 26 completion notes](../tasks/TASK_26_COMPLETION.md))

### `database`
- `path` - where the SQLite file lives (default `data/climate_risk.db`)
- `backup_enabled` / `backup_interval_hours` - **configured but not
  currently implemented by any code in this project** (no automated backup
  job exists yet). Treat these as a reserved placeholder for a future task,
  not a live feature - see [Section 6](#6-data-backup-procedures) for the
  actual (manual) backup procedure today.

---

## 3. Running the Monitoring Loop

### Option A: One-off cycle
Useful for testing, or triggering a cycle on demand:
```bash
python -m src.continuous_monitoring.monitor
```
Runs ingestion -> scoring -> change detection -> alerting -> portfolio
alert -> notification once, and prints a summary.

### Option B: Continuous scheduled operation
```python
from src.config import setup_logging
from src.continuous_monitoring import SchedulerManager

setup_logging()
scheduler = SchedulerManager()
scheduler.start()   # runs a cycle every alert_check_interval_minutes (default 5)

# keep the process alive - e.g. a simple blocking loop, a systemd service,
# or however your deployment environment keeps a long-running process up
```
`scheduler.stop()` shuts down gracefully, waiting for any in-progress cycle
to finish. The scheduler guarantees cycles never overlap (`max_instances=1`)
and collapses any backlog of missed fire times into a single catch-up run
(`coalesce=True`) if a cycle ever runs long - see
[Task 24 completion notes](../tasks/TASK_24_COMPLETION.md).

This project does not currently ship a dedicated `main.py`/service wrapper
- the snippet above is the intended integration point for whatever process
manager (systemd, a container entrypoint, a simple `while True` script)
your deployment uses to keep a Python process running.

### Generating a portfolio report on demand
```bash
python -m src.portfolio.reporter
```
Prints a text summary and writes `reports/portfolio_YYYY-MM-DD.txt`.

---

## 4. Monitoring Health

### Log files (`logs/`)
| File | Contents | Level |
|---|---|---|
| `app.log` | Everything - full debug detail, rotates at 10MB, keeps 5 backups | DEBUG+ |
| `errors.log` | Only ERROR and above, same rotation policy but 5MB | ERROR+ |
| `alerts.log` | Only alert notifications (`Notifier`), separate from `app.log` so alert output isn't lost in general noise | INFO+ |

Console output mirrors `app.log` at INFO level and above. Configured in
`config/logging_config.json`; call `setup_logging()` once at process start
(idempotent - safe to call from multiple modules).

### What a healthy cycle looks like
```
=== Monitoring cycle starting at 2026-08-03T12:00:00+00:00 ===
... (ingestion, scoring log lines) ...
=== Monitoring cycle complete in 12.3s: 45 hazard records, 100 properties scored, 2 new alerts, 2 notifications sent, 0 errors ===
```
- `errors: []` (or `0 errors`) every cycle is the normal state
- `hazard_records_ingested` should be > 0 most cycles (some cells may be
  skipped as "fresh" within `freshness_minutes`, which is also normal)
- `new_alerts` and `notifications_sent` will be 0 on most quiet cycles -
  that's expected, not a malfunction

### Signs of a real problem
- **Repeated `0 hazard records` every cycle** - check `.env` keys and each
  `data_sources.*.enabled` flag (see Troubleshooting)
- **`errors` non-empty every cycle, same message** - a persistent condition,
  not a transient network blip; read the specific error text (it names the
  failing property_id or cell)
- **`cycles_failed` climbing in `SchedulerManager`** (`scheduler.cycles_failed`)
  - the whole cycle is throwing, not just one component; check `errors.log`
    for the traceback

### Checking alert state directly
```python
from src.database import AlertDAO
active = AlertDAO().get_active_alerts()
print(f"{len(active)} active alerts")
```

---

## 5. Troubleshooting

Real issues encountered during this project's own development, and how to
recognize/resolve each:

### "0 fires ingested" / "0 weather points" every cycle
**Cause:** either `.env` is missing the relevant API key, or that source's
`enabled` flag is `false` in `config/settings.json`. This is by design -
`fetch_active_fires()`/`fetch_weather()`/`fetch_river_gauges()` all log a
warning and return an empty result rather than raising, so ingestion never
crashes just because one source isn't configured.
**Fix:** check `logs/app.log` for `"No ... API key configured"` or
`"ingestion is disabled in config"`; set the key in `.env` and/or flip
`enabled: true`.

### A gauge reading you expected to see is missing
**Cause:** USGS readings older than `DEFAULT_MAX_GAUGE_READING_AGE_HOURS`
(48 hours) are deliberately filtered as stale by `DataNormalizer.normalize_gauge()`
- discovered during development when a genuinely stale 2004-dated reading
came back from a live API call. Not a bug; a data-quality safeguard.
**Fix:** none needed - this is expected. If you need to see why a specific
reading was dropped, `logs/app.log` records a warning naming the site and age.

### API key visible in an error message or log line
**Should never happen** - `wildfire_ingestion.py` and `weather_ingestion.py`
both redact the key from any exception text before logging
(`str(e).replace(self.api_key, "***")`). If you ever see a raw key in
output anyway (e.g. a new ingester added without this pattern), **rotate
the key immediately** at its registration link (Section 1) and add the same
redaction to the new code path.

### First run after upgrading to a version with Task 27's portfolio alerts
**What happens:** `AlertDAO()`'s first construction against an older
database automatically rebuilds the `alerts` table to make `property_id`
nullable (a one-time migration, since SQLite can't drop a `NOT NULL`
constraint via `ALTER TABLE`). This is logged
(`"Migrated alerts table: property_id is now nullable (N rows preserved)"`)
and preserves every existing row - no action needed, but don't be alarmed
by that log line on first startup after upgrading.

### `days=0` (or similar) silently using a default instead of the value you passed
**Historical bug, already fixed** (Task 10): `days = days or self.default_days`
treated `0` as falsy and silently substituted the default. Fixed to
`days if days is not None else self.default_days`. Mentioned here as a
pattern to watch for if extending any function with a numeric optional
argument that could legitimately be `0`.

### A scheduled cycle seems to "disappear" (never logged as run)
**Cause:** `SchedulerManager` uses `coalesce=True` - if the process was
paused/delayed long enough to miss multiple scheduled fire times, they
collapse into a single catch-up run rather than each firing separately.
Check `EVENT_JOB_MISSED` warnings in `app.log` to confirm this is what happened.

### One property (or one ingestion cell) fails but the rest complete fine
**This is intentional, not a bug.** Every per-property and per-cell
operation in `RiskScoringEngine`, `IngestionEngine`, and `Monitor` is
individually wrapped in try/except - one bad record never stops the rest
of the portfolio from processing. Check the `errors` list in that
component's summary dict for exactly which property/cell failed and why.

---

## 6. Data Backup Procedures

**There is currently no automated backup job** in this codebase - the
`database.backup_enabled`/`backup_interval_hours` config values are
reserved for a future task, not wired to any running code (verified: no
reference to either key anywhere in `src/`). Until that exists, backups are
manual:

### Manual backup
The entire database is one file - copying it is a complete, consistent
backup as long as no write is in progress:
```bash
cp data/climate_risk.db data/backups/climate_risk_$(date +%Y%m%d_%H%M%S).db
```
(Create the `data/backups/` directory once: `mkdir -p data/backups`.)

### Restoring from backup
```bash
cp data/backups/climate_risk_<timestamp>.db data/climate_risk.db
```
Restart any running `SchedulerManager` process afterward - it holds no
in-memory state that depends on database contents surviving a restart, but
a restart guarantees every DAO opens a fresh connection against the
restored file.

### What's safe to delete/regenerate vs. what to actually back up
| Path | Backup? | Why |
|---|---|---|
| `data/climate_risk.db` | **Yes** | The only source of truth - properties, all historical assessments, alert history |
| `data/sample_properties.json` / `.csv` | No | Regenerable via `property_generator.py` (deterministic, fixed seed) |
| `logs/*.log` | Optional | Useful for post-incident review, not required for the system to function |
| `reports/*.txt` | No | Regenerable on demand via `PortfolioReporter` |
| `config/settings.json`, `.env` | **Yes** | Not regenerable - `.env` in particular contains your API keys |

---

## Related Documentation
- [api-reference.md](api-reference.md) - full class/function reference
- [alert-lifecycle-design.md](alert-lifecycle-design.md) - alert state machine design
- [scaling-design.md](scaling-design.md) - ingestion scaling rationale
- [implementation-plan.md](implementation-plan.md) - overall system design decisions
