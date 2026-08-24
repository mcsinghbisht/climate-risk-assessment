# Climate Risk Assessment - Continuous Monitoring Data Product

## Project Vision

Build an **AI-powered geospatial risk monitoring agent** that continuously assesses wildfire and flood exposure for insured properties, enabling:
- Dynamic underwriting based on real-time risk changes
- Portfolio-level risk visibility and accumulation tracking
- Proactive early warnings and mitigation recommendations
- Integration with underwriting, claims, and pricing workflows

**Shift from:** Risk assessment at policy inception only  
**Shift to:** Continuous monitoring with environmental change detection and dynamic risk updates

---

## Industry Problem Statement

Current insurance industry limitations:
1. **Static Risk Assessment** — Risk evaluated once at underwriting, never updated
2. **Outdated Hazard Data** — Static maps that don't reflect real-time environmental changes
3. **Lack of Visibility** — No real-time exposure visibility across portfolio
4. **Catastrophic Losses** — CAT losses occur due to poor accumulation tracking and risk clustering
5. **Reactive Approach** — Limited early warning capabilities for customers and underwriters

---

## Solution Architecture

### Core Components

#### 1. Data Ingestion Layer
- **Property & Exposure Data**
  - Geo-coordinates and addresses of insured properties
  - Property attributes (construction, year built, etc.)
  
- **Real-Time Hazard Data (Wildfire)**
  - Satellite imagery and burn patterns
  - Wind speed and direction
  - Temperature and humidity levels
  - Fire spread probability models
  
- **Real-Time Hazard Data (Flood)**
  - Rainfall intensity and accumulation trends
  - Soil moisture levels
  - Storm tracking data
  - Floodplain maps and historical flood data
  - River gauge levels and drainage patterns

#### 2. Risk Scoring & Modeling Engine
- Dynamic risk scoring based on:
  - Proximity to active/predicted wildfires
  - Fire spread probability and wind-driven escalation
  - Rainfall accumulation trends
  - Flood probability based on drainage, soil saturation
  - Historical hazard patterns and seasonal trends

#### 3. Continuous Monitoring & Detection
- Environmental change detection system
- Trigger mechanisms for risk threshold breaches
- Real-time event tracking (fire growth, rainfall spikes, etc.)

#### 4. Alerts & Intervention System
- Notifications to underwriters, brokers, insurers, reinsurers
- Risk escalation workflows
- Proactive mitigation recommendations

#### 5. Portfolio Management
- Hotspot detection and geographic clustering
- Scenario simulation for catastrophe planning
- Accumulation monitoring and aggregated exposure analysis

#### 6. Integration Points
- Underwriting system integration for renewal repricing
- Claims integration for loss prediction
- Broker/customer notification channels

---

## Project Structure

```
Climate_Risk_Assessment/
├── src/
│   ├── data_ingestion/          # Property and hazard data ingestion
│   ├── risk_scoring/             # Risk calculation and modeling
│   ├── continuous_monitoring/    # Real-time monitoring engine
│   ├── alerts/                   # Alert and notification system
│   ├── portfolio/                # Portfolio aggregation and analysis
│   └── integrations/             # External system integrations
├── data/                         # Sample datasets and configurations
├── docs/
│   ├── reference-principles.md   # Design and development principles
│   ├── architecture.md           # System architecture documentation
│   ├── data-sources.md           # Hazard data source specifications
│   └── api-specs.md              # API endpoint documentation
├── tests/                        # Unit and integration tests
├── scripts/                      # Utility and setup scripts
├── config/                       # Configuration files and environment setup
└── .claude/                      # Claude Code settings
```

---

## Development Phases

**See [docs/task-breakdown.md](docs/task-breakdown.md) for 34 small, verifiable tasks organized by phase.**

- **Phase 1 (6 tasks):** Foundation setup — project structure, DB schema, configuration
- **Phase 2 (8 tasks):** Data ingestion — properties, wildfire, weather, flood APIs
- **Phase 3 (5 tasks):** Risk scoring — wildfire/flood algorithms, aggregation, storage
- **Phase 4 (6 tasks):** Alerts & monitoring — thresholds, notifications, persistence/lifecycle, continuous loop
- **Phase 5 (3 tasks):** Portfolio aggregation — metrics, hotspots, reporting
- **Phase 6 (7 tasks):** Testing & documentation — unit/integration tests, guides, performance

**Total: 35 tasks, ~32-37 hours solo development, each task verifiable**

---

## Technology Stack (TBD)

*To be determined based on implementation requirements*

---

## Key References

See [docs/reference-principles.md](docs/reference-principles.md) for design principles and development guidelines.

All 35 tasks (Phases 1-6) are complete. See [docs/future-roadmap.md](docs/future-roadmap.md)
for what's next - the LLM layer, web UI, and underwriting/claims integration
work referenced throughout this doc are deliberately deferred and scoped there.

---

## Claude Code Workflow

- `/help` — Claude Code features and commands
- `/code-review` — Code quality and best practice reviews
- `/run` — Execute and test the application
- `/verify` — End-to-end verification of changes
