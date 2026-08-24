# Future Roadmap - Phase 7+

What's complete, what's deliberately deferred, and the highest-value next steps.  
Updated after completion of all 35 tasks (Phases 1-6): full backend + web UI + LLM layer.

**Table of Contents**
1. [What's Built (Phases 1-6)](#1-whats-built-phases-1-6)
2. [Phase 7: Production Hardening](#2-phase-7-production-hardening)
3. [Phase 8: Integration & API](#3-phase-8-integration--api)
4. [Phase 9: Advanced Features](#4-phase-9-advanced-features)
5. [Known MVP Simplifications to Revisit](#5-known-mvp-simplifications-to-revisit)
6. [Deployment Roadmap](#6-deployment-roadmap)
7. [Suggested Order of Attack](#7-suggested-order-of-attack)

---

## 1. What's Built (Phases 1-6)

**✅ COMPLETE:** Full system end-to-end

**Backend (Tasks 1-22):**
- Continuous monitoring pipeline: ingest → score → detect → alert → aggregate
- Real-time hazard data (NASA FIRMS, OpenWeatherMap, USGS)
- Dynamic risk scoring (wildfire + flood) with explainable factors
- Change detection and threshold-based alerting
- Portfolio metrics and geographic hotspot clustering
- SQLite persistence with DAO-based data access
- 559+ passing tests, 98%+ coverage

**Frontend (Tasks 23-28):**
- Streamlit multi-page dashboard (Portfolio Manager & Underwriter roles)
- Interactive KPI metrics, risk distributions, geographic maps (Folium)
- Property-level drill-down with factor breakdowns
- Active alerts management
- CSV/PDF export for reports
- Responsive design (mobile/tablet/desktop) with dark mode support

**LLM Layer (Tasks 29-35):**
- Claude-powered chat agent with tool use orchestration
- 8 curated DAO tools for safe data access
- LLM explanation cache (30-day TTL) for cost optimization
- Role-based system prompts (Portfolio Manager vs. Underwriter)
- Optional SQL fallback (disabled by default)
- Unit tests with mocked Anthropic API

**Documentation:**
- High-level and low-level architecture (NEW)
- Comprehensive API reference
- Operations guide with troubleshooting
- Task breakdown (all 35 complete)
- Reference principles and design decisions

---

## 2. Phase 7: Production Hardening

Get the system production-ready with better observability, reliability, and maintainability.

### 2.1 Enhanced Monitoring & Observability

**What's needed:**
- Structured logging (not just print/print) with correlation IDs across requests
- Metrics collection (Prometheus-compatible): API latency, score distribution, alert counts
- Health check endpoint: "is the system alive? last monitoring cycle successful? LLM working?"
- Dashboard for ops: Last cycle status, error rates, queue depths, API quota usage

**Scope estimate:** 3-4 tasks
- Logging refactor (centralized structured format)
- Metrics collection (per-component counters)
- Health check API (FastAPI stub)
- Ops dashboard (Streamlit or static HTML)

**Why now:** Before deploying to production, ops needs visibility into what's happening.

### 2.2 Database Backup & Recovery

**What's needed:**
- Automated SQLite backups (hourly or configurable)
- Backup retention policy (keep last N backups)
- Recovery procedure documentation
- Point-in-time recovery testing

**Scope estimate:** 2 tasks
- Backup implementation (simple file copy, or cloud storage)
- Recovery testing & documentation

**Why now:** Data loss is catastrophic; backups are non-negotiable before production.

### 2.3 Configuration Validation & Safe Upgrades

**What's needed:**
- Config schema validation on startup (fail loudly if settings.json is malformed)
- Database migration safety checks (versioning, rollback capability)
- Secrets rotation procedures (API key rotation without downtime)

**Scope estimate:** 2 tasks
- Config validation (JSON schema)
- Database migration versioning

**Why now:** Configuration errors and migrations are common production issues.

### 2.4 Performance Optimization

**What's built:** Measured baseline (165s per cycle, 1.2s dashboard load)  
**What's needed:**
- Database query optimization (indexes on risk_level, timestamps)
- Caching layer for frequently-accessed queries (e.g., portfolio metrics)
- Hotspot detection optimization (current O(n²), could be O(n log n) with spatial index)
- Parallel processing for scorers (currently sequential per property)

**Scope estimate:** 3-4 tasks (optional, depending on scaling needs)

**Why now:** As portfolio grows, current performance may not scale.

---

## 3. Phase 8: Integration & API

Connect the system to external underwriting, claims, and pricing workflows.

### 3.1 REST API Layer

**What's needed:**
- FastAPI/Flask wrapper exposing read endpoints
- Authentication (API keys, OAuth, etc.)
- Rate limiting per client
- Versioning strategy
- OpenAPI/Swagger documentation

**Key endpoints:**
- `GET /api/properties` — list properties with filters
- `GET /api/properties/{id}/assessments` — risk history
- `GET /api/properties/{id}/alerts` — related alerts
- `GET /api/portfolio/metrics` — portfolio summary
- `GET /api/hotspots?hazard_type=wildfire` — geographic clusters

**Scope estimate:** 4 tasks
- API framework setup (FastAPI)
- DAO endpoint wrappers
- Auth/rate limiting middleware
- Documentation & testing

**Why now:** External systems need to consume data; API is the standard interface.

### 3.2 Event Webhooks

**What's needed:**
- Webhook dispatcher for critical events
- Configurable targets and retry logic
- Event payload schema (consistent across alert types)
- Webhook testing & debugging tools

**Key events:**
- `property.critical_alert` — risk threshold breached
- `portfolio.threshold_breach` — accumulation threshold hit
- `property.risk_changed` — score changed significantly
- `assessment.completed` — batch scoring cycle done

**Scope estimate:** 3 tasks
- Event dispatcher architecture
- Webhook delivery with retries
- Testing tools

**Why now:** Downstream systems need real-time notifications, not polling.

### 3.3 Underwriting Integration

**Concrete scope:**
- Endpoint: `PATCH /api/properties/{id}/renewal_quote` → update underwriting system
- Payload includes: property_id, current_risk_score, premium_adjustment, recommended_action
- Integration points: renewal cycle trigger, pricing system callback

**Scope estimate:** 2 tasks (depends on underwriting system API)

### 3.4 Claims Integration

**Concrete scope:**
- Endpoint: `POST /api/claims/loss_prediction` → predict likelihood of loss
- Payload includes: property_id, historical_risk_scores, current_hazard_state
- Returns: loss probability estimate, recommended reserves

**Scope estimate:** 2 tasks

---

## 4. Phase 9: Advanced Features

Next-generation capabilities built on top of the foundation.

### 4.1 Predictive Analytics

**What's needed:**
- Time-series forecasting (ARIMA, Prophet, or neural net)
- Anomaly detection on hazard trends
- Property-level risk trajectory (improving? worsening?)
- Portfolio-level risk forecasting ("in 2 weeks, 10% more will be critical")

**Scope estimate:** 4-5 tasks (distinct from LLM layer)

**Why later:** Requires historical data & tuning; not as high-value as integration.

### 4.2 Advanced Mitigation Recommendations

**Current state:** LLM can suggest actions ("install fire breaks")  
**Enhancement:** Rank by ROI, integrate with community/state programs, track efficacy

**Scope estimate:** 3 tasks

### 4.3 Compliance & Audit

**What's needed:**
- Access control (role-based: admin, underwriter, broker, customer)
- Formal audit logging (who accessed what, when, why)
- Data retention policies
- GDPR/CCPA compliance

**Scope estimate:** 4-5 tasks

**Why later:** Depends on deployment target and regulatory requirements.

### 4.4 Mobile App

**What's needed:**
- Native or React Native app
- Simplified underwriter workflow
- Push notifications for critical alerts
- Offline mode for properties already loaded

**Scope estimate:** 8-10 tasks (significant new codebase)

**Why later:** Requires separate frontend infrastructure.

---

## 5. Known MVP Simplifications to Revisit

Flagged in the codebase as "correct and simple today, revisit if scale changes"  
(not bugs, but first candidates for optimization if performance complaints arise):

| Simplification | Where | Revisit Trigger |
|---|---|---|
| `RiskScoringEngine` fetches entire `hazard_data` table once per cycle, scans per property | `scoring_engine.py` | Portfolio or hazard data grows to thousands+ rows |
| `HotspotDetector` does O(n²) distance comparisons across assessed properties | `hotspot_detector.py` | Same scaling issue |
| `Monitor` re-queries assessment/alert state per property individually | `monitor.py` | Batch processing would reduce DB round-trips |
| Ingestion grid-cell size (0.5°) barely reduces API calls for geographically scattered portfolio | `ingestion_engine.py` | Wide geographic spread; consider region-based partitioning |
| No automated database backup implementation (config exists, code doesn't) | `config/settings.json` | **Critical for Phase 7 before production** |
| LLM explanation cache is file-based JSON (not indexed) | `src/llm/cache.py` | Cache size grows; consider SQLite or Redis |
| Static thresholds in scoring (distance_km, wind_speed_kmh) | Scorers | Real-world tuning needed based on regional loss data |

---

## 6. Deployment Roadmap

### MVP (Current - Local/Development)
- Single machine, SQLite database
- Monitoring loop as background Python process
- Streamlit UI on same machine
- Manual config via JSON

### Phase 7 Target (Production-Ready)
- Cloud VMs or containers (AWS EC2 / GCP Compute Engine)
- Managed database option (PostgreSQL) - SQLite still works for single-instance
- Automated backups
- Structured logging + metrics
- Health checks and alerting

### Phase 8+ (Enterprise Scale)
- Containerized services (Docker/Kubernetes)
- Load balancing for API
- Cache layer (Redis)
- CDN for static assets
- Managed database (RDS/Cloud SQL)
- Message queue (RabbitMQ/Kafka) for async tasks

---

## 7. Suggested Order of Attack (Phase 7+)

**Near-term (Phase 7 - Production Hardening):**
1. **Database backups** — Critical blocker for production. 2-3 tasks.
2. **Structured logging & metrics** — Ops visibility. 3-4 tasks.
3. **Config validation** — Fail loudly on bad settings. 1-2 tasks.
4. **Health check endpoint** — Simple status API. 1 task.

**Medium-term (Phase 8 - Integration):**
5. **REST API layer** — Expose data for external systems. 4 tasks.
6. **Event webhooks** — Real-time notifications. 3 tasks.
7. **Underwriting integration** — Production integration point. 2 tasks.
8. **Claims integration** — Loss prediction endpoint. 2 tasks.

**Later (Phase 9 - Advanced):**
9. **Predictive analytics** — Forecasting & anomaly detection. 4-5 tasks.
10. **Mobile app** — Native underwriter workflow. 8-10 tasks.
11. **Advanced compliance** — Audit, access control, retention. 4-5 tasks.

**Performance (Optional, as-needed):**
- Database query optimization & indexing
- Hotspot detection algorithm improvement (O(n²) → spatial index)
- Parallel risk scoring
- Caching layer for portfolio metrics

---

## Estimated Effort

| Phase | Tasks | Estimated Hours | Key Deliverable |
|-------|-------|-----------------|-----------------|
| **1-6 (Complete)** | 35 | ~200 | Full system backend + UI + LLM |
| **7 (Hardening)** | 7-8 | 30-40 | Production-ready infrastructure |
| **8 (Integration)** | 11 | 60-80 | External API + webhook support |
| **9 (Advanced)** | 15-20 | 100-150 | Forecasting + compliance + mobile |
| **Total Roadmap** | 68-83 | 390-470 | Enterprise insurance platform |

---

## Success Criteria by Phase

### Phase 6 (Just Completed) ✅
- [x] 35 tasks complete, all deliverables shipped
- [x] 559+ tests passing, 98%+ coverage
- [x] Dashboard works, chat agent deployed
- [x] Documentation comprehensive
- [x] All code in git, ready for sharing

### Phase 7 (Production Hardening) Target
- [ ] Automated backups working & tested
- [ ] Structured logs + metrics dashboard
- [ ] Health check API responds correctly
- [ ] Config validation catches errors early
- [ ] Runbook for common operational tasks

### Phase 8 (Integration) Target
- [ ] REST API deployed, documented (Swagger)
- [ ] Webhook delivery working with retries
- [ ] Real underwriting system consuming data
- [ ] Claims system using loss predictions
- [ ] Auth/rate limiting enforced

### Phase 9 (Advanced) Target
- [ ] Risk forecasts available (30-day ahead)
- [ ] Anomaly detection running
- [ ] Mobile app in beta
- [ ] Audit logging complete
- [ ] SOC 2 / compliance ready

---

## Decision Points for Prioritization

**Run Phase 7 ASAP if:**
- You're taking this to production soon
- You need ops visibility and monitoring
- Data loss would be catastrophic

**Run Phase 8 ASAP if:**
- External systems need to integrate
- Underwriting/claims already have APIs ready
- Webhooks are a blocking integration requirement

**Defer Phase 9 if:**
- You don't need forecasting yet
- Compliance isn't a driver
- Mobile is nice-to-have

---

## Related Documentation

**Architecture & Design:**
- [ARCHITECTURE_HIGH_LEVEL.md](ARCHITECTURE_HIGH_LEVEL.md) — System overview (NEW)
- [ARCHITECTURE_LOW_LEVEL.md](ARCHITECTURE_LOW_LEVEL.md) — Component details (NEW)
- [implementation-plan.md](implementation-plan.md) — Original design decisions
- [reference-principles.md](reference-principles.md) — Development principles

**Operations & Running:**
- [operations-guide.md](operations-guide.md) — Installation, running, troubleshooting
- [api-reference.md](api-reference.md) — All classes/methods
- [GIT_SETUP.md](GIT_SETUP.md) — Version control setup

**Completed Work:**
- [PHASE_1_UI_COMPLETION.md](PHASE_1_UI_COMPLETION.md) — Streamlit dashboard
- [PHASE_2_LLM_COMPLETION.md](PHASE_2_LLM_COMPLETION.md) — Claude integration
- [PHASE_3_COMPLETION.md](PHASE_3_COMPLETION.md) — Polish & testing
- [task-breakdown.md](task-breakdown.md) — All 35 tasks detail
