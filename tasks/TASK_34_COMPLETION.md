# Task 34: Create Main Application Entry Point - COMPLETED ✓

**Completed:** 2026-08-03
**Status:** `src/main.py` created — the final task of the 35-task implementation
plan. Every component built across Phases 1-6 now runs behind one CLI
entrypoint, closing the exact gap the Operations Guide (Task 32) flagged
explicitly: *"this project does not currently ship a dedicated main.py/service
wrapper."*

---

## What Was Completed

### `src/main.py` — `main()` with three modes

```bash
python src/main.py --mode test              # one monitoring cycle, then exit
python src/main.py --mode report             # generate + print a portfolio report
python src/main.py --mode run                # start the continuous scheduler (Ctrl+C to stop)
python src/main.py --mode run --duration 30  # run for 30 minutes, then stop automatically
python src/main.py --mode run --interval 1   # override the configured cycle interval (minutes)
```

- **`--mode test`** (default) — `Monitor().run_monitoring_cycle()`, prints
  the summary dict
- **`--mode report`** — `PortfolioReporter().generate_summary_report()`,
  prints the report (and writes `reports/portfolio_YYYY-MM-DD.txt`, per
  Task 27's existing behavior)
- **`--mode run`** — starts `SchedulerManager`, blocks in a 1-second poll
  loop until: a `--duration` limit (minutes) elapses, or `Ctrl+C`/`SIGTERM`
  is received. Either path calls `scheduler.stop()` for a graceful
  shutdown (waits for any in-progress cycle to finish) and prints final
  `cycles_run`/`cycles_failed` counts.
- **`--interval`** overrides the configured
  `alerts.alert_check_interval_minutes` for that run only, rather than
  requiring a config file edit just to try a different cadence - the
  standard CLI-args-override-config pattern.

Every mode calls `setup_logging()` and `initialize_database()` first
(both idempotent - safe on every invocation, per Tasks 3/6).

**A real, immediate bug caught by actually running the verification
commands** (not just writing the code): `python src/main.py --mode test`
initially failed with `ModuleNotFoundError: No module named 'src'`. Running
a script directly (`python src/main.py`) doesn't put the project root on
`sys.path` the way `python -m src.main` would. Fixed by inserting the
project root into `sys.path` at the top of `main.py`, before the `src`
imports - now both invocation styles work, matching the task spec's literal
`python src/main.py --mode test` verification command.

---

## Verification Results

All three of the task spec's own verification commands were actually run
against the real system, not just inspected:

### `--help`
```
usage: main.py [-h] [--mode {run,test,report}] [--duration DURATION] [--interval INTERVAL]
...
--mode {run,test,report}   run: start the continuous scheduler...; test: run a single
                            monitoring cycle...; report: generate and print...
```
Lists all three modes and both options, as required.

### `--mode report`
Ran successfully against the real (clean) database - printed a full
portfolio report (0/100 assessed, no hotspots, no active alerts - correct
for a clean DB) and confirmed `reports/portfolio_2026-08-03.txt` was written.

### `--mode test`
Ran against the real system - confirmed real ingestion actually executed
(1074 real hazard_data rows stored across live NASA FIRMS/OpenWeatherMap/USGS
calls, including USGS correctly filtering two stale gauge readings per
Task 12's staleness logic) before a 200-second harness timeout intercepted
it mid-cycle - expected, given Task 33's measured ~162s+ real-world
ingestion time for this synthetic, 82-cell-producing portfolio. This
confirmed the wiring is correct without needing the full multi-minute cycle
to run to completion for verification purposes. A second, bounded run with
ingestion mocked out completed the *entire* cycle (ingest -> score -> alert
-> store) in 0.9s and printed the exact documented summary shape.

### `--mode run`
A bounded run (`--interval 0.03 --duration 0.1`, fake `Monitor`) confirmed:
scheduler starts, runs multiple cycles on the overridden interval, stops
automatically once the duration limit is reached, and reports final
cycle counts - all without needing to manually send Ctrl+C for this
automated check. A separate manual Ctrl+C path is also wired via
`signal.signal(SIGINT, ...)` and a `KeyboardInterrupt` fallback in the poll
loop.

**Real database cleaned up after both live runs** - `hazard_data`,
`risk_assessments`, `alerts`, `alert_history` back to 0 rows; `properties`
unchanged at 100; the generated report file removed.

### Pytest Suite

Created `tests/test_main_pytest.py` — **17 tests**, using fake
`Monitor`/`SchedulerManager`/`PortfolioReporter` stand-ins (monkeypatched
directly into `src.main`'s namespace, since it imports the classes rather
than the modules) so these tests are fast and don't depend on live APIs or
real scheduler timing - `main.py`'s job is CLI wiring, and each component
it orchestrates already has its own dedicated suite (Tasks 23-27).

**`TestParseArgs` (5)** — defaults to `test` mode; `run`/`report` accepted;
an invalid mode raises `SystemExit` (argparse's own validation); `--duration`/
`--interval` parsed as floats

**`TestTestMode` (2)** — returns the real `Monitor` summary dict unmodified;
prints every summary field

**`TestReportMode` (2)** — returns the report text unmodified; prints it

**`TestRunMode` (4)** — starts and stops the scheduler; `--interval`
override is applied to the scheduler instance; omitting `--interval`
leaves the scheduler's own default untouched; a `--duration` limit causes
`run_mode()` to return promptly rather than hang

**`TestMainDispatch` (4)** — `main()` dispatches to the correct mode
function based on parsed args (default, `report`, `run` with args
threaded through correctly); `setup_logging()`/`initialize_database()` are
always called regardless of mode

```
tests/test_main_pytest.py ................. 17 passed in 4.42s
```

**Full project test suite (Tasks 4-34 combined): 559 passed in 53.24s** ✓
(542 prior + 17 new).

---

## Files Created/Modified

| File | Purpose |
|------|---------|
| `src/main.py` | `main()` entrypoint (new) |
| `tests/test_main_pytest.py` | New pytest suite (17 tests) |

---

## Following Reference Principles

**Reliability Over Cleverness** ✓ — graceful shutdown (`scheduler.stop()`
on both signal and `KeyboardInterrupt` paths) means an operator can always
stop the system cleanly, without losing an in-progress cycle's work or
needing to kill the process forcefully.

**Continuous Monitoring, Not Point-in-Time** ✓ — `--mode run` is the first
place the project's actual production posture (a long-running,
self-scheduling process) is directly invokable from the command line,
rather than only assembled by hand in a Python REPL or test.

**Data Quality as a First-Class Concern**, applied to verification itself
✓ — actually running every one of the task spec's literal verification
commands against the real system (catching the `sys.path` bug immediately)
rather than trusting the code by inspection, consistent with every prior
task's practice in this project.

---

## Usage Going Forward

```bash
# Quick check that everything's wired up
python src/main.py --mode test

# See current portfolio status
python src/main.py --mode report

# Run continuously (e.g. inside a systemd service or container entrypoint)
python src/main.py --mode run
```

---

## Project Status

**All 35 tasks across 6 phases are now complete:**
- Phase 1: Foundation Setup (6 tasks)
- Phase 2: Data Ingestion (8 tasks)
- Phase 3: Risk Scoring (5 tasks)
- Phase 4: Alerts & Monitoring (6 tasks)
- Phase 5: Portfolio Aggregation (3 tasks)
- Phase 6: Testing & Documentation (7 tasks)

**559 passing tests**, 98%+ coverage on the modules with dedicated
coverage passes (Tasks 28-29), full API reference (Task 31), operations
guide (Task 32), measured performance characteristics (Task 33), and now
one CLI entrypoint tying the entire continuous monitoring system together.

---

**Status:** Task 34 Complete ✓
**Phase 6 (Testing & Documentation) — 7 of 7 tasks complete. Phase 6 done.**
**Project Status: All 35 tasks complete.**
