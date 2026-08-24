"""
Pytest test suite for SchedulerManager (Task 24)

Run with: pytest tests/test_scheduler_pytest.py -v

Uses fake Monitor objects (not the real one) so these tests run in
milliseconds and don't depend on live APIs or a real database - Monitor's
own orchestration is already covered by test_monitor_pytest.py (Task 23).
What this suite exercises is APScheduler wiring: does start()/stop() work,
does the interval actually fire repeatedly, is overlap prevented, and are
failures isolated per cycle.
"""

import time

import pytest

from src.continuous_monitoring.scheduler import SchedulerManager

FAST_INTERVAL_MINUTES = 0.03  # ~1.8 seconds, fast enough for tests


class CountingMonitor:
    def __init__(self):
        self.calls = 0

    def run_monitoring_cycle(self):
        self.calls += 1
        return {"properties_scored": 1, "new_alerts": 0, "errors": []}


class SlowMonitor:
    """Sleeps longer than the interval, to prove overlap protection."""
    def __init__(self, sleep_seconds):
        self.sleep_seconds = sleep_seconds
        self.calls = 0
        self.concurrent = 0
        self.max_concurrent = 0

    def run_monitoring_cycle(self):
        self.concurrent += 1
        self.max_concurrent = max(self.max_concurrent, self.concurrent)
        self.calls += 1
        time.sleep(self.sleep_seconds)
        self.concurrent -= 1
        return {"properties_scored": 0, "new_alerts": 0, "errors": []}


class FailingMonitor:
    def __init__(self):
        self.calls = 0

    def run_monitoring_cycle(self):
        self.calls += 1
        raise RuntimeError("simulated failure")


@pytest.fixture
def scheduler_factory():
    """Yields a factory for SchedulerManagers, ensuring cleanup even on test failure."""
    created = []

    def _make(monitor, interval=FAST_INTERVAL_MINUTES):
        s = SchedulerManager(monitor=monitor)
        s.interval_minutes = interval
        created.append(s)
        return s

    yield _make

    for s in created:
        if s.is_running:
            s.stop(wait=False)


class TestStartStop:
    def test_not_running_before_start(self, scheduler_factory):
        s = scheduler_factory(CountingMonitor())
        assert s.is_running is False

    def test_running_after_start(self, scheduler_factory):
        s = scheduler_factory(CountingMonitor())
        s.start()
        assert s.is_running is True

    def test_not_running_after_stop(self, scheduler_factory):
        s = scheduler_factory(CountingMonitor())
        s.start()
        s.stop()
        assert s.is_running is False

    def test_calling_start_twice_is_a_safe_noop(self, scheduler_factory):
        s = scheduler_factory(CountingMonitor())
        s.start()
        s.start()  # should log a warning, not raise
        assert s.is_running is True

    def test_calling_stop_when_not_running_is_a_safe_noop(self, scheduler_factory):
        s = scheduler_factory(CountingMonitor())
        s.stop()  # should log a warning, not raise
        assert s.is_running is False


class TestRecurringExecution:
    def test_interval_read_from_config_by_default(self):
        s = SchedulerManager(monitor=CountingMonitor())
        assert s.interval_minutes == 5  # config/settings.json alerts.alert_check_interval_minutes
        assert s.is_running is False

    def test_cycle_runs_multiple_times_on_interval(self, scheduler_factory):
        monitor = CountingMonitor()
        s = scheduler_factory(monitor)
        s.start()
        time.sleep(6)
        s.stop()
        assert monitor.calls >= 2

    def test_cycles_run_counter_tracks_successes(self, scheduler_factory):
        monitor = CountingMonitor()
        s = scheduler_factory(monitor)
        s.start()
        time.sleep(4)
        s.stop()
        assert s.cycles_run == monitor.calls
        assert s.cycles_failed == 0

    def test_last_result_reflects_most_recent_cycle(self, scheduler_factory):
        monitor = CountingMonitor()
        s = scheduler_factory(monitor)
        s.start()
        time.sleep(2.5)
        s.stop()
        assert s.last_result is not None
        assert s.last_result["properties_scored"] == 1


class TestOverlapProtection:
    def test_never_runs_two_cycles_concurrently(self, scheduler_factory):
        monitor = SlowMonitor(sleep_seconds=3)
        s = scheduler_factory(monitor, interval=FAST_INTERVAL_MINUTES)
        s.start()
        time.sleep(8)
        s.stop()
        assert monitor.max_concurrent == 1


class TestFailureIsolation:
    def test_failed_cycle_does_not_crash_scheduler(self, scheduler_factory):
        monitor = FailingMonitor()
        s = scheduler_factory(monitor)
        s.start()
        time.sleep(4)
        assert s.is_running is True  # scheduler survives repeated cycle failures
        s.stop()

    def test_failed_cycles_counted_separately(self, scheduler_factory):
        monitor = FailingMonitor()
        s = scheduler_factory(monitor)
        s.start()
        time.sleep(4)
        s.stop()
        assert s.cycles_failed >= 1
        assert s.cycles_run == 0

    def test_subsequent_successful_cycles_still_run_after_a_failure(self, scheduler_factory):
        class FlakyMonitor:
            def __init__(self):
                self.calls = 0

            def run_monitoring_cycle(self):
                self.calls += 1
                if self.calls == 1:
                    raise RuntimeError("first cycle fails")
                return {"properties_scored": 1, "new_alerts": 0, "errors": []}

        monitor = FlakyMonitor()
        s = scheduler_factory(monitor)
        s.start()
        time.sleep(6)
        s.stop()
        assert s.cycles_failed == 1
        assert s.cycles_run >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
