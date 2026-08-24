"""
Underwriter Workspace

Property-level decision support: risk factors, factor breakdown,
risk history, active alerts for a specific property.

Accessed via the main app when role is set to "Underwriter".
"""

import streamlit as st
import plotly.graph_objects as go

from src.database import PropertyDAO, RiskDAO, AlertDAO
from src.ui.config import RISK_COLORS
from src.ui.components import render_property_card, render_alerts_table, render_system_health


def render_factor_radar(factors: dict, title: str) -> None:
    """
    Render a radar/spider chart for risk factors.

    Args:
        factors: Dict with factor names and scores (0-100)
        title: Chart title (e.g., "Wildfire Factors")
    """
    if not factors:
        st.info(f"No factor data for {title}")
        return

    fig = go.Figure()

    factor_names = list(factors.keys())
    factor_values = list(factors.values())

    fig.add_trace(go.Scatterpolar(
        r=factor_values,
        theta=factor_names,
        fill='toself',
        name=title,
    ))

    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
        title=title,
        height=400,
    )

    st.plotly_chart(fig, use_container_width=True)


def render_risk_trend(assessments: list) -> None:
    """
    Render a line chart of risk score over time.

    Args:
        assessments: List of assessment dicts with 'overall_risk_score' and 'assessment_timestamp'
    """
    if not assessments:
        st.info("No assessment history available")
        return

    # Sort by timestamp
    assessments = sorted(assessments, key=lambda x: x.get("assessment_timestamp", ""))

    timestamps = [a.get("assessment_timestamp", "")[:10] for a in assessments]  # date only
    scores = [a.get("overall_risk_score", 0) for a in assessments]

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=timestamps,
        y=scores,
        mode='lines+markers',
        name='Overall Risk Score',
        line=dict(color='#1f77b4', width=2),
        marker=dict(size=6),
    ))

    fig.update_layout(
        title="Risk Score History",
        xaxis_title="Date",
        yaxis_title="Risk Score (0-100)",
        height=400,
        hovermode='x unified',
    )

    st.plotly_chart(fig, use_container_width=True)


def main():
    st.set_page_config(page_title="Underwriter", layout="wide")
    st.title("🏠 Underwriter Workspace")

    # Property search/selection in sidebar
    st.sidebar.write("### Property Lookup")
    search_input = st.sidebar.text_input(
        "Search by ID or address",
        placeholder="Type property ID or address...",
        key="property_search",
    )

    # Get all properties for autocomplete
    @st.cache_data(ttl=60)
    def get_all_properties():
        return PropertyDAO().get_all_properties()

    all_properties = get_all_properties()

    # Filter properties based on search
    if search_input:
        filtered = [
            p for p in all_properties
            if search_input.lower() in str(p.get("property_id", "")).lower()
            or search_input.lower() in p.get("address", "").lower()
        ]
    else:
        filtered = all_properties

    # Property selector
    if filtered:
        property_options = [f"{p.get('property_id')} - {p.get('address', 'Unknown')}" for p in filtered]
        selected = st.sidebar.selectbox("Select a property", property_options)

        if selected:
            # Extract property_id from selection
            prop_id = int(selected.split(" - ")[0])
            selected_property = next((p for p in filtered if p.get("property_id") == prop_id), None)
        else:
            selected_property = None
    else:
        st.sidebar.warning("No properties found")
        selected_property = None

    if not selected_property:
        st.info("👈 Select a property from the sidebar to get started")
        return

    # Fetch data for selected property
    @st.cache_data(ttl=60)
    def get_property_data(prop_id):
        risk_dao = RiskDAO()
        alert_dao = AlertDAO()

        latest = risk_dao.get_latest_assessment(prop_id)
        history = risk_dao.get_assessment_history(prop_id) if hasattr(risk_dao, 'get_assessment_history') else []
        alerts = alert_dao.get_alerts_for_property(prop_id) if hasattr(alert_dao, 'get_alerts_for_property') else []

        return {
            "latest": latest,
            "history": history,
            "alerts": alerts,
        }

    property_data = get_property_data(selected_property.get("property_id"))
    latest_assessment = property_data.get("latest")
    assessment_history = property_data.get("history", [])
    property_alerts = property_data.get("alerts", [])

    # === PROPERTY DETAILS CARD ===
    st.subheader("Property Details")
    render_property_card(selected_property, latest_assessment)

    st.divider()

    # === CURRENT RISK SCORES ===
    if latest_assessment:
        st.subheader("Current Risk Assessment")

        col1, col2, col3 = st.columns(3)

        with col1:
            wf_score = latest_assessment.get("wildfire_risk_score", 0)
            st.metric(
                "Wildfire Risk",
                f"{wf_score:.1f}",
                help="0-100 scale",
                delta=None,
            )

        with col2:
            fl_score = latest_assessment.get("flood_risk_score", 0)
            st.metric(
                "Flood Risk",
                f"{fl_score:.1f}",
                help="0-100 scale",
                delta=None,
            )

        with col3:
            overall = latest_assessment.get("overall_risk_score", 0)
            risk_level = latest_assessment.get("risk_level", "unknown").upper()
            color = RISK_COLORS.get(latest_assessment.get("risk_level", "unknown"), "#999999")
            st.markdown(f"### Overall Risk")
            st.markdown(
                f"<div style='background-color:{color}; color:white; padding:16px; border-radius:8px; text-align:center;'>"
                f"<h2>{overall:.1f}</h2>"
                f"<p>{risk_level}</p>"
                f"</div>",
                unsafe_allow_html=True,
            )

        st.divider()

        # === FACTOR BREAKDOWNS ===
        st.subheader("Risk Factor Analysis")

        col1, col2 = st.columns(2)

        with col1:
            wf_factors = latest_assessment.get("wildfire_factors", {})
            render_factor_radar(wf_factors, "Wildfire Risk Factors")

        with col2:
            fl_factors = latest_assessment.get("flood_factors", {})
            render_factor_radar(fl_factors, "Flood Risk Factors")

        st.divider()

        # === RISK EXPLANATION ===
        st.subheader("Risk Explanation")
        st.info(latest_assessment.get("wildfire_explanation", "No explanation available"))

        st.divider()

        # === RISK HISTORY ===
        st.subheader("Risk History")
        render_risk_trend(assessment_history)

    else:
        st.warning("No assessment data available for this property yet. Run a monitoring cycle first.")

    st.divider()

    # === ACTIVE ALERTS ===
    st.subheader("Active Alerts for this Property")
    if property_alerts:
        render_alerts_table(property_alerts)
    else:
        st.success("✓ No active alerts for this property")

    st.divider()

    # === SYSTEM HEALTH ===
    render_system_health()


if __name__ == "__main__":
    main()
