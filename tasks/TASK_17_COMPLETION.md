# Task 17: Create Risk Score Aggregator - COMPLETED ✓

**Completed:** 2026-07-22
**Status:** `RiskAggregator` built and verified against the exact examples from `docs/task-breakdown.md`.

---

## What Was Completed

### `src/risk_scoring/aggregator.py` — `RiskAggregator` class

```python
class RiskAggregator:
    def classify_risk_level(score: float) -> str
    def aggregate_scores(wildfire_score: float, flood_score: float) -> Dict
    def build_overall_assessment(property_data, wildfire_result, flood_result) -> Dict
```

**`aggregate_scores()`** combines a wildfire score and flood score using the
`risk_scoring.overall_weights` from config (default 50/50, validated to sum to 1.0
since Task 5), returning `{overall_score, risk_level, breakdown}` — the breakdown
shows each hazard's raw score, its weight, and its actual point contribution, so the
math is never a black box.

**`classify_risk_level()`** buckets a 0-100 score into `low`/`medium`/`high`/`critical`
using the `risk_scoring.risk_levels` thresholds (low ≤25, medium ≤50, high ≤75,
critical >75) that have been sitting configured, unused, since Task 5.

**`build_overall_assessment()`** — a small convenience addition beyond the minimum
task scope: takes the full `{score, factors, explanation}` output of both
`WildFireScorer` and `FloodScorer` and combines them into one dict shaped to match
the `risk_assessments` table schema (Task 3) exactly — `wildfire_risk_score`,
`wildfire_factors`, `flood_risk_score`, `flood_factors`, `overall_risk_score`,
`risk_level` — plus both explanation strings. This is deliberately built now, ahead
of Task 18 (storage), since it's the natural place both scorers' output converges
before being written to the database or handed to a future LLM agent.

---

## Update: Single-Hazard Override Added (Same-Day Follow-Up)

The initial implementation surfaced a real issue during review: a property with a
**100/100 wildfire score** (an active, severe, wind-driven fire) and a **0 flood
score** produced an overall score of only **50 — "medium," not "critical."** This was
mathematically correct under a pure 50/50 weighted average and matched the originally
documented formula, but the business call was clear: **an extreme score in a single
hazard should never be diluted into a lower band just because the other hazard is
calm** — this is standard "worst-of-peril" thinking in underwriting, and it's
genuinely rare for a property to face severe wildfire and severe flood risk
simultaneously.

**Decision: Option D** (of four alternatives discussed — see chat history for the
comparison of a pure "worst-of" floor, a probabilistic/compounding combination, a
classification-only override, and this option). `aggregate_scores()` now applies a
**single-hazard override**: if either individual score is
`>= risk_scoring.critical_single_hazard_threshold` (default 85), `overall_score` is
raised to `max(weighted_average, dominant_score)` and `risk_level` is forced to
`"critical"`.

**Effect on the previously-verified examples:**

| Input | Before override | After override | Changed? |
|---|---|---|---|
| wildfire=60, flood=40 | 50.0 / medium | 50.0 / medium | No (dominant=60 < 85) |
| wildfire=85, flood=90 | 87.5 / critical | **90.0** / critical | Score changed, level unchanged (dominant=90 ≥ 85) |
| wildfire=100, flood=0 | 50.0 / medium | **100.0 / critical** | Both changed — the fix |

The (60, 40) example — the primary spec example from `docs/task-breakdown.md` — is
**unaffected**, since neither score reaches the 85 threshold. The (85, 90) example's
risk level was already "critical" either way; only its exact numeric score changed.
Both `docs/task-breakdown.md` and `docs/implementation-plan.md` were updated to
document the override formula.

---

## Verification Results

### Exact Task Breakdown Examples

```bash
python -m src.risk_scoring.aggregator
```
```
wildfire=60, flood=40  -> overall=50.0,  risk_level=medium    (matches spec exactly)
wildfire=85, flood=90  -> overall=90.0,  risk_level=critical  (score raised by override; level unchanged)
wildfire=0,  flood=0   -> overall=0.0,   risk_level=low
wildfire=100,flood=0   -> overall=100.0, risk_level=critical  (the fix - no longer diluted)
```

### Pytest Suite

`tests/test_aggregator_pytest.py` has **15 tests** across three classes (3 added
after the single-hazard override was implemented):

**TestAggregateScores (10)** — the (60,40) spec example unaffected by the override;
(85,90) now documented as triggering the override (score raised to 90, still
critical); 0/0→low; 100/100→critical; breakdown present with contributions summing
correctly; **the extreme-single-hazard fix locked in as a regression test**
(100/0 → 100.0/critical); a score of 84 (just below the 85 threshold) does *not*
trigger the override; a score of exactly 85 *does* trigger it; the override never
lowers the score below the plain weighted average when they're equal

**TestClassifyRiskLevel (4)** — boundary tests at all four thresholds (25/26,
50/51, 75/76, 100), confirming `<=` semantics match the config exactly (e.g., a
score of exactly 25 is "low," 26 is "medium")

**TestBuildOverallAssessment (1)** — confirms the convenience method correctly
combines both scorers' full output into the `risk_assessments`-shaped dict

```
tests/test_aggregator_pytest.py ............... 15 passed
```

**Full project test suite (Tasks 4-17 combined): 220 passed in 2.00s** ✓

---

## Files Created/Modified

| File | Purpose |
|------|---------|
| `src/risk_scoring/aggregator.py` | `RiskAggregator` class, incl. single-hazard override (155 lines) |
| `src/risk_scoring/__init__.py` | Exported `RiskAggregator` |
| `config/settings.json` | Added `risk_scoring.critical_single_hazard_threshold` (default 85) |
| `tests/test_aggregator_pytest.py` | Pytest suite (15 tests) |
| `docs/task-breakdown.md` | Task 17 updated to document the override |
| `docs/implementation-plan.md` | Overall Risk Score formula updated to include the override |

---

## Following Reference Principles

**Transparency and Explainability** ✓ — the `breakdown` dict means every overall
score can be traced back to exactly how much each hazard contributed, in points, not
just as opaque weights.

**Data-Driven Risk Intelligence** ✓ — risk level thresholds are read from config,
not hardcoded, so a future change to what counts as "critical" is a one-line config
edit, not a code change.

**Regulatory and Compliance Readiness** ✓ — naming the extreme-single-hazard
characteristic explicitly (rather than letting it go unnoticed) is exactly the kind
of behavior a regulator or auditor would ask about; having it documented and tested
means there's a ready answer.

---

## Usage Going Forward

```python
from src.risk_scoring import RiskAggregator

aggregator = RiskAggregator()
result = aggregator.aggregate_scores(wildfire_score=60, flood_score=40)
print(result["overall_score"], result["risk_level"])

# Or, combining full scorer output for storage/LLM context:
assessment = aggregator.build_overall_assessment(property_data, wildfire_result, flood_result)
```

---

## Next Task

**Task 18: Risk Assessment Storage & Retrieval**
- Build `src/database/risk_dao.py` — a `RiskDAO` class
- `save_assessment(...)`, `get_latest_assessment(property_id)`,
  `get_assessment_history(property_id, days)`, `get_all_latest_assessments()`
- This is where `build_overall_assessment()`'s output finally gets persisted into
  the `risk_assessments` table (Task 3 schema), completing the loop from raw hazard
  data all the way to a stored, auditable risk snapshot

---

**Status:** Task 17 Complete ✓
**Phase 3 (Risk Scoring) — 3 of 5 tasks complete.**
**Ready for:** Task 18 - Risk Assessment Storage & Retrieval
