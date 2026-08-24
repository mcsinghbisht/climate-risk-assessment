# Task 7: Generate 100 Sample Properties - COMPLETED ✓

**Completed:** 2026-07-21
**Status:** 100 properties generated, saved, and verified

---

## What Was Completed

### `src/data_ingestion/property_generator.py`

```python
def generate_properties(seed: int = 42) -> List[Dict]
def save_to_json(properties, path=JSON_OUTPUT_PATH) -> None
def save_to_csv(properties, path=CSV_OUTPUT_PATH) -> None
```

Generates 100 synthetic but realistic property records across 10 states, driven by a
`STATE_CONFIGS` table (state, county names, city names, coordinate center + spread,
elevation range, and a risk `category`: wildfire / flood / mixed).

**Reproducible by design:** generation uses a seeded `random.Random(42)` instance, so
`generate_properties()` returns identical output on every run — important for
deterministic testing and for regenerating the same dataset later.

### Geographic Distribution (100 properties)

| Category | States | Count |
|----------|--------|-------|
| Wildfire risk | CA (20), AZ (15), CO (10) | 45 |
| Flood risk | LA (15), TX (12), FL (13) | 40 |
| Mixed / other | OR (5), WA (4), NC (3), NM (3) | 15 |
| **Total** | | **100** |

### Risk-Correlated Attribute Weighting

Rather than assigning attributes uniformly at random, the generator biases them by
each state's risk category so the dataset is meaningful for scoring, not just
structurally valid:

- **Construction type** — wood is weighted higher in wildfire states (60%), masonry
  higher in flood states (50%)
- **Wildland-Urban Interface (WUI)** flag — 55% likelihood in wildfire states,
  5% in flood states
- **Floodplain** flag — 45% likelihood in flood states, 5% in wildfire states

Result from this run: **28 properties in WUI**, **21 properties in a floodplain**.

### Output Files

| File | Contents |
|------|----------|
| `data/sample_properties.json` | 100 property records, primary format for the DB loader (Task 8) |
| `data/sample_properties.csv` | Same 100 records, CSV backup/inspection format |

---

## Verification Results

### Exact Task Breakdown Verification (from docs/task-breakdown.md)

```
Generated 100 properties
Sample property: 4606 Highland Way, Big Bear Lake, CA 98696 at (34.613478, -119.589953)
[PASS] All required fields present, exactly 100 properties

Properties by state: [('AZ', 15), ('CA', 20), ('CO', 10), ('FL', 13), ('LA', 15),
                       ('NC', 3), ('NM', 3), ('OR', 5), ('TX', 12), ('WA', 4)]
[PASS] CA, AZ, CO (wildfire) and LA, TX, FL (flood) all present
```

CSV file confirmed readable with correct header and quoted address field.

### Pytest Suite

Created `tests/test_property_generator_pytest.py` with 14 tests across two classes:

**TestPropertyGeneration (10 tests)**
- Exactly 100 properties generated
- Property IDs are sequential and unique (1-100)
- All 13 required fields present on every record
- CA/AZ/CO (wildfire) and LA/TX/FL (flood) states present
- All coordinates within valid lat/lon ranges
- Construction type is one of wood/masonry/mixed
- Same seed produces identical output (reproducibility)
- Different seeds produce different output
- **Every generated property passes Task 4's `validate_property_data()`** — a direct
  cross-check between this task's output and the earlier validation utility

**TestOutputFiles (4 tests)**
- `sample_properties.json` and `sample_properties.csv` both exist on disk
- JSON file parses and contains exactly 100 records
- CSV file has a header row plus exactly 100 data rows

```
tests/test_property_generator_pytest.py ..............  14 passed
```

**Full project test suite (Tasks 4-7 combined): 49 passed in 0.30s** ✓

---

## Files Created

| File | Purpose |
|------|---------|
| `src/data_ingestion/property_generator.py` | Generator logic + CLI entry point (218 lines) |
| `data/sample_properties.json` | 100 generated property records |
| `data/sample_properties.csv` | CSV backup of the same records |
| `tests/test_property_generator_pytest.py` | Pytest suite (14 tests) |

---

## Following Reference Principles

**Data Quality as a First-Class Concern** ✓
- Every generated property is validated against the same `validate_property_data()`
  function real ingested data will go through later — the sample data is held to the
  same bar as production data, not a special case.

**Geospatial Precision** ✓
- Coordinates are generated as realistic clusters around real city centers per state,
  not arbitrary random points across the whole US, so proximity-based risk scoring
  (Tasks 15-16) will operate on plausible spatial data.

**Scalability From Day One** ✓
- `STATE_CONFIGS` is a simple list to extend — adding a new state or increasing the
  property count requires no changes to the generation logic itself.

**Data-Driven Risk Intelligence** ✓
- Risk-relevant attributes (construction type, WUI, floodplain) are correlated with
  each state's actual hazard category rather than uniform-random, so the eventual
  risk scores calculated on this data will show meaningful variation instead of noise.

---

## Usage Going Forward

```python
from src.data_ingestion.property_generator import generate_properties

properties = generate_properties()  # same 100 properties every time (seed=42)
```

Or from the command line to regenerate the JSON/CSV files:

```bash
python src/data_ingestion/property_generator.py
```

---

## Next Task

**Task 8: Load Sample Properties into Database**
- Build `src/data_ingestion/property_loader.py`
- Read `data/sample_properties.json`, validate each record, insert into the
  `properties` table created in Task 3
- Handle duplicates gracefully and log success/failure counts

---

**Status:** Task 7 Complete ✓
**Ready for:** Task 8 - Load Sample Properties into Database
