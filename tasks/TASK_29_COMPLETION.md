# Task 29: Write Unit Tests for Risk Scoring - COMPLETED ✓

**Completed:** 2026-08-03
**Status:** `tests/test_risk_scoring.py` created — a gap-filling, edge-case-focused
suite (not a from-scratch one), since `src/risk_scoring/` already had strong
coverage from Tasks 15-19's own per-component test suites.

---

## What Was Completed

### Coverage Checked First, Same Approach as Task 28

Before writing anything, measured actual coverage of `src/risk_scoring/`
across the whole existing test suite:

```
pytest tests/ --cov=src/risk_scoring --cov-report=term-missing
Name                                  Stmts   Miss  Cover
src\risk_scoring\aggregator.py           41      0   100%
src\risk_scoring\flood_scorer.py         80      0   100%
src\risk_scoring\scoring_engine.py       48      5    90%   100, 102-105
src\risk_scoring\scoring_utils.py        18      4    78%   32-33, 59-60
src\risk_scoring\wildfire_scorer.py      85      0   100%
TOTAL                                   277      9    97%
```

Already 97% overall - well past the 85% target - thanks to `test_wildfire_scorer_pytest.py`,
`test_flood_scorer_pytest.py`, `test_aggregator_pytest.py`, and
`test_scoring_engine_pytest.py` (66 tests total, built during Tasks 15-19).
This confirmed Task 29's real job was two things: (1) the explicit edge
cases the task spec calls out, consolidated in one dedicated file, and
(2) closing the two genuine remaining gaps.

### `tests/test_risk_scoring.py` (new, 28 tests)

**Named per the task spec:**
- **`TestWildfireScorerProximity` (3)** — closer fire scores higher; a fire
  beyond `proximity_max_km` scores exactly 0; the nearest of several fires
  is the one used
- **`TestWildfireScorerWindEscalation` (3)** — a downwind property with
  strong wind scores higher than no wind at all; wind below the speed
  threshold scores 0 regardless of direction; an upwind property scores 0
  regardless of speed. (Bearing math verified explicitly via
  `get_bearing()` rather than guessed, after an initial wrong guess about
  fire/property geometry caused two tests to fail on the first run - fixed
  by computing the correct downwind/upwind wind directions directly instead
  of assuming them.)
- **`TestFloodScorerRainfall` (3)** — higher rainfall scores higher;
  multiple readings sum correctly; extreme rainfall is capped at 100
- **`TestAggregatorScoreCombination` (3)** — plain weighted average without
  override; the single-hazard override raising both score and level;
  `build_overall_assessment()` correctly threads scorer outputs through

**Edge cases, explicitly required (score=0, score=100, missing data,
invalid coordinates):**
- **`TestEdgeCaseScoreZero` (3)** — wildfire/flood scorers both correctly
  return exactly 0 with no hazard data; aggregator of (0, 0) is 0/"low"
- **`TestEdgeCaseScoreHundred` (2)** — aggregator of (100, 100) is 100/"critical";
  flood scorer stays capped at 100 even with absurdly extreme rainfall input
- **`TestEdgeCaseMissingData` (3)** — a property missing `latitude` raises
  `KeyError` (not silently defaulting - confirms this is a hard requirement,
  not an optional field); a property missing `is_in_floodplain` correctly
  defaults to `False`; missing weather data correctly zeroes the
  environment factor rather than crashing
- **`TestEdgeCaseInvalidCoordinates` (2)** — both scorers raise `ValueError`
  (via `calculate_distance`'s own validation) when the property's
  coordinates are out of range and at least one hazard row exists to
  compare against

**Closing the two real gaps found up front:**
- **`TestScoringEngineRiskLevelCounts` / `TestScoringEngineErrorIsolation`
  (2)** — using a `VariableScorer` test double (returns a fixed score per
  `property_id`, or raises for specific ones) to directly drive
  `RiskScoringEngine.score_all_properties()` through its `high_risk_count`
  and `critical_count` branches, and its per-property error-isolation
  branch, without needing real hazard data engineered to land in a precise
  score band
- **`TestScoringUtilsMalformedData` (4)** — `parse_weather_extras()`/
  `parse_gauge_extras()` both fall back cleanly to empty defaults when
  `raw_data` contains malformed JSON, and both handle a `None` row

---

## Verification Results

```
pytest tests/test_risk_scoring.py -v
28 passed in 0.34s

pytest tests/test_risk_scoring.py --cov=src/risk_scoring --cov-report=term-missing
Name                                  Stmts   Miss  Cover   Missing
src\risk_scoring\__init__.py              5      0   100%
src\risk_scoring\aggregator.py           41      1    98%   61
src\risk_scoring\flood_scorer.py         80      4    95%   102, 118, 173, 226
src\risk_scoring\scoring_engine.py       48      0   100%
src\risk_scoring\scoring_utils.py        18      0   100%
src\risk_scoring\wildfire_scorer.py      85      0   100%
TOTAL                                   277      5    98%
```

**98% coverage - well above the 85% target.** Both real gaps identified
before writing (`scoring_engine.py`, `scoring_utils.py`) are now at 100%.
The handful of remaining uncovered lines in `aggregator.py`/`flood_scorer.py`
are branches this file doesn't happen to touch but are already fully
covered by the existing per-component suites (e.g. `aggregator.py` line 61
is the `"critical"` classification branch, exercised in
`test_aggregator_pytest.py`) - not a real gap, just not re-tested here to
avoid duplication.

**Full project test suite (Tasks 4-29 combined): 534 passed in 44.78s** ✓
(506 prior + 28 new). Purely unit-level (temp databases and in-memory test
doubles throughout) - no live-database demo or cleanup needed for this task.

---

## Files Created/Modified

| File | Purpose |
|------|---------|
| `tests/test_risk_scoring.py` | New pytest suite (28 tests), edge-case and gap-filling coverage of `src/risk_scoring/` |

---

## Following Reference Principles

**Data Quality as a First-Class Concern** ✓ — the explicit missing-data test
(`test_wildfire_scorer_missing_latitude_raises`) confirms a genuinely
important invariant: a property without coordinates should fail loudly
(`KeyError`), not silently produce a meaningless score.

**Reliability Over Cleverness** ✓ — the wind-escalation test failures on
first run are exactly the kind of bug this task exists to catch: an
assumption about bearing geometry that looked right on paper but was wrong,
caught immediately by a failing assertion rather than shipped as a subtly
incorrect wind-direction check.

---

## Usage Going Forward

```bash
pytest tests/test_risk_scoring.py -v
pytest tests/test_risk_scoring.py --cov=src/risk_scoring --cov-report=term-missing
```

---

## Next Task

**Task 30: Write Integration Tests for Continuous Monitoring**
- Likely a similar gap-filling exercise given `Monitor` (Task 23),
  `SchedulerManager` (Task 24), and `ChangeDetector` (Task 22) already have
  substantial dedicated suites from their own tasks - check actual coverage
  first before deciding scope, same approach as Tasks 28-29

---

**Status:** Task 29 Complete ✓
**Phase 6 (Testing & Documentation) — 2 of 7 tasks complete.**
**Ready for:** Task 30 - Integration Tests for Continuous Monitoring
