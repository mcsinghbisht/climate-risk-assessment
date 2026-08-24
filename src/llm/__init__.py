"""
LLM Layer for Climate Risk Assessment

Provides Claude-powered query interface over the risk database:
- Curated tools (10 safe, tested DAO methods)
- Guarded SQL fallback (read-only queries with validation)
- Chat interface for Portfolio Managers and Underwriters
"""

from src.llm.tools import (
    get_portfolio_metrics,
    get_hotspots,
    get_active_alerts,
    get_alerts_for_property,
    get_property_risk_history,
    get_properties_by_state,
    get_properties_by_risk_level,
    search_property_by_id_or_address,
)

__all__ = [
    "get_portfolio_metrics",
    "get_hotspots",
    "get_active_alerts",
    "get_alerts_for_property",
    "get_property_risk_history",
    "get_properties_by_state",
    "get_properties_by_risk_level",
    "search_property_by_id_or_address",
]
