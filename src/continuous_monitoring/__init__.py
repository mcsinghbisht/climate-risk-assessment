"""
Continuous Monitoring Module

Provides change detection and (in later tasks) the monitoring loop and
scheduler that tie ingestion, scoring, and alerting together on a
recurring cadence.
"""

from src.continuous_monitoring.change_detector import ChangeDetector
from src.continuous_monitoring.monitor import Monitor
from src.continuous_monitoring.scheduler import SchedulerManager

__all__ = [
    "ChangeDetector",
    "Monitor",
    "SchedulerManager",
]
