"""
Shared Risk Scoring Utilities

Small helpers reused across scorers (WildFireScorer, FloodScorer) to avoid
duplicating the same hazard_data parsing logic in each one - the same
lesson Task 13 applied to the ingestion layer, applied here to scoring.
"""

import json
from typing import Dict, Optional


def parse_weather_extras(row: Optional[Dict]) -> Dict:
    """
    Extract wind_speed, wind_direction, humidity, temperature from a weather
    hazard_data row's raw_data JSON. Only `temperature` is stored directly as
    `value` on the row itself; the rest live inside raw_data (see Task 13's
    normalize_weather).

    Args:
        row: A hazard_data row with hazard_type='weather', or None

    Returns:
        Dict with temperature, humidity, wind_speed, wind_direction (any may
        be None if row is None or the fields are missing)
    """
    if row is None:
        return {"temperature": None, "humidity": None, "wind_speed": None, "wind_direction": None}

    try:
        raw = json.loads(row.get("raw_data") or "{}")
    except (json.JSONDecodeError, TypeError):
        raw = {}

    return {
        "temperature": row.get("value"),
        "humidity": raw.get("humidity"),
        "wind_speed": raw.get("wind_speed"),
        "wind_direction": raw.get("wind_direction"),
    }


def parse_gauge_extras(row: Optional[Dict]) -> Dict:
    """
    Extract site_name and parameter_label from a USGS gauge hazard_data
    row's raw_data JSON (see Task 13's normalize_gauge).

    Args:
        row: A hazard_data row with source='USGS', or None

    Returns:
        Dict with site_name and parameter_label (may be None)
    """
    if row is None:
        return {"site_name": None, "parameter_label": None}

    try:
        raw = json.loads(row.get("raw_data") or "{}")
    except (json.JSONDecodeError, TypeError):
        raw = {}

    return {
        "site_name": raw.get("site_name"),
        "parameter_label": raw.get("parameter_label"),
    }
