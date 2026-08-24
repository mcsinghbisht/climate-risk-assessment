# Task 15: Implement Wildfire Risk Scoring Algorithm - COMPLETED ✓

**Completed:** 2026-07-22
**Status:** `WildFireScorer` built, tested, and verified — first algorithm to actually *use* the hazard data ingested in Tasks 10-14.

---

## What Was Completed

### `src/risk_scoring/wildfire_scorer.py` — `WildFireScorer` class

```python
class WildFireScorer:
    def calculate_risk_for_property(property_data: Dict, hazard_data: List[Dict]) -> Dict
    # internal: _score_proximity, _score_wind_escalation, _score_intensity, _score_environment
```

Calculates an explainable 0-100 wildfire risk score from four weighted components,
matching the formula defined in `docs/implementation-plan.md` Section 5:

| Component | Default Weight | What It Measures |
|-----------|----------------|-------------------|
| Proximity | 0.4 | Distance to the nearest active fire (linear falloff to 0 at `proximity_max_km`, default 50km) |
| Wind escalation | 0.3 | Is the property downwind of that fire, and how strong is the wind pushing toward it? |
| Intensity | 0.2 | Fire Radiative Power (FRP) relative to a configured historical maximum |
| Environment | 0.1 | Low humidity + high temperature (fire-danger weather conditions) |

**Input format:** `hazard_data` is a list of `hazard_data`-table-shaped dicts — the
same shape produced by `DataNormalizer` (Task 13) and stored by the ingesters
(Tasks 10-12). This means the scorer can be called directly with rows queried from
the database, with no translation layer required.

**Weather field extraction:** wind speed/direction/humidity aren't separate
`hazard_data` columns — only temperature is stored as `value` directly; the rest live
inside the `raw_data` JSON blob (per Task 13's `normalize_weather`). A small
`_parse_weather_extras()` helper handles this extraction once, consistently.

**Nearest-weather selection:** when multiple weather observations are in range, the
scorer uses the one geographically closest to the property (not just the first in the
list) — verified with a dedicated test using two weather stations with very different
readings.

All weights and thresholds are configuration-driven
(`config/settings.json` → `risk_scoring.wildfire_weights` / `risk_scoring.wildfire_params`)
— no hardcoded numbers in the scoring logic itself.

---

## A Real Logic Bug Caught by the Test Suite

`test_far_fire_scores_low` expected a fire ~450km away (well beyond the 50km
proximity range) to produce a score of exactly `0.0`. It returned `4.0` instead.

**Root cause:** `_score_proximity()` correctly zeroed the *proximity* score for an
out-of-range fire, but still returned that fire as `nearest_fire` — and the
orchestration code used `nearest_fire` (not range-checked) to compute the *intensity*
score. So a fire hundreds of kilometers away, posing no realistic threat, was still
contributing 20% of the overall score just because it happened to be the closest fire
found anywhere in the queried hazard data.

**Fix:** introduced `fire_in_range` — `nearest_fire` only if its distance is within
`proximity_max_km` — and used that (not the raw `nearest_fire`) for both the intensity
and wind-escalation components. The `factors.frp` field was updated to match, so the
reported factors never show an intensity value that didn't actually contribute to the
score. Distance/category reporting still uses the true nearest fire (informational,
even if out of range), preserving transparency about what was found without letting
it skew the score.

---

## Verification Results

### Manual Demo (Realistic Scenario)

```bash
python -m src.risk_scoring.wildfire_scorer
```
```
Score: 77.09
Factors: {
  "proximity_score": 88.28, "wind_score": 75.0,
  "intensity_score": 50.0, "environment_score": 92.8,
  "distance_km": 5.86, "distance_category": "near",
  "frp": 250.0, "wind_speed": 15.0, "wind_direction": 162,
  "temperature": 38.0, "humidity": 12.0
}
Explanation: Nearest active fire is 5.86 km away (near). Wind (15.0 m/s) is blowing
toward the property, increasing escalation risk. Fire intensity (FRP): 250.0 MW.
Conditions: 38.0°C, 12.0% humidity. Overall wildfire risk score: 77.09/100.
```

A worked example with no fire present correctly returns `score: 0.0` with a clear,
non-alarming explanation ("No active wildfire detected nearby...").

**Building this demo also required getting the geometry right** — the first attempt
used a wind direction that didn't actually put the demo property downwind of the demo
fire (`is_downwind()` correctly returned `False`, giving `wind_score: 0.0`). Rather
than declare that a bug, computed the actual bearing between the two demo points
(`get_bearing()` → 341.6°) and picked a wind direction that genuinely puts the
property downwind — a useful reminder that `is_downwind()`'s correctness (verified
back in Task 4) means demo data has to be geometrically consistent, not just
plausible-looking.

### Pytest Suite

Created `tests/test_wildfire_scorer_pytest.py` with **23 tests** across six classes:

**TestOverallScore (6)** — score bounded 0-100; no hazard data → 0; result always has
`factors`/`explanation`; a nearby+downwind+intense+hot/dry fire scores >70; a far
fire scores exactly 0 (the bug fix, now locked in as a regression test); a nearby
fire with no weather data still scores from proximity+intensity alone

**TestProximityScoring (3)** — closer fire scores higher; no fires → 0; correctly
selects the nearest of multiple fires

**TestWindEscalationScoring (5)** — downwind+strong wind scores positive; upwind
scores 0 even with strong wind; below-threshold wind scores 0; missing wind data
scores 0; score is capped at 100

**TestIntensityScoring (4)** — higher FRP scores higher; zero/None FRP scores 0;
score capped at 100

**TestEnvironmentScoring (4)** — low humidity + high temp scores high; high humidity
+ low temp scores low; no data scores 0; partial data (one of two fields) still
produces a score

**TestNearestWeatherSelection (1)** — with two weather stations at different
distances, the closer one's reading is used, not an arbitrary one

```
tests/test_wildfire_scorer_pytest.py ....................... 23 passed
```

**Full project test suite (Tasks 4-15 combined): 185 passed in 1.88s** ✓

---

## Files Created/Modified

| File | Purpose |
|------|---------|
| `src/risk_scoring/wildfire_scorer.py` | `WildFireScorer` class (280 lines) |
| `src/risk_scoring/__init__.py` | Package export |
| `config/settings.json` | New `risk_scoring.wildfire_params` section (7 tunable thresholds) |
| `tests/test_wildfire_scorer_pytest.py` | Pytest suite (23 tests) |

---

## Following Reference Principles

**Transparency and Explainability** ✓ — every score returns both a `factors`
breakdown (each component's individual contribution) and a human-readable
`explanation` string, so an underwriter can see *why* a property scored the way it
did, not just the number.

**Data-Driven Risk Intelligence** ✓ — the scorer operates directly on the same
`hazard_data` shape produced by real ingestion (Tasks 10-13), with no synthetic
intermediate format — what gets tested is what will actually run in production.

**Data Quality as a First-Class Concern** ✓ — the out-of-range-fire bug is exactly
the kind of subtle correctness issue this principle warns about: the code "worked"
in the sense that it ran without error, but silently produced a wrong answer until a
specific test caught it.

---

## Usage Going Forward

```python
from src.risk_scoring import WildFireScorer

scorer = WildFireScorer()
result = scorer.calculate_risk_for_property(property_data, hazard_data)
print(result["score"], result["explanation"])
```

---

## Next Task

**Task 16: Implement Flood Risk Scoring Algorithm**
- Build `src/risk_scoring/flood_scorer.py` — a `FloodScorer` class
- Same design pattern: rainfall accumulation, proximity to water/gauges, floodplain
  status (already a property attribute from Task 7), soil saturation
- Will reuse the same `hazard_data`-shaped input convention established here

---

**Status:** Task 15 Complete ✓
**Phase 3 (Risk Scoring) underway — 1 of 5 tasks complete.**
**Ready for:** Task 16 - Flood Risk Scoring Algorithm
