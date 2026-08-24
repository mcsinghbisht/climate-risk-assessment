# Task 30: Write Integration Tests (Scenario-Based) - COMPLETED ✓

**Completed:** 2026-08-03
**Status:** `tests/test_integration.py` and `tests/fixtures/mock_hazard_data.json`
created — the first task that deliberately exercises the *whole* system
together (real ingesters, real scorers, real aggregators) rather than one
component in isolation, with only the HTTP layer mocked.

---

## What Was Completed

### `tests/fixtures/mock_hazard_data.json` (new)

Sample API response bodies matching the real NASA FIRMS (CSV), OpenWeatherMap
(JSON), and USGS Water Services (JSON) formats exactly, so `DataNormalizer`
(Task 13) parses them identically to live data:

- `firms_csv_header` / `firms_csv_row_active_fire` — one active fire detection
- `openweather_hot_dry_windy_rainy` — hot/dry/windy conditions *with* rain
  (drives both wildfire environment scoring and flood rainfall scoring from
  one shared canned response, same as a real API call would)
- `openweather_calm_no_rain` — a calmer baseline, available for future tests
- `usgs_gauge_response_template` — one river gauge reading, with its
  `dateTime` deliberately left as a placeholder rather than a fixed date

**Deliberate fix before the fixture could be trusted long-term:** a
hardcoded USGS gauge timestamp would silently start failing once it aged
past the 48-hour staleness filter (`DEFAULT_MAX_GAUGE_READING_AGE_HOURS`,
Task 12) - a fixture that works today but breaks in a month is worse than
no fixture. Fixed by injecting a fresh `get_utc_now()` timestamp into the
gauge response at test-runtime (`build_usgs_response()`), keeping the
static fixture file itself timestamp-independent.

### `tests/test_integration.py` (new, 4 tests)

Reuses the exact `monkeypatch.setattr(module, "requests", fake)` pattern
already established in Tasks 10-12's own ingestion test suites - only the
HTTP layer is faked; `WildFireIngester`, `WeatherIngester`, `FloodIngester`,
`RiskScoringEngine`, `PortfolioAggregator`, and `HotspotDetector` are all
the real, unmocked components.

- **`test_full_cycle_completes_without_errors`** — the named
  `test_full_monitoring_cycle` scenario: two properties (one near the mock
  fire, one near the mock gauge/rain), run through `Monitor.run_monitoring_cycle()`
  (the actual production entrypoint from Task 23) with only the ingestion
  APIs mocked. Asserts zero errors, both properties scored, and hazard data
  actually landed in the database - proving ingest -> score -> alert ->
  store completes as one real chain, not simulated pieces.
- **`test_nearby_fire_produces_elevated_wildfire_score`** — a property
  ~11km from (and downwind of) the mock fire scores a wildfire risk clearly
  above baseline (`>30.0`), combining real proximity, wind-escalation, and
  environment scoring against ingested (not hand-built) hazard data.
- **`test_floodplain_property_scores_higher_than_non_floodplain`** — two
  otherwise-identical properties, one flagged `is_in_floodplain=True`, both
  scored against the same ingested rain/gauge data - the floodplain
  property's flood score is strictly higher and non-zero.
- **`test_metrics_and_hotspots_reflect_real_scored_portfolio`** — a
  4-property mock portfolio (a close elevated-risk pair, a floodplain
  property, and a far-away low-risk control), ingested and scored for
  real, then run through both `PortfolioAggregator.get_portfolio_metrics()`
  (Task 25) and `HotspotDetector.detect_hotspots()` (Task 26) - confirms
  the portfolio-level components work correctly against genuinely
  ingested-and-scored data, not synthetic `RiskDAO.save_assessment()` calls
  like earlier tasks' own test suites used.

**A `mocked_ingesters` fixture** centralizes the setup every non-Monitor
scenario needs: force-enable each ingester, assign fake API keys, and
monkeypatch all three ingestion modules' `requests` attribute at once -
including the subtlety that `FloodIngester` wraps its *own* internal
`WeatherIngester` instance for precipitation (a separate object from the
standalone `WeatherIngester` used for the weather hazard type), which needs
enabling independently or `fetch_precipitation()` silently returns `None`.

---

## Verification Results

```
pytest tests/test_integration.py -v
tests/test_integration.py::TestFullMonitoringCycle::test_full_cycle_completes_without_errors PASSED
tests/test_integration.py::TestPropertyScoringWithNearbyFire::test_nearby_fire_produces_elevated_wildfire_score PASSED
tests/test_integration.py::TestFloodRiskInFloodplain::test_floodplain_property_scores_higher_than_non_floodplain PASSED
tests/test_integration.py::TestPortfolioAggregation::test_metrics_and_hotspots_reflect_real_scored_portfolio PASSED
4 passed in 2.85s
```

All 4 named scenarios passed on the first real run - no live network calls
made (confirmed via each `FakeRequests`' call counter never touching the
real `requests` library).

**Full project test suite (Tasks 4-30 combined): 538 passed in 47.28s** ✓
(534 prior + 4 new). Purely temp-database and mocked-HTTP throughout - the
real `data/climate_risk.db` was confirmed untouched afterward (100
properties, 0 rows in every other table, unchanged from before this task).

---

## Files Created/Modified

| File | Purpose |
|------|---------|
| `tests/fixtures/mock_hazard_data.json` | Sample fire/weather/flood API response bodies for offline testing |
| `tests/test_integration.py` | New pytest suite (4 tests), full end-to-end scenarios |

---

## Following Reference Principles

**Continuous Monitoring, Not Point-in-Time** ✓ — `test_full_cycle_completes_without_errors`
is the first test to run `Monitor.run_monitoring_cycle()` itself against
mocked-but-realistic ingestion, rather than stubbing ingestion out entirely
(as `test_monitor_pytest.py`, Task 23, deliberately does) or hand-inserting
assessments directly (as most other tasks' live demos do) - closing the gap
between "each piece works" and "the whole system works together."

**Data Quality as a First-Class Concern** ✓ — catching the hardcoded-USGS-timestamp
issue before it could become a real, time-delayed test failure is the same
category of bug this project has caught before (Task 12's real stale-gauge
discovery) - just found proactively in test fixture design this time
instead of live data.

**Reliability Over Cleverness** ✓ — reusing the exact mocking pattern from
Tasks 10-12 rather than inventing a new one keeps this suite consistent
with the rest of the codebase's testing conventions.

---

## Usage Going Forward

```bash
pytest tests/test_integration.py -v
```

---

## Next Task

**Task 31: Create API Reference Documentation**
- Documentation task, not a testing task - likely the first task in Phase 6
  that isn't about test coverage. Will check `docs/task-breakdown.md` for
  exact scope before starting.

---

**Status:** Task 30 Complete ✓
**Phase 6 (Testing & Documentation) — 3 of 7 tasks complete.**
**Ready for:** Task 31 - API Reference Documentation
