# Task 33: Performance Testing - COMPLETED ✓

**Completed:** 2026-08-03
**Status:** `tests/test_performance.py` created — and a real, measured
performance characteristic of the current ingestion design was found and
documented along the way, discussed with the user before deciding how to
scope the ingestion test.

---

## A Real Finding, Before Writing Any Test

Before writing `test_ingestion_cycle`, measured what a full real ingestion
cycle against the actual 100-property portfolio would cost, with the HTTP
layer mocked (removing network latency as a variable, but leaving
`RateLimiter`'s pacing real):

```
Elapsed: 162.1s
{'fires_ingested': 0, 'weather_points': 82, 'precipitation_points': 82,
 'gauge_readings': 0, 'cells_processed': 82, 'cells_skipped_fresh': 0, 'errors': []}
```

**The real 100-property portfolio produces 82 distinct grid cells** at the
configured `grid_cell_size_degrees` (0.5°, ~55km) - because the synthetic
portfolio (Task 7) is deliberately spread across 10 states for scoring
variety, the geographic-cell aggregation designed in Task 14
([scaling-design.md](scaling-design.md)) barely reduces call volume (82
cells for 100 properties). Each cell makes up to 4 paced API calls
(`RateLimiter`, 2s/1.2s intervals per provider), and 162s comfortably
exceeds both the "<1 minute ingestion" sub-target and eats a third of the
overall "<5 minutes per cycle" budget.

**This is not a code performance bug** - it's an honest consequence of
testing a geographically-scattered synthetic portfolio against a
cell-aggregation design that assumes real-world geographic clustering (a
real insurer's book concentrated in fewer metro areas would produce far
fewer cells and stay well under budget). Flagged to the user before
deciding how `test_ingestion_cycle` should be scoped, given three options:
measure engine overhead only (neutralize rate-limiter sleeps), test against
a smaller/denser sub-portfolio, or assert the real full-portfolio time and
mark it expected-slow.

**Decision: test against a smaller, denser sub-portfolio** - properties
that share a single grid cell, so the real `RateLimiter` pacing is
exercised as-is (not neutered), while staying within the 1-minute target.
The 162s full-portfolio measurement is documented here rather than
asserted in the test suite itself, since it reflects the *test portfolio's*
geographic scatter, not a regression to chase in code.

---

## What Was Completed

### `tests/test_performance.py` (new, 4 tests)

**`TestScoringPerformance` (2)** — against the real, deterministic
100-property portfolio (`generate_properties()`, Task 7) plus a modest
hazard_data set (6 rows across a few real property locations, so scoring
does genuine proximity/wind/rainfall computation, not a trivial
empty-hazard-data short-circuit):
- `test_scoring_all_100_properties_under_time_limit` — asserts wall-clock
  time under 120s (2 minutes)
- `test_scoring_memory_usage_under_limit` — asserts peak `tracemalloc`
  allocation under 500MB

**`TestIngestionPerformance` (2)** — against a small (5-property) portfolio
clustered into a single grid cell, with the HTTP layer mocked (same
`monkeypatch.setattr(module, "requests", fake)` pattern used since Tasks
10-12, reused again in Task 30):
- `test_ingestion_cycle_under_time_limit` — asserts wall-clock time under
  60s (1 minute); also asserts `cells_processed == 1`, confirming the
  clustering assumption actually holds for this sub-portfolio
- `test_ingestion_memory_usage_under_limit` — asserts peak `tracemalloc`
  allocation under 500MB

**Memory measured via `tracemalloc`** (stdlib), not `psutil` - `psutil` is
not installed in this project's environment, and `tracemalloc` needs no
new dependency. It measures Python-level object allocation rather than
full process RSS, which is a reasonable proxy at this project's scale and
avoids adding a dependency for a single test file.

---

## Verification Results

```
pytest tests/test_performance.py -v
tests/test_performance.py::TestScoringPerformance::test_scoring_all_100_properties_under_time_limit PASSED
tests/test_performance.py::TestScoringPerformance::test_scoring_memory_usage_under_limit PASSED
tests/test_performance.py::TestIngestionPerformance::test_ingestion_cycle_under_time_limit PASSED
tests/test_performance.py::TestIngestionPerformance::test_ingestion_memory_usage_under_limit PASSED
4 passed in 1.99s
```

**Actual measured numbers** (well under every target):

| Test | Measured | Target |
|---|---|---|
| Scoring 100 properties | **0.61s** | < 120s |
| Scoring peak memory | **0.13 MB** | < 500 MB |
| Ingestion, 1 cell/5 properties | **0.016s** | < 60s |
| Ingestion peak memory | **0.02 MB** | < 500 MB |

Scoring in particular has enormous headroom - real-world bottlenecks in
this system are entirely on the ingestion/network side (as the 162s
full-portfolio finding above demonstrates), not the in-process scoring
math.

**Full project test suite (Tasks 4-33 combined): 542 passed in 48.92s** ✓
(538 prior + 4 new). All performance tests use temp databases and mocked
HTTP - the real `data/climate_risk.db` was untouched by this task.

---

## Files Created/Modified

| File | Purpose |
|------|---------|
| `tests/test_performance.py` | New pytest suite (4 tests) |

---

## Following Reference Principles

**Data Quality as a First-Class Concern**, applied to the test design
itself ✓ — measuring the real 162s full-portfolio number *before* deciding
how to scope the test (rather than assuming performance would be fine, or
writing a test that would either flake or need loosened assertions to pass)
is the same "verify against reality first" discipline this project applies
to hazard data.

**Scalability From Day One** ✓ — this finding is a direct, concrete
instance of the "revisit if the portfolio grows/spreads" caveat already
flagged in Task 14's ingestion design and Task 19/26's own documented MVP
simplifications - not a new problem, but a now-measured one.

---

## Usage Going Forward

```bash
pytest tests/test_performance.py -v
```

If ingestion timing against the *full* 100-property portfolio ever needs
active monitoring (not just this task's scoped sub-portfolio test),
`grid_cell_size_degrees` (currently 0.5°) is the first configuration lever
to widen - fewer, larger cells directly reduce the number of paced API
calls for a geographically-scattered portfolio like this one.

---

## Next Task

**Task 34: Create Main Application Entry Point**
- `src/main.py` (create) - a `main()` function with CLI args
  (`--mode run/test/report`, `--duration`, `--interval`), wiring together
  logging setup, database initialization, and `SchedulerManager` - the
  single entrypoint the Operations Guide (Task 32) noted was missing

---

**Status:** Task 33 Complete ✓
**Phase 6 (Testing & Documentation) — 6 of 7 tasks complete.**
**Ready for:** Task 34 - Main Application Entry Point
