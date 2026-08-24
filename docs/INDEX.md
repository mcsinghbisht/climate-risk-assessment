# Documentation Index

Complete guide to all documentation for the Climate Risk Assessment project.

---

## Quick Navigation

### I'm New to the Project
Start with: **[../CLAUDE.md](../CLAUDE.md)** → **[reference-principles.md](reference-principles.md)** → **[task-breakdown.md](task-breakdown.md)**

### I Want to Run the System
Start with: **[operations-guide.md](operations-guide.md)** → **[api-reference.md](api-reference.md)**

### I Want to Extend the System
Start with: **[future-roadmap.md](future-roadmap.md)** → **[web-ui-llm-implementation-plan.md](web-ui-llm-implementation-plan.md)**

### I Want to Understand How It Was Built
Start with: **[PHASE_1_UI_COMPLETION.md](PHASE_1_UI_COMPLETION.md)** → **[PHASE_2_LLM_COMPLETION.md](PHASE_2_LLM_COMPLETION.md)** → **[PHASE_3_COMPLETION.md](PHASE_3_COMPLETION.md)**

---

## All Documentation Files

### Project Overview & Strategy

| File | Purpose | Audience |
|------|---------|----------|
| [../CLAUDE.md](../CLAUDE.md) | Project vision, architecture, and structure | Everyone |
| [reference-principles.md](reference-principles.md) | Design and development principles | Architects, Developers |
| [task-breakdown.md](task-breakdown.md) | All 35 tasks across 6 phases with status | Project Managers, Developers |
| [future-roadmap.md](future-roadmap.md) | What's next after Phase 3 | Product, Engineering Leads |

### Architecture & Design

| File | Purpose | Audience |
|------|---------|----------|
| [implementation-plan.md](implementation-plan.md) | Detailed backend system design (Phases 1-6) | Developers, Architects |
| [alert-lifecycle-design.md](alert-lifecycle-design.md) | Alert generation, thresholds, and lifecycle | Developers |
| [scaling-design.md](scaling-design.md) | Performance optimization and scaling | Architects, DevOps |

### Phase Implementation Summaries

**Phase 1: Backend Foundation (Tasks 1-6)**
- See: [task-breakdown.md](task-breakdown.md#phase-1-foundation-setup-tasks-16-completed)

**Phase 2: Data Ingestion (Tasks 7-14)**
- See: [task-breakdown.md](task-breakdown.md#phase-2-data-ingestion-tasks-714-completed)

**Phase 3: Risk Scoring (Tasks 15-19)**
- See: [task-breakdown.md](task-breakdown.md#phase-3-risk-scoring--monitoring-tasks-1519-completed)

**Phase 4: Alerts & Monitoring (Tasks 20-25)**
- See: [task-breakdown.md](task-breakdown.md#phase-4-alerts--monitoring-tasks-2025-completed)

**Phase 5: Portfolio Aggregation (Tasks 26-28)**
- See: [task-breakdown.md](task-breakdown.md#phase-5-portfolio-aggregation-tasks-2628-completed)

**Phase 6: Web UI & LLM (Tasks 29-35)** ← *You are here*
- [PHASE_1_UI_COMPLETION.md](PHASE_1_UI_COMPLETION.md) — UI foundation with Streamlit
- [PHASE_2_LLM_COMPLETION.md](PHASE_2_LLM_COMPLETION.md) — Claude integration & chat layer
- [PHASE_3_COMPLETION.md](PHASE_3_COMPLETION.md) — Caching, export, responsive design, testing

### User Guides & References

| File | Purpose | Audience |
|------|---------|----------|
| [operations-guide.md](operations-guide.md) | Installation, configuration, running, monitoring, troubleshooting | Operations, DevOps |
| [api-reference.md](api-reference.md) | Full class/function reference for all modules | Developers |
| [../UI_QUICKSTART.md](../UI_QUICKSTART.md) | Get the web dashboard running in 5 minutes | End Users, PMs |
| [responsive-design.md](responsive-design.md) | Mobile/tablet/desktop responsiveness & dark mode | Frontend Developers |

### Supplementary Docs

| File | Purpose | Audience |
|------|---------|----------|
| [../PROJECT_STRUCTURE.md](../PROJECT_STRUCTURE.md) | Directory structure and file organization | Developers |
| [DATABASE_USAGE_GUIDE.md](DATABASE_USAGE_GUIDE.md) | SQL queries, schema, and data access patterns | Developers |
| [DATABASE_TOOLS_SUMMARY.md](DATABASE_TOOLS_SUMMARY.md) | Summary of DAO classes and query helpers | Developers |
| [web-ui-llm-implementation-plan.md](web-ui-llm-implementation-plan.md) | Original implementation plan for Phase 6 (historical) | Reference |

---

## Reading Paths by Role

### Product Manager
1. [../CLAUDE.md](../CLAUDE.md) — Vision and problem statement
2. [task-breakdown.md](task-breakdown.md) — Task status and progress
3. [PHASE_1_UI_COMPLETION.md](PHASE_1_UI_COMPLETION.md) — What was built
4. [future-roadmap.md](future-roadmap.md) — What's next

### Backend Developer
1. [../CLAUDE.md](../CLAUDE.md) — Architecture overview
2. [reference-principles.md](reference-principles.md) — Design principles
3. [implementation-plan.md](implementation-plan.md) — System design
4. [api-reference.md](api-reference.md) — Classes and functions
5. [operations-guide.md](operations-guide.md) — Running and debugging

### Frontend Developer (UI/Dashboard)
1. [../CLAUDE.md](../CLAUDE.md) — Overview
2. [PHASE_1_UI_COMPLETION.md](PHASE_1_UI_COMPLETION.md) — UI architecture
3. [responsive-design.md](responsive-design.md) — Mobile/responsive design
4. [api-reference.md](api-reference.md#ui-modules) — UI component reference
5. [../UI_QUICKSTART.md](../UI_QUICKSTART.md) — Get it running

### LLM/Chat Developer
1. [../CLAUDE.md](../CLAUDE.md) — Overview
2. [PHASE_2_LLM_COMPLETION.md](PHASE_2_LLM_COMPLETION.md) — Chat agent architecture
3. [api-reference.md](api-reference.md#llm-modules) — LLM API reference
4. [operations-guide.md](operations-guide.md) — Configuration and environment

### DevOps / Operations
1. [operations-guide.md](operations-guide.md) — Installation, configuration, monitoring
2. [scaling-design.md](scaling-design.md) — Performance and scaling
3. [alert-lifecycle-design.md](alert-lifecycle-design.md) — Understanding alerts
4. [api-reference.md](api-reference.md) — API reference for integrations

### New Contributor
1. [../CLAUDE.md](../CLAUDE.md) — Start here
2. [reference-principles.md](reference-principles.md) — Development principles
3. [../PROJECT_STRUCTURE.md](../PROJECT_STRUCTURE.md) — File organization
4. [operations-guide.md](operations-guide.md) — Setting up your environment
5. [task-breakdown.md](task-breakdown.md) — Find a task to work on

---

## File Organization

```
docs/
├── INDEX.md                                 # You are here
├── CLAUDE.md                                # Back in root (project instructions)
├── README.md                                # Back in root
│
├── Project Overview & Strategy
│   ├── reference-principles.md              # Design principles
│   ├── task-breakdown.md                    # All 35 tasks (Phases 1-6)
│   ├── future-roadmap.md                    # Post-Phase 3 roadmap
│   └── implementation-plan.md               # Backend system design
│
├── Phase Completion Summaries
│   ├── PHASE_1_UI_COMPLETION.md             # Streamlit UI foundation
│   ├── PHASE_2_LLM_COMPLETION.md            # Claude integration
│   └── PHASE_3_COMPLETION.md                # Polish & optimization
│
├── Architecture & Design
│   ├── alert-lifecycle-design.md            # Alert generation and lifecycle
│   ├── scaling-design.md                    # Performance and scaling
│   └── web-ui-llm-implementation-plan.md    # Original Phase 6 plan (historical)
│
├── User Guides & References
│   ├── operations-guide.md                  # Installation, configuration, running
│   ├── api-reference.md                     # Class/function reference
│   ├── responsive-design.md                 # Mobile/responsive design
│   ├── DATABASE_USAGE_GUIDE.md              # SQL and data access
│   └── DATABASE_TOOLS_SUMMARY.md            # DAO class summary
│
└── Back in Root
    ├── UI_QUICKSTART.md                     # Get dashboard running (5 min)
    └── PROJECT_STRUCTURE.md                 # Directory structure
```

---

## How to Contribute

1. Read [reference-principles.md](reference-principles.md) — Understand our design approach
2. Browse [task-breakdown.md](task-breakdown.md) — Find an incomplete task
3. Check [operations-guide.md](operations-guide.md) — Set up your environment
4. Reference [api-reference.md](api-reference.md) — Understand existing code
5. Make your changes following the design principles
6. Run tests and verify with [operations-guide.md#Testing](operations-guide.md#testing)

---

## Key Concepts

**Phases:**
- **Phase 1-5:** Backend system (data ingestion, risk scoring, alerts, portfolio management)
- **Phase 6:** Web UI and LLM integration (split across Phase_1/2/3 completion docs)

**Architecture:**
- **Backend:** Continuous monitoring loop, real-time hazard data ingestion, risk scoring
- **Frontend:** Streamlit multi-page dashboard (Portfolio Manager & Underwriter roles)
- **LLM Layer:** Claude-powered Q&A with tool use over 8 curated DAO methods
- **Storage:** SQLite database with Data Access Objects (DAOs) for all queries

**Data Flow:**
```
Real-time Hazard Data 
  → Data Ingestion Layer 
  → Risk Scoring Engine 
  → Continuous Monitoring 
  → Alert System 
  → SQLite Database
  → Web Dashboard & Chat Agent
```

---

## Support & Issues

For questions or issues:
1. Search existing documentation using `Ctrl+F`
2. Check [operations-guide.md#Troubleshooting](operations-guide.md#troubleshooting)
3. Review [task-breakdown.md](task-breakdown.md) for context on what was built
4. Refer to [api-reference.md](api-reference.md) for class/method details
