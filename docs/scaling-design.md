# Scaling Design: Geographic-Cell Data Ingestion

**Status:** Approved design, implemented in Task 14
**Applies to:** `src/data_ingestion/ingestion_engine.py`, `rate_limiter.py`, `geo_utils.assign_grid_cell()`

---

## The Problem

The MVP operates on 100 properties. Production deployments are expected to reach
thousands or more. The naive approach — one hazard-data API call per property per
monitoring cycle — does not scale:

| Portfolio size | Weather calls/cycle (naive) | Time at 60 calls/min (OpenWeatherMap free tier) |
|---|---|---|
| 100 properties | 100 | ~1.7 minutes |
| 10,000 properties | 10,000 | ~2.8 hours |
| 100,000 properties | 100,000 | ~27.8 hours |

At production scale, the naive approach cannot complete a single ingestion cycle
within the 5-minute monitoring interval, regardless of how the code is written —
the problem is architectural, not a matter of optimizing request speed.

---

## The Insight: Hazard Data Varies by Location, Not by Property

Weather, wildfire proximity, and flood conditions are properties of **geography**,
not of individual insured properties. Two properties 500 meters apart experience
effectively identical weather. There is no informational value in querying the same
conditions twice just because two different policies happen to cover that area.

**Therefore: the unit of ingestion work should be a geographic cell, not a property.**

```
100 properties in 10 states     → ~10-15 cells → ~15 weather calls/cycle
100,000 properties, same states → ~10-15 cells → ~15 weather calls/cycle (unchanged!)
100,000 properties, all 50 states → ~150-200 cells → ~200 calls/cycle
```

**API call volume scales with geographic footprint, not portfolio size.** Growing
the book of business within already-covered regions costs nothing extra. This is the
property that makes the design genuinely production-shaped rather than a stopgap
that will need rework at the next order of magnitude.

---

## Architecture

### 1. Grid-Cell Assignment (`src/utils/geo_utils.py`)

```python
def assign_grid_cell(lat: float, lon: float, cell_size_degrees: float = 0.5) -> Tuple[float, float]:
    """Round a coordinate to its containing grid cell's centroid."""
```

Every property is assigned to a cell by rounding its coordinates to the nearest
`cell_size_degrees` grid line. Properties sharing a cell share hazard data.

`cell_size_degrees` is configurable (`config/settings.json` → `ingestion.grid_cell_size_degrees`).
Smaller cells → more precision, more API calls. Larger cells → fewer calls, coarser
resolution. 0.5° (~55km) is the MVP default — the same order of magnitude as the
50km proximity radius already used for wildfire risk scoring.

### 2. Rate Limiting (`src/data_ingestion/rate_limiter.py`)

```python
class RateLimiter:
    def __init__(self, calls_per_minute: int): ...
    def wait_if_needed(self) -> None: ...
```

One shared, reusable component wrapped around each ingester's HTTP calls, configured
per-provider in `config/settings.json` (each `data_sources.*` section gets a
`calls_per_minute` field). This guarantees provider limits are respected **regardless
of cell count** — the limiter paces requests; it does not fail or drop them.

### 3. Freshness-Aware Skip

Before fetching hazard data for a cell, `IngestionEngine` checks whether a
sufficiently recent `hazard_data` row already exists for that cell/source. If so, the
fetch is skipped for this cycle. This keeps cycle time bounded as cell count grows,
and avoids wasteful duplicate calls when multiple monitoring cycles overlap with
still-fresh data.

### 4. Property-to-Hazard Matching Stays at Query Time (No Change Needed)

`hazard_data` (Task 3 schema) has **no `property_id` foreign key** — hazard records
are stored independently, keyed by coordinates. This was already the right design
before this task existed: risk scoring (Task 15+) performs the spatial join
("hazards within 50km of property X") at *query* time, not at ingestion time.

This means growing the portfolio never requires changing how hazard data is matched
to properties — only the number of grid cells queried changes, and that is driven
by data (where properties actually are), not by code.

---

## What Is Deliberately Kept Simple for Now

| Not built yet | Why it's fine to defer |
|---|---|
| Async/concurrent cell fetching | At 10-200 cells, sequential + rate-limited is fast enough. `IngestionEngine.run_ingestion_cycle()` is the sole entry point — swapping in a concurrent executor internally later requires no caller-facing changes. |
| External cache (Redis, etc.) | The freshness check against `hazard_data` itself is sufficient at this scale; a dedicated cache layer would be premature infrastructure. |
| Dynamic/adaptive cell sizing | Fixed `cell_size_degrees` from config is sufficient for the MVP's geographic spread (10 states). Adaptive density-based clustering is a reasonable future enhancement, not a current requirement. |

---

## Summary Table

| Concern | Design | Why it scales |
|---|---|---|
| API call volume | Per grid-cell, not per-property | Scales with geography, not portfolio size |
| Rate limits | One shared, configurable `RateLimiter` | Tunable per provider without code changes |
| Refetching | Skip if a fresh reading already exists this cycle | Keeps cycle time bounded as cells grow |
| Property↔hazard matching | Spatial join at risk-scoring time (Task 3 design, unchanged) | No change needed as scale grows |
| Concurrency | Sequential for now, swappable later | Interface doesn't leak this detail to callers |

---

## Related Documentation

- [task-breakdown.md](task-breakdown.md) — Task 14 full spec
- [reference-principles.md](reference-principles.md) — Principle 9 (Scalability From Day One), Principle 2 (Real-Time Over Static)
- [implementation-plan.md](implementation-plan.md) — Section 5 (Risk Scoring Logic), Section 10 (Key Technical Decisions)
