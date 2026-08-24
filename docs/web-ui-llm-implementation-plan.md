# Web UI & LLM Layer Implementation Plan

**Document Version:** 1.0  
**Created:** 2026-08-11  
**Status:** Planning (ready to execute)  
**Target Personas:** Portfolio Manager, Underwriter  

---

## Executive Summary

This plan details the implementation of a web-based dashboard and LLM-powered query layer for the Climate Risk Assessment system. The UI will provide two specialized views for Portfolio Managers (portfolio-wide oversight) and Underwriters (property-level decision support), backed by a sophisticated LLM chat interface that combines curated, tested database queries with a safe, read-only SQL fallback for novel questions.

**Timeline estimate:** 3-4 weeks solo development, phased delivery (dashboard MVP first, LLM layer second).

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Phase 1: Web UI Foundation](#phase-1-web-ui-foundation)
3. [Phase 2: LLM Query Layer](#phase-2-llm-query-layer)
4. [Phase 3: Integration & Polish](#phase-3-integration--polish)
5. [Implementation Details](#implementation-details)
6. [Testing Strategy](#testing-strategy)
7. [Known Dependencies & Blockers](#known-dependencies--blockers)

---

## Architecture Overview

### High-Level System Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    Web Application (Streamlit)              │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────────┐  ┌──────────────────┐                │
│  │ Portfolio Manager │  │   Underwriter    │                │
│  │    Dashboard     │  │   Workspace      │                │
│  └────────┬─────────┘  └────────┬─────────┘                │
│           │                     │                           │
│           └──────────┬──────────┘                           │
│                      │                                      │
│              ┌───────▼────────┐                            │
│              │  LLM Chat      │ ◄──── Claude API           │
│              │  Interface     │                            │
│              └───────┬────────┘                            │
│                      │                                      │
│         ┌────────────┴────────────┐                        │
│         │                         │                        │
│    ┌────▼─────┐          ┌───────▼────┐                   │
│    │ Curated  │          │  Guarded    │                   │
│    │ Tools    │          │ SQL Query   │                   │
│    │ (DAO     │          │ Validator   │                   │
│    │ methods) │          │ & Executor  │                   │
│    └────┬─────┘          └───────┬────┘                   │
│         │                        │                        │
│         └────────────┬───────────┘                        │
│                      │                                     │
│         ┌────────────▼─────────────┐                      │
│         │   SQLite Database        │                      │
│         │  (climate_risk.db)       │                      │
│         └─────────────────────────┘                      │
│                                                            │
└─────────────────────────────────────────────────────────────┘
```

### Key Design Principles

- **Separation of concerns:** Web UI reads from DAOs; backend ingestion/scoring runs independently
- **Two-tier LLM access:** Curated tools for expected queries, guarded SQL for novel ones
- **No write access via UI:** All mutations only via tested CLI or direct code
- **Live database reads:** No caching except for performance-critical aggregations
- **Graceful degradation:** LLM failures never break the dashboard; template/fallback text fills in

---

## Phase 1: Web UI Foundation

### Step 1: Set up Streamlit project structure

**Description:** Create a minimal Streamlit app with basic page routing and state management.

**Files to create:**
- `app.py` — Streamlit app entry point with page router
- `src/ui/` — new directory for UI-specific code
  - `src/ui/config.py` — UI configuration (page names, refresh intervals, color scheme)
  - `src/ui/pages/` — directory for Streamlit pages

**Dependencies to add:** `streamlit>=1.28.0`, `streamlit-folium>=0.13.0` (for map), `plotly>=5.17.0` (for charts)

**Key decisions:**
- Use Streamlit's multi-page feature (pages/ directory) for clean separation of Portfolio Manager and Underwriter views
- Implement session state for selected property (persists across page navigation)
- Configuration-driven refresh rates (default 30s, user-adjustable via dropdown)

---

### Step 2: Build Portfolio Manager dashboard

**Description:** Implement the complete read-only overview page for portfolio-wide risk visibility.

**Components to build:**

**2.1 — KPI strip (top of page)**
- Total properties
- Assessed properties
- % in high/critical risk
- Active alert count (general)
- Portfolio-level alert (specially highlighted if active)
- Latest assessment freshness (minutes ago, red if >30 min stale)

**Implementation:**
- Call `PortfolioAggregator.get_portfolio_metrics()` once per refresh
- Call `AlertDAO.get_active_alerts()` and filter `property_id IS NULL` for portfolio alerts
- Display with Streamlit's `st.metric()` widgets, color-coded by value

**2.2 — Risk distribution chart**
- Pie or donut chart: low/medium/high/critical percentages
- Clickable slices that filter the property table below

**Implementation:**
- Use Plotly Express pie chart
- On-click, set session state `selected_risk_level` and re-run to filter

**2.3 — Geographic distribution table**
- By state: property count, avg risk score, highest risk level present

**Implementation:**
- Query from `PortfolioAggregator.get_portfolio_metrics()` → `state_distribution` field (if it already exists; if not, add it in Step 2.4)
- Display as Streamlit table, sortable

**2.4 — The Map (with hotspots)**
- Continental US, zoomed to fit all properties
- Three layers (all toggleable):
  - **Property markers:** individual properties, colored by risk level (green/yellow/orange/red)
  - **Wildfire hotspots:** circles, pale orange → deep red by avg_risk
  - **Flood hotspots:** circles, pale blue → deep indigo by avg_risk
- Clicking a property marker shows a mini-card and opens the underwriter view for that property
- Clicking a hotspot circle filters the property table to just that cluster

**Implementation:**
- Use `folium` for the base map, `streamlit-folium` to embed it
- Layer 1 (properties): read from `PropertyDAO.get_all_properties()` + latest `RiskDAO.get_latest_assessment()` per property
- Layers 2 & 3 (hotspots): **REQUIRES Step 2.5 backend work below**
- Use folium's `FeatureGroup` and `LayerControl` for toggles
- Use folium callbacks or session state to handle clicks

**2.5 — BACKEND WORK: Hotspot detection by hazard type**

Currently `HotspotDetector.detect_hotspots()` clusters only on `overall_risk_score`. We need to:
- Add a `hazard_type` parameter (optional, default "overall")
- When `hazard_type="wildfire"`, cluster on `wildfire_risk_score` instead
- When `hazard_type="flood"`, cluster on `flood_risk_score` instead
- Returns same structure but clusters reflect the specific hazard's risk distribution

**File to modify:** `src/portfolio/hotspot_detector.py`

**Implementation:**
```python
def detect_hotspots(self, hazard_type: str = "overall") -> List[Dict]:
    """
    hazard_type: "overall", "wildfire", or "flood"
    Clusters properties by the specified risk score type.
    """
    # existing logic, but use the right score field based on hazard_type
```

**2.6 — Active alerts table**
- `AlertDAO.get_active_alerts()`, displayed as a sortable table
- Columns: property_id, risk_type (wildfire/flood/portfolio), risk_level, triggered_at, status
- Portfolio-level alerts pinned to top and highlighted
- Clicking a row navigates to that property's underwriter view (or portfolio view if it's a portfolio alert)

**Implementation:**
- Streamlit table with `st.dataframe()`
- Use `column_config` for date formatting, status color coding
- `on_click` on row to update session state and rerun

---

### Step 3: Build Underwriter workspace

**Description:** Implement the property drill-down view for single-property decision support.

**Entry points:**
- Clicking a property marker on the map
- Searching for a property by ID or address
- From the active alerts list

**Components:**

**3.1 — Property search / selector**
- Dropdown or text input to find a property by ID or address
- Autocomplete as you type (use `streamlit-select` or plain autocomplete)

**Implementation:**
- `PropertyDAO.get_all_properties()` once at app load, cache in session state
- Filter on each keystroke with Python `str.lower().startswith()`

**3.2 — Property details card**
- Address, coordinates, state, county, construction type, elevation
- WUI and floodplain flags prominently shown
- Currently assessed risk levels and scores (wildfire, flood, overall)
- Risk level color-coded prominently

**Implementation:**
- `PropertyDAO.get_property_by_id()` + `RiskDAO.get_latest_assessment(property_id)`
- Use Streamlit columns for a card layout

**3.3 — Factor breakdown visualization**
- For wildfire and flood, show the four factors (proximity, wind/rainfall, intensity/saturation, environment) as a radar/spider chart
- The values come from the latest assessment's `wildfire_factors` and `flood_factors` dicts

**Implementation:**
- Use Plotly `go.Scatterpolar()` for radar charts
- Extract factor values from latest assessment

**3.4 — Risk explanation text**
- Show the LLM-generated explanation (if available from Priority 2)
- Fallback to the template-generated `explanation` string from the scorer

**Implementation:**
- `RiskDAO.get_latest_assessment()` includes `wildfire_explanation` and `flood_explanation`
- Display in Markdown

**3.5 — Risk history trend**
- Line chart of overall risk score over time (last N assessments, configurable, default 10)
- Annotations for alert fires (triangles on the line when alert triggered)
- X-axis: assessment timestamp

**Implementation:**
- `RiskDAO.get_assessment_history(property_id)` returns list of assessments
- Use Plotly line chart with `add_trace()` for alert annotations

**3.6 — What changed since last assessment**
- If `ChangeDetector` flagged `changed=True`, display:
  - Which factors changed and by how much
  - Whether this change triggered an alert

**Implementation:**
- Store `change_summary` in `alert_history` when an alert fires (or compute on-demand)
- Display as a bullet-point list or small table

**3.7 — Active alerts for this property**
- Table: risk_type (wildfire/flood), risk_level, triggered_at, current_status, action_taken_at (if acknowledged)
- Action column: "acknowledge" button → `AlertDAO.acknowledge_alert()` → refresh

**Implementation:**
- `AlertDAO.get_alerts_for_property(property_id)` (new DAO method, see Step 3.8)
- Button click calls `acknowledge_alert()`, updates `status` to "acknowledged", re-renders

**3.8 — BACKEND WORK: New DAO methods for property-level queries**

Add to `src/database/alert_dao.py`:
```python
def get_alerts_for_property(self, property_id: int) -> List[Dict]:
    """All alerts (active/acknowledged/resolved/stale) for a single property."""
    # query: WHERE property_id = ? ORDER BY triggered_at DESC

def acknowledge_alert(self, alert_id: int) -> bool:
    """Mark an alert as acknowledged by the user."""
    # UPDATE alerts SET status='acknowledged', action_taken_at=NOW() WHERE id=alert_id
    # Return success/failure
```

Add to `src/database/risk_dao.py`:
```python
def get_nearby_hazards(self, latitude: float, longitude: float, radius_km: float = 20) -> List[Dict]:
    """
    Return all hazard_data records within radius_km of the given coordinates.
    Used to show "what's near this property right now" on the underwriter view.
    """
    # Query hazard_data with distance calculation
```

---

### Step 4: System health widget

**Description:** Display monitoring cycle status and data freshness on every page.

**What to show:**
- Last completed cycle: timestamp and duration
- Per-source status: ✓ (got data) or ⚠ (0 records ingested) or ✗ (error) for NASA FIRMS, OpenWeatherMap, USGS
- Error count in last 10 cycles
- DB size (curiosity item, not critical)

**Implementation:**
- Add a `get_system_health()` method to `PortfolioAggregator` or create new `SystemHealthDAO`
- Query `alert_history` for errors in the last 10 assessments (counts of "ingestion error", "scoring error", etc.)
- Display in a collapsible `st.expander()` in the sidebar or footer on every page

---

### Step 5: Role selection & layout

**Description:** Simple, loginless role toggle so both personas can use the same app.

**Implementation:**
- Sidebar radio button: "Portfolio Manager" (default) or "Underwriter"
- Using Streamlit's `st.session_state`, persist the choice
- Show the appropriate page based on selection
- In Underwriter mode, show the property search at the top of every page for quick switching

---

## Phase 2: LLM Query Layer

### Step 6: Curated tool set

**Description:** Build a fixed set of well-tested, safe database query tools for the LLM.

**Tools to implement** (as Python functions in `src/llm/tools.py`):

1. `get_portfolio_metrics()` — return the KPI strip data
2. `get_hotspots(hazard_type: str = "overall")` — return wildfire/flood/overall hotspots
3. `get_active_alerts()` — return all active alerts
4. `get_alerts_for_property(property_id: int)` — return a property's alert history
5. `get_property_risk_history(property_id: int, limit: int = 10)` — return last N assessments
6. `get_properties_by_state(state_code: str)` — return all properties in a state
7. `get_properties_by_risk_level(risk_level: str)` — return all properties in high/critical
8. `get_assessment_history(property_id: int)` — same as get_property_risk_history, different name for clarity
9. `search_property_by_id_or_address(query: str)` — fuzzy-search properties
10. `get_nearby_hazards(latitude: float, longitude: float, radius_km: float = 20)` — hazards near a location

**Implementation:**
- Each tool is a Python function that calls the appropriate DAO method
- All return structured JSON (dicts), never raw DB rows
- All are decorated with `@tool` (or equivalent) so the LLM can discover them
- Implemented using Anthropic's `tool_use` feature in the Messages API

**Testing:**
- Unit test each tool independently
- Integration test with a real Claude API call to ensure the LLM actually calls them

---

### Step 7: Guarded SQL fallback

**Description:** For novel questions the curated tools don't cover, allow the LLM to generate SELECT queries safely.

**Architecture:**

The LLM has a second-tier tool: `query_database(sql_query: str) -> List[Dict]`

Before executing, validate:
1. Parse with `sqlparse`; reject if not a SELECT statement
2. Check the AST for forbidden keywords (DROP, ALTER, INSERT, UPDATE, DELETE, etc.)
3. Set execution timeout to 30 seconds
4. Limit result set to 1000 rows
5. Open a read-only connection to the database before execution
6. Log the query and its source (which user/property context triggered it)

**Implementation:** `src/llm/sql_executor.py`

```python
class SafeSQLExecutor:
    def __init__(self, db_path: str, max_rows: int = 1000, timeout_seconds: int = 30):
        ...
    
    def execute(self, sql_query: str) -> Tuple[List[Dict], Optional[str]]:
        """
        Returns (results, error_message).
        If error_message is not None, results will be [].
        """
        # 1. Validate it's a SELECT
        # 2. Check for forbidden keywords
        # 3. Set timeout
        # 4. Open read-only connection
        # 5. Execute
        # 6. Return results limited to max_rows
        # 7. Log query
```

**Shown to user:** After the LLM runs a query, display the query text in a collapsible code block, so the user can verify what was actually asked.

---

### Step 8: LLM chat interface

**Description:** Streamlit UI for the chat, grounded by context based on current view.

**Components:**

**8.1 — Context-aware system prompt**

Portfolio Manager view:
```
You are a climate risk assistant analyzing insurance portfolios. You have access to 
tools that query property risk assessments, active alerts, and geographic hotspots.
Answer questions about portfolio exposure, accumulation risk, and geographic clusters.
Always cite the specific numbers and dates from your query results.
```

Underwriter view (when a property is selected):
```
You are a climate risk assistant supporting property underwriting decisions. You have 
access to detailed risk assessments for a specific property, its risk history, nearby 
hazards, and similar properties.

Current property: [ID, address, state]
Current risk: [wildfire score, flood score, overall score, risk level]

Answer questions about this property's risk drivers, what's changed recently, and 
mitigation considerations. When relevant, compare to state/national benchmarks.
```

**8.2 — Chat message interface**
- `st.chat_input()` for user questions
- Display chat history (user messages in blue, assistant in gray)
- Loading spinner while LLM responds
- Error states (API unavailable, query failed) show gracefully with fallback text

**8.3 — Tool use visualization**
- When the LLM calls a tool, show which one: "🔍 Fetching portfolio metrics..."
- After the tool returns, show the result in a collapsible expandable

**8.4 — Generated SQL visibility**
- If the LLM uses the `query_database` tool, show the query in a collapsible `st.code()` block below the answer

**Implementation:**
- Use Anthropic SDK's Messages API with `tool_use` blocks
- Implement a simple agentic loop: send message → parse tool_use → call tool → send result back → repeat until text response
- See `src/llm/chat_agent.py` (new file)

---

### Step 9: LLM configuration & deployment

**Description:** Wire up API keys, model selection, and enable/disable flags.

**Add to `config/settings.json`:**
```json
{
  "llm": {
    "enabled": true,
    "provider": "anthropic",
    "model": "claude-3-5-sonnet-20241022",
    "api_key_env": "ANTHROPIC_API_KEY",
    "temperature": 0.7,
    "max_tokens": 1024,
    "curated_tools_only": false,
    "sql_fallback_enabled": true,
    "sql_timeout_seconds": 30,
    "sql_max_rows": 1000,
    "cache_explanations": true
  }
}
```

**In `.env.example`:**
```
ANTHROPIC_API_KEY=your_key_here
```

**Key safeguards:**
- LLM disabled by default in development (set `enabled: false` locally)
- `curated_tools_only: true` in production MVP (SQL fallback off until audited)
- All API keys redacted from logs (same pattern as Task 11)
- Each LLM call logged with timestamp, user context, tokens used, cost

---

## Phase 3: Integration & Polish

### Step 10: Caching & performance optimization

**Description:** Cache expensive queries that don't change frequently between refreshes.

**What to cache:**
- `PropertyDAO.get_all_properties()` — doesn't change mid-session, only between ingestion cycles
- `PortfolioAggregator.get_portfolio_metrics()` — changes every cycle, but don't re-query multiple times within a 5-second window
- Hotspot detection — same

**Implementation:**
- Use Streamlit's `@st.cache_data()` decorator with `ttl=60` (cache for 60 seconds)
- Add a "Refresh now" button to force-clear cache without restarting the app
- Log cache hits/misses in debug mode

---

### Step 11: Export & reporting

**Description:** Allow users to download filtered views as CSV or PDF.

**What to export:**
- Current portfolio table (all properties or filtered by risk level/state)
- Alert history for a specific property
- The current chart snapshots (portfolio distribution pie chart, risk trend line chart)

**Implementation:**
- Use `streamlit-download-button` or native Streamlit buttons with CSV generation
- For PDF: use `reportlab` or `fpdf2` to generate a styled report with charts, export link in Streamlit

---

### Step 12: Responsive design & dark mode

**Description:** Ensure the app is usable on mobile and respects the user's system theme.

**Implementation:**
- Streamlit's built-in responsive layout (uses flexbox)
- Test on mobile browsers (Chrome DevTools device emulation)
- Streamlit supports dark/light mode via `config.toml`; make sure colors chosen in Step 2 and 3 work in both

---

### Step 13: Testing & QA

**Description:** Comprehensive test coverage for the UI layer.

See [Testing Strategy](#testing-strategy) below for details.

---

## Implementation Details

### New Backend Methods Required

**In `src/database/alert_dao.py`:**
- `get_alerts_for_property(property_id: int) -> List[Dict]`
- `acknowledge_alert(alert_id: int) -> bool`

**In `src/database/risk_dao.py`:**
- `get_nearby_hazards(latitude: float, longitude: float, radius_km: float) -> List[Dict]`

**In `src/portfolio/hotspot_detector.py`:**
- Add `hazard_type` parameter to `detect_hotspots(hazard_type: str = "overall")`

**In `src/portfolio/aggregator.py` (optional, for convenience):**
- Add `get_system_health()` → health summary (last cycle, errors, per-source status)

### New Files to Create

```
src/
├── ui/
│   ├── __init__.py
│   ├── config.py                    # UI constants (colors, refresh rates, etc.)
│   ├── components.py                # Reusable Streamlit components
│   └── pages/
│       ├── portfolio_manager.py    # Portfolio Manager dashboard
│       └── underwriter.py          # Underwriter workspace
├── llm/
│   ├── __init__.py
│   ├── tools.py                    # Curated LLM tools (tool definitions & implementations)
│   ├── sql_executor.py             # Safe SQL execution with validation
│   └── chat_agent.py               # Chat interface & agentic loop
│
app.py                               # Streamlit entry point (top level)
requirements-ui.txt                  # Additional dependencies (streamlit, plotly, folium, etc.)
```

### File Structure on Disk

```
Climate_Risk_Assessment/
├── app.py                          # NEW: Streamlit app entry point
├── requirements-ui.txt             # NEW: UI/LLM dependencies
├── src/
│   ├── ui/                         # NEW
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── components.py
│   │   └── pages/
│   │       ├── portfolio_manager.py
│   │       └── underwriter.py
│   ├── llm/                        # NEW
│   │   ├── __init__.py
│   │   ├── tools.py
│   │   ├── sql_executor.py
│   │   └── chat_agent.py
│   ├── database/
│   │   ├── alert_dao.py            # MODIFIED: add get_alerts_for_property, acknowledge_alert
│   │   └── risk_dao.py             # MODIFIED: add get_nearby_hazards
│   ├── portfolio/
│   │   ├── hotspot_detector.py     # MODIFIED: add hazard_type parameter
│   │   └── aggregator.py           # MODIFIED: add get_system_health (optional)
│   ├── config/
│   │   └── settings.json           # MODIFIED: add [llm] section
│   └── ... (existing)
├── config/
│   ├── settings.json               # MODIFIED: add [llm] section
│   └── ... (existing)
├── .env.example                    # MODIFIED: add ANTHROPIC_API_KEY
└── docs/
    └── web-ui-llm-implementation-plan.md  # THIS FILE
```

---

## Testing Strategy

### Unit Tests

**For Curated Tools** (`tests/test_llm_tools.py`):
- Test each tool function independently with a temp database
- Mock the DAOs if needed
- Verify return shape (JSON-serializable dicts)

**For SQL Executor** (`tests/test_sql_executor.py`):
- Test valid SELECT queries (should execute)
- Test forbidden keywords (should reject)
- Test large result sets (should cap at max_rows)
- Test malformed SQL (should error gracefully)

**For New DAO Methods** (`tests/test_alert_dao_pytest.py`, `tests/test_risk_dao_pytest.py`):
- `get_alerts_for_property()` — returns correct alerts for a given property
- `acknowledge_alert()` — updates status and action_taken_at timestamp
- `get_nearby_hazards()` — returns hazards within radius_km, excludes those outside

### Integration Tests

**For LLM Chat Agent** (`tests/test_llm_chat_agent.py`):
- Mock Anthropic API (using responses library or similar)
- Send a test message, verify tool_use blocks are parsed correctly
- Test tool execution flow: user message → LLM calls tool → executor returns result → LLM sends final answer

**For UI Components** (`tests/test_ui_components.py`):
- Use Streamlit's testing framework (`streamlit.testing.v1`)
- Load each page (portfolio_manager, underwriter) with mock data
- Verify key components render (KPI strip, map, charts, tables)
- Simulate user interactions (button clicks, dropdown selections)

### End-to-End Tests

**Scenario tests** (`tests/test_e2e_ui_llm.py`):
- Scenario 1: Portfolio Manager views portfolio, asks "which states have the most critical properties", LLM uses curated tools to answer
- Scenario 2: Underwriter selects a property, asks "why did the risk go up", LLM uses property history to answer
- Scenario 3: User asks a novel question not covered by curated tools, LLM uses SQL fallback safely

### Performance Tests

**For LLM chat latency** (not strict time limits, but baseline):
- Measure time from user message to LLM response (goal: <5 sec with API latency)
- Measure time for tool execution (goal: <1 sec per tool call)

---

## Known Dependencies & Blockers

### Hard Dependencies

1. **Anthropic API Key** — required to run the LLM layer
   - Get one free at https://console.anthropic.com
   - Set in `.env` as `ANTHROPIC_API_KEY`

2. **Python packages:**
   - `streamlit>=1.28.0`
   - `streamlit-folium>=0.13.0`
   - `plotly>=5.17.0`
   - `folium>=0.14.0` (for map)
   - `sqlparse>=0.4.4` (for SQL validation)
   - `anthropic>=0.15.0` (for Claude API)

3. **Backend methods** (listed above) must be implemented before UI can call them

### Soft Dependencies / Nice-to-Haves

- `streamlit-select` — for autocomplete property search (optional, can use simpler dropdown)
- `reportlab` or `fpdf2` — for PDF export (optional, CSV export is sufficient for MVP)

### Known Risks / Mitigations

| Risk | Mitigation |
|------|-----------|
| LLM generates invalid or harmful SQL | Use `sqlparse` to validate; limit to SELECT only; read-only DB connection; log all queries |
| LLM hallucinations (confident wrong answers) | Always show the query/tool used and raw data in collapsible blocks; user can verify |
| High latency (LLM API + DB queries) | Cache aggressively; use curated tools in the happy path; show loading state |
| Database changes while UI is reading | SQLite handles concurrent readers well; accept that a multi-second read might see data from different cycles |
| User privacy / data exposure in logs | Redact API keys (existing pattern); sanitize SQL queries before logging if they contain sensitive values |

---

## Deployment Considerations

### Local Development

```bash
# Install UI dependencies
pip install -r requirements-ui.txt

# Run the Streamlit app
streamlit run app.py

# App opens at http://localhost:8501
```

### Production Deployment

**Option 1: Streamlit Cloud** (easiest)
- Push code to GitHub
- Connect to Streamlit Cloud (https://share.streamlit.io/)
- Set secrets in `.streamlit/secrets.toml` on the cloud dashboard

**Option 2: Self-hosted**
- Run `streamlit run app.py --server.port 8501 --server.address 0.0.0.0` on a server
- Put behind a reverse proxy (nginx) for HTTPS and load balancing
- Set environment variables for API keys (don't commit them)

**Option 3: Containerized**
- Create `Dockerfile` with Streamlit + dependencies
- Deploy to Docker Hub or Kubernetes

---

## Rollout Plan

### MVP Delivery

**Week 1:**
- Steps 1-2: Streamlit setup + Portfolio Manager dashboard
- Step 4: System health widget
- Deploy to Streamlit Cloud

**Week 2:**
- Steps 3, 5: Underwriter workspace + role selection
- Backend methods (Step 3.8)
- Deploy

**Week 3:**
- Steps 6-8: LLM curated tools + guarded SQL + chat interface
- Step 9: Configuration
- Deploy

**Week 4:**
- Steps 10-12: Caching, export, polish
- Step 13: Testing & QA
- Production release

---

## Success Criteria

- [ ] Portfolio Manager can view portfolio KPIs, risk distribution, and hotspots on a map
- [ ] Underwriter can search a property and see its risk factors, history, and active alerts
- [ ] Portfolio Manager can chat with LLM: "Which states have the most critical properties?" and get an accurate answer
- [ ] Underwriter can chat with LLM: "Why did this property's risk increase?" and get explanation
- [ ] All LLM queries (tool calls and generated SQL) are logged and visible to the user
- [ ] The UI gracefully handles missing data (fresh database, no assessments yet)
- [ ] The UI works on desktop (1920x1080) and mobile (375x667)
- [ ] Test coverage >80% for UI components and LLM tools
- [ ] Load testing: chat response <5 sec, page load <2 sec (with ~100 properties)

---

## References

- [future-roadmap.md](future-roadmap.md) — broader vision and priorities
- [operations-guide.md](operations-guide.md) — how the backend system runs
- [api-reference.md](api-reference.md) — available DAO methods
- [alert-lifecycle-design.md](alert-lifecycle-design.md) — alert state machine (relevant to alert feed UI)
