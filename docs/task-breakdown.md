# Task Breakdown: Climate Risk Assessment MVP

**Purpose:** Small, independent, verifiable tasks that build toward the full MVP  
**Each task:** ~30min to 2 hours, one clear outcome, easy to verify  
**Format:** Numbered, organized by phase

---

## Phase 1: Foundation Setup

### Task 1: Initialize Python Project Structure
**Outcome:** Project folders created, requirements.txt with dependencies, .gitignore configured  
**Files Created/Modified:**
- `requirements.txt` (create)
- `.gitignore` (update with Python-specific patterns)
- Verify folder structure exists:
  - `src/` (all subdirectories from implementation-plan)
  - `tests/`
  - `config/`
  - `data/`

**Dependencies:** None  
**Verify:**
```bash
# Should see all folders
ls -R src/
# Should see requirements.txt
cat requirements.txt
```

---

### Task 2: Set Up Virtual Environment & Install Dependencies
**Outcome:** Virtual environment created, all dependencies installed, can import modules  
**Files Created/Modified:**
- `venv/` (created)
- `requirements.txt` (already has all dependencies)

**Dependencies:** Task 1  
**Verify:**
```bash
# Activate venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Test imports work
python -c "import pandas; import geopandas; import shapely; import requests; print('All imports successful')"
```

---

### Task 3: Create SQLite Database Schema
**Outcome:** SQLite database initialized with all 6 tables (properties, risk_assessments, hazard_data, alerts, alert_history, + metadata)  
**Files Created/Modified:**
- `src/database/__init__.py` (create)
- `src/database/db.py` (create) - main database setup
- `src/database/migrations.py` (create) - schema version tracking
- `data/climate_risk.db` (created by script)
- `data/schema.sql` (create - optional, backup schema definition)

**Dependencies:** Task 2  
**Verify:**
```bash
# Run database setup
python src/database/db.py

# Check database exists and tables created
sqlite3 data/climate_risk.db ".tables"
# Should show: properties, risk_assessments, hazard_data, alerts, alert_history, schema_version

# Check schema of properties table
sqlite3 data/climate_risk.db ".schema properties"
# Should show all columns: property_id, address, latitude, longitude, etc.
```

---

### Task 4: Create Utility Functions (Geospatial & Time)
**Outcome:** Utility modules with distance calculation, coordinate validation, timestamp handling  
**Files Created/Modified:**
- `src/utils/__init__.py` (create)
- `src/utils/geo_utils.py` (create) - functions for:
  - `calculate_distance(lat1, lon1, lat2, lon2)` - returns km
  - `is_valid_coordinate(lat, lon)` - returns bool
  - `get_bearing(lat1, lon1, lat2, lon2)` - returns degrees
- `src/utils/time_utils.py` (create) - functions for:
  - `get_utc_now()` - returns datetime
  - `hours_ago(hours)` - returns datetime
- `src/utils/validation.py` (create) - functions for:
  - `validate_property_data(dict)` - returns (is_valid, errors)
  - `validate_coordinate(lat, lon)` - returns bool

**Dependencies:** Task 2  
**Verify:**
```bash
# Test distance calculation
python -c "
from src.utils.geo_utils import calculate_distance
dist = calculate_distance(33.7521, -116.7277, 33.9425, -116.7953)
print(f'Distance: {dist:.1f} km')  # Should be ~20km
assert 19 < dist < 21, 'Distance calculation off'
"

# Test coordinate validation
python -c "
from src.utils.validation import validate_coordinate
assert validate_coordinate(33.75, -116.72), 'Valid coord should pass'
assert not validate_coordinate(91, 0), 'Invalid lat should fail'
print('Coordinate validation working')
"

# Test timestamp utility
python -c "
from src.utils.time_utils import get_utc_now, hours_ago
now = get_utc_now()
past = hours_ago(24)
assert (now - past).total_seconds() > 86000, 'Hours ago calculation off'
print('Time utilities working')
"
```

---

### Task 5: Create Configuration System
**Outcome:** Configuration files created and config module to load them; settings accessible from anywhere in code  
**Files Created/Modified:**
- `config/settings.json` (create) - main config file with:
  - monitoring interval (5 minutes)
  - risk thresholds (wildfire 70, flood 65, etc.)
  - API endpoints and keys (placeholders)
  - weights for risk scoring
- `config/logging_config.json` (create) - logging setup
- `src/config/__init__.py` (create)
- `src/config/settings.py` (create) - ConfigManager class to:
  - Load JSON configs
  - Validate required fields
  - Return nested config values
  - Hot-reload capability (optional)

**Dependencies:** Task 1  
**Verify:**
```bash
# Test config loading
python -c "
from src.config.settings import ConfigManager
cfg = ConfigManager()
interval = cfg.get('monitoring.interval_minutes')
print(f'Monitoring interval: {interval}')
assert interval == 5, 'Should load 5 minutes from config'

wildfire_thresh = cfg.get('alerts.wildfire_threshold')
print(f'Wildfire threshold: {wildfire_thresh}')
assert wildfire_thresh == 70, 'Should load threshold from config'
"

# Verify config file is valid JSON
python -c "import json; json.load(open('config/settings.json'))"
```

---

### Task 6: Set Up Logging Framework
**Outcome:** Logging configured globally; all modules can log with proper formatting, levels, and rotation  
**Files Created/Modified:**
- `src/config/logging_config.py` (create) - setup_logging() function that:
  - Creates logs/ directory
  - Configures file handler (logs/app.log with rotation)
  - Configures console handler
  - Sets up proper formatting with timestamps
- `logs/` directory (created by first run)

**Dependencies:** Task 5  
**Verify:**
```bash
# Run a simple test that logs
python -c "
from src.config.logging_config import setup_logging
import logging
setup_logging()
logger = logging.getLogger(__name__)
logger.info('Test log message')
logger.warning('Test warning')
print('Check logs/app.log should have messages')
"

# Verify log file exists and has content
cat logs/app.log
# Should show timestamps, levels, and messages
```

---

## Phase 2: Data Ingestion - Properties

### Task 7: Generate 100 Sample Properties
**Outcome:** 100 realistic property records generated and ready to load into DB  
**Files Created/Modified:**
- `src/data_ingestion/__init__.py` (create)
- `src/data_ingestion/property_generator.py` (create) - function to:
  - Generate 100 properties with realistic data
  - Mix of high/low risk zones (CA, AZ, CO for wildfire; LA, TX, FL for flood)
  - Include coordinates, addresses, construction type, elevation, floodplain status
- `data/sample_properties.json` (create) - JSON file with all 100 properties
- `data/sample_properties.csv` (create) - CSV backup

**Dependencies:** Task 1  
**Verify:**
```bash
# Verify JSON is valid and has 100 properties
python -c "
import json
props = json.load(open('data/sample_properties.json'))
print(f'Generated {len(props)} properties')
assert len(props) == 100, 'Should have exactly 100 properties'

# Check one property has all required fields
prop = props[0]
required = ['property_id', 'address', 'latitude', 'longitude', 'state', 'county', 'construction_type', 'is_in_wildland_urban_interface', 'is_in_floodplain']
for field in required:
    assert field in prop, f'Missing field: {field}'
    
print(f'Sample property: {prop[\"address\"]} at ({prop[\"latitude\"]}, {prop[\"longitude\"]})')
"

# Verify geographic distribution
python -c "
import json
props = json.load(open('data/sample_properties.json'))
states = {}
for p in props:
    state = p['state']
    states[state] = states.get(state, 0) + 1
print('Properties by state:', sorted(states.items()))
# Should have CA, AZ, CO (wildfire) and LA, TX, FL (flood)
"

# Verify CSV is readable
head -5 data/sample_properties.csv
```

---

### Task 8: Load Sample Properties into Database
**Outcome:** All 100 properties inserted into `properties` table in SQLite  
**Files Created/Modified:**
- `src/data_ingestion/property_loader.py` (create) - function to:
  - Read sample_properties.json
  - Validate each property
  - Insert into DB with timestamps
  - Log success/failures
  - Handle duplicates gracefully

**Dependencies:** Task 3, Task 7  
**Verify:**
```bash
# Run loader
python src/data_ingestion/property_loader.py

# Check properties in database
sqlite3 data/climate_risk.db "SELECT COUNT(*) FROM properties;"
# Should return 100

# Check one property
sqlite3 data/climate_risk.db "SELECT property_id, address, latitude, longitude, state FROM properties LIMIT 1;"

# Verify geographic spread
sqlite3 data/climate_risk.db "SELECT state, COUNT(*) FROM properties GROUP BY state ORDER BY state;"
# Should show CA, AZ, CO, FL, LA, TX, etc.

# Check timestamps
sqlite3 data/climate_risk.db "SELECT COUNT(*) FROM properties WHERE created_at IS NOT NULL;"
# Should return 100
```

---

### Task 9: Create Property Data Access Layer
**Outcome:** Simple module to query properties from DB; all property reads go through this  
**Files Created/Modified:**
- `src/database/property_dao.py` (create) - class PropertyDAO with methods:
  - `get_all_properties()` - returns list of all properties as dicts
  - `get_property_by_id(id)` - returns single property
  - `get_properties_by_state(state)` - filters by state
  - `get_properties_in_floodplain()` - filters by floodplain
  - `get_properties_in_wui()` - filters by WUI status
  - `count_properties()` - returns total count

**Dependencies:** Task 3, Task 8  
**Verify:**
```bash
# Test data access
python -c "
from src.database.property_dao import PropertyDAO
dao = PropertyDAO()

# Test count
count = dao.count_properties()
print(f'Total properties: {count}')
assert count == 100, 'Should have 100 properties'

# Test get all
props = dao.get_all_properties()
assert len(props) == 100, 'get_all should return 100'

# Test get by ID
prop = dao.get_property_by_id(1)
assert prop['property_id'] == 1, 'Should return correct property'
print(f'Property 1: {prop[\"address\"]}')

# Test filtering
ca_props = dao.get_properties_by_state('CA')
print(f'Properties in CA: {len(ca_props)}')

# Test floodplain
flood_props = dao.get_properties_in_floodplain()
print(f'Properties in floodplain: {len(flood_props)}')
"
```

---

## Phase 2: Data Ingestion - Hazard Data APIs

### Task 10: Create Wildfire API Ingestion (NASA FIRMS)
**Outcome:** Live wildfire data fetched from NASA FIRMS API, parsed, validated, stored in DB  
**Files Created/Modified:**
- `src/data_ingestion/wildfire_ingestion.py` (create) - WildFireIngester class with:
  - `fetch_active_fires(lat_min, lat_max, lon_min, lon_max, days=7)` - get fires from NASA FIRMS
  - Parse response (lat, lon, frp, confidence, timestamp)
  - Validate coordinates and values
  - Store in `hazard_data` table with source='NASA_FIRMS', hazard_type='wildfire'
  - Log all API calls and errors

**Dependencies:** Task 2, Task 3, Task 6  
**Verify:**
```bash
# Manually test NASA FIRMS API call
python -c "
from src.data_ingestion.wildfire_ingestion import WildFireIngester
ingester = WildFireIngester()

# Get recent fires for California
fires = ingester.fetch_active_fires(lat_min=32, lat_max=42, lon_min=-124, lon_max=-114, days=7)
print(f'Found {len(fires)} active fires')
# Should return 0-10+ depending on current conditions

# Check first fire has required fields
if fires:
    fire = fires[0]
    assert 'latitude' in fire, 'Missing latitude'
    assert 'longitude' in fire, 'Missing longitude'
    assert 'frp' in fire, 'Missing FRP'
    assert 'confidence' in fire, 'Missing confidence'
    print(f'Sample fire: lat={fire[\"latitude\"]}, lon={fire[\"longitude\"]}, frp={fire[\"frp\"]}')
else:
    print('No active fires (expected depending on season)')
"

# Check stored in database
sqlite3 data/climate_risk.db "SELECT COUNT(*) FROM hazard_data WHERE source='NASA_FIRMS';"
```

---

### Task 11: Create Weather API Ingestion (NOAA/OpenWeather)
**Outcome:** Live weather data (wind, temp, humidity) fetched and stored for risk modeling  
**Files Created/Modified:**
- `src/data_ingestion/weather_ingestion.py` (create) - WeatherIngester class with:
  - `fetch_weather(latitude, longitude)` - get current weather
  - Support multiple providers (OpenWeatherMap free tier as primary)
  - Parse wind speed, direction, temperature, humidity
  - Validate and normalize values
  - Store in `hazard_data` table with source='WEATHER', hazard_type='weather'

**Dependencies:** Task 2, Task 3, Task 6  
**Verify:**
```bash
# Test weather API fetch
python -c "
from src.data_ingestion.weather_ingestion import WeatherIngester
ingester = WeatherIngester()

# Get weather for a sample location (California property)
weather = ingester.fetch_weather(lat=33.7521, lon=-116.7277)
print(f'Weather at Idyllwild: temp={weather.get(\"temperature\")}, wind={weather.get(\"wind_speed\")}, humidity={weather.get(\"humidity\")}')

# Check required fields
assert 'temperature' in weather, 'Missing temperature'
assert 'wind_speed' in weather, 'Missing wind speed'
assert 'wind_direction' in weather, 'Missing wind direction'
assert 'humidity' in weather, 'Missing humidity'
"

# Verify stored in DB
sqlite3 data/climate_risk.db "SELECT COUNT(*) FROM hazard_data WHERE hazard_type='weather';"
```

---

### Task 12: Create Flood API Ingestion (USGS/NOAA Precipitation)
**Outcome:** Precipitation and river data fetched from USGS/NOAA, validated, stored  
**Files Created/Modified:**
- `src/data_ingestion/flood_ingestion.py` (create) - FloodIngester class with:
  - `fetch_precipitation(lat_min, lat_max, lon_min, lon_max)` - get rainfall data
  - `fetch_river_gauges(lat_min, lat_max, lon_min, lon_max)` - get river levels from USGS
  - Parse responses (rainfall mm, gauge height, discharge)
  - Validate and normalize
  - Store in `hazard_data` table with source='USGS'/'NOAA', hazard_type='flood'

**Dependencies:** Task 2, Task 3, Task 6  
**Verify:**
```bash
# Test flood data fetch
python -c "
from src.data_ingestion.flood_ingestion import FloodIngester
ingester = FloodIngester()

# Get flood data for Louisiana
precip = ingester.fetch_precipitation(lat_min=28, lat_max=32, lon_min=-94, lon_max=-88)
print(f'Found {len(precip)} precipitation records')

# Check structure
if precip:
    rec = precip[0]
    assert 'latitude' in rec, 'Missing lat'
    assert 'longitude' in rec, 'Missing lon'
    assert 'value' in rec, 'Missing rainfall value'
    print(f'Sample: rainfall={rec[\"value\"]}mm')
"

# Verify stored in DB
sqlite3 data/climate_risk.db "SELECT COUNT(*) FROM hazard_data WHERE hazard_type='flood';"
```

---

### Task 13: Create Data Normalizer Pipeline
**Outcome:** All hazard data normalized to consistent format before storage; handles different API response formats  
**Files Created/Modified:**
- `src/data_ingestion/data_normalizer.py` (create) - DataNormalizer class with:
  - `normalize_fire(raw_api_response)` - standardize fire data
  - `normalize_weather(raw_response)` - standardize weather data
  - `normalize_precipitation(raw_response)` - standardize rainfall data
  - `normalize_gauge(raw_response)` - standardize river gauge data
  - Consistent output format: `{latitude, longitude, value, confidence, timestamp, metadata}`
  - Validation and error logging

**Dependencies:** Task 10, Task 11, Task 12  
**Verify:**
```bash
# Test normalization
python -c "
from src.data_ingestion.data_normalizer import DataNormalizer
normalizer = DataNormalizer()

# Test fire normalization
raw_fire = {
    'latitude': 33.5,
    'longitude': -116.2,
    'frp': 250.5,
    'confidence': 95
}
normalized = normalizer.normalize_fire(raw_fire)
print(f'Normalized fire: {normalized}')
assert normalized['latitude'] == 33.5
assert normalized['confidence'] == 0.95  # Should normalize 0-1
assert 'timestamp' in normalized

# Test weather normalization
raw_weather = {'temp': 85, 'wind': 15, 'humidity': 45}
normalized = normalizer.normalize_weather(raw_weather)
print(f'Normalized weather: {normalized}')
assert 'temperature' in normalized
assert 'wind_speed' in normalized
"
```

---

### Task 14: Integrate Ingestion into Single Data Ingestion Pipeline
**Outcome:** Single orchestrated flow that fetches all hazard data across the entire
property portfolio, normalizes, and stores it — designed to scale from 100 properties
to 100,000+ without code changes, by querying hazard data per **geographic cell**
rather than per property.

**Design rationale (see `docs/scaling-design.md` for full detail):** weather and flood
conditions vary by location, not by individual property. Two properties 500m apart
share essentially the same weather. Fetching hazard data once per property (100 calls
at MVP scale) becomes catastrophic at production scale (100,000+ calls per 5-minute
cycle would blow through every free-tier API limit). Instead, properties are grouped
into geographic grid cells; hazard data is fetched **once per cell**, then matched to
properties by proximity at risk-scoring time (Task 15+), not at ingestion time. API
call volume scales with geographic footprint, not portfolio size.

**Files Created/Modified:**
- `src/utils/geo_utils.py` (modify) — add `assign_grid_cell(lat, lon, cell_size_degrees)`,
  returning the cell's centroid coordinates for a given point
- `src/data_ingestion/rate_limiter.py` (create) — `RateLimiter` class:
  - `__init__(calls_per_minute: int)`
  - `wait_if_needed()` — sleeps just long enough to stay under the configured limit
  - One shared, reusable component wrapped around each ingester's HTTP calls,
    configured per-provider (not hardcoded per-ingester)
- `src/data_ingestion/ingestion_engine.py` (create) — `IngestionEngine` class:
  - `run_ingestion_cycle()` — orchestrates all data fetches across all cells
  - Groups all properties (via `PropertyDAO`) into grid cells
  - For each cell: fetches wildfire (bbox), gauges (bbox), weather + precipitation
    (cell centroid point), rate-limited per source
  - **Freshness-aware skip:** before fetching, checks whether a sufficiently recent
    `hazard_data` reading already exists for that cell/source this cycle — skips
    the API call if so, keeping cycle time bounded as cell count grows
  - **Error isolation:** one source failing (e.g., NASA FIRMS down) does not prevent
    the others from completing — matches the graceful degradation already built into
    each individual ingester (Tasks 10-12), now guaranteed at the orchestration level too
  - Returns summary: `{fires_ingested, weather_points, precipitation_points,
    gauge_readings, cells_processed, cells_skipped_fresh, errors: [...]}`
- `config/settings.json` (modify) — add per-source `calls_per_minute`, and
  `grid_cell_size_degrees` under a new `ingestion` config section

**Dependencies:** Task 9, Task 10, Task 11, Task 12, Task 13

**Verify:**
```bash
# Run full ingestion pipeline across the real 100-property portfolio
python -m src.data_ingestion.ingestion_engine

# Confirm hazard data now spans multiple states, not just one demo location
python tools/query.py "SELECT source, COUNT(*) FROM hazard_data GROUP BY source;"

# Confirm cell count is much smaller than property count (proving the
# geographic-cell design, not a 1-call-per-property pattern)
# summary['cells_processed'] should be roughly 10-15, not 100
```

---

## Phase 3: Risk Scoring

### Task 15: Implement Wildfire Risk Scoring Algorithm
**Outcome:** Wildfire risk score calculated based on proximity, wind, intensity, environment  
**Files Created/Modified:**
- `src/risk_scoring/__init__.py` (create)
- `src/risk_scoring/wildfire_scorer.py` (create) - WildFireScorer class with:
  - `calculate_risk_for_property(property, hazard_data)` - main method
  - `_score_proximity(property_lat, property_lon, fires)` - proximity component
  - `_score_wind_escalation(fire_lat, fire_lon, property_lat, property_lon, wind_speed, wind_dir)` - wind component
  - `_score_intensity(frp)` - fire intensity component
  - `_score_environment(temp, humidity)` - environmental component
  - Returns: `{score: 0-100, factors: {...}, explanation: "..."}`

**Dependencies:** Task 9, Task 14  
**Verify:**
```bash
# Test wildfire scoring
python -c "
from src.risk_scoring.wildfire_scorer import WildFireScorer
scorer = WildFireScorer()

# Create mock property and hazard data
property_data = {'property_id': 1, 'latitude': 33.75, 'longitude': -116.72}
hazard_data = [
    {'latitude': 33.70, 'longitude': -116.70, 'frp': 250, 'type': 'fire'},  # ~10km away
    {'latitude': 33.75, 'longitude': -116.72, 'wind_speed': 25, 'wind_direction': 90, 'type': 'weather'}
]

result = scorer.calculate_risk_for_property(property_data, hazard_data)
print(f'Wildfire risk: {result[\"score\"]:.1f}')
print(f'Factors: {result[\"factors\"]}')
assert 0 <= result['score'] <= 100, 'Score should be 0-100'
assert 'factors' in result, 'Should return factors'
assert 'explanation' in result, 'Should return explanation'
"
```

---

### Task 16: Implement Flood Risk Scoring Algorithm
**Outcome:** Flood risk score calculated based on rainfall, proximity to water, floodplain, saturation  
**Files Created/Modified:**
- `src/risk_scoring/flood_scorer.py` (create) - FloodScorer class with:
  - `calculate_risk_for_property(property, hazard_data)` - main method
  - `_score_rainfall(precipitation_72h)` - rainfall component
  - `_score_proximity_to_water(property_lat, property_lon, water_bodies)` - proximity component
  - `_score_floodplain(is_in_floodplain)` - floodplain status component
  - `_score_soil_saturation(recent_rainfall, humidity)` - soil saturation component
  - Returns: `{score: 0-100, factors: {...}, explanation: "..."}`

**Dependencies:** Task 9, Task 14  
**Verify:**
```bash
# Test flood scoring
python -c "
from src.risk_scoring.flood_scorer import FloodScorer
scorer = FloodScorer()

property_data = {'property_id': 1, 'latitude': 29.5, 'longitude': -91.5, 'is_in_floodplain': True}
hazard_data = [
    {'latitude': 29.5, 'longitude': -91.5, 'value': 150, 'type': 'precipitation'},  # 150mm
    {'latitude': 29.4, 'longitude': -91.4, 'value': 2.5, 'type': 'gauge_height'}    # River level
]

result = scorer.calculate_risk_for_property(property_data, hazard_data)
print(f'Flood risk: {result[\"score\"]:.1f}')
print(f'Factors: {result[\"factors\"]}')
assert 0 <= result['score'] <= 100, 'Score should be 0-100'
"
```

---

### Task 17: Create Risk Score Aggregator
**Outcome:** Combines wildfire and flood scores into single overall risk score and risk level  
**Files Created/Modified:**
- `src/risk_scoring/aggregator.py` (create) - RiskAggregator class with:
  - `aggregate_scores(wildfire_score, flood_score)` - combines two scores with weights
  - Returns: `{overall_score: 0-100, risk_level: "low"/"medium"/"high"/"critical", breakdown: {...}}`
  - Respects configurable weights (default 50/50)
  - **Single-hazard override** (added after initial implementation, based on review):
    a pure weighted average can dilute a genuinely extreme single-hazard score (e.g.
    wildfire=100, flood=0 -> 50/medium under 50/50 averaging). If either individual
    score is >= `risk_scoring.critical_single_hazard_threshold` (default 85),
    `overall_score` is raised to at least that dominant score and `risk_level` is
    forced to `"critical"` - an extreme single peril is never hidden by averaging
    against a calm second peril.

**Dependencies:** Task 5, Task 15, Task 16  
**Verify:**
```bash
# Test aggregation
python -c "
from src.risk_scoring.aggregator import RiskAggregator
agg = RiskAggregator()

result = agg.aggregate_scores(wildfire_score=60, flood_score=40)
print(f'Overall risk: {result[\"overall_score\"]:.1f}')
print(f'Risk level: {result[\"risk_level\"]}')
assert result['overall_score'] == 50.0, 'Should average 50'
assert result['risk_level'] == 'medium', 'Should be medium'

result = agg.aggregate_scores(wildfire_score=85, flood_score=90)
assert result['risk_level'] == 'critical', 'High scores should be critical'
"
```

---

### Task 18: Create Risk Assessment Storage & Retrieval
**Outcome:** Risk scores stored as snapshots in DB; can retrieve history and latest scores  
**Files Created/Modified:**
- `src/database/risk_dao.py` (create) - RiskDAO class with:
  - `save_assessment(property_id, wildfire_score, wildfire_factors, flood_score, flood_factors, overall_score, risk_level, alerts)` - store snapshot
  - `get_latest_assessment(property_id)` - get most recent score
  - `get_assessment_history(property_id, days=30)` - get historical trend
  - `get_all_latest_assessments()` - all properties' latest scores

**Dependencies:** Task 3  
**Verify:**
```bash
# Test risk storage
python -c "
from src.database.risk_dao import RiskDAO
dao = RiskDAO()

# Save a risk assessment
dao.save_assessment(
    property_id=1,
    wildfire_score=60,
    wildfire_factors={'proximity_km': 15, 'wind_speed': 20},
    flood_score=30,
    flood_factors={'rainfall_mm': 20},
    overall_score=45,
    risk_level='medium',
    alerts=[]
)

# Retrieve it
latest = dao.get_latest_assessment(1)
print(f'Latest score for prop 1: {latest[\"overall_score\"]}')
assert latest['overall_score'] == 45

# Check in database
import sqlite3
conn = sqlite3.connect('data/climate_risk.db')
c = conn.cursor()
c.execute('SELECT COUNT(*) FROM risk_assessments WHERE property_id=1')
count = c.fetchone()[0]
assert count > 0, 'Should be stored'
conn.close()
"
```

---

### Task 19: Create Risk Scoring Orchestrator
**Outcome:** Single module that calculates risk for all 100 properties in one run  
**Files Created/Modified:**
- `src/risk_scoring/scoring_engine.py` (create) - RiskScoringEngine class with:
  - `score_all_properties()` - main orchestration method
  - Fetches latest hazard data from DB
  - Iterates through all properties
  - Calculates wildfire + flood scores
  - Aggregates into overall score
  - Stores snapshots
  - Returns summary: `{properties_scored: 100, average_risk: X, high_risk_count: Y, critical_count: Z}`

**Dependencies:** Task 15, Task 16, Task 17, Task 18  
**Verify:**
```bash
# Run full scoring
python -c "
from src.risk_scoring.scoring_engine import RiskScoringEngine
engine = RiskScoringEngine()
summary = engine.score_all_properties()
print(f'Scored {summary[\"properties_scored\"]} properties')
print(f'Average risk: {summary[\"average_risk\"]:.1f}')
print(f'High risk: {summary[\"high_risk_count\"]}')
print(f'Critical: {summary[\"critical_count\"]}')
"

# Verify all 100 are scored
sqlite3 data/climate_risk.db "SELECT COUNT(DISTINCT property_id) FROM risk_assessments;"
# Should return 100
```

---

## Phase 4: Alerts & Monitoring

### Task 20: Create Alert Threshold Engine
**Outcome:** Evaluates risk scores against thresholds; detects when properties breach limits  
**Files Created/Modified:**
- `src/alerts/__init__.py` (create)
- `src/alerts/alert_engine.py` (create) - AlertEngine class with:
  - `evaluate_property(property_id, current_risk, previous_risk)` - check if alert should trigger
  - Compare absolute score vs threshold (e.g., wildfire_score > 70)
  - Compare score increase vs delta threshold (e.g., increase > 40 since last assessment)
  - Consider both risk types independently
  - Returns: `[alert_objects]` or `[]` if no alerts

**Dependencies:** Task 5, Task 18  
**Verify:**
```bash
# Test alert evaluation
python -c "
from src.alerts.alert_engine import AlertEngine
engine = AlertEngine()

# Property crosses absolute threshold
alerts = engine.evaluate_property(
    property_id=1,
    current_risk={'wildfire': 75, 'flood': 30},  # Wildfire crosses 70 threshold
    previous_risk={'wildfire': 60, 'flood': 30}
)
print(f'Alerts generated: {len(alerts)}')
assert len(alerts) >= 1, 'Should trigger wildfire alert'

# Property has a large increase (45 points - must exceed wildfire_increase_threshold=40
# from config/settings.json; a 35-point increase, as an earlier draft of this example
# used, does NOT cross that threshold and was corrected here after actually running it)
alerts = engine.evaluate_property(
    property_id=2,
    current_risk={'wildfire': 60, 'flood': 60},  # Increased 45 points
    previous_risk={'wildfire': 15, 'flood': 60}
)
assert len(alerts) >= 1, 'Should trigger increase alert'
"
```

---

### Task 21: Create Alert Notification System
**Outcome:** Alerts formatted and output to console/file/logs; easy to extend to email/SMS later  
**Files Created/Modified:**
- `src/alerts/notification.py` (create) - Notifier class with:
  - `send_alert(alert)` - main method
  - Console output (formatted, readable)
  - File output (alerts.log)
  - Structured logging (for parsing)
  - Support multiple notification channels (initially console + file)

**Dependencies:** Task 6, Task 20  
**Verify:**
```bash
# Create and send a test alert
python -c "
from src.alerts.notification import Notifier
notifier = Notifier()

alert = {
    'alert_id': 'TEST_001',
    'property_id': 1,
    'risk_type': 'wildfire',
    'message': 'Wildfire risk increased to 75',
    'timestamp': '2026-07-17T14:30:00Z'
}
notifier.send_alert(alert)
print('Alert sent')
"

# Check console output appeared (should print)
# Check logs/alerts.log exists
cat logs/alerts.log
# Should have alert content
```

---

### Task 21b: Alert Persistence & Lifecycle Management
**Outcome:** Alerts are durably persisted, deduplicated across repeated evaluation
cycles, and carry a full lifecycle (active -> acknowledged/stale -> resolved) - so a
future delivery channel (email, dashboard, Slack) never needs to reimplement "don't
re-notify about something already pending" or "is this still true." Inserted between
Tasks 21 and 22 after reviewing the notification system's output and identifying
that alerts were never persisted anywhere queryable. Full design rationale in
[alert-lifecycle-design.md](alert-lifecycle-design.md).

**Files Created/Modified:**
- `data/schema.sql` / `src/database/db.py` (modify) - additive schema change to
  `alerts`: new `status` column (`active`/`acknowledged`/`stale`/`resolved`,
  default `active`), `resolved_at`, `last_notified_at`
- `src/database/alert_dao.py` (create) - `AlertDAO` class:
  - `save_new_alerts(alerts)` - inserts new alerts, or updates an existing
    active/acknowledged row for the same property_id + risk_type instead of
    creating a duplicate; records every status transition in `alert_history`
  - `get_active_alerts()` - all alerts where `status IN ('active', 'stale')`
  - `get_alerts_for_property(property_id, include_resolved=False)`
  - `acknowledge_alert(alert_id)` - sets `status='acknowledged'`
  - `evaluate_lifecycle(property_id, risk_type, current_score, latest_assessment_timestamp)` -
    applies the resolution-hysteresis and staleness rules to an existing alert
- `src/database/__init__.py` (modify) - export `AlertDAO`
- `config/settings.json` (modify) - add `alerts.renotify_interval_minutes` (60),
  `alerts.resolution_hysteresis` (10), `alerts.stale_after_hours` (6)

**Dependencies:** Task 3, Task 18, Task 20, Task 21

**Verify:**
```bash
# A new alert is persisted once, not duplicated on repeated evaluation
python -c "
from src.database import AlertDAO
dao = AlertDAO()

alerts = [{'property_id': 1, 'risk_type': 'wildfire', 'risk_score': 80,
           'threshold_exceeded': 70, 'alert_level': 'critical',
           'message': 'test', 'triggered_at': '2026-07-23T10:00:00Z'}]

ids_first = dao.save_new_alerts(alerts)
ids_second = dao.save_new_alerts(alerts)  # same condition, re-evaluated
print(f'First save: {len(ids_first)} new row(s)')
print(f'Second save (same condition): {len(ids_second)} new row(s)')
assert len(ids_first) == 1
assert len(ids_second) == 0, 'Should not duplicate an already-active alert'
"

# Resolution with hysteresis, and staleness detection, are covered by the
# pytest suite (tests/test_alert_dao_pytest.py) rather than a one-off script,
# since they depend on time-based comparisons.
```

---

### Task 22: Implement Change Detection (Score Comparison)
**Outcome:** Tracks property risk over time; detects when risk changed significantly  
**Files Created/Modified:**
- `src/continuous_monitoring/__init__.py` (create)
- `src/continuous_monitoring/change_detector.py` (create) - ChangeDetector class with:
  - `detect_changes(property_id, current_assessment, previous_assessment)` - compare assessments
  - Returns: `{changed: bool, risk_delta: X, factors_changed: [...]}`

**Dependencies:** Task 18  
**Verify:**
```bash
# Test change detection
python -c "
from src.continuous_monitoring.change_detector import ChangeDetector
detector = ChangeDetector()

current = {'overall_score': 65, 'risk_level': 'high', 'timestamp': '14:30'}
previous = {'overall_score': 50, 'risk_level': 'medium', 'timestamp': '14:25'}

changes = detector.detect_changes(1, current, previous)
print(f'Changed: {changes[\"changed\"]}')
print(f'Delta: {changes[\"risk_delta\"]}')
assert changes['changed'], 'Should detect change'
assert changes['risk_delta'] == 15, 'Should be +15'
"
```

---

### Task 23: Create Continuous Monitoring Loop
**Outcome:** Main loop that runs every 5 minutes: ingest → score → alert → store  
**Files Created/Modified:**
- `src/continuous_monitoring/monitor.py` (create) - Monitor class with:
  - `run_monitoring_cycle()` - single cycle (ingest → score → alert)
  - Orchestrates all components in correct order
  - Error handling: logs failures but doesn't crash
  - Returns: `{cycle_timestamp, hazard_records: X, properties_scored: 100, alerts_triggered: Y}`
- Update `src/config/logging_config.py` to log cycle starts/ends

**Dependencies:** Task 14, Task 19, Task 20, Task 21  
**Verify:**
```bash
# Run a single monitoring cycle
python -c "
from src.continuous_monitoring.monitor import Monitor
monitor = Monitor()
result = monitor.run_monitoring_cycle()
print(f'Cycle complete: {result}')
# Should show: hazard records ingested, 100 properties scored, X alerts

# Check logs
tail -20 logs/app.log
# Should show cycle start/end with details
"
```

---

### Task 24: Set Up Scheduled Execution (APScheduler)
**Outcome:** Monitoring runs automatically every 5 minutes; can start/stop from code  
**Files Created/Modified:**
- `src/continuous_monitoring/scheduler.py` (create) - SchedulerManager class with:
  - `start()` - start scheduler, begin 5-minute cycles
  - `stop()` - stop scheduler gracefully
  - Configurable interval from settings.json
  - Handles missed cycles (reschedules if one takes > 5 min)
  - Health checks: logs successful/failed cycles

**Dependencies:** Task 23, Task 5  
**Verify:**
```bash
# Start scheduler and let it run for 10 minutes
python -c "
from src.continuous_monitoring.scheduler import SchedulerManager
import time

scheduler = SchedulerManager()
scheduler.start()
print('Scheduler started, running for 20 seconds...')
time.sleep(20)
scheduler.stop()
print('Scheduler stopped')
"

# Check logs
tail -50 logs/app.log
# Should show multiple cycle executions (every 5 min)
```

---

## Phase 5: Portfolio Aggregation

### Task 25: Create Portfolio-Level Metrics Aggregator
**Outcome:** Calculate portfolio-wide statistics from individual property scores  
**Files Created/Modified:**
- `src/portfolio/__init__.py` (create)
- `src/portfolio/aggregator.py` (create) - PortfolioAggregator class with:
  - `get_portfolio_metrics()` - returns aggregate stats
  - Properties by risk level: count & percentage in each level (low/med/high/crit)
  - Geographic distribution: count by state/county
  - Average risk score, median, min, max
  - Timestamp of latest assessment

**Dependencies:** Task 18  
**Verify:**
```bash
# Get portfolio metrics
python -c "
from src.portfolio.aggregator import PortfolioAggregator
agg = PortfolioAggregator()
metrics = agg.get_portfolio_metrics()
print(f'Total properties: {metrics[\"total_properties\"]}')
print(f'Risk distribution: {metrics[\"by_risk_level\"]}')
# low: 50, medium: 30, high: 15, critical: 5 (example)
print(f'Average risk: {metrics[\"average_risk\"]:.1f}')
print(f'Geographic distribution: {metrics[\"by_state\"]}')
"
```

---

### Task 26: Implement Hotspot Detection
**Outcome:** Identify geographic clusters where many properties have high risk  
**Files Created/Modified:**
- `src/portfolio/hotspot_detector.py` (create) - HotspotDetector class with:
  - `detect_hotspots(radius_km=50)` - find clusters
  - Uses property coordinates and risk scores
  - Spatial clustering: find areas where properties within radius_km have avg risk > threshold
  - Returns: `[{center_lat, center_lon, property_count, avg_risk, properties: []}]`

**Dependencies:** Task 9, Task 18  
**Verify:**
```bash
# Detect hotspots
python -c "
from src.portfolio.hotspot_detector import HotspotDetector
detector = HotspotDetector()
hotspots = detector.detect_hotspots(radius_km=50)
print(f'Found {len(hotspots)} hotspots')
for hs in hotspots:
    print(f'  Hotspot at ({hs[\"center_lat\"]:.2f}, {hs[\"center_lon\"]:.2f}): {hs[\"property_count\"]} properties, avg risk {hs[\"avg_risk\"]:.1f}')
"
```

---

### Task 27: Create Portfolio Reporter (+ Portfolio-Level Alerting)
**Outcome:** Generate text-based portfolio summary reports; extensible for PDF/HTML later.
Also implements the portfolio-level alert deferred from Task 20/21b (">10% of
properties in high/critical") - design in
[alert-lifecycle-design.md](alert-lifecycle-design.md#portfolio-level-alerts-task-27-extension).
**Files Created/Modified:**
- `src/database/db.py`, `data/schema.sql` - `alerts.property_id` becomes nullable
  (portfolio alerts aren't about one property)
- `src/database/alert_dao.py` - idempotent table-rebuild migration for the nullable
  column; `property_id = ?` comparisons changed to the null-safe `property_id IS ?`
- `src/alerts/alert_engine.py` - `evaluate_portfolio()`: same threshold-crossing
  logic as `evaluate_property()`, keyed on `risk_type='portfolio_high_risk_pct'`,
  `property_id=None`
- `src/continuous_monitoring/monitor.py` - one portfolio-level check per cycle
  (compute via `PortfolioAggregator`, evaluate/persist/notify via the same
  `AlertEngine`/`AlertDAO`/`Notifier` path as property alerts) alongside the
  existing per-property loop
- `src/portfolio/reporter.py` (create) - PortfolioReporter class with:
  - `generate_summary_report()` - text report of portfolio status
  - Includes metrics (Task 25), hotspots (Task 26), and alerts summary (including
    the portfolio-level alert, if active)
  - Timestamp and data freshness info
  - Output to console and file (reports/portfolio_YYYY-MM-DD.txt)
- `config/settings.json` - new `alerts.portfolio_resolution_hysteresis_percent`

**Dependencies:** Task 25, Task 26  
**Verify:**
```bash
# Generate report
python -c "
from src.portfolio.reporter import PortfolioReporter
reporter = PortfolioReporter()
report = reporter.generate_summary_report()
print(report)
"

# Check report file created
ls -la reports/
# Should have portfolio_*.txt files
```

---

## Phase 6: Testing & Documentation

### Task 28: Write Unit Tests for Utilities
**Outcome:** All utility functions have test coverage  
**Files Created/Modified:**
- `tests/test_utils.py` (create)
  - test_calculate_distance
  - test_validate_coordinates
  - test_timestamp_functions
  - ≥80% coverage of utils/

**Dependencies:** Task 4  
**Verify:**
```bash
pytest tests/test_utils.py -v
# All tests should pass
pytest tests/test_utils.py --cov=src/utils --cov-report=term-missing
# Should show >80% coverage
```

---

### Task 29: Write Unit Tests for Risk Scoring
**Outcome:** Risk scoring logic has test coverage; edge cases handled  
**Files Created/Modified:**
- `tests/test_risk_scoring.py` (create)
  - test_wildfire_scorer_proximity
  - test_wildfire_scorer_wind_escalation
  - test_flood_scorer_rainfall
  - test_aggregator_score_combination
  - Test edge cases: score=0, score=100, missing data, invalid coords
  - ≥85% coverage of risk_scoring/

**Dependencies:** Task 15, Task 16, Task 17  
**Verify:**
```bash
pytest tests/test_risk_scoring.py -v
pytest tests/test_risk_scoring.py --cov=src/risk_scoring --cov-report=term-missing
# Should show >85% coverage
```

---

### Task 30: Write Integration Tests (Scenario-Based)
**Outcome:** End-to-end tests of key workflows; can run offline with mock data  
**Files Created/Modified:**
- `tests/fixtures/mock_hazard_data.json` (create) - sample fire, weather, flood data
- `tests/test_integration.py` (create)
  - test_full_monitoring_cycle: ingest → score → alert → store
  - test_property_scoring_with_nearby_fire
  - test_flood_risk_in_floodplain
  - test_portfolio_aggregation
  - Use mock API responses to run offline

**Dependencies:** All previous tasks  
**Verify:**
```bash
pytest tests/test_integration.py -v
# All integration tests pass without live API calls
```

---

### Task 31: Create API Reference Documentation
**Outcome:** Document all public functions, classes, return types  
**Files Created/Modified:**
- `docs/api-reference.md` (create)
  - Document all classes and methods
  - Include parameters, return types, examples
  - Cover: data ingestion, risk scoring, alerts, portfolio

**Dependencies:** All tasks complete  
**Verify:**
```bash
# Verify all public functions documented
grep -r "^def " src/ | wc -l
# Compare with documented functions in docs/api-reference.md
```

---

### Task 32: Create Deployment & Ops Guide
**Outcome:** How to run the system, configure it, monitor it, troubleshoot it  
**Files Created/Modified:**
- `docs/operations-guide.md` (create)
  - Installation & setup steps
  - Configuration walkthrough (settings.json)
  - How to run the monitoring loop
  - Monitoring health: logs to check, what's normal
  - Troubleshooting: common errors and fixes
  - Data backup procedures

**Dependencies:** All tasks complete  
**Verify:**
```bash
# Can a new user follow the guide?
# Review for clarity, completeness
```

---

### Task 33: Performance Testing
**Outcome:** System can handle 100 properties in < 5 minutes per cycle  
**Files Created/Modified:**
- `tests/test_performance.py` (create)
  - test_scoring_all_100_properties: < 2 minutes
  - test_ingestion_cycle: < 1 minute
  - Memory usage: < 500MB

**Dependencies:** All previous tasks  
**Verify:**
```bash
pytest tests/test_performance.py -v
# All performance tests pass
# Time output shows cycle < 5 min total
```

---

### Task 34: Create Main Application Entry Point
**Outcome:** Single script to run the entire system; configurable via CLI args  
**Files Created/Modified:**
- `src/main.py` (update or create)
  - `main()` function that:
    - Parses CLI args (--mode run/test/report, --duration, --interval)
    - Sets up logging, database, configs
    - Starts scheduler (if mode=run)
    - Runs single cycle (if mode=test)
    - Generates report (if mode=report)
  - Graceful shutdown on Ctrl+C

**Dependencies:** All previous tasks  
**Verify:**
```bash
# Run single test cycle
python src/main.py --mode test
# Should complete one full monitoring cycle

# Generate report
python src/main.py --mode report
# Should output portfolio summary

# Show help
python src/main.py --help
# Should list all available modes and options
```

---

## Summary Table

| Task # | Task Name | Phase | Dependencies | Est. Time |
|--------|-----------|-------|--------------|-----------|
| 1 | Project structure & requirements | 1 | None | 30min |
| 2 | Virtual environment setup | 1 | T1 | 15min |
| 3 | Database schema | 1 | T2 | 45min |
| 4 | Utility functions | 1 | T2 | 45min |
| 5 | Configuration system | 1 | T1 | 45min |
| 6 | Logging framework | 1 | T5 | 30min |
| 7 | Generate 100 properties | 2a | T1 | 45min |
| 8 | Load properties to DB | 2a | T3,T7 | 30min |
| 9 | Property data access layer | 2a | T3,T8 | 30min |
| 10 | Wildfire API ingestion | 2b | T2,T3,T6 | 1hr |
| 11 | Weather API ingestion | 2b | T2,T3,T6 | 1hr |
| 12 | Flood API ingestion | 2b | T2,T3,T6 | 1hr |
| 13 | Data normalizer | 2b | T10,T11,T12 | 1hr |
| 14 | Integrate ingestion pipeline (grid-cell + rate limiter) | 2b | T9-T13 | 2.5hr |
| 15 | Wildfire scoring algorithm | 3 | T9,T14 | 1.5hr |
| 16 | Flood scoring algorithm | 3 | T9,T14 | 1.5hr |
| 17 | Score aggregator | 3 | T5,T15,T16 | 45min |
| 18 | Risk storage & retrieval | 3 | T3 | 1hr |
| 19 | Scoring orchestrator | 3 | T15-T18 | 1hr |
| 20 | Alert threshold engine | 4 | T5,T18 | 1hr |
| 21 | Alert notification system | 4 | T6,T20 | 1hr |
| 21b | Alert persistence & lifecycle | 4 | T3,T18,T20,T21 | 2hr |
| 22 | Change detection | 4 | T18 | 45min |
| 23 | Monitoring loop | 4 | T14,T19-T22 | 1hr |
| 24 | Scheduler setup | 4 | T23,T5 | 1hr |
| 25 | Portfolio metrics | 5 | T18 | 1hr |
| 26 | Hotspot detection | 5 | T9,T18 | 1.5hr |
| 27 | Portfolio reporter | 5 | T25,T26 | 1hr |
| 28 | Unit tests: utils | 6 | T4 | 1hr |
| 29 | Unit tests: scoring | 6 | T15-T17 | 1.5hr |
| 30 | Integration tests | 6 | All | 2hr |
| 31 | API reference docs | 6 | All | 1.5hr |
| 32 | Operations guide | 6 | All | 1.5hr |
| 33 | Performance testing | 6 | All | 1hr |
| 34 | Main entry point | 6 | All | 1hr |

**Total Estimated Time:** ~30-35 hours solo development

---

## How to Use This Task Breakdown

1. **Pick a task** from the numbered list above
2. **Check dependencies** — make sure previous tasks are done
3. **Read the outcome** — what does done look like?
4. **Build the feature** — write code
5. **Verify** — run the exact verification commands
6. **Commit** — git commit with task number (e.g., "Task 8: Load properties to DB")
7. **Check off** — mark task as done, move to next

**Recommended order:** Follow tasks 1→34 as listed. Most have clear dependencies.

**Parallel work:** Some tasks can be done in parallel if dependencies allow (e.g., T10, T11, T12 can start once T2,T3,T6 are done).
