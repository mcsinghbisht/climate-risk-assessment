# Task 20: Create Alert Threshold Engine - COMPLETED ✓

**Completed:** 2026-07-23
**Status:** `AlertEngine` built, tested, and verified — first component to use the `alerts.*` config thresholds (unused since Task 5) and the `alerts_triggered` parameter (accepted since Task 18).

---

## What Was Completed

### `src/alerts/alert_engine.py` — `AlertEngine` class

```python
class AlertEngine:
    def evaluate_property(property_id, current_risk: Dict, previous_risk: Optional[Dict] = None) -> List[Dict]
```

**Two independent trigger conditions per hazard type**, both configured since Task 5:

| Trigger | Config Key | Default | Logic |
|---|---|---|---|
| Absolute threshold | `alerts.wildfire_threshold` / `alerts.flood_threshold` | 70 / 65 | `current_score > threshold` |
| Sudden increase | `alerts.wildfire_increase_threshold` / `alerts.flood_increase_threshold` | 40 / 30 | `(current - previous) > increase_threshold` |

Wildfire and flood are evaluated completely independently. A single hazard type can
produce **up to two alerts** if both conditions are met simultaneously (e.g., a score
that's both already critical *and* jumped sharply) — each represents a distinct
reason to escalate, so both are surfaced rather than merged into one.

**Graceful handling of a property's first-ever assessment:** `previous_risk=None`
simply skips the increase check (nothing to compare against) rather than raising an
error — a property can still trigger on the absolute threshold alone.

**Output shape** matches the `alerts` table schema from Task 3 exactly
(`property_id`, `risk_type`, `risk_score`, `threshold_exceeded`, `alert_level`,
`message`, `triggered_at`), so storing these (Task 21+) requires no translation.

---

## A Real Discrepancy Found Between the Original Spec and the Finalized Config

The original task-breakdown.md verify script included this illustrative example:
```python
current_risk={'wildfire': 50, 'flood': 60}, previous_risk={'wildfire': 15, 'flood': 60}
# comment: "Increased 35 points" — asserted this would trigger an alert
```

Running it against the actual implementation returned **0 alerts**. Investigation
confirmed why: `wildfire_increase_threshold` was set to **40** in Task 5 (matching
`docs/implementation-plan.md`'s documented default), and this example's 35-point jump
simply doesn't cross a 40-point threshold. The illustrative example in the early
planning doc was written before the exact threshold value was finalized, and the
inconsistency was never caught until actually running the code against it.

**Resolution:** rather than silently lower the threshold to make the old example
pass (a real design value nobody asked to change) or silently patch the doc without
comment, both were corrected together:
- `docs/task-breakdown.md`'s example changed to a 45-point jump (15→60), which
  genuinely crosses the 40-point threshold, with a comment explaining the correction
- A new pytest test, `test_35_point_increase_does_not_cross_40_point_threshold`,
  locks in the *original* 35-point scenario as a documented, correct **no-alert**
  case — so the discrepancy is preserved as a permanent regression test, not just
  quietly fixed and forgotten

This is the same category of finding as Task 12's stale-gauge-data bug and Task
15/17's scoring edge cases: a concrete number, actually run, surfaced a real
inconsistency that abstract review would likely have missed.

---

## Verification Results

### Manual Demo (Corrected Examples)

```bash
python -m src.alerts.alert_engine
```
```
Wildfire threshold: 70 (increase: 40)
Flood threshold:    65 (increase: 30)

Property 1 (Absolute wildfire threshold crossed): 1 alert(s)
  [CRITICAL] Wildfire risk score 75 exceeds the critical threshold of 70.

Property 2 (35-point wildfire increase): 0 alert(s)

Property 3 (No thresholds crossed): 0 alert(s)

Property 4 (First-ever assessment, no previous): 2 alert(s)
  [CRITICAL] Wildfire risk score 80 exceeds the critical threshold of 70.
  [CRITICAL] Flood risk score 70 exceeds the critical threshold of 65.
```

Both corrected spec examples re-verified directly:
```
Test 1 - Alerts generated: 1
Test 2 - Alerts generated: 1 (45-point jump, corrected from the original 35-point example)
[PASS] Both corrected spec examples verified
```

### Pytest Suite

Created `tests/test_alert_engine_pytest.py` with **14 tests** across five classes:

**TestAbsoluteThreshold (4)** — wildfire above threshold triggers critical; exactly
at threshold does *not* trigger (strict `>`, matching the pattern used everywhere
else in this codebase, e.g. `RiskAggregator.classify_risk_level`); flood above
threshold triggers critical; both hazards crossing simultaneously produce two
distinct alerts

**TestIncreaseThreshold (4)** — the corrected 45-point jump triggers a warning;
**the original 35-point example is locked in as a documented no-alert case**; exactly
at the increase threshold does not trigger; one point above does

**TestNoAlertScenarios (3)** — nothing crossed → empty list; no previous risk still
checks the absolute threshold correctly; no previous risk + no absolute breach →
empty list (no crash)

**TestBothTriggersOnSameHazard (1)** — a score that's both already critical and
jumped sharply produces two distinct alerts for the same hazard type, not one merged
alert

**TestAlertShape (2)** — every alert has all expected fields; `property_id` in the
output matches the input

```
tests/test_alert_engine_pytest.py .............. 14 passed
```

**Full project test suite (Tasks 4-20 combined): 257 passed in 3.33s** ✓

---

## Files Created/Modified

| File | Purpose |
|------|---------|
| `src/alerts/alert_engine.py` | `AlertEngine` class (150 lines) |
| `src/alerts/__init__.py` | Package export |
| `docs/task-breakdown.md` | Task 20's verify example corrected (35→45-point jump) with explanation |
| `tests/test_alert_engine_pytest.py` | Pytest suite (14 tests) |

---

## Following Reference Principles

**Actionable Alerts Over Noise** ✓ — two independent, clearly-reasoned trigger
conditions (not a single vague "risk went up" signal) means each alert's `message`
can state exactly why it fired — absolute severity, sudden change, or both.

**Data Quality as a First-Class Concern** ✓ — the 35-vs-40-point discrepancy is
exactly the kind of "looks right until you actually run the numbers" issue this
principle is meant to catch — found here, documented, and turned into a permanent
regression test rather than silently smoothed over.

**Transparency and Explainability** ✓ — every alert's `message` field is a
human-readable sentence stating the specific score, threshold, and (for increase
alerts) the before/after values — consistent with the same explainability standard
applied to `WildFireScorer`/`FloodScorer` since Task 15.

---

## Usage Going Forward

```python
from src.alerts import AlertEngine
from src.database import RiskDAO

risk_dao = RiskDAO()
history = risk_dao.get_assessment_history(property_id, days=1)
current = history[0] if history else None
previous = history[1] if len(history) > 1 else None

if current:
    current_scores = {"wildfire": current["wildfire_risk_score"], "flood": current["flood_risk_score"]}
    previous_scores = (
        {"wildfire": previous["wildfire_risk_score"], "flood": previous["flood_risk_score"]}
        if previous else None
    )
    alerts = AlertEngine().evaluate_property(property_id, current_scores, previous_scores)
```

---

## Next Task

**Task 21: Create Alert Notification System**
- Build `src/alerts/notification.py` — a `Notifier` class
- Formats `AlertEngine`'s output for console/file output (structured logging via
  Task 6's framework), with the door open for email/SMS channels later
- This is where alerts actually get surfaced to a human, not just computed

---

**Status:** Task 20 Complete ✓
**Phase 4 (Alerts & Monitoring) — 1 of 5 tasks complete.**
**Ready for:** Task 21 - Alert Notification System
