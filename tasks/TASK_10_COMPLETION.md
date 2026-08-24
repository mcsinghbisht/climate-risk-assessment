# Task 10: Create Wildfire API Ingestion (NASA FIRMS) - COMPLETED ✓

**Completed:** 2026-07-22
**Status:** Live NASA FIRMS data fetched, parsed, stored, and verified — including a real API call.

---

## What Was Completed

### `src/data_ingestion/wildfire_ingestion.py` — `WildFireIngester` class

```python
class WildFireIngester:
    def fetch_active_fires(lat_min, lat_max, lon_min, lon_max, days=None) -> List[Dict]
    def store_fires(fires: List[Dict]) -> int
    # internal: _parse_csv_response(csv_text), _parse_acquisition_time(date, time)
```

**Behavior:**
1. Reads NASA FIRMS config (`enabled`, `base_url`, `sensor`, `days_lookback`) from
   `config/settings.json` via Task 5's `ConfigManager`
2. Loads the API key from the `NASA_FIRMS_API_KEY` environment variable (via `.env` and
   `python-dotenv`) — **never stored in config or code**
3. Builds the request URL in FIRMS' required `west,south,east,north` bounding-box order
   (confirmed from live API documentation — this is the opposite order from a naive
   `lat_min,lat_max,lon_min,lon_max` assumption)
4. Clamps the day-range parameter to FIRMS' allowed 1–5 range
5. Parses the returned CSV (VIIRS sensor columns), validates each coordinate with Task 4's
   `is_valid_coordinate()`, maps FIRMS' letter-coded confidence (`l`/`n`/`h`) to a numeric
   0–1 confidence score, and combines `acq_date` + `acq_time` into an ISO 8601 timestamp
6. `store_fires()` inserts normalized records into `hazard_data` with
   `source='NASA_FIRMS'`, `hazard_type='wildfire'`
7. Degrades gracefully: disabled source, missing key, network failure, or an unexpected
   (non-CSV) response all log a warning/error and return an empty list — never crash the
   caller

### API Key Setup

- Registered a free NASA FIRMS `MAP_KEY` (email-based, instant, no approval wait)
- Stored in `.env` (already gitignored) as `NASA_FIRMS_API_KEY`
- `config/settings.json` updated to reference `"api_key_env": "NASA_FIRMS_API_KEY"`
  instead of a literal placeholder — the actual key never appears in version control
- Added `.env.example` documenting the required variable names for future setup
- Fixed `days_lookback` in config from an invalid `7` down to `3` (FIRMS' hard max is 5)

---

## Verification Results

### Live API Call (Real Data, Not Mocked)

```bash
python -m src.data_ingestion.wildfire_ingestion
```
```
Fetching active fires for California bounding box...
Parsed 269 valid fire detections from NASA FIRMS response
Found 269 active fire detections

Sample detection:
{
  "hazard_type": "wildfire",
  "source": "NASA_FIRMS",
  "latitude": 36.3569,
  "longitude": -114.91347,
  "value": 8.53,
  "confidence": 0.6,
  "observation_timestamp": "2026-07-20T08:33:00+00:00",
  "raw_data": "{...full original FIRMS row preserved...}"
}
Stored 269 records in hazard_data table
```

### Database Verification (via tools/query.py)

```
SELECT source, hazard_type, COUNT(*) FROM hazard_data GROUP BY source, hazard_type;
  → NASA_FIRMS | wildfire | 269

SELECT confidence, COUNT(*) FROM hazard_data GROUP BY confidence;
  → 0.3 (low): 30    0.6 (nominal): 196    0.9 (high): 43

SELECT MIN(value), MAX(value), AVG(value) FROM hazard_data;
  → min 0.3, max 142.29, avg 17.08  (fire radiative power, MW)
```

This confirmed real, live wildfire detections were fetched, correctly parsed, and
stored with sensible value ranges. Test data was then cleared from the real database
(`DELETE FROM hazard_data`) before writing automated tests, so the production database
stays clean between manual verification and the pytest suite.

### Pytest Suite (Offline, Deterministic, No Live Network Calls)

Created `tests/test_wildfire_ingestion_pytest.py` with **19 tests** across three classes,
using a canned FIRMS-format CSV response and a hand-built `FakeRequests` stand-in so
tests never touch the network or depend on a real API key:

**TestParseCsvResponse (9 tests)** — pure parsing logic
- Valid rows parsed correctly; all normalized fields present
- `hazard_type`/`source` set correctly
- FRP parsed as float
- Confidence letter codes (`n`, `h`) mapped to `0.6`/`0.9`; unknown codes default to `0.5`
- Invalid coordinates are skipped
- A non-CSV error response (e.g. "Invalid MAP_KEY") returns `[]` instead of crashing
- `acq_date` + `acq_time` combine into a correct ISO timestamp

**TestFetchActiveFires (7 tests)** — HTTP orchestration, mocked
- Disabled source or missing API key returns `[]` **without making a request**
- Successful fetch returns parsed fires
- Bounding box is sent in the correct `west,south,east,north` order
- Day range above 5 is clamped to 5; day range below 1 is clamped to 1
- A network exception returns `[]` rather than propagating

**TestStoreFires (3 tests)** — database persistence, isolated temp DB
- All fires stored, correct count returned
- Database row count matches
- Empty list stores nothing (no-op, no error)

```
tests/test_wildfire_ingestion_pytest.py ................... 19 passed
```

### Bug Found and Fixed During Testing

The `test_day_range_below_min_is_clamped` test caught a real bug:
```python
days = days or self.default_days   # BUG: days=0 is falsy in Python!
```
Passing `days=0` silently substituted the configured default (`3`) instead of being
clamped to the minimum (`1`), because `0 or x` evaluates to `x` in Python. Fixed to:
```python
days = days if days is not None else self.default_days
```
This is a good example of why the test suite matters even for "obvious" logic — the bug
only surfaces for the specific edge-case input of exactly `0`.

**Full project test suite (Tasks 4-10 combined): 86 passed in 1.24s** ✓

---

## Files Created/Modified

| File | Purpose |
|------|---------|
| `src/data_ingestion/wildfire_ingestion.py` | `WildFireIngester` class (223 lines) |
| `config/settings.json` | `nasa_firms` section: `api_key_env`, `sensor`, corrected `days_lookback` |
| `.env` | Real `NASA_FIRMS_API_KEY` (gitignored, not in version control) |
| `.env.example` | Documents required env var names for future setup |
| `tests/test_wildfire_ingestion_pytest.py` | Pytest suite (19 tests, offline/mocked) |

---

## Following Reference Principles

**Real-Time Over Static** ✓
- This is the first component pulling live, near-real-time hazard data (VIIRS NRT —
  Near Real Time) rather than static or generated sample data.

**Data Quality as a First-Class Concern** ✓
- Every coordinate is re-validated on ingestion; malformed rows are skipped and logged,
  not silently included or fatal to the batch.

**Data-Driven Risk Intelligence** ✓
- `raw_data` preserves the full original FIRMS row as JSON alongside the normalized
  fields, so the source of every hazard record is fully auditable later.

**Scalability From Day One** ✓
- Graceful degradation (disabled source, missing key, network failure all return `[]`
  rather than crashing) means the 5-minute monitoring loop (Task 23) can call this
  safely even during a temporary API outage.

---

## Usage Going Forward

```python
from src.data_ingestion.wildfire_ingestion import WildFireIngester

ingester = WildFireIngester()
fires = ingester.fetch_active_fires(lat_min=32, lat_max=42, lon_min=-124, lon_max=-114)
stored_count = ingester.store_fires(fires)
```

---

## Next Task

**Task 11: Create Weather API Ingestion (NOAA/OpenWeather)**
- Build `src/data_ingestion/weather_ingestion.py` — a `WeatherIngester` class
- Fetch current wind speed, direction, temperature, and humidity per property location
- Same design pattern as this task: config-driven, env-var API key, graceful degradation,
  stored in `hazard_data` with `hazard_type='weather'`
- Will need its own API key registration (OpenWeatherMap free tier) before live testing

---

**Status:** Task 10 Complete ✓
**Ready for:** Task 11 - Weather API Ingestion
