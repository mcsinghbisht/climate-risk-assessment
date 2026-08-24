"""
Portfolio Manager Dashboard

High-level view of portfolio risk, geographic distribution, hotspots,
and active alerts. Read-only consumption of PortfolioAggregator and HotspotDetector.

Accessed via the main app when role is set to "Portfolio Manager".
"""

import streamlit as st
import plotly.express as px
import folium
from streamlit_folium import st_folium

from src.database import PropertyDAO, AlertDAO
from src.portfolio import PortfolioAggregator, HotspotDetector
from src.ui.config import (
    RISK_COLORS, MAP_CENTER_LAT, MAP_CENTER_LON, MAP_ZOOM_START,
    HOTSPOT_RADIUS_KM
)
from src.ui.components import render_kpi_strip, render_alerts_table, render_system_health


def main():
    st.set_page_config(page_title="Portfolio Manager", layout="wide")
    st.title("📊 Portfolio Manager Dashboard")

    # Refresh interval in sidebar
    st.sidebar.write("### Dashboard Settings")
    refresh_interval = st.sidebar.selectbox(
        "Auto-refresh interval",
        options=["Off", "30 seconds", "1 minute", "5 minutes"],
        index=2,
    )

    # Fetch data (with implicit caching via Streamlit's @st.cache_data)
    @st.cache_data(ttl=60)
    def get_portfolio_data():
        agg = PortfolioAggregator()
        return agg.get_portfolio_metrics()

    @st.cache_data(ttl=60)
    def get_hotspots():
        detector = HotspotDetector()
        return {
            "overall": detector.detect_hotspots(),
            # TODO: add hazard_type parameter to HotspotDetector in Step 2.5
            # "wildfire": detector.detect_hotspots(hazard_type="wildfire"),
            # "flood": detector.detect_hotspots(hazard_type="flood"),
        }

    @st.cache_data(ttl=60)
    def get_alerts():
        return AlertDAO().get_active_alerts()

    # Load data
    portfolio = get_portfolio_data()
    hotspots_data = get_hotspots()
    alerts = get_alerts()

    # Calculate display metrics
    metrics = {
        "total_properties": portfolio.get("total_properties", 0),
        "assessed_properties": portfolio.get("assessed_properties", 0),
        "high_critical_percent": (
            100 * (portfolio.get("high_count", 0) + portfolio.get("critical_count", 0))
            / max(portfolio.get("total_properties", 1), 1)
        ),
        "active_alerts": len(alerts),
        "freshness_minutes": portfolio.get("freshness_minutes", None),
    }

    # === KPI STRIP ===
    st.subheader("Portfolio Overview")
    render_kpi_strip(metrics)

    st.divider()

    # === RISK DISTRIBUTION CHART ===
    col1, col2 = st.columns([1.5, 1])

    with col1:
        st.subheader("Risk Level Distribution")
        risk_dist = {
            "Low": portfolio.get("low_count", 0),
            "Medium": portfolio.get("medium_count", 0),
            "High": portfolio.get("high_count", 0),
            "Critical": portfolio.get("critical_count", 0),
        }

        fig = px.pie(
            values=list(risk_dist.values()),
            names=list(risk_dist.keys()),
            color_discrete_map={k: RISK_COLORS.get(k.lower(), "#999") for k in risk_dist.keys()},
            title="Portfolio Distribution"
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Risk Statistics")
        st.metric("Average Score", f"{portfolio.get('average_score', 0):.2f}", help="0-100")
        st.metric("Median Score", f"{portfolio.get('median_score', 0):.2f}", help="0-100")
        st.metric("Max Score", f"{portfolio.get('max_score', 0):.2f}", help="0-100")
        st.metric("Min Score", f"{portfolio.get('min_score', 0):.2f}", help="0-100")

    st.divider()

    # === GEOGRAPHIC DISTRIBUTION ===
    st.subheader("Geographic Distribution (by State)")
    state_dist = portfolio.get("state_distribution", {})
    if state_dist:
        state_data = []
        for state, count in state_dist.items():
            state_data.append({
                "State": state,
                "Properties": count,
                "Avg Risk": f"{portfolio.get('average_score', 0):.1f}",
            })
        st.dataframe(state_data, use_container_width=True)
    else:
        st.info("No geographic data available yet.")

    st.divider()

    # === MAP WITH HOTSPOTS ===
    st.subheader("Geographic Hotspots & Properties")

    try:
        # Create folium map
        m = folium.Map(
            location=[MAP_CENTER_LAT, MAP_CENTER_LON],
            zoom_start=MAP_ZOOM_START,
            tiles="OpenStreetMap",
        )

        # Add property markers
        prop_dao = PropertyDAO()
        properties = prop_dao.get_all_properties()
        for prop in properties:
            lat = prop.get("latitude")
            lon = prop.get("longitude")
            if lat and lon:
                # Get latest assessment for this property to determine color
                risk_level = "low"  # placeholder; would fetch from RiskDAO in full impl
                color = RISK_COLORS.get(risk_level, "#999999")

                folium.CircleMarker(
                    location=[lat, lon],
                    radius=4,
                    popup=f"{prop.get('address', 'Unknown')}",
                    color=color,
                    fill=True,
                    fillOpacity=0.7,
                ).add_to(m)

        # Add hotspot circles
        for hotspot in hotspots_data.get("overall", []):
            avg_risk = hotspot.get("avg_risk", 0)
            # Color gradient based on avg_risk (0-100 → pale orange to deep red)
            risk_pct = min(1.0, avg_risk / 100)
            r = int(255 * risk_pct)
            g = int(150 * (1 - risk_pct))
            b = int(0)
            color = f"#{r:02x}{g:02x}{b:02x}"

            folium.Circle(
                location=[hotspot.get("center_lat"), hotspot.get("center_lon")],
                radius=hotspot.get("radius_km", HOTSPOT_RADIUS_KM) * 1000,  # convert to meters
                popup=f"Hotspot: {hotspot.get('property_count', 0)} properties, avg risk {avg_risk:.1f}",
                color=color,
                fill=True,
                fillOpacity=0.3,
                weight=2,
            ).add_to(m)

        # Render map
        st_folium(m, width=1400, height=500)

    except Exception as e:
        st.error(f"Could not render map: {e}")

    st.divider()

    # === ACTIVE ALERTS ===
    st.subheader("Active Alerts")
    if alerts:
        render_alerts_table(alerts)
    else:
        st.success("✓ No active alerts")

    st.divider()

    # === SYSTEM HEALTH ===
    render_system_health()


if __name__ == "__main__":
    main()
