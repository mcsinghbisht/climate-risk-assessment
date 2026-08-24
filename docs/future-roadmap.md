# Future Roadmap

What's built, what's deliberately deferred, and how to extend this project
next. Written at the completion of all 35 tasks (Phases 1-6) as the
reference point for future work - read this before starting anything new,
so effort lands on the highest-value gaps rather than re-discovering them.

**Table of Contents**
1. [What's Built](#1-whats-built)
2. [Priority 1: LLM Layer](#2-priority-1-llm-layer)
3. [Priority 2: Web UI / Dashboard](#3-priority-2-web-ui--dashboard)
4. [Priority 3: Underwriting/Claims/Pricing Integration](#4-priority-3-underwritingclaimspricing-integration)
5. [Known MVP Simplifications to Revisit](#5-known-mvp-simplifications-to-revisit)
6. [Other Deferred Enhancements](#6-other-deferred-enhancements)
7. [Suggested Order of Attack](#7-suggested-order-of-attack)

---

## 1. What's Built

The full continuous-monitoring pipeline, end to end: ingest real hazard
data (NASA FIRMS, OpenWeatherMap, USGS) → score every property for
wildfire and flood risk with explainable factor breakdowns → detect what
changed since the last assessment → evaluate and persist alerts (both
per-property and portfolio-wide) with a full lifecycle (active →
acknowledged/stale → resolved) → aggregate portfolio metrics and detect
geographic hotspots → run all of it automatically on a schedule → one CLI
entrypoint (`src/main.py`) to drive the whole thing. 559 passing tests,
98%+ coverage on the modules with dedicated coverage passes, full API
reference, an operations guide, and measured performance characteristics.

**What it is not, today:** there is no UI (everything is Python
classes/CLI/logs), no natural-language layer (scores and factors are
structured data, not prose, beyond the template-based `explanation` strings
already built into each scorer), and no connection to any external
underwriting/claims/pricing system. Those three gaps are this document's
main focus - the original project vision (`CLAUDE.md`) named all three
from the start ("AI-powered... Integration with underwriting, claims, and
pricing workflows"), and the 35-task plan deliberately built the data
foundation those three need before attempting any of them.

---

## 2. Priority 1: LLM Layer

**Why this is ready to build now, not from scratch:** every scorer was
deliberately designed since Task 15 to produce an explanation, not just a
number - this was flagged explicitly at the time ("I hope all these details
are captured somewhere while scoring so that the product can write these
plain english sentences to the users when we integrate LLM"). The
groundwork already in place:

- `WildFireScorer`/`FloodScorer` return `{"score", "factors", "explanation"}`
  - `factors` is a structured dict (distance_km, wind_speed, humidity,
    frp, etc.) - exactly what an LLM prompt needs as grounded context
  - `explanation` is already a template-generated natural-language string -
    a baseline to compare an LLM-generated one against, or a fallback if
    the LLM call fails
- `RiskAggregator.aggregate_scores()`'s `breakdown` dict explains *why* the
  overall score is what it is, including whether the single-hazard
  override fired
- `ChangeDetector.detect_changes()`'s `factors_changed` list is
  purpose-built for "what changed and why" narratives ("wind picked up,
  fire got closer") - already flagged in Task 22 as "useful... for a future
  LLM layer's context"
- `PortfolioReporter` already assembles portfolio-wide context (metrics,
  hotspots, active alerts) in one place - a natural single input to
  summarize

### Concrete scope

1. **Per-property narrative generation** — replace (or augment) each
   scorer's template `explanation` with an LLM call fed the same `factors`
   dict, producing genuinely natural prose for underwriters/brokers/
   customers who don't want to parse a JSON breakdown. Keep the template
   version as a fallback if the LLM call fails or is disabled - never make
   the LLM a hard dependency of the scoring pipeline itself.
2. **Alert narrative enrichment** — `AlertEngine`'s messages are currently
   template strings ("Wildfire risk score 85.0 exceeds..."). An LLM layer
   sitting between `AlertDAO` and `Notifier` could turn this into
   something closer to what a human would actually write, using
   `ChangeDetector`'s `factors_changed` for the "why now" context.
3. **Portfolio Q&A** — a chat-style interface over `PortfolioAggregator`/
   `HotspotDetector`/`AlertDAO` output ("which counties have the most
   critical alerts right now?" / "what changed for property 42 this
   week?"), likely as a small tool-calling agent rather than a single
   prompt - the existing DAOs are the natural "tools."
4. **Mitigation recommendations** — the original vision's "proactive
   mitigation recommendations" (CLAUDE.md) is not built at all yet. An LLM
   given a property's risk factors (e.g. high wind-escalation score, WUI
   flag) is well-suited to suggesting concrete, property-specific actions -
   this is genuinely new scope, not a wrapper around existing data.

### Design considerations carried over from this project's own patterns
- **Config-driven, not hardcoded**: model name, temperature, and
  enable/disable flags belong in `config/settings.json` under a new `llm`
  section, same as every other threshold in this project.
- **Never let the LLM call block or fail the core pipeline** - same
  error-isolation principle already applied everywhere (`Monitor`,
  `IngestionEngine`, `RiskScoringEngine` all wrap per-item work in
  try/except so one failure doesn't stop the rest). An LLM API call is
  slower and less reliable than anything currently in the pipeline; it
  should be additive/optional, not a new point of failure for scoring or
  alerting.
- **Redact API keys from logs** - the same lesson from Task 11 (a real key
  was once exposed in error output and had to be rotated) applies to
  whichever LLM provider's key is used.
- **Cache repeated explanations** - a property whose risk hasn't changed
  cycle over cycle shouldn't regenerate the same narrative every 5
  minutes; only call the LLM when `ChangeDetector` reports `changed=True`
  or a new alert fires.

---

## 3. Priority 2: Web UI / Dashboard

Already named as a stated future enhancement (`implementation-plan.md`
§12: "Web Dashboard: Flask/Streamlit UI for visualization") but not
started. Streamlit is the faster path to something usable (a Python-native
dashboard, no separate frontend build step) - Flask + a proper frontend is
the path if this needs to be embedded in a larger web product later.

### Concrete scope
1. **Portfolio overview page** — wraps `PortfolioAggregator.get_portfolio_metrics()`:
   risk-level distribution (chart), geographic distribution, score
   statistics, freshness indicator. This is almost directly renderable
   from existing data with no new backend work.
2. **Map view with hotspots** — property markers colored by risk level,
   `HotspotDetector.detect_hotspots()` overlaid as clusters. The existing
   `latitude`/`longitude` fields on every property and hotspot make this
   straightforward with any Python mapping library (folium, pydeck).
3. **Property drill-down** — one property's current assessment, factor
   breakdown, and history (`RiskDAO.get_assessment_history()`) as a trend
   chart - this is exactly what `ChangeDetector`'s "improving but not
   resolved" narrative was designed to support visually.
4. **Alert feed** — `AlertDAO.get_active_alerts()` as a live-updating list,
   with an "acknowledge" button wired to `AlertDAO.acknowledge_alert()` -
   the first real consumer of that method (currently only exercised by
   tests).
5. **Operational controls** — buttons wrapping `src/main.py`'s three modes
   (run one cycle now, view/regenerate the latest report, start/stop the
   scheduler) - turns the CLI entrypoint into something a non-technical
   user can drive.

### Design considerations
- **Read-only against existing DAOs first** - the dashboard should be a
  consumer of `PropertyDAO`/`RiskDAO`/`AlertDAO`/`PortfolioAggregator`/
  `HotspotDetector`, not a second data-access layer. This was explicitly
  why `AlertDAO`'s docstring (Task 21b) says "a future delivery channel...
  only ever needs to call `get_active_alerts()`... never needs to
  reimplement any of the above" - the dashboard is that future consumer.
- **The scheduler and the dashboard are separate processes** - don't run
  `SchedulerManager` inside the Streamlit/Flask process; the dashboard
  reads from the same SQLite file a separately-running `python src/main.py
  --mode run` process is writing to. SQLite handles concurrent readers
  fine; this avoids coupling the UI's lifecycle to the monitoring loop's.

---

## 4. Priority 3: Underwriting/Claims/Pricing Integration

Named in the original vision (`CLAUDE.md` §"Integration Points") but
completely unbuilt - no code references any external system today.

### Concrete scope
- **Outbound webhooks/API endpoints** for renewal repricing (underwriting)
  and loss prediction (claims) - likely a thin REST API (FastAPI/Flask)
  exposing `RiskDAO`/`PortfolioAggregator` read endpoints, plus a webhook
  fired on specific events (new critical alert, portfolio threshold
  breach) rather than requiring external systems to poll.
- **Broker/customer notification channels** - `Notifier` (Task 21) was
  explicitly designed to be extended this way: *"additional channels
  (email, SMS, Slack) can be added as new private `_send_to_*` methods and
  registered in `send_alert()`, without changing the public interface."*
  This is the smallest, most self-contained piece of this priority - a
  good first step before building a full integration API.

### Design considerations
- This is genuinely new infrastructure (auth, API versioning, webhook
  delivery/retry semantics) - don't underestimate it relative to the LLM
  layer or the dashboard, which are both primarily *consumers* of
  already-built data. This priority requires building new *producers*
  (APIs) that external, untrusted-by-default systems will call.

---

## 5. Known MVP Simplifications to Revisit

Explicitly flagged in the codebase and completion docs as "correct and
simple today, revisit if scale changes" - not bugs, but the first places to
look if performance or accuracy complaints show up at a larger portfolio size:

| Simplification | Where | Revisit trigger |
|---|---|---|
| `RiskScoringEngine` fetches the entire `hazard_data` table once per cycle, scans it per property | `scoring_engine.py` (Task 19) | Portfolio size or hazard_data row count growing into the thousands+ |
| `HotspotDetector` does O(n²) distance comparisons across all assessed properties | `hotspot_detector.py` (Task 26) | Same - large assessed-portfolio counts |
| `Monitor` re-queries assessment/alert state per property individually rather than batching | `monitor.py` (Task 23) | Same |
| Ingestion grid-cell size (0.5°) barely reduces API calls for a geographically *scattered* portfolio (measured: 82 cells for 100 properties spread across 10 states, ~162s real ingestion time) | `ingestion_engine.py` config (Task 33 finding) | A real portfolio spread as widely as the synthetic one - widen `grid_cell_size_degrees`, or consider concentrating ingestion by region |
| No automated database backup - `database.backup_enabled`/`backup_interval_hours` are configured but not implemented by any code | `config/settings.json` / ops guide (Task 32 finding) | Before any production deployment - this is a real gap, not a scale concern |

---

## 6. Other Deferred Enhancements

From `implementation-plan.md`'s original "Future Enhancements (Post-MVP)"
list, not otherwise covered above:

- **Advanced ML** - time-series forecasting, anomaly detection on hazard
  trends (distinct from the LLM layer - this is statistical/ML modeling of
  the risk scores themselves, not natural-language generation)
- **Commercial hazard data providers** - higher resolution/lower latency
  than the current free public APIs (NASA FIRMS, OpenWeatherMap, USGS)
- **Cloud deployment** - AWS/GCP, moving off SQLite + local file storage
  for redundancy and scale beyond a single machine
- **Compliance** - access controls, data governance, formal audit logging
  beyond the existing `alert_history` table

---

## 7. Suggested Order of Attack

1. **LLM layer, narrative generation only** (§2, items 1-2) - smallest
   scope, highest leverage on data already collected, no new
   infrastructure beyond an LLM API client and a config section.
2. **Web UI, read-only dashboard** (§3, items 1-4) - makes everything
   built so far actually visible to a non-technical user; no new backend
   logic needed, purely a consumption layer.
3. **Notifier channel extension** (§4, second bullet) - the smallest,
   most self-contained piece of the integration priority; a natural
   companion to the dashboard's alert feed.
4. **LLM layer, mitigation recommendations + portfolio Q&A** (§2, items
   3-4) - more open-ended, benefits from having the dashboard already in
   place to surface the results.
5. **Full underwriting/claims integration API** (§4, first bullet) and
   **cloud deployment** - the two largest, most infrastructure-heavy items;
   sequence these last and only once there's a concrete external
   consumer/deployment target driving the requirements, rather than
   building speculative API surface.

---

## Related Documentation
- [api-reference.md](api-reference.md) - what's callable today
- [operations-guide.md](operations-guide.md) - how to run what's built today
- [web-ui-llm-implementation-plan.md](web-ui-llm-implementation-plan.md) - detailed step-by-step plan for web dashboard and LLM layer (start here to build Priority 1 & 2)
- [implementation-plan.md](implementation-plan.md) - original design decisions and trade-offs
- [scaling-design.md](scaling-design.md) - ingestion scaling rationale (relevant to §5's grid-cell finding)
- [alert-lifecycle-design.md](alert-lifecycle-design.md) - alert state machine, relevant to §3's alert feed and §4's notification channels
