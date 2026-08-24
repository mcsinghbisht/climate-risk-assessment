# Task 32: Create Deployment & Ops Guide - COMPLETED ✓

**Completed:** 2026-08-03
**Status:** `docs/operations-guide.md` created — an operator-facing companion
to Task 31's developer-facing API reference. Second documentation-only
task in Phase 6 (no source code changed).

---

## What Was Completed

### `docs/operations-guide.md` (new)

Six sections, matching the task spec exactly:

1. **Installation & Setup** — a real, verified 5-step sequence: install
   dependencies, register the two required free API keys (NASA FIRMS,
   OpenWeatherMap - USGS needs none), copy `.env.example` to `.env`,
   initialize the database (`python -m src.database.db`), generate and
   load the sample 100-property portfolio, and a verification check.
2. **Configuration Walkthrough** — a guided tour of every section of
   `config/settings.json` (`risk_scoring`, `alerts`, `data_sources`,
   `ingestion`, `portfolio`, `database`) explaining what each value
   actually controls, cross-referenced to the design docs that explain *why*.
3. **Running the Monitoring Loop** — one-off cycle
   (`python -m src.continuous_monitoring.monitor`) vs. continuous scheduled
   operation via `SchedulerManager`, plus on-demand portfolio reports.
4. **Monitoring Health** — the three log files and what each contains, what
   a healthy cycle's log output looks like versus real warning signs.
5. **Troubleshooting** — real issues this project actually hit during
   development (not hypothetical ones), each with cause and fix.
6. **Data Backup Procedures** — an honest account of what's actually
   implemented today (manual `cp`) versus what's configured but not yet
   built (see below).

### A Real Gap Found and Documented Honestly

While writing the configuration section, checked whether
`database.backup_enabled`/`backup_interval_hours` (present in
`config/settings.json` since early in the project) are actually wired to
any code:

```bash
grep -rn "backup_enabled\|backup_interval" src/
# (no output - not referenced anywhere)
```

Confirmed these are a **reserved placeholder, not a live feature** - no
automated backup job exists. Rather than describing a feature that doesn't
exist (or silently omitting the config keys and letting a future reader
assume they work), the guide states this explicitly and gives the real,
current manual backup procedure (copy the SQLite file) instead. This
mirrors the project's established practice of flagging documented "MVP
simplifications" openly (e.g. `RiskScoringEngine`'s full-table hazard_data
fetch, `HotspotDetector`'s O(n²) comparison) rather than letting
docs/config imply more than the code delivers.

### Verified, Not Just Written

Every command in the guide was actually run before being included:

```bash
python -m src.database.db
# [OK] Tables created: 7, [OK] properties: 100 records - SUCCESS: Database is ready!
# Confirmed idempotent - re-running against the already-initialized real
# database made no destructive changes and the 100 real properties survived.

python -c "from src.database import PropertyDAO; print(f'{PropertyDAO().count_properties()} properties loaded')"
# 100 properties loaded - exact match to the guide's documented expected output
```

---

## Verification Results

Both verified commands produced output matching the guide exactly. Full
project test suite re-run after writing the guide to confirm the
idempotent database re-initialization command didn't disturb anything:

**Full project test suite (Tasks 4-32 combined): 538 passed in 47.30s** ✓
(unchanged from Task 31 - no source code was modified this task, only
documentation; the one command run against the real database was
confirmed idempotent).

---

## Files Created/Modified

| File | Purpose |
|------|---------|
| `docs/operations-guide.md` | New — installation, configuration, running, monitoring, troubleshooting, and backup guidance |

---

## Following Reference Principles

**Data Quality as a First-Class Concern**, applied to documentation ✓ —
checked `backup_enabled`/`backup_interval_hours` against actual code before
writing about it, rather than assuming a configured value implies a
working feature. Same discipline the project applies to hazard data itself.

**Reliability Over Cleverness** ✓ — the troubleshooting section documents
*real* incidents from this project's own history (the API key exposure,
the stale-gauge discovery, the `days=0` bug) rather than generic, made-up
troubleshooting entries - a future operator hitting one of these will find
it described exactly as it actually happened.

---

## Next Task

**Task 33: Performance Testing**
- `tests/test_performance.py` (create) - `test_scoring_all_100_properties`
  (<2 min), `test_ingestion_cycle` (<1 min), confirming the system meets
  its "100 properties in <5 minutes per cycle" target

---

**Status:** Task 32 Complete ✓
**Phase 6 (Testing & Documentation) — 5 of 7 tasks complete.**
**Ready for:** Task 33 - Performance Testing
