# Task 14: Integrate Ingestion into Single Data Ingestion Pipeline - COMPLETED ✓

**Completed:** 2026-07-22
**Status:** `IngestionEngine` built with geographic-cell design, verified live and offline.

---

## What Was Completed

This task closes the "how do we know which coordinates to query?" gap flagged before
Task 10 — and does so with a design intended to scale from 100 properties to
100,000+ **without code changes**. Full rationale in
[docs/scaling-design.md](../docs/scaling-design.md); summary below.

### `src/utils/geo_utils.py` — `assign_grid_cell()`

```python
def assign_grid_cell(lat, lon, cell_size_degrees=0.5) -> Tuple[float, float]
```

Rounds a coordinate to its containing grid cell's centroid. Two coordinates in the
same cell always return the identical centroid, making it usable directly as a
grouping key.

### `src/data_ingestion/rate_limiter.py` — `RateLimiter` class

```python
class RateLimiter:
    def __init__(self, calls_per_minute: int)
    def wait_if_needed() -> float
```

One shared, reusable component; each provider gets its own instance, configured from
`config/settings.json`. Uses a simple fixed-window sleep strategy — sufficient at this
project's call volumes (documented as a deliberate simplification, swappable later
without changing the public interface).

### `src/data_ingestion/ingestion_engine.py` — `IngestionEngine` class

```python
class IngestionEngine:
    def run_ingestion_cycle() -> Dict
```

**Behavior:**
1. Groups the entire property portfolio (via `PropertyDAO`) into grid cells
2. For each cell: fetches wildfire (bbox) and river gauges (bbox) around the cell,
   and weather + precipitation (point) at the cell centroid
3. **Freshness-aware skip:** before each fetch, checks whether a sufficiently recent
   `hazard_data` row already exists for that cell/source (`ingestion.freshness_minutes`,
   default 4) — skips the API call entirely if so
4. **Error isolation:** each of the four fetch operations per cell is wrapped in its
   own `try/except`; one source failing does not prevent the others from completing
5. Each provider's calls are paced through its dedicated `RateLimiter`
6. Returns a summary: `fires_ingested`, `weather_points`, `precipitation_points`,
   `gauge_readings`, `cells_processed`, `cells_skipped_fresh`, `errors`

### `config/settings.json` — New Configuration

- Added `calls_per_minute` to each `data_sources.*` section (NASA FIRMS: 30,
  OpenWeatherMap: 50, USGS: 30)
- New `ingestion` section: `grid_cell_size_degrees` (0.5°, ~55km) and
  `freshness_minutes` (4 — just under the 5-minute monitoring interval, so each new
  monitoring cycle re-fetches while redundant calls within the same cycle are skipped)

---

## Verification Results

### Cell Count on the Real 100-Property Portfolio

```
Total unique cells: 82 (from 100 properties)
```

**Honest finding, documented rather than glossed over:** this is a modest reduction,
not a dramatic one — because Task 7's synthetic property generator scatters
properties *widely* within each state (e.g., California's cluster spread is 2.2°,
several times larger than the 0.5° cell size). Real production portfolios cluster far
more densely (many policies within the same city), where this design would show a
much larger reduction. The architecture is correct regardless of dataset density —
call volume is always bounded by geographic footprint, not portfolio size — but the
demo dataset's artificial spread means the MVP doesn't showcase the full effect.
`grid_cell_size_degrees` is also tunable if coarser cells are preferred.

### Bounded Live Smoke Test (Real APIs, Real Data)

Running all 82 cells live would mean 300+ real API calls purely for a verification
step, when each individual ingester was already proven live in Tasks 10-12. Instead,
ran a **bounded live test against 2 real cells** to prove the orchestration layer
itself works end-to-end for real, before relying on the offline suite for full
coverage:

```
First run  (cold):  30 fires, 2 weather points, 2 precipitation points,
                     215 gauge readings, 2 cells processed, 0 skipped, 0 errors
                     (43.4 seconds, rate-limited across 4 providers)

Second run (immediate re-run, same 2 cells):
                     0 fires, 0 weather points, 0 precipitation points,
                     0 gauge readings, 0 cells processed, 8 cells skipped (fresh)
                     (0.0 seconds - zero API calls made)
```

The second run is the key proof point: **the freshness-skip mechanism works
correctly against the real database and real timestamps**, not just in a mocked
test. This is the specific property that keeps repeated cycles fast and cheap at
scale. Test data was cleared afterward (`DELETE FROM hazard_data`).

### Pytest Suite (Offline, Deterministic)

**`tests/test_rate_limiter_pytest.py` — 5 tests**
- Rejects non-positive `calls_per_minute`
- First call never waits; second call waits ~the configured interval
- A call arriving after a natural delay doesn't over-wait
- `reset()` correctly restores first-call behavior

**`tests/test_ingestion_engine_pytest.py` — 13 tests**, using hand-built fakes for
`PropertyDAO` and all three ingesters (no network, no real API keys):

- `TestGridCellGrouping` (3) — nearby properties share one cell; far properties
  produce separate cells; cell count never exceeds property count
- `TestFreshnessCheck` (4) — no existing data is not fresh; recent data is fresh;
  old data (past the threshold) is not fresh; a different source's data doesn't
  count as freshness for another source
- `TestRunIngestionCycle` (6) — all four sources counted correctly; **a second run
  is fully skipped as fresh** (the same property proven live above, now also
  covered offline); a simulated NASA FIRMS failure does not block weather/flood
  from succeeding; missing weather data doesn't error; an empty portfolio completes
  cleanly; the rate limiter is actually invoked once per source call

```
tests/test_rate_limiter_pytest.py       ..... 5 passed
tests/test_ingestion_engine_pytest.py   ............. 13 passed
```

### Two Test-Authoring Bugs Found and Fixed While Writing the Suite

Both in test fixtures, not source code — worth documenting for the same reason as
Task 12's similar finding:

1. The fake ingesters' `store_*()` methods initially only *counted* records instead
   of actually inserting them into the temp database — meaning the freshness check
   (which queries real rows) could never find anything on a "second run," making the
   test pass or fail for the wrong reason. Fixed by having the fakes perform a real
   `INSERT` against the schema, mirroring what the actual ingesters do.
2. `SAMPLE_GAUGE`'s coordinates were copied from an earlier Louisiana example, while
   the test's portfolio property was in California — completely different grid
   cells, so the freshness bounding-box check correctly found no match. Fixed by
   aligning the fixture's coordinates with the cell actually under test.

**Full project test suite (Tasks 4-14 combined): 162 passed in 1.79s** ✓

---

## Files Created/Modified

| File | Change |
|------|--------|
| `src/utils/geo_utils.py` | Added `assign_grid_cell()` + demo test |
| `src/utils/__init__.py` | Exported `assign_grid_cell` |
| `src/data_ingestion/rate_limiter.py` | New — `RateLimiter` class (75 lines) |
| `src/data_ingestion/ingestion_engine.py` | New — `IngestionEngine` class (200 lines) |
| `config/settings.json` | Added `calls_per_minute` per source, new `ingestion` section |
| `tests/test_rate_limiter_pytest.py` | New — 5 tests |
| `tests/test_ingestion_engine_pytest.py` | New — 13 tests |
| `docs/scaling-design.md` | New (written before implementation) — full design rationale |
| `docs/task-breakdown.md` | Task 14 rewritten with new scope |
| `docs/implementation-plan.md` | New trade-off row + updated risk mitigation |

---

## Following Reference Principles

**Scalability From Day One** ✓ — this task *is* the concrete embodiment of this
principle for data ingestion: the design was chosen and documented specifically so
that growing from 100 to 100,000+ properties requires zero code changes, only more
grid cells being processed.

**Real-Time Over Static** ✓ — the freshness check keeps the system honest about "how
current is this data" rather than either always refetching (wasteful) or caching
indefinitely (stale).

**Data Quality as a First-Class Concern** ✓ — error isolation means a single
provider outage degrades the cycle's completeness, not its correctness: sources that
succeed are still stored and used, rather than one failure discarding an entire
cycle's data.

---

## Usage Going Forward

```python
from src.data_ingestion.ingestion_engine import IngestionEngine

engine = IngestionEngine()
summary = engine.run_ingestion_cycle()
print(f"{summary['cells_processed']} cells fetched, "
      f"{summary['cells_skipped_fresh']} skipped as fresh, "
      f"{len(summary['errors'])} errors")
```

Or from the command line:
```bash
python -m src.data_ingestion.ingestion_engine
```

---

## Next Task

**Phase 3 begins: Task 15 — Implement Wildfire Risk Scoring Algorithm**
- Build `src/risk_scoring/wildfire_scorer.py` — a `WildFireScorer` class
- First task to actually *use* the hazard data this phase has been ingesting:
  proximity, wind-driven escalation, fire intensity, and environmental factors
  combined into an explainable 0-100 risk score per property
- This is also where the spatial join between properties and hazard data (by
  proximity, not by cell) finally happens — completing the design loop this task
  set up

---

**Status:** Task 14 Complete ✓
**Phase 2b (Data Ingestion, Tasks 10-14) fully complete.**
**Ready for:** Task 15 - Wildfire Risk Scoring Algorithm
