# High-Level Architecture - Climate Risk Assessment System

Complete system overview at 10,000 feet.

---

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│              CLIMATE RISK ASSESSMENT SYSTEM                     │
│                   (Complete Implementation)                     │
└─────────────────────────────────────────────────────────────────┘

┌──────────────────────────┐       ┌──────────────────────────┐
│   DATA SOURCES           │       │   USER INTERFACES        │
│  (Ingestion Layer)       │       │   (Consumption Layer)    │
├──────────────────────────┤       ├──────────────────────────┤
│ • NASA FIRMS (Wildfire)  │       │ • Streamlit Dashboard    │
│ • OpenWeatherMap         │       │   - Portfolio Manager    │
│ • USGS (Flood)           │       │   - Underwriter View     │
│ • Property Database      │       │ • Claude AI Chat         │
│ • Risk Assessments (DB)  │       │   - Natural Q&A          │
└──────────────────────────┘       └──────────────────────────┘
         │                                    ▲
         │                                    │
         ▼                                    │
┌─────────────────────────────────────────────────────────────────┐
│          CORE PROCESSING ENGINE (Backend)                       │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │ 1. DATA INGESTION                                       │  │
│  │    - Fetch real-time hazard data                        │  │
│  │    - Normalize & validate                               │  │
│  │    - Rate-limited API calls                             │  │
│  └─────────────────────────────────────────────────────────┘  │
│              │                                                  │
│              ▼                                                  │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │ 2. RISK SCORING                                         │  │
│  │    - Wildfire risk (proximity, wind, escalation)        │  │
│  │    - Flood risk (rainfall, drainage, saturation)        │  │
│  │    - Overall risk aggregation                           │  │
│  │    - Factor breakdown for explainability                │  │
│  └─────────────────────────────────────────────────────────┘  │
│              │                                                  │
│              ▼                                                  │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │ 3. CONTINUOUS MONITORING                                │  │
│  │    - Change detection (what changed since last cycle)   │  │
│  │    - Threshold evaluation                               │  │
│  │    - Alert generation                                   │  │
│  │    - Scheduled execution (configurable interval)        │  │
│  └─────────────────────────────────────────────────────────┘  │
│              │                                                  │
│              ▼                                                  │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │ 4. PORTFOLIO AGGREGATION                                │  │
│  │    - Portfolio-level metrics                            │  │
│  │    - Geographic hotspot detection                       │  │
│  │    - Accumulation tracking                              │  │
│  │    - Risk clustering analysis                           │  │
│  └─────────────────────────────────────────────────────────┘  │
│              │                                                  │
│              ▼                                                  │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │ 5. LLM ENHANCEMENT LAYER                                │  │
│  │    - Risk explanation generation (Claude)               │  │
│  │    - Natural language Q&A                               │  │
│  │    - Tool-based data access                             │  │
│  │    - Caching for performance                            │  │
│  └─────────────────────────────────────────────────────────┘  │
│                       │                                         │
│                       ▼                                         │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │ 6. PERSISTENCE & STORAGE                                │  │
│  │    - SQLite Database (properties, risks, alerts)         │  │
│  │    - Structured data model with DAOs                    │  │
│  │    - Alert history & lifecycle tracking                 │  │
│  │    - LLM explanation cache                              │  │
│  └─────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                             ▲
                             │
                    (Read/Write Operations)
                             │
         ┌───────────────────┴────────────────────┐
         │                                        │
         ▼                                        ▼
   Dashboard Access               Integration Points
   (Streamlit UI)                 (Future: APIs/Webhooks)
```

---

## Architecture Layers

### 1. Data Ingestion Layer
**Responsibility:** Fetch and normalize real-time environmental data

**Components:**
- `IngestionEngine` — Orchestrates all ingestion sources
- `WildFireIngestion` — NASA FIRMS satellite fire data
- `FloodIngestion` — USGS flood gauge & rainfall data
- `WeatherIngestion` — OpenWeatherMap conditions
- `PropertyLoader` — Initial property database load
- `DataNormalizer` — Standardize units and coordinate systems
- `RateLimiter` — Respect API rate limits

**Output:** Normalized hazard data stored in SQLite

**Key Property:** Non-blocking (failures don't stop the monitoring loop)

### 2. Risk Scoring Layer
**Responsibility:** Calculate property-level risk scores with explainability

**Components:**
- `WildFireScorer` — Proximity + environmental escalation factors
- `FloodScorer` — Rainfall + drainage + soil saturation factors
- `RiskAggregator` — Combine wildfire/flood into overall score
- `ScoringEngine` — Apply to entire portfolio

**Output Structure:**
```python
{
    "overall_risk_score": 65.2,      # 0-100
    "risk_level": "medium",           # low/medium/high/critical
    "wildfire_score": 45.0,
    "flood_score": 55.3,
    "factors": {                      # Explainability
        "distance_to_active_fire_km": 12.5,
        "wind_escalation_factor": 1.3,
        "rainfall_24h_mm": 45.2,
        ...
    },
    "explanation": "Natural language description..."
}
```

**Key Property:** Deterministic (same inputs → same outputs)

### 3. Continuous Monitoring Layer
**Responsibility:** Detect changes and trigger alerts

**Components:**
- `ChangeDetector` — Compare current vs. previous assessment
- `AlertEngine` — Evaluate thresholds and create alerts
- `Monitor` — Main monitoring loop
- `SchedulerManager` — Periodic execution

**Flow:**
```
For each property:
  1. Score current state
  2. Compare to previous assessment
  3. If changed or threshold breached → create alert
  4. Persist alert with full context
  5. Notify stakeholders (if configured)
```

**Key Property:** Triggers only when state changes (efficiency)

### 4. Portfolio Aggregation Layer
**Responsibility:** Portfolio-level insights and clustering

**Components:**
- `PortfolioAggregator` — Portfolio metrics (avg, distribution, etc.)
- `HotspotDetector` — Geographic clusters of high-risk properties
- `PortfolioReporter` — Summary reporting

**Output Examples:**
- "45% of portfolio is in high/critical risk"
- "3 hotspots detected in California, 2 in Texas"
- "Average risk score: 52.3, trending up"

**Key Property:** Enables early warning (accumulation detection)

### 5. LLM Enhancement Layer
**Responsibility:** Natural language explanations and Q&A

**Components:**
- `ClimateRiskChatAgent` — Agentic loop with Claude
- `ExplanationCache` — Cache LLM-generated text
- 8 Curated Tools — DAO wrappers for safe data access
- `SafeSQLExecutor` — Optional SQL fallback (guarded)

**Capabilities:**
1. Risk explanation generation (replaces templates)
2. Natural language Q&A (tool use over DAOs)
3. Change narrative ("what changed and why")
4. Portfolio summarization

**Key Property:** Optional & non-blocking (system works without LLM)

### 6. Persistence Layer
**Responsibility:** Store state and enable history tracking

**Database Schema:**
- `properties` — Insured property records
- `property_risk_assessments` — Timestamped risk scores
- `alerts` — Alert generation and lifecycle
- `alert_history` — Complete audit trail

**Data Access Objects (DAOs):**
- `PropertyDAO` — Property queries
- `RiskDAO` — Risk assessment history
- `AlertDAO` — Alert lifecycle management

**Key Property:** SQLite (single-file, deployable, queryable)

---

## User-Facing Interfaces

### Portfolio Manager Dashboard
**Audience:** Portfolio/risk managers

**Features:**
- Portfolio KPIs (total properties, % critical, alert count)
- Risk distribution charts (pie, bar)
- Geographic heatmap with hotspots
- Active alerts table
- System health indicators

**Data Sources:** `PortfolioAggregator`, `HotspotDetector`, `AlertDAO`

### Underwriter Workspace
**Audience:** Underwriters evaluating individual properties

**Features:**
- Property search/selection
- Current risk scores (wildfire, flood, overall)
- Factor breakdown (radar charts)
- Risk explanation (LLM-generated)
- Historical trend chart
- Related alerts
- Export assessments (CSV)

**Data Sources:** `PropertyDAO`, `RiskDAO`, `AlertDAO`, `ChatAgent`

### Claude AI Chat
**Audience:** Both roles (natural language Q&A)

**Capabilities:**
- "How many properties are in critical risk?" → uses `get_properties_by_risk_level()`
- "What's property 42's risk history?" → uses `get_property_risk_history()`
- "Show me hotspots in California" → uses `get_hotspots()`, filters by state
- Free-text questions answered via Claude with tool context

**Powered by:** Tool use with 8 curated DAO methods

---

## Data Flow Diagram

### Monitoring Cycle (Periodic)
```
┌─────────────────────────────────────────────────────────────┐
│ START: Scheduled Monitor Cycle (e.g., every 5 minutes)      │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│ 1. INGEST                                                   │
│    - Fetch latest fire, weather, flood data from APIs       │
│    - Normalize to standard formats                          │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. SCORE                                                    │
│    - For each property, calculate wildfire & flood risk     │
│    - Generate factors breakdown & explanation               │
│    - Persist to property_risk_assessments table             │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. DETECT CHANGES                                           │
│    - Compare new assessment to previous                     │
│    - Identify which factors changed                         │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. ALERT                                                    │
│    - If changed or threshold breached:                      │
│      • Create alert record                                  │
│      • Mark as "triggered"                                  │
│      • Queue notification (if not suppressed)               │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. AGGREGATE                                                │
│    - Recalculate portfolio metrics                          │
│    - Detect geographic hotspots                             │
│    - Update portfolio summary                               │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│ END: Cycle Complete - Ready for next monitoring interval    │
└─────────────────────────────────────────────────────────────┘
```

### User Interaction Flow
```
User Opens Dashboard
         │
         ▼
Streamlit loads PropertyDAO / RiskDAO data
         │
         ├─→ Display portfolio KPIs (1 query)
         ├─→ Load risk distribution (1 query)
         ├─→ Fetch hotspots (1 query)
         ├─→ Get active alerts (1 query)
         │
         └─→ User selects a property
                 │
                 ▼
            Underwriter view loads:
            - Property details
            - Current risk scores
            - Factor breakdown
            - Risk history (10 most recent)
            - Related alerts
                 │
                 ▼
            User clicks "Chat about this property"
                 │
                 ▼
            ClimateRiskChatAgent:
            1. User asks question
            2. Claude evaluates tools available
            3. Execute 1+ DAO tool(s)
            4. Claude synthesizes answer
            5. Cache explanation
            6. Return to user
```

---

## Key Architectural Principles

### 1. **Separation of Concerns**
Each layer is independent:
- Data ingestion doesn't know about scoring
- Scoring doesn't know about monitoring
- Monitoring doesn't know about UI
- Enables testing, scaling, and replacement

### 2. **Error Isolation**
Failures are local:
- One API call fails → skip that data, continue
- One property fails to score → alert, continue
- One alert notification fails → log, continue
- LLM call fails → fallback to template, continue

### 3. **Configuration Over Code**
All thresholds, models, and flags in `config/settings.json`:
- Risk thresholds (when to alert)
- LLM model and parameters
- Ingestion API credentials
- Monitoring interval and schedule
- Notification settings

### 4. **Explainability**
Every decision is explained:
- Risk scores include factor breakdown
- Changes tracked (what changed, by how much)
- Alerts logged with full context
- LLM explanations provide narratives

### 5. **Non-Blocking Enhancements**
UI and LLM are consumption layers, not core:
- System runs without Streamlit or Claude
- LLM failures don't stop monitoring
- Cache reduces API cost but isn't required
- Enables graceful degradation

### 6. **Data-Driven**
All decisions based on structured data:
- Factors, scores, assessments all queryable
- DAO pattern ensures consistent access
- SQLite enables ad-hoc investigation
- History preserved for auditing

---

## Deployment Model

### Development/MVP (Current)
- Single machine deployment
- SQLite database (single file)
- Monitoring loop as separate Python process
- Streamlit UI as separate process
- Manual configuration via JSON

### Production (Deferred, Post-Phase 6)
- Cloud deployment (AWS/GCP)
- Managed database (PostgreSQL)
- Containerized services (Docker)
- API for external integrations
- Webhooks for event notifications
- Formal access control & audit logging

---

## What's Built vs. Deferred

### ✅ Built (Phases 1-6)
- Full monitoring pipeline (ingest → score → alert → aggregate)
- SQLite-based persistence with DAOs
- Streamlit dashboard (Portfolio Manager & Underwriter views)
- Claude AI chat with tool use
- Comprehensive testing (559+ tests, 98%+ coverage)
- Documentation & API reference

### ⏳ Deferred (Phase 7+)
- Integration APIs (webhooks for underwriting/claims)
- Advanced ML (forecasting, anomaly detection)
- Cloud deployment & scaling
- Formal access control & compliance
- Commercial hazard data providers
- Mobile app

---

## Technology Stack

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| **Data Ingestion** | Python (requests) | Simple HTTP, rate limiting control |
| **Risk Scoring** | Python (numpy) | Numerical computation, deterministic |
| **Monitoring** | Python (APScheduler) | Periodic task scheduling |
| **Persistence** | SQLite + Python | Single file, queryable, standard SQL |
| **Dashboard** | Streamlit | Python-native, fast to iterate, no frontend build |
| **LLM** | Anthropic Claude | State-of-the-art reasoning, tool use, cost-effective |
| **Testing** | pytest | Standard Python testing, good coverage tools |

---

## Success Metrics

### System Health
- Monitoring cycle completion rate (target: 99%+)
- API call success rate (target: 95%+, retries handled)
- Alert latency (target: <5 min from hazard change to alert)

### Data Quality
- Risk score consistency (deterministic for same inputs)
- Factor breakdown coverage (all scoring decisions explainable)
- Change detection accuracy (no spurious alerts)

### User Value
- Dashboard load time (target: <2s for full page)
- Chat response time (target: <5s including LLM call)
- Query accuracy (sample QA queries answered correctly)

---

## Glossary

- **Assessment** — One property's risk score at one point in time
- **Hazard** — Fire, flood, or weather condition at a location
- **Hotspot** — Geographic cluster of high-risk properties
- **Alert** — Notification triggered when risk breaches threshold or changes significantly
- **Lifecycle** — Alert states (triggered → acknowledged → stale → resolved)
- **Factor** — Individual component of risk score (e.g., distance_to_fire_km)
- **DAO** — Data Access Object (pattern for database queries)
- **Tool Use** — Claude's ability to call functions (our DAOs) to gather context

---

## Further Reading

- [ARCHITECTURE_LOW_LEVEL.md](ARCHITECTURE_LOW_LEVEL.md) — Detailed component design
- [api-reference.md](api-reference.md) — All classes and methods
- [operations-guide.md](operations-guide.md) — Running and monitoring
- [CLAUDE.md](../CLAUDE.md) — Project vision and context
