# Task 19: Create Risk Scoring Orchestrator - COMPLETED ✓

**Completed:** 2026-07-22
**Status:** `RiskScoringEngine` built and verified — the first true "whole system" moment: `PropertyDAO`, both scorers, `RiskAggregator`, and `RiskDAO` running together across all 100 properties in one call.

---

## What Was Completed

### `src/risk_scoring/scoring_engine.py` — `RiskScoringEngine` class

```python
class RiskScoringEngine:
    def score_all_properties() -> Dict
```

**Behavior:**
1. Fetches all properties via `PropertyDAO.get_all_properties()`
2. Fetches the entire `hazard_data` table once (see MVP simplification below)
3. For each property (wrapped in its own `try/except` — one property's scoring
   failure does not stop the rest, same error-isolation principle as Task 14's
   `IngestionEngine`):
   - Scores wildfire risk (`WildFireScorer`)
   - Scores flood risk (`FloodScorer`)
   - Combines both into an overall assessment (`RiskAggregator.build_overall_assessment()`)
   - Persists the snapshot (`RiskDAO.save_assessment()`)
4. Returns a summary: `{properties_scored, average_risk, high_risk_count, critical_count, errors}`

**Documented MVP simplification:** fetches the entire `hazard_data` table once and
passes the same full list to every property's scorers. Each scorer already finds the
nearest relevant hazard internally and applies its own `proximity_max_km` cutoff
(Tasks 15/16), so out-of-range data naturally scores 0 — this is correct, just not
optimally efficient at scale. At production volume, this is the next place Task 14's
grid-cell design pattern would need to extend to the read side (querying only
hazard_data within each property's cell, rather than scanning the full table per
run). Not needed at 100 properties / a few hundred hazard rows; explicitly flagged
for when it will be.

---

## Verification Results

### Live Run Against the Real 100-Property Portfolio (Baseline: Empty hazard_data)

```bash
python -m src.risk_scoring.scoring_engine
```
```
Properties scored: 100
Average risk:       2.1
High risk count:    0
Critical count:     0
```

With no hazard data yet ingested, every property's wildfire/flood scores from
hazard-driven factors are 0 — the only signal is each property's own static
`is_in_floodplain` flag, contributing exactly 10.0 to `overall_risk_score` for
floodplain properties (floodplain_score=100 × flood weight 0.2 × overall weight
0.5 = 10) and 0.0 for the rest. This is the expected, correct "graceful
degradation with no data" behavior designed back in Tasks 15/16 — not an error.

### Live Run With Real Hazard Data Seeded

To prove the pipeline responds to genuine signal (not just the floodplain
baseline), seeded real hazard data via a bounded 2-cell live ingestion (same
technique as Task 14's smoke test): **45 fires, 213 gauge readings, 2 weather/
precipitation points** across a California and a Louisiana cell. Re-running the
scorer against this real data:

```
Properties scored: 100
Average risk:       7.27
High risk count:    0
Critical count:     0

Top-scoring properties:
  property_id=48: overall=32.53 (medium)  wildfire=38.26  flood=26.81
  property_id=56: overall=31.63 (medium)  wildfire=26.30  flood=36.96
  property_id=58: overall=26.64 (medium)  wildfire=35.83  flood=17.46
```

Properties geographically near the two seeded cells picked up genuine,
differentiated wildfire and flood signal from **real NASA FIRMS and USGS data**,
producing "medium" risk levels, while distant properties correctly stayed near
baseline — confirming the full chain (ingestion → scoring → aggregation →
storage) works correctly end-to-end with live external data, not just
synthetic test fixtures. Both `hazard_data` and `risk_assessments` were cleared
afterward to keep the production database clean, consistent with every prior
live-data task.

### Pytest Suite

Created `tests/test_scoring_engine_pytest.py` with **8 tests**, using **real Task
7-generated properties** (not synthetic test fixtures) inserted into a temporary
database, and exercising the actual `WildFireScorer`/`FloodScorer`/
`RiskAggregator`/`RiskDAO` stack — no mocks — to prove the real wiring works, not
just each component in isolation:

- All properties in the portfolio get scored (`properties_scored` matches the count)
- An empty portfolio completes cleanly with a zero-value summary, no errors
- Exactly one assessment is persisted per property
- `average_risk` in the summary matches an independently computed mean of the
  stored `overall_risk_score` values
- **A floodplain property scores higher than an otherwise-identical non-floodplain
  property** — proving the static property attribute correctly flows through the
  whole pipeline into the final score
- `high_risk_count`/`critical_count` in the summary match the actual count of
  `risk_level` values stored in the database (not just an internal counter that
  could silently drift from what was actually saved)
- **A wildfire hazard_data row near a property increases that property's stored
  wildfire_risk_score above 0** — the clearest possible proof the DB→scorer→DB
  round-trip works correctly
- The summary always has all five expected keys

```
tests/test_scoring_engine_pytest.py ........ 8 passed
```

**Full project test suite (Tasks 4-19 combined): 243 passed in 2.86s** ✓

---

## Files Created/Modified

| File | Purpose |
|------|---------|
| `src/risk_scoring/scoring_engine.py` | `RiskScoringEngine` class (140 lines) |
| `src/risk_scoring/__init__.py` | Exported `RiskScoringEngine` |
| `tests/test_scoring_engine_pytest.py` | Pytest suite (8 tests, real properties + real scorer stack) |

---

## Following Reference Principles

**Data-Driven Risk Intelligence** ✓ — this task is the concrete proof that every
piece built since Task 9 composes correctly into one coherent pipeline, not just
individually-tested components that happen to share compatible interfaces.

**Scalability From Day One** ✓ — the documented MVP simplification (fetch-all vs.
spatial pre-filter) is named explicitly as a scale boundary now, rather than
discovered as a performance surprise later — the same discipline applied throughout
this project (Tasks 12, 14, 16, 18 all have similar documented, tested boundaries).

**Data Quality as a First-Class Concern** ✓ — per-property error isolation means one
malformed property record or scoring edge case degrades the batch's completeness,
not its correctness — the other 99 properties still get scored and stored correctly.

---

## Usage Going Forward

```python
from src.risk_scoring import RiskScoringEngine

engine = RiskScoringEngine()
summary = engine.score_all_properties()
print(f"{summary['properties_scored']} scored, avg={summary['average_risk']}, "
      f"critical={summary['critical_count']}")
```

Or from the command line:
```bash
python -m src.risk_scoring.scoring_engine
```

---

## Next Task

**Phase 4 begins: Task 20 — Create Alert Threshold Engine**
- Build `src/alerts/alert_engine.py` — an `AlertEngine` class
- Compares current vs. previous risk assessments (now retrievable via
  `RiskDAO.get_assessment_history()`) against configured thresholds
  (`config/settings.json` → `alerts.*`, sitting unused since Task 5)
- The `alerts_triggered` parameter `RiskDAO.save_assessment()` already accepts
  (Task 18, Option 2) gets its first real caller here

---

**Status:** Task 19 Complete ✓
**Phase 3 (Risk Scoring, Tasks 15-19) fully complete.**
**Ready for:** Task 20 - Alert Threshold Engine
