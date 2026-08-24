# Task 18: Risk Assessment Storage & Retrieval - COMPLETED ✓

**Completed:** 2026-07-22
**Status:** `RiskDAO` built, tested, and verified — closes the loop from raw hazard data to a stored, auditable risk snapshot.

---

## What Was Completed

### `src/database/risk_dao.py` — `RiskDAO` class

```python
class RiskDAO:
    def save_assessment(assessment: Dict, alerts_triggered: Optional[List] = None) -> int
    def get_latest_assessment(property_id: int) -> Optional[Dict]
    def get_assessment_history(property_id: int, days: int = 30) -> List[Dict]
    def get_all_latest_assessments() -> List[Dict]
```

Mirrors `PropertyDAO`'s design (Task 9), with one deliberate difference:
**`save_assessment()` never upserts.** Unlike properties (which represent one current
state), each assessment is a new time-series snapshot — the whole reason this table
exists is to preserve risk history over time, not just the latest value.

**Input shape:** `save_assessment()` accepts the exact dict produced by Task 17's
`RiskAggregator.build_overall_assessment()` — no translation layer needed between
scoring and storage, same principle applied throughout this project since Task 13.

### Schema Gap Handled Without a Migration

`risk_assessments` (Task 3) has `wildfire_factors`/`flood_factors` JSON columns, but
no dedicated column for the explanation strings `WildFireScorer`/`FloodScorer`
produce. Rather than add a schema migration for two extra text columns, the
explanation is folded into each factors JSON blob under an `"explanation"` key before
storage — the same pattern already used for `raw_data` in `hazard_data` (Tasks
10-12): more detail inside an existing JSON column, not a new column for every new
piece of context.

### Option 2 From the Task Summary, Implemented as Discussed

`alerts_triggered` is accepted as an optional parameter, defaulting to `None`/`NULL`.
Task 20 (Alert Engine) will pass real alert data through this same method later — no
changes to `RiskDAO` will be needed when that task arrives.

### "Latest" Determined by `assessment_id`, Not Timestamp

All three read methods order by `assessment_id DESC`, not `assessment_timestamp
DESC`. Since `assessment_id` is a strictly-increasing autoincrement key, this avoids
any ambiguity if two assessments for the same property land in the same second
(e.g., during rapid testing, or a monitoring cycle running faster than 1-second
timestamp resolution) — a small robustness choice made proactively rather than
waiting to discover a tie-breaking bug the way Task 10/12's bugs were found.

---

## Verification Results

### Manual Demo (Real Database)

```bash
python -m src.database.risk_dao
```
```
Saved assessment_id: 1
Latest assessment: overall=44.5, level=medium
Wildfire factors (with explanation folded in): {'proximity_score': 88.28, 'distance_km': 5.86,
  'explanation': 'Nearest active fire is 5.86 km away.'}
History (last 30 days): 1 record(s)
All latest assessments across portfolio: 1 record(s)
```

Confirmed via `tools/query.py` against the real `risk_assessments` table
(`assessment_id=1, property_id=1, overall_risk_score=44.5, risk_level=medium,
wildfire_risk_score=77.09, flood_risk_score=12.0`) — all values round-tripped
correctly through storage and retrieval. Demo row cleared afterward
(`DELETE FROM risk_assessments`) to keep the production database clean, consistent
with Tasks 10-12's approach to manual verification data.

### Pytest Suite

Created `tests/test_risk_dao_pytest.py` with **15 tests** across four classes, using
a temporary SQLite database with both `properties` and `risk_assessments` tables (to
exercise the real foreign key relationship, not a mocked one):

**TestSaveAssessment (6)** — returns a valid new ID; **a second save creates a new
row, not an update** (confirming the deliberate no-upsert design); explanations are
correctly folded into the factors JSON; factors without an explanation are stored
correctly (no stray `"explanation": null` key); `alerts_triggered` defaults to `None`
when omitted; `alerts_triggered` is correctly stored and retrieved when provided

**TestGetLatestAssessment (4)** — returns `None` when no assessments exist; returns
correct scores; returns the most recent of multiple saved assessments; returns `None`
for a property_id with no data (not an error)

**TestGetAssessmentHistory (3)** — empty list for an unknown property; all
assessments within the window returned newest-first; only the requested property's
assessments are returned (not another property's)

**TestGetAllLatestAssessments (2)** — empty list when no assessments exist anywhere;
**exactly one row per property, not one row per snapshot** — verified with property 1
having 3 historical snapshots and property 2 having 1, confirming the join correctly
picks each property's single newest row rather than returning all 4

```
tests/test_risk_dao_pytest.py ............... 15 passed
```

**Full project test suite (Tasks 4-18 combined): 235 passed in 2.44s** ✓

---

## Files Created/Modified

| File | Purpose |
|------|---------|
| `src/database/risk_dao.py` | `RiskDAO` class (195 lines) |
| `src/database/__init__.py` | Exported `RiskDAO` |
| `tests/test_risk_dao_pytest.py` | Pytest suite (15 tests, real FK relationship via temp DB) |

---

## Following Reference Principles

**Data-Driven Risk Intelligence / Regulatory Readiness** ✓ — this is the concrete
mechanism that makes risk assessments auditable: every snapshot is preserved, never
overwritten, so "what did we know and when" can always be reconstructed for a given
property.

**Scalability From Day One** ✓ — `get_all_latest_assessments()` returns one row per
property via a single indexed join, not N queries in a loop — the same query shape
works whether the portfolio has 100 properties or 100,000.

**Transparency and Explainability** ✓ — folding the explanation string into the
factors JSON means a stored assessment is self-describing: reading one row back
gives both the numeric breakdown and the plain-English reasoning behind it, with
nothing to reconstruct from a separate source.

---

## Usage Going Forward

```python
from src.database import RiskDAO
from src.risk_scoring import WildFireScorer, FloodScorer, RiskAggregator

wildfire_result = WildFireScorer().calculate_risk_for_property(property_data, hazard_data)
flood_result = FloodScorer().calculate_risk_for_property(property_data, hazard_data)
assessment = RiskAggregator().build_overall_assessment(property_data, wildfire_result, flood_result)

RiskDAO().save_assessment(assessment)
```

---

## Next Task

**Task 19: Create Risk Scoring Orchestrator**
- Build `src/risk_scoring/scoring_engine.py` — a `RiskScoringEngine` class
- `score_all_properties()` — the first component to run this entire pipeline (scoring
  + aggregation + storage) across **all 100 properties** in one call, not just a
  single demo property
- This is where `PropertyDAO`, both scorers, `RiskAggregator`, and `RiskDAO` all come
  together for the first time as a complete system

---

**Status:** Task 18 Complete ✓
**Phase 3 (Risk Scoring) — 4 of 5 tasks complete.**
**Ready for:** Task 19 - Risk Scoring Orchestrator
