# Task 16: Implement Flood Risk Scoring Algorithm - COMPLETED ✓

**Completed:** 2026-07-22
**Status:** `FloodScorer` built, tested, and verified — mirrors `WildFireScorer`'s design exactly.

---

## What Was Completed

### `src/risk_scoring/scoring_utils.py` — Shared Scoring Helpers (new)

Before building `FloodScorer`, extracted the weather-parsing logic that would
otherwise have been duplicated a second time (the same lesson Task 13 applied to
the ingestion layer, applied here to scoring):

```python
def parse_weather_extras(row) -> Dict   # temperature, humidity, wind_speed, wind_direction
def parse_gauge_extras(row) -> Dict     # site_name, parameter_label
```

`WildFireScorer` was refactored to import `parse_weather_extras` from here instead
of keeping its own private copy — a safe, non-breaking internal change (all 23
existing wildfire scorer tests still pass unchanged, confirming the refactor didn't
alter behavior).

### `src/risk_scoring/flood_scorer.py` — `FloodScorer` class

```python
class FloodScorer:
    def calculate_risk_for_property(property_data: Dict, hazard_data: List[Dict]) -> Dict
    # internal: _score_rainfall, _score_proximity_to_water, _score_floodplain, _score_soil_saturation
```

Four weighted components, matching `docs/implementation-plan.md` Section 5:

| Component | Default Weight | What It Measures |
|-----------|----------------|-------------------|
| Rainfall accumulation | 0.5 | Sum of recent precipitation readings (`OPENWEATHER_RAIN` rows) |
| Proximity to water | 0.2 | Distance to the nearest USGS gauge station (proxy for "is there a water body nearby") |
| Floodplain status | 0.2 | Property's own `is_in_floodplain` flag — a **static attribute from Task 7**, not fetched hazard data |
| Soil saturation | 0.1 | Proxy combining rainfall total + humidity (no direct soil-moisture data source exists) |

**Same output contract as `WildFireScorer`:** `{score, factors, explanation}` — this
was deliberate, not incidental. The future LLM agent context (discussed after Task
15) needs both scorers to produce an identical shape so a shared prompt-building
function can handle either hazard type without special-casing.

**Key structural difference, called out explicitly:** floodplain status is read
directly from `property_data`, not from `hazard_data` — the only component across
both scorers that doesn't come from ingested API data.

**Documented simplification:** proximity-to-water uses only distance to the nearest
gauge, not that gauge's current reading severity — a design choice matching the
documented MVP plan rather than inventing an unplanned fifth weighted factor. (Task
12 already flagged that gauge values mix incompatible units — discharge in cfs vs.
gage height in feet — so using severity directly here would need unit-aware handling
that's out of scope for this task.)

---

## Verification Results

### Manual Demo

```bash
python -m src.risk_scoring.flood_scorer
```
```
Score: 58.46
Factors: {
  "rainfall_score": 30.0, "proximity_score": 93.58,
  "floodplain_score": 100.0, "saturation_score": 47.4,
  "total_rainfall_mm": 45.0, "distance_km": 1.28,
  "distance_category": "immediate", "gauge_site_name": "New Orleans Gauge",
  "is_in_floodplain": true, "humidity": 88.0
}
Explanation: Recent rainfall accumulation: 45.0 mm. Nearest water gauge
(New Orleans Gauge) is 1.28 km away (immediate). Property is located within
a designated FEMA floodplain. Humidity: 88.0%. Overall flood risk score: 58.46/100.
```

No-hazard baseline (not in floodplain) correctly returns `score: 0.0` with a clear
explanation.

### Pytest Suite

Created `tests/test_flood_scorer_pytest.py` with **20 tests** across six classes:

**TestOverallScore (6)** — score bounded 0-100; no data + not in floodplain → 0;
result always has `factors`/`explanation`; heavy rain + floodplain + near gauge
scores >60; floodplain status alone (no hazard data at all) still contributes to the
score; **a far-away gauge with a huge discharge value does not affect the score** —
this test was added proactively, informed directly by Task 15's out-of-range-fire
bug, and passed on the first run (confirming `_score_proximity_to_water` doesn't
have the same value-leakage issue, since gauge severity was never used elsewhere in
this scorer to begin with)

**TestRainfallScoring (4)** — more rain scores higher; no rain rows → 0; multiple
rainfall readings are summed (accumulation proxy); score capped at 100

**TestProximityToWaterScoring (3)** — closer gauge scores higher; no gauges → 0;
a gauge beyond `proximity_max_km` scores 0

**TestFloodplainScoring (2)** — in floodplain → 100; not in floodplain → 0

**TestSoilSaturationScoring (4)** — high rainfall + high humidity scores high; low
rainfall + low humidity scores low; no data → 0; partial data (one of two inputs)
still produces a score

**TestNearestWeatherSelection (1)** — with two weather stations, the closer one's
humidity is used, not an arbitrary one (mirrors Task 15's identical test)

```
tests/test_flood_scorer_pytest.py .................... 20 passed
```

**Full project test suite (Tasks 4-16 combined): 205 passed in 2.33s** ✓ — zero
bugs found this time, a direct result of applying Task 15's lessons proactively
(the far-gauge regression test) rather than discovering them after the fact.

---

## Files Created/Modified

| File | Change |
|------|--------|
| `src/risk_scoring/scoring_utils.py` | New — shared `parse_weather_extras`, `parse_gauge_extras` (65 lines) |
| `src/risk_scoring/wildfire_scorer.py` | Refactored to use the shared helper (removed ~15 duplicated lines) |
| `src/risk_scoring/flood_scorer.py` | New — `FloodScorer` class (255 lines) |
| `src/risk_scoring/__init__.py` | Exported `FloodScorer` |
| `config/settings.json` | New `risk_scoring.flood_params` section (4 tunable thresholds) |
| `tests/test_flood_scorer_pytest.py` | New — 20 tests |

---

## Following Reference Principles

**Transparency and Explainability** ✓ — identical to Task 15: every score returns a
full `factors` breakdown and a plain-English `explanation`, keeping both hazard
types consistent for the eventual LLM-layer consumption.

**Scalability From Day One** ✓ — extracting `scoring_utils.py` now (at 2 scorers)
rather than waiting until duplication became a bigger problem across more scorers
later.

**Data Quality as a First-Class Concern** ✓ — the far-gauge test demonstrates the
lesson from Task 15's bug was actually internalized, not just fixed in isolation:
the same category of risk (an out-of-range hazard reading contaminating a score) was
checked for here before it could occur, rather than after.

---

## Usage Going Forward

```python
from src.risk_scoring import FloodScorer

scorer = FloodScorer()
result = scorer.calculate_risk_for_property(property_data, hazard_data)
print(result["score"], result["explanation"])
```

---

## Next Task

**Task 17: Create Risk Score Aggregator**
- Build `src/risk_scoring/aggregator.py` — a `RiskAggregator` class
- Combines `WildFireScorer` and `FloodScorer` output into a single overall score and
  risk level classification (`low`/`medium`/`high`/`critical`, using the
  `risk_scoring.risk_levels` thresholds already sitting in config since Task 5)
- Small, focused task — the last piece before Task 18 (storage) and Task 19
  (orchestrating both scorers across all 100 properties)

---

**Status:** Task 16 Complete ✓
**Phase 3 (Risk Scoring) — 2 of 5 tasks complete.**
**Ready for:** Task 17 - Risk Score Aggregator
