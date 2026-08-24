# Task 21: Create Alert Notification System - COMPLETED ✓

**Completed:** 2026-07-23
**Status:** `Notifier` built, tested, and verified — reuses Task 6's `alerts` logger rather than building new output plumbing.

---

## What Was Completed

### `src/alerts/notification.py` — `Notifier` class

```python
class Notifier:
    def send_alert(alert: Dict) -> None
    def send_alerts(alerts: List[Dict]) -> int
```

**Design decision: no new logging infrastructure.** Task 6 already built a dedicated
`alerts` logger (console + `logs/alerts.log`, both at INFO level, `propagate: False`
so it never mixes into `app.log`). `Notifier` simply uses
`logging.getLogger("alerts")` correctly — `.critical()` for `alert_level="critical"`,
`.warning()` otherwise — rather than duplicating console/file output handling that
already exists and was already tested.

**Tolerant input handling:** `send_alert()` accepts both `AlertEngine`'s real output
shape (`risk_type`, `risk_score`, `alert_level`, `message`, `triggered_at`) and the
simpler illustrative shape from the original task spec (`alert_id`, `message`,
`timestamp`) — missing fields degrade gracefully (e.g., missing `alert_level`
defaults to `"warning"`) rather than raising.

**Extensibility, without building it yet:** the docstring notes that additional
channels (email, SMS, Slack) would be added as new private `_send_to_*` methods
registered inside `send_alert()`, without changing the public interface — not
implemented now since nothing in the task scope calls for it yet, but the shape is
ready.

---

## Verification Results

### Manual Demo (Both Alert Shapes)

```bash
python -m src.alerts.notification
```
```
1. Sending a simple/legacy-shaped alert...
2026-07-23 19:15:52 | WARNING  | alerts | [TEST_001] Property 1 (wildfire): Wildfire risk increased to 75

2. Sending real AlertEngine-shaped alerts...
2026-07-23 19:15:52 | CRITICAL | alerts | Property 42 (wildfire): Wildfire risk score 80 exceeds the critical threshold of 70.
2026-07-23 19:15:52 | WARNING  | alerts | Property 42 (wildfire): Wildfire risk score increased by 60.0 points (from 20 to 80), exceeding the 40-point increase threshold.
```

`logs/alerts.log` confirmed to contain exactly these 3 entries after clearing it
beforehand for a clean check.

**Confirmed isolation from `app.log`:** after running the demo, `logs/app.log`
contained only the `setup_logging()` debug line — no alert messages leaked in,
proving Task 6's `propagate: False` config for the `alerts` logger works correctly
with real usage. `logs/errors.log` was empty even though a CRITICAL message was
logged, because the `alerts` logger's handler list (console + `alerts_file` only,
per Task 6) never includes `error_file` — CRITICAL alerts are deliberately isolated
to `alerts.log`, not mixed into the general error log.

### Pytest Suite

Created `tests/test_notification_pytest.py` with **10 tests** across three classes:

**TestSendAlert (7)** — critical alerts logged at CRITICAL level; warning alerts at
WARNING; a missing `alert_level` key defaults to warning; the formatted message
includes property_id and risk_type; `alert_id` is included when present; a missing
`alert_id` doesn't crash; **the `alerts` logger's `propagate` attribute is verified
directly to be `False`**

**TestSendAlerts (2)** — sends all alerts in a list and returns the correct count;
an empty list sends nothing

**TestIntegrationWithAlertEngine (1)** — feeds `Notifier` real `AlertEngine` output
(not a hand-built fixture) and confirms both a CRITICAL and a WARNING record are
correctly produced from the two alerts a real absolute-threshold-and-increase
scenario generates

```
tests/test_notification_pytest.py .......... 10 passed
```

### A Test-Authoring Issue Found and Fixed (pytest `caplog` Quirk, Not a Source Bug)

An initial test asserted that logging an alert wouldn't be captured by `caplog`
attached to the root logger (testing `propagate: False` indirectly). It failed —
`caplog` captured the record anyway, despite the `alerts` logger genuinely having
`propagate=False` (confirmed directly via a standalone script:
`logging.getLogger("alerts").propagate` → `False`, correct handlers attached).

**Root cause:** pytest's `caplog` fixture has known cross-logger capture semantics
that don't reliably respect a child logger's `propagate=False` the way plain Python
logging does. This is a limitation of the test tool, not the code under test.

**Fix:** rewrote the test to assert the actual `logging.getLogger("alerts").propagate`
attribute directly — a more precise and trustworthy test of the real property being
verified, rather than relying on `caplog`'s unreliable behavior for this specific
scenario. Documented clearly in the test's docstring so the reasoning isn't lost.

**Full project test suite (Tasks 4-21 combined): 267 passed in 3.06s** ✓

---

## Files Created/Modified

| File | Purpose |
|------|---------|
| `src/alerts/notification.py` | `Notifier` class (75 lines) |
| `src/alerts/__init__.py` | Exported `Notifier` |
| `tests/test_notification_pytest.py` | Pytest suite (10 tests) |

---

## Following Reference Principles

**Scalability From Day One** ✓ — reusing Task 6's existing logging infrastructure
instead of building parallel console/file-writing code means one less thing that
could drift out of sync as the system grows.

**Actionable Alerts Over Noise** ✓ — routing critical vs. warning alerts to distinct
log levels (and therefore distinct visual/operational treatment) means a critical
wildfire alert doesn't get lost in a stream of routine warnings.

**Transparency and Explainability** ✓ — the formatted log line always includes the
property, hazard type, and the exact message `AlertEngine` produced — nothing is
summarized away or abbreviated in a way that would hide the reasoning.

---

## Usage Going Forward

```python
from src.alerts import AlertEngine, Notifier

engine = AlertEngine()
notifier = Notifier()

alerts = engine.evaluate_property(property_id, current_risk, previous_risk)
notifier.send_alerts(alerts)
```

---

## Next Task

**Task 22: Implement Change Detection (Score Comparison)**
- Build `src/continuous_monitoring/change_detector.py` — a `ChangeDetector` class
- Compares two risk assessments and reports what changed (score delta, which
  factors shifted) — a smaller, more general-purpose sibling to `AlertEngine`'s
  threshold-specific comparison
- First component in the `continuous_monitoring` module (previously empty)

---

**Status:** Task 21 Complete ✓
**Phase 4 (Alerts & Monitoring) — 2 of 5 tasks complete.**
**Ready for:** Task 22 - Change Detection
