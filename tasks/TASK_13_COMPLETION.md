# Task 13: Create Data Normalizer Pipeline - COMPLETED ✓

**Completed:** 2026-07-22
**Status:** `DataNormalizer` built, all three ingesters refactored to use it, zero regressions.

---

## What Was Completed

### `src/data_ingestion/data_normalizer.py` — `DataNormalizer` class

```python
class DataNormalizer:
    def normalize_fire(row: Dict) -> Optional[Dict]
    def normalize_weather(data: Dict, latitude, longitude) -> Optional[Dict]
    def normalize_precipitation(weather_raw_response, latitude, longitude, observation_timestamp) -> Dict
    def normalize_gauge(series: Dict) -> Optional[Dict]
```

Consolidates what was previously duplicated (with small inconsistencies) across
`WildFireIngester`, `WeatherIngester`, and `FloodIngester`:

| Concern | Before (duplicated) | After (shared) |
|---------|---------------------|-----------------|
| Coordinate validation | Inline `is_valid_coordinate()` check in each of 3 places | One `_build_record()` helper, called by all four `normalize_*()` methods |
| Confidence handling | FIRMS letter-map inline; weather/flood hardcoded `1.0` in 3 places | `FIRMS_CONFIDENCE_MAP`, `DEFAULT_CONFIDENCE`, `OBSERVATION_CONFIDENCE` as single named constants |
| Timestamp parsing | 3 separate private methods (`_parse_acquisition_time`, inline `dt` parsing, `_parse_usgs_timestamp`) | 3 shared helpers on `DataNormalizer`, one obvious place to fix a bug in any of them |
| Staleness filtering | Only existed in `FloodIngester` (Task 12's bug fix) | Now a general capability (`_is_stale()`, configurable `max_gauge_reading_age_hours`) any future normalizer can reuse |
| Output record shape | Each ingester built its own dict literal | One `_build_record()` producing an identical field set every time |

### Field naming decision (deviation from the generic task spec, documented)

The original task description described a generic output shape of
`{latitude, longitude, value, confidence, timestamp, metadata}`. Normalized records
instead use `observation_timestamp` and `raw_data` — matching the actual `hazard_data`
table column names from Task 3 — so every normalized record is directly insertable
with no translation step. This mirrors the same kind of deliberate, documented
adaptation made in Task 12 (point-based `fetch_precipitation` instead of bbox-based).

### Refactored: `WildFireIngester`, `WeatherIngester`, `FloodIngester`

All three now hold a `self._normalizer = DataNormalizer(...)` instance and delegate
per-record normalization to it:

- `WildFireIngester._parse_csv_response()` loops CSV rows, calling
  `self._normalizer.normalize_fire(row)` per row (was: ~30 lines of inline logic)
- `WeatherIngester._parse_weather_response()` is now a one-line delegation to
  `self._normalizer.normalize_weather(data, latitude, longitude)`
- `FloodIngester._parse_gauge_response()` loops USGS time series entries, calling
  `self._normalizer.normalize_gauge(series)` per entry; `fetch_precipitation()`
  delegates to `self._normalizer.normalize_precipitation(...)`

**Backward compatibility preserved by design:** every existing method name, signature,
and observable behavior on the three ingesters is unchanged (`_parse_csv_response()`,
`_parse_weather_response()`, `_parse_gauge_response()`, `MAX_GAUGE_READING_AGE_HOURS`,
`PARAMETER_LABELS`, `CONFIDENCE_MAP` are all still importable from their original
modules, re-exported from `data_normalizer.py`). This was a deliberate constraint:
all 121 tests written in Tasks 10-12 needed to keep passing **unchanged**, proving the
refactor removed duplication without altering behavior.

---

## Verification Results

### Extract-Refactor Correctness: Zero Regressions

```
Before refactor: 121 tests passing (Tasks 4-12)
After refactor:  121 same tests passing, unchanged + 23 new DataNormalizer tests
                 = 144 passing, 0 failing
```

Ran each ingester's test file individually immediately after refactoring it, before
moving to the next, to isolate any regression to its source immediately:
```
tests/test_wildfire_ingestion_pytest.py  19 passed  (after refactoring wildfire_ingestion.py)
tests/test_weather_ingestion_pytest.py   18 passed  (after refactoring weather_ingestion.py)
tests/test_flood_ingestion_pytest.py     17 passed  (after refactoring flood_ingestion.py)
```

### DataNormalizer Demo (Offline)

```bash
python -m src.data_ingestion.data_normalizer
```
All four `normalize_*()` methods exercised with sample data, each producing a
consistent field set (`hazard_type`, `source`, `latitude`, `longitude`, `value`,
`confidence`, `observation_timestamp`, `raw_data`) — confirmed visually:
```
normalize_fire()          → hazard_type='wildfire', source='NASA_FIRMS', confidence=0.6
normalize_weather()       → hazard_type='weather',  source='OPENWEATHER', + convenience fields
normalize_precipitation() → hazard_type='flood',    source='OPENWEATHER_RAIN'
normalize_gauge()         → hazard_type='flood',    source='USGS'
```

### Pytest Suite: `DataNormalizer` Tested in Isolation

Created `tests/test_data_normalizer_pytest.py` with **23 tests** across five classes,
testing the normalizer directly (not through an ingester), since the ingester test
suites already cover the integration path:

**TestNormalizeFire (6)** — valid row, hazard_type/source, missing/invalid coordinates,
confidence map applied for every code, unmapped code uses default

**TestNormalizeWeather (6)** — valid response, convenience fields, `value` mirrors
temperature, full confidence, malformed response returns `None`, uses the *passed*
coordinates rather than trusting the response's own `coord` field

**TestNormalizePrecipitation (3)** — extracts `rain.1h`, defaults to `0.0` when
absent, hazard_type/source correct

**TestNormalizeGauge (7)** — current reading kept, stale reading rejected,
hazard_type/source, parameter label present in `raw_data`, invalid coordinates
rejected, malformed series returns `None`, **custom staleness threshold is
respected** (constructing `DataNormalizer(max_gauge_reading_age_hours=1)` and
confirming a 2-hour-old reading is now correctly rejected — proving the threshold is
actually configurable, not just hardcoded)

**TestConsistencyAcrossSources (1)** — the key contract test: normalizes one record
from *each* of the four sources and asserts they all produce the same field set

```
tests/test_data_normalizer_pytest.py ....................... 23 passed
```

**Full project test suite (Tasks 4-13 combined): 144 passed in 1.45s** ✓

---

## Files Created/Modified

| File | Change |
|------|--------|
| `src/data_ingestion/data_normalizer.py` | New — `DataNormalizer` class (290 lines) |
| `src/data_ingestion/wildfire_ingestion.py` | Refactored: per-row logic delegated to normalizer (net -28 lines) |
| `src/data_ingestion/weather_ingestion.py` | Refactored: `_parse_weather_response` now a 1-line delegation (net -43 lines) |
| `src/data_ingestion/flood_ingestion.py` | Refactored: gauge loop and precipitation delegated to normalizer (net -60 lines) |
| `tests/test_data_normalizer_pytest.py` | New — 23 tests, normalizer tested in isolation |

**Net effect:** ~130 lines of duplicated logic removed from the three ingesters,
replaced by ~290 lines of centralized, independently-tested normalization logic (the
increase reflects thorough docstrings and the new configurability/consistency tests
that didn't exist before — the *duplicated* logic itself shrank substantially).

---

## Following Reference Principles

**Data Quality as a First-Class Concern** ✓
- The staleness check (originally a one-off fix in `FloodIngester`, Task 12) is now a
  general, configurable capability any future normalizer can use — fixing a
  data-quality bug once, in one place, benefits every hazard source, not just the one
  that happened to surface it first.

**Scalability From Day One** ✓
- Adding a fifth hazard source (e.g., a future satellite soil-moisture feed) now means
  writing one `normalize_soil_moisture()` method reusing `_build_record()`, rather than
  re-implementing coordinate validation and record assembly from scratch again.

**Transparency and Explainability** ✓
- `TestConsistencyAcrossSources` makes the "every hazard record looks the same
  regardless of source" guarantee an explicit, tested contract — not just an informal
  convention that could silently drift as ingesters evolve independently.

---

## Usage Going Forward

Ingesters use it internally and transparently — no change to how `fetch_active_fires()`,
`fetch_weather()`, or `fetch_river_gauges()` are called. `DataNormalizer` can also be
used directly for testing or future one-off normalization needs:

```python
from src.data_ingestion.data_normalizer import DataNormalizer

normalizer = DataNormalizer()
record = normalizer.normalize_fire(csv_row)
```

---

## Next Task

**Task 14: Integrate Ingestion into Single Data Ingestion Pipeline**
- Build `src/data_ingestion/ingestion_engine.py` — an `IngestionEngine` class
- Orchestrates all three ingesters (wildfire, weather, flood) across the actual
  property portfolio's geographic footprint
- This is where the "how do we know which coordinates to query?" design question
  (raised before Task 10) finally gets resolved — deriving bounding boxes/coordinates
  from `PropertyDAO` and Task 7's state clusters, rather than the hardcoded demo
  coordinates each ingester's `__main__` block currently uses individually

---

**Status:** Task 13 Complete ✓
**Phase 2b (Data Ingestion, Tasks 10-14) nearly done — one integration task remains.**
**Ready for:** Task 14 - Integrate Ingestion into Single Data Ingestion Pipeline
