"""
Curated LLM Tools (Step 6)

10 safe, tested database query tools for Claude to use.
Each tool wraps an existing DAO method and returns structured JSON.

These are the "Tier 1" tools that Claude can call. They handle 80% of
expected queries. For novel questions, there's a guarded SQL fallback (Tier 2).
"""

import logging
from typing import List, Dict, Optional

from src.database import PropertyDAO, RiskDAO, AlertDAO
from src.portfolio import PortfolioAggregator, HotspotDetector

logger = logging.getLogger(__name__)


def get_portfolio_metrics() -> Dict:
    """
    Get high-level portfolio metrics: total properties, assessment status,
    risk distribution, geographic summary.

    Returns:
        Dict with keys like total_properties, assessed_properties, low_count,
        medium_count, high_count, critical_count, average_score, median_score,
        min_score, max_score, state_distribution, freshness_minutes.

    Example usage:
        data = get_portfolio_metrics()
        print(f"Portfolio: {data['total_properties']} properties,
               {data['high_count']} high/critical, avg score {data['average_score']:.1f}")
    """
    try:
        agg = PortfolioAggregator()
        metrics = agg.get_portfolio_metrics()
        logger.debug(f"get_portfolio_metrics: {metrics['total_properties']} properties")
        return metrics
    except Exception as e:
        logger.error(f"get_portfolio_metrics failed: {e}")
        return {"error": str(e)}


def get_hotspots(hazard_type: str = "overall") -> List[Dict]:
    """
    Get geographic hotspots: clusters of properties with elevated risk.

    Args:
        hazard_type: one of "overall" (default), "wildfire", or "flood".
                     Determines which risk score type is used for clustering.

    Returns:
        List of hotspot dicts, each with:
        - center_lat, center_lon: cluster center (geographic coordinates)
        - radius_km: cluster radius in kilometers
        - property_count: how many properties in this cluster
        - avg_risk: average risk score in this cluster (0-100)
        - properties: list of property_ids in this cluster

    Example usage:
        hotspots = get_hotspots("wildfire")
        for h in hotspots:
            print(f"Wildfire hotspot near {h['center_lat']},{h['center_lon']}:
                   {h['property_count']} properties, avg risk {h['avg_risk']:.1f}")
    """
    try:
        detector = HotspotDetector()
        # TODO: Pass hazard_type parameter once HotspotDetector.detect_hotspots is updated
        hotspots = detector.detect_hotspots()
        logger.debug(f"get_hotspots({hazard_type}): found {len(hotspots)} hotspots")
        return hotspots
    except Exception as e:
        logger.error(f"get_hotspots({hazard_type}) failed: {e}")
        return []


def get_active_alerts() -> List[Dict]:
    """
    Get all currently active alerts (both property-level and portfolio-level).

    Active = status is "active" (not acknowledged, stale, or resolved).

    Returns:
        List of alert dicts, each with:
        - id: unique alert ID
        - property_id: which property (None for portfolio-level alerts)
        - risk_type: "wildfire", "flood", or "portfolio"
        - risk_level: "warning" or "critical"
        - triggered_at: ISO timestamp when alert was triggered
        - status: "active", "acknowledged", "stale", or "resolved"
        - triggered_by: "absolute_threshold" or "increase_threshold"

    Example usage:
        alerts = get_active_alerts()
        critical_alerts = [a for a in alerts if a['risk_level'] == 'critical']
        print(f"Active critical alerts: {len(critical_alerts)}")
    """
    try:
        alert_dao = AlertDAO()
        alerts = alert_dao.get_active_alerts()
        logger.debug(f"get_active_alerts: found {len(alerts)} active alerts")
        return alerts
    except Exception as e:
        logger.error(f"get_active_alerts failed: {e}")
        return []


def get_alerts_for_property(property_id: int, include_resolved: bool = False) -> List[Dict]:
    """
    Get all alerts for a specific property (alert history, not just active).

    Args:
        property_id: the property to query
        include_resolved: if False (default), only return active/acknowledged/stale alerts.
                         if True, also include resolved alerts.

    Returns:
        List of alert dicts (same schema as get_active_alerts).

    Example usage:
        alerts = get_alerts_for_property(42)
        if alerts:
            print(f"Property 42: {len(alerts)} alerts")
            for a in alerts:
                print(f"  {a['risk_type']}: {a['risk_level']} ({a['status']})")
        else:
            print("Property 42: no alerts")
    """
    try:
        alert_dao = AlertDAO()
        alerts = alert_dao.get_alerts_for_property(property_id, include_resolved=include_resolved)
        logger.debug(f"get_alerts_for_property({property_id}): found {len(alerts)} alerts")
        return alerts
    except Exception as e:
        logger.error(f"get_alerts_for_property({property_id}) failed: {e}")
        return []


def get_property_risk_history(property_id: int, limit: int = 10) -> List[Dict]:
    """
    Get a property's risk assessment history (trend over time).

    Args:
        property_id: the property to query
        limit: return at most this many assessments (default 10, most recent first)

    Returns:
        List of assessment dicts, each with:
        - assessment_timestamp: ISO timestamp when assessed
        - overall_risk_score: combined wildfire + flood score (0-100)
        - wildfire_risk_score: wildfire-specific score (0-100)
        - flood_risk_score: flood-specific score (0-100)
        - risk_level: "low", "medium", "high", or "critical"
        - wildfire_factors: dict of factor scores (proximity, wind, intensity, environment)
        - flood_factors: dict of factor scores (rainfall, proximity, saturation, floodplain)

    Example usage:
        history = get_property_risk_history(42, limit=5)
        for h in history:
            print(f"{h['assessment_timestamp']}: {h['overall_risk_score']:.1f} ({h['risk_level']})")
    """
    try:
        risk_dao = RiskDAO()
        assessments = risk_dao.get_assessment_history(property_id, days=365)
        if assessments:
            assessments = assessments[:limit]
        logger.debug(f"get_property_risk_history({property_id}): found {len(assessments)} assessments")
        return assessments
    except Exception as e:
        logger.error(f"get_property_risk_history({property_id}) failed: {e}")
        return []


def get_properties_by_state(state_code: str) -> List[Dict]:
    """
    Get all properties in a given state.

    Args:
        state_code: two-letter state abbreviation (e.g., "CA", "TX", "FL")

    Returns:
        List of property dicts, each with:
        - property_id: unique ID
        - address: street address
        - state: state abbreviation
        - county: county name
        - latitude, longitude: geographic coordinates
        - is_in_wildland_urban_interface: boolean WUI flag
        - is_in_floodplain: boolean floodplain flag

    Example usage:
        ca_properties = get_properties_by_state("CA")
        print(f"California: {len(ca_properties)} properties")
    """
    try:
        prop_dao = PropertyDAO()
        properties = prop_dao.get_properties_by_state(state_code)
        logger.debug(f"get_properties_by_state({state_code}): found {len(properties)} properties")
        return properties
    except Exception as e:
        logger.error(f"get_properties_by_state({state_code}) failed: {e}")
        return []


def get_properties_by_risk_level(risk_level: str) -> List[Dict]:
    """
    Get all properties at a specific risk level.

    Args:
        risk_level: one of "low", "medium", "high", or "critical"

    Returns:
        List of property dicts (same schema as get_properties_by_state),
        with their latest risk assessment included.

    Example usage:
        critical = get_properties_by_risk_level("critical")
        print(f"Critical properties: {len(critical)}")
        for p in critical:
            print(f"  {p['address']} ({p['state']})")
    """
    try:
        prop_dao = PropertyDAO()
        properties = prop_dao.get_properties_by_risk_level(risk_level)
        logger.debug(f"get_properties_by_risk_level({risk_level}): found {len(properties)} properties")
        return properties
    except Exception as e:
        logger.error(f"get_properties_by_risk_level({risk_level}) failed: {e}")
        return []


def search_property_by_id_or_address(query: str) -> List[Dict]:
    """
    Search for properties by ID or address (fuzzy match).

    Args:
        query: search term (property ID as number or string, or partial address)

    Returns:
        List of matching property dicts (same schema as get_properties_by_state),
        up to 20 results.

    Example usage:
        results = search_property_by_id_or_address("123 main")
        for p in results:
            print(f"{p['property_id']}: {p['address']}")
    """
    try:
        prop_dao = PropertyDAO()
        all_props = prop_dao.get_all_properties()

        query_lower = str(query).lower()
        matches = [
            p for p in all_props
            if query_lower in str(p.get("property_id", "")).lower()
            or query_lower in p.get("address", "").lower()
        ]

        # Sort by relevance: exact ID match first, then address match
        matches_sorted = sorted(
            matches,
            key=lambda p: (
                0 if str(p.get("property_id")) == query else 1,
                p.get("address", ""),
            )
        )

        results = matches_sorted[:20]
        logger.debug(f"search_property_by_id_or_address({query}): found {len(results)} properties")
        return results
    except Exception as e:
        logger.error(f"search_property_by_id_or_address({query}) failed: {e}")
        return []


# === TOOL DEFINITIONS FOR CLAUDE ===

# These definitions tell Claude what each tool does and what parameters it accepts.
# Format matches Anthropic's tool_use feature.

TOOLS_DEFINITIONS = [
    {
        "name": "get_portfolio_metrics",
        "description": "Get high-level portfolio metrics: total properties, assessment status, risk distribution, geographic summary, and freshness indicators.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "get_hotspots",
        "description": "Get geographic hotspots: clusters of properties with elevated risk. Can filter by hazard type (overall, wildfire, or flood).",
        "input_schema": {
            "type": "object",
            "properties": {
                "hazard_type": {
                    "type": "string",
                    "enum": ["overall", "wildfire", "flood"],
                    "description": "Which risk type to cluster on (default: overall)",
                }
            },
            "required": [],
        },
    },
    {
        "name": "get_active_alerts",
        "description": "Get all currently active alerts (property-level and portfolio-level) that require attention.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "get_alerts_for_property",
        "description": "Get alert history for a specific property (active, acknowledged, stale, or resolved).",
        "input_schema": {
            "type": "object",
            "properties": {
                "property_id": {
                    "type": "integer",
                    "description": "The property ID to query",
                },
                "include_resolved": {
                    "type": "boolean",
                    "description": "If true, also return resolved alerts (default: false)",
                },
            },
            "required": ["property_id"],
        },
    },
    {
        "name": "get_property_risk_history",
        "description": "Get a property's risk assessment history over time, showing trends in wildfire, flood, and overall risk scores.",
        "input_schema": {
            "type": "object",
            "properties": {
                "property_id": {
                    "type": "integer",
                    "description": "The property ID to query",
                },
                "limit": {
                    "type": "integer",
                    "description": "Return at most this many recent assessments (default: 10)",
                },
            },
            "required": ["property_id"],
        },
    },
    {
        "name": "get_properties_by_state",
        "description": "Get all properties in a specific state.",
        "input_schema": {
            "type": "object",
            "properties": {
                "state_code": {
                    "type": "string",
                    "description": "Two-letter state abbreviation (e.g., CA, TX, FL)",
                }
            },
            "required": ["state_code"],
        },
    },
    {
        "name": "get_properties_by_risk_level",
        "description": "Get all properties at a specific risk level (low, medium, high, critical).",
        "input_schema": {
            "type": "object",
            "properties": {
                "risk_level": {
                    "type": "string",
                    "enum": ["low", "medium", "high", "critical"],
                    "description": "The risk level to filter by",
                }
            },
            "required": ["risk_level"],
        },
    },
    {
        "name": "search_property_by_id_or_address",
        "description": "Search for properties by ID or address. Useful when you know part of the address or property ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search term: property ID or partial address (e.g., '42' or 'main st')",
                }
            },
            "required": ["query"],
        },
    },
]


def execute_tool(tool_name: str, tool_input: Dict) -> str:
    """
    Execute a curated tool by name with the given input.

    Args:
        tool_name: name of the tool to call
        tool_input: dict of parameters for the tool

    Returns:
        JSON string with the tool's result

    Raises:
        ValueError: if tool_name is not recognized
    """
    import json

    tools_map = {
        "get_portfolio_metrics": lambda: get_portfolio_metrics(),
        "get_hotspots": lambda: get_hotspots(
            hazard_type=tool_input.get("hazard_type", "overall")
        ),
        "get_active_alerts": lambda: get_active_alerts(),
        "get_alerts_for_property": lambda: get_alerts_for_property(
            property_id=tool_input.get("property_id"),
            include_resolved=tool_input.get("include_resolved", False),
        ),
        "get_property_risk_history": lambda: get_property_risk_history(
            property_id=tool_input.get("property_id"),
            limit=tool_input.get("limit", 10),
        ),
        "get_properties_by_state": lambda: get_properties_by_state(
            state_code=tool_input.get("state_code"),
        ),
        "get_properties_by_risk_level": lambda: get_properties_by_risk_level(
            risk_level=tool_input.get("risk_level"),
        ),
        "search_property_by_id_or_address": lambda: search_property_by_id_or_address(
            query=tool_input.get("query"),
        ),
    }

    if tool_name not in tools_map:
        raise ValueError(f"Unknown tool: {tool_name}")

    try:
        result = tools_map[tool_name]()
        return json.dumps(result)
    except Exception as e:
        logger.error(f"Tool {tool_name} failed: {e}")
        return json.dumps({"error": str(e)})
