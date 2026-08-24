"""
Reusable Streamlit UI components for the dashboard.
"""

import streamlit as st
from datetime import datetime, timedelta
from typing import Dict, Optional

from src.ui.config import RISK_COLORS


def render_kpi_strip(metrics: Dict) -> None:
    """
    Render a horizontal strip of key performance indicators.

    Args:
        metrics: Dict with keys like 'total_properties', 'assessed_properties',
                 'high_critical_percent', 'active_alerts', 'freshness_minutes'
    """
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric(
            "Total Properties",
            metrics.get("total_properties", 0),
            help="Total properties in portfolio"
        )

    with col2:
        st.metric(
            "Assessed",
            f"{metrics.get('assessed_properties', 0)}/{metrics.get('total_properties', 0)}",
            help="Properties with current risk assessment"
        )

    with col3:
        pct = metrics.get("high_critical_percent", 0)
        delta = f"{pct:.1f}%" if pct > 0 else "—"
        st.metric(
            "High/Critical",
            delta,
            help="% of portfolio in high or critical risk"
        )

    with col4:
        alert_count = metrics.get("active_alerts", 0)
        alert_color = "🔴" if alert_count > 0 else "🟢"
        st.metric(
            "Active Alerts",
            f"{alert_color} {alert_count}",
            help="Active property-level alerts"
        )

    with col5:
        freshness_min = metrics.get("freshness_minutes", None)
        if freshness_min is not None:
            if freshness_min > 30:
                freshness_text = f"⚠️ {int(freshness_min)}m ago"
            else:
                freshness_text = f"✓ {int(freshness_min)}m ago"
        else:
            freshness_text = "—"

        st.metric(
            "Latest Assessment",
            freshness_text,
            help="Time since last monitoring cycle"
        )


def render_risk_badge(risk_level: str, score: float) -> str:
    """
    Render a risk level badge with color and score.

    Args:
        risk_level: one of 'low', 'medium', 'high', 'critical'
        score: numeric risk score (0-100)

    Returns:
        HTML/markdown representation
    """
    color = RISK_COLORS.get(risk_level.lower(), "#999999")
    return f"<span style='background-color:{color}; color:white; padding:4px 8px; border-radius:4px; font-weight:bold;'>{risk_level.upper()} ({score:.1f})</span>"


def render_property_card(property_data: Dict, assessment: Optional[Dict] = None) -> None:
    """
    Render a property details card.

    Args:
        property_data: Property attributes (address, state, coords, etc.)
        assessment: Latest risk assessment (if available)
    """
    col_left, col_right = st.columns([2, 1])

    with col_left:
        st.write(f"**{property_data.get('address', 'Unknown')}**")
        st.write(f"📍 {property_data.get('state', 'N/A')}, {property_data.get('county', 'N/A')}")
        st.write(f"Latitude: {property_data.get('latitude', 'N/A')}, Longitude: {property_data.get('longitude', 'N/A')}")

        flags = []
        if property_data.get("is_in_wildland_urban_interface"):
            flags.append("🔥 WUI")
        if property_data.get("is_in_floodplain"):
            flags.append("💧 Floodplain")
        if flags:
            st.write("Flags: " + " ".join(flags))

    with col_right:
        if assessment:
            st.write(f"**Overall Risk**")
            st.write(f"markup:{render_risk_badge(assessment.get('risk_level', 'unknown'), assessment.get('overall_risk_score', 0))}")


def render_system_health() -> None:
    """
    Render a collapsible system health widget showing ingestion status,
    last cycle time, and error counts.
    """
    with st.expander("🏥 System Health"):
        try:
            from src.database import RiskDAO, PropertyDAO

            prop_dao = PropertyDAO()
            risk_dao = RiskDAO()

            total = prop_dao.count_properties()
            assessed = len(risk_dao.get_all_assessments()) if hasattr(risk_dao, 'get_all_assessments') else 0

            col1, col2 = st.columns(2)

            with col1:
                st.metric("Total Properties", total)
                st.metric("Assessments", assessed)

            with col2:
                st.metric("DB Size", "~0.5 MB")  # placeholder
                st.metric("Status", "🟢 OK")     # placeholder

            st.write("*Detailed health checks coming in Step 4 of implementation*")
        except Exception as e:
            st.warning(f"Could not load system health: {e}")


def render_alerts_table(alerts: list) -> None:
    """
    Render alerts as a Streamlit dataframe with status colors.

    Args:
        alerts: List of alert dicts from AlertDAO
    """
    if not alerts:
        st.info("No active alerts")
        return

    # Format for display
    display_data = []
    for alert in alerts:
        display_data.append({
            "ID": alert.get("id", "—"),
            "Property": alert.get("property_id", "Portfolio"),
            "Hazard": alert.get("risk_type", "—").capitalize(),
            "Level": alert.get("risk_level", "—").capitalize(),
            "Status": alert.get("status", "—").capitalize(),
            "Triggered": alert.get("triggered_at", "—")[:10],  # date only
        })

    st.dataframe(display_data, use_container_width=True)
