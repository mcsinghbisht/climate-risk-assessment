# Task 12: Create Flood API Ingestion (USGS + OpenWeatherMap) - COMPLETED ✓

**Completed:** 2026-07-22
**Status:** Live river gauge and precipitation data fetched, parsed, stored, and verified.

---

## What Was Completed

### `src/data_ingestion/flood_ingestion.py` — `FloodIngester` class

```python
class FloodIngester:
    def fetch_river_gauges(lat_min, lat_max, lon_min, lon_max) -> List[Dict]
    def fetch_precipitation(latitude, longitude) -> Optional[Dict]
    def store_records(records: List[Dict]) -> int
    # internal: _parse_gauge_response(data), _parse_usgs_timestamp(dt_str)
```

**Two independent flood signals, no new API key required:**

1. **River gauges (discharge + gage height)** — USGS Water Services Instantaneous
   Values API, fully open access, no key needed. Parameter codes `00060` (discharge,
   cfs) and `00065` (gage height, ft).
2. **Precipitation** — reuses Task 11's `WeatherIngester` (same `OPENWEATHER_API_KEY`)
   and extracts the `rain.1h` field from OpenWeatherMap's current-weather response,
   rather than registering a separate precipitation API.

**Design deviation from the original task spec, and why:** the task breakdown
described `fetch_precipitation(lat_min, lat_max, lon_min, lon_max)` as a bounding-box
query. OpenWeatherMap's free tier only supports single-coordinate current-weather
lookups, not an area query — so `fetch_precipitation()` is point-based
(`latitude, longitude`), matching how `fetch_weather()` already works. This was a
deliberate, documented adaptation to the real constraints of the free API, not an
oversight.

**Behavior:**
1. Reads USGS config (`enabled`, `base_url`, `parameter_codes`) from `config/settings.json`
2. Builds the bounding box in `west,south,east,north` order (same convention as
   NASA FIRMS from Task 10) and enforces USGS's own constraint that
   `lat_range * lon_range <= 25` degrees², rejecting oversized requests before
   sending them
3. Parses the WaterML-as-JSON response structure (`value.timeSeries[].sourceInfo`,
   `.geoLocation`, `.variable.variableCode`, `.values[].value[]`)
4. Stores into `hazard_data` with `hazard_type='flood'`, `source='USGS'` for gauges
   or `source='OPENWEATHER_RAIN'` for precipitation
5. Degrades gracefully throughout: disabled source, oversized bbox, network failure,
   or malformed response all return `[]`/`None` rather than crashing

---

## A Real Data Quality Bug Found During Live Testing

The first live run against Louisiana returned a **sample gauge reading dated
`2004-10-01`** from a site called "JOURDAN RIVER NR BAY ST LOUIS, MS" — clearly not
representative of "current conditions" despite USGS's "instantaneous values" API
implying real-time data. My initial code trusted `values[-1]` (the last entry in the
response array) as "the most recent reading" without validating that assumption.

**Root cause:** some USGS sites in the "active" status list have broken, offline, or
delayed sensors, and the API still returns their last-known (sometimes years-old)
value without flagging it as stale.

**Fix:** added a staleness filter using Task 4's `is_within_hours()` utility —
any reading older than `MAX_GAUGE_READING_AGE_HOURS = 48` is logged as a warning and
excluded, rather than silently treated as current data that would corrupt risk
scoring.

**Verified impact on the real API:** re-running against the same Louisiana bounding
box after the fix filtered out **30 of 172 readings** as stale — including
observations from 2004, 2009, 2017, 2019, 2021, 2023, and 2024. The remaining 142
readings were all genuinely current (within the last 48 hours). This is a clear,
measured demonstration of **Principle 10 (Data Quality as a First-Class Concern)**
from `reference-principles.md` in action: a real integration test surfaced a data
quality issue that unit tests alone (with clean synthetic data) would never have
caught.

---

## Verification Results

### Live API Calls (Real Data, Not Mocked)

```bash
python -m src.data_ingestion.flood_ingestion
```
```
Fetching USGS river gauge data for Louisiana bounding box...
[30 stale-reading warnings logged and correctly filtered]
Parsed 142 valid gauge readings from USGS response
Found 142 gauge readings

Sample gauge reading:
{
  "hazard_type": "flood", "source": "USGS",
  "latitude": 30.3872222, "longitude": -89.4413889,
  "value": 2.67, "confidence": 1.0,
  "observation_timestamp": "2026-07-22T05:45:00+00:00",
  "raw_data": "{\"site_name\": \"JOURDAN RIVER NR BAY ST LOUIS, MS\", \"parameter_code\": \"00065\", \"parameter_label\": \"gage_height_ft\", ...}"
}
Stored 142 gauge records in hazard_data table

Fetching precipitation for (29.9511, -90.0715)...
Rainfall (last hour): 0.0 mm/h
Stored 1 precipitation record in hazard_data table
```

### Database Verification (via tools/query.py)

```
SELECT source, hazard_type, COUNT(*) FROM hazard_data GROUP BY source, hazard_type;
  → OPENWEATHER_RAIN | flood | 1
  → USGS              | flood | 142

SELECT MIN(value), MAX(value), AVG(value) FROM hazard_data WHERE source='USGS';
  → min -54.6, max 552000.0, avg 7336.61
```

**Known limitation, noted for Task 15/16 (risk scoring):** the `value` column mixes
two different units — discharge in cubic feet/second (can be in the hundreds of
thousands for major rivers) and gage height in feet (typically single digits). The
`raw_data.parameter_label` field distinguishes which is which; risk-scoring logic
must branch on `parameter_code`/`parameter_label` rather than treating `value` as a
single normalized scale. This mirrors how NASA FIRMS confidence needed letter-code
mapping (Task 10) — external APIs bring their own units and conventions that the
ingestion layer preserves faithfully rather than force-normalizing prematurely.

Test data was cleared (`DELETE FROM hazard_data`) afterward to keep the production
database clean, consistent with Tasks 10 and 11.

### Pytest Suite (Offline, Deterministic, No Live Network Calls)

Created `tests/test_flood_ingestion_pytest.py` with **17 tests** across four classes:

**TestParseGaugeResponse (6 tests)** — pure parsing/staleness logic
- A current reading is kept; a stale reading is filtered out
- All normalized fields present; `hazard_type`/`source` correct
- Missing `timeSeries` structure returns `[]` rather than crashing
- Invalid coordinates are skipped

**TestFetchRiverGauges (5 tests)** — HTTP orchestration + bbox constraint, mocked
- Disabled source returns `[]` without a request
- An oversized bounding box (`lat_range * lon_range > 25`) is rejected **before**
  making a request
- Bounding box sent in correct `west,south,east,north` order
- Successful fetch returns parsed records; network exception returns `[]`

**TestFetchPrecipitation (3 tests)** — delegation to `WeatherIngester`, mocked
- Returns `None` when the underlying weather fetch fails
- Correctly extracts `rain.1h` when present
- Defaults to `0.0` (not an error) when the `rain` field is absent (dry conditions)

**TestStoreRecords (3 tests)** — database persistence, isolated temp DB
- All records stored, correct count; empty list stores nothing

```
tests/test_flood_ingestion_pytest.py ................. 17 passed
```

### Two Test-Authoring Bugs Found and Fixed While Writing the Suite

Both were bugs in the **test helper**, not the source code — worth documenting since
they show the same "verify, don't assume" discipline applied to test code itself:

1. `_iso()` formatted UTC-computed clock digits but labeled them with a fake
   `-05:00` offset suffix, silently shifting every test timestamp by 5 hours and
   masking staleness in two tests. Fixed to use the digits' true `+00:00` offset.
2. `test_invalid_coordinates_are_skipped` passed `stale_dt=now` (not actually stale)
   while asserting the record would be filtered "by age" — fixed to pass a genuinely
   old timestamp matching the test's stated intent.

**Full project test suite (Tasks 4-12 combined): 121 passed in 1.25s** ✓

---

## Files Created/Modified

| File | Purpose |
|------|---------|
| `src/data_ingestion/flood_ingestion.py` | `FloodIngester` class (241 lines) |
| `config/settings.json` | `usgs_water` section: corrected `base_url` (`/iv` path), added `parameter_codes` |
| `tests/test_flood_ingestion_pytest.py` | Pytest suite (17 tests, offline/mocked) |

---

## Following Reference Principles

**Data Quality as a First-Class Concern** ✓
- The staleness filter is the clearest example yet of this principle in the codebase:
  a real integration bug (30 stale readings mixed into "active" USGS sites) was
  caught, measured, and fixed with a tested, logged, configurable threshold rather
  than a silent assumption.

**Real-Time Over Static** ✓
- Third live data source now integrated, completing the full trio (wildfire, weather,
  flood) called for in the original solution architecture.

**Scalability From Day One** ✓
- Reusing `WeatherIngester` for precipitation instead of building a parallel
  standalone client avoided duplicating authentication, error handling, and
  redaction logic that was already built and tested in Task 11.

---

## Usage Going Forward

```python
from src.data_ingestion.flood_ingestion import FloodIngester

ingester = FloodIngester()
gauges = ingester.fetch_river_gauges(lat_min=29.0, lat_max=30.8, lon_min=-91.2, lon_max=-89.4)
precip = ingester.fetch_precipitation(latitude=29.9511, longitude=-90.0715)
ingester.store_records(gauges + ([precip] if precip else []))
```

---

## Next Task

**Task 13: Create Data Normalizer Pipeline**
- Build `src/data_ingestion/data_normalizer.py` — a `DataNormalizer` class
- Standardize the (slightly different) output shapes of `WildFireIngester`,
  `WeatherIngester`, and `FloodIngester` into one consistent format before storage
- Consolidates the confidence-mapping, timestamp-parsing, and validation logic that
  is currently duplicated (with small variations) across all three ingesters built
  in Tasks 10-12

---

**Status:** Task 12 Complete ✓
**All three hazard data sources (wildfire, weather, flood) now live and verified — Phase 2b nearly done.**
**Ready for:** Task 13 - Data Normalizer Pipeline
