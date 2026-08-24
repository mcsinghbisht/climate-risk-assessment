# Implementation Plan: Climate Risk Assessment MVP

**Status:** Planning Phase  
**Target:** Backend MVP for continuous monitoring and risk scoring  
**Timeline:** Solo project, local development  
**Date Created:** 2026-07-17

---

## Executive Summary

This plan outlines a Python-based backend system for continuous wildfire and flood risk monitoring on a portfolio of 100 properties. The system will:
- Ingest property data and external hazard APIs every 5 minutes (configurable)
- Calculate dynamic risk scores based on proximity and environmental factors
- Trigger alerts when risk thresholds are breached
- Provide portfolio-level aggregation and reporting
- Run entirely locally with no cloud dependencies

**Key Constraint:** All data must come from public domain sources.

---

## 1. Technology Stack

### Core Technologies
| Component | Choice | Rationale |
|-----------|--------|-----------|
| **Language** | Python 3.11+ | Standard for data/ML projects, rich geospatial libraries |
| **Database** | SQLite | No setup needed, file-based, sufficient for MVP at 100 properties |
| **Geospatial Library** | Shapely + GeoPandas | Calculate distances, polygons (burn areas, floodplains) |
| **Data Processing** | Pandas | Time-series analysis, property-level calculations |
| **HTTP Requests** | Requests + schedule | Fetch hazard data from public APIs on intervals |
| **Scheduler** | APScheduler or schedule library | Run batch jobs every 5 minutes |
| **Logging** | Python logging | Audit trail and debugging |
| **Storage Format** | JSON + SQLite | Configuration, sample data, runtime data |

### Dependencies Summary
```
Core:
- requests (API calls)
- pandas (data manipulation)
- geopandas (geospatial operations)
- shapely (geometric operations)
- sqlalchemy (database ORM - optional but helpful)
- apscheduler (job scheduling)

Testing:
- pytest (unit tests)
- pytest-cov (coverage)
```

---

## 2. System Architecture

### High-Level Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│                     CONTINUOUS MONITORING LOOP               │
│                     (Every 5 minutes)                         │
└─────────────────────────────────────────────────────────────┘
                              │
                    ┌─────────▼──────────┐
                    │  Fetch Hazard Data │
                    │  from Public APIs  │
                    │ (Wildfire, Flood)  │
                    └─────────┬──────────┘
                              │
                    ┌─────────▼──────────────┐
                    │ Normalize & Store      │
                    │ Hazard Data in DB      │
                    └─────────┬──────────────┘
                              │
                    ┌─────────▼──────────────┐
                    │ Load Property Data     │
                    │ from DB               │
                    └─────────┬──────────────┘
                              │
                    ┌─────────▼──────────────────────┐
                    │ Calculate Risk Scores          │
                    │ (Wildfire + Flood per property)│
                    └─────────┬──────────────────────┘
                              │
                    ┌─────────▼──────────────┐
                    │ Evaluate Alerts        │
                    │ (Compare to thresholds)│
                    └─────────┬──────────────┘
                              │
                    ┌─────────▼──────────────┐
                    │ Generate/Send Alerts   │
                    │ if thresholds breached │
                    └─────────┬──────────────┘
                              │
                    ┌─────────▼──────────────┐
                    │ Store Risk Snapshots   │
                    │ (Audit trail)          │
                    └─────────┬──────────────┘
                              │
                    ┌─────────▼──────────────┐
                    │ Aggregate Portfolio    │
                    │ Metrics               │
                    └─────────┬──────────────┘
                              │
                         ┌────▼────┐
                         │Dashboard │ (Deferred - Phase 2)
                         │Reporting │
                         └──────────┘
```

### Component Breakdown

```
src/
├── data_ingestion/
│   ├── __init__.py
│   ├── property_loader.py        # Load 100 sample properties
│   ├── wildfire_ingestion.py     # Fetch NASA FIRMS data
│   ├── flood_ingestion.py        # Fetch USGS/NOAA precipitation data
│   └── data_normalizer.py        # Normalize all hazard data to common format
│
├── risk_scoring/
│   ├── __init__.py
│   ├── wildfire_scorer.py        # Proximity-based wildfire risk
│   ├── flood_scorer.py           # Rainfall-based flood risk
│   ├── aggregator.py             # Combine wildfire + flood into overall score
│   └── scoring_config.py         # Configurable thresholds, weights
│
├── continuous_monitoring/
│   ├── __init__.py
│   ├── monitor.py                # Main monitoring loop
│   ├── scheduler.py              # APScheduler setup
│   └── state_tracker.py          # Track risk changes over time
│
├── alerts/
│   ├── __init__.py
│   ├── alert_engine.py           # Evaluate thresholds, generate alerts
│   ├── notification.py           # Send alerts (console, file, logging)
│   └── alert_config.py           # Configurable thresholds
│
├── portfolio/
│   ├── __init__.py
│   ├── aggregator.py             # Portfolio-level metrics
│   ├── hotspot_detector.py       # Identify geographic clusters
│   └── reporter.py               # Generate reports
│
├── database/
│   ├── __init__.py
│   ├── db.py                     # SQLite setup and connection
│   ├── models.py                 # SQLAlchemy models (optional)
│   └── migrations.py             # Schema versioning
│
├── config/
│   ├── __init__.py
│   ├── settings.py               # Global settings (paths, API endpoints)
│   └── logging_config.py         # Logging setup
│
├── utils/
│   ├── __init__.py
│   ├── geo_utils.py              # Distance calcs, proximity checks
│   ├── time_utils.py             # Timestamp handling
│   └── validation.py             # Data validation
│
└── main.py                        # Application entry point

config/
├── properties.json               # 100 sample properties (generated)
├── risk_thresholds.json          # Risk scoring weights and thresholds
└── api_config.json               # Public API endpoints and schedules

data/
├── sample_properties.csv         # Backup of sample data
└── hazard_sources.md             # Documentation of public APIs

tests/
├── test_data_ingestion.py
├── test_risk_scoring.py
├── test_alerts.py
├── test_geospatial.py
└── fixtures/                     # Mock hazard data for testing
```

---

## 3. Data Model & Database Schema

### SQLite Tables

#### `properties` table
```sql
CREATE TABLE properties (
    property_id INTEGER PRIMARY KEY,
    address TEXT NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    state TEXT,
    county TEXT,
    zip_code TEXT,
    construction_type TEXT,           -- "wood", "masonry", "mixed"
    elevation_m REAL,                 -- Meters above sea level
    is_in_wildland_urban_interface BOOLEAN,
    is_in_floodplain BOOLEAN,
    soil_type TEXT,                   -- For flood modeling
    drainage_class TEXT,              -- For flood modeling
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

#### `risk_assessments` table (snapshots)
```sql
CREATE TABLE risk_assessments (
    assessment_id INTEGER PRIMARY KEY,
    property_id INTEGER FOREIGN KEY,
    assessment_timestamp TIMESTAMP NOT NULL,
    wildfire_risk_score REAL,         -- 0-100
    wildfire_factors JSON,            -- Distance, wind, temp, etc.
    flood_risk_score REAL,            -- 0-100
    flood_factors JSON,               -- Rainfall, saturation, etc.
    overall_risk_score REAL,          -- Weighted combination
    risk_level TEXT,                  -- "low", "medium", "high", "critical"
    alerts_triggered JSON,
    created_at TIMESTAMP
);
```

#### `hazard_data` table (raw ingested data)
```sql
CREATE TABLE hazard_data (
    hazard_id INTEGER PRIMARY KEY,
    hazard_type TEXT,                 -- "wildfire", "flood", "weather"
    source TEXT,                      -- "NASA_FIRMS", "USGS", "NOAA"
    latitude REAL,
    longitude REAL,
    value REAL,                       -- Fire intensity, rainfall mm, etc.
    confidence REAL,                  -- Data confidence score
    observation_timestamp TIMESTAMP,  -- When the hazard was measured
    ingested_timestamp TIMESTAMP,     -- When we fetched it
    raw_data JSON                     -- Full API response for debugging
);
```

#### `alerts` table
```sql
CREATE TABLE alerts (
    alert_id INTEGER PRIMARY KEY,
    property_id INTEGER FOREIGN KEY,
    risk_type TEXT,                   -- "wildfire", "flood"
    risk_score REAL,
    threshold_exceeded REAL,
    alert_level TEXT,                 -- "warning", "critical"
    message TEXT,
    triggered_at TIMESTAMP,
    acknowledged_at TIMESTAMP,
    created_at TIMESTAMP
);
```

#### `alert_history` table (for reporting)
```sql
CREATE TABLE alert_history (
    history_id INTEGER PRIMARY KEY,
    alert_id INTEGER FOREIGN KEY,
    old_status TEXT,
    new_status TEXT,
    timestamp TIMESTAMP
);
```

---

## 4. Public Data Sources (Hazard APIs)

### Wildfire Data
**NASA FIRMS (Fire Information for Resource Management System)**
- **Endpoint:** https://firms.modaps.eosdis.nasa.gov/api/area/csv/
- **Coverage:** Global, near-real-time (24-48 hours latency)
- **Data Points:** Latitude, longitude, fire radiative power (FRP), confidence, acquisition date
- **Frequency:** Updated daily, new observations every ~24 hours
- **Authentication:** API key (free registration)
- **Limitations:** Spatial resolution ~375m, misses small fires

**NOAA Weather Data**
- **Source:** OpenWeatherMap API (free tier) or NOAA Direct API
- **Data:** Wind speed, direction, temperature, humidity
- **Frequency:** Hourly updates
- **Use:** Input to fire spread modeling

### Flood Data
**USGS Water Resources**
- **Endpoint:** https://waterservices.usgs.gov/
- **Data:** Real-time discharge, gauge height from river monitoring stations
- **Coverage:** US only, primarily major rivers
- **Frequency:** 15-minute intervals
- **Authentication:** None (open)

**NOAA Precipitation Data**
- **Source:** National Centers for Environmental Prediction (NCEP)
- **Endpoint:** https://www.ncei.noaa.gov/
- **Data:** Rainfall accumulation, forecasted precipitation
- **Frequency:** 6-hour updates
- **Coverage:** Global gridded data

**FEMA Flood Hazard Maps**
- **Source:** FEMA Flood Map Service Center
- **Data:** Historical floodplain boundaries (static)
- **Use:** Property-level floodplain assessment at setup

---

## 5. Risk Scoring Logic (MVP)

### Wildfire Risk Score

**Components:**
1. **Proximity to Active Fires** (40% weight)
   - Get active fires from NASA FIRMS
   - For each property, find nearest fire within 50km
   - Score = max(0, 100 × (1 - distance_km / 50))

2. **Wind-Driven Escalation** (30% weight)
   - Get wind speed from NOAA
   - If wind > threshold (e.g., 20 mph) AND property is upwind, increase score
   - Upwind = fire is downwind based on wind direction
   - Score multiplier: 1.0 to 1.5x

3. **Fire Intensity** (20% weight)
   - Fire Radiative Power (FRP) from NASA FIRMS
   - Normalized to 0-100 scale based on historical max

4. **Environmental Factors** (10% weight)
   - Temperature, humidity (from NOAA)
   - Inverse humidity correlation: low humidity = higher risk

**Final Wildfire Score:** `(proximity × 0.4) + (wind × 0.3) + (intensity × 0.2) + (env × 0.1)`

### Flood Risk Score

**Components:**
1. **Rainfall Accumulation** (50% weight)
   - Get precipitation from NOAA over last 72 hours
   - Normalize to 0-100 based on historical max rainfall
   - Score = min(100, cumulative_mm / max_historical_mm × 100)

2. **Proximity to Water Bodies** (20% weight)
   - Static: Load USGS river/stream data
   - For each property, distance to nearest water body
   - Score = max(0, 100 × (1 - distance_km / 20))

3. **Floodplain Status** (20% weight)
   - Is property in FEMA floodplain? (static, checked at setup)
   - In floodplain = +30 points to score
   - In "high risk" zone = +50 points

4. **Soil Saturation** (10% weight)
   - Proxy from rainfall trends and humidity
   - After heavy rainfall, soil takes days to dry → lingering risk

**Final Flood Score:** `(rainfall × 0.5) + (proximity × 0.2) + (floodplain × 0.2) + (saturation × 0.1)`

### Overall Risk Score

```
weighted_average = (wildfire_score × 0.5) + (flood_score × 0.5)

# Single-hazard override (Task 17, added after reviewing initial output):
# a pure weighted average can dilute a genuinely extreme single-hazard
# score - e.g. wildfire=100, flood=0 -> 50 under plain averaging,
# understating a property facing one severe peril rather than two
# moderate ones.
dominant_score = max(wildfire_score, flood_score)
if dominant_score >= critical_single_hazard_threshold:   # default 85
    overall_score = max(weighted_average, dominant_score)
    risk_level = "critical"
else:
    overall_score = weighted_average
    risk_level = classify(overall_score)   # see Risk Levels below
```

**Risk Levels** (used only when the single-hazard override above does not apply):
- **Green (Low):** 0-25
- **Yellow (Medium):** 26-50
- **Orange (High):** 51-75
- **Red (Critical):** 76-100 (also always forced when a single hazard >= 85)

---

## 6. Alert Thresholds (Configurable)

**Alert Triggers** (per property):
- **Wildfire:** Score increases > 40 in single update OR absolute score > 70
- **Flood:** Score increases > 30 in single update OR absolute score > 65
- **Portfolio:** > 10% of properties in "high" or "critical" state

**Alert Format:**
```json
{
  "alert_id": "ALT_20260717_PROP_042_WF",
  "property_id": 42,
  "type": "wildfire",
  "severity": "high",
  "message": "Wildfire risk increased from 35 to 68. Active fire detected 12km away. Wind: 25mph from SE (towards property).",
  "timestamp": "2026-07-17T14:23:00Z",
  "factors": {
    "nearest_fire_km": 12.0,
    "wind_speed_mph": 25,
    "wind_direction": "SE",
    "fire_intensity": "high"
  },
  "recommended_actions": [
    "Review property exposure",
    "Contact customer for evacuation readiness",
    "Flag for premium review"
  ]
}
```
*(Note: the `recommended_actions` field above was an early illustrative sketch of
where the Phase 2 Agentic AI layer's Recommendation Agent would plug in - see the
Solution Architecture document. The actual `AlertEngine`/`AlertDAO` implementation
(Tasks 20-21b) uses field names `property_id`, `risk_type`, `risk_score`,
`threshold_exceeded`, `alert_level`, `message`, `triggered_at`, `status` rather than
this exact shape - the automation layer's job is producing the structured score and
message; `recommended_actions` remains a future AI-layer addition, not yet built.)*

### Alert Lifecycle (Added in Task 21b, After Reviewing the Notification System)

An alert is not a fire-and-forget event - it has a lifecycle: **active** (just
triggered) -> **acknowledged** (a human is handling it) or **stale** (no fresh data
to confirm it's still true) -> **resolved** (risk dropped back down, with a
hysteresis buffer to prevent flapping). Re-notification for an ongoing unresolved
alert is throttled (`renotify_interval_minutes`, default 60), not repeated every
monitoring cycle. Full design, state machine, and configuration in
[alert-lifecycle-design.md](alert-lifecycle-design.md).

**Extended in Task 27** to also cover portfolio-level alerts (">10% of assessed
properties in high/critical risk") - the same lifecycle state machine, reused as-is
via `property_id=NULL, risk_type='portfolio_high_risk_pct'` rather than a second
alerting system. Required making `alerts.property_id` nullable (a genuine schema
migration, not an additive one - see "Portfolio-Level Alerts" in
[alert-lifecycle-design.md](alert-lifecycle-design.md#portfolio-level-alerts-task-27-extension)).

---

## 7. Sample Property Data

**100 properties will be generated** with:
- Real-world-like addresses (mix of high-risk and low-risk zones)
- Geographic distribution across:
  - **High wildfire risk zones:** California (20 props), Arizona (15 props), Colorado (10 props)
  - **Flood risk zones:** Louisiana (15 props), Texas (10 props), Florida (10 props)
  - **Mixed risk:** Other states (10 props)
- Construction types: wood, masonry, mixed (realistic distribution)
- Floodplain status: ~20% in FEMA floodplain, 80% outside
- WUI (Wildland-Urban Interface) status: ~30% in WUI, 70% outside

**Sample property record:**
```json
{
  "property_id": 1,
  "address": "123 Pine Ridge Road, Idyllwild, CA 92549",
  "latitude": 33.7521,
  "longitude": -116.7277,
  "state": "CA",
  "county": "Riverside",
  "construction_type": "wood",
  "elevation_m": 1650,
  "is_in_wildland_urban_interface": true,
  "is_in_floodplain": false,
  "soil_type": "sandy_loam",
  "drainage_class": "well_drained"
}
```

---

## 8. Implementation Phases

### Phase 1: Foundation (Week 1-2)
- [x] Project structure and documentation
- [ ] SQLite database schema and setup
- [ ] Property data generation (100 properties)
- [ ] Basic data models and utilities
- [ ] Logging and configuration framework

**Deliverable:** Database with sample properties, fully queryable

---

### Phase 2: Data Ingestion (Week 2-3)
- [ ] NASA FIRMS wildfire data ingestion
- [ ] NOAA weather data ingestion
- [ ] USGS river gauge data ingestion
- [ ] Data normalization pipeline
- [ ] Error handling and logging for API failures

**Deliverable:** Live data flowing into database every 5 minutes

---

### Phase 3: Risk Scoring (Week 3-4)
- [ ] Wildfire risk calculator
- [ ] Flood risk calculator
- [ ] Risk aggregator (property-level)
- [ ] Risk snapshot storage (audit trail)
- [ ] Unit tests for scoring logic

**Deliverable:** Risk scores calculated and stored for all properties every 5 minutes

---

### Phase 4: Alerts & Monitoring (Week 4-5)
- [ ] Alert engine and thresholds
- [ ] Alert notification system (console, file, logging)
- [ ] Change detection (score increased from last assessment)
- [ ] Alert history tracking

**Deliverable:** Alerts triggered and logged when thresholds breached

---

### Phase 5: Portfolio Aggregation (Week 5-6)
- [ ] Portfolio-level metrics (% in each risk level)
- [ ] Hotspot detection (geographic clustering)
- [ ] Summary reporting
- [ ] Dashboard-ready data aggregation

**Deliverable:** Portfolio view showing risk distribution

---

### Phase 6: Testing & Hardening (Week 6)
- [ ] Full test suite
- [ ] Manual testing with real APIs
- [ ] Stress testing (performance at 100 properties)
- [ ] Documentation

**Deliverable:** Production-ready MVP

---

## 9. Configuration & Flexibility

**Key Configurable Parameters** (config/settings.json):

```json
{
  "monitoring": {
    "interval_minutes": 5,
    "enabled": true
  },
  "risk_scoring": {
    "wildfire_weights": {
      "proximity": 0.4,
      "wind": 0.3,
      "intensity": 0.2,
      "environment": 0.1
    },
    "flood_weights": {
      "rainfall": 0.5,
      "proximity": 0.2,
      "floodplain": 0.2,
      "saturation": 0.1
    },
    "overall_weights": {
      "wildfire": 0.5,
      "flood": 0.5
    }
  },
  "alerts": {
    "wildfire_threshold": 70,
    "wildfire_increase_threshold": 40,
    "flood_threshold": 65,
    "flood_increase_threshold": 30,
    "portfolio_threshold_percent": 10
  },
  "data_sources": {
    "nasa_firms": {
      "enabled": true,
      "api_key": "YOUR_API_KEY"
    },
    "noaa": {
      "enabled": true
    },
    "usgs": {
      "enabled": true
    }
  }
}
```

---

## 10. Key Technical Decisions & Trade-offs

| Decision | Choice | Rationale | Trade-off |
|----------|--------|-----------|-----------|
| **Database** | SQLite | Zero setup, file-based, sufficient for 100 properties | Not suitable for 100k+ properties, would need migration later |
| **Scheduling** | APScheduler | Reliable cron-like scheduling, Python-native | Runs in single process, not distributed |
| **Geospatial** | Shapely + GeoPandas | Simple distance/proximity calcs, no server needed | Limited to Cartesian calcs, may need PostGIS for complex queries at scale |
| **Risk Model** | Proximity-based | Simple, explainable, low compute | Not sophisticated ML, but sufficient for MVP |
| **Data Format** | JSON config | Human-readable, version-controllable | Less structured than database, need validation |
| **Batch Processing** | Every 5 min | Frequent enough for "near real-time" behavior | Misses hazards between batches, but API rate limits are okay |
| **Public APIs Only** | FIRMS + NOAA/OpenWeather + USGS | Free, no subscriptions, open data | Lower resolution/latency than commercial, gaps in data coverage |
| **Local Deployment** | SQLite + file storage | Zero infrastructure, works on laptop | Not scalable beyond laptop, no redundancy |
| **Hazard Data Ingestion Strategy** | Per geographic grid-cell, not per-property (Task 14) | API call volume scales with geographic footprint, not portfolio size — same design works at 100 or 100,000+ properties. See [scaling-design.md](scaling-design.md) | Coarser spatial resolution within a cell (default 0.5°/~55km); tunable via config |

---

## 11. Success Criteria for MVP

- ✅ 100 properties loaded into database
- ✅ Live hazard data flowing in every 5 minutes from public APIs
- ✅ Risk scores calculated and stored for all properties
- ✅ Alerts triggered when thresholds breached
- ✅ Portfolio-level metrics computed and available
- ✅ Full audit trail (risk snapshots and alert history)
- ✅ All configurable via JSON (no code changes needed to adjust thresholds/intervals)
- ✅ Comprehensive logging for debugging
- ✅ Basic unit and integration tests

---

## 12. Future Enhancements (Post-MVP)

- **Web Dashboard:** Flask/Streamlit UI for visualization
- **Advanced ML:** Time-series forecasting, anomaly detection
- **Commercial Data:** Integration with premium data providers for better accuracy
- **Cloud Deployment:** AWS/GCP for scale beyond laptop
- **Underwriting Integration:** API endpoints for underwriting system
- **Historical Analysis:** Trend analysis, model performance tracking
- **Compliance:** Audit logs, access controls, data governance

---

## 13. Timeline Estimate

| Phase | Duration | Effort |
|-------|----------|--------|
| Phase 1: Foundation | 3-4 days | Setup, schemas, sample data |
| Phase 2: Data Ingestion | 4-5 days | API integration, error handling |
| Phase 3: Risk Scoring | 3-4 days | Algorithm implementation |
| Phase 4: Alerts | 2-3 days | Thresholds, notifications |
| Phase 5: Portfolio | 2-3 days | Aggregation, reporting |
| Phase 6: Testing | 3-4 days | Full test suite, hardening |
| **Total** | **4-5 weeks** | Solo development |

**Actual timeline depends on:**
- Complexity of public APIs (unexpected rate limits, data inconsistencies)
- Testing and debugging complexity
- Iterations based on testing results

---

## 14. Development Workflow

**Getting Started:**
```bash
# 1. Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# 2. Install dependencies
pip install -r requirements.txt

# 3. Initialize database
python src/database/db.py

# 4. Load sample properties
python src/data_ingestion/property_loader.py

# 5. Start monitoring system
python src/main.py

# 6. Run tests
pytest tests/
```

**Development Loop:**
1. Write tests first (TDD approach)
2. Implement feature
3. Run tests locally
4. Commit to git with clear messages
5. Review code with /code-review

**Git Strategy:**
- Main branch = stable
- Feature branches for each component (feature/wildfire-scoring, etc.)
- Commit after each phase

---

## 15. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Public APIs rate-limited (esp. at scale) | No new data, stale assessments | **Implemented (Task 14):** shared `RateLimiter` per provider + geographic grid-cell ingestion, so call volume scales with geographic footprint rather than portfolio size — see [scaling-design.md](scaling-design.md). Each ingester also degrades gracefully if a source is down (Tasks 10-12). |
| NASA FIRMS has gaps (misses fires) | Missed risks | Supplement with secondary sources, document limitations |
| API latency > 5 min schedule | Stale data | Freshness-aware skip (Task 14) avoids redundant calls; async fetching remains a future option if cell count grows large enough to need it |
| Database grows large (1 year of snapshots) | Slow queries | Archive old data, implement indexes early |
| Geospatial calculations slow | Performance issues | Pre-compute distances, spatial indexes, optimize queries |
| Scheduling drifts (jobs delay) | Inconsistent monitoring | Add job failure alerts, health checks |

---

## Document Status

- **Created:** 2026-07-17
- **Phase:** Planning (Ready for Phase 1 implementation)
- **Next Step:** Begin Phase 1 - Foundation setup

---

## Related Documentation

- [CLAUDE.md](../CLAUDE.md) — Project vision and overview
- [reference-principles.md](reference-principles.md) — Design principles
