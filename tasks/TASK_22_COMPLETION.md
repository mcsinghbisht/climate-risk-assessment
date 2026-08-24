# Task 22: Implement Change Detection (Score Comparison) - COMPLETED ✓

**Completed:** 2026-07-24
**Status:** `ChangeDetector` built, tested, and verified — first content in the previously-empty `continuous_monitoring` module.

---

## What Was Completed

### `src/continuous_monitoring/change_detector.py` — `ChangeDetector` class

```python
class ChangeDetector:
    def detect_changes(property_id, current_assessment, previous_assessment: Optional[Dict] = None) -> Dict
```

Compares two `risk_assessments`-shaped dicts (as produced by `RiskDAO`, Task 18) and
reports what actually changed:

```python
{
    "property_id": 1,
    "changed": True,
    "is_baseline": False,
    "risk_delta": 32.09,
    "risk_level_changed": True,
    "trend": "worsening",
    "factors_changed": [
        {"factor": "wildfire.distance_km", "from": 15.0, "to": 5.86},
        {"factor": "wildfire.proximity_score", "from": 60.0, "to": 88.28},
        {"factor": "wildfire.wind_score", "from": 0.0, "to": 75.0},
    ],
}
```

**Deliberately kept separate from `AlertEngine` (Task 20)**, as discussed: `AlertEngine`
answers "should we notify someone?" (only fires on threshold crossings);
`ChangeDetector` answers "what actually changed?" — useful even for moves too small
to alert on, and granular enough to identify *which specific factor* shifted, not
just the overall score.

**Factor-level diffing**, not just score comparison: `_diff_factors()` compares the
`wildfire_factors`/`flood_factors` dicts key-by-key, with two deliberate exclusions
from being noise:
- `explanation` is skipped — it's a natural-language rendering of the other factors,
  not itself a factor, and would flag cosmetic wording differences as "changes"
- Float values within `FLOAT_TOLERANCE` (0.01) are treated as unchanged, avoiding
  false positives from floating-point rounding noise

**Graceful baseline handling:** a property's first-ever assessment (`previous_assessment=None`)
reports `is_baseline: True`, `trend: "baseline"`, `changed: False` — not an error, not
a fabricated "0 change," just an honest "nothing to compare against yet."

---

## Verification Results

### Manual Demo (Four Scenarios)

```bash
python -m src.continuous_monitoring.change_detector
```
```
1. Worsening scenario (fire got closer, wind picked up)
   changed=True, delta=32.09, trend=worsening
   risk_level_changed=True
   - wildfire.distance_km: 15.0 -> 5.86
   - wildfire.proximity_score: 60.0 -> 88.28
   - wildfire.wind_score: 0.0 -> 75.0

2. Improving scenario (same data, reversed)
   changed=True, delta=-32.09, trend=improving

3. No change
   changed=False, delta=0.0, trend=stable

4. First-ever assessment (no previous)
   changed=False, is_baseline=True, trend=baseline
```

All four match expectations exactly on the first run — notably, the flood factors
(unchanged between the two scenarios) were correctly excluded from
`factors_changed`, confirming the diffing logic only reports what actually moved.

### Pytest Suite

Created `tests/test_change_detector_pytest.py` with **19 tests** across five classes:

**TestBaseline (1)** — no previous assessment reports a clean baseline, not an error

**TestTrend (4)** — increased score → worsening; decreased → improving; identical →
stable and `changed: False`; a tiny float difference in the overall score doesn't
read as noise after rounding

**TestRiskLevelChange (3)** — a risk-level bucket change is detected independently
of the score change; same level isn't flagged; **a risk-level change alone (even
with an identical score) still counts as `changed: True`** — an edge case worth
testing explicitly since it's easy to accidentally gate `changed` on `risk_delta`
alone

**TestFactorDiffing (9)** — a changed factor is reported with correct
`from`/`to`; an unchanged factor is not; multiple changes are all captured; wildfire
and flood factors are both diffed independently; **`explanation` is correctly
ignored**; **float noise within tolerance is not reported**; a key present only in
the current assessment (not the previous) is reported with `from: None`; missing
factors dicts entirely don't crash; **string factor values (not just numbers) are
also diffed correctly** (e.g., `distance_category` flipping from "far" to "near")

**TestResultShape (2)** — `property_id` matches input; the result always has all
seven expected keys

```
tests/test_change_detector_pytest.py ................... 19 passed
```

**Full project test suite (Tasks 4-22 combined): 314 passed in 7.03s** ✓ — zero bugs
found, continuing the pattern from Task 21b: composing already-tested, well-defined
components (here, just diffing two already-validated dict shapes) tends to go
smoothly when the upstream contracts are solid.

---

## Files Created/Modified

| File | Purpose |
|------|---------|
| `src/continuous_monitoring/change_detector.py` | `ChangeDetector` class (140 lines) |
| `src/continuous_monitoring/__init__.py` | First real content in this previously-empty module |
| `tests/test_change_detector_pytest.py` | Pytest suite (19 tests) |

---

## Following Reference Principles

**Transparency and Explainability** ✓ — `factors_changed` gives a precise,
structured answer to "why did this score move," at the level of individual inputs
(wind, proximity, rainfall), not just the aggregate number — directly useful for the
"improving but not resolved" narrative discussed in Task 21b's design, and for a
future LLM layer's context.

**Data Quality as a First-Class Concern** ✓ — the float tolerance and explanation
exclusion are both about the same idea: don't let cosmetic or numerical noise
masquerade as a meaningful signal.

**Scalability From Day One** ✓ — being independent of `AlertEngine` means this
component works the same whether it's comparing two consecutive 5-minute cycles or
two assessments a week apart — no assumption baked in about *when* the two inputs
came from.

---

## Usage Going Forward

```python
from src.continuous_monitoring import ChangeDetector
from src.database import RiskDAO

risk_dao = RiskDAO()
history = risk_dao.get_assessment_history(property_id, days=1)
current = history[0] if history else None
previous = history[1] if len(history) > 1 else None

if current:
    result = ChangeDetector().detect_changes(property_id, current, previous)
    if result["changed"]:
        print(f"Property {property_id} is {result['trend']}: {result['risk_delta']:+.1f} points")
```

---

## Next Task

**Task 23: Create Continuous Monitoring Loop**
- Build `src/continuous_monitoring/monitor.py` — a `Monitor` class
- `run_monitoring_cycle()` — the first component to orchestrate **everything** built
  so far in one call: ingestion (Task 14) → scoring (Task 19) → change detection
  (Task 22) → alerting (Tasks 20-21b)
- This is the single cycle that Task 24's scheduler will then run every 5 minutes

---

**Status:** Task 22 Complete ✓
**Phase 4 (Alerts & Monitoring) — 4 of 6 tasks complete.**
**Ready for:** Task 23 - Continuous Monitoring Loop
