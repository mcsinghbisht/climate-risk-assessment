# API Reference

Complete reference for every public class and function in `src/`, organized
by module. Each entry lists parameters, return type, and a one-line
description; classes include a short usage example. Private helpers
(names starting with `_`) are omitted except where documenting a public
method's behavior requires mentioning one.

This document is generated from the codebase as of Task 31 (2026-08-03) -
30 completed tasks across Phases 1-5. For design rationale behind
*why* something works the way it does, see
[implementation-plan.md](implementation-plan.md),
[alert-lifecycle-design.md](alert-lifecycle-design.md), and
[scaling-design.md](scaling-design.md).

**Table of Contents**
1. [Configuration](#1-configuration)
2. [Database](#2-database)
3. [Utilities](#3-utilities)
4. [Data Ingestion](#4-data-ingestion)
5. [Risk Scoring](#5-risk-scoring)
6. [Alerts](#6-alerts)
7. [Continuous Monitoring](#7-continuous-monitoring)
8. [Portfolio](#8-portfolio)

---

## 1. Configuration

### `src.config.get_config() -> ConfigManager`
Returns the process-wide singleton `ConfigManager`, loading `config/settings.json`
on first call.

### `class ConfigManager`
Loads, validates, and provides typed access to `config/settings.json`.

| Method | Parameters | Returns | Description |
|---|---|---|---|
| `__init__` | `settings_path: Optional[Path] = None` | - | Loads and validates settings from the given path (default `config/settings.json`) |
| `reload()` | - | `None` | Re-reads the settings file from disk |
| `get(key_path, default=None)` | `key_path: str` (dot-separated, e.g. `"alerts.wildfire_threshold"`) | `Any` | Dotted-path lookup with a default fallback |
| `get_required(key_path)` | `key_path: str` | `Any` | Same as `get()` but raises if the key is missing |
| `get_section(section)` | `section: str` | `dict` | Returns an entire top-level config section |
| `as_dict()` | - | `dict` | Full config as a plain dict |
| `validate()` | - | `tuple(bool, List[str])` | Checks the config against expected structure |

```python
from src.config import get_config

config = get_config()
threshold = config.get("alerts.wildfire_threshold", 70)
alerts_cfg = config.get_section("alerts")
```

### `src.config.setup_logging(config_path=None, force=False) -> None`
Configures the project's logging framework (console + `logs/app.log` +
`logs/errors.log` + a dedicated `"alerts"` logger to `logs/alerts.log`).
Call once near process start; `force=True` re-configures even if already set up.

### `src.config.is_configured() -> bool`
Whether `setup_logging()` has already run in this process.

---

## 2. Database

All DAOs open and close their own SQLite connection per call (no persistent
connection pool) - simple and correct at this project's scale (Task 3, 21b).

### `src.database.get_db_connection() -> sqlite3.Connection`
Opens a connection to `data/climate_risk.db` with `row_factory = sqlite3.Row`
(so rows support both index and key access, e.g. `row["property_id"]`).

### `src.database.get_schema() -> Dict[str, str]`
Returns `{table_name: CREATE TABLE ddl}` for every table (`properties`,
`hazard_data`, `risk_assessments`, `alerts`, `alert_history`, `schema_version`).

### `src.database.initialize_database() -> None`
Creates all tables (if not already present) and indexes.

### `src.database.verify_database() -> tuple(bool, List[str])`
Checks that every expected table exists; returns `(ok, list of problems)`.

### `src.database.drop_all_tables() -> tuple(bool, str)`
Drops every table. **Destructive** - used by test fixtures and manual resets only.

### `class MigrationManager`
| Method | Returns | Description |
|---|---|---|
| `get_current_version()` | `int` | Reads `schema_version` table |
| `is_up_to_date()` | `bool` | Compares against `SCHEMA_VERSION` constant |
| `needs_migration()` | `bool` | Inverse of `is_up_to_date()` |
| `record_migration(version, description)` | `None` | Appends a migration record |

### `class PropertyDAO`
Read-only accessors over the `properties` table.

| Method | Parameters | Returns |
|---|---|---|
| `get_all_properties()` | - | `List[Dict]`, ordered by `property_id` |
| `get_property_by_id(property_id)` | `int` | `Optional[Dict]` |
| `get_properties_by_state(state)` | `str` | `List[Dict]` |
| `get_properties_in_floodplain()` | - | `List[Dict]` |
| `get_properties_in_wui()` | - | `List[Dict]` |
| `count_properties()` | - | `int` |

```python
from src.database import PropertyDAO

properties = PropertyDAO().get_all_properties()
ca_properties = PropertyDAO().get_properties_by_state("CA")
```

### `class RiskDAO`
Persists and reads `risk_assessments` (Task 18). Never upserts - every
`save_assessment()` call inserts a new row, so history is preserved.

| Method | Parameters | Returns | Description |
|---|---|---|---|
| `save_assessment(assessment, alerts_triggered=None)` | `assessment: Dict` (see `RiskAggregator.build_overall_assessment()` shape) | `int` (new `assessment_id`) | Inserts one assessment row |
| `get_latest_assessment(property_id)` | `int` | `Optional[Dict]` | Most recent assessment for one property |
| `get_assessment_history(property_id, days=30)` | `int, int` | `List[Dict]`, newest first | All assessments within N days |
| `get_all_latest_assessments()` | - | `List[Dict]` | The single latest assessment per property, portfolio-wide |

```python
from src.database import RiskDAO

risk_dao = RiskDAO()
history = risk_dao.get_assessment_history(property_id=1, days=1)
current, previous = (history[0], history[1] if len(history) > 1 else None)
```

### `class AlertDAO`
Persists alerts and manages their full lifecycle (Task 21b, extended in
Task 27 for portfolio-level alerts). Full design in
[alert-lifecycle-design.md](alert-lifecycle-design.md).

| Method | Parameters | Returns | Description |
|---|---|---|---|
| `save_new_alerts(alerts)` | `List[Dict]` (`AlertEngine` output shape) | `List[int]` | Inserts new alerts, or updates the matching ongoing alert instead of duplicating. Returns IDs of *genuinely new* rows only |
| `evaluate_lifecycle(property_id, risk_type, current_score, latest_assessment_timestamp)` | `Optional[int], str, float, Optional[str]` | `List[Dict]` | Re-evaluates every active/acknowledged alert for this property+risk_type (staleness -> resolution -> unchanged); `property_id=None` targets the portfolio-level alert |
| `should_notify(alert_id)` | `int` | `bool` | Whether the re-notification cooldown has elapsed |
| `mark_notified(alert_id)` | `int` | `None` | Records that a notification was just sent |
| `get_active_alerts()` | - | `List[Dict]` | All `active`/`stale` alerts, portfolio-wide |
| `get_alerts_for_property(property_id, include_resolved=False)` | `Optional[int], bool` | `List[Dict]` | Alerts for one property (or portfolio-level, if `None`) |
| `acknowledge_alert(alert_id)` | `int` | `bool` | Marks an alert `acknowledged` |

```python
from src.database import AlertDAO

alert_dao = AlertDAO()
active = alert_dao.get_active_alerts()
for alert in active:
    if alert_dao.should_notify(alert["alert_id"]):
        # ... send it ...
        alert_dao.mark_notified(alert["alert_id"])
```

---

## 3. Utilities

### `src.utils.geo_utils`

| Function | Signature | Returns |
|---|---|---|
| `calculate_distance` | `(lat1, lon1, lat2, lon2) -> float` | Haversine distance in km. Raises `ValueError` on invalid coordinates |
| `is_valid_coordinate` | `(lat, lon) -> bool` | Range + NaN/Infinity check |
| `get_bearing` | `(lat1, lon1, lat2, lon2) -> float` | Bearing in degrees (0-360), point 1 -> point 2 |
| `is_downwind` | `(fire_lat, fire_lon, property_lat, property_lon, wind_direction) -> bool` | Whether the property is within 45° of the wind's downwind direction from the fire |
| `get_distance_category` | `(distance_km) -> str` | `"immediate"` (<5km) / `"near"` (<20) / `"moderate"` (<50) / `"far"` |
| `haversine_distance` | alias of `calculate_distance` | `float` |
| `assign_grid_cell` | `(lat, lon, cell_size_degrees=0.5) -> Tuple[float, float]` | Centroid of the grid cell containing this point (Task 14 ingestion scaling) |

### `src.utils.time_utils`
All timestamps are UTC-aware (`datetime` with `timezone.utc`).

| Function | Signature | Returns |
|---|---|---|
| `get_utc_now` | `() -> datetime` | Current UTC time |
| `get_utc_timestamp_str` | `() -> str` | Current time, ISO 8601 with `Z` suffix |
| `hours_ago` / `minutes_ago` / `days_ago` / `seconds_ago` | `(n) -> datetime` | N units before now, UTC |
| `time_since` | `(timestamp) -> float` | Seconds elapsed since `timestamp` |
| `is_older_than` | `(timestamp, hours) -> bool` | Whether `timestamp` predates `hours_ago(hours)` |
| `is_within_hours` | `(timestamp, hours) -> bool` | Inverse of `is_older_than` |
| `get_monitoring_cycle_time` / `get_last_cycle_time` | `(interval_minutes=5) -> datetime` | Current/previous cycle boundary |
| `next_cycle_in` | `(interval_minutes=5) -> float` | Seconds until the next cycle boundary |
| `format_timestamp` | `(timestamp, format_str="%Y-%m-%d %H:%M:%S") -> str` | Formatted string |
| `parse_iso_timestamp` | `(timestamp_str) -> datetime` | Parses ISO 8601 (handles trailing `Z`); raises `ValueError` if invalid |
| `get_date_range` | `(days=7) -> Tuple[datetime, datetime]` | `(start, end)` |
| `is_business_hours` | `(timestamp=None) -> bool` | 9 AM-5 PM UTC |

### `src.utils.validation`
Every function returns `(is_valid: bool, errors: List[str])`.

| Function | Validates |
|---|---|
| `validate_coordinate(lat, lon)` | Coordinate range and type |
| `validate_property_data(property_dict)` | Required fields, coordinate validity, field types |
| `validate_risk_score(risk_score, risk_type="overall")` | 0-100 range, numeric |
| `validate_risk_assessment(assessment_dict)` | Required fields, embedded scores, `risk_level` enum |
| `validate_hazard_data(hazard_dict)` | Required fields, coordinates, `hazard_type` enum, `confidence`/`value` |
| `validate_alert(alert_dict)` | Required fields, `risk_type`/`alert_level` enums, embedded score |

```python
from src.utils import validate_property_data

is_valid, errors = validate_property_data({"address": "123 Main St"})
# is_valid == False; errors == ["Missing required field: latitude", "Missing required field: longitude"]
```

---

## 4. Data Ingestion

### `class WildFireIngester` (NASA FIRMS)
| Method | Parameters | Returns |
|---|---|---|
| `fetch_active_fires(lat_min, lat_max, lon_min, lon_max, days=None)` | bounding box (degrees), lookback days (1-5, clamped) | `List[Dict]` normalized fire records. Empty on disabled/missing key/request failure - never raises |
| `store_fires(fires)` | `List[Dict]` | `int` records stored |

### `class WeatherIngester` (OpenWeatherMap)
| Method | Parameters | Returns |
|---|---|---|
| `fetch_weather(latitude, longitude)` | point coordinates | `Optional[Dict]` normalized weather record |
| `store_weather(weather)` | `Dict` | `bool` |

### `class FloodIngester` (USGS + OpenWeatherMap)
| Method | Parameters | Returns |
|---|---|---|
| `fetch_river_gauges(lat_min, lat_max, lon_min, lon_max)` | bounding box | `List[Dict]` normalized gauge records |
| `fetch_precipitation(latitude, longitude)` | point coordinates | `Optional[Dict]` (wraps its own internal `WeatherIngester`) |
| `store_records(records)` | `List[Dict]` | `int` records stored |

### `class DataNormalizer`
Converts each raw API response shape into the common `hazard_data` record
format. `max_gauge_reading_age_hours` (default 48) filters stale USGS readings.

| Method | Parameters | Returns |
|---|---|---|
| `normalize_fire(row)` | one FIRMS CSV row (dict) | `Optional[Dict]` |
| `normalize_weather(data, latitude, longitude)` | raw OpenWeatherMap JSON + queried coords | `Optional[Dict]` |
| `normalize_precipitation(weather_raw_response, latitude, longitude, observation_timestamp)` | - | `Dict` (rainfall defaults to 0.0, not an error, when absent) |
| `normalize_gauge(series)` | one USGS `timeSeries` entry | `Optional[Dict]`, `None` if stale or malformed |

### `class RateLimiter`
| Method | Parameters | Returns |
|---|---|---|
| `__init__(calls_per_minute)` | `int` | - |
| `wait_if_needed()` | - | `float` seconds slept |
| `reset()` | - | `None` |

### `class IngestionEngine`
Orchestrates all three ingesters across the whole portfolio using
grid-cell grouping (Task 14, [scaling-design.md](scaling-design.md)).

| Method | Returns | Description |
|---|---|---|
| `run_ingestion_cycle()` | `Dict`: `fires_ingested, weather_points, precipitation_points, gauge_readings, cells_processed, cells_skipped_fresh, errors` | One full ingestion cycle |

```python
from src.data_ingestion.ingestion_engine import IngestionEngine

summary = IngestionEngine().run_ingestion_cycle()
print(f"{summary['fires_ingested']} fires, {summary['errors']} errors")
```

### Property generation/loading (Task 7)
| Function | Returns |
|---|---|
| `generate_properties(seed=42) -> List[Dict]` | 100 synthetic properties across configured state distributions |
| `save_to_json(properties, path=...)` / `save_to_csv(...)` | `None` |
| `load_properties_from_json(path=...) -> List[Dict]` | Reads generated properties back |
| `load_all_properties(json_path=...) -> Dict` | Validates + upserts every property into the database |

---

## 5. Risk Scoring

### `class WildFireScorer`
Four weighted factors: proximity (0.4), wind escalation (0.3), intensity (0.2),
environment (0.1) - all weights/thresholds config-driven.

| Method | Parameters | Returns |
|---|---|---|
| `calculate_risk_for_property(property_data, hazard_data)` | property dict (needs `latitude`/`longitude`), list of hazard_data rows | `{"score": float, "factors": Dict, "explanation": str}` |

### `class FloodScorer`
Four weighted factors: rainfall (0.5), proximity-to-water (0.2), floodplain
status (0.2), soil saturation proxy (0.1).

| Method | Parameters | Returns |
|---|---|---|
| `calculate_risk_for_property(property_data, hazard_data)` | property dict (needs `latitude`/`longitude`/`is_in_floodplain`), hazard rows | `{"score": float, "factors": Dict, "explanation": str}` |

### `class RiskAggregator`
Combines wildfire + flood scores. Applies a **single-hazard override**: if
either score >= `critical_single_hazard_threshold` (default 85), the overall
score is raised to at least that score and `risk_level` is forced to `"critical"`
- see [implementation-plan.md](implementation-plan.md) §"Overall Risk Score".

| Method | Parameters | Returns |
|---|---|---|
| `classify_risk_level(score)` | `float` | `"low"`/`"medium"`/`"high"`/`"critical"` |
| `aggregate_scores(wildfire_score, flood_score)` | `float, float` | `{"overall_score", "risk_level", "breakdown"}` |
| `build_overall_assessment(property_data, wildfire_result, flood_result)` | property dict + both scorers' output | Full assessment dict, shaped exactly for `RiskDAO.save_assessment()` |

```python
from src.risk_scoring import WildFireScorer, FloodScorer, RiskAggregator

wildfire_result = WildFireScorer().calculate_risk_for_property(property_data, hazard_data)
flood_result = FloodScorer().calculate_risk_for_property(property_data, hazard_data)
assessment = RiskAggregator().build_overall_assessment(property_data, wildfire_result, flood_result)
```

### `class RiskScoringEngine`
Orchestrates scoring across the entire portfolio in one call (Task 19).

| Method | Returns | Description |
|---|---|---|
| `score_all_properties()` | `Dict`: `properties_scored, average_risk, high_risk_count, critical_count, errors` | Scores + persists an assessment for every property; one property's failure doesn't stop the rest |

---

## 6. Alerts

### `class AlertEngine`
Pure threshold-crossing logic - no persistence, no state (Task 20, extended Task 27).

| Method | Parameters | Returns |
|---|---|---|
| `evaluate_property(property_id, current_risk, previous_risk=None)` | `int`, `{"wildfire": score, "flood": score}` x2 | `List[Dict]` alert dicts (0-4, since each hazard type independently checks both an absolute threshold and a sudden-increase threshold) |
| `evaluate_portfolio(high_critical_percent)` | `float` (0-100) | `Optional[Dict]` - a single `critical`-level alert if the portfolio-wide high/critical percentage exceeds `portfolio_threshold_percent` |

### `class Notifier`
Formats and dispatches alerts to the `"alerts"` logger (console + `logs/alerts.log`).

| Method | Parameters | Returns |
|---|---|---|
| `send_alert(alert)` | one alert dict | `None` |
| `send_alerts(alerts)` | `List[Dict]` | `int` count sent |

```python
from src.alerts import AlertEngine, Notifier

alerts = AlertEngine().evaluate_property(1, {"wildfire": 85, "flood": 10}, {"wildfire": 20, "flood": 10})
Notifier().send_alerts(alerts)
```

---

## 7. Continuous Monitoring

### `class ChangeDetector`
Compares two assessments; independent of alert thresholds (Task 22).

| Method | Parameters | Returns |
|---|---|---|
| `detect_changes(property_id, current_assessment, previous_assessment=None)` | property_id + two `risk_assessments`-shaped dicts | `{"property_id", "changed", "is_baseline", "risk_delta", "risk_level_changed", "trend", "factors_changed"}` |

### `class Monitor`
The production entrypoint: one full cycle (ingest -> score -> change-detect
-> alert -> notify), including the portfolio-level alert (Task 23, 27).

| Method | Returns |
|---|---|
| `run_monitoring_cycle()` | `Dict`: `cycle_timestamp, hazard_records_ingested, properties_scored, new_alerts, notifications_sent, errors` |

```python
from src.continuous_monitoring import Monitor

summary = Monitor().run_monitoring_cycle()
```

### `class SchedulerManager`
Runs `Monitor.run_monitoring_cycle()` on a recurring interval via APScheduler
(Task 24). `max_instances=1` + `coalesce=True` guarantee cycles never overlap.

| Method | Description |
|---|---|
| `start()` | Begins the recurring schedule (interval from `alerts.alert_check_interval_minutes`, default 5 min) |
| `stop(wait=True)` | Graceful shutdown |
| `is_running` (property) | `bool` |

```python
from src.continuous_monitoring import SchedulerManager

scheduler = SchedulerManager()
scheduler.start()
# ... application runs ...
scheduler.stop()
```

---

## 8. Portfolio

### `class PortfolioAggregator`
Read-only, side-effect-free portfolio-wide statistics (Task 25).

| Method | Returns |
|---|---|
| `get_portfolio_metrics()` | `Dict`: `total_properties, assessed_properties, risk_level_distribution, geographic_distribution, score_stats, latest_assessment_timestamp` |

### `class HotspotDetector`
Geographic clustering of elevated risk (Task 26).

| Method | Parameters | Returns |
|---|---|---|
| `detect_hotspots(radius_km=None)` | optional override of configured `portfolio.hotspot_radius_km` (default 50) | `List[Dict]`: `center_lat, center_lon, property_count, avg_risk, properties: [{property_id, risk_score}]` |

### `class PortfolioReporter`
Combines the above plus active alerts into a text report (Task 27).

| Method | Parameters | Returns |
|---|---|---|
| `generate_summary_report(write_to_file=True)` | - | `str` report; also writes `reports/portfolio_YYYY-MM-DD.txt` |

```python
from src.portfolio import PortfolioAggregator, HotspotDetector, PortfolioReporter

metrics = PortfolioAggregator().get_portfolio_metrics()
hotspots = HotspotDetector().detect_hotspots()
report = PortfolioReporter().generate_summary_report()
```

---

## Coverage Check

Verified against the codebase per the task spec:

```bash
grep -r "^def \|^class " src/ | grep -v __pycache__ | wc -l
# 74 top-level definitions across 30 files
```

Every public class listed above; private helpers (`_leading_underscore`)
are intentionally omitted as they're implementation details, not part of
the supported interface. Module-level `if __name__ == "__main__":` demo
blocks are also omitted - each is a runnable example (`python -m src.<module>`),
not a public API surface.
