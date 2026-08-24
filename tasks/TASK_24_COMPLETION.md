# Task 24: Set Up Scheduled Execution (APScheduler) - COMPLETED ✓

**Completed:** 2026-07-24
**Status:** `SchedulerManager` built, tested, and verified — `Monitor.run_monitoring_cycle()`
(Task 23) now runs automatically on a recurring interval instead of needing
to be invoked by hand.

---

## What Was Completed

### `src/continuous_monitoring/scheduler.py` — `SchedulerManager` class

```python
class SchedulerManager:
    def start(self) -> None
    def stop(self, wait: bool = True) -> None
    is_running: bool  # property
```

Wraps `Monitor.run_monitoring_cycle()` in an APScheduler `BackgroundScheduler`
interval job:

- **Interval is config-driven, no new key added** — reuses
  `config/settings.json`'s existing `alerts.alert_check_interval_minutes`
  (currently 5), the same value already used elsewhere for "how often do we
  re-check risk," rather than introducing a duplicate/separate scheduler
  interval setting.
- **Overlap protection** — the job is registered with `max_instances=1` and
  `coalesce=True`. If a cycle is still running when the next fire time
  arrives, APScheduler skips starting a second overlapping run; if the
  scheduler falls behind (e.g. one cycle ran long), any backlog of missed
  fire times collapses into a single catch-up run rather than queuing up a
  burst of cycles. This is what the task spec's "reschedules if one takes
  > 5 min" means in practice — verified live (see below).
- **Health-check logging** — every cycle logs success (`cycles_run` counter,
  properties scored / new alerts / errors from that cycle's summary) or
  failure (`cycles_failed` counter, exception message) via the existing
  `app.log` logger. An `EVENT_JOB_MISSED` listener additionally logs a
  warning whenever a fire time is skipped, so a human reviewing logs can see
  both "the cycle ran and here's what happened" and "the cycle didn't run
  when it was supposed to."
- **Failure isolation** — a cycle that raises is caught inside `_run_cycle()`
  and logged; the scheduler itself keeps running and fires the next
  scheduled cycle normally, rather than dying because one iteration failed.

---

## Verification Results

### Live Demos (Fast Intervals, Fake Monitors)

Following the same principle as prior tasks' bounded demos (avoid a real
5-minute wait / repeated real API calls for a routine verification), these
three demos used `interval_minutes` overridden to a few seconds and fake
`Monitor` stand-ins, since `Monitor`'s own correctness is already verified in
Task 23 - what's being proven here is the scheduler wiring around it.

**1. Recurring execution over ~11 seconds (3-second interval):**
```
Scheduler started - running a monitoring cycle every 0.05 minute(s)
Scheduled cycle #1 succeeded: 0 properties scored, 0 new alerts, 0 errors
Scheduled cycle #2 succeeded: 0 properties scored, 0 new alerts, 0 errors
Scheduled cycle #3 succeeded: 0 properties scored, 0 new alerts, 0 errors
Scheduler stopped
cycles_run: 3, fake calls: 3
```

**2. Overlap protection (4-second cycle, 3-second interval — cycle duration
deliberately longer than the interval):**
```
cycles_run(calls): 2, max_concurrent (should be 1): 1
```
Confirmed the scheduler never started a second cycle while the first was
still sleeping, even though the interval elapsed mid-cycle.

**3. Failure handling (every cycle raises):**
```
Scheduled cycle failed entirely: simulated failure
Scheduled cycle failed entirely: simulated failure
Scheduler stopped
cycles_run: 0, cycles_failed: 2
```
Confirmed repeated failures don't crash the scheduler or stop future cycles
from being attempted.

### Pytest Suite

Created `tests/test_scheduler_pytest.py` — **13 tests**, using fake
`Monitor` stand-ins (`CountingMonitor`, `SlowMonitor`, `FailingMonitor`,
`FlakyMonitor`) with a fast interval (~1.8s) so the whole suite still runs
in well under a minute despite exercising real wall-clock scheduling:

**TestStartStop (5)** — not running before `start()`; running after; not
running after `stop()`; calling `start()` twice is a safe no-op (doesn't
raise or double-register the job); calling `stop()` when not running is a
safe no-op

**TestRecurringExecution (4)** — interval defaults to the real
`alert_check_interval_minutes` config value (5) when not overridden; the
cycle actually fires multiple times over a period spanning several
intervals; `cycles_run` tracks the fake monitor's actual call count exactly;
`last_result` reflects the most recent cycle's real return value

**TestOverlapProtection (1)** — a cycle whose fake work takes longer than
the interval never runs concurrently with itself (`max_concurrent == 1`,
verified via a shared counter incremented/decremented around the "work")

**TestFailureIsolation (3)** — a cycle that always raises doesn't crash the
scheduler (still `is_running` afterward); failed cycles are counted
separately from successful ones (`cycles_failed` vs `cycles_run`); a cycle
that fails once and then starts succeeding is correctly reflected in both
counters

```
tests/test_scheduler_pytest.py ............. 13 passed in 35.33s
```

**Full project test suite (Tasks 4-24 combined): 343 passed in 41.65s** ✓
(330 prior + 13 new).

---

## Files Created/Modified

| File | Purpose |
|------|---------|
| `src/continuous_monitoring/scheduler.py` | `SchedulerManager` class (new) |
| `src/continuous_monitoring/__init__.py` | Now exports `SchedulerManager` alongside `ChangeDetector`/`Monitor` |
| `tests/test_scheduler_pytest.py` | New pytest suite (13 tests) |

`apscheduler>=3.10.0` was already listed in `requirements.txt` (added at
project setup, unused until now) — no dependency changes needed.

---

## Following Reference Principles

**Continuous Monitoring, Not Point-in-Time** ✓ — this is the task where the
project's core premise actually becomes true: the system now re-assesses
the whole portfolio on its own, on a schedule, without a human re-running a
script.

**Reliability Over Cleverness** ✓ — overlap protection and per-cycle
failure isolation are both about the same idea: a scheduler that silently
stacks up overlapping runs or dies on the first exception is worse than no
scheduler at all. `max_instances=1` + `coalesce=True` and a try/except
around each cycle keep the system self-healing rather than requiring a human
to notice and restart it.

**Explainability** ✓ — `cycles_run`/`cycles_failed`/`last_result` plus the
existing `app.log` entries mean anyone can answer "is the scheduler
healthy?" without needing to attach a debugger.

---

## Usage Going Forward

```python
from src.continuous_monitoring import SchedulerManager

scheduler = SchedulerManager()
scheduler.start()   # begins running a cycle every alert_check_interval_minutes
# ... application keeps running ...
scheduler.stop()    # graceful shutdown, waits for any in-progress cycle
```

---

## Next Task

**Task 25: Create Portfolio-Level Metrics Aggregator** (Phase 5 begins)
- `src/portfolio/aggregator.py` (create) — `PortfolioAggregator` class:
  `get_portfolio_metrics()` — risk-level distribution (count/percentage per
  bucket), geographic distribution (by state/county), average/median/min/max
  risk score, timestamp of latest assessment
- This is also where the previously-deferred portfolio-level alert
  (">10% of properties in high/critical") gets implemented, per the user's
  earlier note that it would be "handled separately" from Tasks 20/21b

---

**Status:** Task 24 Complete ✓
**Phase 4 (Alerts & Monitoring) — 6 of 6 tasks complete. Phase 4 done.**
**Ready for:** Task 25 - Portfolio-Level Metrics Aggregator (Phase 5 begins)
