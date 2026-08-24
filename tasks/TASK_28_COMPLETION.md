# Task 28: Write Unit Tests for Utilities - COMPLETED ✓

**Completed:** 2026-08-03
**Status:** `tests/test_utils.py` created with dedicated, exhaustive coverage of
every function in `src/utils/` — the first task of Phase 6 (Testing &
Documentation).

---

## What Was Completed

### Coverage Gap Identified First

Before writing anything, checked actual current coverage of `src/utils/`
across the *whole* existing test suite (not just Task 4's original
`test_utils_pytest.py`), since many utility functions are already exercised
indirectly by other suites (e.g. `calculate_distance` via wildfire scorer
tests, `is_within_hours`/`parse_iso_timestamp` via `AlertDAO` tests):

```
pytest tests/ --cov=src/utils --cov-report=term-missing
Name                      Stmts   Miss  Cover
src\utils\geo_utils.py      115     54    53%
src\utils\time_utils.py     115     74    36%
src\utils\validation.py     185    130    30%
TOTAL                       419    258    38%
```

Only 38% - well short of the 80% target, and `validation.py` in particular
(`validate_property_data`, `validate_risk_assessment`, `validate_hazard_data`,
`validate_alert`) is barely touched anywhere in the codebase today. This
confirmed Task 28 needed genuinely new, direct tests, not just a
verification pass.

### `tests/test_utils.py` (new, 114 tests)

Direct unit tests for all 7 `geo_utils.py` functions, all 15 `time_utils.py`
functions, and all 6 `validation.py` functions:

- **`TestCalculateDistance` (6)** — known real-world distance, identical
  points = 0, symmetry, antipodal points ≈ half Earth's circumference,
  invalid-coordinate errors on either point
- **`TestIsValidCoordinate` (8)** — valid/boundary values, out-of-range
  lat/lon, NaN, Infinity, non-numeric, numeric strings
- **`TestGetBearing` (6)** — cardinal directions (N/E/S/W) verified exactly,
  result always in [0, 360), invalid-coordinate error
- **`TestIsDownwind` (4)** — directly downwind, directly upwind,
  perpendicular, invalid-coordinate error
- **`TestGetDistanceCategory` (4)** — all four category boundaries
  (immediate/near/moderate/far) tested at their edges
- **`TestHaversineDistance` (1)** — confirmed to be a true alias of
  `calculate_distance`
- **`TestAssignGridCell` (6)** — nearby points share a cell, distant points
  don't, returns a centroid (not the raw input), deterministic, invalid
  coordinates and non-positive cell size both raise
- **Time utilities (34 tests across 9 classes)** — every relative-time
  helper (`hours_ago`/`minutes_ago`/`days_ago`/`seconds_ago`), `time_since`,
  `is_older_than`/`is_within_hours` (including naive-datetime handling),
  the monitoring-cycle trio (`get_monitoring_cycle_time`/`get_last_cycle_time`/
  `next_cycle_in`), `format_timestamp`, `parse_iso_timestamp` (Z-suffix,
  explicit offset, naive string, invalid format, round-trip), `get_date_range`,
  and `is_business_hours` at every boundary hour
- **Validation utilities (39 tests across 6 classes)** — every validator
  (`validate_coordinate`, `validate_property_data`, `validate_risk_score`,
  `validate_risk_assessment`, `validate_hazard_data`, `validate_alert`)
  tested for both valid input and every distinct rejection branch (missing
  fields, wrong types, out-of-range values, invalid enum values)

**Bug found in test authoring, not source code:** two tests initially used
`datetime.now()` (local time) where the intent was "a naive-but-effectively-UTC
timestamp." On this machine (UTC+5 local), that made a "5 minutes ago"
timestamp read as ~5 hours in the *future* when `time_since()` treated it as
UTC, producing a large negative elapsed time (`-19499` seconds) - caught
immediately by `test_handles_naive_datetime` failing. Fixed by deriving the
naive timestamp from `get_utc_now().replace(tzinfo=None)` instead, which is
correct regardless of the machine's local timezone (and avoids
`datetime.utcnow()`, deprecated in current Python).

### `.coveragerc` (new)

Added `exclude_lines = if __name__ == .__main__.:` so each module's
`if __name__ == "__main__":` demo/manual-test block (which never executes
under pytest, by design - each file already has its own hands-on demo,
e.g. `python -m src.utils.geo_utils`) doesn't count against coverage. This
is a reporting-accuracy fix, not a test-behavior change - excluding
intentionally-non-executed demo code is standard practice, not coverage
gaming.

---

## Verification Results

```
pytest tests/test_utils.py -v
114 passed in 0.43s

pytest tests/test_utils.py --cov=src/utils --cov-report=term-missing
Name                      Stmts   Miss  Cover   Missing
src\utils\__init__.py         4      0   100%
src\utils\geo_utils.py       70      2    97%   81, 83
src\utils\time_utils.py      62      0   100%
src\utils\validation.py     149      3    98%   16-17, 98
TOTAL                       285      5    98%
```

**98% coverage - well above the 80% target.** The 5 remaining uncovered
lines are all legitimately dead code, not gaps in testing:
- `geo_utils.py` 81, 83 — NaN/Infinity checks in `is_valid_coordinate()`
  that sit *after* the range check (`-90 <= lat <= 90`), which already
  returns `False` for NaN/Infinity (any comparison against NaN is `False`)
  before execution ever reaches these lines
- `validation.py` 16-17 — an `ImportError` fallback for running
  `geo_utils.py` as a bare script outside the `src` package, never taken
  under normal package import
- `validation.py` 98 — a `max_val` upper-bound check in
  `validate_property_data()`'s generic numeric-field loop; none of the
  currently-configured fields (`elevation_m`, `property_id`) actually set a
  `max_val`, so the branch body is unreachable with today's field config

**Full project test suite (Tasks 4-28 combined): 506 passed in 44.84s** ✓
(392 prior + 114 new).

---

## Files Created/Modified

| File | Purpose |
|------|---------|
| `tests/test_utils.py` | New pytest suite (114 tests), dedicated coverage of `src/utils/` |
| `.coveragerc` | New - excludes `__main__` demo blocks from coverage reporting |

`tests/test_utils_pytest.py` (Task 4's original, lighter suite) was left
in place unmodified - no conflict, and it continues to serve as the
original smoke-test coverage from early in the project.

---

## Following Reference Principles

**Data Quality as a First-Class Concern** ✓ — the naive-datetime test bug is
exactly the kind of timezone-handling mistake that causes silent data
corruption in production (a "5 minutes ago" that's actually hours off);
catching it here, in a fast unit test, is far cheaper than catching it via a
live alert firing at the wrong time.

**Reliability Over Cleverness** ✓ — `validation.py`'s functions
(`validate_property_data`, `validate_risk_assessment`, `validate_hazard_data`,
`validate_alert`) were essentially untested despite being the intended
data-quality gate for anything ingested from external sources; this task
closes that gap so a future integration point can rely on them with
confidence.

---

## Usage Going Forward

```bash
pytest tests/test_utils.py -v
pytest tests/test_utils.py --cov=src/utils --cov-report=term-missing
```

---

## Next Task

**Task 29: Write Unit Tests for Risk Scoring**
- Dedicated coverage pass for `src/risk_scoring/` (wildfire/flood scorers,
  aggregator, scoring engine) - much of this already has indirect coverage
  from earlier tasks (15-19), so this will likely be a smaller, gap-filling
  effort similar in spirit to today's coverage-first approach

---

**Status:** Task 28 Complete ✓
**Phase 6 (Testing & Documentation) — 1 of 7 tasks complete.**
**Ready for:** Task 29 - Unit Tests for Risk Scoring
