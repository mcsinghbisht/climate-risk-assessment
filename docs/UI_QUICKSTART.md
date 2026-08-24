# Web UI Quick Start

## Installation

Install UI dependencies (Streamlit, mapping, charts, LLM):

```bash
pip install -r requirements-ui.txt
```

This adds to your existing environment:
- `streamlit` — web framework
- `streamlit-folium` — map integration
- `plotly` — interactive charts
- `folium` — geographic mapping
- `anthropic` — Claude API client (for LLM layer, Step 6+)
- `sqlparse` — SQL validation (for LLM layer, Step 7+)

## Running the Dashboard

```bash
streamlit run app.py
```

Opens the dashboard at `http://localhost:8501`

## Features Implemented (Phase 1, Steps 1-3)

### Portfolio Manager Dashboard
- **KPI Strip** — Total properties, assessed count, % high/critical, active alerts, freshness
- **Risk Distribution Chart** — Pie chart of low/medium/high/critical breakdown
- **Risk Statistics** — Average, median, min, max scores
- **Geographic Distribution** — Properties by state
- **Map with Hotspots** — Property markers, hotspot circles (overall risk)
- **Active Alerts Table** — All active alerts with filtering
- **System Health Widget** — Collapsible status check

### Underwriter Workspace
- **Property Search** — Autocomplete search by ID or address
- **Property Card** — Address, coordinates, state, WUI/floodplain flags
- **Current Risk Scores** — Wildfire, flood, overall with visual badges
- **Factor Analysis** — Radar charts for wildfire and flood factors
- **Risk Explanation** — Template-generated or LLM-generated prose
- **Risk History** — Line chart of scores over time (last 10 assessments)
- **Property Alerts** — Active alerts for the selected property

### Shared Components
- **System Health** — Last cycle time, per-source ingestion status, error counts
- **Color-coded Risk Levels** — Green (low), yellow (medium), orange (high), red (critical)
- **Responsive Layout** — Works on desktop and mobile

## Implementation Status

**Complete:**
- ✅ Streamlit setup with multi-page routing
- ✅ Portfolio Manager dashboard (all components)
- ✅ Underwriter workspace (all components)
- ✅ Role selection in sidebar
- ✅ Color schemes and components
- ✅ Integration with existing DAOs (`PropertyDAO`, `RiskDAO`, `AlertDAO`, `PortfolioAggregator`, `HotspotDetector`)

**Next (Step 2.5 backend work):**
- 🔄 Hazard-type-specific hotspot detection (for separate wildfire/flood layers on the map)
- 🔄 System health display (pending DAO method)

**Pending (Phase 2):**
- ⏳ Hazard-type-specific hotspots
- ⏳ LLM chat interface (curated tools + guarded SQL)
- ⏳ Alert acknowledgement UI

## Troubleshooting

**"ModuleNotFoundError: No module named 'streamlit'"**
→ Run `pip install -r requirements-ui.txt`

**"No assessment data available"**
→ Run `python src/main.py --mode test` first to generate some data

**Map not rendering**
→ Check that properties have valid latitude/longitude in the database

**LLM features not working**
→ Those are Phase 2 (not yet implemented). The dashboard works fully without LLM.

## Next Steps

1. Test the app with data from a real monitoring cycle: `python src/main.py --mode test`
2. Run the dashboard: `streamlit run app.py`
3. Switch between Portfolio Manager and Underwriter roles
4. For Phase 2 (LLM), see `docs/web-ui-llm-implementation-plan.md` steps 6-9
