# Task 23: Create Continuous Monitoring Loop - COMPLETED ✓

**Completed:** 2026-07-24
**Status:** `Monitor` built, tested, and verified — the first component to actually
wire together everything built in Tasks 14 through 22 in a single call.

---

## What Was Completed

### `src/continuous_monitoring/monitor.py` — `Monitor` class

```python
class Monitor:
    def run_monitoring_cycle(self) -> Dict
```

One cycle, in order:

1. **Ingestion** (Task 14) — `IngestionEngine.run_ingestion_cycle()`
2. **Scoring** (Task 19) — `RiskScoringEngine.score_all_properties()`
3. **Per property** — for every property in the portfolio:
   - Fetch the last day of assessment history (`RiskDAO.get_assessment_history`)
   - **Change detection** (Task 22) — `ChangeDetector.detect_changes()`, logged
     for observability (trend + delta) but not itself gating any action
   - **Alert evaluation** (Task 20) — `AlertEngine.evaluate_property()` against
     current vs. previous wildfire/flood scores
   - **Persistence** (Task 21b) — `AlertDAO.save_new_alerts()` for anything newly
     triggered
   - **Lifecycle re-evaluation** (Task 21b) — `AlertDAO.evaluate_lifecycle()` is
     called for *both* hazard types on *every* property, every cycle —
     independent of whether a new alert fired this cycle. This is what lets an
     alert transition to `resolved` or `stale` even in a cycle where nothing new
     is triggered.
   - **Notification** (Task 21) — for each of the property's active alerts,
     `AlertDAO.should_notify()` gates whether `Notifier.send_alert()` fires,
     followed by `AlertDAO.mark_notified()`

Returns:
```python
{
    "cycle_timestamp": "2026-07-24T13:21:05.027570+00:00",
    "hazard_records_ingested": 21,
    "properties_scored": 100,
    "new_alerts": 2,
    "notifications_sent": 2,
    "errors": [],
}
```

**Error isolation, at two levels** (matching the pattern already used in
`IngestionEngine` and `RiskScoringEngine`):
- The ingestion step and scoring step are each wrapped in their own
  try/except — if either fails entirely (e.g. the DB is locked, an API is
  down), the cycle logs it, records it in `errors`, and continues rather than
  crashing.
- Each property's alert-handling is wrapped individually — one property
  throwing (e.g. malformed data) doesn't stop the other 99 from being
  processed. Verified explicitly (see below).

---

## Bug Found and Fixed: `AlertDAO.evaluate_lifecycle()` (Task 21b)

Task 23 is the first place `evaluate_lifecycle()` gets called in a real
end-to-end loop rather than in isolation, and doing so surfaced a genuine
correctness bug in the existing Task 21b code.

**The bug:** `AlertEngine` can independently raise a `critical` alert
(absolute threshold) and a `warning` alert (sudden increase) for the *same*
`property_id + risk_type` — that's by design (Task 20). But
`evaluate_lifecycle()`'s query was:

```sql
SELECT * FROM alerts WHERE property_id=? AND risk_type=? AND status IN ('active','acknowledged')
ORDER BY alert_id DESC LIMIT 1
```

`LIMIT 1` only picked the most-recently-inserted row. Proven live: a wildfire
spike (20→85) correctly created both alerts (critical id 2, warning id 3).
A follow-up assessment with the score dropped to 10 (well past the
resolution point) only resolved alert id 3 — alert id 2 stayed `active`
forever, since it was no longer "the latest" row for that property+risk_type.

**The fix:** `evaluate_lifecycle()` now fetches *all* active/acknowledged
rows for `property_id + risk_type` (dropped `LIMIT 1`), applies the same
staleness/resolution logic to each independently, and returns a `List[Dict]`
instead of `Optional[Dict]`. Updated the 8 existing lifecycle tests in
`tests/test_alert_dao_pytest.py` to the new list-returning contract, and
added two new regression tests:

- `test_two_concurrent_alert_levels_both_resolve_independently`
- `test_two_concurrent_alert_levels_both_go_stale`

Re-verified live after the fix: both the critical and warning alert for the
same property+risk_type now resolve together. This is exactly the kind of
integration-only bug the reference principles' "Data Quality as a
First-Class Concern" is meant to catch early — a bug invisible to
unit-level tests of `AlertDAO` in isolation, only found once Task 23 chained
components the way production actually will.

---

## Verification Results

### Live Demo (Real Database, Bounded Ingestion)

Following the established pattern from Tasks 14/19, ingestion was
monkeypatched to only 2 grid cells (avoiding a ~300-call full-portfolio run):

```bash
python demo_task23.py   # IngestionEngine._get_portfolio_cells patched to cells[:2]
```

```
=== Monitoring Cycle Summary ===
cycle_timestamp: 2026-07-24T13:21:05.027570+00:00
hazard_records_ingested: 21
properties_scored: 100
new_alerts: 0
notifications_sent: 0
errors: []
```

All 100 real properties were scored end-to-end (ingestion → scoring →
change detection → alerting → notification) with zero errors. `new_alerts=0`
because real conditions that day didn't cross any threshold — expected, not
a failure.

### Live Demo (Synthetic Alert Scenario)

To prove the alerting/notification/lifecycle path itself (which the bounded
ingestion demo above didn't happen to exercise), inserted synthetic
assessments directly and ran `Monitor`'s per-property methods against the
real DB:

1. Baseline (wildfire=20) → spike (wildfire=85): **2 alerts created**
   (absolute threshold + 40+ point increase), **2 notifications sent**
2. Follow-up assessment (wildfire=10, well below the resolution point):
   **both alerts resolved** (post-fix; pre-fix only 1 of 2 resolved — see bug
   above)

All affected tables (`hazard_data`, `risk_assessments`, `alerts`,
`alert_history`) cleaned back to 0 rows afterward; `properties` unchanged at
100.

### Pytest Suite

Created `tests/test_monitor_pytest.py` — **14 tests**, using fakes for
`IngestionEngine`/`RiskScoringEngine`/`Notifier` (to avoid live API calls and
make notification counts assertable) but the **real** `ChangeDetector`,
`AlertEngine`, `AlertDAO`, `RiskDAO`, and `PropertyDAO` against a temporary
SQLite database:

**TestCycleSummaryShape (4)** — empty portfolio completes cleanly; result
has all expected keys; hazard record counts sum correctly across categories;
`properties_scored` reflects the scoring step's own summary

**TestErrorIsolation (4)** — an ingestion step raising an exception is
captured in `errors`, not propagated; same for a scoring step failure;
errors already inside the ingestion summary's own `errors` list are
surfaced into the cycle summary; **one property's alert-handling raising
does not stop the rest of the portfolio from being processed** — verified
by making `AlertEngine.evaluate_property` raise only for property 1 and
confirming property 2 still got its alert

**TestAlertingIntegration (6)** — a property crossing the absolute
threshold creates and notifies exactly one alert; a low-risk property
creates none; a second cycle within the re-notification cooldown does not
send a duplicate notification; an alert resolves (and stops notifying) once
the score drops past the resolution point in a later cycle; both the
absolute and increase alerts fire independently when a spike crosses both

```
tests/test_monitor_pytest.py .............. 14 passed in 1.08s
```

**Full project test suite (Tasks 4-23 combined): 330 passed in 7.71s** ✓
(316 prior + 14 new for `Monitor`, plus the 2 new `AlertDAO` regression tests
already counted in the 316 after the lifecycle-bug fix).

---

## Files Created/Modified

| File | Purpose |
|------|---------|
| `src/continuous_monitoring/monitor.py` | `Monitor` class (new) |
| `src/continuous_monitoring/__init__.py` | Now exports `Monitor` alongside `ChangeDetector` |
| `src/database/alert_dao.py` | **Bug fix**: `evaluate_lifecycle()` now evaluates all active/acknowledged rows per property+risk_type, not just the latest |
| `tests/test_alert_dao_pytest.py` | Updated 8 existing tests to the new list-returning contract; added 2 regression tests |
| `tests/test_monitor_pytest.py` | New pytest suite (14 tests) |

---

## Following Reference Principles

**Continuous Monitoring, Not Point-in-Time** ✓ — this is the first
component that actually behaves like the project's stated vision: one call
re-assesses the whole portfolio, compares against history, and manages
alert lifecycles automatically, rather than treating any of these as
one-off scripts.

**Data Quality as a First-Class Concern** ✓ — the lifecycle bug found here
existed silently since Task 21b; only real end-to-end composition (not
another isolated unit test) revealed it. Fixing root cause in `AlertDAO`
rather than working around it in `Monitor` keeps the fix correct for every
future caller, not just this one.

**Explainability** ✓ — every cycle's summary and every state transition is
logged with enough detail (`property_id`, `risk_type`, old→new status,
delta/trend) to reconstruct *why* an alert fired, changed, or resolved.

---

## Usage Going Forward

```python
from src.continuous_monitoring import Monitor

monitor = Monitor()
summary = monitor.run_monitoring_cycle()
print(f"{summary['properties_scored']} scored, {summary['new_alerts']} new alerts, "
      f"{summary['notifications_sent']} notifications sent")
```

---

## Next Task

**Task 24: Build Scheduler**
- Wrap `Monitor.run_monitoring_cycle()` in an APScheduler (or similar)
  recurring job, run every `alert_check_interval_minutes` (currently 5,
  `config/settings.json`)
- Needs: start/stop control, overlap protection (don't start a new cycle if
  the previous one is still running), and cycle-level logging/observability
  already provided by `Monitor`'s own summary + log lines

---

**Status:** Task 23 Complete ✓
**Phase 4 (Alerts & Monitoring) — 5 of 6 tasks complete.**
**Ready for:** Task 24 - Scheduler
