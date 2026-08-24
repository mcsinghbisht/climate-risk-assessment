"""
Pytest test suite for src/main.py (Task 34)

Run with: pytest tests/test_main_pytest.py -v

Uses fake Monitor/SchedulerManager/PortfolioReporter stand-ins (monkeypatched
directly into src.main's namespace, since it imports the classes rather than
the modules) so these tests are fast and don't depend on live APIs, a real
database initialization sequence, or real scheduler timing - CLI wiring is
what's under test here, not the components main.py orchestrates (each of
which already has its own dedicated suite).
"""

import pytest

import src.main as main_module


class TestParseArgs:
    def test_defaults_to_test_mode(self):
        args = main_module.parse_args([])
        assert args.mode == "test"
        assert args.duration is None
        assert args.interval is None

    def test_mode_run_accepted(self):
        args = main_module.parse_args(["--mode", "run"])
        assert args.mode == "run"

    def test_mode_report_accepted(self):
        args = main_module.parse_args(["--mode", "report"])
        assert args.mode == "report"

    def test_invalid_mode_rejected(self):
        with pytest.raises(SystemExit):
            main_module.parse_args(["--mode", "bogus"])

    def test_duration_and_interval_parsed_as_floats(self):
        args = main_module.parse_args(["--mode", "run", "--duration", "30", "--interval", "1.5"])
        assert args.duration == 30.0
        assert args.interval == 1.5


class FakeMonitor:
    def __init__(self, summary=None):
        self.summary = summary or {"properties_scored": 100, "new_alerts": 0, "errors": []}
        self.calls = 0

    def run_monitoring_cycle(self):
        self.calls += 1
        return self.summary


class FakeReporter:
    def __init__(self, report_text="REPORT TEXT"):
        self.report_text = report_text
        self.calls = 0

    def generate_summary_report(self):
        self.calls += 1
        return self.report_text


class FakeScheduler:
    def __init__(self, monitor=None):
        self.interval_minutes = 5
        self.started = False
        self.stopped = False
        self.cycles_run = 0
        self.cycles_failed = 0

    def start(self):
        self.started = True

    def stop(self, wait=True):
        self.stopped = True


class TestTestMode:
    def test_returns_monitor_summary(self, monkeypatch, capsys):
        fake = FakeMonitor(summary={"properties_scored": 42, "new_alerts": 1, "errors": []})
        monkeypatch.setattr(main_module, "Monitor", lambda: fake)

        result = main_module.test_mode()
        assert result == fake.summary
        assert fake.calls == 1

    def test_prints_summary_fields(self, monkeypatch, capsys):
        fake = FakeMonitor(summary={"properties_scored": 7, "errors": []})
        monkeypatch.setattr(main_module, "Monitor", lambda: fake)

        main_module.test_mode()
        captured = capsys.readouterr()
        assert "properties_scored: 7" in captured.out


class TestReportMode:
    def test_returns_report_text(self, monkeypatch, capsys):
        fake = FakeReporter(report_text="MY REPORT")
        monkeypatch.setattr(main_module, "PortfolioReporter", lambda: fake)

        result = main_module.report_mode()
        assert result == "MY REPORT"
        assert fake.calls == 1

    def test_prints_report(self, monkeypatch, capsys):
        fake = FakeReporter(report_text="PORTFOLIO SUMMARY HERE")
        monkeypatch.setattr(main_module, "PortfolioReporter", lambda: fake)

        main_module.report_mode()
        captured = capsys.readouterr()
        assert "PORTFOLIO SUMMARY HERE" in captured.out


class TestRunMode:
    def test_starts_and_stops_scheduler(self, monkeypatch):
        fake_scheduler = FakeScheduler()
        monkeypatch.setattr(main_module, "SchedulerManager", lambda: fake_scheduler)

        main_module.run_mode(interval=None, duration=0.001)  # ~0.06s
        assert fake_scheduler.started is True
        assert fake_scheduler.stopped is True

    def test_interval_override_applied(self, monkeypatch):
        fake_scheduler = FakeScheduler()
        monkeypatch.setattr(main_module, "SchedulerManager", lambda: fake_scheduler)

        main_module.run_mode(interval=2.5, duration=0.001)
        assert fake_scheduler.interval_minutes == 2.5

    def test_no_interval_override_keeps_default(self, monkeypatch):
        fake_scheduler = FakeScheduler()
        monkeypatch.setattr(main_module, "SchedulerManager", lambda: fake_scheduler)

        main_module.run_mode(interval=None, duration=0.001)
        assert fake_scheduler.interval_minutes == 5  # FakeScheduler's own default

    def test_stops_after_duration_limit(self, monkeypatch):
        fake_scheduler = FakeScheduler()
        monkeypatch.setattr(main_module, "SchedulerManager", lambda: fake_scheduler)

        import time
        start = time.monotonic()
        main_module.run_mode(interval=None, duration=0.01)  # 0.6s
        elapsed = time.monotonic() - start
        assert elapsed < 5  # returned promptly, didn't hang
        assert fake_scheduler.stopped is True


class TestMainDispatch:
    def test_main_calls_test_mode_by_default(self, monkeypatch, tmp_path):
        monkeypatch.setattr(main_module, "setup_logging", lambda: None)
        monkeypatch.setattr(main_module, "initialize_database", lambda: (True, "ok"))

        called = {"test": False}
        monkeypatch.setattr(main_module, "test_mode", lambda: called.__setitem__("test", True))

        exit_code = main_module.main([])
        assert called["test"] is True
        assert exit_code == 0

    def test_main_calls_report_mode(self, monkeypatch):
        monkeypatch.setattr(main_module, "setup_logging", lambda: None)
        monkeypatch.setattr(main_module, "initialize_database", lambda: (True, "ok"))

        called = {"report": False}
        monkeypatch.setattr(main_module, "report_mode", lambda: called.__setitem__("report", True))

        main_module.main(["--mode", "report"])
        assert called["report"] is True

    def test_main_calls_run_mode_with_parsed_args(self, monkeypatch):
        monkeypatch.setattr(main_module, "setup_logging", lambda: None)
        monkeypatch.setattr(main_module, "initialize_database", lambda: (True, "ok"))

        received = {}

        def fake_run_mode(interval, duration):
            received["interval"] = interval
            received["duration"] = duration

        monkeypatch.setattr(main_module, "run_mode", fake_run_mode)

        main_module.main(["--mode", "run", "--interval", "2", "--duration", "10"])
        assert received == {"interval": 2.0, "duration": 10.0}

    def test_main_always_sets_up_logging_and_database(self, monkeypatch):
        calls = {"logging": False, "db": False}
        monkeypatch.setattr(main_module, "setup_logging", lambda: calls.__setitem__("logging", True))
        monkeypatch.setattr(main_module, "initialize_database", lambda: calls.__setitem__("db", True) or (True, "ok"))
        monkeypatch.setattr(main_module, "test_mode", lambda: None)

        main_module.main(["--mode", "test"])
        assert calls["logging"] is True
        assert calls["db"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
