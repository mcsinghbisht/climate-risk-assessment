"""
UI Configuration

Constants, color schemes, and configuration for the Streamlit dashboard.
"""

# Color palette for risk levels
RISK_COLORS = {
    "low": "#2ecc71",      # green
    "medium": "#f39c12",   # orange
    "high": "#e74c3c",     # red-orange
    "critical": "#c0392b", # dark red
}

# Reverse mapping (for charts)
RISK_COLOR_SEQUENCE = ["#2ecc71", "#f39c12", "#e74c3c", "#c0392b"]

# Hotspot color gradients
WILDFIRE_HOTSPOT_COLORSCALE = [
    (0.0, "#fff8e1"),      # pale yellow
    (0.5, "#ffb300"),      # orange
    (1.0, "#d32f2f"),      # deep red
]

FLOOD_HOTSPOT_COLORSCALE = [
    (0.0, "#e3f2fd"),      # pale blue
    (0.5, "#1976d2"),      # medium blue
    (1.0, "#1a237e"),      # deep indigo
]

# Refresh rate options (seconds)
REFRESH_INTERVALS = {
    "Off": None,
    "30 seconds": 30,
    "1 minute": 60,
    "5 minutes": 300,
}

DEFAULT_REFRESH_INTERVAL = 60  # seconds

# Map settings
MAP_CENTER_LAT = 39.8283
MAP_CENTER_LON = -98.5795
MAP_ZOOM_START = 4
HOTSPOT_RADIUS_KM = 50

# Database settings
DB_PATH = "data/climate_risk.db"

# Sidebar width
SIDEBAR_WIDTH = 250
