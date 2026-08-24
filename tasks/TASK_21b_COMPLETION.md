# Task 21b: Alert Persistence & Lifecycle Management - COMPLETED ✓

**Completed:** 2026-07-24
**Status:** `AlertDAO` built, tested, and verified — including a live migration of the real, existing database.

---

## Why This Task Exists

While showing you what an alert looks like in practice, we identified a real gap:
`AlertEngine` (Task 20) produces alerts in memory, and `Notifier` (Task 21) logs them
to console/file — but nothing was ever persisted to the `alerts` table (built back
in Task 3, unused until now). This meant there was no way to answer "what alerts are
currently active," no protection against re-notifying the same ongoing condition
every 5-minute cycle, and no way to detect when a risk had genuinely resolved versus
when an alert was simply based on stale data. Full design and rationale documented in
[docs/alert-lifecycle-design.md](../docs/alert-lifecycle-design.md), agreed before
implementation.

---

## What Was Completed

### Schema Extension: `alerts` Table Gets a Lifecycle

Three new columns, added additively (no breaking change):

```sql
status TEXT CHECK (status IN ('active', 'acknowledged', 'stale', 'resolved')) DEFAULT 'active'
resolved_at TIMESTAMP
last_notified_at TIMESTAMP
```

Updated in two places to stay consistent: `src/database/db.py`'s `get_schema()`
(governs fresh databases) and `data/schema.sql` (the reference copy).

### `src/database/alert_dao.py` — `AlertDAO` class

```python
class AlertDAO:
    def save_new_alerts(alerts: List[Dict]) -> List[int]
    def evaluate_lifecycle(property_id, risk_type, current_score, latest_assessment_timestamp) -> Optional[Dict]
    def should_notify(alert_id) -> bool
    def mark_notified(alert_id) -> None
    def get_active_alerts() -> List[Dict]
    def get_alerts_for_property(property_id, include_resolved=False) -> List[Dict]
    def acknowledge_alert(alert_id) -> bool
```

**Deduplication** (`save_new_alerts`): re-evaluating the same ongoing condition
updates the existing `active`/`acknowledged` row's score and message instead of
inserting a duplicate. Deliberately keyed on `property_id + risk_type + alert_level`
(not just `property_id + risk_type`) — Task 20's `AlertEngine` can legitimately
produce two independent alerts for the same hazard (one critical/absolute, one
warning/increase), and these must remain separate lifecycle entities, not merged.

**Resolution with hysteresis** (`evaluate_lifecycle`): a score must drop below
`(absolute_threshold - resolution_hysteresis)` — not just barely under the original
trigger point — to count as resolved, preventing flapping. Resolution is evaluated
against the hazard type's absolute threshold from config (not the specific alert
row's own `threshold_exceeded` value), since an "increase" alert's
`threshold_exceeded` holds the delta threshold (e.g., 40 points), which isn't a
meaningful resolution boundary on its own — resolution is fundamentally about
whether the underlying danger for that hazard type has passed.

**Staleness**: if the property's most recent risk assessment is older than
`stale_after_hours`, the alert transitions to `stale` regardless of its last known
score — the system stops confidently claiming a condition is still active/resolved
when there's no fresh evidence either way. An acknowledged alert does **not**
silently revert to plain `active` just because it's still ongoing (verified
explicitly by a test) — acknowledgment is sticky until resolution.

**Re-notification cooldown** (`should_notify`/`mark_notified`): tracked via
`last_notified_at`, independent of when the row's score was last updated — this is
what lets an ongoing critical condition still update its stored score every cycle
without spamming a notification every cycle too.

**Migration safety net** (`_ensure_schema`): every `AlertDAO()` instantiation checks
`PRAGMA table_info(alerts)` and adds any missing lifecycle columns via `ALTER TABLE`
— idempotent, and specifically designed to upgrade a database created before this
task without requiring a separate manual migration step.

---

## Verification Results

### Live Migration of the Real, Pre-Existing Database

The real `data/climate_risk.db` still had the **old** `alerts` schema (from Task 3,
no lifecycle columns) going into this task. Confirmed before running anything:

```
(0, 'alert_id', ...) (1, 'property_id', ...) ... (9, 'created_at', ...)
# no status / resolved_at / last_notified_at
```

Running `AlertDAO()`'s demo against this real database triggered the migration
automatically:

```bash
python -m src.database.alert_dao
```
```
Persisted 1 new alert(s)
First save: 1 new alert(s) -> [1]
Second save (same condition): 0 new alert(s) (deduped, as designed)
Active alerts: 1
should_notify(1): True (never notified)
should_notify(1) after marking: False (cooldown active)
Alert 1 (property=1, wildfire) transitioned active -> resolved
After evaluate_lifecycle (score dropped to 50): status=resolved
```

Confirmed directly afterward: the real database's `alerts` table now has all three
new columns, and the demo alert shows the complete journey —
`risk_score=50.0, status='resolved', resolved_at` and `last_notified_at` both
populated correctly. Demo data cleared afterward (`DELETE FROM alerts`,
`DELETE FROM alert_history`), consistent with every prior live-data verification in
this project.

### Pytest Suite

Created `tests/test_alert_dao_pytest.py` with **28 tests** across seven classes:

**TestSchemaMigration (3)** — idempotent double-init doesn't error; lifecycle
columns exist after init; **a hand-built pre-Task-21b schema (no lifecycle columns
at all) is correctly migrated** — this test constructs the exact "before" state
independently of the real database, so the migration path is verified without
depending on the real DB's history

**TestSaveNewAlerts (5)** — new alert returns an ID; repeated save of the same
condition doesn't duplicate; **critical and warning alerts for the same hazard are
tracked independently** (the key design decision); a different property doesn't
dedupe against an unrelated one; an ongoing alert's score updates in place

**TestEvaluateLifecycle (8)** — no active alert returns `None`; score above the
resolution point stays active; score below it resolves; **the exact hysteresis
boundary does not resolve** (strict `<`, matching the pattern used everywhere else
in this codebase); staleness triggers correctly on old data and on missing data;
transitions are recorded in `alert_history`; **an acknowledged alert does not revert
to active while still ongoing**

**TestRenotificationCooldown (3)** — true before first notification; false
immediately after marking; true again once the cooldown window has elapsed

**TestGetActiveAlerts (3)** — empty when none exist; resolved alerts excluded; stale
alerts still included (they still need attention, just with lower confidence)

**TestGetAlertsForProperty (3)** — resolved excluded by default; included when
requested; only the requested property's alerts returned

**TestAcknowledgeAlert (3)** — sets status and timestamp correctly; returns `False`
for an unknown ID rather than erroring; records the transition in `alert_history`

```
tests/test_alert_dao_pytest.py ............................ 28 passed
```

**Full project test suite (Tasks 4-21b combined): 295 passed in 7.45s** ✓ — zero
bugs found this time; the design discussion before implementation clearly paid off.

---

## Files Created/Modified

| File | Change |
|------|--------|
| `src/database/alert_dao.py` | New — `AlertDAO` class (280 lines) |
| `src/database/db.py` | `alerts` schema extended with `status`/`resolved_at`/`last_notified_at` |
| `data/schema.sql` | Mirrored the same schema change |
| `src/database/__init__.py` | Exported `AlertDAO` |
| `config/settings.json` | Added `renotify_interval_minutes` (60), `resolution_hysteresis` (10), `stale_after_hours` (6) |
| `tests/test_alert_dao_pytest.py` | New — 28 tests |
| `docs/alert-lifecycle-design.md` | Written *before* implementation (per your request) |
| `docs/task-breakdown.md` | Task 21b inserted between Tasks 21 and 22 |
| `docs/implementation-plan.md` | Alert Lifecycle section added |
| `CLAUDE.md` | Task count updated (34 → 35) |

---

## Following Reference Principles

**Actionable Alerts Over Noise** ✓ — this task is the concrete mechanism that
prevents alert fatigue: deduplication and the re-notification cooldown mean a human
sees a new alert once, gets periodic reminders while it's genuinely unresolved, and
isn't flooded every 5 minutes.

**Data Quality as a First-Class Concern** ✓ — staleness detection means the system
never silently claims a condition is "still active" beyond what fresh data can
actually confirm — directly extending the same principle applied to USGS gauge data
in Task 12.

**Scalability From Day One** ✓ — the migration safety net means this schema change
applies safely to any existing deployment without a separate manual migration step,
and any future delivery channel only needs three read methods, never reimplementing
lifecycle logic.

---

## Usage Going Forward

```python
from src.alerts import AlertEngine
from src.database import AlertDAO, RiskDAO

alert_dao = AlertDAO()
risk_dao = RiskDAO()

# When a new assessment comes in:
alerts = AlertEngine().evaluate_property(property_id, current_scores, previous_scores)
new_ids = alert_dao.save_new_alerts(alerts)

# Re-evaluate an existing alert's lifecycle against fresh data:
alert_dao.evaluate_lifecycle(property_id, "wildfire", current_score, latest_assessment_timestamp)

# What should actually be sent right now?
for alert in alert_dao.get_active_alerts():
    if alert_dao.should_notify(alert["alert_id"]):
        # Notifier().send_alert(alert)
        alert_dao.mark_notified(alert["alert_id"])
```

---

## Next Task

**Task 22: Implement Change Detection (Score Comparison)**
- Build `src/continuous_monitoring/change_detector.py` — a `ChangeDetector` class
- A smaller, more general-purpose sibling to `AlertEngine`'s threshold-specific
  comparison — reports *what* changed between two assessments (score delta, which
  factors shifted), independent of whether it crosses an alert threshold
- First component in the `continuous_monitoring` module (previously empty)

---

**Status:** Task 21b Complete ✓
**Phase 4 (Alerts & Monitoring) — 3 of 6 tasks complete.**
**Ready for:** Task 22 - Change Detection
