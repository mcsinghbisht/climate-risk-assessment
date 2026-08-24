"""
Portfolio Module

Provides portfolio-wide risk aggregation, hotspot detection, and reporting
that sit above individual property assessments (Tasks 15-18) and the
per-property alerting/monitoring loop (Tasks 20-24).
"""

from src.portfolio.aggregator import PortfolioAggregator
from src.portfolio.hotspot_detector import HotspotDetector
from src.portfolio.reporter import PortfolioReporter

__all__ = [
    "PortfolioAggregator",
    "HotspotDetector",
    "PortfolioReporter",
]
