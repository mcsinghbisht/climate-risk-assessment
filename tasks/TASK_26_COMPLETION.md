# Task 26: Implement Hotspot Detection - COMPLETED ✓

**Completed:** 2026-08-03
**Status:** `HotspotDetector` built, tested, and verified — the geographic-clustering
half of accumulation tracking, complementing `PortfolioAggregator`'s (Task 25)
portfolio-wide numbers with *where* risk is concentrated.

**Scoping note:** earlier discussion floated folding the deferred >10%
portfolio-level alert into this task. Re-checking `docs/task-breakdown.md`
showed Task 26 is scoped narrowly to spatial clustering only — no alerting.
Implemented exactly as specified; the portfolio alert placement is still an
open decision for a later task.

---

## What Was Completed

### `src/portfolio/hotspot_detector.py` — `HotspotDetector` class

```python
class HotspotDetector:
    def detect_hotspots(self, radius_km: Optional[float] = None) -> List[Dict]
```

**Algorithm:** every assessed property is tried as a candidate cluster
center; all other assessed properties within `radius_km` (real great-circle
distance via Task 9's `calculate_distance`) become its members. A candidate
becomes a hotspot if it has at least `hotspot_min_properties` members and
their average risk score exceeds `hotspot_risk_threshold`. Candidates are
then de-duplicated via **non-max suppression**: sorted by `avg_risk` (then
size) descending, a candidate is kept only if its center isn't already
within `radius_km` of a previously-kept hotspot — otherwise a dense
high-risk area would report one near-identical hotspot per member property
instead of one hotspot for the whole cluster. Verified this explicitly (see
below): 5 co-located high-risk properties correctly produce exactly 1
hotspot, not 5.

**New config value added:** `config/settings.json`'s existing `portfolio`
section already had `hotspot_radius_km: 50` and `hotspot_min_properties: 3`
(set up earlier, unused until now) but was missing the risk-threshold
itself. Added `hotspot_risk_threshold: 50`, aligned with the existing
`risk_scoring.risk_levels.medium_max: 50` — a cluster only counts as a
hotspot once its average pushes past "medium" into "high" territory,
keeping the two threshold systems conceptually consistent rather than
picking an arbitrary new number.

**Result shape:**
```python
[{
    "center_lat": 32.518971, "center_lon": -118.030396,
    "property_count": 3, "avg_risk": 81.67,
    "properties": [
        {"property_id": 6, "risk_score": 80.0},
        {"property_id": 17, "risk_score": 75.0},
        {"property_id": 18, "risk_score": 90.0},
    ],
}]
```
`properties` carries each member's `risk_score` alongside its ID (a richer
shape than the task spec's illustrative `properties: []`) — consistent with
the project's explainability principle and directly useful input for
Task 27's reporter.

**Known MVP simplification, documented in the module docstring**: O(n²)
distance comparisons across the assessed portfolio per call — same category
of "correct and simple today, revisit if the portfolio grows substantially"
already flagged for `RiskScoringEngine`'s full-table fetch (Task 19).

---

## Verification Results

### Live Demo (Real Database)

Clean-slate real DB (0 assessments): `detect_hotspots()` returned `[]`
immediately, no crash.

Found a real 3-property cluster among the 100 actual generated properties
(properties 6, 17, 18 — all within 50km of each other, confirmed via
`calculate_distance`) and assigned synthetic high-risk assessments
(80, 75, 90), plus 3 unrelated low-risk properties elsewhere as a control:

```json
[{
  "center_lat": 32.518971, "center_lon": -118.030396,
  "property_count": 3, "avg_risk": 81.67,
  "properties": [
    {"property_id": 6, "risk_score": 80.0},
    {"property_id": 17, "risk_score": 75.0},
    {"property_id": 18, "risk_score": 90.0}
  ]
}]
```

Exactly 1 hotspot, correctly excluding the 3 low-risk control properties.
Then added a 4th high-risk property (id 7, ~55-84km from the existing
cluster — outside the 50km radius from any single member) and re-ran:
still exactly 1 hotspot with the same 3 members, confirming non-max
suppression doesn't fragment or duplicate the cluster.

All affected tables (`hazard_data`, `risk_assessments`, `alerts`,
`alert_history`) cleaned back to 0 rows afterward; `properties` unchanged
at 100.

### Pytest Suite

Created `tests/test_hotspot_detector_pytest.py` — **14 tests**, using
exact-distance coordinate fixtures (co-located points for distance-0
clusters, ~1° latitude apart for a known ~111km separation) rather than
real addresses, so distances are easy to reason about precisely:

**TestEmptyOrSparsePortfolio (3)** — no properties returns no hotspots;
fewer than `min_properties` assessed returns none even if all are high-risk;
unassessed properties are correctly excluded from the count

**TestClusterDetection (6)** — a tight co-located high-risk cluster is
detected with correct member set and avg_risk; a low-risk cluster of the
same size is *not* flagged; properties ~111km apart (beyond the 50km
default) are not clustered; a custom `radius_km` argument correctly widens
the cluster; avg_risk is the precise mean, not an approximation; a distant
isolated property (even if itself high-risk) is excluded from a nearby
cluster's membership

**TestNonMaxSuppression (3)** — 5 co-located high-risk properties produce
exactly 1 hotspot, not one per property; two genuinely separate clusters
(~666km apart) are both reported independently; hotspots are returned
sorted by `avg_risk` descending

**TestResultShape (2)** — every hotspot has all five expected keys; every
member entry includes both `property_id` and `risk_score`

```
tests/test_hotspot_detector_pytest.py .............. 14 passed in 0.89s
```

**Full project test suite (Tasks 4-26 combined): 369 passed in 41.38s** ✓
(355 prior + 14 new).

---

## Files Created/Modified

| File | Purpose |
|------|---------|
| `src/portfolio/hotspot_detector.py` | `HotspotDetector` class (new) |
| `src/portfolio/__init__.py` | Now exports `HotspotDetector` alongside `PortfolioAggregator` |
| `config/settings.json` | Added `portfolio.hotspot_risk_threshold: 50` |
| `tests/test_hotspot_detector_pytest.py` | Pytest suite (14 tests) |

---

## Following Reference Principles

**Portfolio Visibility & Accumulation Tracking** ✓ — this is the piece of
"catastrophic losses due to poor accumulation tracking and risk clustering"
(the project's own problem statement) that a portfolio-wide average alone
can't answer: 100 properties averaging 20 risk could still contain a
3-property pocket averaging 85 that this surfaces explicitly.

**Data Quality as a First-Class Concern** ✓ — unassessed properties are
silently excluded from clustering (same principle as `PortfolioAggregator`,
Task 25) rather than treated as zero-risk noise diluting a real cluster's
average.

**Config-Driven, No Magic Numbers** ✓ — radius, minimum cluster size, and
risk threshold are all configuration-driven (`portfolio.*`), with the new
threshold deliberately aligned to the existing risk-level boundary rather
than an arbitrary new constant.

---

## Usage Going Forward

```python
from src.portfolio import HotspotDetector

hotspots = HotspotDetector().detect_hotspots()  # uses configured 50km radius
for hs in hotspots:
    print(f"({hs['center_lat']:.2f}, {hs['center_lon']:.2f}): "
          f"{hs['property_count']} properties, avg risk {hs['avg_risk']:.1f}")
```

---

## Next Task

**Task 27: Create Portfolio Reporter**
- `src/portfolio/reporter.py` (create) — `PortfolioReporter.generate_summary_report()`:
  text-based portfolio summary combining `PortfolioAggregator`'s metrics
  (Task 25), `HotspotDetector`'s clusters (Task 26), and an alerts summary
  (from `AlertDAO`, Task 21b)
- Extensible for PDF/HTML later; writes to `reports/portfolio_*.txt`
- Also the natural point to decide, explicitly, where the deferred >10%
  portfolio-level alert belongs — as part of the report itself, or as its
  own dedicated alerting step

---

**Status:** Task 26 Complete ✓
**Phase 5 (Portfolio Aggregation) — 2 of 3 tasks complete.**
**Ready for:** Task 27 - Portfolio Reporter
