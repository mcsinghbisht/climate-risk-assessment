"""
Scheduled Execution (Task 24)

Runs Monitor.run_monitoring_cycle() (Task 23) automatically on a recurring
interval via APScheduler, so the continuous monitoring loop actually runs
continuously rather than needing to be invoked by hand every time.

Interval is read from config/settings.json's alerts.alert_check_interval_minutes
(already used elsewhere for the same "how often do we re-check risk" concept -
no new config key introduced).

Overlap handling: max_instances=1 + coalesce=True on the APScheduler job means
if a cycle is still running when the next one is due (e.g. ingestion took
longer than the interval), APScheduler skips starting an overlapping second
run and collapses any backlog of missed fire times into a single catch-up
run rather than queuing them all up - this is what "reschedules if one takes
longer than 5 min" means in practice, without the scheduler ever running two
cycles concurrently against the same database.
"""

import logging
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR, EVENT_JOB_MISSED

from src.config import get_config
from src.continuous_monitoring.monitor import Monitor

logger = logging.getLogger(__name__)

JOB_ID = "monitoring_cycle"
DEFAULT_INTERVAL_MINUTES = 5


class SchedulerManager:
    """Runs Monitor.run_monitoring_cycle() on a recurring interval."""

    def __init__(self, monitor: Optional[Monitor] = None):
        config = get_config()
        alerts_cfg = config.get_section("alerts")
        self.interval_minutes: float = alerts_cfg.get(
            "alert_check_interval_minutes", DEFAULT_INTERVAL_MINUTES
        )

        self.monitor = monitor or Monitor()
        self.cycles_run = 0
        self.cycles_failed = 0
        self.last_result = None

        self.scheduler = BackgroundScheduler()
        self.scheduler.add_listener(
            self._on_job_event, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR | EVENT_JOB_MISSED
        )

    def start(self) -> None:
        """Start the scheduler and begin running cycles on the configured interval."""
        if self.scheduler.running:
            logger.warning("Scheduler already running - ignoring start() call")
            return

        self.scheduler.add_job(
            self._run_cycle,
            trigger="interval",
            minutes=self.interval_minutes,
            id=JOB_ID,
            max_instances=1,   # never run two cycles concurrently
            coalesce=True,     # collapse missed fire times into one catch-up run
        )
        self.scheduler.start()
        logger.info("Scheduler started - running a monitoring cycle every %s minute(s)", self.interval_minutes)

    def stop(self, wait: bool = True) -> None:
        """Stop the scheduler gracefully. If wait=True, blocks until any in-progress cycle finishes."""
        if not self.scheduler.running:
            logger.warning("Scheduler is not running - ignoring stop() call")
            return
        self.scheduler.shutdown(wait=wait)
        logger.info("Scheduler stopped")

    @property
    def is_running(self) -> bool:
        return self.scheduler.running

    def _run_cycle(self) -> None:
        """Run one monitoring cycle, with health-check logging of the outcome."""
        try:
            result = self.monitor.run_monitoring_cycle()
            self.cycles_run += 1
            self.last_result = result
            logger.info(
                "Scheduled cycle #%d succeeded: %d properties scored, %d new alerts, %d errors",
                self.cycles_run, result.get("properties_scored", 0),
                result.get("new_alerts", 0), len(result.get("errors", [])),
            )
        except Exception as e:
            self.cycles_failed += 1
            logger.error("Scheduled cycle failed entirely: %s", e)

    def _on_job_event(self, event) -> None:
        """APScheduler event listener - logs missed fires (health-check visibility)."""
        if event.code == EVENT_JOB_MISSED:
            logger.warning(
                "Monitoring cycle scheduled for %s was missed (previous cycle still running or scheduler delayed)",
                event.scheduled_run_time,
            )


if __name__ == "__main__":
    import time
    from src.config import setup_logging

    setup_logging()

    print("=" * 60)
    print("Scheduler Manager - Task 24")
    print("=" * 60)
    print()

    scheduler = SchedulerManager()
    print(f"Interval: {scheduler.interval_minutes} minute(s)")
    scheduler.start()
    print("Scheduler started, running for 20 seconds...")
    time.sleep(20)
    scheduler.stop()
    print(f"Scheduler stopped. Cycles run: {scheduler.cycles_run}, failed: {scheduler.cycles_failed}")

    print()
    print("=" * 60)
