# Task 27: Create Portfolio Reporter (+ Portfolio-Level Alerting) - COMPLETED ✓

**Completed:** 2026-08-03
**Status:** `PortfolioReporter` built and verified, and — per the design discussed
and approved before implementation — the deferred portfolio-level accumulation
alert (">10% of properties in high/critical") is now fully wired into the live
monitoring loop. Phase 5 (Portfolio Aggregation) complete.

---

## What Was Completed

### Design Decision, Recorded Before Implementation

Per the established "docs before implementation" practice, the portfolio-alert
design was discussed and written up in
[docs/alert-lifecycle-design.md](../docs/alert-lifecycle-design.md#portfolio-level-alerts-task-27-extension)
before any code changed. Key decisions, all made explicitly with the user:

1. **One alerting system, not two.** A portfolio-level alert reuses the exact
   same `AlertDAO`/`alerts` table and lifecycle state machine (active ->
   acknowledged/stale -> resolved, hysteresis, re-notification cooldown) as
   property-level alerts (Task 21b) - not a parallel system. It's keyed on
   `property_id=NULL, risk_type='portfolio_high_risk_pct'` instead of a real
   property.
2. **Who closes it?** Nobody manually - `Monitor` (Task 23) re-evaluates the
   portfolio percentage every cycle, exactly like it already does for
   property alerts. The alert resolves itself automatically once the
   percentage drops meaningfully below the threshold.
3. **`property_id` must become nullable** - a real, non-additive schema
   migration (not Task 21b's simple `ALTER TABLE ADD COLUMN`), since SQLite
   can't drop a `NOT NULL` constraint directly. Considered and rejected a
   sentinel value (`property_id=0`) instead, since that would only "work"
   because this database never enables `PRAGMA foreign_keys` - `NULL` is the
   honest representation.

### Schema Migration: `alerts.property_id` Nullable

`src/database/db.py` and `data/schema.sql` — `property_id INTEGER NOT NULL`
-> `property_id INTEGER`.

`src/database/alert_dao.py` — `AlertDAO._ensure_property_id_nullable()`, a
new idempotent migration step (checked via `PRAGMA table_info(alerts)`'s
`notnull` flag) that rebuilds the table when needed:
`CREATE alerts_new (nullable schema) -> INSERT ... SELECT -> verify row
count matches -> DROP alerts -> RENAME alerts_new`. Aborts (drops
`alerts_new`, raises) if the row count doesn't match after the copy, rather
than ever silently losing data. A no-op for any database already on the
current schema.

**Verified live** against a hand-built "old schema" database (property_id
`NOT NULL`, missing the Task 21b lifecycle columns, 2 pre-existing rows):
running `AlertDAO()` migrated it correctly in one pass, preserved both rows,
and a second construction confirmed the migration is a true no-op.

**Null-safe comparisons.** SQL's `column = ?` never matches when the bound
parameter is `NULL` (`NULL = NULL` is `NULL`, not `TRUE`). Every
`property_id = ?` comparison in `AlertDAO` (`save_new_alerts()`'s dedup
lookup, `evaluate_lifecycle()`'s lookup, `get_alerts_for_property()`) is now
`property_id IS ?` - SQLite's null-safe equality, behaves identically to `=`
for real property IDs and correctly matches portfolio alerts.

### `AlertEngine.evaluate_portfolio()`

```python
def evaluate_portfolio(self, high_critical_percent: float) -> Optional[Dict]
```

Same shape as `evaluate_property()`'s output, but only one check (no
"sudden increase" variant - a portfolio accumulation breach is inherently
the more severe signal) and always `alert_level='critical'`.

### `Monitor` Wiring (Task 23 extended)

After the existing per-property loop, one new step per cycle:
`_process_portfolio_alert()` — computes `high + critical` percentage via
`PortfolioAggregator`, evaluates/persists via `AlertEngine`/`AlertDAO`, and
re-evaluates lifecycle every cycle (resolution/staleness) regardless of
whether a new alert fired. `_send_due_notifications()` was generalized to
accept `property_id=None` so the exact same notification-cooldown logic
serves both scopes without duplicated code.

### `src/portfolio/reporter.py` — `PortfolioReporter` class

```python
class PortfolioReporter:
    def generate_summary_report(self, write_to_file: bool = True) -> str
```

Combines `PortfolioAggregator` (Task 25), `HotspotDetector` (Task 26), and
`AlertDAO.get_active_alerts()` (Task 21b/27) into one text report: header,
metrics (risk-level distribution, score stats, geographic breakdown),
hotspots, and an alerts section that lists portfolio-level and
property-level alerts separately. Writes to `reports/portfolio_YYYY-MM-DD.txt`
by default (same-day re-runs overwrite, per spec). Built as a list of lines
(`_build_lines()`) rather than one f-string so a future PDF/HTML renderer can
reuse the data-gathering without re-deriving structure.

**New config value:** `alerts.portfolio_resolution_hysteresis_percent: 2` -
deliberately smaller and separate from property-level `resolution_hysteresis`
(10 points), since `10 - 10 = 0%` would make that value degenerate for a
percentage-based condition.

---

## Verification Results

### Live Demo (Real Database, Full Chain)

Reused the real 3-property cluster found in Task 26 (properties 6, 17, 18,
within 50km of each other) with assessments (80, 75, 90) plus 3 unrelated
low-risk properties, run through the real `Monitor.run_monitoring_cycle()`
(ingestion/scoring stubbed since the assessments were already synthetic):

```
[1] Property 6 (wildfire): Wildfire risk score 80.0 exceeds the critical threshold of 70.
[2] Property 17 (wildfire): Wildfire risk score 75.0 exceeds the critical threshold of 70.
[3] Property 18 (wildfire): Wildfire risk score 90.0 exceeds the critical threshold of 70.
[4] Property None (portfolio_high_risk_pct): 50.0% of assessed properties are in high/critical risk, exceeding the 10% portfolio accumulation threshold.

{'new_alerts': 4, 'notifications_sent': 4, 'errors': []}
```

3 property alerts + 1 portfolio alert, all persisted and notified in a
single real cycle. Then generated the report:

```
Risk level distribution:
  Low           3  ( 50.0%)
  High          2  ( 33.3%)
  Critical      1  ( 16.7%)
...
GEOGRAPHIC HOTSPOTS
  (32.5190, -118.0304): 3 properties, avg risk 81.7
...
ACTIVE ALERTS
Portfolio-level:
  [CRITICAL] 50.0% of assessed properties are in high/critical risk, exceeding the 10% portfolio accumulation threshold.
Property-level (3 active):
  3 critical, 0 warning
  ...
```

Every number cross-checked correct; `reports/portfolio_2026-08-03.txt` was
written and matched the printed output exactly. Both the report file and
all affected tables (`hazard_data`, `risk_assessments`, `alerts`,
`alert_history`) cleaned back to baseline afterward; `properties` unchanged
at 100.

### Pytest Suite

**Migration correctness** (`tests/test_alert_dao_pytest.py`, unchanged
count) plus manual verification against a real pre-Task-27 "old schema" DB
(above) - all 30 tests in that suite still pass unmodified, confirming the
`IS`-based comparison changes are fully backward-compatible with real
property IDs.

**`tests/test_alert_engine_pytest.py`** - 5 new tests in
`TestEvaluatePortfolio`: above/at/below threshold behavior (strict `>`,
matching the pattern used elsewhere in this codebase), message content, and
result shape.

**`tests/test_monitor_pytest.py`** - 4 existing single-property tests needed
a `pad_with_low_risk_properties()` helper added, since a lone high-risk test
property is trivially 100% of the assessed portfolio and now also (correctly)
triggers the new portfolio alert - not a bug, but it meant those tests needed
enough portfolio padding to stay isolated to what they were testing. New
`TestPortfolioAlertIntegration` (4 tests): alert created when percentage
exceeds threshold; no alert when padded below threshold; alert resolves when
percentage drops back down; notification is sent for a portfolio alert.

**`tests/test_portfolio_reporter_pytest.py`** (new, 14 tests):
**TestEmptyPortfolio (2)** - generates without crashing on a fully empty
portfolio; zero-assessed state shown explicitly, not hidden. **TestMetricsSection
(3)** - risk distribution, geographic distribution both render correctly;
geography section omitted entirely when no property has a state set (not
shown as an empty section). **TestHotspotsSection (2)** - a real hotspot is
listed with correct stats; "no hotspots" message shown when none exist.
**TestAlertsSection (4)** - property alerts listed with counts; portfolio
alerts shown in their own subsection; both scopes shown together correctly;
a resolved alert is excluded. **TestFileOutput (3)** - file written when
requested and matches the returned string exactly; no file written when
`write_to_file=False`; a second same-day report overwrites rather than
duplicating.

```
tests/test_alert_engine_pytest.py ................... 19 passed
tests/test_monitor_pytest.py .................... 18 passed
tests/test_portfolio_reporter_pytest.py .............. 14 passed
```

**Full project test suite (Tasks 4-27 combined): 392 passed in 44.10s** ✓
(369 prior + 5 + 4 + 14 = 23 new).

---

## Files Created/Modified

| File | Purpose |
|------|---------|
| `docs/alert-lifecycle-design.md` | New "Portfolio-Level Alerts" section, written before implementation |
| `docs/task-breakdown.md` | Task 27 spec updated to describe the alerting scope |
| `src/database/db.py`, `data/schema.sql` | `alerts.property_id` now nullable |
| `src/database/alert_dao.py` | Table-rebuild migration; `property_id IS ?` null-safe comparisons; portfolio threshold/hysteresis config |
| `src/alerts/alert_engine.py` | New `evaluate_portfolio()` method |
| `src/continuous_monitoring/monitor.py` | New `_process_portfolio_alert()` step per cycle; `_send_due_notifications()` generalized |
| `src/portfolio/reporter.py` | `PortfolioReporter` class (new) |
| `src/portfolio/__init__.py` | Now exports `PortfolioReporter` |
| `config/settings.json` | New `alerts.portfolio_resolution_hysteresis_percent: 2` |
| `tests/test_alert_engine_pytest.py` | 5 new tests |
| `tests/test_monitor_pytest.py` | 4 existing tests updated + 4 new tests |
| `tests/test_portfolio_reporter_pytest.py` | New pytest suite (14 tests) |

---

## Following Reference Principles

**Continuous Monitoring, Not Point-in-Time** ✓ — the portfolio alert closes
the loop the project's problem statement specifically called out
("catastrophic losses due to poor accumulation tracking") - it's now a live,
self-managing signal, not a report a human has to remember to check.

**Data Quality as a First-Class Concern** ✓ — the migration verifies row
counts before committing and aborts (not silently proceeds) on a mismatch;
`NULL` was chosen over a sentinel specifically to keep the data honest.

**Reliability Over Cleverness** ✓ — reusing the existing, already-tested
lifecycle state machine for portfolio alerts (rather than building a second,
parallel one) means the resolution/staleness/cooldown logic only has to be
correct in one place.

**Explainability** ✓ — the report's alerts section explicitly separates
portfolio-level from property-level, so a reader immediately understands
*which kind* of risk signal they're looking at.

---

## Usage Going Forward

```python
from src.portfolio import PortfolioReporter

report = PortfolioReporter().generate_summary_report()  # also writes reports/portfolio_YYYY-MM-DD.txt
print(report)
```

The portfolio alert requires no separate invocation - it's automatically
evaluated every cycle by `Monitor.run_monitoring_cycle()` (Task 23/24),
alongside every property's own alerts.

---

## Next Task

**Phase 6: Testing & Documentation begins.**

**Task 28: Write Unit Tests for Utilities**
- `tests/test_utils.py` (create) - dedicated coverage for `calculate_distance`,
  coordinate validation, timestamp functions
- ≥80% coverage of `src/utils/`
- Note: many utility functions already have indirect test coverage through
  other suites (e.g. `calculate_distance` via hotspot/wildfire tests) - this
  task is about direct, focused unit tests for the utilities themselves

---

**Status:** Task 27 Complete ✓
**Phase 5 (Portfolio Aggregation) — 3 of 3 tasks complete. Phase 5 done.**
**Ready for:** Task 28 - Unit Tests for Utilities (Phase 6 begins)
